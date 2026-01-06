"""ENTSO-E Transparency Platform API client.

Provides access to actual generation data (solar, wind), day-ahead prices,
and installed capacity for Swedish bidding zones.

API documentation: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
"""

from __future__ import annotations

import csv
import os
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import DATA_DIR, PROJECT_ROOT, REQUEST_DELAY

# ENTSO-E API configuration
ENTSOE_BASE_URL = "https://web-api.tp.entsoe.eu/api"


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

# Swedish bidding zone EIC codes
ENTSOE_ZONES = {
    "SE1": "10Y1001A1001A44P",
    "SE2": "10Y1001A1001A45N",
    "SE3": "10Y1001A1001A46L",
    "SE4": "10Y1001A1001A47J",
}

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
ENTSOE_DIR = DATA_DIR / "raw" / "entsoe"

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


def _rate_limited(func):
    """Decorator to add rate limiting between API calls."""
    last_call = [0.0]

    def wrapper(*args, **kwargs):
        elapsed = time.time() - last_call[0]
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        result = func(*args, **kwargs)
        last_call[0] = time.time()
        return result

    return wrapper


@_rate_limited
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
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
        zone: Swedish zone ("SE1", "SE2", "SE3", "SE4")
        start_date: Start date
        end_date: End date
        psr_type: Production source type for generation data ("solar", "wind_onshore", etc.)
        process_type: Process type ("realised", "day_ahead")
        token: API security token (defaults to ENTSOE_TOKEN env var)

    Returns:
        XML content as string, or None if request fails
    """
    token = token or ENTSOE_TOKEN
    if not token:
        raise ValueError("ENTSO-E API token required. Set ENTSOE_TOKEN environment variable.")

    if zone not in ENTSOE_ZONES:
        raise ValueError(f"Unknown zone: {zone}. Use: {list(ENTSOE_ZONES.keys())}")

    if document_type not in DOCUMENT_TYPES:
        raise ValueError(f"Unknown document type: {document_type}. Use: {list(DOCUMENT_TYPES.keys())}")

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

    response = requests.get(ENTSOE_BASE_URL, params=params, timeout=60)

    # Handle common error responses
    if response.status_code == 400:
        # No data available for this query
        if "No matching data found" in response.text:
            return None
        response.raise_for_status()

    if response.status_code == 429:
        raise Exception("Rate limit exceeded. Wait 10 minutes before retrying.")

    response.raise_for_status()
    return response.text


def parse_generation_xml(xml_content: str) -> Iterator[dict]:
    """
    Parse actual generation XML from ENTSO-E.

    Yields:
        Dict with timestamp, zone, psr_type, and generation_mw
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return

    # Try different namespaces
    for ns_prefix in [
        "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0",
        "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:1",
    ]:
        ns = {"ns": ns_prefix}
        time_series = root.findall(".//ns:TimeSeries", ns)
        if time_series:
            break
    else:
        # Try without namespace
        time_series = root.findall(".//TimeSeries")
        ns = {}

    for ts in time_series:
        # Get PSR type
        if ns:
            psr_elem = ts.find(".//ns:psrType", ns)
            in_domain = ts.find(".//ns:inBiddingZone_Domain.mRID", ns)
        else:
            psr_elem = ts.find(".//psrType")
            in_domain = ts.find(".//inBiddingZone_Domain.mRID")

        psr_code = psr_elem.text if psr_elem is not None else "unknown"
        psr_name = PSR_TYPE_NAMES.get(psr_code, psr_code)

        # Find zone from domain
        zone = None
        if in_domain is not None:
            for z, code in ENTSOE_ZONES.items():
                if code == in_domain.text:
                    zone = z
                    break

        # Parse periods
        if ns:
            periods = ts.findall(".//ns:Period", ns)
        else:
            periods = ts.findall(".//Period")

        for period in periods:
            if ns:
                start_elem = period.find(".//ns:start", ns)
                resolution_elem = period.find(".//ns:resolution", ns)
                points = period.findall(".//ns:Point", ns)
            else:
                start_elem = period.find(".//start")
                resolution_elem = period.find(".//resolution")
                points = period.findall(".//Point")

            if start_elem is None:
                continue

            start_time = datetime.fromisoformat(start_elem.text.replace("Z", "+00:00"))

            # Parse resolution (PT15M, PT60M, etc.)
            resolution_minutes = 60  # Default to hourly
            if resolution_elem is not None:
                res_text = resolution_elem.text
                if "PT15M" in res_text:
                    resolution_minutes = 15
                elif "PT30M" in res_text:
                    resolution_minutes = 30
                elif "PT60M" in res_text or "PT1H" in res_text:
                    resolution_minutes = 60

            for point in points:
                if ns:
                    position_elem = point.find("ns:position", ns)
                    quantity_elem = point.find("ns:quantity", ns)
                else:
                    position_elem = point.find("position")
                    quantity_elem = point.find("quantity")

                if position_elem is None or quantity_elem is None:
                    continue

                position = int(position_elem.text)
                quantity = float(quantity_elem.text)

                # Calculate timestamp for this point
                point_time = start_time + timedelta(minutes=resolution_minutes * (position - 1))

                yield {
                    "time_start": point_time.isoformat(),
                    "zone": zone,
                    "psr_type": psr_name,
                    "generation_mw": quantity,
                    "resolution_minutes": resolution_minutes,
                }


