#!/usr/bin/env python3
"""Calculate capture prices for solar and wind in Swedish electricity zones."""

from __future__ import annotations

import argparse
from datetime import date

from elpris.capture import calculate_capture_price, calculate_capture_by_period
from elpris.config import ZONES
from elpris.solar_profile import list_available_profiles


def print_summary(result: dict):
    """Print capture price summary."""
    print(f"\nCapture Price Summary for {result['zone']}")
    print("=" * 50)
    print(f"Period: {result['start_date']} to {result['end_date']}")
    print(f"Records analyzed: {result['record_count']:,}")
    print("-" * 50)

    if result["capture_price"] is not None:
        print(f"Average spot price:  {result['average_price']:.4f} SEK/kWh")
        print(f"Solar capture price: {result['capture_price']:.4f} SEK/kWh")
        print(f"Capture ratio:       {result['capture_ratio']:.1%}")
    else:
        print("No data available for this period.")


def print_period_table(results: list[dict], period_type: str):
    """Print capture prices by period as a table."""
    if not results:
        print("No data available.")
        return

    print(f"\n{'Period':<12} {'Capture':>12} {'Average':>12} {'Ratio':>10}")
    print("-" * 50)

    for r in results:
        ratio_str = f"{r['capture_ratio']:.1%}" if r["capture_ratio"] else "-"
        print(
            f"{r['period']:<12} "
            f"{r['capture_price_sek']:>12.4f} "
            f"{r['average_price_sek']:>12.4f} "
            f"{ratio_str:>10}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Calculate capture prices for solar/wind in Swedish electricity zones"
    )
    parser.add_argument(
        "zone",
        choices=ZONES,
        help="Electricity zone (SE1, SE2, SE3, SE4)",
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
        "--period",
        choices=["day", "week", "month", "year", "total"],
        default="month",
        help="Aggregation period (default: month)",
    )
    parser.add_argument(
        "--profile",
        default="sweden",
        help="Production profile (e.g. sweden, entsoe_solar_SE3, entsoe_wind_onshore_SE3)",
    )
    parser.add_argument(
        "--export-excel",
        action="store_true",
        help="Export results to Excel (capture_prices_YYYYMMDD.xlsx)",
    )

    args = parser.parse_args()

    print(f"Calculating capture prices for {args.zone}")
    print(f"Using profile: {args.profile}")

    if args.period == "total":
        result = calculate_capture_price(
            zone=args.zone,
            start_date=args.start,
            end_date=args.end,
            solar_profile=args.profile,
        )
        print_summary(result)
    else:
        results = calculate_capture_by_period(
            zone=args.zone,
            start_date=args.start,
            end_date=args.end,
            period=args.period,
            solar_profile=args.profile,
        )
        print_period_table(results, args.period)

    # Export to Excel if requested
    if args.export_excel:
        try:
            from elpris.excel_export import export_capture_excel
            print("\nExporting to Excel...")
            output_path = export_capture_excel()
            print(f"Saved to: {output_path}")
        except ImportError:
            print("\nError: openpyxl not installed. Run: pip install openpyxl")
        except Exception as e:
            print(f"\nError exporting to Excel: {e}")

    print()


if __name__ == "__main__":
    main()
