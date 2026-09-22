"""Elmarknaden: spotpris, solens capture rate och negativa priser per zon.

Definitioner (samma som visas på sidan):

* **Spotpris (baspris)** — tidsviktat medel av day-ahead-priset i zonen.
* **Solpris** — spotpriset viktat med zonens *faktiska* solproduktion
  (ENTSO-E, B16): Σ(pris × sol) / Σ sol per kvart. Faktisk produktion i
  stället för en typårsprofil (PVsyst), eftersom soliga dagar också är
  billiga dagar — en typårsprofil ser inte det och ger 5–15 procentenheter
  för hög capture rate.
* **Capture rate** — solpris / spotpris för samma period.
* **Negativa timmar** — tid med pris under 0 (en kvart = 0,25 h).

Allt bokförs i svensk lokaltid och i EUR/MWh.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import SWEDEN_TZ
from .common import (
    ALL_ZONES,
    CAL,
    QUARTER_S,
    available_zones,
    fmt_period_end,
    month_bounds,
    month_keys,
    quarter_prices,
    solar_quarters,
    spot_end_epoch,
)

FIRST_MONTH = "2022-01"
# Månader där zonens solproduktion är under denna andel av årets största
# månad får ingen capture rate — med nästan ingen sol blir kvoten brus.
LOW_SUN_SHARE = 0.25


def _r(v: Optional[float], d: int = 2) -> Optional[float]:
    return None if v is None else round(v, d)


def zone_monthly(zone: str, data_end: int) -> Dict[str, Dict[str, Any]]:
    prices = quarter_prices(zone)
    solar = solar_quarters(zone)
    acc: Dict[str, Dict[str, float]] = {}
    for q, price in prices.items():
        if q >= data_end:
            continue
        mk = CAL.month(q)
        if mk < FIRST_MONTH:
            continue
        a = acc.setdefault(mk, {"n": 0, "p": 0.0, "neg_q": 0, "sw": 0.0, "spw": 0.0,
                                "sp_n": 0, "sp_p": 0.0})
        a["n"] += 1
        a["p"] += price
        if price < 0:
            a["neg_q"] += 1
        s = solar.get(q)
        if s is not None:
            a["sw"] += s
            a["spw"] += s * price
            a["sp_n"] += 1
            a["sp_p"] += price
    out = {}
    for mk, a in sorted(acc.items()):
        base = a["p"] / a["n"]
        solar_price = a["spw"] / a["sw"] if a["sw"] > 0 else None
        # Capture rate mot baspriset för samma kvartar som har soldata, så att
        # en lucka i ENTSO-E inte blandar två olika perioder.
        base_solar_period = a["sp_p"] / a["sp_n"] if a["sp_n"] else None
        out[mk] = {
            "base": base,
            "solar_price": solar_price,
            "capture_rate": (solar_price / base_solar_period
                             if solar_price is not None and base_solar_period else None),
            "neg_hours": a["neg_q"] * 0.25,
            "solar_mwh": a["sw"] * 0.25,
            "solar_coverage": a["sp_n"] / a["n"],
            "quarters": a["n"],
        }
    # Tona bort vintermånader.
    by_year: Dict[str, float] = {}
    for mk, v in out.items():
        by_year[mk[:4]] = max(by_year.get(mk[:4], 0.0), v["solar_mwh"])
    for mk, v in out.items():
        peak = by_year.get(mk[:4]) or 0
        v["low_sun"] = peak > 0 and v["solar_mwh"] < LOW_SUN_SHARE * peak
    return out


def _year_bounds(year: str, data_end: int):
    start, _ = month_bounds(f"{year}-01")
    _, end = month_bounds(f"{year}-12")
    return start, min(end, data_end)


def build_marknad_data(data_end: Optional[int] = None) -> Dict[str, Any]:
    zones = available_zones()
    if data_end is None:
        # Gemensamt slut: senaste kvart som alla svenska zoner har pris för.
        ends = [spot_end_epoch(z) for z in zones if z.startswith("SE")]
        data_end = min(e for e in ends if e)
    last_month = CAL.month(data_end - 1)
    months = month_keys(FIRST_MONTH, last_month)
    this_year = last_month[:4]
    last_year = str(int(this_year) - 1)

    monthly: Dict[str, Dict[str, Any]] = {}
    yearly: Dict[str, Dict[str, Any]] = {}
    ytd_compare: Dict[str, Dict[str, Any]] = {}
    for z in zones:
        zm = zone_monthly(z, data_end)
        monthly[z] = {
            mk: {
                "base": _r(v["base"]),
                "solar_price": _r(v["solar_price"]),
                "capture_rate": None if v["low_sun"] or v["solar_coverage"] < 0.5 else _r(v["capture_rate"], 4),
                "neg_hours": round(v["neg_hours"], 2),
                "low_sun": v["low_sun"],
            }
            for mk, v in zm.items()
        }
        years = sorted({mk[:4] for mk in zm})
        yearly[z] = {y: _yearly_capture_period(z, *_year_bounds(y, data_end)) for y in years}
        # Samma period förra året (1 jan → samma datum), för rättvis jämförelse.
        ly_start, _ = month_bounds(f"{last_year}-01")
        ly_end = _same_date_last_year(data_end)
        ytd_compare[z] = _yearly_capture_period(z, ly_start, ly_end)

    spread = {}
    if "SE3" in monthly and "SE4" in monthly:
        p3, p4 = quarter_prices("SE3"), quarter_prices("SE4")
        acc: Dict[str, List[float]] = {}
        for q, v4 in p4.items():
            if q >= data_end or q not in p3:
                continue
            y = CAL.month(q)[:4]
            if y < FIRST_MONTH[:4]:
                continue
            a = acc.setdefault(y, [0, 0.0, 0])
            a[0] += 1
            a[1] += v4 - p3[q]
            a[2] += (v4 - p3[q]) > 0.01
        spread = {y: {"mean_eur": round(a[1] / a[0], 1), "share_se4_higher": round(a[2] / a[0], 3)}
                  for y, a in sorted(acc.items())}

    return {
        "data_end": CAL.day(data_end - 1),
        "data_end_label": fmt_period_end(data_end),
        "zones": zones,
        "main_zones": [z for z in ("SE3", "SE4") if z in zones],
        "months": months,
        "monthly": monthly,
        "yearly": yearly,
        "this_year": this_year,
        "ytd_compare": ytd_compare,
        "spread_se4_se3": spread,
        "low_sun_share": LOW_SUN_SHARE,
        "zone_order": list(ALL_ZONES),
    }


def _same_date_last_year(data_end: int) -> int:
    """data_end (lokal midnatt) flyttat ett år bakåt."""
    d = datetime.fromtimestamp(data_end, SWEDEN_TZ)
    day = min(d.day, 28) if d.month == 2 else d.day
    return int(datetime(d.year - 1, d.month, day, d.hour, tzinfo=SWEDEN_TZ).timestamp())


def _yearly_capture_period(zone: str, start: int, end: int) -> Dict[str, Any]:
    prices = quarter_prices(zone)
    solar = solar_quarters(zone)
    n = 0
    p = sw = spw = sp_p = 0.0
    sp_n = neg = 0
    for q in range(start, end, QUARTER_S):
        price = prices.get(q)
        if price is None:
            continue
        n += 1
        p += price
        neg += price < 0
        s = solar.get(q)
        if s is not None:
            sw += s
            spw += s * price
            sp_n += 1
            sp_p += price
    if not n:
        return {}
    base = p / n
    solar_price = spw / sw if sw else None
    base_sp = sp_p / sp_n if sp_n else None
    return {
        "base": _r(base),
        "solar_price": _r(solar_price),
        "capture_rate": _r(solar_price / base_sp, 4) if solar_price and base_sp else None,
        "neg_hours": round(neg * 0.25, 1),
        "solar_data_share": _r(sp_n / n, 3),
        "period_end": CAL.day(end - 1),
    }
