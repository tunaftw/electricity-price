"""ENTSO-E Transparency Platform API client.

Provides access to actual generation data (solar, wind), day-ahead prices,
and installed capacity for the Swedish (SE1-SE4) and Danish (DK1, DK2)
bidding zones.

Curve types: ENTSO-E publishes most series with ``curveType`` A03
("variable sized block"), where a Point that repeats the previous value is
OMITTED — the previous value holds until the next Point or the end of the
Period. Both parsers expand A03 Periods to one row per resolution step using
the Period's ``timeInterval`` (e.g. a 96-slot price day may carry 95 Points;
a solar month may carry only the daylight Points because the night zeros
collapse into one Point per night).

API documentation: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
"""

from __future__ import annotations

import csv
import os
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator

import requests

from .config import (
    ENTSOE_DATA_DIR,
    HTTP_TIMEOUT_DEFAULT,
    PROJECT_ROOT,
    RAW_DIR,
    SWEDEN_TZ,
    parse_iso,
)
from .http_client import NonRetryableAPIError, rate_limited, with_retry

# ENTSO-E API configuration
ENTSOE_BASE_URL = "https://web-api.tp.entsoe.eu/api"


class EntsoeAuthenticationError(NonRetryableAPIError):
    """Raised when the ENTSO-E API rejects the configured security token."""


class EntsoeRequestError(Exception):
    """HTTP/transport error from ENTSO-E with the security token redacted.

    ``requests`` puts the full URL (including ``securityToken=...``) in its
    exception messages; those end up in stdout and in
    ``Resultat/logs/failed_chunks.csv``. Every error raised from
    ``fetch_entsoe_data`` goes through ``_redact_token`` first.
    """


_TOKEN_RE = re.compile(r"(securityToken=)[^&\s'\"]+")


def _redact_token(text: str) -> str:
    """Strip the ENTSO-E security token from an error message / URL."""
    return _TOKEN_RE.sub(r"\1***", text or "")


def _load_env_file() -> dict[str, str]:
    """Load environment variables from .env file if it exists."""
    env_path = PROJECT_ROOT / ".env"
    env_vars = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def _get_token() -> str:
    """Get ENTSO-E token from environment or .env file."""
    # First check environment variable
    token = os.environ.get("ENTSOE_TOKEN", "")
    if token:
        return token
    # Fall back to .env file
    env_vars = _load_env_file()
    return env_vars.get("ENTSOE_TOKEN", "")


# Security token (loaded lazily)
ENTSOE_TOKEN = _get_token()

# Bidding zone EIC codes
SWEDISH_ZONES = {
    "SE1": "10Y1001A1001A44P",
    "SE2": "10Y1001A1001A45N",
    "SE3": "10Y1001A1001A46L",
    "SE4": "10Y1001A1001A47J",
}
DANISH_ZONES = {
    "DK1": "10YDK-1--------W",
    "DK2": "10YDK-2--------M",
}
# All zones the client can query. Library defaults (download_all_generation)
# stay Swedish-only; DK is opt-in via explicit zones.
ENTSOE_ZONES = {**SWEDISH_ZONES, **DANISH_ZONES}
ENTSOE_ZONE_BY_EIC = {code: zone for zone, code in ENTSOE_ZONES.items()}

# Document types
DOCUMENT_TYPES = {
    "actual_generation": "A75",  # Actual generation per type
    "day_ahead_prices": "A44",  # Day-ahead prices
    "actual_load": "A65",  # Actual total load
    "installed_capacity": "A68",  # Installed generation capacity aggregated
}

# Process types
PROCESS_TYPES = {
    "realised": "A16",
    "day_ahead": "A01",
    "year_ahead": "A33",
}

# PSR (Production Source) types - generation sources
PSR_TYPES = {
    "solar": "B16",
    "wind_offshore": "B18",
    "wind_onshore": "B19",
    "hydro_run_of_river": "B11",
    "hydro_water_reservoir": "B12",
    "nuclear": "B14",
    "fossil_gas": "B04",
    "fossil_hard_coal": "B05",
    "biomass": "B01",
    "other": "B20",
}

# Reverse mapping for parsing
PSR_TYPE_NAMES = {v: k for k, v in PSR_TYPES.items()}

# Data directory
ENTSOE_DIR = ENTSOE_DATA_DIR

# Data availability (approximate start dates for Swedish zones)
ENTSOE_EARLIEST_DATES = {
    "actual_generation": date(2015, 1, 1),
    "day_ahead_prices": date(2015, 1, 1),
    "actual_load": date(2015, 1, 1),
    "installed_capacity": date(2015, 1, 1),
}

# XML namespace
NS = {"ns": "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0"}
NS_PRICE = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}

# Resolution strings seen in ENTSO-E documents -> minutes
_RESOLUTION_MINUTES = {
    "PT15M": 15,
    "PT30M": 30,
    "PT60M": 60,
    "PT1H": 60,
}


