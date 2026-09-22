#!/usr/bin/env python3
"""Download data from the ENTSO-E Transparency Platform.

Two datasets:

* Actual generation per type (A75) for SE1-SE4 and DK1/DK2
  -> Resultat/marknadsdata/entsoe/generation/<zone>/<type>_YYYY.csv
* Day-ahead prices (A44) for DK1/DK2 (``--prices``)
  -> Resultat/marknadsdata/spotpriser/<zone>/YYYY.csv (same format as the
     Swedish elprisetjustnu files; data/quarterly/<zone>/ is regenerated)

Which zones/datasets run:

  (no args)                         SE1-SE4 generation (--types, default solar
                                    wind_onshore) + DK1/DK2 solar + DK1/DK2 prices
  --zones SE3 SE4 [--types ...]     only those zones' generation (as before)
  --zones ... --with-dk             ... plus DK1/DK2 solar + DK1/DK2 prices
  --zones DK1 DK2 --types solar     DK solar only
  --prices [--zones DK1 DK2]        day-ahead prices only (default DK1 DK2)
  --no-dk                           drop the implicit DK part of a no-arg run

All downloads are incremental unless --start/--force is given.

Requires ENTSOE_TOKEN (environment variable or .env).
Get your token at: https://webportal.tp.entsoe.eu/ (My Account Settings)
"""

from __future__ import annotations

import argparse
from datetime import date

from elpris.config import PROJECT_ROOT
from elpris.entsoe import (
    DANISH_ZONES,
    ENTSOE_TOKEN,
    ENTSOE_ZONES,
    PSR_TYPES,
    SWEDISH_ZONES,
    download_all_generation,
    download_all_prices,
    get_price_dir,
)
from elpris.failure_log import log_chunk_failures

# Generation types fetched for DK when DK is added implicitly (--with-dk or
# the no-arg run). Explicit --zones DK1 DK2 uses --types instead.
DK_DEFAULT_TYPES = ["solar"]


def plan_jobs(args) -> tuple[list[tuple[list[str], list[str]]], list[str]]:
    """Decide what to download from parsed CLI args.

    Returns ``(generation_jobs, price_zones)`` where each generation job is
    ``(zones, psr_types)``.
    """
    dk_zones = list(DANISH_ZONES.keys())
    generation_jobs: list[tuple[list[str], list[str]]] = []
    price_zones: list[str] = []

    if args.prices:
        return generation_jobs, list(args.zones or dk_zones)

    if args.zones:
        generation_jobs.append((list(args.zones), list(args.types)))
        include_dk = args.with_dk
    else:
        generation_jobs.append((list(SWEDISH_ZONES.keys()), list(args.types)))
        include_dk = not args.no_dk
    if include_dk:
        explicit_dk = set(args.zones or []) & set(dk_zones)
        implicit_dk = [z for z in dk_zones if z not in explicit_dk]
        if implicit_dk:
            generation_jobs.append((implicit_dk, list(DK_DEFAULT_TYPES)))
        price_zones = dk_zones
    return generation_jobs, price_zones


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download generation (A75) and day-ahead prices (A44) from ENTSO-E",
        epilog="Default (no args): SE1-SE4 generation + DK1/DK2 solar + DK1/DK2 prices.",
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        choices=list(ENTSOE_ZONES.keys()),
        default=None,
        help=(
            "Zones to download (default: SE1-SE4 generation plus DK1/DK2 solar "
            "and prices; with --prices: DK1 DK2)"
        ),
    )
    parser.add_argument(
        "--types",
        nargs="+",
        choices=list(PSR_TYPES.keys()),
        default=["solar", "wind_onshore"],
        help="Generation types to download (default: solar wind_onshore)",
    )
    parser.add_argument(
        "--prices",
        action="store_true",
        help=(
            "Download day-ahead prices instead of generation. DK zones are "
            "written to Resultat/marknadsdata/spotpriser/<zone>/; SE zones to "
            "Resultat/marknadsdata/entsoe/prices/<zone>/ (never overwrites "
            "the elprisetjustnu files)"
        ),
    )
    parser.add_argument(
        "--with-dk",
        action="store_true",
        help="Also download DK1/DK2 solar generation and DK1/DK2 day-ahead prices",
    )
    parser.add_argument(
        "--no-dk",
        action="store_true",
        help="Skip the DK1/DK2 part of a no-argument run",
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
        help="End date, inclusive (YYYY-MM-DD; default: yesterday)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="ENTSO-E API token (default: from .env or ENTSOE_TOKEN env var)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore existing data and download full history from earliest date",
    )

    return parser


def main(argv: list[str] | None = None):
    args = build_parser().parse_args(argv)

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

    generation_jobs, price_zones = plan_jobs(args)

    print("ENTSO-E Transparency Platform Downloader")
    print("=" * 50)
    for zones, types in generation_jobs:
        print(f"Generation: {', '.join(zones)} × {', '.join(types)}")
    if price_zones:
        print(f"Day-ahead prices: {', '.join(price_zones)}")
    if args.start:
        print(f"Start: {args.start}")
    if args.end:
        print(f"End: {args.end}")
    print("=" * 50)
    print()

    generation_results: list[dict] = []
    for zones, types in generation_jobs:
        generation_results += download_all_generation(
            zones=zones,
            psr_types=types,
            start_date=args.start,
            end_date=args.end,
            token=token,
            verbose=True,
            force=args.force,
        )

    price_results: list[dict] = []
    if price_zones:
        price_results = download_all_prices(
            zones=price_zones,
            start_date=args.start,
            end_date=args.end,
            token=token,
            verbose=True,
            force=args.force,
        )

    print("\n" + "=" * 50)
    print("Download complete!")
    print()
    failed = 0
    for r in generation_results:
        chunks = r.get("failed_chunks", [])
        if chunks:
            failed += log_chunk_failures(
                "entsoe", f"{r['zone']}_{r['psr_type']}", chunks
            )
    for r in price_results:
        chunks = r.get("failed_chunks", [])
        if chunks:
            failed += log_chunk_failures("entsoe", f"{r['zone']}_prices", chunks)

    if generation_results:
        total = sum(r["total_records"] for r in generation_results)
        print(f"Generation records: {total}")
        print("  saved to: Resultat/marknadsdata/entsoe/generation/")
    if price_results:
        total = sum(r["total_records"] for r in price_results)
        print(f"Price rows: {total}")
        for r in price_results:
            where = get_price_dir(r["zone"]).resolve()
            try:
                where = where.relative_to(PROJECT_ROOT.resolve())
            except ValueError:
                pass
            print(f"  {r['zone']} saved to: {where}/")
    if failed:
        print(
            f"WARNING: {failed} chunk(s) failed — data has gaps. "
            f"See Resultat/logs/failed_chunks.csv for details."
        )
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
