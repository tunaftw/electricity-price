#!/usr/bin/env python3
"""Download actual generation data from ENTSO-E Transparency Platform.

Requires ENTSOE_TOKEN environment variable to be set with your API security token.
Get your token at: https://webportal.tp.entsoe.eu/ (My Account Settings)
"""

from __future__ import annotations

import argparse
import os
from datetime import date

from elpris.entsoe import (
    ENTSOE_EARLIEST_DATES,
    ENTSOE_TOKEN,
    ENTSOE_ZONES,
    PSR_TYPES,
    download_all_generation,
    download_generation,
)


def main():
    parser = argparse.ArgumentParser(
        description="Download actual generation data from ENTSO-E Transparency Platform"
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        choices=list(ENTSOE_ZONES.keys()),
        default=None,
        help="Zones to download (default: all)",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        choices=list(PSR_TYPES.keys()),
        default=["solar", "wind_onshore"],
        help="Generation types to download (default: solar wind_onshore)",
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
        "--token",
        type=str,
        default=None,
        help="ENTSO-E API token (default: from .env or ENTSOE_TOKEN env var)",
    )

    args = parser.parse_args()

    # Get token (priority: CLI arg > env var > .env file)
    token = args.token or ENTSOE_TOKEN
    if not token:
        print("Error: ENTSO-E API token required.")
        print()
        print("Set the token via:")
        print("  1. Environment variable: export ENTSOE_TOKEN=your-token")
        print("  2. Command line: --token your-token")
        print()
        print("Get your token at: https://webportal.tp.entsoe.eu/")
        return 1

    zones = args.zones or list(ENTSOE_ZONES.keys())

    print("ENTSO-E Transparency Platform Downloader")
    print("=" * 50)
    print(f"Zones: {', '.join(zones)}")
    print(f"Types: {', '.join(args.types)}")
    if args.start:
        print(f"Start: {args.start}")
    if args.end:
        print(f"End: {args.end}")
    print("=" * 50)
    print()

    results = download_all_generation(
        zones=zones,
        psr_types=args.types,
        start_date=args.start,
        end_date=args.end,
        token=token,
        verbose=True,
    )

    print("\n" + "=" * 50)
    print("Download complete!")
    print()
    total = sum(r["total_records"] for r in results)
    print(f"Total records: {total}")
    print("Data saved to: data/raw/entsoe/generation/")

    return 0


if __name__ == "__main__":
    exit(main())