def _format_entsoe_date(dt: datetime) -> str:
    """Format datetime for ENTSO-E API (yyyyMMddHHmm in UTC)."""
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y%m%d%H%M")


def _format_date_range(start: date, end: date) -> tuple[str, str]:
    """Format date range for API query (start at 00:00, end at 00:00 next day)."""
    start_dt = datetime(start.year, start.month, start.day, 0, 0, tzinfo=timezone.utc)
    # End is exclusive, so we add one day
    end_dt = datetime(end.year, end.month, end.day, 0, 0, tzinfo=timezone.utc) + timedelta(days=1)
    return _format_entsoe_date(start_dt), _format_entsoe_date(end_dt)


def _local_day_bounds_utc(start: date, end: date) -> tuple[datetime, datetime]:
    """UTC instants for local (Europe/Stockholm) midnight of ``start`` and of
    the day after ``end``. DK and SE share the CET/CEST timezone, and the
    day-ahead market day is the local calendar day."""
    start_local = datetime(start.year, start.month, start.day, tzinfo=SWEDEN_TZ)
    nxt = end + timedelta(days=1)
    end_local = datetime(nxt.year, nxt.month, nxt.day, tzinfo=SWEDEN_TZ)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _format_local_date_range(start: date, end: date) -> tuple[str, str]:
    """Format a local-day date range (inclusive ``end``) for the API."""
    start_utc, end_utc = _local_day_bounds_utc(start, end)
    return _format_entsoe_date(start_utc), _format_entsoe_date(end_utc)


