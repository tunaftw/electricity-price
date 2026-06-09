"""Obalansprisanalys (eSett) för rework-dashboarden.

eSett-datat (15-min obalanspriser per zon från 2023-05-22) har hittills
varit helt outnyttjat i presentationslagret. För en solproducent är den
relevanta storheten **kostnaden för prognosfel**: skillnaden mellan
obalanspris och spotpris i det kvarter felet inträffar.

Vi beräknar per zon och månad:

* ``mean_abs_diff`` — E[|obalanspris − spot|], proxy för förväntad
  kostnad per MWh prognosfel (oavsett riktning).
* ``p90_abs_diff`` — svansrisken: var 10:e kvart kostar mer än så.
* ``share_up`` / ``share_down`` — andel kvarter där systemet
  uppreglerades resp. nedreglerades (riktningsklimatet).

Aggregeringsfunktionen är ren (tar radlistor) för enhetstestning.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .config import ESETT_DATA_DIR, ZONES

IMBALANCE_DIR = ESETT_DATA_DIR / "imbalance"


def aggregate_imbalance_monthly(rows: Iterable[dict]) -> List[dict]:
    """Aggregera eSett-rader till månadsstatistik.

    Args:
        rows: dicts med ``time_start`` (ISO, "Z"-suffix ok),
            ``imbl_spot_diff_eur_mwh`` och ``main_dir_reg_power``
            (−1 = nedreglering, +1 = uppreglering, 0 = balans).

    Returns:
        [{"month": "YYYY-MM", "mean_abs_diff", "mean_diff",
          "p90_abs_diff", "share_up", "share_down", "n"}, ...]
    """
    acc: Dict[str, dict] = defaultdict(
        lambda: {"abs_vals": [], "sum_diff": 0.0, "up": 0, "down": 0, "n": 0}
    )

    for row in rows:
        ts = (row.get("time_start") or "")
        if len(ts) < 7:
            continue
        diff_raw = row.get("imbl_spot_diff_eur_mwh")
        try:
            diff = float(diff_raw)
        except (TypeError, ValueError):
            continue

        month_key = ts[:7]
        a = acc[month_key]
        a["abs_vals"].append(abs(diff))
        a["sum_diff"] += diff
        a["n"] += 1

        try:
            direction = float(row.get("main_dir_reg_power") or 0)
        except (TypeError, ValueError):
            direction = 0.0
        if direction > 0:
            a["up"] += 1
        elif direction < 0:
            a["down"] += 1

    out: List[dict] = []
    for month_key in sorted(acc):
        a = acc[month_key]
        n = a["n"]
        if n == 0:
            continue
        vals = sorted(a["abs_vals"])
        p90_idx = min(int(0.9 * (n - 1)), n - 1)
        out.append({
            "month": month_key,
            "mean_abs_diff": round(sum(vals) / n, 2),
            "mean_diff": round(a["sum_diff"] / n, 2),
            "p90_abs_diff": round(vals[p90_idx], 2),
            "share_up": round(a["up"] / n * 100.0, 1),
            "share_down": round(a["down"] / n * 100.0, 1),
            "n": n,
        })
    return out


def iter_imbalance_rows(zone: str):
    """Yield:a rader ur eSett-CSV:erna för en zon (alla år)."""
    zone_dir = IMBALANCE_DIR / zone
    if not zone_dir.exists():
        return
    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                yield row


def build_imbalance_analysis(zones: Optional[List[str]] = None) -> dict:
    """Bygg obalanssektionen: månadsstatistik per zon + 12-mån summering.

    Returns:
        {"zones": {zon: {"monthly": [...], "last12": {...}}}}
    """
    if zones is None:
        zones = ZONES

    result: Dict[str, dict] = {}
    for zone in zones:
        monthly = aggregate_imbalance_monthly(iter_imbalance_rows(zone))
        if not monthly:
            continue

        last12 = monthly[-12:]
        n_tot = sum(m["n"] for m in last12)
        summary = None
        if n_tot > 0:
            summary = {
                "mean_abs_diff": round(
                    sum(m["mean_abs_diff"] * m["n"] for m in last12) / n_tot, 2
                ),
                "share_up": round(
                    sum(m["share_up"] * m["n"] for m in last12) / n_tot, 1
                ),
                "share_down": round(
                    sum(m["share_down"] * m["n"] for m in last12) / n_tot, 1
                ),
                "from_month": last12[0]["month"],
                "to_month": last12[-1]["month"],
            }

        result[zone] = {"monthly": monthly, "last12": summary}

    return {"zones": result}
