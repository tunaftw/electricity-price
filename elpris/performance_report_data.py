"""Månadsvis prestandarapport-data för Svea Solars solparker.

Beräknar alla KPI:er för en park och en månad:
- Energiproduktion (faktisk vs budget)
- Specific Yield (kWh/kWp)
- Performance Ratio (PR)
- Performance Index (PI)
- Verkningsgrad (meter vs inverter)
- Modultemperatur (Sandia-uppskattning)
- Förlustanalys (waterfall)
- Dagliga aggregat
- Bästa/sämsta dagar med 15-min detalj
- Year-To-Date sammanfattning
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import (
    PARK_CAPACITY_KWP,
    PARK_ZONES,
    PARKS_PROFILE_DIR,
    SWEDEN_TZ,
    UTC_TZ,
)
from .operations_dashboard_data import load_park_15min
from .park_config import get_budget, get_park_metadata

# Weekday short names (0=Monday) — English for international audience
_WEEKDAY_SV = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Month short names (1-indexed) — English for international audience
_MONTH_SV = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# Antagen genomsnittlig omgivningstemperatur (°C) i Sverige — används bara för att fylla
# `avg_module_temp_c`-fältet i daglig statistik (display-värde), inte i förlustkaskaden.
_DEFAULT_AMBIENT_TEMP_C = 10.0

# Sandia NOCT-modell: T_module = T_ambient + 0.03 * POA (W/m²)
_SANDIA_COEFF = 0.03


# ---------------------------------------------------------------------------
# Dataklasser
# ---------------------------------------------------------------------------

@dataclass
class DailyData:
    """Daglig sammanfattning."""
    day: int
    date_str: str
    weekday: str
    actual_energy_mwh: float
    actual_irradiation_kwh_m2: Optional[float]
    norm_yield_kwh_kwp: float
    expected_gen_mwh: Optional[float]
    performance_ratio_pct: Optional[float]
    performance_index_pct: Optional[float]
    efficiency_pct: Optional[float]
    avg_module_temp_c: Optional[float]
    avg_ambient_temp_c: Optional[float]


@dataclass
class DayDetail:
    """15-min upplösningsdata för en enstaka dag (för bästa/sämsta dag)."""
    date_str: str
    timestamps: list[str]
    power_mw: list[float]
    irradiance_wm2: list[Optional[float]]


@dataclass
class LossCascade:
    """Förlustanalys (waterfall)."""
    budget_energy_mwh: float
    actual_energy_mwh: float
    curtailment_loss_mwh: float
    irradiance_shortfall_loss_mwh: float
    availability_loss_mwh: float
    temperature_loss_mwh: float
    other_losses_mwh: float


@dataclass
class RevenueData:
    """Realiserad intäkt och capture-pris för en park-månad.

    PPA-fält är None när parken saknar kontrakt — visa då bara spot.
    """
    volume_mwh: float                               # Bazefield-volym × spot-join
    revenue_spot_eur: float                         # 100% spot
    revenue_ppa_eur: Optional[float]                # blandad volym × (share×PPA + (1-share)×spot)
    capture_spot_eur_mwh: Optional[float]
    capture_ppa_eur_mwh: Optional[float]
    baseload_eur_mwh: Optional[float]
    capture_premium_pct: Optional[float]            # capture vs baseload (spot-läge)
    ppa_price_sek_mwh: Optional[float]              # kontraktsvärde
    ppa_price_eur_mwh_avg: Optional[float]          # tidsviktad EUR-omräkning
    ppa_share_pct: Optional[float]


@dataclass
class MonthSummary:
    """En rad i YTD-tabellen."""
    year: int
    month: int
    month_name: str
    capacity_mwp: float
    budget_energy_mwh: float
    actual_energy_mwh: float
    curtailment_mwh: float
    vs_budget_energy_mwh: float
    norm_yield_mwh_mwp: float
    wc_budget_mwh: float
    losses_mwh: float
    budget_irr_kwh_m2: float
    actual_irr_kwh_m2: Optional[float]
    vs_budget_irr: Optional[float]
    budget_pr_pct: float
    actual_pr_pct: Optional[float]
    availability_loss_mwh: float


@dataclass
class Incident:
    """En incident-rad från manuell JSON (Resultat/operationsdata/incidenter/).

    Bara ``date`` är obligatoriskt — övriga fält kan saknas i källfilen och
    renderas då som "—".
    """
    date: str
    issue_id: Optional[int] = None
    fault_type: Optional[str] = None
    equipment: Optional[str] = None
    description: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    gen_loss_kwh: Optional[float] = None


@dataclass
class WorkLogEntry:
    """En rad i "work carried out"-loggen från manuell JSON."""
    date: str
    activity: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


@dataclass
class MonthlyReport:
    """Komplett månadsrapport för en park."""
    park_key: str
    park_display_name: str
    park_location: str
    zone: str
    year: int
    month: int
    month_name: str
    capacity_kwp: float
    capacity_mwp: float
    # Sammanfattande KPI:er
    actual_energy_mwh: float
    budget_energy_mwh: float
    actual_irradiation_kwh_m2: Optional[float]
    budget_irradiation_kwh_m2: float
    yield_kwh_kwp: float
    performance_ratio_pct: Optional[float]
    budget_pr_pct: float
    efficiency_pct: Optional[float]
    avg_module_temp_c: Optional[float]
    # Metadata (för Key Project Parameters)
    metadata: dict
    # Daglig data
    daily: list[DailyData]
    # Year-To-Date
    ytd: list[MonthSummary]
    # Förlustanalys
    losses: LossCascade
    # Bästa/sämsta dagar
    best_days: list[DailyData]
    worst_days: list[DailyData]
    best_day_detail: Optional[DayDetail]
    worst_day_detail: Optional[DayDetail]
    # Datatillgänglighet
    has_irradiance: bool
    has_availability: bool
    has_active_power: bool
    # Inverter-data (Phase 6)
    inverters: list = field(default_factory=list)         # list[InverterMonthly]
    inverter_daily_lookup: dict = field(default_factory=dict)  # {inv_name: {day: InverterDaily}}
    alarm_stats: object = None                              # AlarmStats | None
    recent_alarms: list = field(default_factory=list)     # list[AlarmEvent]
    has_inverter_data: bool = False
    has_alarm_data: bool = False
    # Intäkt + PPA (None om Bazefield × spot-join saknas för månaden)
    revenue: Optional[RevenueData] = None
    # Incidents & work orders (manuell JSON, Steg 7 Alternativ A)
    incidents: list = field(default_factory=list)          # list[Incident]
    work_log: list = field(default_factory=list)           # list[WorkLogEntry]
    has_incident_data: bool = False


# ---------------------------------------------------------------------------
# Hjälpfunktioner
# ---------------------------------------------------------------------------

def _safe_div(numerator: float, denominator: float) -> Optional[float]:
    """Säker division som returnerar None vid nolldivision."""
    if denominator == 0:
        return None
    return numerator / denominator


def _filter_month(records: list[dict], year: int, month: int) -> list[dict]:
    """Filtrera poster till specifikt år+månad."""
    return [r for r in records if r["year"] == year and r["month"] == month]


def _check_data_flags(records: list[dict]) -> tuple[bool, bool, bool]:
    """Kontrollera datatillgänglighet.

    Returns:
        (has_irradiance, has_availability, has_active_power)
    """
    has_irr = any(r.get("irradiance_poa") is not None for r in records)
    has_avail = any(r.get("availability") is not None for r in records)
    has_ap = any(r.get("active_power_mw") is not None for r in records)
    return has_irr, has_avail, has_ap


def _swedish_weekday(date_str: str) -> str:
    """Returnera svensk veckodagsförkortning för ett datum (YYYY-MM-DD)."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return _WEEKDAY_SV[d.weekday()]