def _extract_acknowledgement_reason(xml_text: str) -> str | None:
    """Extract ENTSO-E acknowledgement reason text from an error response."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    for elem in root.iter():
        if elem.tag.endswith("text") and elem.text:
            return elem.text.strip()
    return None


@with_retry()
@rate_limited()
def fetch_entsoe_data(
    document_type: str,
    zone: str,
    start_date: date,
    end_date: date,
    psr_type: str | None = None,
    process_type: str = "realised",
    token: str | None = None,
) -> str | None:
    """
    Fetch data from ENTSO-E Transparency Platform API.

    Args:
        document_type: Type of document ("actual_generation", "day_ahead_prices", etc.)
        zone: Bidding zone ("SE1".."SE4", "DK1", "DK2")
        start_date: Start date
        end_date: End date (inclusive). Generation/load/capacity queries use
            UTC day bounds; day-ahead prices use local (CET/CEST) day bounds
            so a chunk maps exactly onto whole market days.
        psr_type: Production source type for generation data ("solar", "wind_onshore", etc.)
        process_type: Process type ("realised", "day_ahead")
        token: API security token (defaults to ENTSOE_TOKEN env var)

    Returns:
        XML content as string, or None if ENTSO-E reports no matching data.

    Raises:
        EntsoeAuthenticationError: bad token (not retried).
        EntsoeRequestError: any other HTTP/transport error (token redacted).
    """
    token = token or ENTSOE_TOKEN
    if not token:
        raise ValueError("ENTSO-E API token required. Set ENTSOE_TOKEN environment variable.")

    if zone not in ENTSOE_ZONES:
        raise ValueError(f"Unknown zone: {zone}. Use: {list(ENTSOE_ZONES.keys())}")

    if document_type not in DOCUMENT_TYPES:
        raise ValueError(f"Unknown document type: {document_type}. Use: {list(DOCUMENT_TYPES.keys())}")

    if document_type == "day_ahead_prices":
        period_start, period_end = _format_local_date_range(start_date, end_date)
    else:
        period_start, period_end = _format_date_range(start_date, end_date)
    zone_code = ENTSOE_ZONES[zone]

    params = {
        "securityToken": token,
        "documentType": DOCUMENT_TYPES[document_type],
        "periodStart": period_start,
        "periodEnd": period_end,
    }

    # Add zone parameters based on document type
    if document_type == "actual_generation":
        params["processType"] = PROCESS_TYPES[process_type]
        params["in_Domain"] = zone_code
        if psr_type:
            if psr_type not in PSR_TYPES:
                raise ValueError(f"Unknown PSR type: {psr_type}. Use: {list(PSR_TYPES.keys())}")
            params["psrType"] = PSR_TYPES[psr_type]
    elif document_type == "day_ahead_prices":
        params["in_Domain"] = zone_code
        params["out_Domain"] = zone_code
    elif document_type == "actual_load":
        params["processType"] = PROCESS_TYPES[process_type]
        params["outBiddingZone_Domain"] = zone_code
    elif document_type == "installed_capacity":
        params["processType"] = PROCESS_TYPES.get("year_ahead", "A33")
        params["in_Domain"] = zone_code
        if psr_type and psr_type in PSR_TYPES:
            params["psrType"] = PSR_TYPES[psr_type]

    try:
        response = requests.get(ENTSOE_BASE_URL, params=params, timeout=HTTP_TIMEOUT_DEFAULT)
    except requests.RequestException as e:
        # requests' messages embed the URL incl. securityToken — redact.
        raise EntsoeRequestError(
            f"{type(e).__name__}: {_redact_token(str(e))}"
        ) from None

    # Handle common error responses
    if response.status_code in {401, 403}:
        reason = _extract_acknowledgement_reason(response.text) or response.text.strip()
        reason = reason.rstrip(".")
        detail = f": {reason}" if reason else ""
        raise EntsoeAuthenticationError(
            "ENTSO-E authentication failed"
            f"{detail}. Check ENTSOE_TOKEN in .env or pass --token."
        )

    if response.status_code == 400:
        # No data available for this query
        if "No matching data found" in response.text:
            return None

    if response.status_code == 429:
        raise EntsoeRequestError("Rate limit exceeded (HTTP 429). Wait 10 minutes before retrying.")

    if response.status_code >= 400:
        reason = _extract_acknowledgement_reason(response.text) or (
            getattr(response, "reason", "") or ""
        )
        raise EntsoeRequestError(
            _redact_token(f"HTTP {response.status_code}: {reason}".strip())
        )

    return response.text


# ---------------------------------------------------------------------------
# XML parsing (namespace-agnostic, A03 gap filling)
# ---------------------------------------------------------------------------

def _local(tag: str) -> str:
    """Local tag name without the ``{namespace}`` prefix."""
    return tag.rsplit("}", 1)[-1]


def _child(elem: ET.Element, name: str) -> ET.Element | None:
    """First direct child with local tag ``name`` (namespace-agnostic)."""
    for c in elem:
        if _local(c.tag) == name:
            return c
    return None


def _children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in elem if _local(c.tag) == name]


def _child_text(elem: ET.Element, name: str) -> str | None:
    c = _child(elem, name)
    if c is None or c.text is None:
        return None
    return c.text.strip()


def _descendants(elem: ET.Element, name: str) -> list[ET.Element]:
    return [e for e in elem.iter() if _local(e.tag) == name]


def _parse_resolution_minutes(text: str | None) -> int:
    """'PT15M' -> 15, 'PT60M'/'PT1H' -> 60. Defaults to 60."""
    if not text:
        return 60
    text = text.strip()
    if text in _RESOLUTION_MINUTES:
        return _RESOLUTION_MINUTES[text]
    m = re.fullmatch(r"PT(\d+)M", text)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"PT(\d+)H", text)
    if m:
        return int(m.group(1)) * 60
    return 60


def _iter_period_values(
    period: ET.Element,
    value_tag: str,
    curve_type: str | None,
) -> Iterator[tuple[datetime, int, float]]:
    """Yield ``(utc_start, resolution_minutes, value)`` for one Period.

    curveType A03 ("variable sized block"): a Point is only published when
    the value changes; each Point's value holds until the next Point's
    position, and the last one until the end of ``timeInterval``. Omitted
    positions are forward-filled here so the output has one row per
    resolution step.

    curveType A01 (or missing): fixed-size blocks — only the Points that are
    actually present are emitted (a missing position is a real data gap).
    """
    interval = _child(period, "timeInterval")
    start_text = _child_text(interval, "start") if interval is not None else None
    if start_text is None:
        # Legacy / malformed documents: fall back to any <start> below Period.
        starts = _descendants(period, "start")
        start_text = starts[0].text.strip() if starts and starts[0].text else None
    if start_text is None:
        return
    start = parse_iso(start_text)
    end_text = _child_text(interval, "end") if interval is not None else None
    end = parse_iso(end_text) if end_text else None

    resolution = _parse_resolution_minutes(_child_text(period, "resolution"))
    step = timedelta(minutes=resolution)

    points: dict[int, float] = {}
    for point in _children(period, "Point"):
        pos_text = _child_text(point, "position")
        val_text = _child_text(point, value_tag)
        if pos_text is None or val_text is None:
            continue
        points[int(pos_text)] = float(val_text)
    if not points:
        return

    if (curve_type or "").strip() == "A03":
        if end is not None:
            n_slots = int((end - start) / step)
        else:
            n_slots = max(points)
        value = None
        for pos in range(1, n_slots + 1):
            if pos in points:
                value = points[pos]
            if value is None:
                # A03 should always start at position 1; never invent data
                # before the first published point.
                continue
            yield start + step * (pos - 1), resolution, value
    else:
        for pos in sorted(points):
            yield start + step * (pos - 1), resolution, points[pos]


def _root_or_none(xml_content: str) -> ET.Element | None:
    try:
        return ET.fromstring(xml_content)
    except ET.ParseError:
        return None


def parse_generation_xml(xml_content: str) -> Iterator[dict]:
    """
    Parse actual generation XML (A75) from ENTSO-E.

    A03 curves (omitted repeated values) are forward-filled to one row per
    resolution step — see ``_iter_period_values``.

    Yields:
        Dict with time_start (UTC ISO), zone, psr_type, generation_mw,
        resolution_minutes
    """
    root = _root_or_none(xml_content)
    if root is None:
        return

    for ts in _descendants(root, "TimeSeries"):
        psr_elems = _descendants(ts, "psrType")
        psr_code = psr_elems[0].text.strip() if psr_elems and psr_elems[0].text else "unknown"
        psr_name = PSR_TYPE_NAMES.get(psr_code, psr_code)

        in_domain = _child_text(ts, "inBiddingZone_Domain.mRID")
        zone = ENTSOE_ZONE_BY_EIC.get(in_domain) if in_domain else None
        curve_type = _child_text(ts, "curveType")

        for period in _descendants(ts, "Period"):
            for point_time, resolution, quantity in _iter_period_values(
                period, "quantity", curve_type
            ):
                yield {
                    "time_start": point_time.isoformat(),
                    "zone": zone,
                    "psr_type": psr_name,
                    "generation_mw": quantity,
                    "resolution_minutes": resolution,
                }


def parse_prices_xml(xml_content: str) -> Iterator[dict]:
    """
    Parse day-ahead prices XML (A44) from ENTSO-E.

    A44 is published as curveType A03: consecutive equal prices are omitted
    (e.g. 95 of 96 quarter-hours present). They are forward-filled here.

    Yields:
        Dict with time_start (UTC ISO), zone, price_eur_mwh, resolution_minutes
    """
    root = _root_or_none(xml_content)
    if root is None:
        return

    for ts in _descendants(root, "TimeSeries"):
        in_domain = _child_text(ts, "in_Domain.mRID")
        zone = ENTSOE_ZONE_BY_EIC.get(in_domain) if in_domain else None
        curve_type = _child_text(ts, "curveType")

        for period in _descendants(ts, "Period"):
            for point_time, resolution, price in _iter_period_values(
                period, "price.amount", curve_type
            ):
                yield {
                    "time_start": point_time.isoformat(),
                    "zone": zone,
                    "price_eur_mwh": price,
                    "resolution_minutes": resolution,
                }


def dedupe_price_records(records: Iterable[dict]) -> list[dict]:
    """Collapse overlapping price records to one series at the finest resolution.

    Around the 15-min MTU go-live ENTSO-E can return both a PT60M and a
    PT15M TimeSeries for the same market day. Keep the finest resolution for
    any instant covered by it and drop coarser records that overlap it.
    Duplicate (time_start, resolution) pairs keep the last occurrence.

    Returns records sorted by UTC start.
    """
    by_key: dict[tuple[str, int], dict] = {}
    for rec in records:
        by_key[(rec["time_start"], int(rec["resolution_minutes"]))] = rec

    items = sorted(
        ((parse_iso(ts), res, rec) for (ts, res), rec in by_key.items()),
        key=lambda x: (x[1], x[0]),  # finest resolution claims its slots first
    )
    covered: set[int] = set()  # epoch minutes already claimed
    kept: list[tuple[datetime, dict]] = []
    for start, res, rec in items:
        first_minute = int(start.timestamp()) // 60
        minutes = range(first_minute, first_minute + res)
        if any(m in covered for m in minutes):
            continue
        covered.update(minutes)
        kept.append((start, rec))

    kept.sort(key=lambda x: x[0])
    return [rec for _, rec in kept]


def get_generation_csv_path(zone: str, psr_type: str, year: int) -> Path:
    """Get CSV file path for generation data."""
    gen_dir = ENTSOE_DIR / "generation" / zone
    gen_dir.mkdir(parents=True, exist_ok=True)
    return gen_dir / f"{psr_type}_{year}.csv"


def get_generation_fieldnames() -> list[str]:
    """Get CSV fieldnames for generation data."""
    return ["time_start", "zone", "psr_type", "generation_mw", "resolution_minutes"]


def get_latest_timestamp(zone: str, psr_type: str) -> datetime | None:
    """
    Get the latest timestamp from existing ENTSO-E data for a zone/type.

    Checks all year files and returns the most recent timestamp found.

    Args:
        zone: Bidding zone ("SE1".."SE4", "DK1", "DK2")
        psr_type: Production source type ("solar", "wind_onshore", etc.)

    Returns:
        Latest timestamp as datetime, or None if no data exists
    """
    gen_dir = ENTSOE_DIR / "generation" / zone
    if not gen_dir.exists():
        return None

    # Find all year files for this psr_type
    pattern = f"{psr_type}_*.csv"
    year_files = sorted(gen_dir.glob(pattern))

    if not year_files:
        return None

    # Walk newest → oldest until we find a file with data, so an empty
    # (header-only) latest-year file doesn't force a full re-download
    # (jfr storage.py).
    for latest_file in reversed(year_files):
        last_ts = None
        with open(latest_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                last_ts = row["time_start"]
        if last_ts:
            # Parse ISO format timestamp (handles both Z and +00:00 formats)
            ts_str = last_ts.replace("Z", "+00:00")
            return datetime.fromisoformat(ts_str)

    return None


def save_generation_data(zone: str, psr_type: str, records: list[dict], year: int) -> int:
    """
    Save generation data to CSV file.

    Returns:
        Number of records saved
    """
    if not records:
        return 0

    csv_path = get_generation_csv_path(zone, psr_type, year)
    fieldnames = get_generation_fieldnames()

    # Read existing data
    existing = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing[row["time_start"]] = row

    # Merge new records
    for record in records:
        existing[record["time_start"]] = record

    # Sort and write
    sorted_records = sorted(existing.values(), key=lambda x: x["time_start"])

    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_records)
    os.replace(tmp, csv_path)

    return len(records)


# Sub-chunk size used when a monthly request fails (e.g. a sporadic HTTP 400).
FALLBACK_CHUNK_DAYS = 7


def _describe_error(exc: BaseException) -> str:
    """Readable, token-free message for a failed chunk.

    ``with_retry`` (tenacity, no ``reraise``) raises ``RetryError`` whose
    str() is just ``RetryError[<Future ...>]``; unwrap to the last attempt's
    real exception so failed_chunks.csv says *why* (e.g. the HTTP 400 text).
    """
    last_attempt = getattr(exc, "last_attempt", None)
    if last_attempt is not None:
        inner = last_attempt.exception()
        if inner is not None:
            exc = inner
    return _redact_token(str(exc) or type(exc).__name__)


def _month_chunks(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Yield (chunk_start, chunk_end) calendar-month pieces of [start, end]."""
    current = start
    while current <= end:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        yield current, min(next_month - timedelta(days=1), end)
        current = next_month


