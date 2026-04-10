"""Inverter-data aggregation för månadsrapporter.

Läser CSV-filer från Resultat/profiler/parker/inverters/ och aggregerar
till månadsvisa statistik som används i performance_report_data.py.

Strukturer:
- InverterMonthly: per-inverter månadsstatistik (yield, max power, CF%, ranking)
- InverterDaily: per-inverter daglig data (för heatmaps och trendlinjer)
- AlarmEvent: enskilt alarm-event (för sektion 18)
- AlarmStats: aggregerad alarm-statistik per månad
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import PARKS_PROFILE_DIR

INVERTER_DIR = PARKS_PROFILE_DIR / "inverters"


# ---------------------------------------------------------------------------
# Dataklasser
# ---------------------------------------------------------------------------

@dataclass
class InverterDaily:
    """Daglig data för en enstaka inverter."""
    date: str                # YYYY-MM-DD
    inverter_name: str
    energy_kwh: float
    max_power_kw: float
    rated_kw: float
    capacity_factor_pct: float


@dataclass
class InverterMonthly:
    """Månadsstatistik per inverter."""
    name: str                # "HRB-TS1-INV04"
    transformer: str         # "TS1"
    rated_kw: float
    total_energy_kwh: float       # Månadens totalsumma
    max_power_kw: float           # Högsta peak under månaden
    avg_capacity_factor_pct: float  # Månatligt snitt CF
    days_active: int              # Antal dagar med >1 kWh
    rank: int = 0                 # Ranking (1=bäst, sätts av aggregering)


@dataclass
class AlarmEvent:
    """Ett alarm-event från en inverter."""
    inverter_name: str
    event_name: str
    event_code: int
    description: str
    time_start_utc: str
    time_end_utc: str
    duration_min: float


@dataclass
class AlarmStats:
    """Aggregerad alarm-statistik per månad."""
    total_alarms: int = 0
    unique_types: int = 0
    avg_mtba_hours: float = 0.0   # Mean Time Between Alarms
    active_at_period_end: int = 0  # Alarms utan timeEnd
    by_type: dict[str, int] = field(default_factory=dict)
    by_inverter: dict[str, int] = field(default_factory=dict)
    daily_count: dict[str, int] = field(default_factory=dict)  # date → count
    top_alarms: list[tuple[str, int, float]] = field(default_factory=list)
    # (event_name, count, total_duration_min)


# ---------------------------------------------------------------------------
# CSV-inläsning
# ---------------------------------------------------------------------------

def load_inverter_yield(park_key: str) -> list[InverterDaily]:
    """Läs alla dagliga yield-rader för en park."""
    csv_path = INVERTER_DIR / f"{park_key}_daily_yield.csv"
    if not csv_path.exists():
        return []

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                records.append(InverterDaily(
                    date=row["date"],
                    inverter_name=row["inverter_name"],
                    energy_kwh=float(row["energy_kwh"] or 0),
                    max_power_kw=float(row["max_power_kw"] or 0),
                    rated_kw=float(row["rated_kw"] or 0),
                    capacity_factor_pct=float(row["capacity_factor_pct"] or 0),
                ))
            except (KeyError, ValueError):
                continue
    return records


def load_alarm_events(park_key: str) -> list[AlarmEvent]:
    """Läs alla alarm-events för en park."""
    csv_path = INVERTER_DIR / f"{park_key}_events.csv"
    if not csv_path.exists():
        return []

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                records.append(AlarmEvent(
                    inverter_name=row["inverter_name"],
                    event_name=row["event_name"],
                    event_code=int(row.get("event_code") or 0),
                    description=row.get("description", ""),
                    time_start_utc=row.get("time_start_utc", ""),
                    time_end_utc=row.get("time_end_utc", ""),
                    duration_min=float(row.get("duration_min") or 0),
                ))
            except (KeyError, ValueError):
                continue
    return records


# ---------------------------------------------------------------------------
# Aggregering till månadsvis statistik
# ---------------------------------------------------------------------------

def aggregate_inverter_monthly(
    daily_records: list[InverterDaily],
    year: int,
    month: int,
) -> list[InverterMonthly]:
    """Aggregera dagliga inverter-rader till månadsstatistik per inverter.

    Filtrerar till given månad och beräknar:
    - total_energy_kwh: summa
    - max_power_kw: max över alla dagar
    - avg_capacity_factor_pct: snitt över dagar med produktion
    - days_active: antal dagar med >1 kWh
    - rank: 1 = bäst inverter (sätts efter sortering)
    """
    month_prefix = f"{year:04d}-{month:02d}"
    filtered = [r for r in daily_records if r.date.startswith(month_prefix)]

    by_inverter: dict[str, list[InverterDaily]] = defaultdict(list)
    for r in filtered:
        by_inverter[r.inverter_name].append(r)

    monthly: list[InverterMonthly] = []
    for inv_name, rows in by_inverter.items():
        if not rows:
            continue
        total_energy = sum(r.energy_kwh for r in rows)
        max_power = max((r.max_power_kw for r in rows), default=0.0)
        rated = rows[0].rated_kw
        active_rows = [r for r in rows if r.energy_kwh > 1.0]
        days_active = len(active_rows)
        avg_cf = (
            sum(r.capacity_factor_pct for r in active_rows) / len(active_rows)
            if active_rows else 0.0
        )

        # Extract transformer from name (e.g. "HRB-TS1-INV04" → "TS1")
        parts = inv_name.split("-")
        transformer = parts[1] if len(parts) >= 3 else ""

        monthly.append(InverterMonthly(
            name=inv_name,
            transformer=transformer,
            rated_kw=rated,
            total_energy_kwh=round(total_energy, 2),
            max_power_kw=round(max_power, 2),
            avg_capacity_factor_pct=round(avg_cf, 2),
            days_active=days_active,
        ))

    # Sortera och tilldela ranking (1 = mest energi)
    monthly.sort(key=lambda m: m.total_energy_kwh, reverse=True)
    for idx, m in enumerate(monthly, 1):
        m.rank = idx

    # Sortera tillbaka alfabetiskt för stabil presentation
    monthly.sort(key=lambda m: m.name)
    return monthly


def aggregate_alarm_stats(
    events: list[AlarmEvent],
    year: int,
    month: int,
) -> AlarmStats:
    """Aggregera alarm-events till månadsstatistik."""
    month_prefix = f"{year:04d}-{month:02d}"
    filtered = [e for e in events if e.time_start_utc.startswith(month_prefix)]

    if not filtered:
        return AlarmStats()

    by_type: Counter = Counter(e.event_name for e in filtered)
    by_inverter: Counter = Counter(e.inverter_name for e in filtered)

    # Daglig count
    daily: defaultdict = defaultdict(int)
    for e in filtered:
        date_str = e.time_start_utc[:10]
        daily[date_str] += 1

    # Top alarms med duration
    type_durations: defaultdict = defaultdict(float)
    for e in filtered:
        type_durations[e.event_name] += e.duration_min

    top_alarms = sorted(
        [(name, count, round(type_durations[name], 1))
         for name, count in by_type.items()],
        key=lambda x: x[1],
        reverse=True,
    )[:10]

    # MTBA: dagar i månad / antal alarm
    days_in_month = 31  # Approximation, OK för rapport
    mtba_hours = (days_in_month * 24 / len(filtered)) if filtered else 0

    # Active at period end (alarms utan timeEnd)
    active_count = sum(1 for e in filtered if not e.time_end_utc)

    return AlarmStats(
        total_alarms=len(filtered),
        unique_types=len(by_type),
        avg_mtba_hours=round(mtba_hours, 2),
        active_at_period_end=active_count,
        by_type=dict(by_type),
        by_inverter=dict(by_inverter),
        daily_count=dict(daily),
        top_alarms=top_alarms,
    )


def get_filtered_alarms(
    events: list[AlarmEvent],
    year: int,
    month: int,
    limit: int = 50,
) -> list[AlarmEvent]:
    """Returnera de senaste N alarm-events för en månad (för detaljtabell)."""
    month_prefix = f"{year:04d}-{month:02d}"
    filtered = [e for e in events if e.time_start_utc.startswith(month_prefix)]
    # Sortera senast först
    filtered.sort(key=lambda e: e.time_start_utc, reverse=True)
    return filtered[:limit]


def get_daily_inverter_data(
    daily_records: list[InverterDaily],
    year: int,
    month: int,
) -> dict[str, dict[int, InverterDaily]]:
    """Returnera dict {inverter_name: {day: InverterDaily}} för månaden.

    Användbart för heatmap-rendering där vi behöver O(1) lookup per
    (inverter, day).
    """
    month_prefix = f"{year:04d}-{month:02d}"
    result: dict[str, dict[int, InverterDaily]] = defaultdict(dict)
    for r in daily_records:
        if not r.date.startswith(month_prefix):
            continue
        day = int(r.date.split("-")[2])
        result[r.inverter_name][day] = r
    return dict(result)