# ---------------------------------------------------------------------------
# Daglig aggregering
# ---------------------------------------------------------------------------

def _meter_inverter_efficiency(records: list[dict]) -> Optional[float]:
    """Verkningsgrad meter/inverter (%) över IDENTISK intervalluppsättning.

    Täljare (mätare) och nämnare (invertersumma) summeras över samma intervall
    — de där inverterdata finns OCH mätaren > 0 — så gles/trasig mätartäckning
    inte biasar KPI:t nedåt (intervall med inverteroutput men mätare = 0 räknas
    annars bara i nämnaren). ActivePower är ofta opålitlig; ligger resultatet
    utanför 50–105 % är data broken → None. Returnerar rundat till 2 decimaler.
    """
    valid = [
        r for r in records
        if r.get("active_power_mw") is not None and r.get("power_mw", 0) > 0
    ]
    inv_total = sum((r.get("active_power_mw") or 0) for r in valid)
    if inv_total <= 0:
        return None
    meter_total = sum(r["power_mw"] for r in valid)
    eff = (meter_total / inv_total) * 100.0
    if 50.0 <= eff <= 105.0:
        return round(eff, 2)
    return None


def _aggregate_daily(
    records: list[dict],
    capacity_kwp: float,
    standard_pr: float,
    has_irradiance: bool,
    has_active_power: bool,
) -> list[DailyData]:
    """Aggregera 15-min poster till daglig data."""
    capacity_mw = capacity_kwp / 1000.0

    # Gruppera per dag
    by_day: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_day[rec["date"]].append(rec)

    daily_list: list[DailyData] = []
    for date_str in sorted(by_day):
        day_records = by_day[date_str]
        day_num = int(date_str.split("-")[2])

        # Energi: använd effective_power_mw (meter om tillgänglig, annars inverter)
        actual_energy = sum(r.get("effective_power_mw", r.get("power_mw", 0)) * 0.25 for r in day_records)

        # Instrålning (kWh/m²)
        actual_irr: Optional[float] = None
        if has_irradiance:
            irr_vals = [r["irradiance_poa"] for r in day_records
                        if r.get("irradiance_poa") is not None]
            if irr_vals:
                # POA i W/m², * 0.25h / 1000 → kWh/m²
                actual_irr = sum(v * 0.25 / 1000.0 for v in irr_vals)

        # Normalized yield
        norm_yield = actual_energy / capacity_mw if capacity_mw > 0 else 0.0

        # Expected generation
        expected_gen: Optional[float] = None
        if actual_irr is not None and actual_irr > 0:
            expected_gen = actual_irr * capacity_kwp * standard_pr / 1000.0

        # Performance Ratio
        pr: Optional[float] = None
        if actual_irr is not None and actual_irr > 0 and capacity_mw > 0:
            pr = _safe_div(actual_energy, actual_irr * capacity_mw)
            if pr is not None:
                pr *= 100.0

        # Performance Index
        pi: Optional[float] = None
        if expected_gen is not None and expected_gen > 0:
            pi = _safe_div(actual_energy, expected_gen)
            if pi is not None:
                pi *= 100.0

        # Verkningsgrad (meter vs inverter) — se _meter_inverter_efficiency.
        efficiency: Optional[float] = None
        if has_active_power:
            efficiency = _meter_inverter_efficiency(day_records)

        # Modultemperatur (Sandia NOCT-uppskattning)
        avg_mod_temp: Optional[float] = None
        avg_amb_temp: Optional[float] = None
        if has_irradiance:
            irr_for_temp = [r["irradiance_poa"] for r in day_records
                            if r.get("irradiance_poa") is not None
                            and r["irradiance_poa"] > 0]
            if irr_for_temp:
                avg_poa = sum(irr_for_temp) / len(irr_for_temp)
                avg_amb_temp = _DEFAULT_AMBIENT_TEMP_C
                avg_mod_temp = avg_amb_temp + _SANDIA_COEFF * avg_poa

        daily_list.append(DailyData(
            day=day_num,
            date_str=date_str,
            weekday=_swedish_weekday(date_str),
            actual_energy_mwh=round(actual_energy, 4),
            actual_irradiation_kwh_m2=(round(actual_irr, 4)
                                       if actual_irr is not None else None),
            norm_yield_kwh_kwp=round(norm_yield, 4),
            expected_gen_mwh=(round(expected_gen, 4)
                              if expected_gen is not None else None),
            performance_ratio_pct=(round(pr, 2) if pr is not None else None),
            performance_index_pct=(round(pi, 2) if pi is not None else None),
            efficiency_pct=(round(efficiency, 2)
                            if efficiency is not None else None),
            avg_module_temp_c=(round(avg_mod_temp, 1)
                               if avg_mod_temp is not None else None),
            avg_ambient_temp_c=(round(avg_amb_temp, 1)
                                if avg_amb_temp is not None else None),
        ))

    return daily_list


