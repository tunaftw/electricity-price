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
    download_park_inverters,
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
    parser.add_argument(
        "--inverters",
        action="store_true",
        help="Sync inverter-level data (daily yield + alarm events) per park. "
             "Tar 5-15 min per park. K\u00f6rs separat fr\u00e5n park-niv\u00e5 sync.",
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
    if args.inverters:
        print("L\u00e4ge: Inverter-niv\u00e5 (daglig yield + alarm events)")
    elif args.backfill:
        print("Läge: Full historik (backfill)")
    else:
        print("Läge: Inkrementell uppdatering")
    print("=" * 50)

    if args.inverters:
        # Inverter-mode: synka inverter-data + events per park
        # Default-period: senaste 100 dagar om inget angivet
        from datetime import date as _date, timedelta as _td
        end = args.end or _date.today()
        start = args.start or (end - _td(days=100))

        total_yield = 0
        total_events = 0
        for park_key in parks:
            try:
                result = download_park_inverters(
                    park_key=park_key,
                    start_date=start,
                    end_date=end,
                    verbose=True,
                )
                total_yield += result.get("yield_records", 0)
                total_events += result.get("event_records", 0)
            except Exception as e:
                print(f"\n[FEL] {park_key}: {e}")

        print("\n" + "=" * 50)
        print("Inverter-synk klar!")
        print(f"  Totalt yield-rader: {total_yield}")
        print(f"  Totalt alarm-events: {total_events}")
        return 0

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
