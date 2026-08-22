"""Daglig puls — avvikelsedetektion över gårdagens data + kort digest.

Detta är produktens proaktiva del: i stället för att någon öppnar en
dashboard och letar, körs sex detektorer över det senaste dygnet och det
enda som rapporteras är det som faktiskt avviker. **Tom dag ger en lugn
rad, inte en rapport.**

Designprincip (docs/plans/2026-08-22-insikt-produkt-spec.md): slutsats i
klartext först — varje fynd formuleras som en mening med siffrorna i, inte
som en tabellrad att tolka.

Detektorer
==========

======================================  =========================================
``INVERTER_UNDERPERFORMANCE``           Inverter under ``UNDERPERF_RATIO`` av
                                        parkmedianen ≥ ``UNDERPERF_MIN_DAYS``
                                        dagar i rad t.o.m. D.
``STUCK_SIGNAL_NIGHT``                  "Nattvakts"-mönstret: inverter-fallback
                                        rapporterar effekt utan ljus (POA ≤ 5).
``MISSING_DATA``                        Parkens serie är för gammal eller dygnet
                                        har för få kvartar.
``PARK_YIELD_ANOMALY``                  Normal instrålning men onormalt låg
                                        yield mot parkens egna 30 dagar.
``ALARM_SURGE``                         Alarmvolym över golv/faktor, eller en
                                        alarmtyp som inte setts på 90 dagar.
``SOURCE_STALENESS``                    Marknadsdatakälla släpar mer än sin
                                        kända publiceringslagg (info-nivå).
======================================  =========================================

Struktur
========
Detektorerna är **rena funktioner** som tar färdig data som argument och
returnerar 0..N fynd::

    {"park", "severity": "warn"|"info", "rubrik", "text",
     "detector": <namn>, "value": {...}}

IO-lagret (``run_puls``) läser CSV via befintliga loaders, normaliserar och
anropar detektorerna. Alla trösklar är namngivna modulkonstanter längst upp
så de går att justera utan att läsa logiken.

API
===
* ``run_puls(date=None)`` → ``{"date", "findings", "summary", "clean", ...}``
* ``render_puls_html(result)`` → fristående HTML (Nordic Clarity-tokens)
* ``write_puls_html(result)`` → skriver ``Resultat/rapporter/puls/puls_<D>.html``
"""

from __future__ import annotations

import csv
import html
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from ..config import (
    ENTSOE_DATA_DIR,
    ESETT_DATA_DIR,
    PARK_CAPACITY_KWP,
    PARK_ZONES,
    RAW_DIR,
    REPORTS_DIR,
    SWEDEN_TZ,
    UTC_TZ,
    ZONES,
    parse_iso,
)

# ---------------------------------------------------------------------------
# Detektornamn
# ---------------------------------------------------------------------------

DETECTOR_INVERTER_UNDERPERFORMANCE = "INVERTER_UNDERPERFORMANCE"
DETECTOR_STUCK_SIGNAL_NIGHT = "STUCK_SIGNAL_NIGHT"
DETECTOR_MISSING_DATA = "MISSING_DATA"
DETECTOR_PARK_YIELD_ANOMALY = "PARK_YIELD_ANOMALY"
DETECTOR_ALARM_SURGE = "ALARM_SURGE"
DETECTOR_SOURCE_STALENESS = "SOURCE_STALENESS"

# ---------------------------------------------------------------------------
# Trösklar (alla justerbara utan att röra logiken)
# ---------------------------------------------------------------------------

QUARTER_HOURS = 0.25
DAY_QUARTERS = 96

# 1. INVERTER_UNDERPERFORMANCE
UNDERPERF_RATIO = 0.70            # andel av parkmedianen som är "ok"
UNDERPERF_MIN_DAYS = 3            # sammanhängande dagar innan larm
UNDERPERF_MIN_MEDIAN_YIELD = 0.5  # kWh/kW — mörkare dagar ger brus, hoppas över
UNDERPERF_LOOKBACK_DAYS = 21      # hur långt bak en streak får sträcka sig
UNDERPERF_MIN_PEERS = 3           # minsta antal invertrar för en meningsfull median
# Datakvalitetsvakt: ett dygn kan fysiskt inte ge mer än ~9 kWh/kW i Sverige
# (klarblå junidag). Bazefield-serien innehåller ändå rader på 15-24 kWh/kW
# (t.ex. björke TS2 2026-05-02: 5 657 kWh på 251 kW = CF 94 %) — sannolikt
# räknarvärden i stället för dygnsdelta. Sådana rader skulle blåsa upp
# parkmedianen och göra friska invertrar till "underpresterande", så de
# lyfts ur jämförelsen.
UNDERPERF_MAX_PLAUSIBLE_YIELD = 12.0  # kWh/kW per dygn

# 2. STUCK_SIGNAL_NIGHT ("nattvakten", jfr insikt/obalans.energies_from_records)
STUCK_NIGHT_POA_WM2 = 5.0         # W/m² — under detta finns inget ljus
STUCK_MIN_POWER_MW = 0.01         # MW — under detta är det mätbrus
STUCK_MIN_QUARTERS = 8            # 8 kvartar = 2 h sammanhängande

