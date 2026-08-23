"""Batteri & investering — data för Insikts tredje sektion.

Komponerar de tre BESS-modulerna till EN payload för renderaren:

* :func:`elpris.insikt.bess_stack.build_stack_data` — revenue stacking-DP
  (körs EN gång; kalkylen återanvänder resultatet i stället för att köra
  om DP:n).
* :func:`elpris.insikt.bess_kalkyl.build_kalkyl_data` — IRR/NPV/payback/
  break-even per zon × duration × acceptans.
* :func:`elpris.insikt.bess_stack.build_btm_real_data` — behind-the-meter
  mot parkernas FAKTISKA profiler vs TMY.

Payload-beskärning (dokumenterad): stack-månadsraderna släpps — UI:t
visar årsnivån (senaste hela året per zon × duration, samma årsval som
kalkylen via ``bess_kalkyl._pick_year``). Kvar per rad: intäktsjämförelsen,
produktmixen, reservandelen och acceptanskänsligheten.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .bess_kalkyl import (
    build_kalkyl_data,
    build_kalkyl_insights,
    _duration_hours,
    _pick_year,
)
from .bess_stack import (
    PRODUCT_LABELS,
    build_btm_real_data,
    build_stack_data,
    build_stack_insights,
)


def _stack_rows(stack_data: dict) -> List[dict]:
    """Platta ut stackingen till en rad per zon × duration (senaste hela år).

    Samma årsval som kalkylen (:func:`bess_kalkyl._pick_year`) så att
    stacking-tabellen och kalkyl-tabellen alltid talar om samma år.
    """
    rows: List[dict] = []
    for zone in sorted(stack_data.get("zones", {})):
        durs = stack_data["zones"][zone]
        for dur_key in sorted(durs, key=lambda k: _duration_hours(k) or 0):
            hours = _duration_hours(dur_key)
            if hours is None:
                continue
            yrow = _pick_year(durs[dur_key].get("yearly", []))
            if yrow is None:
                continue
            rows.append({
                "zone": zone,
                "duration_h": hours,
                "year": yrow.get("year"),
                "days": yrow.get("days"),
                "stacked_eur": yrow.get("stacked_eur"),
                "arb_only_eur": yrow.get("arb_only_eur"),
                "best_ancillary_only_eur": yrow.get("best_ancillary_only_eur"),
                "best_ancillary_product": yrow.get("best_ancillary_product"),
                "uplift_vs_best_single_pct": yrow.get(
                    "uplift_vs_best_single_pct"
                ),
                "reserve_share_pct": yrow.get("reserve_share_pct"),
                "cycles": yrow.get("cycles"),
                "top_product_mix": yrow.get("top_product_mix") or {},
                "acceptance_sensitivity": yrow.get(
                    "acceptance_sensitivity"
                ) or {},
                "invariant_ok": yrow.get("invariant_ok"),
            })
    return rows


def _kalkyl_rows(kalkyl_data: dict) -> List[dict]:
    """Platta ut kalkylen till en rad per zon × duration (huvudacceptans)."""
    rows: List[dict] = []
    for zone in sorted(kalkyl_data.get("zones", {})):
        durs = kalkyl_data["zones"][zone]
        for dur_key in sorted(durs, key=lambda k: _duration_hours(k) or 0):
            block = durs[dur_key]
            acc = block.get("acceptance") or {}
            if not acc:
                continue
            main_key = max(acc, key=lambda k: float(k))
            main = acc[main_key]
            rows.append({
                "zone": zone,
                "duration_h": block.get("duration_h"),
                "year": block.get("year"),
                "year_complete": block.get("year_complete"),
                "capex_eur": block.get("capex_eur"),
                "annual_gross_eur": main.get("annual_gross_eur"),
                "irr_pct": main.get("irr_pct"),
                "npv_eur": main.get("npv_eur"),
                "payback_yr": main.get("payback_yr"),
                "breakeven_revenue_pct": main.get("breakeven_revenue_pct"),
                "viable": main.get("viable"),
                "acceptance": main_key,
            })
    return rows


def build_bess_sektion_data(
    stack_data: Optional[dict] = None,
    kalkyl_data: Optional[dict] = None,
    btm_data: Optional[dict] = None,
) -> Dict[str, Any]:
    """Bygg hela datastrukturen för sektionen Batteri & investering.

    Args:
        stack_data: valfri injicerad stackingdata (tester/cachning) —
            annars körs DP:n här (~10 s + Mimer/spot-laddning).
        kalkyl_data: valfri injicerad kalkyl (tester); annars beräknas
            den ur ``stack_data`` UTAN att köra om DP:n.
        btm_data: valfri injicerad BTM-data (tester).
    """
    if stack_data is None:
        stack_data = build_stack_data()
    if kalkyl_data is None:
        kalkyl_data = build_kalkyl_data(stack_data=stack_data)
    if btm_data is None:
        btm_data = build_btm_real_data()

    return {
        "params": stack_data.get("params"),
        "product_labels": dict(PRODUCT_LABELS),
        "stack_rows": _stack_rows(stack_data),
        "kalkyl_params": kalkyl_data.get("params"),
        "kalkyl_rows": _kalkyl_rows(kalkyl_data),
        "kalkyl_zones": kalkyl_data.get("zones"),
        "kalkyl_best": kalkyl_data.get("best"),
        "btm": btm_data,
        "stack_insights": build_stack_insights(stack_data, btm_data),
        "kalkyl_insights": build_kalkyl_insights(kalkyl_data),
    }