def _fetch_with_fallback(
    fetch,
    chunk_start: date,
    chunk_end: date,
    verbose: bool = True,
    fallback_days: int = FALLBACK_CHUNK_DAYS,
) -> tuple[list[dict], list[str]]:
    """Run ``fetch(start, end)``; on failure retry in ``fallback_days`` pieces.

    Returns ``(records, failed_chunk_messages)``. Authentication errors are
    not split (they would fail identically for every piece).
    """
    try:
        records = fetch(chunk_start, chunk_end)
        if verbose:
            print(f"{len(records)} records" if records else "no data")
        return records, []
    except NonRetryableAPIError as e:
        msg = _describe_error(e)
        if verbose:
            print(f"error: {msg}")
        return [], [f"{chunk_start}..{chunk_end}: {msg}"]
    except Exception as e:  # noqa: BLE001 — logged + retried in pieces below
        msg = _describe_error(e)
        if (chunk_end - chunk_start).days < fallback_days:
            if verbose:
                print(f"error: {msg}")
            return [], [f"{chunk_start}..{chunk_end}: {msg}"]
        if verbose:
            print(f"error: {msg} — retrying in {fallback_days}-day pieces...", end=" ", flush=True)

    records: list[dict] = []
    failures: list[str] = []
    piece_start = chunk_start
    while piece_start <= chunk_end:
        piece_end = min(piece_start + timedelta(days=fallback_days - 1), chunk_end)
        try:
            records.extend(fetch(piece_start, piece_end))
        except Exception as e:  # noqa: BLE001
            failures.append(f"{piece_start}..{piece_end}: {_describe_error(e)}")
        piece_start = piece_end + timedelta(days=1)
    if verbose:
        if failures:
            print(f"{len(records)} records, {len(failures)} piece(s) still failing:")
            for msg in failures:
                print(f"    - {msg}")
        else:
            print(f"{len(records)} records (recovered)")
    return records, failures