# 3. MISSING_DATA
MISSING_MAX_AGE_HOURS = 36.0      # senaste timestamp får vara så här gammal
MISSING_MIN_QUARTERS = 80         # av 96 kvartar på dygnet

# 4. PARK_YIELD_ANOMALY
YIELD_BASELINE_DAYS = 30          # jämförelsefönster (parkens egna dagar)
YIELD_MIN_BASELINE_DAYS = 10      # minsta antal dagar för en median
YIELD_POA_TOLERANCE = 0.20        # ±20 % instrålning = "samma väder"
YIELD_ANOMALY_RATIO = 0.60        # under 60 % av medianyielden = larm
YIELD_MIN_BASELINE_KWH_KWP = 0.5  # vintermörker → ingen slutsats
POA_MIN_QUARTERS = 80             # kvartar med POA-värde för att lita på dygnssumman

# 5. ALARM_SURGE
ALARM_BASELINE_DAYS = 30
ALARM_SURGE_MIN = 10              # golv: färre alarm än så är aldrig en surge
ALARM_SURGE_FACTOR = 3.0          # ... eller 3× dagligt medel, det högsta gäller
ALARM_NEW_TYPE_DAYS = 90          # "ny typ" = osedd i så här många dagar
ALARM_MIN_HISTORY_DAYS = 30       # utan historik går inget att kalla nytt
ALARM_TOP_TYPES = 3               # antal topptyper i texten

# 6. SOURCE_STALENESS — känd publiceringslagg per källa (dagar bakåt från D)
SOURCE_LAG_DAYS: Dict[str, int] = {
    "spot": 0,        # specialfall, se expected_source_date()
    "esett": 2,       # eSett publicerar avräkning med ~2 dygns lagg
    "temperatur": 5,  # ERA5-reanalysen släpar ~5 dygn — annars falsklarm dagligen
    "entsoe": 2,      # ENTSO-E korrigerar och efterpublicerar
}
SPOT_PUBLISH_HOUR = 13  # dagen-före-auktionen är ute ~13:00 svensk tid

PULS_DIR = REPORTS_DIR / "puls"


# ---------------------------------------------------------------------------
# Formatering
# ---------------------------------------------------------------------------

def _fmt(value: float, dec: int = 1) -> str:
    """Svensk talformatering: mellanslag som tusenavskiljare, decimalkomma."""
    s = f"{value:,.{dec}f}"
    return s.replace(",", " ").replace(".", ",")


def _park_name(park_key: str) -> str:
    return park_key.capitalize()


def _finding(park: Optional[str], severity: str, rubrik: str, text: str,
             detector: str, value: dict) -> dict:
    return {
        "park": park,
        "severity": severity,
        "rubrik": rubrik,
        "text": text,
        "detector": detector,
        "value": value,
    }


def _dates_back(day: date, n: int) -> List[str]:
    """ISO-datum för de n dygnen FÖRE ``day`` (äldst först)."""
    return [(day - timedelta(days=i)).isoformat() for i in range(n, 0, -1)]


# ---------------------------------------------------------------------------
# 1. INVERTER_UNDERPERFORMANCE
# ---------------------------------------------------------------------------

