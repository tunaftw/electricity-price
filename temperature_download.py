#!/usr/bin/env python3
"""Download air temperature history per solar park (Open-Meteo ERA5).

Hourly 2 m air temperature for each park's coordinates, used for
temperature-corrected PR in the monthly performance reports.

Free reanalysis data — no API key required. History from 2015-01-01 so the
monthly climatology baseline has ~10 complete years to average over.
"""

from __future__ import annotations

import argparse
from datetime import date

from elpris.failure_log import log_chunk_failures
from elpris.temperature import (
    ERA5_EARLIEST_DATE,
    PARK_COORDS,
    TEMPERATURE_DATA_DIR,
    download_all_temperatures,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download air temperature per solar park from Open-Meteo ERA5"
    )
    parser.add_argument(
        "--parks",
        nargs="+",
        choices=list(PARK_COORDS.keys()),
        default=None,
        help="Parks to download (default: all)",
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=None,
        help=f"Start date (YYYY-MM-DD, earliest fetched by default: {ERA5_EARLIEST_DATE})",
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
        help="End date (YYYY-MM-DD, inclusive; default: yesterday)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore existing data and re-download full history",
    )

    args = parser.parse_args()

    parks = args.parks or list(PARK_COORDS.keys())

    print("Open-Meteo ERA5 Temperature Downloader")
    print("=" * 50)
    print(f"Parks: {', '.join(parks)}")
    print(f"Start: {args.start or 'incremental (från 2015-01-01 vid tom fil)'}")
    if args.end:
        print(f"End: {args.end}")
    print("=" * 50)

    results = download_all_temperatures(
        park_keys=parks,
        start_date=args.start,
        end_date=args.end,
        verbose=True,
        force=args.force,
    )

    print("\n" + "=" * 50)
    print("Download complete!")
    print()

    total = sum(r["total_records"] for r in results)
    failed = 0
    for r in results:
        chunks = r.get("failed_chunks", [])
        if chunks:
            failed += log_chunk_failures("temperatur", r["park"], chunks)

    print(f"Total new records: {total}")
    print(f"Data saved to: {TEMPERATURE_DATA_DIR}")
    if failed:
        print(
            f"WARNING: {failed} chunk(s) failed — data has gaps. "
            f"See Resultat/logs/failed_chunks.csv for details."
        )
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