def download_generation(
    zone: str,
    psr_type: str,
    start_date: date | None = None,
    end_date: date | None = None,
    token: str | None = None,
    verbose: bool = True,
    force: bool = False,
) -> dict:
    """
    Download actual generation data for a specific zone and source type.

    Args:
        zone: Bidding zone ("SE1".."SE4", "DK1", "DK2")
        psr_type: Production source type ("solar", "wind_onshore", etc.)
        start_date: Start date (default: day after latest existing data, or 2015-01-01)
        end_date: End date (default: yesterday)
        token: API security token
        verbose: Print progress
        force: If True, ignore existing data and download from earliest date

    Returns:
        Dict with download statistics
    """
    if start_date is None:
        if force:
            # Force full download from earliest date
            start_date = ENTSOE_EARLIEST_DATES["actual_generation"]
        else:
            # Check for existing data and continue from where we left off
            latest = get_latest_timestamp(zone, psr_type)
            if latest:
                start_date = latest.date() + timedelta(days=1)
                if verbose:
                    print(f"  Found existing data up to {latest.date()}, starting from {start_date}")
            else:
                start_date = ENTSOE_EARLIEST_DATES["actual_generation"]

    if end_date is None:
        end_date = date.today() - timedelta(days=1)

    if verbose:
        print(f"Downloading {psr_type} generation for {zone} from {start_date} to {end_date}")

    total_records = 0
    failed_chunks: list[str] = []

    def fetch_chunk(chunk_start: date, chunk_stop: date) -> list[dict]:
        xml_content = fetch_entsoe_data(
            document_type="actual_generation",
            zone=zone,
            start_date=chunk_start,
            end_date=chunk_stop,
            psr_type=psr_type,
            token=token,
        )
        return list(parse_generation_xml(xml_content)) if xml_content else []

    # Download in monthly chunks (API has limits on query size); a failing
    # month is retried in smaller sub-chunks before it is logged as a gap.
    for chunk_start, chunk_end in _month_chunks(start_date, end_date):
        if verbose:
            print(f"  {chunk_start} to {chunk_end}...", end=" ", flush=True)

        records, chunk_failures = _fetch_with_fallback(
            fetch_chunk, chunk_start, chunk_end, verbose=verbose
        )
        failed_chunks.extend(chunk_failures)

        # Group by (UTC) year and save
        by_year: dict[int, list[dict]] = {}
        for record in records:
            ts = datetime.fromisoformat(record["time_start"])
            by_year.setdefault(ts.year, []).append(record)

        for year, year_records in by_year.items():
            saved = save_generation_data(zone, psr_type, year_records, year)
            total_records += saved

    if verbose:
        print(f"Total: {total_records} records")
        if failed_chunks:
            print(f"  WARNING: {len(failed_chunks)} chunks failed:")
            for msg in failed_chunks:
                print(f"    - {msg}")

    return {
        "zone": zone,
        "psr_type": psr_type,
        "start_date": start_date,
        "end_date": end_date,
        "total_records": total_records,
        "failed_chunks": failed_chunks,
    }


