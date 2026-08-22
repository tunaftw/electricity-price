"""Unified dashboard data — Phase 1 backend.

Aggregerar data från befintliga moduler (dashboard_v2_data,
operations_dashboard_data, performance_report_data) till en enda
JSON-serialiserbar struktur som de fyra unified-flikarna
(CAPTURE / BESS / FUTURES / ASSETS) konsumerar.

Library-modul: ingen CLI / ingen `__main__`-block.
"""

from __future__ import annotations

import calendar
import sys
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .config import PARK_CAPACITY_KWP, PARK_ZONES
from .dashboard_v2_data import calculate_dashboard_v2_data
from .operations_dashboard_data import (
    calculate_negative_price_exposure,
    calculate_tracker_gain,
    load_park_15min,
)
from .park_config import get_park_metadata
from .performance_report_data import generate_report

# 8 solparker som ingår i flottan
PARK_KEYS: List[str] = [
    "horby", "fjallskar", "agerum", "hova",
    "skakelbacken", "stenstorp", "tangen", "bjorke",
]

# Antal månader vi visar i assets-vyn (12 stängda + pågående månad).
# Pågående månad pro-ratas mot dagar-hittills (se `_partial_month_factor`)
# så vs_budget jämför MTD-actual mot MTD-budget i stället för full-month-budget.
DEFAULT_HISTORY_MONTHS = 13

# Antal månader bakåt vi inkluderar daglig data för (drill-down behöver det
# bara för senaste månaderna; håller JSON-storleken nere).
DAILY_HISTORY_MONTHS = 3


def _build_market_section() -> Dict[str, Any]:
    """Hämta marknadsdata från dashboard_v2_data.

    Returnerar dict med zones, profiles, colors, data, validation,
    heatmap, operations, forward (om tillgängligt) m.fl.
    """
    return calculate_dashboard_v2_data()


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


def _latest_data_month(today: Optional[date] = None) -> tuple[int, int]:
    """Returnera (year, month) för senaste månad vi vill visa.

    Inkluderar pågående månad (MTD). Stängda månader visas i sin helhet,
    pågående månad pro-ratas i `_build_park_months` så jämförelser mot
    actual blir rättvisa. Om datat saknas helt för pågående månad
    skippas raden — `_build_park_months` upptäcker det via tomt
    `report.daily`.
    """
    if today is None:
        today = date.today()
    return (today.year, today.month)


def _walk_months_back(num_months: int, today: Optional[date] = None) -> List[tuple[int, int]]:
    """Returnera lista [(year, month), ...] med num_months bakåt från
    senaste månaden (inkl. pågående). Sorterad äldst → nyast."""
    year, month = _latest_data_month(today)
    result: List[tuple[int, int]] = []
    for _ in range(num_months):
        result.append((year, month))
        if month == 1:
            year -= 1
            month = 12
        else:
            month -= 1
    return list(reversed(result))


def _partial_month_factor(
    report,
    year: int,
    month: int,
    today: Optional[date] = None,
) -> float:
    """Pro-rata-faktor för pågående månad (1.0 för stängda månader).

    Faktorn = `len(report.daily) / antal_dagar_i_månaden`. Används för
    att skala budget-värden så jämförelse mot pågående månads MTD-actual
    blir rättvis (t.ex. ~0 % i stället för ~-70 % den 9 maj). För stängda
    månader (year/month < dagens) returneras 1.0 — ingen skalning.
    Returnerar 0.0 om det är pågående månad utan dagliga data ännu.
    """
    if today is None:
        today = date.today()
    if (year, month) < (today.year, today.month):
        return 1.0
    if (year, month) > (today.year, today.month):
        return 0.0
    days_with_data = len(report.daily) if report.daily else 0
    days_in_month = calendar.monthrange(year, month)[1]
    if days_with_data <= 0 or days_in_month <= 0:
        return 0.0
    return min(days_with_data / days_in_month, 1.0)


def _safe_round(value, decimals: int = 2):
    """Round if numeric, else None."""
    if value is None:
        return None
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None


