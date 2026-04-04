"""Nasdaq Nordic Commodities API client for electricity futures.

Downloads settlement prices (daily fix) for Nordic system price (SYS)
baseload futures and EPAD (Electricity Price Area Differential) contracts
for Swedish bidding zones.

API: Undocumented JSON API at api.nasdaq.com (no key required).
Note: Trading moved to Euronext in March 2026 but Nasdaq continues
publishing daily settlement prices.
"""

from __future__ import annotations

import csv
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import NASDAQ_DATA_DIR

# API configuration
NASDAQ_BASE_URL = "https://api.nasdaq.com/api/nordic"
REQUEST_DELAY = 0.5  # seconds between requests

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

# CSV fields
CSV_FIELDS = [
    "date", "contract", "daily_fix_eur",
    "bid_eur", "ask_eur", "high_eur", "low_eur", "open_interest",
]

# Max date range per API request (~90 days works reliably)
MAX_DAYS_PER_REQUEST = 90


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def _api_get(endpoint: str, params: dict | None = None) -> dict:
    """Make a GET request to the Nasdaq API with retries.

    Raises requests.HTTPError on non-200 responses (after retries).
    """
    url = f"{NASDAQ_BASE_URL}/{endpoint}"
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
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
    """
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
        except Exception:
            # API returns 400 for date ranges before instrument started trading
            pass

        chunk_start = chunk_end + timedelta(days=1)
        if chunk_start <= to_date:
            time.sleep(REQUEST_DELAY)

    return all_rows


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
            daily_fix = r.get("dailyFix", "").strip()
            if not daily_fix:
                continue
            all_rows.append({
                "date": r["date"],
                "contract": symbol,
                "daily_fix_eur": daily_fix,
                "bid_eur": r.get("bidPrice", "").strip() or "",
                "ask_eur": r.get("askPrice", "").strip() or "",
                "high_eur": r.get("highPrice", "").strip() or "",
                "low_eur": r.get("lowPrice", "").strip() or "",
                "open_interest": r.get("oi", "").strip().replace(",", "") or "",
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
        with open(filepath, "r") as f:
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

    # Write
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(sorted_rows)

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

    return results