# ---------------------------------------------------------------------------
# 15-min detalj för en dag
# ---------------------------------------------------------------------------

def _extract_day_detail(
    records: list[dict],
    date_str: str,
) -> Optional[DayDetail]:
    """Extrahera 15-min detalj för en specifik dag."""
    day_records = [r for r in records if r["date"] == date_str]
    if not day_records:
        return None

    day_records.sort(key=lambda r: r["timestamp_utc"])

    timestamps: list[str] = []
    power_mw: list[float] = []
    irradiance_wm2: list[Optional[float]] = []

    for rec in day_records:
        ts_local = rec["timestamp_utc"].astimezone(SWEDEN_TZ)
        timestamps.append(ts_local.strftime("%H:%M"))
        power_mw.append(round(rec.get("effective_power_mw", rec.get("power_mw", 0)), 4))
        irr = rec.get("irradiance_poa")
        irradiance_wm2.append(round(irr, 2) if irr is not None else None)

    return DayDetail(
        date_str=date_str,
        timestamps=timestamps,
        power_mw=power_mw,
        irradiance_wm2=irradiance_wm2,
    )


# ---------------------------------------------------------------------------
# Förlustanalys (waterfall)
# ---------------------------------------------------------------------------

def _calculate_loss_cascade(
    budget_energy_mwh: float,
    actual_energy_mwh: float,
    budget_irr_kwh_m2: float,
    actual_irr_kwh_m2: Optional[float],
    capacity_kwp: float,
    standard_pr: float,
    records: list[dict],
    has_irradiance: bool,
    has_availability: bool,
    avg_module_temp_c: Optional[float],
) -> LossCascade:
    """Beräkna förlustanalys (waterfall) för månaden."""
    capacity_mw = capacity_kwp / 1000.0

    # 1. Instrålningsbrist
    irr_shortfall = 0.0
    wc_budget = budget_energy_mwh  # Weather-corrected budget
    if (has_irradiance
            and actual_irr_kwh_m2 is not None
            and budget_irr_kwh_m2 > 0):
        irr_ratio = actual_irr_kwh_m2 / budget_irr_kwh_m2
        wc_budget = budget_energy_mwh * irr_ratio
        irr_shortfall = budget_energy_mwh - wc_budget
    else:
        # Ingen instrålningsdata → sätt till 0
        irr_shortfall = 0.0

    # 2. Tillgänglighetsförlust
    avail_loss = 0.0
    if has_availability and has_irradiance:
        for rec in records:
            avail = rec.get("availability")
            irr = rec.get("irradiance_poa")
            if avail is not None and irr is not None and avail < 1.0:
                # Förväntad gen för detta intervall
                expected_interval = irr * 0.25 / 1000.0 * capacity_kwp * standard_pr / 1000.0
                avail_loss += expected_interval * (1.0 - avail)

    # 3. Oförklarat (residual)
    # Allt som inte kan tillskrivas uppmätt instrålning eller availability hamnar här.
    # Kan vara positiv (faktiska förluster: soiling, clipping, real curtailment, modellfel)
    # eller negativ (parken slog TMY-budgeten — t.ex. vid klart väder, gynnsam temperatur,
    # eller om PVsyst-budgeten är konservativ).
    unexplained = budget_energy_mwh - actual_energy_mwh - irr_shortfall - avail_loss

    return LossCascade(
        budget_energy_mwh=round(budget_energy_mwh, 4),
        actual_energy_mwh=round(actual_energy_mwh, 4),
        curtailment_loss_mwh=round(unexplained, 4),
        irradiance_shortfall_loss_mwh=round(irr_shortfall, 4),
        availability_loss_mwh=round(avail_loss, 4),
        temperature_loss_mwh=0.0,
        other_losses_mwh=0.0,
    )


