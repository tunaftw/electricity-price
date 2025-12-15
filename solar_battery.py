#!/usr/bin/env python3
"""CLI for behind-the-meter solar+battery analysis.

Analyze revenue optimization for solar parks with battery storage where
the battery can only charge from solar production (no grid import).
"""

from __future__ import annotations

import argparse
from datetime import date

from elpris.config import ZONES
from elpris.solar_battery import (
    calculate_btm_day,
    calculate_btm_annual,
    compare_battery_sizes,
    format_btm_summary,
    format_battery_comparison,
)
from elpris.solar_profile import list_available_profiles


def print_day_schedule(result):
    """Print detailed schedule for a single day."""
    print(f"\nBTM Schedule for {result.date}")
    print("=" * 90)
    print(f"Solar production: {result.total_solar_mwh:.2f} MWh")
    print(f"Revenue direct: {result.revenue_direct_eur:.2f} EUR")
    print(f"Revenue with battery: {result.revenue_with_battery_eur:.2f} EUR")
    print(f"Battery gain: +{result.battery_gain_eur:.2f} EUR")
    print(f"Cycles: {result.cycles:.2f}")
    print("-" * 90)
    print(f"{'Time':<8} {'Solar':>8} {'Price':>10} {'Action':<14} {'Charged':>8} {'Discharged':>10} {'SoC':>12}")
    print("-" * 90)

    for q in result.schedule:
        if q.action != "sell" or q.solar_mwh > 0:
            time_str = q.timestamp.strftime("%H:%M") if q.timestamp else "?"
            soc_str = f"{q.soc_before:.2f}->{q.soc_after:.2f}"
            print(
                f"{time_str:<8} "
                f"{q.solar_mwh:>6.3f}  "
                f"{q.price_eur:>8.2f}  "
                f"{q.action:<14} "
                f"{q.charged_mwh:>6.3f}  "
                f"{q.discharged_mwh:>8.3f}  "
                f"{soc_str:>12}"
            )


def print_monthly_breakdown(annual_result: dict):
    """Print monthly breakdown of BTM results."""
    print(f"\nMonthly Breakdown - {annual_result['zone']} {annual_result['year']}")
    print("=" * 80)
    print(f"{'Month':<10} {'Solar MWh':>12} {'Direct EUR':>14} {'Battery EUR':>14} {'Gain EUR':>12}")
    print("-" * 80)

    for month, data in sorted(annual_result["monthly"].items()):
        gain = data["revenue_battery"] - data["revenue_direct"]
        print(
            f"{month:<10} "
            f"{data['solar_mwh']:>10,.0f}  "
            f"{data['revenue_direct']:>12,.0f}  "
            f"{data['revenue_battery']:>12,.0f}  "
            f"{gain:>+10,.0f}"
        )

    print("-" * 80)
    total_gain = annual_result["battery_gain_eur"]
    print(
        f"{'TOTAL':<10} "
        f"{annual_result['total_solar_mwh']:>10,.0f}  "
        f"{annual_result['revenue_direct_eur']:>12,.0f}  "
        f"{annual_result['revenue_with_battery_eur']:>12,.0f}  "
        f"{total_gain:>+10,.0f}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Behind-the-meter solar+battery analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze 20 MWp park with 4 MWh battery for 2024
  python3 solar_battery.py SE4 --mwp 20 --battery-mwh 4 --year 2024

  # Compare different battery sizes
  python3 solar_battery.py SE4 --mwp 20 --compare-sizes 2,4,6,8 --year 2024

  # Analyze specific day with detailed schedule
  python3 solar_battery.py SE4 --mwp 20 --battery-mwh 4 --day 2024-06-15

  # Use different solar profile
  python3 solar_battery.py SE4 --mwp 20 --battery-mwh 4 --year 2024 --profile ew_boda
        """,
    )

    parser.add_argument(
        "zone",
        choices=ZONES,
        help="Electricity zone (SE1, SE2, SE3, SE4)",
    )
    parser.add_argument(
        "--mwp",
        type=float,
        required=True,
        help="Installed solar capacity in MWp",
    )
    parser.add_argument(
        "--battery-mwh",
        type=float,
        default=0,
        help="Battery capacity in MWh (default: 0, no battery)",
    )
    parser.add_argument(
        "--battery-mw",
        type=float,
        default=None,
        help="Battery power in MW (default: same as MWh, i.e. 1C rate)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Year to analyze (default: all available data)",
    )
    parser.add_argument(
        "--day",
        type=date.fromisoformat,
        default=None,
        help="Analyze specific day (YYYY-MM-DD) with detailed schedule",
    )
    parser.add_argument(
        "--compare-sizes",
        type=str,
        default=None,
        help="Compare battery sizes (comma-separated MWh values, e.g., '2,4,6,8')",
    )
    parser.add_argument(
        "--profile",
        default="south_lundby",
        help="Solar profile (default: south_lundby). Use --list-profiles to see options",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available solar profiles and exit",
    )
    parser.add_argument(
        "--monthly",
        action="store_true",
        help="Show monthly breakdown",
    )
    parser.add_argument(
        "--efficiency",
        type=float,
        default=0.88,
        help="Battery round-trip efficiency (default: 0.88)",
    )

    args = parser.parse_args()

    # List profiles if requested
    if args.list_profiles:
        print("Available solar profiles:")
        for p in list_available_profiles():
            print(f"  {p}")
        return

    # Default battery power to capacity (1C rate)
    battery_mw = args.battery_mw if args.battery_mw is not None else args.battery_mwh

    print(f"Behind-the-Meter Analysis - {args.zone}")
    print(f"Solar park: {args.mwp} MWp ({args.profile} profile)")
    if args.battery_mwh > 0:
        print(f"Battery: {args.battery_mwh} MWh / {battery_mw} MW")
    else:
        print("Battery: None (direct sales only)")

    # Single day analysis
    if args.day:
        result = calculate_btm_day(
            zone=args.zone,
            day=args.day,
            installed_mwp=args.mwp,
            battery_mwh=args.battery_mwh,
            battery_mw=battery_mw,
            profile=args.profile,
            efficiency=args.efficiency,
        )
        print_day_schedule(result)
        return

    # Compare different battery sizes
    if args.compare_sizes:
        sizes = [float(s.strip()) for s in args.compare_sizes.split(",")]

        results = compare_battery_sizes(
            zone=args.zone,
            year=args.year or date.today().year,
            installed_mwp=args.mwp,
            battery_sizes_mwh=sizes,
            profile=args.profile,
            efficiency=args.efficiency,
        )

        print(format_battery_comparison(results, args.mwp))
        return

    # Annual analysis
    annual = calculate_btm_annual(
        zone=args.zone,
        year=args.year,
        installed_mwp=args.mwp,
        battery_mwh=args.battery_mwh,
        battery_mw=battery_mw,
        profile=args.profile,
        efficiency=args.efficiency,
    )

    print(format_btm_summary(annual))

    if args.monthly:
        print_monthly_breakdown(annual)

    print()


if __name__ == "__main__":
    main()