def download_all_generation(
    zones: list[str] | None = None,
    psr_types: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    token: str | None = None,
    verbose: bool = True,
    force: bool = False,
) -> list[dict]:
    """
    Download generation data for multiple zones and source types.

    Args:
        zones: List of zones (default: the Swedish zones SE1-SE4; DK1/DK2
            are opt-in)
        psr_types: List of PSR types (default: solar and wind)
        start_date: Start date
        end_date: End date
        token: API token
        verbose: Print progress
        force: If True, ignore existing data and download from earliest date

    Returns:
        List of download statistics per zone/type
    """
    if zones is None:
        zones = list(SWEDISH_ZONES.keys())

    if psr_types is None:
        psr_types = ["solar", "wind_onshore"]

    results = []
    for zone in zones:
        for psr_type in psr_types:
            result = download_generation(
                zone=zone,
                psr_type=psr_type,
                start_date=start_date,
                end_date=end_date,
                token=token,
                verbose=verbose,
                force=force,
            )
            results.append(result)

    return results


# ---------------------------------------------------------------------------
# Day-ahead prices (A44) -> spotpriser-format CSV
# ---------------------------------------------------------------------------
#
# DK1/DK2 are stored exactly like the Swedish elprisetjustnu files so
# downstream code can treat zones uniformly:
#
#   Resultat/marknadsdata/spotpriser/DK1/YYYY.csv
#   time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR
#   2025-10-01T00:00:00+02:00,2025-10-01T00:15:00+02:00,1.13...,0.1026,11.0...
#
# * time_start/time_end: Europe/Stockholm offset ISO (DK is the same tz).
#   Files are bucketed by LOCAL year, like the Swedish ones.
# * EUR_per_kWh = EUR/MWh / 1000 (5 decimals, same as elprisetjustnu).
# * EXR (SEK per EUR) is taken per local date from the SE3 file (the
#   Swedish files carry the ECB rate elprisetjustnu uses);
#   SEK_per_kWh = EUR/MWh * EXR / 1000. If SE3 has no EXR for the date yet
#   the two columns are left empty and filled by ``backfill_exr`` on a later
#   run once SE3 has caught up.
# * Native resolution: 60 min until the 15-min MTU go-live (2025-10-01),
#   then 15 min. data/quarterly/ is derived by elpris.processing as for SE.
#
# Swedish zones can be fetched too, but are written to
# Resultat/marknadsdata/entsoe/prices/<zone>/ so the elprisetjustnu files
# (the canonical Swedish source) are never overwritten.

PRICE_CSV_FIELDS = ["time_start", "time_end", "SEK_per_kWh", "EUR_per_kWh", "EXR"]

# Spot price root (same as elpris.storage / elpris.processing RAW_DIR).
SPOT_DIR = RAW_DIR

# Zone whose files provide the per-day EXR (SEK/EUR).
EXR_SOURCE_ZONE = "SE3"

# First date fetched on a fresh (no data) DK price download.
PRICE_HISTORY_START = date(2022, 1, 1)


def get_price_dir(zone: str) -> Path:
    """Directory for a zone's ENTSO-E day-ahead price files.

    DK zones live next to the Swedish spot files; SE zones go to a separate
    ENTSO-E folder so elprisetjustnu data is never clobbered.
    """
    if zone in DANISH_ZONES:
        return SPOT_DIR / zone
    return ENTSOE_DIR / "prices" / zone


