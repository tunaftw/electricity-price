#!/usr/bin/env python3
"""Download Nordic electricity futures from Nasdaq API.

Downloads settlement prices (daily fix) for:
- SYS Baseload (Nordic System Price)
- EPAD SE1 Luleå, SE2 Sundsvall, SE3 Stockholm, SE4 Malmö

Data is saved to Resultat/marknadsdata/nasdaq/futures/.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from elpris.nasdaq import PRODUCTS, download_all_futures


def main():
    parser = argparse.ArgumentParser(
        description="Download Nordic electricity futures from Nasdaq"
    )
    parser.add_argument(
        "--products",
        nargs="+",
        choices=["sys", "epad_se", "epad_se1", "epad_se2", "epad_se3", "epad_se4"],
        default=None,
        help="Products to download (default: all)",
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=date(2024, 1, 1),
        help="Start date (default: 2024-01-01)",
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=date.today() - timedelta(days=1),
        help="End date (default: yesterday)",
    )
    args = parser.parse_args()

    print(f"Nasdaq Nordic Futures Download")
    print(f"Period: {args.start} -> {args.end}")
    if args.products:
        print(f"Products: {', '.join(args.products)}")
    else:
        print(f"Products: all ({len(PRODUCTS)} products)")

    results = download_all_futures(args.start, args.end, args.products)

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"{'='*60}")
    for name, count in results.items():
        print(f"  {name}: {count} rows")


if __name__ == "__main__":
    main()
