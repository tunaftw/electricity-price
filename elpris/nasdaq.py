"""Nordic electricity futures downloader.

Downloads Nasdaq history and appends current Euronext/Nord Pool Power Futures
snapshot settlements for Nordic system price (SYS) baseload futures and EPAD
(Electricity Price Area Differential) contracts for Swedish bidding zones.

APIs: Nasdaq's undocumented JSON API at api.nasdaq.com and Euronext's live
power-derivatives snapshot.
"""

from __future__ import annotations

import csv
import html
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from .config import HTTP_TIMEOUT_QUICK, NASDAQ_DATA_DIR, REQUEST_DELAY
from .http_client import with_retry

# API configuration
NASDAQ_BASE_URL = "https://api.nasdaq.com/api/nordic"
EURONEXT_POWER_PAGE = (
    "https://live.euronext.com/en/products/commodities/power-derivatives/contracts-list"
)
EURONEXT_POWER_AJAX_URL = (
    "https://live.euronext.com/en/ajax/featured_derivatives_contracts/get_block_content"
)

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

EURONEXT_POWER_PRODUCTS = {
    "Nordic System Price Electricity Base Load": ("sys_baseload.csv", "ENOFUTBL"),
    "Nordic EPAD Electricity Base Load - Sweden LUL": ("epad_se1_lul.csv", "SYLULFUTBL"),
    "Nordic EPAD Electricity Base Load - Sweden SUN": ("epad_se2_sun.csv", "SYSUNFUTBL"),
    "Nordic EPAD Electricity Base Load - Sweden STO": ("epad_se3_sto.csv", "SYSTOFUTBL"),
    "Nordic EPAD Electricity Base Load - Sweden MAL": ("epad_se4_mal.csv", "SYMALFUTBL"),
}

EURONEXT_POWER_GROUPS = [
    ("Nordic System Price Electricity Base Load", "NSBQ-DAMS", "NSBY-DAMS"),
    ("Nordic EPAD Electricity Base Load - Sweden LUL", "LLBQ-DAMS", "LLBY-DAMS"),
    ("Nordic EPAD Electricity Base Load - Sweden SUN", "SUBQ-DAMS", "SUBY-DAMS"),
    ("Nordic EPAD Electricity Base Load - Sweden STO", "STBQ-DAMS", "STBY-DAMS"),
    ("Nordic EPAD Electricity Base Load - Sweden MAL", "MABQ-DAMS", "MABY-DAMS"),
]

EURONEXT_POWER_RANKS = range(1, 7)

# CSV fields
CSV_FIELDS = [
    "date", "contract", "daily_fix_eur",
    "bid_eur", "ask_eur", "high_eur", "low_eur", "open_interest",
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


def _strip_html(value: str) -> str:
    """Convert a small HTML cell fragment to plain text."""
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).replace("\xa0", " ").strip()


def _euronext_snapshot_date(html_text: str) -> str:
    # Euronext lägger ett &nbsp; (inte whitespace) mellan taggen och datumet,
    # så \s* matchar aldrig — hoppa över alla icke-siffror fram till datumet.
    match = re.search(r'class="fdc-dtu">[^\d]*(\d{2})/(\d{2})/(\d{4})', html_text)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return date.today().isoformat()


def _euronext_delivery_suffix(row_type: str, delivery: str) -> str | None:
    if row_type == "Quarter":
        match = re.fullmatch(r"Q([1-4])\s+(\d{4})", delivery)
        if not match:
            return None
        quarter, year = match.groups()
        return f"Q{quarter}-{year[-2:]}"
    if row_type == "Year":
        match = re.fullmatch(r"(\d{4})", delivery)
        if not match:
            return None
        return f"YR-{match.group(1)[-2:]}"
    return None


def parse_euronext_power_snapshot(html_text: str) -> dict[str, list[dict]]:
    """Parse Euronext Nord Pool Power Futures snapshot HTML into CSV rows.

    The Euronext quote snapshot is a current-state table, not a historical
    price-history API. We store each settlement as one daily-fix row using the
    page's own ``fdc-dtu`` update date.
    """
    snapshot_date = _euronext_snapshot_date(html_text)
    rows_by_file: dict[str, list[dict]] = {}

    table_pattern = re.compile(
        r"<caption>(?P<caption>.*?)</caption>\s*<table[^>]*>(?P<table>.*?)</table>",
        re.S,
    )
    for table_match in table_pattern.finditer(html_text):
        caption = _strip_html(table_match.group("caption"))
        product = EURONEXT_POWER_PRODUCTS.get(caption)
        if not product:
            continue
        tbody_match = re.search(
            r"<tbody[^>]*>(?P<tbody>.*?)</tbody>",
            table_match.group("table"),
            re.S,
        )
        if not tbody_match:
            continue
        filename, symbol_prefix = product
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_match.group("tbody"), re.S):
            cells = [_strip_html(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)]
            if len(cells) < 13:
                continue
            row_type, delivery, settlement, open_interest = (
                cells[0],
                cells[2],
                cells[11],
                cells[12],
            )
            if settlement in {"", "-"}:
                continue
            suffix = _euronext_delivery_suffix(row_type, delivery)
            if not suffix:
                continue
            rows_by_file.setdefault(filename, []).append({
                "date": snapshot_date,
                "contract": f"{symbol_prefix}{suffix}",
                "daily_fix_eur": settlement.replace(",", ""),
                "bid_eur": "",
                "ask_eur": "",
                "high_eur": "",
                "low_eur": "",
                "open_interest": "" if open_interest in {"", "-"} else open_interest.replace(",", ""),
            })

    for rows in rows_by_file.values():
        rows.sort(key=lambda r: (r["date"], r["contract"]))
    return rows_by_file


