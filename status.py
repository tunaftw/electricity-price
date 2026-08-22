#!/usr/bin/env python3
"""Show download status for electricity price data."""

import csv
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from elpris.config import RAW_DIR, QUARTERLY_DIR, ZONES
from elpris.storage import find_data_gaps


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def get_dir_stats(base_dir: Path, zone: str) -> dict:
    """Get statistics for a zone's data in a specific directory."""
    zone_dir = base_dir / zone
    if not zone_dir.exists():
        return {
            "zone": zone,
            "first_date": None,
            "last_date": None,
            "records": 0,
            "size_bytes": 0,
        }

    total_records = 0
    total_size = 0
    first_date = None
    last_date = None

    for csv_file in sorted(zone_dir.glob("*.csv")):
        total_size += csv_file.stat().st_size
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_records += 1
                ts = row["time_start"]
                if first_date is None:
                    first_date = ts[:10]
                last_date = ts[:10]

    return {
        "zone": zone,
        "first_date": first_date,
        "last_date": last_date,
        "records": total_records,
        "size_bytes": total_size,
    }


def print_table(title: str, base_dir: Path):
    """Print a status table for a data directory."""
    print(f"\n{title}")
    print(f"Path: {base_dir}")
    print("=" * 60)
    print(f"{'Zone':<6} {'First Date':<12} {'Last Date':<12} {'Records':>10} {'Size':>10}")
    print("-" * 60)

    total_records = 0
    total_size = 0
    has_data = False

    for zone in ZONES:
        s = get_dir_stats(base_dir, zone)
        first = s["first_date"] or "-"
        last = s["last_date"] or "-"
        records = s["records"]
        size = s["size_bytes"]

        if records > 0:
            has_data = True

        total_records += records
        total_size += size

        print(
            f"{zone:<6} {first:<12} {last:<12} {records:>10,} {format_size(size):>10}"
        )

    print("-" * 60)
    print(
        f"{'Total':<6} {'':<12} {'':<12} {total_records:>10,} {format_size(total_size):>10}"
    )
    print("=" * 60)

    return has_data


def print_gaps():
    """Scan raw spot prices for gaps and print findings."""
    print("\nDATA GAPS (raw spotpriser, threshold 2h)")
    print("=" * 60)
    any_gaps = False
    for zone in ZONES:
        gaps = find_data_gaps(zone, max_gap_hours=2)
        if not gaps:
            print(f"{zone:<6} no gaps")
            continue
        any_gaps = True
        print(f"{zone:<6} {len(gaps)} gap(s):")
        # Show up to 5 most recent (likely most actionable)
        for gap_start, gap_end in gaps[-5:]:
            print(f"       {gap_start.date()} → {gap_end.date()}")
        if len(gaps) > 5:
            print(f"       … and {len(gaps) - 5} earlier")
    print("=" * 60)
    if any_gaps:
        print("Backfill: python3 download.py --zones <zone> --start <date> --end <date>")


def print_futures_health():
    """Warn about futures contracts that are stale or near expiry.

    - "Approaching expiry" — delivery starts within 14 days but the latest
      daily fix is older than 7 days, suggesting a sync is due.
    - "Stale finals" — already-delivered contracts whose last fix is more
      than 7 days before delivery_start, indicating an old coverage gap
      whose historical settlement data is incomplete.
    """
    from elpris.config import NASDAQ_DATA_DIR
    from elpris.dashboard_v2_data import (
        EXPIRY_WARNING_DAYS,
        _load_full_history,
        _parse_contract_period,
        build_forward_health,
    )

    sys_file = NASDAQ_DATA_DIR / "sys_baseload.csv"
    if not sys_file.exists():
        return

    contracts = []
    for symbol, series in _load_full_history(sys_file).items():
        if not series:
            continue
        parsed = _parse_contract_period(symbol)
        if not parsed:
            continue
        label, _ctype, start_iso, end_iso = parsed
        contracts.append({
            "label": label,
            "start": start_iso,
            "end": end_iso,
            "last_fix": series[-1]["date"],
        })

    health = build_forward_health(contracts)
    approaching = health["approaching_expiry"]
    stale = health["stale_finals"]

    if not approaching and not stale:
        return

    RED = "\033[31m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"

    print("\nFUTURES HEALTH (forward coverage)")
    print("=" * 60)
    if approaching:
        for row in approaching:
            print(f"{RED}⚠ {row['contract']} expires in <{EXPIRY_WARNING_DAYS} days "
                  f"(delivery {row['delivery_start']}); last fix {row['last_fix']} "
                  f"({row['days_stale']} days stale).{RESET}")
        print("  Run: python3 nasdaq_download.py")
    if stale:
        for row in stale:
            print(f"{YELLOW}⚠ {row['contract']}: last fix {row['last_fix']}, expected "
                  f"near {row['expected_near']}. Possible coverage gap — historical "
                  f"settlement may be missing.{RESET}")
    print("=" * 60)


def main():
    print("Swedish Electricity Price Data Status")

    has_raw = print_table("RAW DATA (mixed resolution)", RAW_DIR)
    has_quarterly = print_table("QUARTERLY DATA (15-min resolution)", QUARTERLY_DIR)

    if has_raw:
        print_gaps()

    print_futures_health()

    if not has_raw:
        print("\nNo raw data downloaded yet. Run 'python download.py' to get started.")
    elif not has_quarterly:
        print("\nNo quarterly data yet. Run 'python process.py' to convert raw → quarterly.")


if __name__ == "__main__":
    main()
