"""Nordic electricity futures downloader.

Downloads Nasdaq history (up to the migration) and Euronext Nord Pool Power
Futures settlements for Nordic system price (SYS) baseload futures and EPAD
(Electricity Price Area Differential) contracts for Swedish bidding zones.

Sources
-------
* **Nasdaq** (``api.nasdaq.com``, undocumented JSON): daily ``dailyFix`` per
  contract. Trading moved to Euronext in March 2026; Nasdaq kept publishing
  dailyFix until :data:`NASDAQ_LAST_DATE`.
* **Euronext** (``live.euronext.com``, the AJAX fragments behind the public
  product pages):

  - ``getPricesFutures/commodities-futures/{CLASS}/DAMS`` — every listed
    maturity of one contract class (e.g. ``NSBQ`` = SYS quarters) with
    bid/ask/last, volumes, OHLC, settlement and open interest *right now*.
  - ``settlements/getHistoricalPricePopup/{CLASS}-DAMS?md=DD-MM-YYYY`` — the
    last *N* sessions of one maturity, **each row carrying its own trading
    date** (Date, Open, High, Low, Settl., Number of shares, Turnover).

  The dated history table is the authoritative source for ``date``: it is the
  trading (settlement) date, never the fetch time. The listing only adds the
  end-of-day fields the history lacks (open interest, bid/ask) and only when
  it provably shows the same session (see :func:`build_euronext_rows`).
  Euronext settlements equal Nasdaq's dailyFix exactly for the overlapping
  period (verified 2026-09-22 on all 2,340 overlapping (date, contract) pairs
  in the five files, 2026-02-02..2026-04-29), so the two sources form one
  continuous series. Only *listed* maturities are served: expired contracts
  (e.g. Q3-26, delisted end of June 2026) cannot be backfilled.

CSV schema
----------
``date`` is always the trading/settlement date. Columns after
``open_interest`` were added 2026-09 and are empty for old rows:

* ``open_eur`` — session open (Euronext only).
* ``volume`` — traded volume in lots (1 lot = 1 MW), Euronext "Number of
  shares" / "Tot Vol" (on + off exchange).
* ``source`` — ``nasdaq`` | ``euronext``. Rows written before the column
  existed are inferred: ``nasdaq`` for dates ≤ :data:`NASDAQ_LAST_DATE`,
  ``euronext`` after.
* ``fetched_at`` — ISO-8601 UTC time the row was fetched (empty = unknown).

``open_interest`` has the same unit in both sources (lots/MW; e.g. SYS
YR-27: Nasdaq 3553 on 2026-03-13, Euronext 4035 on 2026-07-03).
"""

from __future__ import annotations

import csv
import html
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests

from .config import HTTP_TIMEOUT_QUICK, NASDAQ_DATA_DIR, REQUEST_DELAY, SWEDEN_TZ
from .http_client import with_retry

# API configuration
NASDAQ_BASE_URL = "https://api.nasdaq.com/api/nordic"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Products to download
# Search prefix -> (filename, description)
PRODUCTS = {
    "ENOFUTBL": ("sys_baseload", "Nordic System Price Baseload"),
    "SYLUL": ("epad_se1_lul", "EPAD SE1 Luleå"),
    "SYSUN": ("epad_se2_sun", "EPAD SE2 Sundsvall"),
    "SYSTO": ("epad_se3_sto", "EPAD SE3 Stockholm"),
    "SYMAL": ("epad_se4_mal", "EPAD SE4 Malmö"),
}

# Last date with a Nasdaq dailyFix in the local files. Rows after this date
# come from Euronext. Used to infer ``source`` for rows written before the
# column existed, and to protect Nasdaq rows from being overwritten.
NASDAQ_LAST_DATE = "2026-04-29"

# CSV fields. The first eight are the original Nasdaq schema; the rest were
# appended (backward compatible — every reader uses csv.DictReader).
CSV_FIELDS = [
    "date", "contract", "daily_fix_eur",
    "bid_eur", "ask_eur", "high_eur", "low_eur", "open_interest",
    "open_eur", "volume", "source", "fetched_at",
]

# Max date range per API request (~90 days works reliably)
MAX_DAYS_PER_REQUEST = 90


@with_retry()
def _api_get(endpoint: str, params: dict | None = None) -> dict:
    """Make a GET request to the Nasdaq API with retries.

    Raises requests.HTTPError on non-200 responses (after retries).
    """
    url = f"{NASDAQ_BASE_URL}/{endpoint}"
    resp = requests.get(url, params=params, headers=HEADERS, timeout=HTTP_TIMEOUT_QUICK)
    resp.raise_for_status()
    return resp.json()


