"""Capture price comparison report generation."""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from .capture import calculate_capture_by_period
from .config import DATA_DIR, ZONES
from .solar_profile import list_available_profiles

# Directory for exported reports
REPORTS_DIR = DATA_DIR / "reports"


def get_available_years(zone: str = "SE3") -> list[int]:
    """Get list of years with available price data."""
    from .config import QUARTERLY_DIR, RAW_DIR

    years = set()
    for base_dir in [QUARTERLY_DIR, RAW_DIR]:
        zone_dir = base_dir / zone
        if zone_dir.exists():
            for csv_file in zone_dir.glob("*.csv"):
                # Extract year from filename (e.g., 2024-01.csv)
                try:
                    year = int(csv_file.stem.split("-")[0])
                    years.add(year)
                except ValueError:
                    pass
    return sorted(years)


def generate_capture_comparison(
    profiles: list[str] | None = None,
    zones: list[str] | None = None,
    period: str = "year",
    year: int | None = None,
) -> list[dict]:
    """
    Generate capture price comparison across profiles and zones.

    Args:
        profiles: List of profile names (default: all available except 'sweden')
        zones: List of zones (default: SE1-SE4)
        period: 'year' or 'month'
        year: Filter to specific year (for monthly breakdown)

    Returns:
        List of comparison records
    """
    if profiles is None:
        # Use all PVsyst profiles (exclude generic 'sweden')
        profiles = [p for p in list_available_profiles() if p != "sweden"]

    if zones is None:
        zones = list(ZONES)

    results = []

    for zone in zones:
        # Determine date range
        available_years = get_available_years(zone)
        if not available_years:
            continue

        if year:
            if year not in available_years:
                continue
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
        else:
            start_date = date(min(available_years), 1, 1)
            end_date = date(max(available_years), 12, 31)

        for profile in profiles:
            try:
                period_results = calculate_capture_by_period(
                    zone=zone,
                    start_date=start_date,
                    end_date=end_date,
                    period=period,
                    solar_profile=profile,
                )

                for r in period_results:
                    results.append({
                        "zone": zone,
                        "period": r["period"],
                        "profile": profile,
                        "capture_sek": r["capture_price_sek"],
                        "average_sek": r["average_price_sek"],
                        "ratio": r["capture_ratio"],
                        "records": r["records"],
                    })
            except FileNotFoundError:
                # Profile not available
                continue

    return results


def pivot_comparison(results: list[dict]) -> list[dict]:
    """
    Pivot results to have one row per zone/period with columns per profile.

    Returns:
        List of pivoted records with profile values as columns
    """
    # Group by zone + period
    grouped: dict[tuple, dict] = {}

    for r in results:
        key = (r["zone"], r["period"])
        if key not in grouped:
            grouped[key] = {
                "zone": r["zone"],
                "period": r["period"],
                "average_sek": r["average_sek"],
            }
        # Add profile-specific columns
        profile = r["profile"]
        grouped[key][f"{profile}_capture"] = r["capture_sek"]
        grouped[key][f"{profile}_ratio"] = r["ratio"]

    return [grouped[k] for k in sorted(grouped.keys())]


def format_terminal_table(
    results: list[dict],
    profiles: list[str],
    period_type: str = "year",
) -> str:
    """
    Format comparison results as a terminal table.

    Args:
        results: Pivoted comparison results
        profiles: List of profile names for column headers
        period_type: 'year' or 'month'

    Returns:
        Formatted table string
    """
    if not results:
        return "No data available."

    lines = []

    # Calculate dynamic width based on number of profiles
    # Each profile needs: 10 (capture) + 3 (sep) + 7 (ratio) + 3 (sep) = 23 chars
    # Base: Zone(4) + sep(3) + Period(8) + sep(3) + Avg(10) = 28
    base_width = 28
    per_profile_width = 23
    table_width = base_width + (per_profile_width * len(profiles))

    # Header
    title = "Capture Price Comparison (SEK/kWh)"
    lines.append(title)
    lines.append("=" * table_width)

    # Column headers
    header_parts = ["Zone", "Period"]
    for p in profiles:
        name = _short_name(p)
        header_parts.append(f"{name:>10}")
        header_parts.append(f"{name} %")
    header_parts.append("Avg Price")

    lines.append(" | ".join(header_parts))
    lines.append("-" * table_width)

    # Data rows
    for r in results:
        row_parts = [f"{r['zone']:4}", f"{r['period']:>8}"]

        for p in profiles:
            cap_key = f"{p}_capture"
            ratio_key = f"{p}_ratio"

            cap = r.get(cap_key)
            ratio = r.get(ratio_key)

            if cap is not None:
                row_parts.append(f"{cap:10.4f}")
            else:
                row_parts.append(f"{'–':>10}")

            if ratio is not None:
                row_parts.append(f"{ratio*100:6.1f}%")
            else:
                row_parts.append(f"{'–':>7}")

        avg = r.get("average_sek")
        if avg is not None:
            row_parts.append(f"{avg:10.4f}")
        else:
            row_parts.append(f"{'–':>10}")

        lines.append(" | ".join(row_parts))

    lines.append("=" * table_width)

    return "\n".join(lines)


def _short_name(profile: str) -> str:
    """Get short display name for profile."""
    names = {
        "ew_boda": "E-W",
        "south_lundby": "South",
        "tracker_sweden": "Tracker",
    }
    if profile in names:
        return names[profile]
    # Auto-detect tracker profiles
    if profile.startswith("tracker"):
        return "Tracker"
    return profile[:8]


def export_to_csv(
    results: list[dict],
    filename: str | None = None,
) -> Path:
    """
    Export comparison results to CSV.

    Args:
        results: Raw (non-pivoted) comparison results
        filename: Optional filename (default: timestamped)

    Returns:
        Path to saved file
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"capture_comparison_{timestamp}.csv"

    output_path = REPORTS_DIR / filename

    fieldnames = ["zone", "period", "profile", "capture_sek", "average_sek", "ratio", "records"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in sorted(results, key=lambda x: (x["zone"], x["period"], x["profile"])):
            writer.writerow(r)

    return output_path


def print_yearly_summary(zones: list[str] | None = None, profiles: list[str] | None = None):
    """Print yearly capture price summary to terminal."""
    if profiles is None:
        profiles = [p for p in list_available_profiles() if p != "sweden"]

    results = generate_capture_comparison(
        profiles=profiles,
        zones=zones,
        period="year",
    )

    if not results:
        print("No data available.")
        return

    pivoted = pivot_comparison(results)
    table = format_terminal_table(pivoted, profiles, "year")
    print(table)


def print_monthly_summary(
    year: int,
    zones: list[str] | None = None,
    profiles: list[str] | None = None,
):
    """Print monthly capture price summary for a specific year."""
    if profiles is None:
        profiles = [p for p in list_available_profiles() if p != "sweden"]

    results = generate_capture_comparison(
        profiles=profiles,
        zones=zones,
        period="month",
        year=year,
    )

    if not results:
        print(f"No data available for {year}.")
        return

    pivoted = pivot_comparison(results)
    table = format_terminal_table(pivoted, profiles, "month")
    print(table)