def _form_pairs(prefix: str, value) -> list[tuple[str, str]]:
    """Serialize nested dict/list data like jQuery.param for Drupal Ajax."""
    pairs: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            pairs.extend(_form_pairs(f"{prefix}[{key}]", child))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            pairs.extend(_form_pairs(f"{prefix}[{idx}]", child))
    else:
        pairs.append((prefix, "" if value is None else str(value)))
    return pairs


def _euronext_content_data(rank: int) -> dict:
    groups = []
    for group_label, quarter_code, year_code in EURONEXT_POWER_GROUPS:
        groups.append({
            "field_fdc_group_label": [{"value": group_label}],
            "field_fdc_group_rows": [
                {
                    "field_fdc_contract_code": [{"value": quarter_code}],
                    "field_fdc_contract_label": [{"value": "Quarter"}],
                    "field_fdc_contract_maturity_rank": [{"value": str(rank)}],
                },
                {
                    "field_fdc_contract_code": [{"value": year_code}],
                    "field_fdc_contract_label": [{"value": "Year"}],
                    "field_fdc_contract_maturity_rank": [{"value": str(rank)}],
                },
            ],
        })
    return {
        "field_fdc_contracts_type": [{"value": "FUT"}],
        "field_fdc_data_layout": [{"value": "POWER"}],
        "field_fdc_groups": groups,
        "field_fdc_show_totals": [{"value": "1"}],
        "field_fdc_switch_time": [{"value": "PWFUT"}],
    }


def fetch_euronext_power_snapshot(ranks=EURONEXT_POWER_RANKS) -> dict[str, list[dict]]:
    """Fetch current Euronext Nord Pool Power Futures settlements."""
    session = requests.Session()
    session.get(EURONEXT_POWER_PAGE, headers=HEADERS, timeout=HTTP_TIMEOUT_QUICK)

    rows_by_file: dict[str, list[dict]] = {}
    for rank in ranks:
        data = [("lang", "en/")]
        data.extend(_form_pairs("content_data", _euronext_content_data(rank)))
        response = session.post(
            EURONEXT_POWER_AJAX_URL,
            data=data,
            headers={
                **HEADERS,
                "Referer": EURONEXT_POWER_PAGE,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=HTTP_TIMEOUT_QUICK,
        )
        response.raise_for_status()
        for filename, rows in parse_euronext_power_snapshot(response.text).items():
            rows_by_file.setdefault(filename, []).extend(rows)
        time.sleep(REQUEST_DELAY)

    for filename, rows in rows_by_file.items():
        deduped = {(row["date"], row["contract"]): row for row in rows}
        rows_by_file[filename] = sorted(deduped.values(), key=lambda r: (r["date"], r["contract"]))
    return rows_by_file


def update_euronext_power_snapshot() -> dict[str, int]:
    """Append current Euronext power futures snapshot rows to local CSV files."""
    rows_by_file = fetch_euronext_power_snapshot()
    results: dict[str, int] = {}
    for filename, rows in rows_by_file.items():
        if not rows:
            continue
        results[filename] = save_to_csv(rows, NASDAQ_DATA_DIR / filename)
    return results


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
    import re

    pattern = re.compile(contract_filter)
    instruments = search_instruments(prefix)
    futures = [i for i in instruments if pattern.search(i["symbol"])]

    print(f"  Found {len(futures)} contracts for {prefix}")

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
            })
            count += 1

        print(f"{count} rows")

    return all_rows


def save_to_csv(rows: list[dict], filepath: Path) -> int:
    """Save rows to CSV, merging with existing data.

    Returns number of rows in the final file.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data
    existing = {}
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["date"], row["contract"])
                existing[key] = row

    # Merge new data (new overwrites old)
    for row in rows:
        key = (row["date"], row["contract"])
        existing[key] = row

    # Sort by date, then contract
    sorted_rows = sorted(existing.values(), key=lambda r: (r["date"], r["contract"]))

    # Write atomically: write to .tmp, then rename. Prevents truncation if
    # interrupted mid-write.
    tmp = filepath.with_suffix(filepath.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(sorted_rows)
    os.replace(tmp, filepath)

    return len(sorted_rows)


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

        rows = discover_and_download(prefix, from_date, to_date)

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
        print("Updating Euronext Nord Pool Power Futures snapshot")
        print(f"{'='*60}")
        euronext_results = update_euronext_power_snapshot()
        for filename, count in sorted(euronext_results.items()):
            key = filename.replace(".csv", "")
            results[key] = count
            print(f"  Updated {filename}: {count} rows")
    except Exception as e:
        from .failure_log import log_failure

        log_failure("euronext", "power_futures_snapshot", date.today().isoformat(), str(e))
        print(f"  Warning: Euronext snapshot update failed: {e}")

    return results