def detect_inverter_underperformance(
    park: str,
    rows: Sequence[dict],
    day: date,
) -> List[dict]:
    """Invertrar som legat under parkmedianen flera dagar i rad.

    Args:
        park: parknyckel.
        rows: ``[{"date": "YYYY-MM-DD", "inverter": str,
                  "energy_kwh": float, "rated_kw": float|None}, ...]``.
            Märkeffekten normaliserar till kWh/kW så olika stora invertrar
            kan jämföras; saknas den används rå energi (ratio mot medianen
            blir densamma när invertrarna är lika stora).
        day: dygnet som rapporteras (D).

    Returns:
        Ett fynd per inverter med streak ≥ ``UNDERPERF_MIN_DAYS``.

    Metod:
        Dagar där parkmedianen understiger ``UNDERPERF_MIN_MEDIAN_YIELD``
        (mörka vinterdagar) räknas varken som bra eller dålig dag — de
        hoppas över helt, så en streak kan sträcka sig förbi dem. Streaken
        måste sluta på D; saknas D-data är detektorn tyst (då äger
        ``MISSING_DATA`` fallet).
    """
    by_date: Dict[str, Dict[str, dict]] = defaultdict(dict)
    for row in rows:
        rated = row.get("rated_kw") or 0.0
        energy = float(row.get("energy_kwh") or 0.0)
        spec = energy / rated if rated > 0 else energy
        if rated > 0 and spec > UNDERPERF_MAX_PLAUSIBLE_YIELD:
            continue  # sensor-/räknarfel, se UNDERPERF_MAX_PLAUSIBLE_YIELD
        by_date[row["date"]][row["inverter"]] = {
            "spec": spec,
            "rated_kw": rated if rated > 0 else 1.0,
        }

    day_key = day.isoformat()
    window = [
        d for d in _dates_back(day, UNDERPERF_LOOKBACK_DAYS) if d in by_date
    ]
    window.append(day_key)

    evaluable: List[tuple] = []  # (datum, median, {inverter: data}) — nyast först
    for d in reversed(window):
        inv_map = by_date.get(d) or {}
        if len(inv_map) < UNDERPERF_MIN_PEERS:
            continue
        median = statistics.median(v["spec"] for v in inv_map.values())
        if median < UNDERPERF_MIN_MEDIAN_YIELD:
            continue  # för mörk dag — säger inget om invertrarnas hälsa
        evaluable.append((d, median, inv_map))

    if not evaluable or evaluable[0][0] != day_key:
        return []

    findings: List[dict] = []
    for inv_name in sorted(evaluable[0][2]):
        streak_days = 0
        lost_kwh = 0.0
        latest_ratio = None
        latest_spec = None
        latest_median = None
        for d, median, inv_map in evaluable:
            data = inv_map.get(inv_name)
            if data is None:
                break
            ratio = data["spec"] / median if median > 0 else 1.0
            if ratio >= UNDERPERF_RATIO:
                break
            if latest_ratio is None:
                latest_ratio, latest_spec, latest_median = ratio, data["spec"], median
            streak_days += 1
            lost_kwh += max(0.0, median - data["spec"]) * data["rated_kw"]

        if streak_days < UNDERPERF_MIN_DAYS:
            continue

        findings.append(_finding(
            park=park,
            severity="warn",
            rubrik=f"{_park_name(park)}: {inv_name} underpresterar",
            text=(
                f"{inv_name} har legat på {_fmt(latest_ratio * 100, 0)} % av "
                f"parkmedianen {streak_days} dagar i rad "
                f"({_fmt(latest_spec, 2)} mot {_fmt(latest_median, 2)} kWh/kW "
                f"senast). Uppskattat bortfall under perioden: "
                f"{_fmt(lost_kwh, 0)} kWh."
            ),
            detector=DETECTOR_INVERTER_UNDERPERFORMANCE,
            value={
                "inverter": inv_name,
                "days": streak_days,
                "ratio_pct": round(latest_ratio * 100, 1),
                "lost_kwh": round(lost_kwh, 1),
            },
        ))

    return findings


# ---------------------------------------------------------------------------
# 2. STUCK_SIGNAL_NIGHT
# ---------------------------------------------------------------------------

def detect_stuck_signal_night(
    park: str,
    quarters: Sequence[dict],
    day: date,
) -> List[dict]:
    """Nattvakten: inverter-fallback som rapporterar effekt utan ljus.

    Args:
        park: parknyckel.
        quarters: dygnets kvartar, tidsordnade, som
            ``{"timestamp_utc", "meter_mw", "inverter_mw", "poa"}``.
            Mätarsignalen litas alltid på; bara kvartar där mätaren saknas
            och POA ≤ ``STUCK_NIGHT_POA_WM2`` kan flaggas.
        day: dygnet som rapporteras.

    Returns:
        Högst ett fynd per park, med total fantomenergi (MWh) i de
        sammanhängande körningar som är ≥ ``STUCK_MIN_QUARTERS``.
    """
    flags = []
    for q in quarters:
        meter = q.get("meter_mw") or 0.0
        inv = q.get("inverter_mw")
        poa = q.get("poa")
        flagged = (
            meter <= 0
            and inv is not None
            and inv > STUCK_MIN_POWER_MW
            and poa is not None
            and poa <= STUCK_NIGHT_POA_WM2
        )
        flags.append((flagged, inv or 0.0, q.get("timestamp_utc")))

    runs: List[List[tuple]] = []
    current: List[tuple] = []
    for entry in flags:
        if entry[0]:
            current.append(entry)
        else:
            if len(current) >= STUCK_MIN_QUARTERS:
                runs.append(current)
            current = []
    if len(current) >= STUCK_MIN_QUARTERS:
        runs.append(current)

    if not runs:
        return []

    phantom_mwh = sum(e[1] * QUARTER_HOURS for run in runs for e in run)
    longest = max(len(run) for run in runs)
    total_quarters = sum(len(run) for run in runs)

    first_ts = runs[0][0][2]
    when = ""
    if isinstance(first_ts, datetime):
        when = f" från {first_ts.astimezone(SWEDEN_TZ).strftime('%H:%M')}"

    return [_finding(
        park=park,
        severity="warn",
        rubrik=f"{_park_name(park)}: fastnad inverter-signal i mörker",
        text=(
            f"{total_quarters} kvartar ({_fmt(total_quarters * QUARTER_HOURS, 1)} h"
            f"{when}) rapporterade produktion utan mätarsignal och med "
            f"POA ≤ {_fmt(STUCK_NIGHT_POA_WM2, 0)} W/m² — fysiskt omöjligt. "
            f"Det motsvarar {_fmt(phantom_mwh, 2)} MWh fantomenergi som annars "
            f"följer med in i yield och obalansberäkning."
        ),
        detector=DETECTOR_STUCK_SIGNAL_NIGHT,
        value={
            "phantom_mwh": round(phantom_mwh, 3),
            "quarters": total_quarters,
            "longest_run": longest,
            "date": day.isoformat(),
        },
    )]


# ---------------------------------------------------------------------------
# 3. MISSING_DATA
# ---------------------------------------------------------------------------