def _daily_records_from_report(report) -> List[Dict[str, Any]]:
    """Konvertera report.daily (List[DailyData]) till JSON-vänliga records."""
    out: List[Dict[str, Any]] = []
    for d in (report.daily or []):
        out.append({
            "day": d.day,
            "date": d.date_str,
            "weekday": d.weekday,
            "energy_mwh": _safe_round(d.actual_energy_mwh, 3),
            "irradiation_kwh_m2": _safe_round(d.actual_irradiation_kwh_m2, 2),
            "yield_kwh_kwp": _safe_round(d.norm_yield_kwh_kwp, 2),
            "expected_mwh": _safe_round(d.expected_gen_mwh, 3),
            "pr_pct": _safe_round(d.performance_ratio_pct, 2),
            "pi_pct": _safe_round(d.performance_index_pct, 2),
            "efficiency_pct": _safe_round(d.efficiency_pct, 2),
            "module_temp_c": _safe_round(d.avg_module_temp_c, 1),
        })
    return out


def _availability_for_month(park_key: str, year: int, month: int) -> Optional[float]:
    """Irradiance- (eller power-)viktad availability för en park-månad.

    Läser 15-min Bazefield-data och vägar availability-värdena med
    irradiance om finns, annars effective_power. Returnerar None om
    ingen availability-data finns för månaden.
    """
    records = load_park_15min(park_key)
    if not records:
        return None
    total_w = 0.0
    total_a = 0.0
    for r in records:
        if r["year"] != year or r["month"] != month:
            continue
        avail = r.get("availability")
        if avail is None:
            continue
        w = r.get("irradiance_poa") or r.get("effective_power_mw") or 0.0
        if w <= 0:
            continue
        total_w += w
        total_a += avail * w
    return round(total_a / total_w, 2) if total_w > 0 else None


def _losses_dict(losses) -> Optional[Dict[str, float]]:
    """Konvertera LossCascade till JSON-vänlig dict."""
    if losses is None:
        return None
    return {
        "budget_mwh": _safe_round(losses.budget_energy_mwh, 2),
        "actual_mwh": _safe_round(losses.actual_energy_mwh, 2),
        "residual_mwh": _safe_round(losses.residual_loss_mwh, 2),
        "irradiance_shortfall_mwh": _safe_round(losses.irradiance_shortfall_loss_mwh, 2),
        "availability_mwh": _safe_round(losses.availability_loss_mwh, 2),
        "temperature_mwh": _safe_round(losses.temperature_loss_mwh, 2),
        "clipping_mwh": _safe_round(losses.clipping_loss_mwh, 2),
    }


def _losses_dict_prorated(
    losses,
    factor: float,
    actual_energy_mwh: float,
    actual_irr_kwh_m2: Optional[float],
    full_budget_irr_kwh_m2: Optional[float],
) -> Optional[Dict[str, float]]:
    """Som `_losses_dict` men skala budget-baserade fält för pågående månad.

    Speglar `performance_report_data._calculate_loss_cascade` med
    pro-ratade budget-termer:

      irr_shortfall = budget_e * (1 - actual_irr / budget_irr)
      avail/temp/clipping = (oförändrade — beräknas per intervall, redan MTD)
      residual      = budget_e − actual − irr_shortfall − avail − temp − clipping

    Måste hållas i synk med `_calculate_loss_cascade` om den ändras.
    """
    if losses is None:
        return None
    if factor >= 1.0 - 1e-9:
        return _losses_dict(losses)

    prorated_budget_e = (losses.budget_energy_mwh or 0.0) * factor
    prorated_budget_irr = (full_budget_irr_kwh_m2 or 0.0) * factor

    if actual_irr_kwh_m2 is not None and prorated_budget_irr > 0:
        irr_ratio = actual_irr_kwh_m2 / prorated_budget_irr
        irr_shortfall = prorated_budget_e * (1.0 - irr_ratio)
    else:
        irr_shortfall = 0.0

    avail_loss = losses.availability_loss_mwh or 0.0
    temp_loss = losses.temperature_loss_mwh or 0.0
    clipping_loss = losses.clipping_loss_mwh or 0.0
    residual = (
        prorated_budget_e - actual_energy_mwh - irr_shortfall
        - avail_loss - temp_loss - clipping_loss
    )

    return {
        "budget_mwh": _safe_round(prorated_budget_e, 2),
        "actual_mwh": _safe_round(actual_energy_mwh, 2),
        "residual_mwh": _safe_round(residual, 2),
        "irradiance_shortfall_mwh": _safe_round(irr_shortfall, 2),
        "availability_mwh": _safe_round(avail_loss, 2),
        "temperature_mwh": _safe_round(temp_loss, 2),
        "clipping_mwh": _safe_round(clipping_loss, 2),
    }


