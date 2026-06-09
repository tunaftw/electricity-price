"""Capture- och cannibaliseringsanalys för rework-dashboarden.

Tre delar:

1. **Installerad kapacitet per elområde** — Energimyndighetens soldata är
   per län; mappas till dominant elområde (approximation, län kan korsa
   zongränser — duger för trendkorrelation). Vinddata är redan per
   elområde.
2. **Cannibalisering** — årlig capture ratio (sol syd) ställd mot
   installerad solkapacitet per zon.
3. **Orientering** — syd vs öst-väst vs tracker: capture-premie per år,
   EUR/kWp (capture × specifik TMY-produktion) samt normaliserade
   TMY-profilformer för utvalda månader.

Rena aggregeringsfunktioner tar radlistor så de kan enhetstestas utan
filberoenden.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .config import RESULTAT_DIR
from .park_config import PVSYST_PROFILE_DIR, PVSYST_PROFILE_MAP, SPECIFIC_YIELD_KWH_KWP

INSTALLED_DIR = RESULTAT_DIR / "marknadsdata" / "installerad"

# Länskod (två siffror) → dominant elområde. Approximation: några län
# (Gävleborg, Dalarna, Värmland m.fl.) korsar zongränser; vi använder
# den zon där merparten av befolkning/installationer ligger.
LAN_TO_ZONE: Dict[str, str] = {
    "25": "SE1",  # Norrbotten
    "24": "SE2",  # Västerbotten
    "23": "SE2",  # Jämtland
    "22": "SE2",  # Västernorrland
    "21": "SE2",  # Gävleborg
    "20": "SE3",  # Dalarna
    "17": "SE3",  # Värmland
    "19": "SE3",  # Västmanland
    "18": "SE3",  # Örebro
    "01": "SE3",  # Stockholm
    "03": "SE3",  # Uppsala
    "04": "SE3",  # Södermanland
    "05": "SE3",  # Östergötland
    "14": "SE3",  # Västra Götaland
    "06": "SE3",  # Jönköping
    "08": "SE3",  # Kalmar
    "09": "SE3",  # Gotland
    "07": "SE4",  # Kronoberg
    "10": "SE4",  # Blekinge
    "12": "SE4",  # Skåne
    "13": "SE4",  # Halland
}

# Solprofilnycklar i dashboard_v2-datat och deras visningsnamn.
ORIENTATION_PROFILES = {
    "sol_syd": "Syd",
    "sol_ov": "Öst-väst",
    "sol_tracker": "Tracker",
}

# Profilnyckel → profiltyp i park_config (för specifik produktion).
_PROFILE_TYPE = {"sol_syd": "south", "sol_ov": "ew", "sol_tracker": "tracker"}


def _to_float(value) -> float:
    """PxWeb använder '..' för saknade värden — tolka som 0."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def aggregate_installed_solar(rows: Iterable[dict]) -> Dict[str, List[dict]]:
    """Aggregera Energimyndighetens solrader (län-nivå) till zon/år.

    Args:
        rows: dicts med ``ar``, ``region`` ("NN Länsnamn") och
            ``installerad_effekt_(mw)``. Kommunrader (4-siffriga koder)
            och riket ignoreras — bara länsrader summeras.

    Returns:
        {zon: [{"year": int, "mw": float}, ...]} sorterat per år.
        Värdena är ackumulerad installerad effekt (stock, ej tillskott).
    """
    acc: Dict[tuple, float] = defaultdict(float)
    for row in rows:
        region = (row.get("region") or "").strip()
        code = region.split()[0] if region else ""
        if len(code) != 2 or code not in LAN_TO_ZONE:
            continue
        try:
            year = int(row.get("ar"))
        except (TypeError, ValueError):
            continue
        acc[(year, LAN_TO_ZONE[code])] += _to_float(
            row.get("installerad_effekt_(mw)")
        )

    out: Dict[str, List[dict]] = defaultdict(list)
    for (year, zone) in sorted(acc):
        out[zone].append({"year": year, "mw": round(acc[(year, zone)], 1)})
    return dict(out)


