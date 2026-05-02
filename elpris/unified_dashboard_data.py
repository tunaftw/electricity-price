"""Unified dashboard data — Phase 1 backend.

Aggregerar data från befintliga moduler (dashboard_v2_data,
operations_dashboard_data, performance_report_data) till en enda
JSON-serialiserbar struktur som de fyra unified-flikarna
(CAPTURE / BESS / FUTURES / ASSETS) konsumerar.

Library-modul: ingen CLI / ingen `__main__`-block.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .config import PARK_CAPACITY_KWP, PARK_ZONES
from .dashboard_v2_data import calculate_dashboard_v2_data
from .operations_dashboard_data import (
    calculate_negative_price_exposure,
    calculate_tracker_gain,
)
from .park_config import get_park_metadata
from .performance_report_data import generate_report

# 8 solparker som ingår i flottan
PARK_KEYS: List[str] = [
    "horby", "fjallskar", "agerum", "hova",
    "skakelbacken", "stenstorp", "tangen", "bjorke",
]


def _empty_market() -> Dict[str, Any]:
    """Tom market-struktur när dashboard_v2_data inte kan beräknas
    (t.ex. på grund av datafel eller saknade källor).
    """
    return {
        "zones": [],
        "profiles": {},
        "colors": {},
        "data": {},
    }


def _build_market_section() -> Dict[str, Any]:
    """Hämta marknadsdata från dashboard_v2_data.

    Returnerar dict med zones, profiles, colors, data, validation,
    heatmap, operations, forward (om tillgängligt) m.fl. Vid fel i
    underliggande beräkning returneras en tom struktur så att unified
    builder fortfarande är användbar.
    """
    try:
        return calculate_dashboard_v2_data()
    except Exception as exc:
        # Logga men låt bygget fortsätta — bättre med partial data än crash.
        print(f"[unified_dashboard] market beräkning misslyckades: {exc}")
        return _empty_market()


def _build_meta_section(market: Dict[str, Any]) -> Dict[str, Any]:
    """Plocka ut zones/profiles/colors från market för frontend-rendering."""
    return {
        "zones": market.get("zones", []),
        "profiles": market.get("profiles", {}),
        "colors": market.get("colors", {}),
    }


def _park_display_name(park_key: str) -> str:
    """Hämta visningsnamn för en park, fallback till capitalize()."""
    meta = get_park_metadata(park_key)
    if meta and meta.get("display_name"):
        return meta["display_name"]
    return park_key.capitalize()


def _latest_complete_month(today: Optional[date] = None) -> tuple:
    """Returnera (year, month) för senaste fullständiga månad."""
    if today is None:
        today = date.today()
    if today.month == 1:
        return (today.year - 1, 12)
    return (today.year, today.month - 1)


def _walk_months_back(num_months: int, today: Optional[date] = None) -> List[tuple]:
    """Returnera lista [(year, month), ...] med num_months bakåt från
    senaste fullständiga månad (äldst → nyast)."""
    year, month = _latest_complete_month(today)
    result: List[tuple] = []
    for _ in range(num_months):
        result.append((year, month))
        if month == 1:
            year -= 1
            month = 12
        else:
            month -= 1
    return list(reversed(result))


def _safe_round(value, decimals: int = 2):
    """Round if numeric, else None."""
    if value is None:
        return None
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None


def _build_park_months(park_key: str, num_months: int = 13) -> List[Dict[str, Any]]:
    """Bygg lista med månadsvisa KPI:er för en park.

    Går bakåt från senaste fullständiga månad. Hoppar över månader där
    generate_report() kraschar (saknad data är normalt).
    """
    capacity_kwp = PARK_CAPACITY_KWP.get(park_key, 0)
    capacity_mw = capacity_kwp / 1000.0

    months_out: List[Dict[str, Any]] = []
    for year, month in _walk_months_back(num_months):
        try:
            report = generate_report(park_key, year, month)
        except Exception:
            # Saknad data eller okänd park — hoppa över tyst
            continue

        actual = report.actual_energy_mwh or 0.0
        budget = report.budget_energy_mwh or 0.0
        vs_budget = None
        if budget > 0:
            vs_budget = round((actual / budget - 1.0) * 100.0, 1)

        months_out.append({
            "year": year,
            "month": month,
            "energy_mwh": _safe_round(actual, 2),
            "budget_mwh": _safe_round(budget, 2),
            "vs_budget_pct": vs_budget,
            "yield_kwh_kwp": _safe_round(report.yield_kwh_kwp, 1),
            "pr_pct": _safe_round(report.performance_ratio_pct, 2),
        })

    return months_out


def _safe_negative_price_exposure() -> Dict[str, List[Dict[str, Any]]]:
    """Hämta negativa pris-exponering, fallback till tom dict vid fel."""
    try:
        return calculate_negative_price_exposure()
    except Exception as exc:
        print(f"[unified_dashboard] negative_price beräkning misslyckades: {exc}")
        return {}


def _merge_operations_into_months(
    parks: Dict[str, Dict[str, Any]],
    neg_exposure: Dict[str, List[Dict[str, Any]]],
) -> None:
    """Mutera parks: lägg till neg_price_hours/neg_price_volume_mwh per månad."""
    for park_key, park in parks.items():
        # Bygg lookup (year, month) -> exposure-record
        park_neg = neg_exposure.get(park_key, [])
        neg_lookup: Dict[tuple, Dict[str, Any]] = {
            (rec["year"], rec["month"]): rec for rec in park_neg
        }
        for m in park["months"]:
            rec = neg_lookup.get((m["year"], m["month"]))
            if rec is None:
                m["neg_price_hours"] = 0.0
                m["neg_price_volume_mwh"] = 0.0
            else:
                m["neg_price_hours"] = rec.get("neg_hours", 0.0)
                m["neg_price_volume_mwh"] = rec.get("neg_volume_mwh", 0.0)


def _build_assets_section(num_months: int = 13) -> Dict[str, Any]:
    """Bygg assets-sektionen med per-park månadsvisa KPI:er."""
    parks: Dict[str, Dict[str, Any]] = {}
    for park_key in PARK_KEYS:
        capacity_kwp = PARK_CAPACITY_KWP.get(park_key, 0)
        parks[park_key] = {
            "name": _park_display_name(park_key),
            "zone": PARK_ZONES.get(park_key, ""),
            "capacity_mwp": round(capacity_kwp / 1000.0, 3),
            "months": _build_park_months(park_key, num_months=num_months),
        }

    # Berika med operations-data (negativa pris-exponering)
    neg_exposure = _safe_negative_price_exposure()
    _merge_operations_into_months(parks, neg_exposure)

    return {
        "parks": parks,
        "fleet": _build_fleet_overview(parks),
        "tracker_gain": _build_tracker_gain(),
    }


def _build_tracker_gain() -> Dict[str, Any]:
    """Returnera tracker-gain summary (Hova vs fixed-tilt SE3-parker).

    calculate_tracker_gain() returnerar en list[dict] med
    {year, month, sy_hova, sy_fixed_avg, gain_pct}. Vi paketerar den i
    en dict för att kunna utöka senare utan att ändra contract.
    """
    try:
        monthly = calculate_tracker_gain()
    except Exception as exc:
        # TODO: gracefully degrade om underliggande data saknas
        print(f"[unified_dashboard] tracker_gain beräkning misslyckades: {exc}")
        monthly = []
    return {"monthly": monthly}


def _build_fleet_overview(parks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Räkna ut flotta-KPI:er för senaste månad där minst en park har data.

    Summerar energi/budget/kapacitet över alla parker som rapporterat
    den månaden.
    """
    # Hitta senaste (year, month) som finns i någon park
    candidates: set = set()
    for park in parks.values():
        for m in park["months"]:
            candidates.add((m["year"], m["month"]))

    if not candidates:
        return {
            "latest_month": None,
            "park_count": 0,
            "total_capacity_mwp": 0.0,
            "total_energy_mwh": 0.0,
            "vs_budget_pct": None,
        }

    latest = max(candidates)
    year, month = latest

    park_count = 0
    total_capacity = 0.0
    total_energy = 0.0
    total_budget = 0.0
    for park_key, park in parks.items():
        match = next(
            (m for m in park["months"]
             if m["year"] == year and m["month"] == month),
            None,
        )
        if match is None:
            continue
        park_count += 1
        total_capacity += park.get("capacity_mwp", 0.0) or 0.0
        total_energy += match.get("energy_mwh") or 0.0
        total_budget += match.get("budget_mwh") or 0.0

    vs_budget = None
    if total_budget > 0:
        vs_budget = round((total_energy / total_budget - 1.0) * 100.0, 1)

    return {
        "latest_month": {"year": year, "month": month},
        "park_count": park_count,
        "total_capacity_mwp": round(total_capacity, 3),
        "total_energy_mwh": round(total_energy, 2),
        "vs_budget_pct": vs_budget,
    }


def build_unified_data() -> Dict[str, Any]:
    """Bygger den samlade datastrukturen för unified dashboard.

    Returnerar en JSON-serialiserbar dict med top-level keys:
        - generated: ISO-timestamp för när data byggdes
        - market: marknadsdata (zoner, capture-priser, BESS, futures)
        - assets: per-park KPI:er + flotta-översikt
        - meta: zoner, profiler, färger (för frontend-rendering)
    """
    market = _build_market_section()
    assets = _build_assets_section()
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "market": market,
        "assets": assets,
        "meta": _build_meta_section(market),
    }