def search_instruments(prefix: str) -> list[dict]:
    """Search for instruments matching a prefix.

    Returns list of dicts with keys: symbol, orderbookId, isin, fullName.
    """
    data = _api_get("search", {"searchText": prefix})
    instruments = []
    for group in data.get("data") or []:
        for inst in group.get("instruments") or []:
            instruments.append({
                "symbol": inst["symbol"],
                "orderbookId": inst["orderbookId"],
                "isin": inst.get("isin", ""),
                "fullName": inst.get("fullName", ""),
            })
    return instruments


def get_price_history(
    orderbook_id: str, from_date: date, to_date: date
) -> list[dict]:
    """Get daily price history for an instrument.

    Returns list of dicts with keys matching CSV_FIELDS.
    Automatically splits long date ranges into chunks.

    HTTP 400 is silently swallowed because Nasdaq returns 400 for date
    ranges that pre-date when the instrument started trading — that's
    expected, not a failure. Any *other* error (5xx, network, parse) is
    forwarded to ``failure_log`` so cron runs surface real outages.
    """
    from .failure_log import log_failure

    all_rows = []
    chunk_start = from_date

    while chunk_start <= to_date:
        chunk_end = min(chunk_start + timedelta(days=MAX_DAYS_PER_REQUEST), to_date)

        try:
            data = _api_get(
                f"instruments/{orderbook_id}/price-history",
                {
                    "assetClass": "COMMODITIES",
                    "fromDate": chunk_start.isoformat(),
                    "toDate": chunk_end.isoformat(),
                    "lang": "en",
                },
            )
            rows = (data.get("data") or {}).get("priceHistory", {}).get("rows") or []
            all_rows.extend(rows)
        except requests.HTTPError as e:
            # 400 = no data for this range (pre-trading); ignore.
            # Anything else is a real failure worth logging.
            if e.response is None or e.response.status_code != 400:
                log_failure(
                    "nasdaq",
                    orderbook_id,
                    f"{chunk_start}..{chunk_end}",
                    str(e),
                )
        except Exception as e:
            log_failure(
                "nasdaq",
                orderbook_id,
                f"{chunk_start}..{chunk_end}",
                str(e),
            )

        chunk_start = chunk_end + timedelta(days=1)
        if chunk_start <= to_date:
            time.sleep(REQUEST_DELAY)

    return all_rows


# ---------------------------------------------------------------------------
# Euronext Nord Pool Power Futures
# ---------------------------------------------------------------------------

EURONEXT_BASE_URL = "https://live.euronext.com"
EURONEXT_POWER_PAGE = (
    EURONEXT_BASE_URL + "/en/products/commodities/power-derivatives/contracts-list"
)
EURONEXT_LISTING_URL = (
    EURONEXT_BASE_URL + "/en/ajax/getPricesFutures/commodities-futures/{cls}/DAMS"
)
EURONEXT_HISTORY_URL = (
    EURONEXT_BASE_URL + "/en/ajax/settlements/getHistoricalPricePopup/{cls}-DAMS"
)
EURONEXT_PRODUCT_PAGE = EURONEXT_BASE_URL + "/en/product/commodities-futures/{cls}-DAMS"

# Local CSV file -> (Nasdaq-compatible symbol prefix, {kind: Euronext class}).
# Kinds: "Q" quarter, "YR" calendar year, "M" month. Euronext lists every
# open maturity per class (2026-09: SYS 9 quarters, 10 years, 7 months; each
# EPAD 4 quarters, 4 years, 4 months) — no rank limit.
EURONEXT_CLASSES: dict[str, tuple[str, dict[str, str]]] = {
    "sys_baseload.csv": ("ENOFUTBL", {"Q": "NSBQ", "YR": "NSBY", "M": "NSBM"}),
    "epad_se1_lul.csv": ("SYLULFUTBL", {"Q": "LLBQ", "YR": "LLBY", "M": "LLBM"}),
    "epad_se2_sun.csv": ("SYSUNFUTBL", {"Q": "SUBQ", "YR": "SUBY", "M": "SUBM"}),
    "epad_se3_sto.csv": ("SYSTOFUTBL", {"Q": "STBQ", "YR": "STBY", "M": "STBM"}),
    "epad_se4_mal.csv": ("SYMALFUTBL", {"Q": "MABQ", "YR": "MABY", "M": "MABM"}),
}
EURONEXT_KINDS = ("Q", "YR", "M")