def aggregate_installed_wind(rows: Iterable[dict]) -> Dict[str, List[dict]]:
    """Aggregera vindrader (redan per elområde) till {zon: [{year, mw}]}."""
    acc: Dict[tuple, float] = {}
    for row in rows:
        zone = (row.get("zone") or "").strip()
        if not zone:
            continue
        try:
            year = int(row.get("year"))
        except (TypeError, ValueError):
            continue
        acc[(year, zone)] = _to_float(row.get("installed_mw"))

    out: Dict[str, List[dict]] = defaultdict(list)
    for (year, zone) in sorted(acc):
        out[zone].append({"year": year, "mw": round(acc[(year, zone)], 1)})
    return dict(out)


def load_installed_capacity() -> dict:
    """Läs Energimyndigheten-CSV:erna och returnera sol+vind per zon."""
    solar: Dict[str, List[dict]] = {}
    wind: Dict[str, List[dict]] = {}

    solar_path = INSTALLED_DIR / "solar_installations.csv"
    if solar_path.exists():
        with open(solar_path, "r", encoding="utf-8") as f:
            solar = aggregate_installed_solar(csv.DictReader(f))

    wind_path = INSTALLED_DIR / "wind_by_elarea.csv"
    if wind_path.exists():
        with open(wind_path, "r", encoding="utf-8") as f:
            wind = aggregate_installed_wind(csv.DictReader(f))

    return {"solar": solar, "wind": wind}


def build_cannibalization(market_data: dict) -> dict:
    """Cannibaliseringsvy: capture ratio (sol syd) vs installerad sol.

    Args:
        market_data: ``calculate_dashboard_v2_data()``-resultatets
            ``data``-nyckel ({zon: {profil: {yearly, monthly}}}).

    Returns:
        {"installed": {...}, "ratio_yearly": {zon: [...]},
        "ratio_monthly": {zon: [...]}}
    """
    installed = load_installed_capacity()

    ratio_yearly: Dict[str, List[dict]] = {}
    ratio_monthly: Dict[str, List[dict]] = {}
    for zone, profiles in market_data.items():
        syd = profiles.get("sol_syd") or {}
        yearly = []
        for rec in syd.get("yearly", []):
            yearly.append({
                "year": rec["year"],
                "ratio": rec.get("ratio"),
                "capture": rec.get("capture"),
                "baseload": rec.get("baseload"),
            })
        if yearly:
            ratio_yearly[zone] = yearly

        monthly = []
        for rec in syd.get("monthly", []):
            monthly.append({
                "month": f"{rec['year']}-{rec['month']:02d}",
                "ratio": rec.get("ratio"),
            })
        if monthly:
            ratio_monthly[zone] = monthly

    return {
        "installed": installed,
        "ratio_yearly": ratio_yearly,
        "ratio_monthly": ratio_monthly,
    }


