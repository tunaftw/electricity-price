"""Batteri: dagsspread och ett transparent arbitrage-tak per zon.

Definitioner (samma som visas på sidan):

* **Dagsspread (2 h)** — medelpriset under dygnets två dyraste timmar minus
  medelpriset under dygnets två billigaste timmar (EUR/MWh). Modellfritt.
* **Arbitrage-tak, 1 cykel/dag** — vad ett batteri på 1 MW / 2 MWh hade
  tjänat per dygn om det visste dagens priser i förväg: laddar högst 2 MWh
  per dygn och säljer det senare samma dygn, 88 % verkningsgrad tur och
  retur. Summerat per år i EUR per MW installerad effekt. Det är ett **tak**
  — perfekt framförhållning, inga nätavgifter, ingen degradering, inga
  stödtjänster. En verklig handelsstrategi fångar en del av det.

Allt räknas på timpriser (kvartspriser medelvärdesbildas efter
2025-10-01) så att tidsserien är jämförbar över hela perioden. Effekten
av att handla på kvartsnivå redovisas separat som en uppsida.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .common import CAL, HOUR_S, QUARTER_S, available_zones, hourly_prices, quarter_prices

POWER_MW = 1.0
ENERGY_MWH = 2.0
ROUND_TRIP_EFF = 0.88
FIRST_DAY = "2023-01-01"
SPREAD_HOURS = 2


def best_one_cycle(prices: List[float], block_mwh: float, blocks: int,
                   eff: float = ROUND_TRIP_EFF) -> float:
    """Max intäkt för en laddcykel under ett dygn (perfekt framförhållning).

    Varje steg kan batteriet ladda eller ladda ur ett block (``block_mwh``,
    t.ex. 1 MWh per timme vid 1 MW). Totalt högst ``blocks`` block laddas
    per dygn (= 1 cykel) och lagret rymmer ``blocks`` block. Verkningsgraden
    dras vid urladdning. Returnerar EUR (≥ 0).
    """
    neg = float("-inf")
    # state index = level * (blocks + 1) + charged
    width = blocks + 1
    best = [neg] * (width * width)
    best[0] = 0.0
    for p in prices:
        buy = p * block_mwh
        sell = p * block_mwh * eff
        nxt = best[:]
        for level in range(width):
            for charged in range(level, width):
                v = best[level * width + charged]
                if v == neg:
                    continue
                if level < blocks and charged < blocks:
                    i = (level + 1) * width + charged + 1
                    if v - buy > nxt[i]:
                        nxt[i] = v - buy
                if level > 0:
                    i = (level - 1) * width + charged
                    if v + sell > nxt[i]:
                        nxt[i] = v + sell
        best = nxt
    return max(0.0, max(best[c] for c in range(width)))  # tomt lager vid dygnets slut


def _daily_series(prices: Dict[int, float], step: int, data_end: int) -> Dict[str, List[float]]:
    days: Dict[str, List[tuple]] = {}
    for t, p in prices.items():
        if t >= data_end:
            continue
        d = CAL.day(t)
        if d < FIRST_DAY:
            continue
        days.setdefault(d, []).append((t, p))
    expected_min = (20 * HOUR_S) // step  # släpp dygn med stora luckor
    return {d: [p for _, p in sorted(v)] for d, v in days.items() if len(v) >= expected_min}


def _percentile(sorted_vals: List[float], q: float) -> Optional[float]:
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def zone_battery(zone: str, data_end: int, with_quarter_uplift: bool) -> Dict[str, Any]:
    daily = _daily_series(hourly_prices(zone), HOUR_S, data_end)
    blocks = int(round(ENERGY_MWH / POWER_MW))
    rows = []
    for d, prices in sorted(daily.items()):
        srt = sorted(prices)
        spread = sum(srt[-SPREAD_HOURS:]) / SPREAD_HOURS - sum(srt[:SPREAD_HOURS]) / SPREAD_HOURS
        rev = best_one_cycle(prices, POWER_MW * 1.0, blocks)
        rows.append((d, spread, rev))

    monthly: Dict[str, Dict[str, float]] = {}
    for d, spread, rev in rows:
        m = monthly.setdefault(d[:7], {"n": 0, "spread": 0.0, "rev": 0.0})
        m["n"] += 1
        m["spread"] += spread
        m["rev"] += rev
    yearly: Dict[str, Dict[str, Any]] = {}
    for d, spread, rev in rows:
        y = yearly.setdefault(d[:4], {"days": 0, "revenue_eur_mw": 0.0})
        y["days"] += 1
        y["revenue_eur_mw"] += rev
    for y in yearly.values():
        y["revenue_eur_mw"] = round(y["revenue_eur_mw"])

    last12 = rows[-365:]
    revs = sorted(r[2] for r in last12)
    total12 = sum(revs)
    top_n = max(1, len(revs) // 10)
    out = {
        "monthly": {mk: {"spread_2h": round(v["spread"] / v["n"], 1),
                         "revenue_eur_mw": round(v["rev"]), "days": v["n"]}
                    for mk, v in sorted(monthly.items())},
        "yearly": yearly,
        "rolling_12m": {
            "from": last12[0][0] if last12 else None,
            "to": last12[-1][0] if last12 else None,
            "days": len(last12),
            "revenue_eur_mw": round(total12),
            "daily_p10": round(_percentile(revs, 0.10) or 0),
            "daily_median": round(_percentile(revs, 0.50) or 0),
            "daily_p90": round(_percentile(revs, 0.90) or 0),
            "top10pct_share": round(sum(revs[-top_n:]) / total12, 3) if total12 else None,
            "spread_2h": round(sum(r[1] for r in last12) / len(last12), 1) if last12 else None,
        },
    }
    if with_quarter_uplift and last12:
        qdaily = _daily_series(quarter_prices(zone), QUARTER_S, data_end)
        first = last12[0][0]
        common = [d for d, _, _ in last12 if d in qdaily and d >= "2025-10-01" and d >= first]
        if common:
            hourly_rev = {d: r for d, _, r in last12}
            q_blocks = int(round(ENERGY_MWH / (POWER_MW * 0.25)))
            q_total = sum(best_one_cycle(qdaily[d], POWER_MW * 0.25, q_blocks) for d in common)
            h_total = sum(hourly_rev[d] for d in common)
            out["quarter_uplift"] = {
                "days": len(common),
                "from": common[0],
                "uplift": round(q_total / h_total - 1, 3) if h_total else None,
            }
    return out


def build_batteri_data(data_end: int) -> Dict[str, Any]:
    zones = available_zones()
    per_zone = {z: zone_battery(z, data_end, with_quarter_uplift=z in ("SE3", "SE4"))
                for z in zones}
    return {
        "zones": zones,
        "per_zone": per_zone,
        "assumptions": {
            "power_mw": POWER_MW,
            "energy_mwh": ENERGY_MWH,
            "round_trip_eff": ROUND_TRIP_EFF,
            "cycles_per_day": 1,
            "spread_hours": SPREAD_HOURS,
        },
    }