def get_price_csv_path(zone: str, year: int) -> Path:
    return get_price_dir(zone) / f"{year}.csv"


def _fmt_num(value: float, ndigits: int = 5) -> str:
    """Format like the elprisetjustnu files: '0.1026', '9e-05', '0'."""
    r = round(value, ndigits)
    if r == 0:
        return "0"
    if r == int(r):
        return str(int(r))
    return repr(r)


def load_exr_by_date(source_zone: str = EXR_SOURCE_ZONE) -> dict[str, str]:
    """Map local date 'YYYY-MM-DD' -> EXR string from the Swedish spot files."""
    exr: dict[str, str] = {}
    zone_dir = SPOT_DIR / source_zone
    if not zone_dir.exists():
        return exr
    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                value = (row.get("EXR") or "").strip()
                if value:
                    exr.setdefault(row["time_start"][:10], value)
    return exr


def price_records_to_rows(
    records: Iterable[dict], exr_by_date: dict[str, str]
) -> list[dict]:
    """Convert parsed A44 records (UTC, EUR/MWh) to spotpriser-format rows."""
    rows = []
    for rec in records:
        start_utc = parse_iso(rec["time_start"])
        res = int(rec["resolution_minutes"])
        start_local = start_utc.astimezone(SWEDEN_TZ)
        end_local = (start_utc + timedelta(minutes=res)).astimezone(SWEDEN_TZ)
        eur_mwh = float(rec["price_eur_mwh"])
        exr = exr_by_date.get(start_local.date().isoformat(), "")
        rows.append({
            "time_start": start_local.isoformat(),
            "time_end": end_local.isoformat(),
            "SEK_per_kWh": _fmt_num(eur_mwh * float(exr) / 1000) if exr else "",
            "EUR_per_kWh": _fmt_num(eur_mwh / 1000),
            "EXR": exr,
        })
    return rows


def _fill_missing_exr(row: dict, exr_by_date: dict[str, str]) -> bool:
    """Fill empty EXR/SEK in-place from ``exr_by_date``. Returns True if changed."""
    if (row.get("EXR") or "").strip():
        return False
    exr = exr_by_date.get(row["time_start"][:10])
    if not exr or not (row.get("EUR_per_kWh") or "").strip():
        return False
    row["EXR"] = exr
    row["SEK_per_kWh"] = _fmt_num(float(row["EUR_per_kWh"]) * float(exr))
    return True


def _write_price_file(csv_path: Path, rows: Iterable[dict]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    # Sort on the instant, not the string: during the DST fall-back hour
    # '02:00+02:00' precedes '02:00+01:00' but sorts after it lexically.
    ordered = sorted(rows, key=lambda r: parse_iso(r["time_start"]))
    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PRICE_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ordered)
    os.replace(tmp, csv_path)


def _read_price_file(csv_path: Path) -> dict[str, dict]:
    existing: dict[str, dict] = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["time_start"]] = row
    return existing


def save_price_rows(
    zone: str, rows: list[dict], exr_by_date: dict[str, str] | None = None
) -> dict[int, int]:
    """Merge rows into the zone's local-year files. Returns {year: n_rows_saved}.

    Existing rows with the same ``time_start`` are replaced. If
    ``exr_by_date`` is given, any row in the touched files that still lacks
    EXR is filled from it.
    """
    by_year: dict[int, list[dict]] = {}
    for row in rows:
        by_year.setdefault(int(row["time_start"][:4]), []).append(row)

    saved: dict[int, int] = {}
    for year, year_rows in sorted(by_year.items()):
        csv_path = get_price_csv_path(zone, year)
        existing = _read_price_file(csv_path)
        for row in year_rows:
            existing[row["time_start"]] = row
        if exr_by_date:
            for row in existing.values():
                _fill_missing_exr(row, exr_by_date)
        _write_price_file(csv_path, existing.values())
        saved[year] = len(year_rows)
    return saved


def backfill_exr(zone: str, exr_by_date: dict[str, str] | None = None) -> list[int]:
    """Fill empty EXR/SEK_per_kWh in all of a zone's price files.

    Rewrites only files where something changed; returns those years.
    """
    if exr_by_date is None:
        exr_by_date = load_exr_by_date()
    changed_years = []
    zone_dir = get_price_dir(zone)
    if not zone_dir.exists():
        return changed_years
    for csv_path in sorted(zone_dir.glob("*.csv")):
        existing = _read_price_file(csv_path)
        changed = False
        for row in existing.values():
            changed |= _fill_missing_exr(row, exr_by_date)
        if changed:
            _write_price_file(csv_path, existing.values())
            changed_years.append(int(csv_path.stem))
    return changed_years


