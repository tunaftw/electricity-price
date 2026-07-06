#!/usr/bin/env python3
"""Download Nordic electricity futures history and current snapshot.

Downloads settlement prices for:
- SYS Baseload (Nordic System Price)
- EPAD SE1 Luleå, SE2 Sundsvall, SE3 Stockholm, SE4 Malmö

Uses Nasdaq for history and Euronext/Nord Pool Power Futures for current
snapshot settlements.
Data is saved to Resultat/marknadsdata/nasdaq/futures/.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from elpris.failure_log import failure_count
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

    print(f"Nordic Futures Download")
    print(f"Period: {args.start} -> {args.end}")
    if args.products:
        print(f"Products: {', '.join(args.products)}")
    else:
        print(f"Products: all ({len(PRODUCTS)} products)")

    failures_before = failure_count()
    results = download_all_futures(args.start, args.end, args.products)

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"{'='*60}")
    for name, count in results.items():
        print(f"  {name}: {count} rows")

    failed = failure_count() - failures_before
    if failed:
        print(
            f"\nWARNING: {failed} chunk(s) failed — data has gaps. "
            f"See Resultat/logs/failed_chunks.csv for details."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
