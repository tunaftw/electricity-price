#!/usr/bin/env python3
"""Show download status for electricity price data."""

import csv
from pathlib import Path

from elpris.config import RAW_DIR, QUARTERLY_DIR, ZONES


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def get_dir_stats(base_dir: Path, zone: str) -> dict:
    """Get statistics for a zone's data in a specific directory."""
    zone_dir = base_dir / zone
    if not zone_dir.exists():
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

    for csv_file in sorted(zone_dir.glob("*.csv")):
        total_size += csv_file.stat().st_size
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_records += 1
                ts = row["time_start"]
                if first_date is None:
                    first_date = ts[:10]
                last_date = ts[:10]

    return {
        "zone": zone,
        "first_date": first_date,
        "last_date": last_date,
        "records": total_records,
        "size_bytes": total_size,
    }


def print_table(title: str, base_dir: Path):
    """Print a status table for a data directory."""
    print(f"\n{title}")
    print(f"Path: {base_dir}")
    print("=" * 60)
    print(f"{'Zone':<6} {'First Date':<12} {'Last Date':<12} {'Records':>10} {'Size':>10}")
    print("-" * 60)

    total_records = 0
    total_size = 0
    has_data = False

    for zone in ZONES:
        s = get_dir_stats(base_dir, zone)
        first = s["first_date"] or "-"
        last = s["last_date"] or "-"
        records = s["records"]
        size = s["size_bytes"]

        if records > 0:
            has_data = True

        total_records += records
        total_size += size

        print(
            f"{zone:<6} {first:<12} {last:<12} {records:>10,} {format_size(size):>10}"
        )

    print("-" * 60)
    print(
        f"{'Total':<6} {'':<12} {'':<12} {total_records:>10,} {format_size(total_size):>10}"
    )
    print("=" * 60)

    return has_data


def main():
    print("Swedish Electricity Price Data Status")

    has_raw = print_table("RAW DATA (mixed resolution)", RAW_DIR)
    has_quarterly = print_table("QUARTERLY DATA (15-min resolution)", QUARTERLY_DIR)

    if not has_raw:
        print("\nNo raw data downloaded yet. Run 'python download.py' to get started.")
    elif not has_quarterly:
        print("\nNo quarterly data yet. Run 'python process.py' to convert raw → quarterly.")


if __name__ == "__main__":
    main()