# Sessions of dated history fetched per maturity. The daily job re-reads two
# weeks so a missed run heals itself; a backfill reads everything Euronext
# still serves (history starts 2026-02-02 for contracts listed then).
# Expired (delisted) maturities are no longer served at all.
EURONEXT_DAILY_SESSIONS = 10
EURONEXT_BACKFILL_SESSIONS = 400

# Settlement-publication rule, only used where no dated source exists
# (sanity checks, legacy rows). Evidence (2026-09-22 investigation):
#   * last trades of the day are stamped up to ~16:45 local time, so the
#     settlement cannot be final before the session closes;
#   * a fetch Sat 2026-09-12 08:21 showed Fri 2026-09-11's settlement
#     (Q1-27 116.90 == Euronext history 11/09/2026);
#   * fetches Tue 2026-09-22 21:1x/22:1x showed Tue 2026-09-22's settlement
#     (Q4-26 104.01 == history 22/09/2026);
#   * weekday fetches made earlier in the day (e.g. the 2026-07-15 and
#     2026-07-29 snapshots) showed the *previous* session's settlement.
# 18:00 local is therefore a conservative cut-off. Exchange holidays are not
# modelled — the dated history is authoritative whenever it is available.
SETTLEMENT_PUBLISHED_LOCAL_HOUR = 18

_MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def settlement_date_for_fetch(fetched_at: datetime) -> date:
    """Trading date of the newest settlement visible at ``fetched_at``.

    Rule (Europe/Stockholm local time): on a weekday at/after
    :data:`SETTLEMENT_PUBLISHED_LOCAL_HOUR` the same day's settlement is
    published; before that, or on a weekend, the newest settlement belongs to
    the previous weekday. Holidays are not modelled.

    Args:
        fetched_at: timezone-aware fetch time (naive values are taken as UTC).
    """
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    local = fetched_at.astimezone(SWEDEN_TZ)
    day = local.date()
    if day.weekday() < 5 and local.hour >= SETTLEMENT_PUBLISHED_LOCAL_HOUR:
        return day
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _utc_now_iso(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_html(value: str) -> str:
    """Convert a small HTML cell fragment to plain text."""
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).replace("\xa0", " ").strip()


def _euronext_number(text: str) -> str:
    """Normalise a Euronext number cell: ``"5,758"`` -> ``"5758"``, ``"-"`` -> ``""``."""
    text = (text or "").strip()
    if text in {"", "-", "–"}:
        return ""
    return text.replace(",", "").replace(" ", "")


def _euronext_date(text: str) -> str | None:
    """``"22/09/2026"`` -> ``"2026-09-22"`` (None if not a date)."""
    match = re.fullmatch(r"\s*(\d{2})/(\d{2})/(\d{4})\s*", text or "")
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month}-{day}"


def euronext_contract_suffix(kind: str, delivery: str) -> str | None:
    """Map a Euronext delivery label to the Nasdaq-style symbol suffix.

    ``("Q", "Q4 2026")`` -> ``"Q4-26"``, ``("YR", "2027")`` -> ``"YR-27"``,
    ``("M", "Oct 2026")`` -> ``"MOCT-26"``. Month symbols deliberately do not
    end in ``YR-yy``/``Qn-yy``, so the older Q/YR-only parsers skip them.
    """
    delivery = (delivery or "").strip()
    if kind == "Q":
        match = re.fullmatch(r"Q([1-4])\s+(\d{4})", delivery)
        if match:
            return f"Q{match.group(1)}-{match.group(2)[-2:]}"
    elif kind == "YR":
        match = re.fullmatch(r"(\d{4})", delivery)
        if match:
            return f"YR-{match.group(1)[-2:]}"
    elif kind == "M":
        match = re.fullmatch(r"([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{4})", delivery)
        if match and match.group(1).upper() in _MONTH_ABBR:
            return f"M{match.group(1).upper()}-{match.group(2)[-2:]}"
    return None


