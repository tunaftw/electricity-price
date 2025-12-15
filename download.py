#!/usr/bin/env python3
"""Download historical electricity prices from elprisetjustnu.se."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from elpris.api import fetch_day_prices
from elpris.config import EARLIEST_DATE, ZONES
from elpris.storage import append_day_data, get_latest_date


def download_zone(
    zone: str,
    start_date: date,
    end_date: date,
    verbose: bool = True,
) -> int:
    """
    Download data for a single zone over a date range.

    Returns the number of days successfully downloaded.
    """
    downloaded = 0
    current = start_date
    total_days = (end_date - start_date).days + 1

    while current <= end_date:
        day_num = (current - start_date).days + 1
        if verbose:
            print(f"  [{day_num}/{total_days}] {current}", end="", flush=True)

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


def download_historical(
    zones: list[str],
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = True,
) -> dict[str, int]:
    """
    Download historical data for specified zones.

    Returns dict mapping zone to number of days downloaded.
    """
    if start_date is None:
        start_date = EARLIEST_DATE
    if end_date is None:
        end_date = date.today() - timedelta(days=1)

    results = {}
    for zone in zones:
        # Check if we already have data and adjust start date
        latest = get_latest_date(zone)
        zone_start = start_date
        if latest is not None and latest >= start_date:
            zone_start = latest + timedelta(days=1)
            if verbose:
                print(f"\n{zone}: Data exists until {latest}, starting from {zone_start}")
        else:
            if verbose:
                print(f"\n{zone}: Downloading from {zone_start}")

        if zone_start > end_date:
            if verbose:
                print(f"  Already up to date!")
            results[zone] = 0
            continue

        results[zone] = download_zone(zone, zone_start, end_date, verbose)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Download historical electricity prices from elprisetjustnu.se"
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        choices=ZONES,
        default=ZONES,
        help=f"Zones to download (default: all - {', '.join(ZONES)})",
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=None,
        help=f"Start date in YYYY-MM-DD format (default: {EARLIEST_DATE})",
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
        help="End date in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    print("Swedish Electricity Price Downloader")
    print("=" * 40)
    print(f"Zones: {', '.join(args.zones)}")
    print(f"Start: {args.start or EARLIEST_DATE}")
    print(f"End: {args.end or (date.today() - timedelta(days=1))}")
    print("=" * 40)

    results = download_historical(
        zones=args.zones,
        start_date=args.start,
        end_date=args.end,
        verbose=not args.quiet,
    )

    print("\n" + "=" * 40)
    print("Summary:")
    for zone, days in results.items():
        print(f"  {zone}: {days} days downloaded")
    print("=" * 40)

    total = sum(results.values())
    if total > 0:
        print(f"\nTotal: {total} days downloaded successfully")
    else:
        print("\nNo new data to download")


if __name__ == "__main__":
    main()
