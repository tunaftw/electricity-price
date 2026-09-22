"""Portföljen: produktion, budget, datatäckning och capture per park och månad.

Definitioner (samma som visas på sidan):

* **Produktion** — uppmätt nätleverans. Mätaren gäller; invertern används
  bara när mätaren saknas och värdet är levande (se
  ``operations_dashboard_data.load_park_15min``). Kvartar utan trovärdig
  signal räknas inte — de är okända, inte noll.
* **Datatäckning** — andel av månadens dagsljus (solhöjd > 5°, varje kvart
  viktad med sin(solhöjd)) som har en trovärdig mätning.
* **Mot budget** — produktion delat med budget för *samma* tid som har
  data, minus 1. Månadsbudgeten (PVsyst) fördelas över månadens kvartar
  med samma solhöjdsvikt. Visas bara när täckningen är minst
  ``MIN_COVERAGE_FOR_BUDGET`` — annars är jämförelsen för osäker.
* **Capturepris** — Σ(energi × spotpris) / Σ energi i parkens elområde.
* **Capture-kvot** — capturepris / genomsnittligt spotpris (tidsviktat,
  dygnet runt) i samma elområde under de dygn parken har mätdata.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import PARK_CAPACITY_KWP, PARK_ZONES, SWEDEN_TZ
from ..park_config import PARK_METADATA, get_budget
from ..solar_geometry import solar_elevation_deg
from ..temperature import PARK_COORDS
from .common import (
    CAL,
    park_records,
    QUARTER_S,
    month_bounds,
    month_keys,
    quarter_prices,
)

MIN_COVERAGE_FOR_BUDGET = 0.80   # under detta visas inte "mot budget"
GOOD_COVERAGE = 0.95             # under detta märks värden som osäkra
DAYLIGHT_MIN_ELEVATION = 5.0
FIRST_MONTH = "2025-01"
OBSERVED = ("meter", "inverter")

PARK_ORDER = ["horby", "agerum", "tangen", "fjallskar", "hova", "bjorke",
              "skakelbacken", "stenstorp"]


def _weight(epoch: int, coords) -> float:
    elev = solar_elevation_deg(datetime.fromtimestamp(epoch + QUARTER_S // 2, SWEDEN_TZ), *coords)
    return math.sin(math.radians(elev)) if elev > DAYLIGHT_MIN_ELEVATION else 0.0


def _park_info(park: str, first_epoch: Optional[int]) -> Dict[str, Any]:
    meta = PARK_METADATA.get(park, {})
    return {
        "key": park,
        "name": meta.get("display_name", park),
        "zone": PARK_ZONES[park],
        "kwp": PARK_CAPACITY_KWP[park],
        "location": meta.get("location"),
        "type": "tracker" if meta.get("tracking") else "fast",
        "grid_limit_mw": meta.get("grid_limit_mwac"),
        "first_data": CAL.day(first_epoch) if first_epoch else None,
    }


def _rnd(v: Optional[float], d: int = 1) -> Optional[float]:
    return None if v is None else round(v, d)


def _ratio(num: float, den: float) -> Optional[float]:
    return num / den if den else None


def build_park(park: str, data_end: int) -> Dict[str, Any]:
    """Månads- och dagsvärden för en park fram till data_end (exklusivt)."""
    zone = PARK_ZONES[park]
    coords = PARK_COORDS[park]
    prices = quarter_prices(zone)
    records = park_records(park)
    obs: Dict[int, tuple] = {}
    for r in records:
        e = int(r["timestamp_utc"].timestamp())
        obs[e] = (r["energy_source"], r["effective_power_mw"])
    observed_epochs = [e for e, (src, _) in obs.items() if src in OBSERVED]
    first_epoch = min(observed_epochs) if observed_epochs else None
    last_meter = max((e for e, (src, _) in obs.items() if src == "meter"), default=None)
    last_obs = max(observed_epochs, default=None)

    months: Dict[str, Dict[str, Any]] = {}
    days: Dict[str, List[Dict[str, Any]]] = {}
    if first_epoch is None:
        return {"info": _park_info(park, None), "months": months, "days": days,
                "last_meter": None, "last_observed": None}

    first_month = max(CAL.month(first_epoch), FIRST_MONTH)
    last_month = CAL.month(data_end - 1)
    for mk in month_keys(first_month, last_month):
        m_start, m_end = month_bounds(mk)
        p_end = min(m_end, data_end)
        budget_month = get_budget(park, int(mk[:4]), int(mk[5:]))["energy_mwh"]

        w_full = w_period = w_cov = 0.0
        energy = value = neg_energy = priced_energy = 0.0
        meter_energy = 0.0
        day_acc: Dict[str, Dict[str, float]] = {}
        q = m_start
        while q < m_end:
            w = _weight(q, coords)
            w_full += w
            if q < p_end:
                day = CAL.day(q)
                d = day_acc.setdefault(day, {"w": 0.0, "wc": 0.0, "e": 0.0})
                w_period += w
                d["w"] += w
                src_mw = obs.get(q)
                if src_mw and src_mw[0] in OBSERVED:
                    w_cov += w
                    d["wc"] += w
                    e_mwh = src_mw[1] * 0.25
                    energy += e_mwh
                    d["e"] += e_mwh
                    if src_mw[0] == "meter":
                        meter_energy += e_mwh
                    price = prices.get(q)
                    if price is not None:
                        value += e_mwh * price
                        priced_energy += e_mwh
                        if price < 0:
                            neg_energy += e_mwh
            q += QUARTER_S

        coverage = _ratio(w_cov, w_period)
        budget_period = budget_month * _ratio(w_period, w_full) if w_full else None
        budget_obs = budget_month * w_cov / w_full if w_full else None
        vs_budget = None
        if coverage is not None and coverage >= MIN_COVERAGE_FOR_BUDGET and budget_obs:
            vs_budget = energy / budget_obs - 1
        capture = _ratio(value, priced_energy)
        # Spotpris för jämförelse: alla kvartar (dygnet runt) under de dygn
        # parken har mätdata. Saknas halva månaden ska kvoten inte jämföra
        # parkens dagar med en annan prisperiod.
        obs_days = {day for day, acc in day_acc.items() if acc["wc"] > 0}
        month_prices = [prices[t] for t in range(m_start, p_end, QUARTER_S)
                        if t in prices and CAL.day(t) in obs_days]
        baseload = sum(month_prices) / len(month_prices) if month_prices else None

        months[mk] = {
            "energy_mwh": round(energy, 2),
            "budget_month_mwh": round(budget_month, 1),
            "budget_period_mwh": _rnd(budget_period),
            "budget_obs_mwh": _rnd(budget_obs, 2),
            "coverage": _rnd(coverage, 4),
            "vs_budget": _rnd(vs_budget, 4),
            "yield_kwh_kwp": round(energy * 1000 / PARK_CAPACITY_KWP[park], 1),
            "capture_eur": _rnd(capture, 2),
            "baseload_eur": _rnd(baseload, 2),
            "capture_ratio": _rnd(_ratio(capture, baseload) if capture is not None and baseload else None, 4),
            "value_eur": round(value, 0),
            "neg_share": _rnd(_ratio(neg_energy, priced_energy), 4),
            "meter_share": _rnd(_ratio(meter_energy, energy), 4),
            "partial": p_end < m_end,
        }
        days[mk] = [
            {
                "date": day,
                "energy_mwh": round(acc["e"], 2),
                "budget_mwh": round(budget_month * acc["w"] / w_full, 2) if w_full else None,
                "coverage": _rnd(_ratio(acc["wc"], acc["w"]), 3),
            }
            for day, acc in sorted(day_acc.items())
        ]

    return {
        "info": _park_info(park, first_epoch),
        "months": months,
        "days": days,
        "last_meter": CAL.day(last_meter) if last_meter else None,
        "last_observed": CAL.day(last_obs) if last_obs else None,
    }


def aggregate(park_months: List[tuple]) -> Dict[str, Any]:
    """Summera park-månader till ett portfölj-/periodvärde.

    park_months: lista av (park_key, zone, kwp, month_dict).
    """
    energy = value = 0.0
    inc_energy = inc_budget = 0.0
    budget_period = budget_obs = 0.0
    zone_energy: Dict[str, float] = {}
    zone_base_weighted = 0.0
    priced_for_base = 0.0
    neg_num = neg_den = 0.0
    kwp_energy = 0.0
    included, excluded = set(), set()
    for park, zone, kwp, m in park_months:
        energy += m["energy_mwh"]
        value += m["value_eur"]
        if m.get("budget_period_mwh"):
            budget_period += m["budget_period_mwh"]
        if m.get("budget_obs_mwh"):
            budget_obs += m["budget_obs_mwh"]
        if m["vs_budget"] is not None:
            inc_energy += m["energy_mwh"]
            inc_budget += m["budget_obs_mwh"]
            included.add(park)
        else:
            excluded.add(park)
        if m["baseload_eur"] is not None and m["energy_mwh"] > 0:
            zone_base_weighted += m["energy_mwh"] * m["baseload_eur"]
            priced_for_base += m["energy_mwh"]
        if m["neg_share"] is not None:
            neg_num += m["neg_share"] * m["energy_mwh"]
            neg_den += m["energy_mwh"]
        zone_energy[zone] = zone_energy.get(zone, 0.0) + m["energy_mwh"]
        kwp_energy += kwp
    # En park som saknar jämförbar budget i någon av periodens månader räknas
    # ändå som "med" om den har minst en jämförbar månad — men då bara med de
    # månaderna (hanteras ovan per månad).
    excluded -= included
    capture = _ratio(value, energy)
    base_mix = _ratio(zone_base_weighted, priced_for_base)
    return {
        "energy_mwh": round(energy, 1),
        "budget_period_mwh": round(budget_period, 1),
        "budget_obs_mwh": round(budget_obs, 1),
        "vs_budget": _rnd(inc_energy / inc_budget - 1, 4) if inc_budget else None,
        "compared_energy_mwh": round(inc_energy, 1),
        "compared_budget_mwh": round(inc_budget, 1),
        "coverage": _rnd(_ratio(budget_obs, budget_period), 4),
        "capture_eur": _rnd(capture, 2),
        "baseload_mix_eur": _rnd(base_mix, 2),
        "capture_ratio": _rnd(capture / base_mix, 4) if capture and base_mix else None,
        "value_eur": round(value, 0),
        "neg_share": _rnd(_ratio(neg_num, neg_den), 4),
        "parks_included": sorted(included, key=PARK_ORDER.index),
        "parks_excluded": sorted(excluded, key=PARK_ORDER.index),
    }


def end_of_last_complete_day(last_quarter_start: int) -> int:
    """Lokal midnatt efter sista kompletta dygnet som innehåller data."""
    day = datetime.fromisoformat(CAL.day(last_quarter_start))
    midnight = datetime(day.year, day.month, day.day, tzinfo=SWEDEN_TZ)
    next_midnight = datetime.fromtimestamp(midnight.timestamp() + 26 * 3600, SWEDEN_TZ)
    next_midnight = datetime(next_midnight.year, next_midnight.month, next_midnight.day,
                             tzinfo=SWEDEN_TZ)
    if last_quarter_start + QUARTER_S >= next_midnight.timestamp():
        return int(next_midnight.timestamp())
    return int(midnight.timestamp())


def build_portfolj_data(data_end: Optional[int] = None) -> Dict[str, Any]:
    """Hela portföljsektionens data.

    data_end: exklusivt slut (epok). Default = senaste kvart som finns i
    någon parkfil + 15 min, avrundat nedåt till hel lokal dag så att en
    halv dag inte ser ut som en dålig dag.
    """
    parks_present = [p for p in PARK_ORDER if p in PARK_ZONES]
    if data_end is None:
        latest = 0
        for p in parks_present:
            recs = park_records(p)
            if recs:
                latest = max(latest, int(recs[-1]["timestamp_utc"].timestamp()))
        data_end = end_of_last_complete_day(latest)

    parks = {p: build_park(p, data_end) for p in parks_present}
    all_months = sorted({mk for p in parks.values() for mk in p["months"]})

    portfolio: Dict[str, Any] = {}
    ytd: Dict[str, Any] = {}
    park_ytd: Dict[str, Dict[str, Any]] = {p: {} for p in parks}
    for mk in all_months:
        rows = [(p, d["info"]["zone"], d["info"]["kwp"], d["months"][mk])
                for p, d in parks.items() if mk in d["months"]]
        portfolio[mk] = aggregate(rows)
        portfolio[mk]["kwp"] = sum(r[2] for r in rows)
        portfolio[mk]["yield_kwh_kwp"] = round(
            portfolio[mk]["energy_mwh"] * 1000 / portfolio[mk]["kwp"], 1) if rows else None
        portfolio[mk]["partial"] = any(r[3]["partial"] for r in rows)
        year_rows = [(p, d["info"]["zone"], d["info"]["kwp"], d["months"][k])
                     for p, d in parks.items() for k in d["months"]
                     if k[:4] == mk[:4] and k <= mk]
        ytd[mk] = aggregate(year_rows)
        for p, d in parks.items():
            pr = [(p, d["info"]["zone"], d["info"]["kwp"], d["months"][k])
                  for k in d["months"] if k[:4] == mk[:4] and k <= mk]
            if pr:
                a = aggregate(pr)
                a["yield_kwh_kwp"] = round(a["energy_mwh"] * 1000 / d["info"]["kwp"], 1)
                park_ytd[p][mk] = a

    complete = [mk for mk in all_months if not portfolio[mk]["partial"]]
    default_month = complete[-1] if complete else (all_months[-1] if all_months else None)

    return {
        "data_end": CAL.day(data_end - 1),
        "months": all_months,
        "default_month": default_month,
        "parks": {p: {"info": d["info"], "months": d["months"], "days": d["days"],
                      "ytd": park_ytd[p], "last_meter": d["last_meter"],
                      "last_observed": d["last_observed"]}
                  for p, d in parks.items()},
        "portfolio": portfolio,
        "ytd": ytd,
        "rules": {
            "min_coverage_for_budget": MIN_COVERAGE_FOR_BUDGET,
            "good_coverage": GOOD_COVERAGE,
        },
    }