def get_latest_price_end(zone: str) -> datetime | None:
    """``time_end`` of the last stored price row for a zone (tz-aware)."""
    zone_dir = get_price_dir(zone)
    if not zone_dir.exists():
        return None
    year_files = sorted(zone_dir.glob("*.csv"), key=lambda p: p.stem)
    for csv_path in reversed(year_files):
        last = None
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                last = row
        if last is not None:
            return parse_iso(last["time_end"])
    return None


def download_day_ahead_prices(
    zone: str,
    start_date: date | None = None,
    end_date: date | None = None,
    token: str | None = None,
    verbose: bool = True,
    force: bool = False,
    update_quarterly: bool = True,
) -> dict:
    """Download day-ahead prices (A44) for a zone into spotpriser-format CSVs.

    Args:
        zone: Bidding zone ("DK1", "DK2"; SE zones go to entsoe/prices/)
        start_date: First local market day (default: day after the latest
            stored row, or ``PRICE_HISTORY_START`` if nothing is stored)
        end_date: Last local market day, inclusive (default: yesterday, like
            the Swedish spot update). Day-ahead prices for today/tomorrow
            are available if passed explicitly.
        token: API token
        verbose: Print progress
        force: Ignore stored data and start from ``PRICE_HISTORY_START``
        update_quarterly: Regenerate data/quarterly/<zone>/YYYY.csv for the
            touched years (only for zones stored next to the Swedish files)

    Returns:
        Dict with download statistics (``failed_chunks`` as for generation).
    """
    if zone not in ENTSOE_ZONES:
        raise ValueError(f"Unknown zone: {zone}. Use: {list(ENTSOE_ZONES.keys())}")

    if start_date is None:
        latest_end = None if force else get_latest_price_end(zone)
        if latest_end is not None:
            # time_end of the last row: local midnight -> next day; a partial
            # day (shouldn't happen for day-ahead) is re-fetched.
            start_date = latest_end.astimezone(SWEDEN_TZ).date()
            if verbose:
                print(f"  Found existing prices up to {latest_end.isoformat()}, starting from {start_date}")
        else:
            start_date = PRICE_HISTORY_START

    if end_date is None:
        end_date = date.today() - timedelta(days=1)

    if verbose:
        print(f"Downloading day-ahead prices for {zone} from {start_date} to {end_date}")

    exr_by_date = load_exr_by_date()
    total_records = 0
    failed_chunks: list[str] = []
    touched_years: set[int] = set()

    def fetch_chunk(chunk_start: date, chunk_stop: date) -> list[dict]:
        xml_content = fetch_entsoe_data(
            document_type="day_ahead_prices",
            zone=zone,
            start_date=chunk_start,
            end_date=chunk_stop,
            token=token,
        )
        if not xml_content:
            return []
        lo, hi = _local_day_bounds_utc(chunk_start, chunk_stop)
        records = [
            r for r in parse_prices_xml(xml_content)
            if lo <= parse_iso(r["time_start"]) < hi
        ]
        return dedupe_price_records(records)

    for chunk_start, chunk_end in _month_chunks(start_date, end_date):
        if verbose:
            print(f"  {chunk_start} to {chunk_end}...", end=" ", flush=True)
        records, chunk_failures = _fetch_with_fallback(
            fetch_chunk, chunk_start, chunk_end, verbose=verbose
        )
        failed_chunks.extend(chunk_failures)
        if not records:
            continue
        rows = price_records_to_rows(dedupe_price_records(records), exr_by_date)
        saved = save_price_rows(zone, rows, exr_by_date)
        touched_years.update(saved)
        total_records += sum(saved.values())

    # Rows stored on an earlier run before SE3 had that day's EXR.
    touched_years.update(backfill_exr(zone, exr_by_date))

    quarterly_records = 0
    if update_quarterly and zone in DANISH_ZONES and SPOT_DIR == RAW_DIR:
        from .processing import process_zone_year

        for year in sorted(touched_years):
            quarterly_records += process_zone_year(zone, year)

    if verbose:
        print(f"Total: {total_records} price rows")
        if quarterly_records:
            print(f"  data/quarterly/{zone}: {quarterly_records} rows regenerated")
        if failed_chunks:
            print(f"  WARNING: {len(failed_chunks)} chunks failed:")
            for msg in failed_chunks:
                print(f"    - {msg}")

    return {
        "zone": zone,
        "start_date": start_date,
        "end_date": end_date,
        "total_records": total_records,
        "failed_chunks": failed_chunks,
        "years": sorted(touched_years),
    }


def download_all_prices(
    zones: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    token: str | None = None,
    verbose: bool = True,
    force: bool = False,
) -> list[dict]:
    """Download day-ahead prices for several zones (default: DK1, DK2)."""
    if zones is None:
        zones = list(DANISH_ZONES.keys())
    return [
        download_day_ahead_prices(
            zone=zone,
            start_date=start_date,
            end_date=end_date,
            token=token,
            verbose=verbose,
            force=force,
        )
        for zone in zones
    ]