def _last_data_ts(park_key: str) -> Optional[str]:
    """Senaste 15-min timestamp i Bazefield-CSV (ISO 8601)."""
    records = load_park_15min(park_key)
    if not records:
        return None
    last = max(r["timestamp_utc"] for r in records)
    return last.isoformat()


def _park_facts(park_key: str) -> Optional[Dict[str, Any]]:
    """Subset av park-metadata för 'About this park'-panel."""
    meta = get_park_metadata(park_key)
    if not meta:
        return None
    standard_pr = meta.get("standard_pr") or 0
    return {
        "location": meta.get("location"),
        "commissioning_date": meta.get("commissioning_date"),
        "module_type": meta.get("module_type"),
        "module_wp": meta.get("module_wp"),
        "num_modules": meta.get("num_modules"),
        "inverter_model": meta.get("inverter_model"),
        "inverter_manufacturer": meta.get("inverter_manufacturer"),
        "num_inverters": meta.get("num_inverters"),
        "tilt_angle": meta.get("tilt_angle"),
        "azimuth": meta.get("azimuth"),
        "tracking": meta.get("tracking"),
        "tracking_type": meta.get("tracking_type"),
        "ac_capacity_mwac": meta.get("ac_capacity_mwac"),
        "grid_limit_mwac": meta.get("grid_limit_mwac"),
        "transformer_capacity_kva": meta.get("transformer_capacity_kva"),
        "transformer_count": meta.get("transformer_count"),
        "expected_pr_pct": round(standard_pr * 100, 1) if standard_pr else None,
        "expected_annual_yield_kwh_kwp": meta.get("expected_annual_yield_kwh_kwp"),
        "profile_type": meta.get("profile_type"),
    }