def detect_missing_data(
    park: str,
    last_timestamp: Optional[datetime],
    quarter_count: int,
    day: date,
) -> List[dict]:
    """Parkserie som har slutat komma in, eller ett dygn med hål.

    Args:
        park: parknyckel.
        last_timestamp: senaste tidstämpel i parkens CSV (tz-aware) eller
            ``None`` om filen saknas/är tom.
        quarter_count: antal kvartar för dygn D i CSV:n (av 96).
        day: dygnet som rapporteras.
    """
    day_end = datetime(day.year, day.month, day.day, tzinfo=SWEDEN_TZ) + timedelta(days=1)

    if last_timestamp is None:
        return [_finding(
            park=park,
            severity="warn",
            rubrik=f"{_park_name(park)}: ingen data",
            text=(
                f"Parkens 15-min-serie är tom eller saknas — inget kunde "
                f"utvärderas för {day.isoformat()}."
            ),
            detector=DETECTOR_MISSING_DATA,
            value={"last_timestamp": None, "quarters": quarter_count,
                   "age_hours": None},
        )]

    age_hours = (day_end - last_timestamp).total_seconds() / 3600.0
    stale = age_hours > MISSING_MAX_AGE_HOURS
    thin = quarter_count < MISSING_MIN_QUARTERS
    if not stale and not thin:
        return []

    last_local = last_timestamp.astimezone(SWEDEN_TZ)
    if stale:
        text = (
            f"Senaste mätvärdet är från {last_local.strftime('%Y-%m-%d %H:%M')} — "
            f"{_fmt(age_hours, 0)} h gammalt (gräns "
            f"{_fmt(MISSING_MAX_AGE_HOURS, 0)} h). Dygnet har "
            f"{quarter_count} av {DAY_QUARTERS} kvartar; synken behöver köras om."
        )
        rubrik = f"{_park_name(park)}: data släpar"
    else:
        text = (
            f"Bara {quarter_count} av {DAY_QUARTERS} kvartar finns för dygnet "
            f"({_fmt(100.0 * quarter_count / DAY_QUARTERS, 0)} % täckning). "
            f"Yield och capture för dagen är underskattade."
        )
        rubrik = f"{_park_name(park)}: hål i dygnet"

    return [_finding(
        park=park,
        severity="warn",
        rubrik=rubrik,
        text=text,
        detector=DETECTOR_MISSING_DATA,
        value={
            "last_timestamp": last_local.isoformat(),
            "quarters": quarter_count,
            "age_hours": round(age_hours, 1),
        },
    )]


# ---------------------------------------------------------------------------
# 4. PARK_YIELD_ANOMALY
# ---------------------------------------------------------------------------

def detect_park_yield_anomaly(
    park: str,
    daily: Sequence[dict],
    day: date,
) -> List[dict]:
    """Normal instrålning men onormalt låg yield — enkel väderjustering.

    Args:
        park: parknyckel.
        daily: dygnsserie ``[{"date", "yield_kwh_kwp", "poa_wh_m2"}, ...]``
            (se :func:`summarize_park_days`).
        day: dygnet som rapporteras.

    Metod:
        Jämför D mot medianen av parkens egna ``YIELD_BASELINE_DAYS``
        föregående dygn. Larmar bara när instrålningen för D ligger inom
        ±``YIELD_POA_TOLERANCE`` av baslinjens median (samma väder) men
        yielden ändå är under ``YIELD_ANOMALY_RATIO``. Ingen PVsyst- eller
        modellkoppling — parken jämförs med sig själv.
    """
    by_date = {row["date"]: row for row in daily}
    today = by_date.get(day.isoformat())
    if not today:
        return []
    y_today = today.get("yield_kwh_kwp")
    poa_today = today.get("poa_wh_m2")
    if y_today is None or poa_today is None:
        return []

    baseline = [
        by_date[d] for d in _dates_back(day, YIELD_BASELINE_DAYS)
        if d in by_date
        and by_date[d].get("yield_kwh_kwp") is not None
        and by_date[d].get("poa_wh_m2") is not None
    ]
    if len(baseline) < YIELD_MIN_BASELINE_DAYS:
        return []

    med_yield = statistics.median(r["yield_kwh_kwp"] for r in baseline)
    med_poa = statistics.median(r["poa_wh_m2"] for r in baseline)
    if med_yield < YIELD_MIN_BASELINE_KWH_KWP or med_poa <= 0:
        return []

    poa_dev = poa_today / med_poa - 1.0
    if abs(poa_dev) > YIELD_POA_TOLERANCE:
        return []  # vädret förklarar dagen

    yield_ratio = y_today / med_yield
    if yield_ratio >= YIELD_ANOMALY_RATIO:
        return []

    return [_finding(
        park=park,
        severity="warn",
        rubrik=f"{_park_name(park)}: låg yield trots normalt väder",
        text=(
            f"Dygnet gav {_fmt(y_today, 2)} kWh/kWp — "
            f"{_fmt(yield_ratio * 100, 0)} % av parkens 30-dagarsmedian "
            f"({_fmt(med_yield, 2)}), samtidigt som instrålningen låg "
            f"{_fmt(abs(poa_dev) * 100, 0)} % "
            f"{'över' if poa_dev >= 0 else 'under'} medianen. Vädret förklarar "
            f"inte tappet — kolla tillgänglighet och inverterlarm."
        ),
        detector=DETECTOR_PARK_YIELD_ANOMALY,
        value={
            "yield_kwh_kwp": round(y_today, 3),
            "median_yield_kwh_kwp": round(med_yield, 3),
            "yield_ratio_pct": round(yield_ratio * 100, 1),
            "poa_dev_pct": round(poa_dev * 100, 1),
            "baseline_days": len(baseline),
        },
    )]


