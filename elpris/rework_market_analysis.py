"""Marknadsanalys för rework-dashboarden.

Beräknar strukturell prisstatistik direkt från quarterly-spot-CSV:erna
(en läsning per zon):

* Årsstatistik: snittpris, volatilitet (std), negativa timmar,
  intradagsspread (max−min av timmedel).
* Månadsstatistik: snittpris, negativa timmar, genomsnittlig daglig
  intradagsspread (flexvärdes-proxy).
* Duck curve: snittpris per timme (lokal svensk tid) per år — visar
  hur middagsgropen utvecklats.
* Månad × timme-profil per år (lokal tid) — driver både heatmap och
  pris-överlägg i orienteringsanalysen.

Alla aggregeringsfunktioner är rena (tar radlistor/iteratorer) så att
de kan enhetstestas utan filberoenden.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, Iterator, List, Optional
from zoneinfo import ZoneInfo

from .config import QUARTERLY_DIR, ZONES

SWEDEN_TZ = ZoneInfo("Europe/Stockholm")

# Ett "komplett" år kräver minst ~360 dagars kvartersdata.
_COMPLETE_YEAR_QUARTERS = 360 * 96

# Zonspreadar vi visar (köpdyr zon minus säljbillig zon).
SPREAD_PAIRS = [("SE4", "SE3"), ("SE3", "SE1"), ("SE2", "SE1")]


def iter_quarter_rows(zone: str) -> Iterator[dict]:
    """Yield:a rader ur quarterly-CSV:erna för en zon (alla år, sorterat)."""
    zone_dir = QUARTERLY_DIR / zone
    if not zone_dir.exists():
        return
    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                yield row


def analyze_zone_quarters(rows: Iterable[dict]) -> dict:
    """Aggregera kvartersrader till års-/månads-/timstatistik.

    Args:
        rows: dicts med minst ``time_start`` (ISO med offset) och
            ``EUR_per_kWh``.

    Returns:
        dict med nycklarna ``yearly``, ``monthly``, ``duck_by_year``,
        ``month_hour_by_year`` (alla JSON-serialiserbara).
    """
    y_acc: Dict[int, dict] = defaultdict(
        lambda: {"n": 0, "sum": 0.0, "sumsq": 0.0, "neg": 0}
    )
    m_acc: Dict[str, dict] = defaultdict(
        lambda: {"n": 0, "sum": 0.0, "neg": 0}
    )
    # duck[year][hour] -> [sum, n]
    duck: Dict[int, List[List[float]]] = defaultdict(
        lambda: [[0.0, 0] for _ in range(24)]
    )
    # mh[year][month-1][hour] -> [sum, n]
    mh: Dict[int, List[List[List[float]]]] = defaultdict(
        lambda: [[[0.0, 0] for _ in range(24)] for _ in range(12)]
    )
    # Daglig timprofil för intradagsspread: day -> hour -> [sum, n]
    day_hours: Dict[str, Dict[int, List[float]]] = defaultdict(
        lambda: defaultdict(lambda: [0.0, 0])
    )
    last_ts: Optional[str] = None

    for row in rows:
        ts = datetime.fromisoformat(row["time_start"])
        local = ts.astimezone(SWEDEN_TZ)
        price = float(row["EUR_per_kWh"]) * 1000.0  # EUR/MWh

        year = local.year
        month_key = f"{year:04d}-{local.month:02d}"
        hour = local.hour

        ya = y_acc[year]
        ya["n"] += 1
        ya["sum"] += price
        ya["sumsq"] += price * price
        if price < 0:
            ya["neg"] += 1

        ma = m_acc[month_key]
        ma["n"] += 1
        ma["sum"] += price
        if price < 0:
            ma["neg"] += 1

        cell = duck[year][hour]
        cell[0] += price
        cell[1] += 1

        mcell = mh[year][local.month - 1][hour]
        mcell[0] += price
        mcell[1] += 1

        dh = day_hours[local.strftime("%Y-%m-%d")][hour]
        dh[0] += price
        dh[1] += 1

        raw_ts = row["time_start"]
        if last_ts is None or raw_ts > last_ts:
            last_ts = raw_ts

    # Daglig spread (max−min av timmedel) -> månadsgenomsnitt
    spread_acc: Dict[str, List[float]] = defaultdict(list)
    for day_key, hours in day_hours.items():
        means = [s / n for s, n in hours.values() if n > 0]
        if len(means) >= 20:  # kräver nästan hel dag för meningsfull spread
            spread_acc[day_key[:7]].append(max(means) - min(means))

    yearly = []
    for year in sorted(y_acc):
        a = y_acc[year]
        n = a["n"]
        avg = a["sum"] / n
        var = max(a["sumsq"] / n - avg * avg, 0.0)
        hour_means = [
            c[0] / c[1] for c in duck[year] if c[1] > 0
        ]
        yearly.append({
            "year": year,
            "avg": round(avg, 2),
            "std": round(math.sqrt(var), 2),
            "neg_hours": round(a["neg"] * 0.25, 1),
            "intraday_spread": (
                round(max(hour_means) - min(hour_means), 2)
                if len(hour_means) >= 20 else None
            ),
            "n_quarters": n,
            "complete": n >= _COMPLETE_YEAR_QUARTERS,
        })

    monthly = []
    for month_key in sorted(m_acc):
        a = m_acc[month_key]
        spreads = spread_acc.get(month_key, [])
        monthly.append({
            "month": month_key,
            "avg": round(a["sum"] / a["n"], 2),
            "neg_hours": round(a["neg"] * 0.25, 1),
            "avg_daily_spread": (
                round(sum(spreads) / len(spreads), 2) if spreads else None
            ),
        })

    duck_by_year = {}
    for year, cells in duck.items():
        duck_by_year[str(year)] = [
            round(c[0] / c[1], 2) if c[1] > 0 else None for c in cells
        ]

    month_hour_by_year = {}
    for year, months in mh.items():
        month_hour_by_year[str(year)] = [
            [round(c[0] / c[1], 2) if c[1] > 0 else None for c in hrs]
            for hrs in months
        ]

    return {
        "yearly": yearly,
        "monthly": monthly,
        "duck_by_year": duck_by_year,
        "month_hour_by_year": month_hour_by_year,
        "last_ts": last_ts,
    }


def calculate_zone_spreads(
    monthly_by_zone: Dict[str, List[dict]],
    pairs: Optional[List[tuple]] = None,
) -> List[dict]:
    """Beräkna månadsvisa zonspreadar (avg_hi − avg_lo) ur månadsstatistik.

    Args:
        monthly_by_zone: {zon: [{"month": "YYYY-MM", "avg": float}, ...]}
        pairs: lista av (hi, lo)-zonpar; default ``SPREAD_PAIRS``.

    Returns:
        [{"month": "YYYY-MM", "SE4-SE3": float|None, ...}, ...] sorterat.
    """
    if pairs is None:
        pairs = SPREAD_PAIRS

    lookup: Dict[str, Dict[str, float]] = {}
    for zone, months in monthly_by_zone.items():
        lookup[zone] = {m["month"]: m["avg"] for m in months}

    all_months = sorted({
        m for zone_months in lookup.values() for m in zone_months
    })

    out = []
    for month in all_months:
        rec: dict = {"month": month}
        for hi, lo in pairs:
            hi_avg = lookup.get(hi, {}).get(month)
            lo_avg = lookup.get(lo, {}).get(month)
            key = f"{hi}-{lo}"
            rec[key] = (
                round(hi_avg - lo_avg, 2)
                if hi_avg is not None and lo_avg is not None else None
            )
        out.append(rec)
    return out


def build_market_analysis(zones: Optional[List[str]] = None) -> dict:
    """Bygg hela marknadsanalys-sektionen (läser quarterly-CSV:erna).

    Returns:
        {"zones": {zon: {yearly, monthly, duck_by_year,
        month_hour_by_year}}, "spreads_monthly": [...]}
    """
    if zones is None:
        zones = ZONES

    per_zone: Dict[str, dict] = {}
    for zone in zones:
        print(f"  Marknadsanalys {zone}...")
        result = analyze_zone_quarters(iter_quarter_rows(zone))
        if result["yearly"]:
            per_zone[zone] = result

    spreads = calculate_zone_spreads(
        {z: d["monthly"] for z, d in per_zone.items()}
    )

    return {"zones": per_zone, "spreads_monthly": spreads}
