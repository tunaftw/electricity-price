#!/usr/bin/env python3
"""Master update script - download all data and generate reports.

This script runs the entire update pipeline:
1. Update spot prices (elprisetjustnu.se)
2. Update ENTSO-E generation data (if token available)
3. Update Mimer regulation prices (SVK)
4. Update eSett imbalance prices
5. Process raw data to quarterly format
6. Calculate capture prices
7. Generate Excel reports
8. Show status
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent

# Check for ENTSO-E token
ENTSOE_TOKEN = os.getenv("ENTSOE_TOKEN")

# Try to load from .env if not in environment
if not ENTSOE_TOKEN:
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("ENTSOE_TOKEN="):
                    ENTSOE_TOKEN = line.strip().split("=", 1)[1]
                    break


def run_script(name: str, args: list[str] = None, quiet: bool = False) -> bool:
    """Run a Python script and return success status."""
    script_path = PROJECT_ROOT / name
    if not script_path.exists():
        print(f"  Warning: {name} not found, skipping")
        return False

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    try:
        if quiet:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        else:
            result = subprocess.run(cmd)
            return result.returncode == 0
    except Exception as e:
        print(f"  Error running {name}: {e}")
        return False


def step(number: int, total: int, description: str):
    """Print step header."""
    print()
    print(f"[{number}/{total}] {description}")
    print("-" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Master update - download all data and generate reports"
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        choices=["SE1", "SE2", "SE3", "SE4"],
        default=["SE1", "SE2", "SE3", "SE4"],
        help="Zones to update (default: all)",
    )
    parser.add_argument(
        "--skip-entsoe",
        action="store_true",
        help="Skip ENTSO-E download (even if token available)",
    )
    parser.add_argument(
        "--skip-mimer",
        action="store_true",
        help="Skip Mimer regulation prices",
    )
    parser.add_argument(
        "--skip-esett",
        action="store_true",
        help="Skip eSett imbalance prices",
    )
    parser.add_argument(
        "--skip-excel",
        action="store_true",
        help="Skip Excel report generation",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed progress output",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ELECTRICITY PRICE - MASTER UPDATE")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Zones: {', '.join(args.zones)}")
    print(f"ENTSO-E token: {'Found' if ENTSOE_TOKEN else 'Not found'}")
    print("=" * 60)

    total_steps = 8
    current_step = 0
    success_count = 0

    # Step 1: Update spot prices
    current_step += 1
    step(current_step, total_steps, "Updating spot prices (elprisetjustnu.se)")
    zone_args = ["--zones"] + args.zones
    if args.quiet:
        zone_args.append("--quiet")
    if run_script("update.py", zone_args, quiet=args.quiet):
        success_count += 1
        print("  Done!")
    else:
        print("  Failed or no updates needed")

    # Step 2: Update ENTSO-E (if token available and not skipped)
    current_step += 1
    if args.skip_entsoe:
        step(current_step, total_steps, "ENTSO-E data (SKIPPED - user request)")
    elif not ENTSOE_TOKEN:
        step(current_step, total_steps, "ENTSO-E data (SKIPPED - no token)")
        print("  Set ENTSOE_TOKEN environment variable to enable")
    else:
        step(current_step, total_steps, "Updating ENTSO-E generation data")
        entsoe_args = ["--zones"] + args.zones + ["--types", "solar", "wind_onshore"]
        if run_script("entsoe_download.py", entsoe_args, quiet=args.quiet):
            success_count += 1
            print("  Done!")
        else:
            print("  Failed or no updates needed")

    # Step 3: Update Mimer regulation prices
    current_step += 1
    if args.skip_mimer:
        step(current_step, total_steps, "Mimer regulation prices (SKIPPED)")
    else:
        step(current_step, total_steps, "Updating Mimer regulation prices (SVK)")
        if run_script("mimer_download.py", quiet=args.quiet):
            success_count += 1
            print("  Done!")
        else:
            print("  Failed or no updates needed")

    # Step 4: Update eSett imbalance prices
    current_step += 1
    if args.skip_esett:
        step(current_step, total_steps, "eSett imbalance prices (SKIPPED)")
    else:
        step(current_step, total_steps, "Updating eSett imbalance prices")
        esett_args = ["--zones"] + args.zones
        if run_script("esett_download.py", esett_args, quiet=args.quiet):
            success_count += 1
            print("  Done!")
        else:
            print("  Failed or no updates needed")

    # Step 5: Process to quarterly format
    current_step += 1
    step(current_step, total_steps, "Processing data to quarterly format")
    process_args = ["--zones"] + args.zones
    if run_script("process.py", process_args, quiet=args.quiet):
        success_count += 1
        print("  Done!")
    else:
        print("  Failed")

    # Step 6: Calculate capture prices
    current_step += 1
    step(current_step, total_steps, "Calculating capture prices")
    # Run capture for each zone and print summary
    for zone in args.zones:
        capture_args = [zone, "--period", "year"]
        run_script("capture.py", capture_args, quiet=True)
    success_count += 1
    print("  Done!")

    # Step 7: Generate Excel reports
    current_step += 1
    if args.skip_excel:
        step(current_step, total_steps, "Excel reports (SKIPPED)")
    else:
        step(current_step, total_steps, "Generating Excel reports")
        try:
            # Generate capture prices Excel
            from elpris.excel_export import export_capture_excel
            capture_path = export_capture_excel()
            print(f"  Created: {capture_path.name}")

            # Generate battery arbitrage Excel
            from elpris.battery_excel import export_battery_excel
            battery_path = export_battery_excel()
            print(f"  Created: {battery_path.name}")

            success_count += 1
            print("  Done!")
        except ImportError as e:
            print(f"  Warning: Could not import Excel modules: {e}")
            print("  Install openpyxl: pip install openpyxl")
        except Exception as e:
            print(f"  Error generating Excel: {e}")

    # Step 8: Show status
    current_step += 1
    step(current_step, total_steps, "Data status")
    run_script("status.py", quiet=False)

    # Summary
    print()
    print("=" * 60)
    print("UPDATE COMPLETE")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Steps completed: {success_count}/{total_steps}")

    if not args.skip_excel:
        print()
        print("Excel reports saved to: Resultat/rapporter/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