# ---------------------------------------------------------------------------
# 5. ALARM_SURGE
# ---------------------------------------------------------------------------

def detect_alarm_surge(
    park: str,
    events: Sequence[dict],
    day: date,
) -> List[dict]:
    """Ovanligt många alarm — eller en alarmtyp som inte setts på länge.

    Args:
        park: parknyckel.
        events: ``[{"date": "YYYY-MM-DD", "event_name": str}, ...]``.
        day: dygnet som rapporteras.

    Returns:
        Upp till två fynd: volymspik (``kind == "volym"``) och/eller ny
        alarmtyp (``kind == "ny typ"``). Utan minst
        ``ALARM_MIN_HISTORY_DAYS`` historik är detektorn tyst — då vore
        allt "nytt".
    """
    if not events:
        return []

    day_key = day.isoformat()
    dates = sorted({e["date"] for e in events})
    try:
        earliest = date.fromisoformat(dates[0])
    except ValueError:
        return []
    if (day - earliest).days < ALARM_MIN_HISTORY_DAYS:
        return []

    today_events = [e for e in events if e["date"] == day_key]
    baseline_dates = set(_dates_back(day, ALARM_BASELINE_DAYS))
    baseline_count = sum(1 for e in events if e["date"] in baseline_dates)
    mean_per_day = baseline_count / ALARM_BASELINE_DAYS
    threshold = max(float(ALARM_SURGE_MIN), ALARM_SURGE_FACTOR * mean_per_day)

    findings: List[dict] = []
    count = len(today_events)
    if count > threshold:
        top = Counter(e["event_name"] for e in today_events).most_common(ALARM_TOP_TYPES)
        top_text = ", ".join(f"{name} ({n})" for name, n in top)
        findings.append(_finding(
            park=park,
            severity="warn",
            rubrik=f"{_park_name(park)}: alarmspik",
            text=(
                f"{count} alarm under dygnet mot normalt "
                f"{_fmt(mean_per_day, 1)}/dygn senaste {ALARM_BASELINE_DAYS} "
                f"dagarna (larmgräns {_fmt(threshold, 1)}). Vanligast: {top_text}."
            ),
            detector=DETECTOR_ALARM_SURGE,
            value={
                "kind": "volym",
                "count": count,
                "mean_per_day": round(mean_per_day, 2),
                "threshold": round(threshold, 2),
                "top_types": top,
            },
        ))

    history_dates = set(_dates_back(day, ALARM_NEW_TYPE_DAYS))
    seen_before = {e["event_name"] for e in events if e["date"] in history_dates}
    new_types = sorted({e["event_name"] for e in today_events} - seen_before)
    if new_types:
        counts = Counter(e["event_name"] for e in today_events)
        listed = ", ".join(f"{n} ({counts[n]})" for n in new_types[:ALARM_TOP_TYPES])
        findings.append(_finding(
            park=park,
            severity="warn",
            rubrik=f"{_park_name(park)}: ny alarmtyp",
            text=(
                f"{listed} har inte förekommit på {ALARM_NEW_TYPE_DAYS} dagar. "
                f"Ny felbild är oftare en verklig förändring än brus."
            ),
            detector=DETECTOR_ALARM_SURGE,
            value={"kind": "ny typ", "types": new_types,
                   "counts": {n: counts[n] for n in new_types}},
        ))

    return findings


# ---------------------------------------------------------------------------
# 6. SOURCE_STALENESS
# ---------------------------------------------------------------------------

def expected_source_date(source: str, day: date,
                         now: Optional[datetime] = None) -> date:
    """Senaste datum en källa RIMLIGEN ska ha när pulsen körs för ``day``.

    Spotpriser publiceras i dagen-före-auktionen ~13:00 svensk tid: efter
    den tidpunkten ska D+1 finnas, dessförinnan bara D. Övriga källor har
    en fast lagg i ``SOURCE_LAG_DAYS`` — särskilt temperaturen (ERA5,
    ~5 dygn) måste ha rätt lagg, annars larmar pulsen varje dag i onödan.
    """
    if source == "spot":
        ref = now or datetime.now(SWEDEN_TZ)
        local = ref.astimezone(SWEDEN_TZ)
        return day + timedelta(days=1 if local.hour >= SPOT_PUBLISH_HOUR else 0)
    return day - timedelta(days=SOURCE_LAG_DAYS.get(source, 1))