# ---------------------------------------------------------------------------
# Year-To-Date
# ---------------------------------------------------------------------------

def _build_ytd(
    all_records: list[dict],
    park_key: str,
    year: int,
    up_to_month: int,
    capacity_kwp: float,
    standard_pr: float,
    has_irradiance: bool,
    has_availability: bool,
) -> list[MonthSummary]:
    """Bygg YTD-tabell för alla månader jan → up_to_month."""
    capacity_mw = capacity_kwp / 1000.0
    ytd: list[MonthSummary] = []

    for m in range(1, up_to_month + 1):
        month_records = _filter_month(all_records, year, m)

        # Faktisk energi: använd effective_power_mw (meter om tillgänglig, annars inverter)
        actual_energy = sum(r.get("effective_power_mw", r.get("power_mw", 0)) * 0.25 for r in month_records)

        # Budget
        try:
            budget = get_budget(park_key, year, m)
        except (ValueError, FileNotFoundError):
            budget = {"energy_mwh": 0.0, "irradiation_kwh_m2": 0.0, "pr_pct": 80.0}

        budget_energy = budget["energy_mwh"]
        budget_irr = budget["irradiation_kwh_m2"]
        budget_pr = budget["pr_pct"]

        # Faktisk instrålning
        actual_irr: Optional[float] = None
        if has_irradiance:
            irr_vals = [r["irradiance_poa"] for r in month_records
                        if r.get("irradiance_poa") is not None]
            if irr_vals:
                actual_irr = sum(v * 0.25 / 1000.0 for v in irr_vals)

        # Weather-corrected budget
        wc_budget = budget_energy
        if actual_irr is not None and budget_irr > 0:
            wc_budget = budget_energy * (actual_irr / budget_irr)

        # PR
        actual_pr: Optional[float] = None
        if actual_irr is not None and actual_irr > 0 and capacity_mw > 0:
            pr_val = _safe_div(actual_energy, actual_irr * capacity_mw)
            if pr_val is not None:
                actual_pr = round(pr_val * 100.0, 2)

        # Instrålningsdelta
        vs_irr: Optional[float] = None
        if actual_irr is not None:
            vs_irr = round(budget_irr - actual_irr, 4)

        # Tillgänglighetsförlust
        avail_loss = 0.0
        if has_availability and has_irradiance:
            for rec in month_records:
                avail = rec.get("availability")
                irr = rec.get("irradiance_poa")
                if avail is not None and irr is not None and avail < 1.0:
                    expected_int = irr * 0.25 / 1000.0 * capacity_kwp * standard_pr / 1000.0
                    avail_loss += expected_int * (1.0 - avail)

        # Oförklarat (residual). Inte clampad — negativt värde betyder att parken
        # slog TMY-budgeten efter justering för uppmätt instrålning + availability.
        irr_shortfall = 0.0
        if actual_irr is not None and budget_irr > 0:
            irr_shortfall = budget_energy - wc_budget
        unexplained = budget_energy - actual_energy - irr_shortfall - avail_loss

        # Norm yield (kWh/kWp = MWh/MWp)
        norm_yield = actual_energy / capacity_mw if capacity_mw > 0 else 0.0

        # Losses
        losses = budget_energy - actual_energy

        ytd.append(MonthSummary(
            year=year,
            month=m,
            month_name=_MONTH_SV[m],
            capacity_mwp=round(capacity_mw, 3),
            budget_energy_mwh=round(budget_energy, 2),
            actual_energy_mwh=round(actual_energy, 2),
            curtailment_mwh=round(unexplained, 2),
            vs_budget_energy_mwh=round(budget_energy - actual_energy, 2),
            norm_yield_mwh_mwp=round(norm_yield, 2),
            wc_budget_mwh=round(wc_budget, 2),
            losses_mwh=round(losses, 2),
            budget_irr_kwh_m2=round(budget_irr, 2),
            actual_irr_kwh_m2=(round(actual_irr, 2)
                                if actual_irr is not None else None),
            vs_budget_irr=vs_irr,
            budget_pr_pct=round(budget_pr, 2),
            actual_pr_pct=actual_pr,
            availability_loss_mwh=round(avail_loss, 2),
        ))

    return ytd


