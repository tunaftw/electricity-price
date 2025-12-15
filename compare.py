#!/usr/bin/env python3
"""Compare capture prices across solar profiles and zones."""

from __future__ import annotations

import argparse

from elpris.capture_report import (
    export_to_csv,
    generate_capture_comparison,
    get_available_years,
    pivot_comparison,
    format_terminal_table,
)
from elpris.config import ZONES
from elpris.solar_profile import list_available_profiles


def main():
    available_profiles = [p for p in list_available_profiles() if p != "sweden"]
    available_years = get_available_years()

    parser = argparse.ArgumentParser(
        description="Compare capture prices across solar profiles and zones"
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=available_profiles,
        help=f"Profiles to compare (available: {', '.join(available_profiles)})",
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        choices=ZONES,
        default=list(ZONES),
        help="Zones to include (default: all SE1-SE4)",
    )
    parser.add_argument(
        "--period",
        choices=["year", "month"],
        default="year",
        help="Aggregation period (default: year)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help=f"Filter to specific year (available: {', '.join(map(str, available_years))})",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Export to CSV file (optional filename)",
    )
    parser.add_argument(
        "--no-terminal",
        action="store_true",
        help="Skip terminal output (only export CSV)",
    )
    parser.add_argument(
        "--excel",
        type=str,
        default=None,
        nargs="?",
        const="",
        help="Export to Excel file (optional filename)",
    )
    parser.add_argument(
        "--exchange-rate",
        type=float,
        default=11.50,
        help="SEK/EUR exchange rate (default: 11.50)",
    )

    args = parser.parse_args()

    print(f"Comparing profiles: {', '.join(args.profiles)}")
    print(f"Zones: {', '.join(args.zones)}")
    print(f"Period: {args.period}")
    if args.year:
        print(f"Year: {args.year}")
    print()

    # Generate comparison data
    results = generate_capture_comparison(
        profiles=args.profiles,
        zones=args.zones,
        period=args.period,
        year=args.year,
    )

    if not results:
        print("No data available for the specified parameters.")
        return

    # Terminal output
    if not args.no_terminal:
        pivoted = pivot_comparison(results)
        table = format_terminal_table(pivoted, args.profiles, args.period)
        print(table)
        print()

    # CSV export
    if args.output is not None:
        # If --output given without value, use default filename
        filename = args.output if args.output else None
        output_path = export_to_csv(results, filename)
        print(f"Exported CSV: {output_path}")

    # Excel export
    if args.excel is not None:
        from elpris.excel_export import export_capture_excel

        filename = args.excel if args.excel else None
        output_path = export_capture_excel(
            filename=filename,
            exchange_rate=args.exchange_rate,
            profiles=args.profiles,
        )
        print(f"Exported Excel: {output_path}")


if __name__ == "__main__":
    main()
