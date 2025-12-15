#!/usr/bin/env python3
"""Incremental update of electricity prices - download only new data."""

import argparse
from datetime import date, timedelta

from elpris.api import fetch_day_prices
from elpris.config import EARLIEST_DATE, ZONES
from elpris.storage import append_day_data, get_latest_date


def update_zone(zone: str, verbose: bool = True) -> int:
    """
    Update a single zone with new data since last download.

    Returns the number of days downloaded.
    """
    latest = get_latest_date(zone)
    end_date = date.today() - timedelta(days=1)

    if latest is None:
        start_date = EARLIEST_DATE
        if verbose:
            print(f"{zone}: No existing data, starting from {start_date}")
    else:
        start_date = latest + timedelta(days=1)
        if verbose:
            print(f"{zone}: Last data from {latest}, checking from {start_date}")

    if start_date > end_date:
        if verbose:
            print(f"  Already up to date!")
        return 0

    downloaded = 0
    current = start_date

    while current <= end_date:
        if verbose:
            print(f"  {current}", end="", flush=True)

        try:
            data = fetch_day_prices(zone, current)
            if data is not None:
                append_day_data(zone, current, data)
                downloaded += 1
                if verbose:
                    print(f" - {len(data)} records")
            else:
                if verbose:
                    print(" - no data")
        except Exception as e:
            if verbose:
                print(f" - ERROR: {e}")

        current += timedelta(days=1)

    return downloaded


def main():
    parser = argparse.ArgumentParser(
        description="Update electricity prices - download only new data"
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        choices=ZONES,
        default=ZONES,
        help=f"Zones to update (default: all - {', '.join(ZONES)})",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    print("Updating electricity prices...")
    print("=" * 40)

    total = 0
    for zone in args.zones:
        days = update_zone(zone, verbose=not args.quiet)
        total += days
        if not args.quiet:
            print()

    print("=" * 40)
    if total > 0:
        print(f"Downloaded {total} new days of data")
    else:
        print("Already up to date!")


if __name__ == "__main__":
    main()