def calculate_orientation_yearly(market_data: dict) -> dict:
    """Orienteringsjämförelse per zon och år ur dashboard_v2-datat.

    Returns:
        {"yearly": {zon: {profilnyckel: [{year, capture, ratio}]}},
         "premium_vs_syd": {zon: [{year, ov_pct, tracker_pct}]},
         "eur_per_kwp": {zon: [{year, syd, ov, tracker}]}}
    """
    yearly: Dict[str, Dict[str, List[dict]]] = {}
    premium: Dict[str, List[dict]] = {}
    eur_kwp: Dict[str, List[dict]] = {}

    for zone, profiles in market_data.items():
        zone_yearly: Dict[str, List[dict]] = {}
        for key in ORIENTATION_PROFILES:
            prof = profiles.get(key) or {}
            recs = [
                {
                    "year": r["year"],
                    "capture": r.get("capture"),
                    "ratio": r.get("ratio"),
                }
                for r in prof.get("yearly", [])
            ]
            if recs:
                zone_yearly[key] = recs
        if not zone_yearly:
            continue
        yearly[zone] = zone_yearly

        # Premie vs syd + EUR/kWp per år
        syd_by_year = {
            r["year"]: r["capture"]
            for r in zone_yearly.get("sol_syd", [])
            if r.get("capture")
        }
        prem_rows: List[dict] = []
        ekwp_rows: List[dict] = []
        years = sorted(syd_by_year)
        for year in years:
            syd_cap = syd_by_year[year]
            row_p: dict = {"year": year}
            row_e: dict = {"year": year}
            row_e["syd"] = _eur_per_kwp("sol_syd", syd_cap)
            for key, out_name in (("sol_ov", "ov"), ("sol_tracker", "tracker")):
                cap = next(
                    (
                        r["capture"]
                        for r in zone_yearly.get(key, [])
                        if r["year"] == year and r.get("capture")
                    ),
                    None,
                )
                row_p[f"{out_name}_pct"] = (
                    round((cap / syd_cap - 1.0) * 100.0, 1)
                    if cap and syd_cap else None
                )
                row_e[out_name] = _eur_per_kwp(key, cap)
            prem_rows.append(row_p)
            ekwp_rows.append(row_e)
        premium[zone] = prem_rows
        eur_kwp[zone] = ekwp_rows

    return {
        "yearly": yearly,
        "premium_vs_syd": premium,
        "eur_per_kwp": eur_kwp,
    }


def _eur_per_kwp(profile_key: str, capture: Optional[float]) -> Optional[float]:
    """EUR per installerad kWp och år = capture × specifik produktion."""
    if capture is None:
        return None
    ptype = _PROFILE_TYPE.get(profile_key)
    sy = SPECIFIC_YIELD_KWH_KWP.get(ptype)
    if sy is None:
        return None
    # capture [EUR/MWh] × yield [kWh/kWp] / 1000 = EUR/kWp
    return round(capture * sy / 1000.0, 1)


def load_profile_shapes(months: Optional[List[int]] = None) -> dict:
    """Normaliserade TMY-produktionsprofiler per timme för utvalda månader.

    Läser PVsyst-CSV:erna (month, day, hour, power_mw, normerade till
    1 MW) och returnerar snittprofil per timme, normaliserad till
    max=1.0 inom varje (profil, månad).

    Returns:
        {"6": {"sol_syd": [24 floats], ...}, "12": {...}}
    """
    if months is None:
        months = [6, 12]

    shapes: Dict[str, Dict[str, List[float]]] = {}
    for key, ptype in _PROFILE_TYPE.items():
        filename = PVSYST_PROFILE_MAP.get(ptype)
        if not filename:
            continue
        path = PVSYST_PROFILE_DIR / filename
        if not path.exists():
            continue
        # acc[month][hour] = [sum, n]
        acc: Dict[int, List[List[float]]] = {
            m: [[0.0, 0] for _ in range(24)] for m in months
        }
        with open(path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                month = int(row["month"])
                if month not in acc:
                    continue
                hour = int(row["hour"])
                acc[month][hour][0] += float(row["power_mw"])
                acc[month][hour][1] += 1

        for month in months:
            cells = acc[month]
            means = [c[0] / c[1] if c[1] > 0 else 0.0 for c in cells]
            peak = max(means) if means else 0.0
            normalized = [
                round(v / peak, 4) if peak > 0 else 0.0 for v in means
            ]
            shapes.setdefault(str(month), {})[key] = normalized

    return shapes


def build_orientation(market_data: dict) -> dict:
    """Bygg hela orienteringssektionen."""
    result = calculate_orientation_yearly(market_data)
    result["labels"] = ORIENTATION_PROFILES
    result["specific_yield_kwh_kwp"] = {
        key: SPECIFIC_YIELD_KWH_KWP[ptype]
        for key, ptype in _PROFILE_TYPE.items()
        if ptype in SPECIFIC_YIELD_KWH_KWP
    }
    result["profile_shapes"] = load_profile_shapes()
    return result
