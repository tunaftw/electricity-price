#!/usr/bin/env python3
"""Bryt ned juni 2026 MTD-budgetgapet i instrålning / tillgänglighet / prestanda.

Speglar unified_dashboard_data._losses_dict_prorated:
  gap = prorated_budget - actual = irr_shortfall + avail_loss + unexplained
"""
import calendar
import io
import json
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from elpris.park_config import list_parks
from elpris.performance_report_data import generate_report

YEAR, MONTH = 2026, 6
DIM = calendar.monthrange(YEAR, MONTH)[1]


def main():
    rows = []
    for pk in list_parks():
        try:
            r = generate_report(pk, YEAR, MONTH)
        except Exception as e:
            print(f"FEL {pk}: {e}", file=sys.stderr)
            continue
        days = len(r.daily or [])
        factor = min(days / DIM, 1.0) if days else 0.0
        L = r.losses
        prorated_budget = (L.budget_energy_mwh or 0.0) * factor
        actual = r.actual_energy_mwh or 0.0
        full_budget_irr = r.budget_irradiation_kwh_m2 or 0.0
        prorated_budget_irr = full_budget_irr * factor
        actual_irr = r.actual_irradiation_kwh_m2

        if actual_irr is not None and prorated_budget_irr > 0:
            irr_ratio = actual_irr / prorated_budget_irr
            irr_shortfall = prorated_budget * (1.0 - irr_ratio)
        else:
            irr_ratio = None
            irr_shortfall = 0.0
        avail_loss = L.availability_loss_mwh or 0.0
        unexplained = prorated_budget - actual - irr_shortfall - avail_loss
        gap = prorated_budget - actual

        rows.append({
            "park": r.park_display_name, "zone": r.zone,
            "prorated_budget": prorated_budget, "actual": actual, "gap": gap,
            "irr_shortfall": irr_shortfall, "avail_loss": avail_loss, "unexplained": unexplained,
            "actual_irr": actual_irr, "budget_irr": prorated_budget_irr,
            "irr_ratio_pct": (irr_ratio * 100.0) if irr_ratio is not None else None,
            "pr_pct": r.performance_ratio_pct, "budget_pr_pct": r.budget_pr_pct,
            "capture": (r.revenue.capture_spot_eur_mwh if r.revenue else None),
            "baseload": (r.revenue.baseload_eur_mwh if r.revenue else None),
        })

    rows.sort(key=lambda x: x["gap"], reverse=True)

    tb = sum(r["prorated_budget"] for r in rows)
    ta = sum(r["actual"] for r in rows)
    g_irr = sum(r["irr_shortfall"] for r in rows)
    g_av = sum(r["avail_loss"] for r in rows)
    g_un = sum(r["unexplained"] for r in rows)
    gap = tb - ta

    print(f"\n=== JUNI 2026 MTD — BUDGETGAP NEDBRYTNING ({rows and ''}) ===")
    print(f"Pro-ratad budget : {tb:8.0f} MWh")
    print(f"Faktisk          : {ta:8.0f} MWh")
    print(f"GAP              : {gap:8.0f} MWh  ({ta/tb*100:.1f}% av budget)\n")
    print(f"  Instrålning (sol < TMY) : {g_irr:8.0f} MWh  ({g_irr/gap*100:5.1f}% av gapet)")
    print(f"  Tillgänglighet (stopp)  : {g_av:8.0f} MWh  ({g_av/gap*100:5.1f}% av gapet)")
    print(f"  Prestanda/oförklarat    : {g_un:8.0f} MWh  ({g_un/gap*100:5.1f}% av gapet)")

    print(f"\n{'Park':<14}{'Gap':>8}{'Irr':>8}{'Avail':>8}{'Perf':>8}{'IrrRatio':>10}{'PR':>7}{'BudPR':>7}")
    print("-" * 70)
    for r in rows:
        ir = f"{r['irr_ratio_pct']:.0f}%" if r['irr_ratio_pct'] is not None else "—"
        pr = f"{r['pr_pct']:.0f}" if r['pr_pct'] is not None else "—"
        print(f"{r['park']:<14}{r['gap']:>8.0f}{r['irr_shortfall']:>8.0f}"
              f"{r['avail_loss']:>8.0f}{r['unexplained']:>8.0f}{ir:>10}{pr:>7}{r['budget_pr_pct']:>7.0f}")

    out = {
        "portfolio": {
            "prorated_budget_mwh": round(tb, 1), "actual_mwh": round(ta, 1), "gap_mwh": round(gap, 1),
            "vs_budget_pct": round(ta / tb * 100, 1),
            "irr_shortfall_mwh": round(g_irr, 1), "avail_loss_mwh": round(g_av, 1),
            "unexplained_mwh": round(g_un, 1),
            "irr_pct_of_gap": round(g_irr / gap * 100, 1),
            "avail_pct_of_gap": round(g_av / gap * 100, 1),
            "perf_pct_of_gap": round(g_un / gap * 100, 1),
        },
        "parks": [{
            "park": r["park"], "zone": r["zone"],
            "gap_mwh": round(r["gap"], 1),
            "irr_shortfall_mwh": round(r["irr_shortfall"], 1),
            "avail_loss_mwh": round(r["avail_loss"], 1),
            "unexplained_mwh": round(r["unexplained"], 1),
            "irr_ratio_pct": round(r["irr_ratio_pct"], 1) if r["irr_ratio_pct"] is not None else None,
            "pr_pct": round(r["pr_pct"], 1) if r["pr_pct"] is not None else None,
            "budget_pr_pct": round(r["budget_pr_pct"], 1),
            "capture": round(r["capture"], 2) if r["capture"] is not None else None,
            "baseload": round(r["baseload"], 2) if r["baseload"] is not None else None,
        } for r in rows],
    }
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n-> {sys.argv[1]}")


if __name__ == "__main__":
    main()
