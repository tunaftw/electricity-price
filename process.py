#!/usr/bin/env python3
"""Process raw price data to quarterly (15-minute) resolution."""

import argparse

from elpris.config import ZONES
from elpris.processing import process_all


def main():
    parser = argparse.ArgumentParser(
        description="Process raw electricity prices to 15-minute resolution"
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        choices=ZONES,
        default=ZONES,
        help=f"Zones to process (default: all - {', '.join(ZONES)})",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    print("Processing raw data to quarterly (15-min) resolution")
    print("=" * 50)

    stats = process_all(zones=args.zones, verbose=not args.quiet)

    print("\n" + "=" * 50)
    print("Summary:")
    total = 0
    for zone, zone_stats in stats.items():
        records = zone_stats["total_records"]
        total += records
        print(f"  {zone}: {records:,} quarterly records")

    print("=" * 50)
    print(f"Total: {total:,} quarterly records")
    print("\nData saved to: data/quarterly/")


if __name__ == "__main__":
    main()
