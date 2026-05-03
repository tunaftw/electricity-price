"""CSV file storage management."""

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .config import CSV_FIELDS, RAW_DIR, ZONES


def get_csv_path(zone: str, year: int) -> Path:
    """Return path to raw CSV file for zone and year."""
    return RAW_DIR / zone / f"{year}.csv"


def get_zone_years(zone: str) -> list[int]:
    """Get list of years with raw data for a zone."""
    zone_dir = RAW_DIR / zone
    if not zone_dir.exists():
        return []
    return sorted([int(f.stem) for f in zone_dir.glob("*.csv")])


def get_latest_timestamp(zone: str) -> Optional[datetime]:
    """
    Find the latest downloaded timestamp for a zone.

    Walks year files from newest to oldest until it finds a non-empty one,
    so empty/header-only year files don't mask earlier data.

    Note: this returns the literal latest timestamp, not the latest
    *contiguous* one. If a year-end gap exists (e.g. 2024 missing
    Dec 15-31 while 2025 has data), incremental download will skip the
    older gap. Use ``find_data_gaps`` (or ``status.py``) to detect such
    gaps, then run ``download.py --start ... --end ...`` to backfill.

    Returns None if no data exists.
    """
    years = get_zone_years(zone)
    if not years:
        return None

    # Walk newest → oldest until we find a year file with at least one row.
    # Protects against the edge case where the latest year file exists but
    # is empty (header only) — without this, we'd return None and re-download
    # the entire year unnecessarily.
    for year in reversed(years):
        csv_path = get_csv_path(zone, year)
        if not csv_path.exists():
            continue
        last_timestamp = None
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                last_timestamp = row["time_start"]
        if last_timestamp is not None:
            return datetime.fromisoformat(last_timestamp)

    return None


def find_data_gaps(zone: str, max_gap_hours: int = 2) -> list[tuple[datetime, datetime]]:
    """
    Scan all year files for a zone and return gaps in coverage.

    A gap is any pair of adjacent timestamps separated by more than
    ``max_gap_hours``. The default 2h tolerates the spring DST jump
    (1h gap) but flags real missing days.

    Returns a list of (gap_start, gap_end) tuples — both are tz-aware
    datetimes from the CSV. Empty list means no gaps.
    """
    years = get_zone_years(zone)
    if not years:
        return []

    from datetime import timedelta

    threshold = timedelta(hours=max_gap_hours)
    prev: Optional[datetime] = None
    gaps: list[tuple[datetime, datetime]] = []

    for year in years:
        csv_path = get_csv_path(zone, year)
        if not csv_path.exists():
            continue
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cur = datetime.fromisoformat(row["time_start"])
                if prev is not None and (cur - prev) > threshold:
                    gaps.append((prev, cur))
                prev = cur

    return gaps


def get_latest_date(zone: str) -> Optional[date]:
    """Get the date of the latest downloaded data for a zone."""
    ts = get_latest_timestamp(zone)
    if ts is None:
        return None
    return ts.date()


def append_day_data(zone: str, target_date: date, records: list[dict]) -> None:
    """
    Append price records for a day to the appropriate year file.

    Creates the zone directory and file with header if they don't exist.
    """
    csv_path = get_csv_path(zone, target_date.year)

    # Ensure zone directory exists
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if file exists to determine if we need header
    write_header = not csv_path.exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(records)


def get_zone_stats(zone: str) -> dict:
    """Get statistics for a zone's downloaded data."""
    years = get_zone_years(zone)
    if not years:
        return {
            "zone": zone,
            "first_date": None,
            "last_date": None,
            "records": 0,
            "size_bytes": 0,
        }

    total_records = 0
    total_size = 0
    first_date = None
    last_date = None

    for year in years:
        csv_path = get_csv_path(zone, year)
        if csv_path.exists():
            total_size += csv_path.stat().st_size
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_records += 1
                    ts = row["time_start"]
                    if first_date is None:
                        first_date = ts[:10]  # Extract date part
                    last_date = ts[:10]

    return {
        "zone": zone,
        "first_date": first_date,
        "last_date": last_date,
        "records": total_records,
        "size_bytes": total_size,
    }


def get_all_stats() -> list[dict]:
    """Get statistics for all zones."""
    return [get_zone_stats(zone) for zone in ZONES]
