#!/usr/bin/env python3
"""Engångsskript: extrahera nyckel-KPI:er för april 2026 för alla 8 parker."""

import io
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from elpris.park_config import list_parks, get_park_metadata
from elpris.performance_report_data import generate_report


def _fmt(v, fmt="{:.1f}", na="—"):
    return fmt.format(v) if v is not None else na


def main():
    rows = []
    for park_key in list_parks():
        meta = get_park_metadata(park_key)
        try:
            r = generate_report(park_key, 2026, 4)
        except Exception as e:
            print(f"FEL för {park_key}: {e}", file=sys.stderr)
            continue

        rev = r.revenue
        loss = r.losses
        vs_budget_pct = (
            (r.actual_energy_mwh / r.budget_energy_mwh * 100.0)
            if r.budget_energy_mwh
            else None
        )

        rows.append({
            "park": r.park_display_name,
            "zone": r.zone,
            "kwp": r.capacity_kwp,
            "actual_mwh": r.actual_energy_mwh,
            "budget_mwh": r.budget_energy_mwh,
            "vs_budget_pct": vs_budget_pct,
            "yield_kwh_kwp": r.yield_kwh_kwp,
            "pr_pct": r.performance_ratio_pct,
            "budget_pr_pct": r.budget_pr_pct,
            "avail_loss_mwh": loss.availability_loss_mwh,
            "irr_short_mwh": loss.irradiance_shortfall_loss_mwh,
            "curtail_mwh": loss.curtailment_loss_mwh,
            "rev_spot_eur": rev.revenue_spot_eur if rev else None,
            "capture_eur_mwh": rev.capture_spot_eur_mwh if rev else None,
            "baseload_eur_mwh": rev.baseload_eur_mwh if rev else None,
            "premium_pct": rev.capture_premium_pct if rev else None,
        })

    rows.sort(key=lambda x: x["actual_mwh"], reverse=True)

    # Tabell 1 — produktion vs budget
    print("\n=== APRIL 2026 — PRODUKTION & BUDGET ===")
    print(f"{'Park':<14}{'Zon':<5}{'kWp':>7}{'Faktisk':>10}{'Budget':>9}{'%':>7}{'Yield':>8}{'PR':>7}{'Bud-PR':>8}")
    print(f"{'':<14}{'':<5}{'':>7}{'MWh':>10}{'MWh':>9}{'':>7}{'kWh/kWp':>8}{'%':>7}{'%':>8}")
    print("-" * 75)
    for r in rows:
        print(
            f"{r['park']:<14}{r['zone']:<5}{r['kwp']:>7.0f}"
            f"{_fmt(r['actual_mwh'], '{:>10.1f}')}"
            f"{_fmt(r['budget_mwh'], '{:>9.1f}')}"
            f"{_fmt(r['vs_budget_pct'], '{:>6.0f}%')}"
            f"{_fmt(r['yield_kwh_kwp'], '{:>8.1f}')}"
            f"{_fmt(r['pr_pct'], '{:>6.1f}')}"
            f"{_fmt(r['budget_pr_pct'], '{:>7.1f}')}"
        )

    # Tabell 2 — förluster
    print("\n=== APRIL 2026 — FÖRLUSTANALYS (MWh) ===")
    print(f"{'Park':<14}{'Avail-loss':>11}{'Irr-short':>11}{'Curtail':>9}")
    print("-" * 45)
    for r in rows:
        print(
            f"{r['park']:<14}"
            f"{_fmt(r['avail_loss_mwh'], '{:>11.1f}')}"
            f"{_fmt(r['irr_short_mwh'], '{:>11.1f}')}"
            f"{_fmt(r['curtail_mwh'], '{:>9.1f}')}"
        )

    # Tabell 3 — intäkt & capture
    print("\n=== APRIL 2026 — INTÄKT & CAPTURE PRICE ===")
    print(f"{'Park':<14}{'Spot-rev':>12}{'Capture':>10}{'Baseload':>10}{'Premium':>10}")
    print(f"{'':<14}{'EUR':>12}{'EUR/MWh':>10}{'EUR/MWh':>10}{'%':>10}")
    print("-" * 56)
    for r in rows:
        print(
            f"{r['park']:<14}"
            f"{_fmt(r['rev_spot_eur'], '{:>12,.0f}')}"
            f"{_fmt(r['capture_eur_mwh'], '{:>10.2f}')}"
            f"{_fmt(r['baseload_eur_mwh'], '{:>10.2f}')}"
            f"{_fmt(r['premium_pct'], '{:>9.1f}%')}"
        )

    # Sammanfattning
    total_actual = sum(r["actual_mwh"] for r in rows)
    total_budget = sum(r["budget_mwh"] for r in rows if r["budget_mwh"])
    total_rev = sum(r["rev_spot_eur"] for r in rows if r["rev_spot_eur"])
    print("\n=== PORTFÖLJ-SUMMA ===")
    print(f"Total faktisk produktion : {total_actual:>10.1f} MWh")
    print(f"Total PVsyst-budget      : {total_budget:>10.1f} MWh")
    if total_budget:
        print(f"Portföljutfall vs budget : {total_actual/total_budget*100:>10.1f}%")
    print(f"Total spot-intäkt        : {total_rev:>10,.0f} EUR")


if __name__ == "__main__":
    main()
