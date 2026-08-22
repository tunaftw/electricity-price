#!/usr/bin/env python3
"""Master update script - download all data and generate reports.

This script runs the entire update pipeline:
 1. Update spot prices (elprisetjustnu.se)
 2. Sync Bazefield solar park data (if API key available)
 3. Update park air temperature (Open-Meteo ERA5)
 4. Update ENTSO-E generation data (if token available)
 5. Update Mimer regulation prices (SVK)
 6. Update Nasdaq Nordic futures
 7. Update eSett imbalance prices
 8. Process raw data to quarterly format
 9. Calculate capture prices
10. Generate Excel reports
11. Generate Unified Dashboard (Track C — Nordic Editorial)
12. Generate park performance reports (only with --reports / --auto-reports)
13. Show status
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent

# Check for ENTSO-E token
ENTSOE_TOKEN = os.getenv("ENTSOE_TOKEN")

# Check for Bazefield API key
BAZEFIELD_API_KEY = os.getenv("BAZEFIELD_API_KEY")

# Try to load from .env if not in environment
if not ENTSOE_TOKEN or not BAZEFIELD_API_KEY:
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if not ENTSOE_TOKEN and line.startswith("ENTSOE_TOKEN="):
                    ENTSOE_TOKEN = line.strip().split("=", 1)[1]
                if not BAZEFIELD_API_KEY and line.startswith("BAZEFIELD_API_KEY="):
                    BAZEFIELD_API_KEY = line.strip().split("=", 1)[1]


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


def previous_month(today: date | None = None) -> str:
    """Compute the previous full month relative to today.

    Args:
        today: Reference date (default: today's date)

    Returns:
        Month string in format "YYYY-MM"
    """
    if today is None:
        today = date.today()

    # First day of current month
    first_of_current = today.replace(day=1)
    # Subtract one day to get last day of previous month
    last_of_previous = first_of_current - timedelta(days=1)
    # Return "YYYY-MM" of the previous month
    return last_of_previous.strftime("%Y-%m")


def reports_exist_for_month(month_str: str) -> bool:
    """Check whether all park performance reports exist for a given month.

    Args:
        month_str: Month in format "YYYY-MM"

    Returns:
        True if all park reports exist, False otherwise
    """
    from elpris.config import PARK_ZONES, RESULTAT_DIR

    reports_dir = RESULTAT_DIR / "rapporter"

    for park_key, zone in PARK_ZONES.items():
        filename = f"performance_{park_key}_{zone}_{month_str}.html"
        filepath = reports_dir / filename
        if not filepath.exists():
            return False

    return True


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
        "--skip-nasdaq",
        action="store_true",
        help="Skip Nasdaq futures download",
    )
    parser.add_argument(
        "--skip-bazefield",
        action="store_true",
        help="Skip Bazefield solar park sync",
    )
    parser.add_argument(
        "--skip-temperature",
        action="store_true",
        help="Skip park air temperature download (Open-Meteo ERA5)",
    )
    parser.add_argument(
        "--skip-excel",
        action="store_true",
        help="Skip Excel report generation",
    )
    parser.add_argument(
        "--reports",
        action="store_true",
        help="Also regenerate park performance reports",
    )
    parser.add_argument(
        "--auto-reports",
        action="store_true",
        help="Generate park performance reports for the previous month if missing (for daily automation)",
    )
    parser.add_argument(
        "--month",
        help="Month for park reports (YYYY-MM); only used with --reports",
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
    print(f"Bazefield key: {'Found' if BAZEFIELD_API_KEY else 'Not found'}")
    print("=" * 60)

    total_steps = 13
    current_step = 0
    success_count = 0
    failures: list[str] = []

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
        failures.append(f"step {current_step}")

    # Step 2: Sync Bazefield solar park data
    current_step += 1
    if args.skip_bazefield:
        step(current_step, total_steps, "Bazefield solar parks (SKIPPED)")
    elif not BAZEFIELD_API_KEY:
        step(current_step, total_steps, "Bazefield solar parks (SKIPPED - no API key)")
        print("  Set BAZEFIELD_API_KEY in .env to enable")
    else:
        step(current_step, total_steps, "Syncing Bazefield solar park data")
        if run_script("bazefield_download.py", quiet=args.quiet):
            success_count += 1
            print("  Done!")
        else:
            print("  Failed or no updates needed")
            failures.append(f"step {current_step}")

    # Step 3: Update park air temperature (Open-Meteo ERA5, no API key)
    current_step += 1
    if args.skip_temperature:
        step(current_step, total_steps, "Park air temperature (SKIPPED)")
    else:
        step(current_step, total_steps, "Updating park air temperature (Open-Meteo ERA5)")
        if run_script("temperature_download.py", quiet=args.quiet):
            success_count += 1
            print("  Done!")
        else:
            print("  Failed or no updates needed")
            failures.append(f"step {current_step}")

    # Step 4: Update ENTSO-E (if token available and not skipped)
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
            failures.append(f"step {current_step}")

    # Step 5: Update Mimer regulation prices
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
            failures.append(f"step {current_step}")

    # Step 6: Update Nasdaq futures
    current_step += 1
    if args.skip_nasdaq:
        step(current_step, total_steps, "Nasdaq futures (SKIPPED)")
    else:
        step(current_step, total_steps, "Updating Nasdaq Nordic futures")
        if run_script("nasdaq_download.py", quiet=args.quiet):
            success_count += 1
            print("  Done!")
        else:
            print("  Failed or no updates needed")
            failures.append(f"step {current_step}")

    # Step 7: Update eSett imbalance prices
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
            failures.append(f"step {current_step}")

    # Step 8: Process to quarterly format
    current_step += 1
    step(current_step, total_steps, "Processing data to quarterly format")
    process_args = ["--zones"] + args.zones
    if run_script("process.py", process_args, quiet=args.quiet):
        success_count += 1
        print("  Done!")
    else:
        print("  Failed")
        failures.append(f"step {current_step}")

    # Step 9: Calculate capture prices
    current_step += 1
    step(current_step, total_steps, "Calculating capture prices")
    # Run capture for each zone and print summary
    capture_ok = True
    for zone in args.zones:
        capture_args = [zone, "--period", "year"]
        if not run_script("capture.py", capture_args, quiet=True):
            capture_ok = False
            print(f"  Failed for {zone}")
    if capture_ok:
        success_count += 1
        print("  Done!")
    else:
        failures.append(f"step {current_step}")

    # Step 10: Generate Excel reports
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
            failures.append(f"step {current_step}")
        except Exception as e:
            print(f"  Error generating Excel: {e}")
            failures.append(f"step {current_step}")

    # Step 11: Generate Unified Dashboard (Track C — Nordic Editorial)
    current_step += 1
    step(current_step, total_steps, "Generating Unified Dashboard (Track C)")
    if run_script("generate_unified_dashboard.py", quiet=args.quiet):
        success_count += 1
        print("  Done!")
    else:
        print("  Failed")
        failures.append(f"step {current_step}")

    # Step 12: Park performance reports (conditional on --reports or --auto-reports)
    current_step += 1
    if args.reports:
        step(current_step, total_steps, "Generating park performance reports")
        report_args = ["--all"]
        if args.month:
            report_args += ["--month", args.month]
        if run_script("generate_performance_report.py", report_args, quiet=args.quiet):
            success_count += 1
            print("  Done!")
        else:
            print("  Failed")
            failures.append(f"step {current_step}")
    elif args.auto_reports:
        step(current_step, total_steps, "Generating park performance reports (auto)")
        month_str = previous_month()
        if reports_exist_for_month(month_str):
            print(f"  Reports for {month_str} already exist — skipping")
            success_count += 1
        else:
            report_args = ["--all", "--month", month_str]
            if run_script("generate_performance_report.py", report_args, quiet=args.quiet):
                success_count += 1
                print("  Done!")
            else:
                print("  Failed")
                failures.append(f"step {current_step}")
    else:
        step(current_step, total_steps, "Park reports (SKIPPED — use --reports or --auto-reports)")

    # Step 13: Show status
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

    print()
    print("Reports saved to: Resultat/rapporter/")

    # Surface failed download chunks logged during this run.
    # See elpris.failure_log — each downloader appends to
    # Resultat/logs/failed_chunks.csv on per-chunk failure.
    try:
        from elpris.failure_log import recent_failures
        chunk_failures = recent_failures(hours=2)
        if chunk_failures:
            print()
            print(
                f"WARNING: {len(chunk_failures)} download chunk(s) failed "
                f"in the last 2h:"
            )
            # Group by source for readable summary
            by_source: dict[str, int] = {}
            for entry in chunk_failures:
                key = f"{entry.get('source', '?')}/{entry.get('scope', '?')}"
                by_source[key] = by_source.get(key, 0) + 1
            for key, count in sorted(by_source.items()):
                print(f"  {key}: {count} chunk(s)")
            print("  Details: Resultat/logs/failed_chunks.csv")
    except Exception as e:
        print(f"  (Could not read failure log: {e})")

    # Surface real failures (not intentional skips) so cron / CI can alert
    if failures:
        print()
        print(f"WARNING: {len(failures)} step(s) reported failure: "
              f"{', '.join(failures)}. Re-run those scripts to investigate gaps.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
