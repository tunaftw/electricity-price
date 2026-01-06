"""eSett Open Data API client for Nordic imbalance settlement data.

Provides access to imbalance prices, regulation prices, and volumes
for Swedish bidding zones.

API documentation: https://api.opendata.esett.com/
"""

from __future__ import annotations

import csv
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import DATA_DIR, REQUEST_DELAY

# eSett API configuration
ESETT_BASE_URL = "https://api.opendata.esett.com"

# Swedish bidding zone EIC codes (same as ENTSO-E)
ESETT_ZONES = {
    "SE1": "10Y1001A1001A44P",
    "SE2": "10Y1001A1001A45N",
    "SE3": "10Y1001A1001A46L",
    "SE4": "10Y1001A1001A47J",
}

# Data directory
ESETT_DIR = DATA_DIR / "raw" / "esett"

# Data availability (15-min resolution started May 2023)
ESETT_EARLIEST_DATE = date(2023, 5, 22)


def get_latest_timestamp(zone: str) -> datetime | None:
    """
    Get the latest timestamp from existing eSett imbalance data for a zone.

    Args:
        zone: Swedish zone ("SE1", "SE2", "SE3", "SE4")

    Returns:
        datetime of the latest record, or None if no data exists
    """
    zone_dir = ESETT_DIR / "imbalance" / zone
    if not zone_dir.exists():
        return None

    # Find all year files
    year_files = sorted(zone_dir.glob("*.csv"))
    if not year_files:
        return None

    # Read last timestamp from the most recent year file
    latest_file = year_files[-1]
    last_ts = None

    with open(latest_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            last_ts = row["time_start"]

    if last_ts:
        # eSett timestamps are like "2024-12-01T00:00:00Z"
        ts_str = last_ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)

    return None