def parse_euronext_listing(html_text: str) -> dict:
    """Parse a ``getPricesFutures`` fragment (all maturities of one class).

    Returns ``{"date": "YYYY-MM-DD" | None, "maturities": [...]}`` where
    ``date`` is the "Prices - 22 Sep 2026" heading and each maturity dict has
    ``delivery``, ``md`` (Euronext maturity key ``DD-MM-YYYY``) and the
    normalised number strings ``bid``, ``ask``, ``last``, ``tot_vol``,
    ``open``, ``high``, ``low``, ``settle``, ``oi`` ("" when absent).
    """
    heading = re.search(
        r"Prices\s*-\s*(\d{1,2})\s+([A-Za-z]{3})[A-Za-z]*\s+(\d{4})", html_text
    )
    listing_date = None
    if heading and heading.group(2).upper() in _MONTH_ABBR:
        listing_date = date(
            int(heading.group(3)),
            _MONTH_ABBR[heading.group(2).upper()],
            int(heading.group(1)),
        ).isoformat()

    maturities = []
    tbody = re.search(r"<tbody[^>]*>(.*?)</tbody>", html_text, re.S)
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody.group(1) if tbody else "", re.S):
        md = re.search(r"md=(\d{2}-\d{2}-\d{4})", row_html)
        cells = [_strip_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)]
        # Delivery, Bid, Ask, Last, Time, +/-, On Vol, Off Vol, Tot Vol,
        # Open, High, Low, Settl., O.I
        if not md or len(cells) < 14:
            continue
        maturities.append({
            "delivery": cells[0],
            "md": md.group(1),
            "bid": _euronext_number(cells[1]),
            "ask": _euronext_number(cells[2]),
            "last": _euronext_number(cells[3]),
            "tot_vol": _euronext_number(cells[8]),
            "open": _euronext_number(cells[9]),
            "high": _euronext_number(cells[10]),
            "low": _euronext_number(cells[11]),
            "settle": _euronext_number(cells[12]),
            "oi": _euronext_number(cells[13]),
        })
    return {"date": listing_date, "maturities": maturities}


def parse_euronext_history(html_text: str) -> list[dict]:
    """Parse a ``getHistoricalPricePopup`` fragment into dated sessions.

    Returns ``[{"date", "open", "high", "low", "settle", "volume"}, ...]``
    sorted by date, skipping sessions without a settlement. ``date`` is the
    trading date printed by Euronext.
    """
    sessions = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.S):
        cells = [_strip_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)]
        # Date, Open, High, Low, Settl., Number of shares, Turnover
        if len(cells) < 5:
            continue
        session_date = _euronext_date(cells[0])
        settle = _euronext_number(cells[4])
        if not session_date or not settle:
            continue
        sessions.append({
            "date": session_date,
            "open": _euronext_number(cells[1]),
            "high": _euronext_number(cells[2]),
            "low": _euronext_number(cells[3]),
            "settle": settle,
            "volume": _euronext_number(cells[5]) if len(cells) > 5 else "",
        })
    sessions.sort(key=lambda s: s["date"])
    return sessions


def _same_price(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) < 0.005
    except (TypeError, ValueError):
        return False


def build_euronext_rows(
    symbol: str,
    history: list[dict],
    listing_row: dict | None = None,
    listing_date: str | None = None,
    fetched_at: str = "",
) -> list[dict]:
    """Turn one maturity's dated history (+ listing snapshot) into CSV rows.

    Every row is dated by the history table (trading date). The listing's
    open interest and bid/ask are attached to the newest session only when the
    listing provably shows that session: its heading date equals the session
    date AND its settlement equals the session's settlement. Otherwise they
    are dropped (the listing may show an intraday or next-day state).
    """
    rows = [
        {
            "date": s["date"],
            "contract": symbol,
            "daily_fix_eur": s["settle"],
            "bid_eur": "",
            "ask_eur": "",
            "high_eur": s["high"],
            "low_eur": s["low"],
            "open_interest": "",
            "open_eur": s["open"],
            "volume": s["volume"],
            "source": "euronext",
            "fetched_at": fetched_at,
        }
        for s in history
    ]
    if rows and listing_row and listing_date:
        latest = max(rows, key=lambda r: r["date"])
        if latest["date"] == listing_date and _same_price(
            listing_row.get("settle"), latest["daily_fix_eur"]
        ):
            latest["open_interest"] = listing_row.get("oi", "")
            latest["bid_eur"] = listing_row.get("bid", "")
            latest["ask_eur"] = listing_row.get("ask", "")
    return rows


