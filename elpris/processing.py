"""Process raw price data to quarterly (15-minute) resolution."""

import csv
from datetime import datetime, timedelta
from pathlib import Path

from .config import CSV_FIELDS, RAW_DIR, QUARTERLY_DIR, ZONES


def is_quarterly_data(time_start: str, time_end: str) -> bool:
    """Check if a record is 15-minute data (vs hourly)."""
    start = datetime.fromisoformat(time_start)
    end = datetime.fromisoformat(time_end)
    diff = (end - start).total_seconds()
    return diff == 900  # 15 minutes = 900 seconds


def expand_hourly_to_quarterly(record: dict) -> list[dict]:
    """
    Expand an hourly record to 4 quarterly records with the same price.

    If already quarterly data, returns the record unchanged in a list.
    """
    time_start = record["time_start"]
    time_end = record["time_end"]

    if is_quarterly_data(time_start, time_end):
        return [record]

    # Parse the hourly timestamps
    start = datetime.fromisoformat(time_start)

    # Create 4 quarterly records
    quarterly_records = []
    for i in range(4):
        q_start = start + timedelta(minutes=15 * i)
        q_end = q_start + timedelta(minutes=15)

        quarterly_records.append({
            "time_start": q_start.isoformat(),
            "time_end": q_end.isoformat(),
            "SEK_per_kWh": record["SEK_per_kWh"],
            "EUR_per_kWh": record["EUR_per_kWh"],
            "EXR": record["EXR"],
        })

    return quarterly_records


def process_zone_year(zone: str, year: int) -> int:
    """
    Process a single zone/year file from raw to quarterly.

    Returns number of quarterly records written.
    """
    raw_path = RAW_DIR / zone / f"{year}.csv"
    quarterly_path = QUARTERLY_DIR / zone / f"{year}.csv"

    if not raw_path.exists():
        return 0

    # Ensure output directory exists
    quarterly_path.parent.mkdir(parents=True, exist_ok=True)

    records_written = 0

    with open(raw_path, "r", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)

        with open(quarterly_path, "w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=CSV_FIELDS)
            writer.writeheader()

            for record in reader:
                quarterly_records = expand_hourly_to_quarterly(record)
                writer.writerows(quarterly_records)
                records_written += len(quarterly_records)

    return records_written


def process_all(zones: list[str] = None, verbose: bool = True) -> dict:
    """
    Process all raw data to quarterly resolution.

    Returns dict with processing statistics.
    """
    if zones is None:
        zones = ZONES

    stats = {}

    for zone in zones:
        zone_raw_dir = RAW_DIR / zone
        if not zone_raw_dir.exists():
            if verbose:
                print(f"{zone}: No raw data found")
            continue

        zone_stats = {"years": {}, "total_records": 0}

        for csv_file in sorted(zone_raw_dir.glob("*.csv")):
            year = int(csv_file.stem)
            if verbose:
                print(f"{zone}/{year}: Processing...", end=" ", flush=True)

            records = process_zone_year(zone, year)
            zone_stats["years"][year] = records
            zone_stats["total_records"] += records

            if verbose:
                print(f"{records:,} quarterly records")

        stats[zone] = zone_stats

    return stats
