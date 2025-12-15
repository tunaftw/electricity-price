#!/usr/bin/env python3
"""Batteridimensionering CLI för prognosfelkompensation i solsiter."""

import argparse
import sys

from elpris.battery_sizing import (
    BatterySpec,
    size_for_forecast_error,
    print_sizing_summary,
    calculate_coverage,
)
from elpris.forecast_error import ForecastErrorModel, calculate_production_stats
from elpris.imbalance_cost import print_imbalance_summary
from elpris.solar_profile import list_available_profiles


def main():
    parser = argparse.ArgumentParser(
        description="Dimensionera batteri för prognosfelkompensation i solsite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exempel:
  # Dimensionera för 1 MW site med 5% prognosfel
  python3 battery_sizing_cli.py --profile south_lundby --capacity 1.0 --mape 0.05

  # Med Monte Carlo-simulering
  python3 battery_sizing_cli.py --profile south_lundby --capacity 1.0 --mape 0.05 --simulate

  # Visa obalansanalys
  python3 battery_sizing_cli.py --profile south_lundby --capacity 1.0 --mape 0.05 --imbalance

  # Lista tillgängliga profiler
  python3 battery_sizing_cli.py --list-profiles
""",
    )

    parser.add_argument(
        "--profile",
        default="south_lundby",
        help="Solprofil att använda (default: south_lundby)",
    )
    parser.add_argument(
        "--capacity",
        type=float,
        default=1.0,
        help="Installerad kapacitet i MW (default: 1.0)",
    )
    parser.add_argument(
        "--mape",
        type=float,
        default=0.05,
        help="Mean Absolute Percentage Error (default: 0.05 = 5%%)",
    )
    parser.add_argument(
        "--percentile",
        type=float,
        default=0.95,
        choices=[0.95, 0.99],
        help="Design-percentil (default: 0.95)",
    )
    parser.add_argument(
        "--correlation-periods",
        type=int,
        default=4,
        help="Antal korrelerade 15-min perioder (default: 4)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Använd Monte Carlo-simulering",
    )
    parser.add_argument(
        "--n-simulations",
        type=int,
        default=1000,
        help="Antal simuleringar (default: 1000)",
    )
    parser.add_argument(
        "--imbalance",
        action="store_true",
        help="Visa obalansanalys med kostnad/besparing",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="Lista tillgängliga solprofiler",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Visa produktionsstatistik för profilen",
    )

    args = parser.parse_args()

    # Lista profiler
    if args.list_profiles:
        print("\nTillgängliga solprofiler:")
        print("-" * 40)
        for profile in list_available_profiles():
            try:
                stats = calculate_production_stats(profile)
                print(f"  {profile}:")
                print(f"    Peak: {stats.peak_mw:.3f} MW/MW")
                print(f"    Årlig: {stats.annual_mwh:.0f} MWh/MW")
            except Exception:
                print(f"  {profile}: (generisk profil)")
        return

    # Visa produktionsstatistik
    if args.stats:
        try:
            stats = calculate_production_stats(args.profile)
            print(f"\nProduktionsstatistik för {args.profile}:")
            print("-" * 40)
            print(f"Peak-produktion: {stats.peak_mw:.3f} MW per MW installerad")
            print(f"Årsproduktion:   {stats.annual_mwh:.0f} MWh per MW installerad")
            print(f"Produktionstimmar: {stats.production_hours} timmar/år")
            print(f"\nMånadsvis peak (MW/MW):")
            for month in range(1, 13):
                peak = stats.monthly_peaks.get(month, 0)
                bar = "#" * int(peak * 50)
                print(f"  {month:2d}: {peak:.3f} {bar}")
        except FileNotFoundError:
            print(f"Profil '{args.profile}' hittades inte.")
            sys.exit(1)
        return

    # Dimensionering
    print(f"\nDimensionerar batteri för {args.capacity} MW solsite...")
    print(f"Profil: {args.profile}")
    print(f"MAPE: {args.mape*100:.1f}%")

    try:
        result = size_for_forecast_error(
            profile_name=args.profile,
            site_capacity_mw=args.capacity,
            mape=args.mape,
            design_percentile=args.percentile,
            max_correlation_periods=args.correlation_periods,
            use_simulation=args.simulate,
            n_simulations=args.n_simulations,
        )
    except FileNotFoundError:
        print(f"\nFel: Profil '{args.profile}' hittades inte.")
        print("Använd --list-profiles för att se tillgängliga profiler.")
        sys.exit(1)

    print_sizing_summary(result)

    # Beräkna och visa coverage
    if args.simulate:
        error_model = ForecastErrorModel(
            mape=args.mape,
            correlation_periods=args.correlation_periods,
        )
        coverage = calculate_coverage(
            result.recommended_spec,
            args.profile,
            args.capacity,
            error_model,
            args.n_simulations,
        )
        print("\nCoverage (från simulering):")
        print(f"  Power:    {coverage['power_coverage_pct']:.1f}%")
        print(f"  Energi:   {coverage['energy_coverage_pct']:.1f}%")
        print(f"  Kombinerat: {coverage['combined_coverage_pct']:.1f}%")

    # Obalansanalys
    if args.imbalance:
        print_imbalance_summary(
            args.profile,
            args.capacity,
            args.mape,
            result.recommended_spec,
            coverage_pct=95.0,
        )


if __name__ == "__main__":
    main()