def _build_park_months(
    park_key: str,
    num_months: int = DEFAULT_HISTORY_MONTHS,
    daily_months: int = DAILY_HISTORY_MONTHS,
) -> tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """Bygg lista med månadsvisa KPI:er för en park samt daglig data per månad.

    Går bakåt från senaste fullständiga månad. Hoppar över månader där
    generate_report() kraschar (saknad data är normalt).

    Returnerar (months_list, daily_by_month_dict). daily_by_month_dict
    har formatet {"YYYY-MM": [daily_record, ...]} och inkluderar bara
    de senaste `daily_months` månaderna för att begränsa JSON-storleken.
    """
    months_out: List[Dict[str, Any]] = []
    walked = _walk_months_back(num_months)
    # Sista `daily_months` månaderna i listan (= senaste; walked är äldst→nyast)
    daily_keys: set = set()
    for ym in walked[-daily_months:]:
        daily_keys.add(ym)

    daily_by_month: Dict[str, List[Dict[str, Any]]] = {}

    for year, month in walked:
        try:
            report = generate_report(park_key, year, month)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            print(
                f"[unified_dashboard] {park_key} {year}-{month}: {exc}",
                file=sys.stderr,
            )
            continue

        # Pro-rata-faktor för pågående månad (1.0 för stängda).
        factor = _partial_month_factor(report, year, month)
        is_partial = factor < 1.0 - 1e-9

        # Skippa pågående månad om data saknas helt — undvik tomma rader
        # som kan dyka upp första dagen efter månadsskifte innan nattens
        # Bazefield-sync hunnit.
        if is_partial and factor <= 0.0:
            continue

        actual = report.actual_energy_mwh or 0.0
        full_budget = report.budget_energy_mwh or 0.0
        budget = full_budget * factor  # pro-ratad för pågående månad
        vs_budget = None
        if budget > 0:
            vs_budget = round((actual / budget - 1.0) * 100.0, 1)

        actual_irr = report.actual_irradiation_kwh_m2  # may be None
        full_budget_irr = report.budget_irradiation_kwh_m2 or 0.0
        budget_irr = full_budget_irr * factor  # pro-ratad för pågående månad
        vs_budget_irr = None
        if budget_irr > 0 and actual_irr is not None:
            vs_budget_irr = round((actual_irr / budget_irr - 1.0) * 100.0, 1)

        months_out.append({
            "year": year,
            "month": month,
            "is_partial": is_partial,
            "energy_mwh": _safe_round(actual, 2),
            "budget_mwh": _safe_round(budget, 2),
            "vs_budget_pct": vs_budget,
            "yield_kwh_kwp": _safe_round(report.yield_kwh_kwp, 1),
            "pr_pct": _safe_round(report.performance_ratio_pct, 2),
            "actual_pr_pct": _safe_round(report.performance_ratio_pct, 2),
            "budget_pr_pct": _safe_round(report.budget_pr_pct, 2),
            "availability_pct": _availability_for_month(park_key, year, month),
            "actual_irr_kwh_m2": _safe_round(actual_irr, 1),
            "budget_irr_kwh_m2": _safe_round(budget_irr, 1),
            "vs_budget_irr_pct": vs_budget_irr,
            "losses": _losses_dict_prorated(
                report.losses,
                factor,
                actual,
                actual_irr,
                full_budget_irr,
            ),
        })

        if (year, month) in daily_keys:
            daily_by_month[f"{year}-{month:02d}"] = _daily_records_from_report(report)

    return months_out, daily_by_month


def _safe_negative_price_exposure() -> Dict[str, List[Dict[str, Any]]]:
    """Hämta negativa pris-exponering, fallback till tom dict vid fel."""
    try:
        return calculate_negative_price_exposure()
    except Exception as exc:
        print(
            f"[unified_dashboard] negative_price beräkning misslyckades: {exc}",
            file=sys.stderr,
        )
        return {}


def _safe_park_revenue() -> Dict[str, List[Dict[str, Any]]]:
    """Hämta realiserad capture/revenue per park, fallback till tom dict."""
    try:
        from .park_revenue import calculate_park_revenue_capture
        return calculate_park_revenue_capture()
    except Exception as exc:
        print(
            f"[unified_dashboard] park_revenue beräkning misslyckades: {exc}",
            file=sys.stderr,
        )
        return {}


def _merge_revenue_into_months(
    parks: Dict[str, Dict[str, Any]],
    revenue: Dict[str, List[Dict[str, Any]]],
) -> None:
    """Mutera parks: lägg till revenue/capture-fält per månad."""
    for park_key, park in parks.items():
        rev = revenue.get(park_key, [])
        rev_lookup: Dict[tuple, Dict[str, Any]] = {
            (r["year"], r["month"]): r for r in rev
        }
        for m in park["months"]:
            r = rev_lookup.get((m["year"], m["month"]))
            if r is None:
                m["revenue_eur"] = None
                m["capture_eur_mwh"] = None
                m["baseload_eur_mwh"] = None
                m["capture_premium_pct"] = None
                m["bazefield_volume_mwh"] = None
                m["revenue_eur_ppa"] = None
                m["capture_eur_mwh_ppa"] = None
                m["ppa_price_eur_mwh_avg"] = None
                m["effective_baseload_eur_mwh_ppa"] = None
            else:
                m["revenue_eur"] = r["revenue_eur"]
                m["capture_eur_mwh"] = r["capture_eur_mwh"]
                m["baseload_eur_mwh"] = r["baseload_eur_mwh"]
                m["capture_premium_pct"] = r["capture_premium_pct"]
                m["bazefield_volume_mwh"] = r["volume_mwh"]
                m["revenue_eur_ppa"] = r.get("revenue_eur_ppa")
                m["capture_eur_mwh_ppa"] = r.get("capture_eur_mwh_ppa")
                m["ppa_price_eur_mwh_avg"] = r.get("ppa_price_eur_mwh_avg")
                m["effective_baseload_eur_mwh_ppa"] = r.get(
                    "effective_baseload_eur_mwh_ppa"
                )