# ---------------------------------------------------------------------------
# Incidents & Work Orders (Steg 7, Alternativ A — manuell JSON)
# ---------------------------------------------------------------------------

def load_incidents(
    park_key: str, year: int, month: int
) -> tuple[list[Incident], list[WorkLogEntry], bool]:
    """Läs manuell incident/work-log JSON för en park och månad.

    Fil: ``Resultat/operationsdata/incidenter/{park_key}_{YYYY-MM}.json``.
    Se ``_template.json`` i samma katalog för formatet. Filerna fylls i
    manuellt av O&M/asset-teamet — de finns inte för alla park-månader.

    Returns:
        (incidents, work_log, has_data) — ``has_data`` är True endast om
        filen fanns och kunde tolkas som giltig JSON. Ett trasigt/ogiltigt
        innehåll loggas via print() och behandlas som "ingen fil".
    """
    from .config import RESULTAT_DIR

    path = (
        RESULTAT_DIR / "operationsdata" / "incidenter"
        / f"{park_key}_{year:04d}-{month:02d}.json"
    )
    if not path.exists():
        return [], [], False

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[performance_report] incidents {park_key} {year}-{month:02d}: "
              f"could not parse {path} ({exc}) — falling back to placeholder",
              file=sys.stderr)
        return [], [], False

    if not isinstance(raw, dict):
        print(f"[performance_report] incidents {park_key} {year}-{month:02d}: "
              f"{path} is not a JSON object — falling back to placeholder",
              file=sys.stderr)
        return [], [], False

    incidents: list[Incident] = []
    for entry in raw.get("incidents") or []:
        if not isinstance(entry, dict) or "date" not in entry:
            continue
        incidents.append(Incident(
            date=entry["date"],
            issue_id=entry.get("issue_id"),
            fault_type=entry.get("fault_type"),
            equipment=entry.get("equipment"),
            description=entry.get("description"),
            start=entry.get("start"),
            end=entry.get("end"),
            priority=entry.get("priority"),
            status=entry.get("status"),
            gen_loss_kwh=entry.get("gen_loss_kwh"),
        ))

    work_log: list[WorkLogEntry] = []
    for entry in raw.get("work_carried_out") or []:
        if not isinstance(entry, dict) or "date" not in entry:
            continue
        work_log.append(WorkLogEntry(
            date=entry["date"],
            activity=entry.get("activity"),
            status=entry.get("status"),
            remarks=entry.get("remarks"),
        ))

    return incidents, work_log, True


