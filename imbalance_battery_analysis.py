#!/usr/bin/env python3
"""Analysera hur många MWp ett batteri kan balansera vid solprognosfel.

Tidsstegsbaserad simulering med verkliga eSett-obalanspriser och PVsyst-solprofil.

Usage:
    python3 imbalance_battery_analysis.py [options]

Examples:
    # Quick smoke test
    python3 imbalance_battery_analysis.py --zones SE3 --mape 0.05 --park-sizes 1,5,10 --simulations 10

    # Full analysis (default)
    python3 imbalance_battery_analysis.py

    # With Excel export
    python3 imbalance_battery_analysis.py --excel
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from elpris.imbalance_simulation import (
    export_excel,
    format_table,
    run_analysis,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analysera hur många MWp ett 1 MW / 1 MWh batteri kan balansera"
    )
    parser.add_argument(
        "--zones", nargs="+", default=["SE3", "SE4"],
        help="Elområden att analysera (default: SE3 SE4)"
    )
    parser.add_argument(
        "--mape", nargs="+", type=float, default=[0.05, 0.075, 0.10],
        help="MAPE-scenarier (default: 0.05 0.075 0.10)"
    )
    parser.add_argument(
        "--park-sizes", type=str, default="1,2,3,5,7,10,15,20,25,30",
        help="Parkstorlekar i MWp, kommaseparerade (default: 1,2,3,5,7,10,15,20,25,30)"
    )
    parser.add_argument(
        "--battery-mw", type=float, default=1.0,
        help="Batterieffekt i MW (default: 1.0)"
    )
    parser.add_argument(
        "--battery-mwh", type=float, default=1.0,
        help="Batterienergi i MWh (default: 1.0)"
    )
    parser.add_argument(
        "--simulations", type=int, default=200,
        help="Antal Monte Carlo-simuleringar (default: 200)"
    )
    parser.add_argument(
        "--profile", type=str, default="south_lundby",
        help="PVsyst-profil (default: south_lundby)"
    )
    parser.add_argument(
        "--coverage-target", type=float, default=99.0,
        help="Coverage target i procent (default: 99)"
    )
    parser.add_argument(
        "--years", nargs="+", type=int, default=[2024, 2025],
        help="År att simulera (default: 2024 2025)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Bas-seed för reproducerbarhet (default: 42)"
    )
    parser.add_argument(
        "--excel", action="store_true",
        help="Generera Excel-rapport"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Sökväg för Excel-fil (default: Resultat/rapporter/imbalance_battery_YYYYMMDD.xlsx)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    park_sizes = [float(x) for x in args.park_sizes.split(",")]

    print("=" * 75)
    print("SOLPARK-BATTERIBALANSERING: OBALANSANALYS")
    print("=" * 75)
    print(f"Zoner:        {', '.join(args.zones)}")
    print(f"MAPE:         {', '.join(f'{m*100:.1f}%' for m in args.mape)}")
    print(f"Parkstorlekar: {', '.join(f'{p:.0f}' for p in park_sizes)} MWp")
    print(f"Batteri:      {args.battery_mw} MW / {args.battery_mwh} MWh")
    print(f"Profil:       {args.profile}")
    print(f"Simuleringar: {args.simulations}")
    print(f"År:           {', '.join(str(y) for y in args.years)}")
    print(f"Coverage:     P{args.coverage_target:.0f}")
    print(f"Seed:         {args.seed}")

    t0 = time.time()

    results = run_analysis(
        zones=args.zones,
        park_sizes=park_sizes,
        mapes=args.mape,
        battery_mw=args.battery_mw,
        battery_mwh=args.battery_mwh,
        n_sims=args.simulations,
        years=args.years,
        profile=args.profile,
        base_seed=args.seed,
    )

    elapsed = time.time() - t0
    print(f"\nSimulering klar på {elapsed:.1f}s")

    # Print formatted results
    table = format_table(
        results,
        battery_mw=args.battery_mw,
        battery_mwh=args.battery_mwh,
        profile=args.profile,
        n_sims=args.simulations,
        target_coverage=args.coverage_target,
    )
    print(table)

    # Excel export
    if args.excel:
        if args.output:
            output_path = Path(args.output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d")
            output_path = Path("Resultat/rapporter") / f"imbalance_battery_{timestamp}.xlsx"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        export_excel(
            results,
            battery_mw=args.battery_mw,
            battery_mwh=args.battery_mwh,
            profile=args.profile,
            n_sims=args.simulations,
            output_path=output_path,
        )


if __name__ == "__main__":
    main()
