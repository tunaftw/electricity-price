#!/usr/bin/env python3
"""Extrahera juni 2026 MTD-KPI:er för alla parker + portfölj till JSON.

Pro-ratar PVsyst-budget med faktorn dagar_med_data / dagar_i_månaden,
samma metod som unified_dashboard_data._partial_month_factor.
"""

import calendar
import io
import json
import sys
from datetime import date

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from elpris.park_config import list_parks, get_park_metadata
from elpris.performance_report_data import generate_report

YEAR, MONTH = 2026, 6
DAYS_IN_MONTH = calendar.monthrange(YEAR, MONTH)[1]


def main():
    parks = []
    # portfölj-aggregerad daglig serie
    daily_actual = {}   # date_str -> summa MWh
    days_seen = set()

    for park_key in list_parks():
        meta = get_park_metadata(park_key)
        try:
            r = generate_report(park_key, YEAR, MONTH)
        except Exception as e:
            print(f"FEL {park_key}: {e}", file=sys.stderr)
            continue

        daily = r.daily or []
        days_with_data = len(daily)
        factor = min(days_with_data / DAYS_IN_MONTH, 1.0) if days_with_data else 0.0

        full_budget = r.budget_energy_mwh or 0.0
        prorated_budget = full_budget * factor
        actual = r.actual_energy_mwh or 0.0
        vs_budget_pct = (actual / prorated_budget * 100.0) if prorated_budget else None

        rev = r.revenue
        rev_eur = rev.revenue_spot_eur if rev else None
        capture = rev.capture_spot_eur_mwh if rev else None
        baseload = rev.baseload_eur_mwh if rev else None
        premium = rev.capture_premium_pct if rev else None

        # estimerad budget-intäkt = pro-ratad budget-MWh × capture (samma EUR/MWh)
        budget_rev_eur = (prorated_budget * capture) if (capture is not None) else None

        # daglig serie
        day_rows = []
        for d in daily:
            ds = d.date_str
            e = d.actual_energy_mwh or 0.0
            day_rows.append({"date": ds, "energy_mwh": round(e, 3)})
            daily_actual[ds] = daily_actual.get(ds, 0.0) + e
            days_seen.add(ds)

        parks.append({
            "park": r.park_display_name,
            "zone": r.zone,
            "kwp": r.capacity_kwp,
            "days_with_data": days_with_data,
            "factor": round(factor, 4),
            "actual_mwh": round(actual, 2),
            "full_budget_mwh": round(full_budget, 2),
            "prorated_budget_mwh": round(prorated_budget, 2),
            "vs_budget_pct": round(vs_budget_pct, 1) if vs_budget_pct is not None else None,
            "yield_kwh_kwp": round(r.yield_kwh_kwp, 1) if r.yield_kwh_kwp is not None else None,
            "pr_pct": round(r.performance_ratio_pct, 1) if r.performance_ratio_pct is not None else None,
            "budget_pr_pct": round(r.budget_pr_pct, 1) if r.budget_pr_pct is not None else None,
            "rev_spot_eur": round(rev_eur) if rev_eur is not None else None,
            "budget_rev_eur": round(budget_rev_eur) if budget_rev_eur is not None else None,
            "capture_eur_mwh": round(capture, 2) if capture is not None else None,
            "baseload_eur_mwh": round(baseload, 2) if baseload is not None else None,
            "premium_pct": round(premium, 1) if premium is not None else None,
            "daily": day_rows,
        })

    parks.sort(key=lambda x: x["actual_mwh"], reverse=True)

    # portfölj-summa
    tot_actual = sum(p["actual_mwh"] for p in parks)
    tot_prorated_budget = sum(p["prorated_budget_mwh"] for p in parks)
    tot_full_budget = sum(p["full_budget_mwh"] for p in parks)
    tot_rev = sum(p["rev_spot_eur"] for p in parks if p["rev_spot_eur"])
    tot_budget_rev = sum(p["budget_rev_eur"] for p in parks if p["budget_rev_eur"])
    tot_kwp = sum(p["kwp"] for p in parks)

    # daglig portfölj-serie (sorterad), med kumulativ
    sorted_days = sorted(daily_actual.keys())
    daily_series = []
    cum_actual = 0.0
    daily_budget = tot_full_budget / DAYS_IN_MONTH  # platt pro-ratad budget/dag
    cum_budget = 0.0
    for i, ds in enumerate(sorted_days):
        e = daily_actual[ds]
        cum_actual += e
        cum_budget += daily_budget
        daily_series.append({
            "date": ds,
            "actual_mwh": round(e, 2),
            "budget_mwh": round(daily_budget, 2),
            "cum_actual_mwh": round(cum_actual, 2),
            "cum_budget_mwh": round(cum_budget, 2),
        })

    out = {
        "year": YEAR,
        "month": MONTH,
        "days_in_month": DAYS_IN_MONTH,
        "days_with_data": len(sorted_days),
        "last_date": sorted_days[-1] if sorted_days else None,
        "portfolio": {
            "kwp": round(tot_kwp),
            "actual_mwh": round(tot_actual, 1),
            "prorated_budget_mwh": round(tot_prorated_budget, 1),
            "full_budget_mwh": round(tot_full_budget, 1),
            "vs_budget_pct": round(tot_actual / tot_prorated_budget * 100.0, 1) if tot_prorated_budget else None,
            "rev_spot_eur": round(tot_rev),
            "budget_rev_eur": round(tot_budget_rev) if tot_budget_rev else None,
        },
        "parks": parks,
        "daily_series": daily_series,
    }

    out_path = sys.argv[1] if len(sys.argv) > 1 else "june_mtd.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # konsol-sammanfattning
    p = out["portfolio"]
    print(f"Juni 2026 MTD t.o.m. {out['last_date']} ({out['days_with_data']}/{DAYS_IN_MONTH} dagar)")
    print(f"Produktion : {p['actual_mwh']:.1f} MWh")
    print(f"Budget(pro): {p['prorated_budget_mwh']:.1f} MWh")
    print(f"Mot budget : {p['vs_budget_pct']:.1f}%")
    print(f"Spot-intäkt: {p['rev_spot_eur']:,} EUR")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