def _build_fleet_capture_by_zone(
    parks: Dict[str, Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Volym-vägd realiserad capture per zon per månad (alla parker i zonen)."""
    by_zone: dict[str, dict[tuple[int, int], dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {"rev": 0.0, "rev_ppa": 0.0, "vol": 0.0})
    )
    for park in parks.values():
        zone = park.get("zone")
        if not zone:
            continue
        for m in park["months"]:
            rev = m.get("revenue_eur")
            vol = m.get("bazefield_volume_mwh")
            if rev is None or vol is None or vol <= 0:
                continue
            ym = (m["year"], m["month"])
            by_zone[zone][ym]["rev"] += rev
            by_zone[zone][ym]["vol"] += vol
            # PPA: fall tillbaka till spot-revenue om parken saknar PPA-kontrakt
            rev_ppa = m.get("revenue_eur_ppa")
            by_zone[zone][ym]["rev_ppa"] += (
                rev_ppa if rev_ppa is not None else rev
            )

    out: Dict[str, List[Dict[str, Any]]] = {}
    for zone, months in by_zone.items():
        records = []
        for (year, month), d in sorted(months.items()):
            cap = d["rev"] / d["vol"] if d["vol"] > 0 else None
            cap_ppa = d["rev_ppa"] / d["vol"] if d["vol"] > 0 else None
            records.append({
                "month": f"{year}-{month:02d}",
                "fleet_capture_eur_mwh": round(cap, 2) if cap is not None else None,
                "fleet_capture_eur_mwh_ppa": (
                    round(cap_ppa, 2) if cap_ppa is not None else None
                ),
                "fleet_volume_mwh": round(d["vol"], 2),
            })
        if records:
            out[zone] = records
    return out


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


def _build_assets_section(
    market: Dict[str, Any],
    num_months: int = DEFAULT_HISTORY_MONTHS,
) -> Dict[str, Any]:
    """Bygg assets-sektionen med per-park månadsvisa KPI:er."""
    from .park_config import get_ppa  # local import to avoid cycle at top
    parks: Dict[str, Dict[str, Any]] = {}
    for park_key in PARK_KEYS:
        capacity_kwp = PARK_CAPACITY_KWP.get(park_key, 0)
        months, daily_by_month = _build_park_months(park_key, num_months=num_months)
        parks[park_key] = {
            "name": _park_display_name(park_key),
            "zone": PARK_ZONES.get(park_key, ""),
            "capacity_mwp": round(capacity_kwp / 1000.0, 3),
            "last_data_ts": _last_data_ts(park_key),
            "facts": _park_facts(park_key),
            "ppa": get_ppa(park_key),
            "months": months,
            "daily_by_month": daily_by_month,
        }

    # Berika med operations-data (negativa pris-exponering)
    neg_exposure = _safe_negative_price_exposure()
    _merge_operations_into_months(parks, neg_exposure)

    # Berika med realiserad capture & revenue (Bazefield × spot 15-min)
    revenue = _safe_park_revenue()
    _merge_revenue_into_months(parks, revenue)

    return {
        "parks": parks,
        "fleet": _build_fleet_overview(parks),
        "tracker_gain": _build_tracker_gain(),
        "capture_by_zone": _build_capture_by_zone(market),
        "fleet_capture_by_zone": _build_fleet_capture_by_zone(parks),
    }


def _build_capture_by_zone(market: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Plocka fram capture price per zon per månad från market-datan.

    Använder solprofilen `sol_syd` som standard-referens. Returnerar
    `{"SE3": [{"month": "2025-05", "capture_eur_mwh": 45.2}, ...], ...}`.
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    market_data = market.get("data") or {}
    for zone, profiles in market_data.items():
        # Föredra sol_syd; fall tillbaka till första tillgängliga solprofil
        candidate_keys = ["sol_syd", "sol_ov", "sol_tracker"]
        chosen = None
        for k in candidate_keys:
            if k in profiles and profiles[k].get("monthly"):
                chosen = profiles[k]
                break
        if chosen is None:
            continue
        records = []
        for m in chosen.get("monthly", []):
            year = m.get("year")
            month = m.get("month")
            cap = m.get("capture")
            if year is None or month is None:
                continue
            records.append({
                "month": f"{year}-{month:02d}",
                "capture_eur_mwh": _safe_round(cap, 2),
            })
        if records:
            out[zone] = records
    return out


def _build_tracker_gain() -> Dict[str, Any]:
    """Returnera tracker-gain summary (Hova vs fixed-tilt SE3-parker).

    calculate_tracker_gain() returnerar en list[dict] med
    {year, month, sy_hova, sy_fixed_avg, gain_pct}. Vi paketerar den i
    en dict för att kunna utöka senare utan att ändra contract.
    """
    try:
        monthly = calculate_tracker_gain()
    except Exception as exc:
        print(
            f"[unified_dashboard] tracker_gain beräkning misslyckades: {exc}",
            file=sys.stderr,
        )
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
    total_revenue = 0.0
    total_revenue_ppa = 0.0
    total_volume = 0.0
    total_baseload_weighted = 0.0
    has_revenue = False
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
        rev = match.get("revenue_eur")
        vol = match.get("bazefield_volume_mwh")
        if rev is not None:
            total_revenue += rev
            # PPA fallback to spot when park has no PPA contract
            rev_ppa = match.get("revenue_eur_ppa")
            total_revenue_ppa += rev_ppa if rev_ppa is not None else rev
            has_revenue = True
        if vol is not None:
            total_volume += vol
            base = match.get("baseload_eur_mwh")
            if base is not None:
                total_baseload_weighted += base * vol

    vs_budget = None
    if total_budget > 0:
        vs_budget = round((total_energy / total_budget - 1.0) * 100.0, 1)

    fleet_capture = (total_revenue / total_volume) if total_volume > 0 else None
    fleet_capture_ppa = (
        (total_revenue_ppa / total_volume) if total_volume > 0 else None
    )
    fleet_baseload = (total_baseload_weighted / total_volume) if total_volume > 0 else None
    capture_premium = None
    if (fleet_capture is not None and fleet_baseload is not None
            and fleet_baseload != 0):
        capture_premium = (fleet_capture / fleet_baseload - 1.0) * 100.0

    return {
        "latest_month": f"{year}-{month:02d}",
        "park_count": park_count,
        "total_capacity_mwp": round(total_capacity, 3),
        "total_energy_mwh": round(total_energy, 2),
        "vs_budget_pct": vs_budget,
        "total_revenue_eur": round(total_revenue, 2) if has_revenue else None,
        "total_revenue_eur_ppa": (
            round(total_revenue_ppa, 2) if has_revenue else None
        ),
        "fleet_volume_mwh": round(total_volume, 2) if total_volume > 0 else None,
        "fleet_capture_eur_mwh": round(fleet_capture, 2) if fleet_capture is not None else None,
        "fleet_capture_eur_mwh_ppa": (
            round(fleet_capture_ppa, 2) if fleet_capture_ppa is not None else None
        ),
        "fleet_baseload_eur_mwh": round(fleet_baseload, 2) if fleet_baseload is not None else None,
        "fleet_capture_premium_pct": round(capture_premium, 2) if capture_premium is not None else None,
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
    assets = _build_assets_section(market)
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "market": market,
        "assets": assets,
        "meta": _build_meta_section(market),
    }
