#!/usr/bin/env python3
"""Jämför PVsyst-profilernas capture-pris mot ENTSO-E faktisk sol-capture.

Frågan: Överensstämmer våra simulerade PVsyst-profiler (south_lundby, ew_boda,
tracker_sweden) med den nationella faktiska solproduktionen per zon?

Om de avviker mycket finns risk att alla capture-siffror i dashboarden är
systematiskt fel. Om de stämmer — grunden är solid.

Output: tabell per zon × år med:
- PVsyst capture (EUR/MWh) för varje profil
- ENTSO-E faktisk solcapture (EUR/MWh)
- Avvikelse i EUR/MWh och procent
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.config import ZONES
from elpris.dashboard_v2_data import (
    STANDARD_SOLAR_PROFILES,
    _aggregate_to_yearly,
    _calculate_entsoe_capture,
    _calculate_profile_capture,
    load_entsoe_generation,
    load_pvsyst_profile,
    load_spot_prices,
)


def _yearly_capture(daily_data: dict) -> dict[int, float]:
    """Extract {year: capture_price} from daily-data dict."""
    yearly = _aggregate_to_yearly(daily_data)
    return {row["year"]: row["capture"] for row in yearly if row["capture"] is not None}


def _days_per_year(daily_data: dict) -> dict[int, int]:
    """Count number of days with data per year."""
    counts: dict[int, int] = {}
    for date_key in daily_data:
        year = int(date_key[:4])
        counts[year] = counts.get(year, 0) + 1
    return counts


def main() -> int:
    print("Laddar PVsyst-profiler...")
    pvsyst: dict[str, dict] = {}
    for key, (filename, label) in STANDARD_SOLAR_PROFILES.items():
        p = load_pvsyst_profile(filename)
        if p:
            pvsyst[key] = p
            print(f"  {key} ({label}): {len(p)} timmar")

    print()
    print("Analys: PVsyst-profil capture vs ENTSO-E faktisk sol-capture")
    print("=" * 88)

    rows = []
    for zone in ZONES:
        print(f"\nLaddar {zone}...")
        spot = load_spot_prices(zone)
        if not spot:
            print(f"  Ingen spot-data för {zone}")
            continue

        entsoe_gen = load_entsoe_generation(zone, "solar")
        if not entsoe_gen:
            print(f"  Ingen ENTSO-E sol-data för {zone}")
            continue

        # ENTSO-E capture per år
        entsoe_daily = _calculate_entsoe_capture(spot, entsoe_gen)
        entsoe_yearly = _yearly_capture(entsoe_daily)
        entsoe_days = _days_per_year(entsoe_daily)

        # Profile capture per år för varje PVsyst-profil
        profile_yearly: dict[str, dict[int, float]] = {}
        for key, profile in pvsyst.items():
            daily = _calculate_profile_capture(spot, profile)
            profile_yearly[key] = _yearly_capture(daily)

        # Skriv ut tabell per år. Märk partiella år (< 360 dagar).
        all_years = sorted(entsoe_yearly.keys())
        for year in all_years:
            entsoe = entsoe_yearly.get(year)
            if entsoe is None:
                continue
            days = entsoe_days.get(year, 0)
            is_partial = days < 360
            for key in pvsyst:
                pvsyst_cap = profile_yearly[key].get(year)
                if pvsyst_cap is None:
                    continue
                diff_eur = pvsyst_cap - entsoe
                diff_pct = (diff_eur / entsoe * 100) if entsoe else 0
                rows.append({
                    "zone": zone,
                    "year": year,
                    "profile": key,
                    "pvsyst": pvsyst_cap,
                    "entsoe": entsoe,
                    "diff_eur": diff_eur,
                    "diff_pct": diff_pct,
                    "days": days,
                    "partial": is_partial,
                })

    if not rows:
        print("\nIngen data att jämföra.")
        return 1

    # Print detailed table
    print("\n" + "=" * 96)
    print(f"{'Zone':<5} {'Year':<5} {'Profile':<14} {'Days':>5} {'PVsyst':>10} "
          f"{'ENTSO-E':>10} {'Diff':>10} {'Diff %':>10}")
    print("-" * 96)
    for r in rows:
        partial_flag = " *" if r["partial"] else "  "
        print(f"{r['zone']:<5} {r['year']:<5} {r['profile']:<14} {r['days']:>5} "
              f"{r['pvsyst']:>10.2f} {r['entsoe']:>10.2f} "
              f"{r['diff_eur']:>+10.2f} {r['diff_pct']:>+9.1f}%{partial_flag}")
    print("\n* = partiellt år (< 360 dagar ENTSO-E-data). Exkluderas från statistik.")

    # Filter out partial years for statistics
    full_year_rows = [r for r in rows if not r["partial"]]

    # Summary per profile (only full years)
    print("\n" + "=" * 96)
    print("SAMMANFATTNING (endast fullständiga år, medelavvikelse per profil)")
    print("-" * 96)
    print(f"{'Profile':<14} {'N':<4} {'Avg diff EUR':>14} {'Avg diff %':>12} "
          f"{'Max |diff %|':>14}")
    print("-" * 96)
    by_profile: dict[str, list[dict]] = {}
    for r in full_year_rows:
        by_profile.setdefault(r["profile"], []).append(r)
    for profile, profile_rows in by_profile.items():
        n = len(profile_rows)
        avg_diff = sum(r["diff_eur"] for r in profile_rows) / n
        avg_pct = sum(r["diff_pct"] for r in profile_rows) / n
        max_abs_pct = max(abs(r["diff_pct"]) for r in profile_rows)
        print(f"{profile:<14} {n:<4} {avg_diff:>+14.2f} {avg_pct:>+11.1f}% "
              f"{max_abs_pct:>13.1f}%")

    # Summary per zone (only full years)
    print("\n" + "=" * 96)
    print("SAMMANFATTNING (endast fullständiga år, medelavvikelse per zon)")
    print("-" * 96)
    print(f"{'Zone':<5} {'N':<4} {'Avg PVsyst':>12} {'Avg ENTSO-E':>12} "
          f"{'Avg diff %':>12}")
    print("-" * 96)
    by_zone: dict[str, list[dict]] = {}
    for r in full_year_rows:
        by_zone.setdefault(r["zone"], []).append(r)
    for zone in ZONES:
        if zone not in by_zone:
            continue
        zone_rows = by_zone[zone]
        n = len(zone_rows)
        avg_p = sum(r["pvsyst"] for r in zone_rows) / n
        avg_e = sum(r["entsoe"] for r in zone_rows) / n
        avg_pct = sum(r["diff_pct"] for r in zone_rows) / n
        print(f"{zone:<5} {n:<4} {avg_p:>12.2f} {avg_e:>12.2f} {avg_pct:>+11.1f}%")

    print("\n" + "=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
