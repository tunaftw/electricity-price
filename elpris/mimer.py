"""Svenska kraftnät Mimer API client for balancing market data.

Provides access to FCR, aFRR, and mFRR prices and volumes.
"""

from __future__ import annotations

import csv
import io
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import MIMER_DATA_DIR, REQUEST_DELAY

# Mimer base URL
MIMER_BASE_URL = "https://mimer.svk.se"

# Mimer endpoints
MIMER_ENDPOINTS = {
    "fcr": "/PrimaryRegulation/DownloadText",
    "afrr": "/AutomaticFrequencyRestorationReserve/DownloadText",
    "mfrr_cm": "/ManualFrequencyRestorationReserveCM/DownloadText",
    "mfrr": "/ManualFrequencyRestorationReserve/DownloadText",
}

# Data directory for Mimer
MIMER_DIR = MIMER_DATA_DIR

# Zone mapping (Mimer uses different zone names)
MIMER_ZONES = {
    "SE1": "SN1",
    "SE2": "SN2",
    "SE3": "SN3",
    "SE4": "SN4",
}

# Data availability
MIMER_EARLIEST_DATES = {
    "fcr": date(2021, 1, 1),  # FCR data available from 2021
    "afrr": date(2022, 11, 1),  # aFRR market started Nov 2022
    "mfrr_cm": date(2024, 6, 1),  # mFRR capacity market started mid-2024
    "mfrr": date(2022, 1, 1),  # mFRR energy activation data
}


def _format_mimer_date(d: date) -> str:
    """Format date for Mimer API (MM/DD/YYYY HH:MM:SS)."""
    return f"{d.month:02d}/{d.day:02d}/{d.year} 00:00:00"


def _rate_limited(func):
    """Decorator to add rate limiting between API calls."""
    last_call = [0.0]  # Mutable to allow modification in closure

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
def fetch_mimer_data(
    product: str,
    start_date: date,
    end_date: date,
    constraint_area_id: int = 0,
) -> str | None:
    """
    Fetch data from Mimer API.

    Args:
        product: Product type ("fcr", "afrr", "mfrr_cm")
        start_date: Start date
        end_date: End date
        constraint_area_id: 0 for all areas, or specific area ID

    Returns:
        CSV content as string, or None if request fails
    """
    if product not in MIMER_ENDPOINTS:
        raise ValueError(f"Unknown product: {product}. Use: {list(MIMER_ENDPOINTS.keys())}")

    endpoint = MIMER_ENDPOINTS[product]
    url = f"{MIMER_BASE_URL}{endpoint}"

    params = {
        "periodFrom": _format_mimer_date(start_date),
        "periodTo": _format_mimer_date(end_date),
    }

    # FCR requires additional parameters
    if product == "fcr":
        params["auctionTypeId"] = 1  # 0=All, 1=Total (volume-weighted)
        params["productTypeId"] = 0  # 0=All products
    else:
        params["ConstraintAreaId"] = constraint_area_id

    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()

    return response.text


def _parse_price(val: str) -> float | None:
    """Parse a price value from Mimer CSV (handles comma decimal separator)."""
    if not val or val.strip() == "":
        return None
    val = val.strip().replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return None