def detect_source_staleness(
    sources: Sequence[dict],
    day: date,
    now: Optional[datetime] = None,
) -> List[dict]:
    """Marknadsdatakällor som släpar mer än sin kända publiceringslagg.

    Args:
        sources: ``[{"source", "label", "scope", "latest_date": date|None}]``.
        day: dygnet som rapporteras.
        now: körtidpunkt (styr spotpris-förväntan).

    Returns:
        En info-rad per källa som släpar. ``park`` är ``None``.
    """
    findings: List[dict] = []
    for src in sources:
        key = src["source"]
        expected = expected_source_date(key, day, now)
        latest = src.get("latest_date")
        label = src.get("label", key)
        scope = src.get("scope", "")
        scope_txt = f" ({scope})" if scope else ""

        if latest is None:
            findings.append(_finding(
                park=None,
                severity="info",
                rubrik=f"{label}{scope_txt} saknas",
                text=(
                    f"Ingen data hittades för {label.lower()}{scope_txt}. "
                    f"Förväntat t.o.m. {expected.isoformat()}."
                ),
                detector=DETECTOR_SOURCE_STALENESS,
                value={"source": key, "scope": scope, "latest_date": None,
                       "expected_date": expected.isoformat(), "days_behind": None},
            ))
            continue

        if latest >= expected:
            continue

        days_behind = (expected - latest).days
        findings.append(_finding(
            park=None,
            severity="info",
            rubrik=f"{label}{scope_txt} släpar",
            text=(
                f"Senaste datum är {latest.isoformat()}, "
                f"{_plural(days_behind, 'dag', 'dagar')} efter förväntat "
                f"({expected.isoformat()}). Analyser som bygger på källan "
                f"täcker inte gårdagen."
            ),
            detector=DETECTOR_SOURCE_STALENESS,
            value={"source": key, "scope": scope,
                   "latest_date": latest.isoformat(),
                   "expected_date": expected.isoformat(),
                   "days_behind": days_behind},
        ))
    return findings


# ---------------------------------------------------------------------------
# Dygnsaggregat ur 15-min-serien
# ---------------------------------------------------------------------------

def summarize_park_days(records: Iterable[dict],
                        capacity_kwp: Optional[float]) -> List[dict]:
    """Aggregera ``load_park_15min``-records till dygn i svensk lokaltid.

    Returns:
        ``[{"date", "quarters", "yield_kwh_kwp", "poa_wh_m2"}, ...]``
        sorterad på datum. ``poa_wh_m2`` sätts bara när minst
        ``POA_MIN_QUARTERS`` kvartar har ett POA-värde (annars vore
        dygnssumman missvisande låg).
    """
    acc: Dict[str, dict] = defaultdict(
        lambda: {"energy_mwh": 0.0, "poa_sum": 0.0, "poa_n": 0, "quarters": 0}
    )
    for rec in records:
        local_day = rec["timestamp_utc"].astimezone(SWEDEN_TZ).date().isoformat()
        bucket = acc[local_day]
        bucket["energy_mwh"] += rec.get("effective_power_mw", 0.0) * QUARTER_HOURS
        bucket["quarters"] += 1
        poa = rec.get("irradiance_poa")
        if poa is not None:
            bucket["poa_sum"] += poa * QUARTER_HOURS
            bucket["poa_n"] += 1

    out: List[dict] = []
    for day_key in sorted(acc):
        bucket = acc[day_key]
        mwp = (capacity_kwp / 1000.0) if capacity_kwp else None
        out.append({
            "date": day_key,
            "quarters": bucket["quarters"],
            "yield_kwh_kwp": (bucket["energy_mwh"] / mwp) if mwp else None,
            "poa_wh_m2": (bucket["poa_sum"]
                          if bucket["poa_n"] >= POA_MIN_QUARTERS else None),
        })
    return out


# ---------------------------------------------------------------------------
# Sammanfattning
# ---------------------------------------------------------------------------

def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def build_summary(findings: Sequence[dict], park_count: int) -> str:
    """En mening som räcker om man bara läser en rad."""
    if not findings:
        return (
            f"Inga avvikelser — alla {park_count} parker och datakällor "
            f"ser normala ut"
        )

    parks = {f["park"] for f in findings if f.get("park")}
    sources = [f for f in findings
               if f.get("detector") == DETECTOR_SOURCE_STALENESS]

    parts: List[str] = []
    if parks:
        parts.append(_plural(len(parks), "park", "parker"))
    if sources:
        parts.append(_plural(len(sources), "datakälla", "datakällor"))

    head = _plural(len(findings), "avvikelse", "avvikelser")
    return f"{head}: {', '.join(parts)}" if parts else head


# ---------------------------------------------------------------------------
# IO-lager
# ---------------------------------------------------------------------------

def _latest_date_in_dir(directory: Path, pattern: str,
                        column: str) -> Optional[date]:
    """Senaste datum i den sist sorterade CSV:n som matchar ``pattern``."""
    if not directory.is_dir():
        return None
    files = sorted(directory.glob(pattern))
    if not files:
        return None
    latest: Optional[date] = None
    # Sista filen räcker normalt (filer är per år), men en tom sista fil
    # ska inte dölja data i den näst sista.
    for path in reversed(files[-2:]):
        for row in _read_csv(path):
            value = row.get(column)
            if not value:
                continue
            try:
                ts = parse_iso(value)
            except ValueError:
                continue
            d = ts.astimezone(SWEDEN_TZ).date() if ts.tzinfo else ts.date()
            if latest is None or d > latest:
                latest = d
        if latest is not None:
            return latest
    return latest