# ---------------------------------------------------------------------------
# Huvudfunktion
# ---------------------------------------------------------------------------

def generate_report(park_key: str, year: int, month: int) -> MonthlyReport:
    """Generera komplett månadsrapport för en park.

    Args:
        park_key: Parknyckel (t.ex. "horby", "hova")
        year: År
        month: Månad (1-12)

    Returns:
        MonthlyReport med alla KPI:er, daglig data, YTD, förluster m.m.

    Raises:
        ValueError: Om parken inte finns eller ogiltigt datum.
    """
    if not 1 <= month <= 12:
        raise ValueError(f"Ogiltig månad: {month}")

    # Metadata
    meta = get_park_metadata(park_key)
    if meta is None:
        raise ValueError(
            f"Okänd park: {park_key!r}. "
            f"Tillgängliga: {list(PARK_CAPACITY_KWP.keys())}"
        )

    capacity_kwp = meta["capacity_kwp"]
    capacity_mw = capacity_kwp / 1000.0
    zone = meta["zone"]
    display_name = meta["display_name"]
    location = meta["location"]
    standard_pr = meta.get("standard_pr", 0.80)

    # 1. Ladda all 15-min data
    all_records = load_park_15min(park_key)
    if not all_records:
        # Returnera tom rapport
        return _empty_report(park_key, meta, year, month)

    # 2. Filtrera till begärd månad
    month_records = _filter_month(all_records, year, month)
    if not month_records:
        return _empty_report(park_key, meta, year, month)

    # 3. Kontrollera datatillgänglighet
    has_irradiance, has_availability, has_active_power = _check_data_flags(
        month_records
    )

    # 4. Dagliga aggregat
    daily = _aggregate_daily(
        month_records,
        capacity_kwp,
        standard_pr,
        has_irradiance,
        has_active_power,
    )

    # 5. Månadstotaler
    actual_energy = sum(d.actual_energy_mwh for d in daily)

    actual_irr: Optional[float] = None
    if has_irradiance:
        irr_vals = [d.actual_irradiation_kwh_m2 for d in daily
                    if d.actual_irradiation_kwh_m2 is not None]
        if irr_vals:
            actual_irr = sum(irr_vals)

    # Yield (kWh/kWp)
    yield_kwh_kwp = actual_energy / capacity_mw if capacity_mw > 0 else 0.0

    # 6. Budget
    try:
        budget = get_budget(park_key, year, month)
    except (ValueError, FileNotFoundError):
        budget = {"energy_mwh": 0.0, "irradiation_kwh_m2": 0.0, "pr_pct": 80.0}

    budget_energy = budget["energy_mwh"]
    budget_irr = budget["irradiation_kwh_m2"]
    budget_pr = budget["pr_pct"]

    # 7. PR, PI, verkningsgrad
    pr: Optional[float] = None
    if actual_irr is not None and actual_irr > 0 and capacity_mw > 0:
        pr_val = _safe_div(actual_energy, actual_irr * capacity_mw)
        if pr_val is not None:
            pr = round(pr_val * 100.0, 2)

    # Verkningsgrad: meter vs inverter sum — se _meter_inverter_efficiency.
    efficiency: Optional[float] = None
    if has_active_power:
        efficiency = _meter_inverter_efficiency(month_records)

    # Modultemperatur (medelvärde av dagliga)
    avg_mod_temp: Optional[float] = None
    if has_irradiance:
        temp_vals = [d.avg_module_temp_c for d in daily
                     if d.avg_module_temp_c is not None]
        if temp_vals:
            avg_mod_temp = round(sum(temp_vals) / len(temp_vals), 1)

    # 8. Förlustanalys
    losses = _calculate_loss_cascade(
        budget_energy_mwh=budget_energy,
        actual_energy_mwh=actual_energy,
        budget_irr_kwh_m2=budget_irr,
        actual_irr_kwh_m2=actual_irr,
        capacity_kwp=capacity_kwp,
        standard_pr=standard_pr,
        records=month_records,
        has_irradiance=has_irradiance,
        has_availability=has_availability,
        avg_module_temp_c=avg_mod_temp,
    )

    # 9. Bästa/sämsta dagar
    # Top 5 bästa (högst energi)
    sorted_by_energy = sorted(daily, key=lambda d: d.actual_energy_mwh,
                              reverse=True)
    best_days = sorted_by_energy[:5]

    # Bottom 5 sämsta (lägst energi, men > 0.01 MWh)
    producing_days = [d for d in daily if d.actual_energy_mwh > 0.01]
    producing_days.sort(key=lambda d: d.actual_energy_mwh)
    worst_days = producing_days[:5]

    # 10. 15-min detalj för bästa och sämsta dag
    best_day_detail: Optional[DayDetail] = None
    if best_days:
        best_day_detail = _extract_day_detail(month_records,
                                              best_days[0].date_str)

    worst_day_detail: Optional[DayDetail] = None
    if worst_days:
        worst_day_detail = _extract_day_detail(month_records,
                                               worst_days[0].date_str)

    # 11. YTD — alla månader jan → aktuell månad, samma år
    year_records = [r for r in all_records if r["year"] == year]
    ytd = _build_ytd(
        all_records=year_records,
        park_key=park_key,
        year=year,
        up_to_month=month,
        capacity_kwp=capacity_kwp,
        standard_pr=standard_pr,
        has_irradiance=has_irradiance,
        has_availability=has_availability,
    )

    # 12. Ladda inverter-data om det finns (Phase 6)
    inverters_monthly: list = []
    inverter_daily_lookup: dict = {}
    alarm_stats = None
    recent_alarms: list = []
    has_inverter_data = False
    has_alarm_data = False

    # 12b. Realiserad capture & PPA-revenue för månaden
    revenue: Optional[RevenueData] = None
    try:
        from .park_revenue import calculate_park_revenue_capture
        rev_data = calculate_park_revenue_capture()
        park_rows = rev_data.get(park_key, [])
        match = next(
            (r for r in park_rows
             if r["year"] == year and r["month"] == month),
            None,
        )
        if match is not None and match.get("volume_mwh", 0) > 0:
            revenue = RevenueData(
                volume_mwh=match["volume_mwh"],
                revenue_spot_eur=match["revenue_eur"],
                revenue_ppa_eur=match.get("revenue_eur_ppa"),
                capture_spot_eur_mwh=match.get("capture_eur_mwh"),
                capture_ppa_eur_mwh=match.get("capture_eur_mwh_ppa"),
                baseload_eur_mwh=match.get("baseload_eur_mwh"),
                capture_premium_pct=match.get("capture_premium_pct"),
                ppa_price_sek_mwh=match.get("ppa_price_sek_mwh"),
                ppa_price_eur_mwh_avg=match.get("ppa_price_eur_mwh_avg"),
                ppa_share_pct=match.get("ppa_share_pct"),
            )
    except Exception:
        # Graceful: revenue-sektionen renderar bara om datat finns
        revenue = None

    try:
        from .inverter_data import (
            load_inverter_yield, load_alarm_events,
            aggregate_inverter_monthly, aggregate_alarm_stats,
            get_filtered_alarms, get_daily_inverter_data,
        )
        inv_yield = load_inverter_yield(park_key)
        if inv_yield:
            inverters_monthly = aggregate_inverter_monthly(inv_yield, year, month)
            inverter_daily_lookup = get_daily_inverter_data(inv_yield, year, month)
            has_inverter_data = bool(inverters_monthly)

        alarm_events = load_alarm_events(park_key)
        if alarm_events:
            alarm_stats = aggregate_alarm_stats(alarm_events, year, month)
            recent_alarms = get_filtered_alarms(alarm_events, year, month, limit=50)
            has_alarm_data = (alarm_stats.total_alarms > 0)
    except ImportError:
        pass  # inverter_data inte tillgänglig — graceful degradation

    # 12c. Incidents & work orders (manuell JSON, Steg 7 Alternativ A)
    incidents, work_log, has_incident_data = load_incidents(park_key, year, month)

    # 13. Bygg rapport
    return MonthlyReport(
        park_key=park_key,
        park_display_name=display_name,
        park_location=location,
        zone=zone,
        year=year,
        month=month,
        month_name=_MONTH_SV[month],
        capacity_kwp=capacity_kwp,
        capacity_mwp=round(capacity_mw, 3),
        actual_energy_mwh=round(actual_energy, 2),
        budget_energy_mwh=round(budget_energy, 2),
        actual_irradiation_kwh_m2=(round(actual_irr, 2)
                                    if actual_irr is not None else None),
        budget_irradiation_kwh_m2=round(budget_irr, 2),
        yield_kwh_kwp=round(yield_kwh_kwp, 2),
        performance_ratio_pct=pr,
        budget_pr_pct=round(budget_pr, 2),
        efficiency_pct=efficiency,
        avg_module_temp_c=avg_mod_temp,
        metadata=meta,
        daily=daily,
        ytd=ytd,
        losses=losses,
        best_days=best_days,
        worst_days=worst_days,
        best_day_detail=best_day_detail,
        worst_day_detail=worst_day_detail,
        has_irradiance=has_irradiance,
        has_availability=has_availability,
        has_active_power=has_active_power,
        inverters=inverters_monthly,
        inverter_daily_lookup=inverter_daily_lookup,
        alarm_stats=alarm_stats,
        recent_alarms=recent_alarms,
        has_inverter_data=has_inverter_data,
        has_alarm_data=has_alarm_data,
        revenue=revenue,
        incidents=incidents,
        work_log=work_log,
        has_incident_data=has_incident_data,
    )