def parse_fcr_csv(csv_content: str) -> Iterator[dict]:
    """
    Parse FCR CSV content from Mimer.

    FCR CSV format (semicolon-separated):
    Datum;FCR-N Pris (EUR/MW);Total;SE1 FCRN;...;FCR-D upp Pris (EUR/MW);...;FCR-D ned Pris (EUR/MW);...

    This is aggregate market data with weighted average prices and volumes per zone.

    Yields:
        Dict with parsed FCR data (one row per hour with prices and zone volumes)
    """
    # Remove BOM if present (can be \ufeff or the UTF-8 bytes as latin-1)
    if csv_content.startswith("\ufeff"):
        csv_content = csv_content[1:]
    elif csv_content.startswith("ï»¿"):
        csv_content = csv_content[3:]

    reader = csv.DictReader(io.StringIO(csv_content), delimiter=";")

    for row in reader:
        try:
            # Parse timestamp from "Datum" column
            period_str = row.get("Datum", "").strip()
            if not period_str:
                continue

            # Try different date formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"]:
                try:
                    ts = datetime.strptime(period_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                continue

            # Parse prices (weighted average for total market)
            fcr_n_price = _parse_price(row.get("FCR-N Pris (EUR/MW)", ""))
            fcr_d_up_price = _parse_price(row.get("FCR-D upp Pris (EUR/MW)", ""))
            fcr_d_down_price = _parse_price(row.get("FCR-D ned Pris (EUR/MW)", ""))

            # Parse total volumes
            fcr_n_volume = _parse_price(row.get("Total", ""))
            fcr_d_up_volume = _parse_price(row.get("Total FCRD upp", ""))
            fcr_d_down_volume = _parse_price(row.get("Total FCRD ned", ""))

            yield {
                "time_start": ts.isoformat(),
                "fcr_n_price_eur_mw": fcr_n_price,
                "fcr_n_volume_mw": fcr_n_volume,
                "fcr_d_up_price_eur_mw": fcr_d_up_price,
                "fcr_d_up_volume_mw": fcr_d_up_volume,
                "fcr_d_down_price_eur_mw": fcr_d_down_price,
                "fcr_d_down_volume_mw": fcr_d_down_volume,
            }
        except Exception:
            # Skip malformed rows
            continue


def parse_afrr_csv(csv_content: str) -> Iterator[dict]:
    """
    Parse aFRR CSV content from Mimer.

    Yields:
        Dict with parsed aFRR data
    """
    # Remove BOM if present
    if csv_content.startswith("\ufeff"):
        csv_content = csv_content[1:]
    elif csv_content.startswith("ï»¿"):
        csv_content = csv_content[3:]

    reader = csv.DictReader(io.StringIO(csv_content), delimiter=";")

    for row in reader:
        try:
            period_str = row.get("Period", "").strip()
            if not period_str:
                continue

            for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M"]:
                try:
                    ts = datetime.strptime(period_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                continue

            # Zone can be in different columns depending on encoding
            zone = ""
            for key in row.keys():
                if "omr" in key.lower() or key.startswith("El"):
                    zone = row[key].strip()
                    break

            yield {
                "time_start": ts.isoformat(),
                "zone": zone,
                "afrr_up_price_eur_mw": _parse_price(row.get("aFRR Upp Pris (EUR/MW)", "")),
                "afrr_up_volume_mw": _parse_price(row.get("aFRR Upp Volym (MW)", "")),
                "afrr_down_price_eur_mw": _parse_price(row.get("aFRR Ned Pris (EUR/MW)", "")),
                "afrr_down_volume_mw": _parse_price(row.get("aFRR Ned Volym (MW)", "")),
            }
        except Exception:
            continue


def parse_mfrr_cm_csv(csv_content: str) -> Iterator[dict]:
    """
    Parse mFRR capacity market CSV content from Mimer.

    Yields:
        Dict with parsed mFRR-CM data
    """
    # Remove BOM if present
    if csv_content.startswith("\ufeff"):
        csv_content = csv_content[1:]
    elif csv_content.startswith("ï»¿"):
        csv_content = csv_content[3:]

    reader = csv.DictReader(io.StringIO(csv_content), delimiter=";")

    for row in reader:
        try:
            period_str = row.get("Period", "").strip()
            if not period_str:
                continue

            for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M"]:
                try:
                    ts = datetime.strptime(period_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                continue

            # Zone can be in different columns depending on encoding
            zone = ""
            for key in row.keys():
                if "omr" in key.lower() or key.startswith("El"):
                    zone = row[key].strip()
                    break

            yield {
                "time_start": ts.isoformat(),
                "zone": zone,
                "mfrr_cm_up_price_eur_mw": _parse_price(row.get("mFRR Upp Pris (EUR/MW)", "")),
                "mfrr_cm_up_volume_mw": _parse_price(row.get("mFRR Upp Volym (MW)", "")),
                "mfrr_cm_down_price_eur_mw": _parse_price(row.get("mFRR Ned Pris (EUR/MW)", "")),
                "mfrr_cm_down_volume_mw": _parse_price(row.get("mFRR Ned Volym (MW)", "")),
            }
        except Exception:
            continue


def parse_mfrr_csv(csv_content: str) -> Iterator[dict]:
    """
    Parse mFRR energy activation CSV content from Mimer.

    Note: Data format is hourly before March 2025, 15-min after.
    After mFRR EAM introduction (March 2025), data may be empty in Mimer.
    Use eSett for post-EAM activation data.

    Yields:
        Dict with parsed mFRR activation data
    """
    # Remove BOM if present
    if csv_content.startswith("\ufeff"):
        csv_content = csv_content[1:]
    elif csv_content.startswith("ï»¿"):
        csv_content = csv_content[3:]

    reader = csv.DictReader(io.StringIO(csv_content), delimiter=";")

    for row in reader:
        try:
            period_str = row.get("Period", "").strip()
            if not period_str:
                continue

            for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M"]:
                try:
                    ts = datetime.strptime(period_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                continue

            # Zone can be in different columns depending on encoding
            zone = ""
            for key in row.keys():
                if "omr" in key.lower() or key.startswith("El"):
                    zone = row[key].strip()
                    break

            # Map Mimer zone names back to standard SE names
            zone_map = {"SN1": "SE1", "SN2": "SE2", "SN3": "SE3", "SN4": "SE4"}
            zone = zone_map.get(zone, zone)

            yield {
                "time_start": ts.isoformat(),
                "zone": zone,
                "mfrr_up_price_eur_mwh": _parse_price(row.get("mFRR Upp Pris (EUR/MWh)", "")),
                "mfrr_up_volume_mwh": _parse_price(row.get("mFRR Upp Volym (MW)h", "")),
                "mfrr_down_price_eur_mwh": _parse_price(row.get("mFRR Ned Pris (EUR/MWh)", "")),
                "mfrr_down_volume_mwh": _parse_price(row.get("mFRR Ned Volym (MW)h", "")),
            }
        except Exception:
            continue


def get_csv_path(product: str, year: int) -> Path:
    """Get the CSV file path for a product and year."""
    product_dir = MIMER_DIR / product
    product_dir.mkdir(parents=True, exist_ok=True)
    return product_dir / f"{year}.csv"


def get_fcr_fieldnames() -> list[str]:
    """Get CSV fieldnames for FCR data."""
    return [
        "time_start",
        "fcr_n_price_eur_mw",
        "fcr_n_volume_mw",
        "fcr_d_up_price_eur_mw",
        "fcr_d_up_volume_mw",
        "fcr_d_down_price_eur_mw",
        "fcr_d_down_volume_mw",
    ]


def get_afrr_fieldnames() -> list[str]:
    """Get CSV fieldnames for aFRR data."""
    return [
        "time_start",
        "zone",
        "afrr_up_price_eur_mw",
        "afrr_up_volume_mw",
        "afrr_down_price_eur_mw",
        "afrr_down_volume_mw",
    ]


def get_mfrr_cm_fieldnames() -> list[str]:
    """Get CSV fieldnames for mFRR-CM data."""
    return [
        "time_start",
        "zone",
        "mfrr_cm_up_price_eur_mw",
        "mfrr_cm_up_volume_mw",
        "mfrr_cm_down_price_eur_mw",
        "mfrr_cm_down_volume_mw",
    ]


def get_mfrr_fieldnames() -> list[str]:
    """Get CSV fieldnames for mFRR energy activation data."""
    return [
        "time_start",
        "zone",
        "mfrr_up_price_eur_mwh",
        "mfrr_up_volume_mwh",
        "mfrr_down_price_eur_mwh",
        "mfrr_down_volume_mwh",
    ]


def save_mimer_data(product: str, records: list[dict], year: int) -> int:
    """
    Save Mimer data to CSV file.

    Args:
        product: Product type
        records: List of parsed records
        year: Year for the data

    Returns:
        Number of records saved
    """
    if not records:
        return 0

    csv_path = get_csv_path(product, year)

    # Get fieldnames based on product
    if product == "fcr":
        fieldnames = get_fcr_fieldnames()
    elif product == "afrr":
        fieldnames = get_afrr_fieldnames()
    elif product == "mfrr_cm":
        fieldnames = get_mfrr_cm_fieldnames()
    elif product == "mfrr":
        fieldnames = get_mfrr_fieldnames()
    else:
        raise ValueError(f"Unknown product: {product}")

    # Read existing data if file exists
    existing_records = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Use time_start + zone (if present) as key
                key = (row["time_start"], row.get("zone", ""))
                existing_records[key] = row

    # Merge new records (use same key structure)
    for record in records:
        key = (record["time_start"], record.get("zone", ""))
        existing_records[key] = record

    # Sort by time and zone
    sorted_records = sorted(existing_records.values(), key=lambda x: (x["time_start"], x.get("zone", "")))

    # Write back
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_records)

    return len(records)


def get_latest_timestamp(product: str) -> datetime | None:
    """
    Get the latest timestamp from existing Mimer data for a product.

    Checks all year files and returns the most recent timestamp found.

    Args:
        product: Product type ("fcr", "afrr", "mfrr_cm", "mfrr")

    Returns:
        Latest timestamp as datetime, or None if no data exists
    """
    product_dir = MIMER_DIR / product
    if not product_dir.exists():
        return None

    # Find all year files
    year_files = sorted(product_dir.glob("*.csv"))

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
        # Parse timestamp (format: 2025-01-01T00:00:00)
        try:
            return datetime.fromisoformat(last_ts)
        except ValueError:
            # Try adding timezone if missing
            return datetime.fromisoformat(last_ts + "+00:00")

    return None


def download_mimer_product(
    product: str,
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = True,
    force: bool = False,
) -> dict:
    """
    Download data for a Mimer product.

    Args:
        product: Product type ("fcr", "afrr", "mfrr_cm", "mfrr")
        start_date: Start date (default: day after latest existing data, or earliest available)
        end_date: End date (default: yesterday)
        verbose: Print progress
        force: If True, ignore existing data and download from earliest date

    Returns:
        Dict with download statistics
    """
    if start_date is None:
        if force:
            # Force full download from earliest date
            start_date = MIMER_EARLIEST_DATES.get(product, date(2021, 1, 1))
        else:
            # Check for existing data and continue from where we left off
            latest = get_latest_timestamp(product)
            if latest:
                start_date = latest.date() + timedelta(days=1)
                if verbose:
                    print(f"  Found existing data up to {latest.date()}, starting from {start_date}")
            else:
                start_date = MIMER_EARLIEST_DATES.get(product, date(2021, 1, 1))

    if end_date is None:
        end_date = date.today() - timedelta(days=1)

    if verbose:
        print(f"Downloading {product.upper()} data from {start_date} to {end_date}")

    # Select parser based on product
    if product == "fcr":
        parser = parse_fcr_csv
    elif product == "afrr":
        parser = parse_afrr_csv
    elif product == "mfrr_cm":
        parser = parse_mfrr_cm_csv
    elif product == "mfrr":
        parser = parse_mfrr_csv
    else:
        raise ValueError(f"Unknown product: {product}")

    # Download in monthly chunks to avoid timeout
    total_records = 0
    current = start_date

    while current <= end_date:
        # Calculate chunk end (one month or end_date)
        chunk_end = min(
            date(current.year, current.month + 1, 1) - timedelta(days=1)
            if current.month < 12
            else date(current.year, 12, 31),
            end_date,
        )

        if verbose:
            print(f"  {current} to {chunk_end}...", end=" ", flush=True)

        try:
            csv_content = fetch_mimer_data(product, current, chunk_end)
            if csv_content:
                records = list(parser(csv_content))

                # Group records by year and save
                by_year: dict[int, list[dict]] = {}
                for record in records:
                    ts = datetime.fromisoformat(record["time_start"])
                    year = ts.year
                    if year not in by_year:
                        by_year[year] = []
                    by_year[year].append(record)

                for year, year_records in by_year.items():
                    saved = save_mimer_data(product, year_records, year)
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
        print(f"Total: {total_records} records downloaded")

    return {
        "product": product,
        "start_date": start_date,
        "end_date": end_date,
        "total_records": total_records,
    }
