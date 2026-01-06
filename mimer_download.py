#!/usr/bin/env python3
"""Download balancing market data from Svenska kraftnät Mimer."""

from __future__ import annotations

import argparse
from datetime import date

from elpris.mimer import (
    MIMER_EARLIEST_DATES,
    MIMER_ENDPOINTS,
    download_mimer_product,
)


def main():
    parser = argparse.ArgumentParser(
        description="Download FCR, aFRR, and mFRR data from Svenska kraftnät Mimer"
    )
    parser.add_argument(
        "--product",
        choices=list(MIMER_ENDPOINTS.keys()),
        default=None,
        help="Product to download (default: all)",
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
        "--force",
        action="store_true",
        help="Ignore existing data and download full history from earliest date",
    )

    args = parser.parse_args()

    print("Svenska kraftnät Mimer Downloader")
    print("=" * 50)

    if args.product:
        products = [args.product]
    else:
        products = list(MIMER_ENDPOINTS.keys())

    print(f"Products: {', '.join(p.upper() for p in products)}")
    if args.start:
        print(f"Start: {args.start}")
    if args.end:
        print(f"End: {args.end}")
    print("=" * 50)
    print()

    for product in products:
        # Determine start date:
        # - If --start provided: use that
        # - If --force without --start: use earliest date for full history
        # - Otherwise: None (let incremental logic in download_mimer_product decide)
        if args.start:
            start = args.start
        elif args.force:
            start = MIMER_EARLIEST_DATES.get(product)
        else:
            start = None

        print(f"\n--- {product.upper()} ---")
        try:
            result = download_mimer_product(
                product=product,
                start_date=start,
                end_date=args.end,
                verbose=True,
                force=args.force,
            )
            print(f"Done: {result['total_records']} records")
        except Exception as e:
            print(f"Error downloading {product}: {e}")

    print("\n" + "=" * 50)
    print("Download complete!")
    print("Data saved to: data/raw/mimer/")


if __name__ == "__main__":
    main()