def _read_csv(path: Path) -> List[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def collect_source_status(day: date) -> List[dict]:
    """Senaste datum per marknadsdatakälla, grupperat per zon-uppsättning.

    Zoner som ligger på samma datum slås ihop till en rad, så en generellt
    släpande källa ger en rad i stället för fyra.
    """
    def _grouped(source: str, label: str,
                 per_zone: Dict[str, Optional[date]]) -> List[dict]:
        by_date: Dict[Optional[str], List[str]] = defaultdict(list)
        for zone in ZONES:
            d = per_zone.get(zone)
            by_date[d.isoformat() if d else None].append(zone)
        rows = []
        for key, zones in by_date.items():
            rows.append({
                "source": source,
                "label": label,
                "scope": ", ".join(zones) if len(zones) < len(ZONES) else "SE1-SE4",
                "latest_date": date.fromisoformat(key) if key else None,
            })
        return rows

    sources: List[dict] = []

    spot = {z: _latest_date_in_dir(RAW_DIR / z, "*.csv", "time_start")
            for z in ZONES}
    sources += _grouped("spot", "Spotpriser", spot)

    esett = {z: _latest_date_in_dir(ESETT_DATA_DIR / "imbalance" / z,
                                    "*.csv", "time_start") for z in ZONES}
    sources += _grouped("esett", "eSett obalanspriser", esett)

    entsoe = {z: _latest_date_in_dir(ENTSOE_DATA_DIR / "generation" / z,
                                     "solar_*.csv", "time_start") for z in ZONES}
    sources += _grouped("entsoe", "ENTSO-E solproduktion", entsoe)

    from ..temperature import TEMPERATURE_DATA_DIR
    temp_dates = []
    for park in sorted(PARK_ZONES):
        d = _latest_date_in_dir(TEMPERATURE_DATA_DIR, f"{park}.csv", "timestamp")
        temp_dates.append(d)
    worst = None if any(d is None for d in temp_dates) else min(temp_dates)
    sources.append({
        "source": "temperatur",
        "label": "Temperatur (ERA5)",
        "scope": f"{len(temp_dates)} parker",
        "latest_date": worst,
    })

    return sources


def _park_findings(park: str, day: date) -> List[dict]:
    """Kör alla parkdetektorer för en park (IO + normalisering)."""
    from ..inverter_data import load_alarm_events, load_inverter_yield
    from ..operations_dashboard_data import load_park_15min

    findings: List[dict] = []
    records = load_park_15min(park)

    day_key = day.isoformat()
    day_records = [
        r for r in records
        if r["timestamp_utc"].astimezone(SWEDEN_TZ).date().isoformat() == day_key
    ]
    last_ts = max((r["timestamp_utc"] for r in records), default=None)

    findings += detect_missing_data(park, last_ts, len(day_records), day)

    if day_records:
        quarters = [{
            "timestamp_utc": r["timestamp_utc"],
            "meter_mw": r.get("power_mw", 0.0),
            "inverter_mw": r.get("active_power_mw"),
            "poa": r.get("irradiance_poa"),
        } for r in sorted(day_records, key=lambda r: r["timestamp_utc"])]
        findings += detect_stuck_signal_night(park, quarters, day)

        daily = summarize_park_days(records, PARK_CAPACITY_KWP.get(park))
        findings += detect_park_yield_anomaly(park, daily, day)

    inverter_rows = [{
        "date": r.date,
        "inverter": r.inverter_name,
        "energy_kwh": r.energy_kwh,
        "rated_kw": r.rated_kw,
    } for r in load_inverter_yield(park)]
    if inverter_rows:
        findings += detect_inverter_underperformance(park, inverter_rows, day)

    events = [{"date": e.time_start_utc[:10], "event_name": e.event_name}
              for e in load_alarm_events(park) if e.time_start_utc]
    if events:
        findings += detect_alarm_surge(park, events, day)

    return findings


_SEVERITY_ORDER = {"warn": 0, "info": 1}


def run_puls(date=None) -> dict:
    """Kör hela pulsen för ett dygn.

    Args:
        date: ``datetime.date`` eller ``"YYYY-MM-DD"``. Default: igår
            i svensk lokaltid.

    Returns:
        ``{"date", "findings", "summary", "clean", "generated_at",
        "park_count"}``.
    """
    now = datetime.now(SWEDEN_TZ)
    if date is None:
        day = now.date() - timedelta(days=1)
    elif isinstance(date, str):
        day = datetime.strptime(date, "%Y-%m-%d").date()
    elif isinstance(date, datetime):
        day = date.astimezone(SWEDEN_TZ).date()
    else:
        day = date

    findings: List[dict] = []
    for park in sorted(PARK_ZONES):
        findings += _park_findings(park, day)

    findings += detect_source_staleness(collect_source_status(day), day, now)

    findings.sort(key=lambda f: (
        _SEVERITY_ORDER.get(f["severity"], 9),
        f.get("park") or "￿",
        f["detector"],
    ))

    return {
        "date": day.isoformat(),
        "findings": findings,
        "summary": build_summary(findings, len(PARK_ZONES)),
        "clean": not findings,
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "park_count": len(PARK_ZONES),
    }


# ---------------------------------------------------------------------------
# Rendering — minimal fristående HTML (Nordic Clarity-tokens)
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --bg: #f6f8f9; --card: #ffffff; --ink: #16242f; --muted: #5b6b78;
  --faint: #8a98a4; --line: #e3e9ed; --teal: #0e7c86; --teal-deep: #0a5961;
  --teal-soft: #d8ecee; --amber: #de9b26; --coral: #d95f4c; --green: #2e9e6b;
  --radius: 10px;
  --shadow: 0 1px 2px rgba(22,36,47,.05), 0 4px 16px rgba(22,36,47,.06);
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14.5px; line-height: 1.55; -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 780px; margin: 0 auto; padding: 32px 24px 56px; }
.eyebrow {
  font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
  color: var(--faint); font-weight: 600;
}
h1 { font-size: 26px; margin: 6px 0 2px; letter-spacing: -.01em; }
.sub { color: var(--muted); font-size: 12.5px; margin-bottom: 22px; }
.verdict {
  background: var(--card); border: 1px solid var(--line); border-left: 4px solid var(--teal);
  border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 18px 20px; font-size: 17px; font-weight: 600; letter-spacing: -.01em;
}
.verdict.clean { border-left-color: var(--green); }
.verdict.warn { border-left-color: var(--coral); }
h2 {
  font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
  color: var(--muted); margin: 30px 0 10px; font-weight: 700;
}
.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 14px 16px; margin-bottom: 10px; border-left: 3px solid var(--line);
}
.card.warn { border-left-color: var(--coral); }
.card.info { border-left-color: var(--amber); }
.card h3 { margin: 0 0 4px; font-size: 14.5px; letter-spacing: -.005em; }
.card p { margin: 0; color: var(--muted); }
.tag {
  display: inline-block; margin-left: 8px; padding: 1px 7px; border-radius: 999px;
  background: var(--teal-soft); color: var(--teal-deep);
  font-size: 10px; letter-spacing: .08em; text-transform: uppercase;
  font-weight: 700; vertical-align: 2px;
}
.foot { margin-top: 30px; color: var(--faint); font-size: 11.5px; }
"""

_SHELL = """<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daglig puls {date}</title>
<style>{css}</style>
</head>
<body>
<div class="wrap">
  <div class="eyebrow">Insikt · Daglig puls</div>
  <h1>{date}</h1>
  <div class="sub">Genererad {generated_at} · {park_count} parker · 6 detektorer</div>
  <div class="verdict {verdict_class}">{summary}</div>
{body}
  <div class="foot">
    Detektorer: inverter-underprestation, fastnad nattsignal, saknad data,
    yield-avvikelse mot eget 30-dagarsfönster, alarmspik, källor som släpar.
    Trösklar dokumenterade i <code>elpris/insikt/puls.py</code>.
  </div>