@with_retry()
def _euronext_get(session: requests.Session, url: str, params: dict | None = None,
                  referer: str = EURONEXT_POWER_PAGE) -> str:
    resp = session.get(
        url,
        params=params,
        headers={
            **HEADERS,
            "Accept": "text/html, */*; q=0.01",
            "Referer": referer,
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=HTTP_TIMEOUT_QUICK,
    )
    resp.raise_for_status()
    return resp.text


def fetch_euronext_listing(session: requests.Session, cls: str) -> dict:
    """All listed maturities of one Euronext class (see parse_euronext_listing)."""
    text = _euronext_get(
        session,
        EURONEXT_LISTING_URL.format(cls=cls),
        referer=EURONEXT_PRODUCT_PAGE.format(cls=cls),
    )
    return parse_euronext_listing(text)


def fetch_euronext_history(
    session: requests.Session, cls: str, md: str, n_sessions: int
) -> list[dict]:
    """The last ``n_sessions`` dated settlements of one maturity."""
    text = _euronext_get(
        session,
        EURONEXT_HISTORY_URL.format(cls=cls),
        params={
            "fOrO": "F",
            "md": md,
            "cOrP": "",
            "sp": "",
            "modeBascule": "true",
            "classSubType": "PWFUT",
            "nbSession": str(n_sessions),
        },
        referer=EURONEXT_PRODUCT_PAGE.format(cls=cls),
    )
    return parse_euronext_history(text)


def fetch_euronext_futures(
    n_sessions: int = EURONEXT_DAILY_SESSIONS,
    files: Iterable[str] | None = None,
    kinds: Iterable[str] = EURONEXT_KINDS,
    session: requests.Session | None = None,
    now: datetime | None = None,
    log=print,
) -> tuple[dict[str, list[dict]], list[str]]:
    """Fetch dated Euronext settlements for every listed maturity.

    Returns ``(rows_by_file, errors)``. ``errors`` lists every class or
    maturity that could not be fetched/parsed; the rows that did succeed are
    still returned so a partial outage does not block the rest.
    """
    session = session or requests.Session()
    fetched_at = _utc_now_iso(now)
    rows_by_file: dict[str, list[dict]] = {}
    errors: list[str] = []
    for filename, (prefix, classes) in EURONEXT_CLASSES.items():
        if files is not None and filename not in files:
            continue
        rows_by_file.setdefault(filename, [])
        for kind in kinds:
            cls = classes.get(kind)
            if not cls:
                continue
            try:
                listing = fetch_euronext_listing(session, cls)
            except Exception as e:  # noqa: BLE001 — reported, run continues
                errors.append(f"{cls}: listing failed: {e}")
                continue
            time.sleep(REQUEST_DELAY)
            if not listing["maturities"]:
                # Power futures always list maturities: an empty class means a
                # layout change or outage. Report it — otherwise e.g. every
                # YR contract silently drops out of the zonal forwards.
                errors.append(f"{cls} ({filename}): listing had no maturities")
                continue
            for mat in listing["maturities"]:
                suffix = euronext_contract_suffix(kind, mat["delivery"])
                if not suffix:
                    errors.append(f"{cls}: unparsed delivery {mat['delivery']!r}")
                    continue
                symbol = f"{prefix}{suffix}"
                try:
                    history = fetch_euronext_history(session, cls, mat["md"], n_sessions)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{cls} {mat['md']}: history failed: {e}")
                    continue
                finally:
                    time.sleep(REQUEST_DELAY)
                if not history:
                    # Newly listed maturity with no settlement yet: not an error.
                    log(f"    {symbol}: no settled sessions yet")
                    continue
                rows_by_file[filename].extend(
                    build_euronext_rows(
                        symbol, history, mat, listing["date"], fetched_at
                    )
                )
            log(f"  {cls} ({filename}): {len(listing['maturities'])} maturities, "
                f"listing date {listing['date']}")
        if not rows_by_file[filename]:
            errors.append(f"{filename}: no settlements fetched (layout change?)")
    return rows_by_file, errors


def euronext_sessions_needed(
    data_dir: Path | None = None,
    today: date | None = None,
    minimum: int = EURONEXT_DAILY_SESSIONS,
) -> int:
    """Sessions to re-read so the fetch reaches back to the newest stored day.

    The pipeline is often run by hand with gaps of weeks; a fixed 10-session
    window would then skip days that can never be fetched again once a
    contract expires. Window = weekdays since the newest SYS settlement + 3,
    at least ``minimum``, at most EURONEXT_BACKFILL_SESSIONS.
    """
    data_dir = data_dir or NASDAQ_DATA_DIR
    today = today or datetime.now(timezone.utc).astimezone(SWEDEN_TZ).date()
    rows = load_futures_csv(data_dir / "sys_baseload.csv")
    if not rows:
        return EURONEXT_BACKFILL_SESSIONS
    newest = date.fromisoformat(max(r["date"] for r in rows))
    weekdays, d = 0, newest
    while d < today:
        d += timedelta(days=1)
        weekdays += d.weekday() < 5
    return max(minimum, min(EURONEXT_BACKFILL_SESSIONS, weekdays + 3))


def update_euronext_futures(
    n_sessions: int | None = None,
    data_dir: Path | None = None,
    log=print,
    **fetch_kwargs,
) -> tuple[dict[str, dict], list[str]]:
    """Fetch Euronext settlements and merge them into the local CSVs.

    Idempotent: rows are keyed on (trading date, contract), so re-fetching a
    session replaces it instead of duplicating it. ``n_sessions=None`` sizes
    the window from the newest stored settlement (:func:`euronext_sessions_needed`).

    Returns ``({filename: {"rows": total, "new": added, "latest": date}}, errors)``.
    """
    data_dir = data_dir or NASDAQ_DATA_DIR
    if n_sessions is None:
        n_sessions = euronext_sessions_needed(data_dir)
        log(f"  Euronext window: {n_sessions} sessions per maturity")
    rows_by_file, errors = fetch_euronext_futures(n_sessions=n_sessions, log=log,
                                                  **fetch_kwargs)
    summary: dict[str, dict] = {}
    for filename, rows in rows_by_file.items():
        if not rows:
            continue
        path = data_dir / filename
        before = len(load_futures_csv(path)) if path.exists() else 0
        total = save_to_csv(rows, path)
        summary[filename] = {
            "rows": total,
            "new": total - before,
            "latest": max(r["date"] for r in rows),
        }
    return summary, errors


def update_euronext_power_snapshot() -> dict[str, int]:
    """Backward-compatible entry point used by :func:`download_all_futures`.

    Raises RuntimeError if any class/maturity failed (after saving whatever
    succeeded) so callers log the failure.
    """
    summary, errors = update_euronext_futures()
    if errors:
        raise RuntimeError("; ".join(errors[:5]) + (" ..." if len(errors) > 5 else ""))
    return {filename: info["rows"] for filename, info in summary.items()}


def redate_legacy_euronext_rows(
    rows: list[dict],
    history: dict[str, dict[str, str]],
    window_days: int = 10,
) -> tuple[list[dict], list[dict]]:
    """Re-date legacy Euronext snapshot rows to their real trading date.

    Rows appended by the old rank-based snapshot (2026-07-05 .. 2026-09-22)
    carry the *page update date* (``fdc-dtu``) instead of the settlement
    date: weekend rows hold Friday's settlement and weekday rows fetched
    before publication hold the previous session's. Legacy rows are those
    with ``source == "euronext"``, no ``fetched_at`` and a date after
    :data:`NASDAQ_LAST_DATE`.

    Each snapshot date D (one group of rows per file) is matched against the
    dated Euronext history: the newest trading date T in [D-window, D] where
    *every* row of the group whose contract has history shows exactly the
    same settlement is taken as the true date. Deterministic, value-based,
    no clock assumptions.

    * Resolved groups: all rows move to T (OI kept — it is the snapshot's).
    * Unresolved groups: rows stay at D, except rows whose (D, contract) has
      a *different* dated settlement — those are dropped, the dated history
      wins.

    Args:
        rows: normalised CSV rows (see :func:`load_futures_csv`).
        history: {contract: {trading_date: settle}} from Euronext.

    Returns:
        (rows_out, report) — report has one dict per legacy group.
    """
    def is_legacy(r: dict) -> bool:
        return (
            r.get("source") == "euronext"
            and not r.get("fetched_at")
            and r["date"] > NASDAQ_LAST_DATE
        )

    trading_dates = sorted({d for series in history.values() for d in series})
    out = [r for r in rows if not is_legacy(r)]
    groups: dict[str, list[dict]] = {}
    for r in rows:
        if is_legacy(r):
            groups.setdefault(r["date"], []).append(r)

    report = []
    redated: dict[tuple[str, str], dict] = {}
    for snap_date in sorted(groups):
        group = groups[snap_date]
        with_hist = [r for r in group if history.get(r["contract"])]
        lo = (date.fromisoformat(snap_date) - timedelta(days=window_days)).isoformat()
        candidates = [d for d in reversed(trading_dates) if lo <= d <= snap_date]
        matches = []
        for cand in candidates:
            if with_hist and all(
                cand in history[r["contract"]]
                and _same_price(history[r["contract"]][cand], r["daily_fix_eur"])
                for r in with_hist
            ):
                matches.append(cand)
        target = matches[0] if matches else None
        dropped = 0
        for r in group:
            if target:
                new = dict(r, date=target)
            else:
                dated = history.get(r["contract"], {}).get(snap_date)
                if dated is not None and not _same_price(dated, r["daily_fix_eur"]):
                    dropped += 1
                    continue
                new = dict(r)
            # Later snapshots of the same session win (larger snap_date).
            redated[(new["date"], new["contract"])] = new
        report.append({
            "snapshot_date": snap_date,
            "trading_date": target,
            "rows": len(group),
            "compared": len(with_hist),
            "ambiguous": len(matches) > 1,
            "dropped": dropped,
        })
    return out + list(redated.values()), report

def discover_and_download(
    prefix: str,
    from_date: date,
    to_date: date,
    contract_filter: str = r"FUTBL(YR|Q\d)",
) -> list[dict]:
    """Discover instruments for a product and download price history.

    Args:
        prefix: Search prefix (e.g. "ENOFUTBL", "SYSTO")
        from_date: Start date
        to_date: End date
        contract_filter: Regex to filter contract symbols (default: year + quarter)

    Returns:
        List of CSV-ready row dicts
    """
    pattern = re.compile(contract_filter)
    instruments = search_instruments(prefix)
    futures = [i for i in instruments if pattern.search(i["symbol"])]

    print(f"  Found {len(futures)} contracts for {prefix}")

    fetched_at = _utc_now_iso()
    all_rows = []
    for inst in sorted(futures, key=lambda x: x["symbol"]):
        symbol = inst["symbol"]
        oid = inst["orderbookId"]
        print(f"    {symbol} ({oid})...", end=" ", flush=True)

        time.sleep(REQUEST_DELAY)
        raw_rows = get_price_history(oid, from_date, to_date)

        count = 0
        for r in raw_rows:
            # Nasdaq returns null (not just missing keys) for absent values.
            # Always coalesce None → "" before .strip() to avoid AttributeError.
            daily_fix = (r.get("dailyFix") or "").strip()
            if not daily_fix:
                continue
            all_rows.append({
                "date": r["date"],
                "contract": symbol,
                "daily_fix_eur": daily_fix,
                "bid_eur": (r.get("bidPrice") or "").strip(),
                "ask_eur": (r.get("askPrice") or "").strip(),
                "high_eur": (r.get("highPrice") or "").strip(),
                "low_eur": (r.get("lowPrice") or "").strip(),
                "open_interest": (r.get("oi") or "").strip().replace(",", ""),
                "source": "nasdaq",
                "fetched_at": fetched_at,
            })
            count += 1

        print(f"{count} rows")

    return all_rows



def _normalize_row(row: dict) -> dict:
    """Coerce a row to CSV_FIELDS (None -> "") and infer a missing ``source``."""
    out = {}
    for field in CSV_FIELDS:
        value = row.get(field)
        out[field] = "" if value is None else str(value).strip()
    if not out["source"]:
        out["source"] = "nasdaq" if out["date"] <= NASDAQ_LAST_DATE else "euronext"
    return out


def load_futures_csv(filepath: Path) -> list[dict]:
    """Read a futures CSV (old 8-column or new schema) as normalised rows."""
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return [_normalize_row(row) for row in csv.DictReader(f)]


def merge_futures_rows(
    existing: dict[tuple[str, str], dict], new_rows: Iterable[dict]
) -> dict[tuple[str, str], dict]:
    """Merge rows keyed on (date, contract) — one row per trading date.

    * A new key is added as-is.
    * A Nasdaq row is never overwritten by a non-Nasdaq row (Nasdaq dailyFix
      is the reference for its own era; Euronext only fills holes there).
    * Otherwise non-empty fields of the new row replace the old ones, so a
      re-fetch of the same session replaces its settlement while keeping
      fields the new fetch lacks (e.g. open interest from an earlier listing).
    * An identical re-fetch leaves the row untouched, including its
      ``fetched_at`` (= when the row's content was first/last changed), so
      the daily job does not churn the CSVs.
    """
    for row in new_rows:
        row = _normalize_row(row)
        key = (row["date"], row["contract"])
        old = existing.get(key)
        if old is None:
            existing[key] = row
        elif old["source"] == "nasdaq" and row["source"] != "nasdaq":
            continue
        else:
            updates = {k: v for k, v in row.items() if v != "" and k != "fetched_at"}
            unchanged = all(old.get(k) == v for k, v in updates.items())
            if unchanged and (old["fetched_at"] or not row["fetched_at"]):
                continue
            merged = dict(old)
            merged.update(updates)
            if row["fetched_at"]:
                merged["fetched_at"] = row["fetched_at"]
            existing[key] = merged
    return existing


def write_futures_csv(filepath: Path, rows: Iterable[dict]) -> int:
    """Atomically write rows sorted by (date, contract). Returns row count."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(
        (_normalize_row(r) for r in rows), key=lambda r: (r["date"], r["contract"])
    )
    # Write to .tmp, then rename — prevents truncation if interrupted.
    tmp = filepath.with_suffix(filepath.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(sorted_rows)
    os.replace(tmp, filepath)
    return len(sorted_rows)


def save_to_csv(rows: list[dict], filepath: Path) -> int:
    """Merge rows into the CSV (see :func:`merge_futures_rows`).

    Returns number of rows in the final file.
    """
    existing = merge_futures_rows({}, load_futures_csv(filepath))
    return write_futures_csv(filepath, merge_futures_rows(existing, rows).values())


def backfill_euronext_history(
    n_sessions: int = EURONEXT_BACKFILL_SESSIONS,
    data_dir: Path | None = None,
    redate_legacy: bool = True,
    log=print,
) -> tuple[dict[str, dict], list[str]]:
    """Fetch all dated Euronext history and (optionally) fix legacy rows.

    With ``redate_legacy`` the old fetch-dated snapshot rows are first moved
    to their real trading date (:func:`redate_legacy_euronext_rows`), then the
    dated history is merged in. Re-dating is skipped when any fetch failed,
    to avoid judging legacy rows against incomplete history.

    Returns ``({filename: {"rows", "new", "report"}}, errors)``.
    """
    data_dir = data_dir or NASDAQ_DATA_DIR
    rows_by_file, errors = fetch_euronext_futures(n_sessions=n_sessions, log=log)
    if errors and redate_legacy:
        log("  Fetch errors — legacy rows are NOT re-dated this run.")
        redate_legacy = False
    summary: dict[str, dict] = {}
    for filename, rows in rows_by_file.items():
        path = data_dir / filename
        existing_rows = load_futures_csv(path)
        before = len(existing_rows)
        report: list[dict] = []
        if redate_legacy:
            history: dict[str, dict[str, str]] = {}
            for r in rows:
                history.setdefault(r["contract"], {})[r["date"]] = r["daily_fix_eur"]
            existing_rows, report = redate_legacy_euronext_rows(existing_rows, history)
        merged = merge_futures_rows(merge_futures_rows({}, existing_rows), rows)
        total = write_futures_csv(path, merged.values())
        summary[filename] = {"rows": total, "new": total - before, "report": report}
    return summary, errors


def download_all_futures(
    from_date: date,
    to_date: date,
    products: list[str] | None = None,
) -> dict[str, int]:
    """Download futures data for all (or selected) products.

    Args:
        from_date: Start date
        to_date: End date
        products: List of product keys to download. None = all.
                  Valid keys: "sys", "epad_se1", "epad_se2", "epad_se3", "epad_se4",
                  or "epad_se" for all Swedish EPADs.

    Returns:
        Dict mapping filename to row count.
    """
    # Map friendly names to prefixes
    product_map = {
        "sys": ["ENOFUTBL"],
        "epad_se1": ["SYLUL"],
        "epad_se2": ["SYSUN"],
        "epad_se3": ["SYSTO"],
        "epad_se4": ["SYMAL"],
        "epad_se": ["SYLUL", "SYSUN", "SYSTO", "SYMAL"],
        "all": list(PRODUCTS.keys()),
    }

    if products is None:
        prefixes = list(PRODUCTS.keys())
    else:
        prefixes = []
        for p in products:
            if p in product_map:
                prefixes.extend(product_map[p])
            elif p in PRODUCTS:
                prefixes.append(p)
            else:
                print(f"  Warning: Unknown product '{p}', skipping")
        prefixes = list(dict.fromkeys(prefixes))  # deduplicate, preserve order

    results = {}
    for prefix in prefixes:
        filename, desc = PRODUCTS[prefix]
        print(f"\n{'='*60}")
        print(f"Downloading {desc}")
        print(f"  Period: {from_date} -> {to_date}")
        print(f"{'='*60}")

        try:
            rows = discover_and_download(prefix, from_date, to_date)
        except Exception as e:  # noqa: BLE001 — must not block the Euronext step
            from .failure_log import log_failure

            log_failure("nasdaq", prefix, date.today().isoformat(), str(e))
            print(f"  Warning: Nasdaq download failed for {prefix}: {e}")
            rows = []

        if rows:
            filepath = NASDAQ_DATA_DIR / f"{filename}.csv"
            count = save_to_csv(rows, filepath)
            results[filename] = count
            print(f"  Saved {count} rows to {filepath}")
        else:
            print(f"  No data found")
            results[filename] = 0

    try:
        print(f"\n{'='*60}")
        print("Updating Euronext Nord Pool Power Futures (dated settlements)")
        print(f"{'='*60}")
        euronext_results = update_euronext_power_snapshot()
        for filename, count in sorted(euronext_results.items()):
            key = filename.replace(".csv", "")
            results[key] = count
            print(f"  Updated {filename}: {count} rows")
    except Exception as e:
        from .failure_log import log_failure

        log_failure("euronext", "power_futures", date.today().isoformat(), str(e))
        print(f"  Warning: Euronext update failed: {e}")

    return results
