#!/usr/bin/env python3
"""Download imbalance prices from eSett Open Data API.

eSett provides Nordic imbalance settlement data including:
- Imbalance prices (purchase/sales)
- Regulation prices (up/down)
- Main direction of regulation power

Data is available from May 2023 with 15-minute resolution.
No API key required - completely free and open.
"""

from __future__ import annotations

import argparse
from datetime import date

from elpris.esett import (
    ESETT_EARLIEST_DATE,
    ESETT_ZONES,
    download_all_imbalance_prices,
)


def main():
    parser = argparse.ArgumentParser(
        description="Download imbalance prices from eSett Open Data API"
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        choices=list(ESETT_ZONES.keys()),
        default=None,
        help="Zones to download (default: all)",
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=None,
        help=f"Start date (YYYY-MM-DD, earliest: {ESETT_EARLIEST_DATE})",
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
        help="End date (YYYY-MM-DD, default: yesterday)",
    )

    args = parser.parse_args()

    zones = args.zones or list(ESETT_ZONES.keys())

    print("eSett Open Data Downloader")
    print("=" * 50)
    print(f"Zones: {', '.join(zones)}")
    if args.start:
        print(f"Start: {args.start}")
    else:
        print(f"Start: {ESETT_EARLIEST_DATE} (earliest available)")
    if args.end:
        print(f"End: {args.end}")
    print("=" * 50)
    print()

    results = download_all_imbalance_prices(
        zones=zones,
        start_date=args.start,
        end_date=args.end,
        verbose=True,
    )

    print("\n" + "=" * 50)
    print("Download complete!")
    print()
    total = sum(r["total_records"] for r in results)
    print(f"Total records: {total}")
    print("Data saved to: data/raw/esett/imbalance/")

    return 0


if __name__ == "__main__":
    exit(main())