def _format_esett_datetime(d: date, end_of_day: bool = False) -> str:
    """Format date for eSett API (ISO 8601 with milliseconds)."""
    if end_of_day:
        dt = datetime(d.year, d.month, d.day, 23, 59, 59, 999000, tzinfo=timezone.utc)
    else:
        dt = datetime(d.year, d.month, d.day, 0, 0, 0, 0, tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


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
def fetch_imbalance_prices(
    zone: str,
    start_date: date,
    end_date: date,
) -> list[dict] | None:
    """
    Fetch imbalance prices from eSett Open Data API.

    Args:
        zone: Swedish zone ("SE1", "SE2", "SE3", "SE4")
        start_date: Start date
        end_date: End date

    Returns:
        List of price records, or None if request fails
    """
    if zone not in ESETT_ZONES:
        raise ValueError(f"Unknown zone: {zone}. Use: {list(ESETT_ZONES.keys())}")

    eic_code = ESETT_ZONES[zone]
    start_str = _format_esett_datetime(start_date)
    end_str = _format_esett_datetime(end_date, end_of_day=True)

    url = f"{ESETT_BASE_URL}/EXP14/Prices"
    params = {
        "mba": eic_code,
        "start": start_str,
        "end": end_str,
    }

    response = requests.get(url, params=params, timeout=60)

    if response.status_code == 400:
        # Bad request - possibly no data for this period
        return None

    if response.status_code == 429:
        raise Exception("Rate limit exceeded. Wait before retrying.")

    response.raise_for_status()
    return response.json()


def parse_imbalance_prices(json_data: list[dict], zone: str) -> Iterator[dict]:
    """
    Parse imbalance price response from eSett.

    Args:
        json_data: Raw JSON response from API
        zone: Zone name for the records

    Yields:
        Dict with parsed imbalance price data
    """
    for record in json_data:
        try:
            # Use UTC timestamp
            timestamp_utc = record.get("timestampUTC", "")
            if not timestamp_utc:
                continue

            yield {
                "time_start": timestamp_utc,
                "zone": zone,
                "imbl_sales_price_eur_mwh": record.get("imblSalesPrice"),
                "imbl_purchase_price_eur_mwh": record.get("imblPurchasePrice"),
                "up_reg_price_eur_mwh": record.get("upRegPrice"),
                "down_reg_price_eur_mwh": record.get("downRegPrice"),
                "main_dir_reg_power": record.get("mainDirRegPowerPerMBA"),
                "imbl_spot_diff_eur_mwh": record.get("imblSpotDifferencePrice"),
            }
        except Exception:
            continue


def get_imbalance_csv_path(zone: str, year: int) -> Path:
    """Get CSV file path for imbalance data."""
    zone_dir = ESETT_DIR / "imbalance" / zone
    zone_dir.mkdir(parents=True, exist_ok=True)
    return zone_dir / f"{year}.csv"


def get_imbalance_fieldnames() -> list[str]:
    """Get CSV fieldnames for imbalance data."""
    return [
        "time_start",
        "zone",
        "imbl_sales_price_eur_mwh",
        "imbl_purchase_price_eur_mwh",
        "up_reg_price_eur_mwh",
        "down_reg_price_eur_mwh",
        "main_dir_reg_power",
        "imbl_spot_diff_eur_mwh",
    ]


def save_imbalance_data(zone: str, records: list[dict], year: int) -> int:
    """
    Save imbalance data to CSV file.

    Returns:
        Number of records saved
    """
    if not records:
        return 0

    csv_path = get_imbalance_csv_path(zone, year)
    fieldnames = get_imbalance_fieldnames()

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


def download_imbalance_prices(
    zone: str,
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = True,
    force: bool = False,
) -> dict:
    """
    Download imbalance prices for a specific zone.

    Args:
        zone: Swedish zone ("SE1", "SE2", "SE3", "SE4")
        start_date: Start date (default: earliest available, or day after latest existing data)
        end_date: End date (default: yesterday)
        verbose: Print progress
        force: If True, ignore existing data and download from earliest date

    Returns:
        Dict with download statistics
    """
    if start_date is None:
        if force:
            start_date = ESETT_EARLIEST_DATE
        else:
            # Check for existing data
            latest = get_latest_timestamp(zone)
            if latest:
                start_date = latest.date() + timedelta(days=1)
                if verbose:
                    print(f"  Found existing data up to {latest.date()}, starting from {start_date}")
            else:
                start_date = ESETT_EARLIEST_DATE

    if end_date is None:
        end_date = date.today() - timedelta(days=1)

    # Ensure we don't request before data is available
    if start_date < ESETT_EARLIEST_DATE:
        start_date = ESETT_EARLIEST_DATE

    if verbose:
        print(f"Downloading imbalance prices for {zone} from {start_date} to {end_date}")

    total_records = 0
    current = start_date

    # Download in monthly chunks
    while current <= end_date:
        # Calculate chunk end (one month or end_date)
        if current.month == 12:
            chunk_end = min(date(current.year, 12, 31), end_date)
        else:
            chunk_end = min(date(current.year, current.month + 1, 1) - timedelta(days=1), end_date)

        if verbose:
            print(f"  {current} to {chunk_end}...", end=" ", flush=True)

        try:
            json_data = fetch_imbalance_prices(zone, current, chunk_end)

            if json_data:
                records = list(parse_imbalance_prices(json_data, zone))

                # Group by year and save
                by_year: dict[int, list[dict]] = {}
                for record in records:
                    # Parse year from timestamp
                    ts = record["time_start"]
                    year = int(ts[:4])
                    if year not in by_year:
                        by_year[year] = []
                    by_year[year].append(record)

                for year, year_records in by_year.items():
                    saved = save_imbalance_data(zone, year_records, year)
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
        "start_date": start_date,
        "end_date": end_date,
        "total_records": total_records,
    }


def download_all_imbalance_prices(
    zones: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = True,
    force: bool = False,
) -> list[dict]:
    """
    Download imbalance prices for multiple zones.

    Args:
        zones: List of zones (default: all Swedish zones)
        start_date: Start date
        end_date: End date
        verbose: Print progress
        force: If True, ignore existing data and download from earliest date

    Returns:
        List of download statistics per zone
    """
    if zones is None:
        zones = list(ESETT_ZONES.keys())

    results = []
    for zone in zones:
        result = download_imbalance_prices(
            zone=zone,
            start_date=start_date,
            end_date=end_date,
            verbose=verbose,
            force=force,
        )
        results.append(result)

    return results