</div>
</body>
</html>
"""


def _esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def _cards(findings: Sequence[dict]) -> str:
    parts = []
    for f in findings:
        sev = f.get("severity", "info")
        tag = f"<span class=\"tag\">{_esc(f.get('detector', ''))}</span>"
        parts.append(
            f'  <div class="card {sev}">\n'
            f'    <h3>{_esc(f.get("rubrik", ""))}{tag}</h3>\n'
            f'    <p>{_esc(f.get("text", ""))}</p>\n'
            f'  </div>'
        )
    return "\n".join(parts)


def render_puls_html(result: dict) -> str:
    """Rendera pulsen som fristående HTML — ingen JS, inga externa beroenden."""
    findings = result.get("findings") or []
    warns = [f for f in findings if f.get("severity") == "warn"]
    infos = [f for f in findings if f.get("severity") != "warn"]

    sections: List[str] = []
    if warns:
        sections.append("  <h2>Att åtgärda</h2>\n" + _cards(warns))
    if infos:
        sections.append("  <h2>Att hålla ögonen på</h2>\n" + _cards(infos))
    if not findings:
        sections.append(
            '  <div class="card">\n'
            '    <p>Ingen detektor slog till. Ingen rapport behövs — '
            'parkerna och datakällorna betedde sig som väntat.</p>\n'
            '  </div>'
        )

    verdict_class = "clean" if result.get("clean") else ("warn" if warns else "")

    return _SHELL.format(
        date=_esc(result.get("date", "")),
        css=_CSS,
        generated_at=_esc(result.get("generated_at", "")),
        park_count=result.get("park_count", len(PARK_ZONES)),
        verdict_class=verdict_class,
        summary=_esc(result.get("summary", "")),
        body="\n" + "\n".join(sections) + "\n",
    )


def write_puls_html(result: dict, out_dir: Optional[Path] = None) -> Path:
    """Skriv pulsen till ``Resultat/rapporter/puls/puls_YYYY-MM-DD.html``."""
    target_dir = out_dir or PULS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"puls_{result['date']}.html"
    path.write_text(render_puls_html(result), encoding="utf-8")
    return path
