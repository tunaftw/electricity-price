#!/usr/bin/env python3
"""Download solar park production data from Bazefield monitoring platform.

Requires BAZEFIELD_API_KEY environment variable or .env file.
"""

from __future__ import annotations

import argparse
from datetime import date

from elpris.bazefield import (
    BAZEFIELD_API_KEY,
    PARKS,
    download_all_parks,
    print_status,
)


def main():
    parser = argparse.ArgumentParser(
        description="Download solar park production data from Bazefield"
    )
    parser.add_argument(
        "--parks",
        nargs="+",
        choices=list(PARKS.keys()),
        default=None,
        help="Parks to download (default: all)",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Search for first available data and download full history",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show sync status and exit",
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=None,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
        help="End date (YYYY-MM-DD)",
    )

    args = parser.parse_args()

    if args.status:
        print_status()
        return 0

    if not BAZEFIELD_API_KEY:
        print("Error: BAZEFIELD_API_KEY not set.")
        print()
        print("Add to .env file:")
        print("  BAZEFIELD_API_KEY=your-api-key-here")
        return 1

    parks = args.parks or list(PARKS.keys())

    print("Bazefield Solar Park Downloader")
    print("=" * 50)
    print(f"Parker: {', '.join(parks)}")
    if args.backfill:
        print("Läge: Full historik (backfill)")
    else:
        print("Läge: Inkrementell uppdatering")
    print("=" * 50)

    results = download_all_parks(
        park_keys=parks,
        start_date=args.start,
        end_date=args.end,
        backfill=args.backfill,
        verbose=True,
    )

    print("\n" + "=" * 50)
    print("Nedladdning klar!")
    print()
    total = sum(r["total_records"] for r in results)
    print(f"Totalt nya poster: {total}")

    print_status()

    return 0


if __name__ == "__main__":
    exit(main())