def parse_prices_xml(xml_content: str) -> Iterator[dict]:
    """
    Parse day-ahead prices XML from ENTSO-E.

    Yields:
        Dict with timestamp, zone, and price_eur_mwh
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return

    # Try different namespaces for price documents
    for ns_prefix in [
        "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3",
        "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0",
    ]:
        ns = {"ns": ns_prefix}
        time_series = root.findall(".//ns:TimeSeries", ns)
        if time_series:
            break
    else:
        time_series = root.findall(".//TimeSeries")
        ns = {}

    for ts in time_series:
        # Find zone
        if ns:
            in_domain = ts.find(".//ns:in_Domain.mRID", ns)
        else:
            in_domain = ts.find(".//in_Domain.mRID")

        zone = None
        if in_domain is not None:
            for z, code in ENTSOE_ZONES.items():
                if code == in_domain.text:
                    zone = z
                    break

        # Parse periods
        if ns:
            periods = ts.findall(".//ns:Period", ns)
        else:
            periods = ts.findall(".//Period")

        for period in periods:
            if ns:
                start_elem = period.find(".//ns:start", ns)
                resolution_elem = period.find(".//ns:resolution", ns)
                points = period.findall(".//ns:Point", ns)
            else:
                start_elem = period.find(".//start")
                resolution_elem = period.find(".//resolution")
                points = period.findall(".//Point")

            if start_elem is None:
                continue

            start_time = datetime.fromisoformat(start_elem.text.replace("Z", "+00:00"))

            # Parse resolution
            resolution_minutes = 60
            if resolution_elem is not None:
                res_text = resolution_elem.text
                if "PT15M" in res_text:
                    resolution_minutes = 15
                elif "PT30M" in res_text:
                    resolution_minutes = 30

            for point in points:
                if ns:
                    position_elem = point.find("ns:position", ns)
                    price_elem = point.find("ns:price.amount", ns)
                else:
                    position_elem = point.find("position")
                    price_elem = point.find("price.amount")

                if position_elem is None or price_elem is None:
                    continue

                position = int(position_elem.text)
                price = float(price_elem.text)

                point_time = start_time + timedelta(minutes=resolution_minutes * (position - 1))

                yield {
                    "time_start": point_time.isoformat(),
                    "zone": zone,
                    "price_eur_mwh": price,
                    "resolution_minutes": resolution_minutes,
                }


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
        zone: Swedish zone ("SE1", "SE2", "SE3", "SE4")
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

    # Read the latest year file
    latest_file = year_files[-1]
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

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_records)

    return len(records)


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
        zone: Swedish zone ("SE1", "SE2", "SE3", "SE4")
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
    current = start_date

    # Download in monthly chunks (API has limits on query size)
    while current <= end_date:
        # Calculate chunk end (one month or end_date)
        if current.month == 12:
            chunk_end = min(date(current.year, 12, 31), end_date)
        else:
            chunk_end = min(date(current.year, current.month + 1, 1) - timedelta(days=1), end_date)

        if verbose:
            print(f"  {current} to {chunk_end}...", end=" ", flush=True)

        try:
            xml_content = fetch_entsoe_data(
                document_type="actual_generation",
                zone=zone,
                start_date=current,
                end_date=chunk_end,
                psr_type=psr_type,
                token=token,
            )

            if xml_content:
                records = list(parse_generation_xml(xml_content))

                # Group by year and save
                by_year: dict[int, list[dict]] = {}
                for record in records:
                    ts = datetime.fromisoformat(record["time_start"])
                    y = ts.year
                    if y not in by_year:
                        by_year[y] = []
                    by_year[y].append(record)

                for year, year_records in by_year.items():
                    saved = save_generation_data(zone, psr_type, year_records, year)
                    total_records += saved

                if verbose:
                    print(f"{len(records)} records")
            else:
                if verbose:
                    print("no data")

        except Exception as e:
            if verbose:
                print(f"error: {e}")

        # Move to next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    if verbose:
        print(f"Total: {total_records} records")

    return {
        "zone": zone,
        "psr_type": psr_type,
        "start_date": start_date,
        "end_date": end_date,
        "total_records": total_records,
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
        zones: List of zones (default: all Swedish zones)
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
        zones = list(ENTSOE_ZONES.keys())

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