def _empty_report(
    park_key: str,
    meta: dict,
    year: int,
    month: int,
) -> MonthlyReport:
    """Returnera en tom rapport när inga data finns."""
    capacity_kwp = meta.get("capacity_kwp", 0)
    capacity_mw = capacity_kwp / 1000.0

    try:
        budget = get_budget(park_key, year, month)
    except (ValueError, FileNotFoundError):
        budget = {"energy_mwh": 0.0, "irradiation_kwh_m2": 0.0, "pr_pct": 80.0}

    return MonthlyReport(
        park_key=park_key,
        park_display_name=meta.get("display_name", park_key),
        park_location=meta.get("location", ""),
        zone=meta.get("zone", ""),
        year=year,
        month=month,
        month_name=_MONTH_SV[month],
        capacity_kwp=capacity_kwp,
        capacity_mwp=round(capacity_mw, 3),
        actual_energy_mwh=0.0,
        budget_energy_mwh=budget["energy_mwh"],
        actual_irradiation_kwh_m2=None,
        budget_irradiation_kwh_m2=budget["irradiation_kwh_m2"],
        yield_kwh_kwp=0.0,
        performance_ratio_pct=None,
        budget_pr_pct=budget["pr_pct"],
        efficiency_pct=None,
        avg_module_temp_c=None,
        metadata=meta,
        daily=[],
        ytd=[],
        losses=LossCascade(
            budget_energy_mwh=budget["energy_mwh"],
            actual_energy_mwh=0.0,
            curtailment_loss_mwh=0.0,
            irradiance_shortfall_loss_mwh=0.0,
            availability_loss_mwh=0.0,
            temperature_loss_mwh=0.0,
            other_losses_mwh=0.0,
        ),
        best_days=[],
        worst_days=[],
        best_day_detail=None,
        worst_day_detail=None,
        has_irradiance=False,
        has_availability=False,
        has_active_power=False,
    )
