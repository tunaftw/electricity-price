# Assets Tab — Ambitious Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transformera Assets-fliken från en operations-vy till en komplett asset-management-vy som tillgodoser både investerare (revenue, realized capture, forward visibility) och teknisk asset manager (PR, availability, loss-waterfall, data freshness), genom att bubbla upp data som redan beräknas i backend men inte exponeras i Assets-fliken idag.

**Architecture:** Tre lager: (1) backend `unified_dashboard_data.py` utökas med nya fält per park-månad och en ny modul `park_revenue.py` för realiserad capture/revenue. (2) Frontend `unified_dashboard_v3_html.py` utökas i tre block: fleet KPIs/tabell, drilldown, samt CAPTURE-fliken. (3) Park-metadata exponeras för "About this park"-panel. All ny data är JSON-serialiserbar och bygger på existerande beräkningar (`performance_report_data`, `operations_dashboard_data`); inga nya externa beroenden.

**Tech Stack:** Python 3 (stdlib + dataclasses), JavaScript (vanilla + Plotly 2.35), SVG för waterfalls, befintlig CSS i `unified_dashboard_v3_html.py`.

---

## Designprinciper (för utförare)

1. **Backend först, frontend sedan.** Varje frontend-task antar att backend-fältet finns. Bryt aldrig denna ordning.
2. **JSON-fält är None-tolerant.** Saknas data ska frontend visa "–" gracefully, aldrig krascha.
3. **Återanvänd existerande färgsystem.** `--good`, `--warn`, `--bad` (vsClass), Nordic Editorial-paletten.
4. **Ingen breaking change.** Existerande fält behålls. Nya fält är additiva.
5. **Commit per task.** Små, granskningsbara commits.
6. **Verifiering:** Kör `python3 generate_unified_dashboard.py` efter varje fas och öppna HTML-filen i webbläsare.

---

## Phase 0 — Förberedelser

### Task 0.1: Snabb sanity-check att test-rigg fungerar

**Steg:**

```bash
cd /Users/pontusskog/Documents/Developer/electricity-price
python3 -c "from elpris.unified_dashboard_data import build_unified_data; d = build_unified_data(); print('parks:', list(d['assets']['parks'].keys()))"
```

Förväntat: lista med 8 park-keys (horby, fjallskar, ...). Om det kraschar — fixa innan du fortsätter.

---

## Phase 1 — Backend data plumbing

### Task 1.1: Utöka `_daily_records_from_report` med PR, availability, PI

**Files:**
- Modify: `elpris/unified_dashboard_data.py:100-115`

**Vad:** Idag exponerar `_daily_records_from_report` bara energi/irr/yield/expected/pr_pct/pi_pct (titta — pr/pi finns redan!). Lägg till `availability_pct` och `efficiency_pct`. Availability finns inte direkt i `DailyData` utan måste härledas — för nu, lägg till `efficiency_pct` (finns) och låt availability komma från Bazefield (separat task).

**Implementation:**

```python
def _daily_records_from_report(report) -> List[Dict[str, Any]]:
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
```

**Verify:**

```bash
python3 -c "
from elpris.unified_dashboard_data import build_unified_data
d = build_unified_data()
horby_daily = d['assets']['parks']['horby']['daily_by_month']
key = sorted(horby_daily.keys())[-1]
print('keys in record:', list(horby_daily[key][0].keys()))
"
```

Förväntat: include `pr_pct`, `pi_pct`, `efficiency_pct`, `module_temp_c`.

**Commit:** `feat(assets): expose pr/pi/efficiency/temp in daily records`

---

### Task 1.2: Utöka `_build_park_months` med PR, budget-PR, loss-cascade, daily availability-aggregat

**Files:**
- Modify: `elpris/unified_dashboard_data.py:118-179`

**Vad:** Lägg till `actual_pr_pct`, `budget_pr_pct`, `losses` (cascade dict), och `availability_pct` (vägd medel av 15-min availability inom månaden för dagar med produktion).

`actual_pr_pct` finns redan i `report.performance_ratio_pct`. `budget_pr_pct` finns i `report.budget_pr_pct`. `losses` finns som `report.losses` (LossCascade-dataklass).

För availability: report-objektet har `report.has_availability`-flagga; den underliggande aggregeringen sker i `performance_report_data._aggregate_daily` men exponeras inte direkt på MonthSummary. Vi beräknar månadsmedel från daily availability genom att gå till Bazefield-data direkt. Skapa en hjälpare:

**Implementation:**

```python
# Nytt: ovanför _build_park_months
def _availability_for_month(park_key: str, year: int, month: int) -> Optional[float]:
    """Energi-viktad availability för en park-månad från Bazefield 15-min.

    Returnerar None om ingen availability-data finns.
    """
    from .operations_dashboard_data import load_park_15min
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
        # Vikt = irradiance om finns, annars effective_power, annars 1
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
        "curtailment_mwh": _safe_round(losses.curtailment_loss_mwh, 2),
        "irradiance_shortfall_mwh": _safe_round(losses.irradiance_shortfall_loss_mwh, 2),
        "availability_mwh": _safe_round(losses.availability_loss_mwh, 2),
        "temperature_mwh": _safe_round(losses.temperature_loss_mwh, 2),
        "other_mwh": _safe_round(losses.other_losses_mwh, 2),
    }
```

Modifiera sedan `_build_park_months` så varje månad också får:

```python
months_out.append({
    # ... befintliga fält ...
    "actual_pr_pct": _safe_round(report.performance_ratio_pct, 2),
    "budget_pr_pct": _safe_round(report.budget_pr_pct, 2),
    "availability_pct": _availability_for_month(park_key, year, month),
    "losses": _losses_dict(report.losses),
})
```

**Verify:**

```bash
python3 -c "
from elpris.unified_dashboard_data import build_unified_data
d = build_unified_data()
m = d['assets']['parks']['horby']['months'][-1]
print('keys:', sorted(m.keys()))
print('losses:', m.get('losses'))
print('availability:', m.get('availability_pct'))
print('actual_pr:', m.get('actual_pr_pct'), 'budget_pr:', m.get('budget_pr_pct'))
"
```

Förväntat: nya nycklar finns, losses är en dict med 7 fält, availability är ett tal mellan 0-100 eller None.

**Commit:** `feat(assets): add PR, availability, loss cascade per park-month`

---

### Task 1.3: Lägg till `last_data_ts` per park (data freshness)

**Files:**
- Modify: `elpris/unified_dashboard_data.py` `_build_assets_section`

**Vad:** Beräkna senaste 15-min timestamp per park från Bazefield-CSV. Spara som ISO-string. Frontend räknar ålder.

**Implementation:**

```python
# Ovanför _build_assets_section:
def _last_data_ts(park_key: str) -> Optional[str]:
    """Senaste 15-min timestamp i Bazefield-CSV (ISO 8601 UTC)."""
    from .operations_dashboard_data import load_park_15min
    records = load_park_15min(park_key)
    if not records:
        return None
    last = max(r["timestamp_utc"] for r in records)
    return last.isoformat()
```

Wire i `_build_assets_section` per park:

```python
parks[park_key] = {
    "name": _park_display_name(park_key),
    "zone": PARK_ZONES.get(park_key, ""),
    "capacity_mwp": round(capacity_kwp / 1000.0, 3),
    "last_data_ts": _last_data_ts(park_key),
    "months": months,
    "daily_by_month": daily_by_month,
}
```

**Verify:**

```bash
python3 -c "
from elpris.unified_dashboard_data import build_unified_data
d = build_unified_data()
for k, p in d['assets']['parks'].items():
    print(k, '->', p.get('last_data_ts'))
"
```

Förväntat: 8 ISO-tidsstämplar; skiljer sig mellan parker beroende på senaste sync.

**Commit:** `feat(assets): expose last_data_ts per park for freshness indicator`

---

### Task 1.4: Lägg till park-metadata för "About this park"-panel

**Files:**
- Modify: `elpris/unified_dashboard_data.py` `_build_assets_section`

**Vad:** Inkludera en kompakt metadata-payload per park: COD, modul, antal moduler, växelriktare, tilt, transformator, AC-kapacitet, grid-limit, tracking-typ, expected PR%, expected yield. Allt finns i `get_park_metadata()`.

**Implementation:**

```python
# Ovanför _build_assets_section:
def _park_facts(park_key: str) -> Optional[Dict[str, Any]]:
    """Plocka subset av park-metadata för 'About this park'-panel."""
    meta = get_park_metadata(park_key)
    if not meta:
        return None
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
        "expected_pr_pct": round((meta.get("standard_pr") or 0) * 100, 1),
        "expected_annual_yield_kwh_kwp": meta.get("expected_annual_yield_kwh_kwp"),
        "profile_type": meta.get("profile_type"),
    }
```

I `_build_assets_section` lägg till `"facts": _park_facts(park_key)` i park-dicten.

**Verify:**

```bash
python3 -c "
from elpris.unified_dashboard_data import build_unified_data
d = build_unified_data()
print(d['assets']['parks']['horby']['facts'])
"
```

Förväntat: dict med ~17 fält.

**Commit:** `feat(assets): expose park metadata facts for About panel`

---

### Task 1.5: Skapa ny modul `elpris/park_revenue.py` för realiserad capture & revenue

**Files:**
- Create: `elpris/park_revenue.py`
- Test: `tests/test_park_revenue.py`

**Vad:** Joina Bazefield 15-min `effective_power_mw` per park × spot-priser 15-min för parkens zon, beräkna per (year, month):
- `volume_mwh` = Σ effective_power × 0.25 (sanity check mot energy_mwh i months)
- `revenue_eur` = Σ effective_power × 0.25 × spot_eur_mwh
- `capture_eur_mwh` = revenue_eur / volume_mwh (realiserad capture för parken)
- `baseload_eur_mwh` = enkel medel av spot 15-min för månaden i parkens zon
- `capture_premium_pct` = (capture / baseload - 1) × 100

**Implementation:**

```python
"""Realized capture price & revenue per park-month.

Joinar Bazefield 15-min produktion (effective_power_mw, meter→inverter
fallback) med spot-priser 15-min för parkens zon. Resultatet är en
faktisk-marknads-baserad capture-prismetrik per park, till skillnad
från generiska zon-capture-priser baserade på PVsyst-profiler.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .config import PARK_CAPACITY_KWP, PARK_ZONES
from .operations_dashboard_data import load_park_15min, load_spot_prices_15min


def calculate_park_revenue_capture() -> Dict[str, List[dict]]:
    """Beräkna realiserad capture & revenue per park-månad.

    Returnerar {park_key: [{year, month, volume_mwh, revenue_eur,
    capture_eur_mwh, baseload_eur_mwh, capture_premium_pct}, ...]}
    sorterat äldst → nyast.
    """
    result: Dict[str, List[dict]] = {}

    # Cacha spot per zon för att undvika att läsa CSV:erna 8 gånger
    spot_cache: dict[str, dict[str, list[dict]]] = {}

    for park_key in PARK_CAPACITY_KWP:
        zone = PARK_ZONES.get(park_key)
        if not zone:
            continue

        park_records = load_park_15min(park_key)
        if not park_records:
            continue

        if zone not in spot_cache:
            spot_cache[zone] = load_spot_prices_15min(zone)
        spot = spot_cache[zone]
        if not spot:
            continue

        # Index park-data per timestamp för join
        park_by_ts: Dict[str, float] = {}
        for r in park_records:
            ts_key = r["timestamp_utc"].strftime("%Y-%m-%dT%H:%M")
            park_by_ts[ts_key] = r["effective_power_mw"]

        # Aggregera per (year, month)
        # m_data[ym] = {"volume_mwh", "revenue_eur",
        #               "spot_sum_eur", "spot_n"}
        m_data: dict[tuple[int, int], dict] = defaultdict(
            lambda: {"volume_mwh": 0.0, "revenue_eur": 0.0,
                     "spot_sum_eur": 0.0, "spot_n": 0}
        )

        for date_key, prices in spot.items():
            for price_rec in prices:
                ts_utc = price_rec["timestamp_utc"]
                ts_key = ts_utc.strftime("%Y-%m-%dT%H:%M")
                price = price_rec["eur_mwh"]
                power = park_by_ts.get(ts_key, 0.0)

                ym = (ts_utc.year, ts_utc.month)
                bucket = m_data[ym]
                bucket["spot_sum_eur"] += price
                bucket["spot_n"] += 1
                if power > 0:
                    energy = power * 0.25  # MWh per 15 min
                    bucket["volume_mwh"] += energy
                    bucket["revenue_eur"] += energy * price

        out = []
        for (year, month), b in sorted(m_data.items()):
            volume = b["volume_mwh"]
            revenue = b["revenue_eur"]
            capture = revenue / volume if volume > 0 else None
            baseload = (b["spot_sum_eur"] / b["spot_n"]
                        if b["spot_n"] > 0 else None)
            premium = None
            if capture is not None and baseload is not None and baseload != 0:
                premium = (capture / baseload - 1.0) * 100.0
            out.append({
                "year": year,
                "month": month,
                "volume_mwh": round(volume, 2),
                "revenue_eur": round(revenue, 2),
                "capture_eur_mwh": round(capture, 2) if capture is not None else None,
                "baseload_eur_mwh": round(baseload, 2) if baseload is not None else None,
                "capture_premium_pct": round(premium, 2) if premium is not None else None,
            })
        if out:
            result[park_key] = out

    return result
```

**Test:**

```python
# tests/test_park_revenue.py
"""Tests for park_revenue module."""

import pytest
from elpris.park_revenue import calculate_park_revenue_capture


def test_calculate_park_revenue_capture_returns_data():
    result = calculate_park_revenue_capture()
    # Minst en park ska ha resultat (Hörby är längst i drift)
    assert "horby" in result
    assert len(result["horby"]) > 0


def test_revenue_records_have_required_fields():
    result = calculate_park_revenue_capture()
    for park, records in result.items():
        for rec in records:
            assert "year" in rec
            assert "month" in rec
            assert "volume_mwh" in rec
            assert "revenue_eur" in rec
            assert "capture_eur_mwh" in rec
            assert "baseload_eur_mwh" in rec
            assert "capture_premium_pct" in rec


def test_capture_consistent_with_revenue_volume():
    """capture_eur_mwh ska = revenue_eur / volume_mwh."""
    result = calculate_park_revenue_capture()
    for park, records in result.items():
        for rec in records:
            if rec["volume_mwh"] > 0 and rec["capture_eur_mwh"] is not None:
                expected = rec["revenue_eur"] / rec["volume_mwh"]
                # round(2) tolerance
                assert abs(rec["capture_eur_mwh"] - expected) < 0.02


def test_records_sorted_chronologically():
    result = calculate_park_revenue_capture()
    for park, records in result.items():
        keys = [(r["year"], r["month"]) for r in records]
        assert keys == sorted(keys)
```

**Verify:**

```bash
pytest tests/test_park_revenue.py -v
```

Förväntat: 4 PASS.

**Commit:** `feat(assets): new park_revenue module — realized capture & revenue per park-month`

---

### Task 1.6: Wire `park_revenue` in i `_build_park_months` + `_build_fleet_overview`

**Files:**
- Modify: `elpris/unified_dashboard_data.py`

**Vad:** Anropa `calculate_park_revenue_capture()` en gång i `_build_assets_section`, sedan merge in i månadsraderna per park (analogt med `_merge_operations_into_months`).

**Implementation:**

```python
# Ovanför _build_assets_section:
def _safe_park_revenue() -> Dict[str, List[Dict[str, Any]]]:
    try:
        from .park_revenue import calculate_park_revenue_capture
        return calculate_park_revenue_capture()
    except Exception as exc:
        print(f"[unified_dashboard] park_revenue beräkning misslyckades: {exc}",
              file=sys.stderr)
        return {}


def _merge_revenue_into_months(
    parks: Dict[str, Dict[str, Any]],
    revenue: Dict[str, List[Dict[str, Any]]],
) -> None:
    for park_key, park in parks.items():
        rev = revenue.get(park_key, [])
        rev_lookup = {(r["year"], r["month"]): r for r in rev}
        for m in park["months"]:
            r = rev_lookup.get((m["year"], m["month"]))
            if r is None:
                m["revenue_eur"] = None
                m["capture_eur_mwh"] = None
                m["baseload_eur_mwh"] = None
                m["capture_premium_pct"] = None
                m["bazefield_volume_mwh"] = None
            else:
                m["revenue_eur"] = r["revenue_eur"]
                m["capture_eur_mwh"] = r["capture_eur_mwh"]
                m["baseload_eur_mwh"] = r["baseload_eur_mwh"]
                m["capture_premium_pct"] = r["capture_premium_pct"]
                m["bazefield_volume_mwh"] = r["volume_mwh"]
```

I `_build_assets_section`:

```python
# Efter _merge_operations_into_months:
revenue = _safe_park_revenue()
_merge_revenue_into_months(parks, revenue)
```

Utöka `_build_fleet_overview` så total `total_revenue_eur` och fleet `realized_capture_eur_mwh` (= totalRev / totalVol) räknas:

```python
# I _build_fleet_overview, lägg till loop-variabler:
total_revenue = 0.0
total_volume = 0.0
has_revenue = False

# I park-loopen:
if match.get("revenue_eur") is not None:
    total_revenue += match["revenue_eur"]
    has_revenue = True
if match.get("bazefield_volume_mwh") is not None:
    total_volume += match["bazefield_volume_mwh"]

# Efter loopen:
fleet_capture = (total_revenue / total_volume) if total_volume > 0 else None

return {
    # ... befintliga fält ...
    "total_revenue_eur": round(total_revenue, 2) if has_revenue else None,
    "fleet_capture_eur_mwh": round(fleet_capture, 2) if fleet_capture is not None else None,
    "fleet_volume_mwh": round(total_volume, 2) if total_volume > 0 else None,
}
```

**Verify:**

```bash
python3 -c "
from elpris.unified_dashboard_data import build_unified_data
d = build_unified_data()
m = d['assets']['parks']['horby']['months'][-1]
print('revenue:', m.get('revenue_eur'), 'EUR')
print('capture:', m.get('capture_eur_mwh'), 'EUR/MWh')
print('baseload:', m.get('baseload_eur_mwh'), 'EUR/MWh')
print('premium:', m.get('capture_premium_pct'), '%')
print('fleet:', d['assets']['fleet'])
"
```

Förväntat: numeriska värden, fleet har `total_revenue_eur` + `fleet_capture_eur_mwh`.

**Commit:** `feat(assets): wire realized revenue & capture into park months + fleet overview`

---

### Task 1.7: Exponera fleet realized capture per zon-månad till CAPTURE-fliken

**Files:**
- Modify: `elpris/unified_dashboard_data.py` (lägg till funktion)

**Vad:** För att CAPTURE-fliken ska kunna rita en "Fleet realized" linje ovanpå zon-capture, behöver vi en zon-aggregerad realiserad capture per månad (där flera parker i samma zon viktas tillsammans).

**Implementation:**

```python
# Ny funktion:
def _build_fleet_capture_by_zone(
    parks: Dict[str, Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Volym-vägd realiserad capture per zon per månad (alla parker i zonen)."""
    # zone -> ym -> {revenue, volume}
    by_zone: dict[str, dict[tuple[int, int], dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {"rev": 0.0, "vol": 0.0})
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

    out: Dict[str, List[Dict[str, Any]]] = {}
    for zone, months in by_zone.items():
        records = []
        for (year, month), d in sorted(months.items()):
            cap = d["rev"] / d["vol"] if d["vol"] > 0 else None
            records.append({
                "month": f"{year}-{month:02d}",
                "fleet_capture_eur_mwh": round(cap, 2) if cap is not None else None,
                "fleet_volume_mwh": round(d["vol"], 2),
            })
        if records:
            out[zone] = records
    return out
```

Krävs `from collections import defaultdict` överst.

I `_build_assets_section`-return:

```python
return {
    "parks": parks,
    "fleet": _build_fleet_overview(parks),
    "tracker_gain": _build_tracker_gain(),
    "capture_by_zone": _build_capture_by_zone(market),
    "fleet_capture_by_zone": _build_fleet_capture_by_zone(parks),  # NY
}
```

**Verify:**

```bash
python3 -c "
from elpris.unified_dashboard_data import build_unified_data
d = build_unified_data()
fcz = d['assets']['fleet_capture_by_zone']
print('zones:', list(fcz.keys()))
print('SE3 first 3:', fcz.get('SE3', [])[:3])
print('SE4 first 3:', fcz.get('SE4', [])[:3])
"
```

Förväntat: SE3 och SE4 har records (parkerna ligger där). SE1/SE2 saknas (inga parker).

**Commit:** `feat(assets): expose fleet realized capture per zone for CAPTURE tab overlay`

---

## Phase 2 — Frontend: Fleet KPIs, tabell, park-tiles

### Task 2.1: Utöka `aggregatePark` med revenue, realized capture, premium, availability

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` `aggregatePark` rad ~2309-2362

**Vad:** Lägg till summor och vägda medel för nya fält.

**Implementation:**

I returnobjektet, lägg till:

```javascript
return {
    // ... befintliga fält ...
    revenue_eur: sum('revenue_eur'),
    bazefield_volume_mwh: sum('bazefield_volume_mwh'),
    realized_capture_eur_mwh: (function() {
        var rev = sum('revenue_eur');
        var vol = sum('bazefield_volume_mwh');
        return (rev != null && vol != null && vol > 0) ? (rev / vol) : null;
    })(),
    baseload_eur_mwh: weightedAvg('baseload_eur_mwh', 'bazefield_volume_mwh'),
    availability_pct: weightedAvg('availability_pct', 'energy_mwh'),
    actual_pr_pct: weightedAvg('actual_pr_pct', 'energy_mwh'),
    budget_pr_pct: weightedAvg('budget_pr_pct', 'energy_mwh')
};
```

Capture premium beräknas i frontend där det behövs (realized / baseload − 1).

**Commit:** `feat(assets): aggregate revenue/capture/availability/PR in aggregatePark`

---

### Task 2.2: Utöka fleet KPI-strip med Revenue + Realized capture + premium

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` `renderFleetKPIs` rad ~2561-2597

**Vad:** Lägg till två nya kort: "Revenue" (k€) och "Realized capture · vs baseload". Behåll befintliga 5 men gör vs-Budget mindre prominent. Ändra storlek/layout om nödvändigt — Nordic Editorial-CSS ska redan klara 7 tiles.

**Implementation:**

```javascript
// Inuti renderFleetKPIs efter befintlig totals-loop, lägg till:
var totalRevenue = 0, totalVolume = 0, totalSpotWeighted = 0;
var hasRevenue = false;
entries.forEach(function(e) {
    var p = e[1];
    var agg = aggregatePark(p, keys);
    if (!agg) return;
    if (agg.revenue_eur != null) { totalRevenue += agg.revenue_eur; hasRevenue = true; }
    if (agg.bazefield_volume_mwh != null) totalVolume += agg.bazefield_volume_mwh;
    // baseload-vägt med volym för fleet baseload
    if (agg.baseload_eur_mwh != null && agg.bazefield_volume_mwh != null) {
        totalSpotWeighted += agg.baseload_eur_mwh * agg.bazefield_volume_mwh;
    }
});
var fleetCapture = (totalVolume > 0 && hasRevenue) ? (totalRevenue / totalVolume) : null;
var fleetBaseload = (totalVolume > 0) ? (totalSpotWeighted / totalVolume) : null;
var capturePremium = (fleetCapture != null && fleetBaseload != null && fleetBaseload !== 0)
    ? (fleetCapture / fleetBaseload - 1) * 100 : null;
var premiumCls = vsClass(capturePremium);
var premiumPill = capturePremium != null
    ? '<span class="pill ' + premiumCls + '">' + fmtPct(capturePremium, 1) + ' vs baseload</span>'
    : '<span class="pill neutral">–</span>';

// Lägg till tiles före neg-h:
var revenueTile = '<div class="kpi"><div class="kpi-label">Revenue · ' + suffix +
    '</div><div><span class="kpi-value">' +
    (hasRevenue ? fmtNum(totalRevenue / 1000, 0) : '–') +
    '</span><span class="kpi-unit">k€</span></div>' +
    '<div class="kpi-sub">' + (hasRevenue ? fmtNum(totalVolume, 0) + ' MWh sold' : 'no spot data') + '</div></div>';

var captureTile = '<div class="kpi"><div class="kpi-label">Realized capture</div>' +
    '<div><span class="kpi-value">' +
    (fleetCapture != null ? fmtNum(fleetCapture, 1) : '–') +
    '</span><span class="kpi-unit">€/MWh</span></div>' +
    '<div class="kpi-sub">' + premiumPill + '</div></div>';

var tiles = [
    kpiTile('Parks', String(entries.length), '', 'Active in fleet view'),
    kpiTile('Installed capacity', fmtNum(totalCap, 1), 'MWp', 'DC, sum across selection'),
    kpiTile(energyLabel, anyData ? fmtNum(totalActual, 0) : '–', 'MWh', energySub),
    revenueTile,
    captureTile,
    '<div class="kpi"><div class="kpi-label">vs Budget</div><div class="kpi-value">' + (vsBudget != null ? fmtPct(vsBudget) : '–') + '</div><div class="kpi-sub">' + pillHtml + '</div></div>',
    kpiTile(negLabel, anyData ? fmtNum(totalNeg, 0) : '–', 'h', 'Sum across selection'),
];
el('fleet-kpis').innerHTML = tiles.join('');
```

**Verify:** Generera dashboard, öppna Assets-fliken, kontrollera att 7 tiles visas och Revenue/Capture är ifyllda.

**Commit:** `feat(assets): add Revenue & Realized capture KPI tiles to fleet strip`

---

### Task 2.3: Utöka park-tabellen med PR%, Avail%, Capture€/MWh, Revenue k€

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` `tableRows` rad ~2651-2671 + `renderParkTable` cols rad ~2690-2699 + `exportParkCsv` rad ~2733-2764

**Vad:** Lägg till 4 nya kolumner. Behåll alla befintliga.

**Implementation tableRows:**

```javascript
return {
    key: pk, name: p.name || pk, zone: p.zone || '',
    capacity_mwp: p.capacity_mwp || 0,
    energy_mwh: agg ? agg.energy_mwh : null,
    budget_mwh: agg ? agg.budget_mwh : null,
    vs_budget_pct: agg ? agg.vs_budget_pct : null,
    yield_kwh_kwp: agg ? agg.yield_kwh_kwp : null,
    actual_irr_kwh_m2: agg ? agg.actual_irr_kwh_m2 : null,
    vs_budget_irr_pct: agg ? agg.vs_budget_irr_pct : null,
    pr_pct: agg ? agg.actual_pr_pct : null,
    availability_pct: agg ? agg.availability_pct : null,
    revenue_eur: agg ? agg.revenue_eur : null,
    capture_eur_mwh: agg ? agg.realized_capture_eur_mwh : null,
    baseload_eur_mwh: agg ? agg.baseload_eur_mwh : null,
    months_present: agg ? agg.months_present : 0,
    months_expected: expected || 1,
    last_data_ts: p.last_data_ts || null
};
```

**Implementation renderParkTable cols:**

```javascript
var captureFmt = function(v) {
    return v == null ? '–' : fmtNum(v, 1);
};
var revFmt = function(v) {
    return v == null ? '–' : fmtNum(v / 1000, 1);
};
var prFmt = function(v) {
    return v == null ? '–' : fmtNum(v, 1);
};

var cols = [
    { k: 'name',          label: 'Park',            fmt: nameFormatter, cls: '', html: true, withDot: true },
    { k: 'zone',          label: 'Zone',            fmt: htmlEsc, cls: '' },
    { k: 'capacity_mwp',  label: 'Cap MWp',         fmt: function(v) { return fmtNum(v, 2); }, cls: 'num' },
    { k: 'energy_mwh',    label: energyLabel,       fmt: function(v) { return fmtNum(v, 0); }, cls: 'num' },
    { k: 'vs_budget_pct', label: 'vs Budget',       fmt: function(v) { if (v == null) return '–'; var c = vsClass(v); return '<span class="pill ' + c + '">' + fmtPct(v) + '</span>'; }, cls: 'num', html: true },
    { k: 'pr_pct',        label: 'PR %',            fmt: prFmt, cls: 'num' },
    { k: 'availability_pct', label: 'Avail %',      fmt: prFmt, cls: 'num' },
    { k: 'capture_eur_mwh', label: 'Capture €/MWh', fmt: captureFmt, cls: 'num' },
    { k: 'revenue_eur',   label: 'Revenue k€',      fmt: revFmt, cls: 'num' },
    { k: 'actual_irr_kwh_m2', label: 'Irr (kWh/m²)', fmt: function(v) { return fmtNum(v, 1); }, cls: 'num' },
    { k: 'yield_kwh_kwp', label: 'Yield kWh/kWp',   fmt: function(v) { return fmtNum(v, 1); }, cls: 'num' },
];
```

**Implementation exportParkCsv** — utöka header + row.

**Verify:** Öppna dashboard, scrolla tabellen — kontrollera 11 kolumner sorterar korrekt.

**Commit:** `feat(assets): add PR/Avail/Capture/Revenue columns to park table`

---

### Task 2.4: Data-freshness-prick på park-tile + tabell-namn

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` `renderParkGrid` rad ~2618-2649 + `renderParkTable`

**Vad:** Beräkna ålder i timmar från `last_data_ts`. Visa en liten färgad prick vid park-namnet:
- ≤ 36 h grön (intet visas — håll det rent när det är OK; valfritt en grå punkt)
- 36-96 h gul med tooltip "Stale: X h"
- > 96 h röd med tooltip "Stale: X days"

**Implementation:**

```javascript
// Ny hjälpare nära toppen av Assets-blocket:
function freshnessIndicator(isoTs) {
    if (!isoTs) return '';
    var t = Date.parse(isoTs);
    if (isNaN(t)) return '';
    var ageH = (Date.now() - t) / 3600000;
    if (ageH <= 36) return '';  // Fresh — no clutter
    var cls, label;
    if (ageH <= 96) { cls = 'warn'; label = Math.round(ageH) + 'h stale'; }
    else { cls = 'bad'; label = Math.round(ageH / 24) + 'd stale'; }
    return ' <span class="freshness-dot ' + cls + '" title="' + label + ' since last data" aria-label="' + label + '"></span>';
}
```

CSS — lägg till i `_CSS` om inte redan finns:

```css
.freshness-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    vertical-align: middle;
    margin-left: 4px;
}
.freshness-dot.warn { background: var(--warn); }
.freshness-dot.bad { background: var(--bad); }
```

I `renderParkGrid`, lägg in efter park-tile-name:

```javascript
'<div class="park-tile-name">' + htmlEsc(p.name || pk) + dot + freshnessIndicator(p.last_data_ts) + '</div>' +
```

I `renderParkTable` nameFormatter / withDot — lägg till:

```javascript
if (c.withDot) disp = disp + dot + freshnessIndicator(r.last_data_ts);
```

**Verify:** Öppna dashboard. Om någon park är stale > 36h ska indikator visas.

**Commit:** `feat(assets): freshness indicator on park tiles & table when data > 36h old`

---

## Phase 3 — Drilldown enhancements

### Task 3.1: Utöka drill-KPI-strip med Revenue, Realized capture, vs zone-capture

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` `renderDrilldown` rad ~3074-3126

**Vad:** Lägg till 3 nya tiles: Revenue, Realized capture (med pill mot zon-capture-genericen), Capture-premium vs baseload. Strukturera om så vi får 3-4 rader om 4 kort istället för en lång rad. Den befintliga generiska "Capture · SE3"-tile bytes ut mot realiserad.

**Implementation:**

```javascript
// I renderDrilldown, efter befintliga tiles-array — lägg till:
var revenueTile;
if (agg && agg.revenue_eur != null) {
    revenueTile = '<div class="kpi"><div class="kpi-label">Revenue</div>' +
        '<div><span class="kpi-value">' + fmtNum(agg.revenue_eur / 1000, 1) + '</span><span class="kpi-unit">k€</span></div>' +
        '<div class="kpi-sub">' + fmtNum(agg.bazefield_volume_mwh, 0) + ' MWh sold</div></div>';
} else {
    revenueTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Revenue</div><div class="kpi-value">—</div><div class="kpi-sub">no spot data</div></div>';
}

var realizedCap = agg ? agg.realized_capture_eur_mwh : null;
var baseload = agg ? agg.baseload_eur_mwh : null;
var realizedTile;
if (realizedCap != null) {
    var captureZoneAvg = captureForPeriod(p.zone, keys);  // PVsyst-baserad zon-capture
    var vsZone = (captureZoneAvg != null && captureZoneAvg !== 0)
        ? (realizedCap - captureZoneAvg) : null;
    var vsZonePill = vsZone != null
        ? '<span class="pill ' + vsClass(vsZone) + '">' + (vsZone >= 0 ? '+' : '') + fmtNum(vsZone, 1) + ' vs zone gen.</span>'
        : '<span class="pill neutral">–</span>';
    realizedTile = '<div class="kpi"><div class="kpi-label">Realized capture</div>' +
        '<div><span class="kpi-value">' + fmtNum(realizedCap, 1) + '</span><span class="kpi-unit">€/MWh</span></div>' +
        '<div class="kpi-sub">' + vsZonePill + '</div></div>';
} else {
    realizedTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Realized capture</div><div class="kpi-value">—</div><div class="kpi-sub">no spot match</div></div>';
}

var premiumTile;
if (realizedCap != null && baseload != null && baseload !== 0) {
    var prem = (realizedCap / baseload - 1) * 100;
    var premPill = '<span class="pill ' + vsClass(prem) + '">' + fmtPct(prem, 1) + '</span>';
    premiumTile = '<div class="kpi"><div class="kpi-label">Capture vs baseload</div>' +
        '<div><span class="kpi-value">' + fmtNum(baseload, 1) + '</span><span class="kpi-unit">€/MWh base</span></div>' +
        '<div class="kpi-sub">' + premPill + '</div></div>';
} else {
    premiumTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Capture vs baseload</div><div class="kpi-value">—</div></div>';
}

var prTile;
if (agg && agg.actual_pr_pct != null) {
    var dPr = (agg.budget_pr_pct != null) ? (agg.actual_pr_pct - agg.budget_pr_pct) : null;
    var prPill = dPr != null
        ? '<span class="pill ' + vsClass(dPr) + '">' + (dPr >= 0 ? '+' : '') + fmtNum(dPr, 1) + ' pp vs budget</span>'
        : '<span class="pill neutral">–</span>';
    prTile = '<div class="kpi"><div class="kpi-label">Performance Ratio</div>' +
        '<div><span class="kpi-value">' + fmtNum(agg.actual_pr_pct, 1) + '</span><span class="kpi-unit">%</span></div>' +
        '<div class="kpi-sub">' + prPill + '</div></div>';
} else {
    prTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Performance Ratio</div><div class="kpi-value">—</div></div>';
}

var availTile;
if (agg && agg.availability_pct != null) {
    availTile = '<div class="kpi"><div class="kpi-label">Availability</div>' +
        '<div><span class="kpi-value">' + fmtNum(agg.availability_pct, 1) + '</span><span class="kpi-unit">%</span></div>' +
        '<div class="kpi-sub">irradiance-weighted</div></div>';
} else {
    availTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Availability</div><div class="kpi-value">—</div></div>';
}

var tiles = [
    energyTile,
    revenueTile,
    realizedTile,
    premiumTile,
    vsTile,
    prTile,
    availTile,
    irrTile,
    kpiTile('Yield', agg && agg.yield_kwh_kwp != null ? fmtNum(agg.yield_kwh_kwp, 1) : '–', 'kWh/kWp', ''),
    kpiTile('Negative-price h', agg && agg.neg_price_hours != null ? fmtNum(agg.neg_price_hours, 0) : '–', 'h', agg && agg.neg_price_volume_mwh != null ? fmtNum(agg.neg_price_volume_mwh, 0) + ' MWh forgone' : ''),
    trackerTile,
];
```

**Commit:** `feat(assets): drill KPI strip — Revenue, Realized capture, PR, Availability`

---

### Task 3.2: PR + Availability-linjer på daily-chart

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` daily chart rad ~3149-3173

**Vad:** Lägg till två extra traces på daily-chart: PR-linje (sekundär y-axel kHash), och, om availability finns, en låg streckad linje. Alternativ: en separat PR-chart bredvid. Pragmatiskt val: en sekundär axel räcker — daglig PR vs energi visar omedelbart "låg sol vs låg PR".

Men daily availability finns INTE i `daily_by_month` ännu (inget i DailyData har det). Lösning: skippa availability-linje på daily; visa bara PR. Lägg till availability-trend som månadsvis chart (se Task 3.3).

**Implementation:**

```javascript
if (days.length) {
    var dxs = days.map(function(d) { return d.date; });
    Plotly.react('drill-daily-chart', [
        { x: dxs, y: days.map(function(d) { return d.energy_mwh; }), name: 'Actual', type: 'bar', marker: { color: '#2E5C4D' }, hovertemplate: '%{x}<br>Actual: <b>%{y:.2f}</b> MWh<extra></extra>' },
        { x: dxs, y: days.map(function(d) { return d.expected_mwh; }), name: 'Expected', type: 'scatter', mode: 'lines', line: { color: '#C16E40', dash: 'dash', width: 2 }, hovertemplate: '%{x}<br>Expected: <b>%{y:.2f}</b> MWh<extra></extra>' },
        { x: dxs, y: days.map(function(d) { return d.irradiation_kwh_m2; }), name: 'POA Irr', type: 'scatter', mode: 'lines', line: { color: '#C9A53C', width: 1.6, shape: 'spline' }, yaxis: 'y2', connectgaps: false, hovertemplate: '%{x}<br>POA Irr: <b>%{y:.2f}</b> kWh/m²<extra></extra>' },
        { x: dxs, y: days.map(function(d) { return d.pr_pct; }), name: 'PR %', type: 'scatter', mode: 'lines+markers', line: { color: '#5B6BA8', width: 1.8, shape: 'spline' }, marker: { size: 4 }, yaxis: 'y3', connectgaps: false, hovertemplate: '%{x}<br>PR: <b>%{y:.1f}</b> %<extra></extra>' },
    ], makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'MWh', font: PLOTLY_BASE.yaxis.title.font }, domain: [0, 1] }),
        yaxis2: Object.assign({}, PLOTLY_BASE.yaxis, {
            title: { text: 'kWh / m²', font: PLOTLY_BASE.yaxis.title.font },
            overlaying: 'y',
            side: 'right',
            position: 1.0,
            gridcolor: 'transparent',
            showgrid: false,
        }),
        yaxis3: Object.assign({}, PLOTLY_BASE.yaxis, {
            title: { text: 'PR %', font: PLOTLY_BASE.yaxis.title.font },
            overlaying: 'y',
            side: 'right',
            position: 0.94,
            anchor: 'free',
            range: [0, 100],
            gridcolor: 'transparent',
            showgrid: false,
        }),
        margin: { t: 12, b: 70, l: 64, r: 96 },
    }), PLOTLY_CFG);
}
```

**Verify:** Öppna en park, kontrollera daily-chart har 4 serier med PR-linjen i blått.

**Commit:** `feat(assets): add PR % line to daily generation chart`

---

### Task 3.3: Loss waterfall card i drilldown

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` HTML shell + JS

**Vad:** Ny card "Loss analysis (waterfall)" — visar Budget → Irradiance shortfall → Availability loss → Curtailment → Temperature → Other → Actual. För perioden (kan vara month/YTD/year — aggregera då losses över valda månader). Toggle MWh/%.

**Implementation:**

HTML — lägg till efter "Daily generation"-card men innan "POA Irradiation":

```html
<div class="card">
    <div class="card-head">
        <div><div class="card-title">Loss analysis</div><div class="card-sub" id="drill-loss-sub">Budget → Actual cascade. Toggle MWh / %.</div></div>
        <div class="card-actions">
            <div class="seg" id="drill-loss-mode" role="tablist">
                <button type="button" data-mode="mwh" role="tab" aria-selected="true">MWh</button>
                <button type="button" data-mode="pct" role="tab" aria-selected="false">%</button>
            </div>
        </div>
    </div>
    <div class="chart" id="drill-loss-chart"></div>
</div>
```

JS — ny funktion:

```javascript
var DRILL_LOSS_MODE = 'mwh';

function aggregateLosses(park, keys) {
    var fields = ['budget_mwh','actual_mwh','irradiance_shortfall_mwh',
                  'availability_mwh','curtailment_mwh','temperature_mwh','other_mwh'];
    var sums = {};
    fields.forEach(function(f) { sums[f] = 0; });
    var any = false;
    (park.months || []).forEach(function(m) {
        if (keys.indexOf(m.year + '-' + pad2(m.month)) === -1) return;
        if (!m.losses) return;
        any = true;
        fields.forEach(function(f) {
            var v = m.losses[f];
            if (v != null) sums[f] += v;
        });
    });
    return any ? sums : null;
}

function renderLossWaterfall(park, keys) {
    var host = el('drill-loss-chart');
    var sums = aggregateLosses(park, keys);
    if (!sums) {
        Plotly.purge('drill-loss-chart');
        host.innerHTML = '<div class="empty-note">No loss data for selected period.</div>';
        return;
    }
    var budget = sums.budget_mwh;
    // Loss-waterfall: budget → -irrShortfall → -availability → -curtailment → -temperature → -other → actual
    // (bevara tecken: dessa är "förlust"-värden, dvs positiva tal som ska dras av)
    var labels = ['Budget', 'Irr shortfall', 'Availability', 'Curtailment', 'Temperature', 'Other', 'Actual'];
    var measures = ['absolute', 'relative', 'relative', 'relative', 'relative', 'relative', 'total'];
    var values;
    var unit;
    if (DRILL_LOSS_MODE === 'mwh') {
        values = [
            budget,
            -sums.irradiance_shortfall_mwh,
            -sums.availability_mwh,
            -sums.curtailment_mwh,
            -sums.temperature_mwh,
            -sums.other_mwh,
            sums.actual_mwh,
        ];
        unit = 'MWh';
    } else {
        var pct = function(x) { return budget > 0 ? (x / budget * 100) : 0; };
        values = [
            100,
            -pct(sums.irradiance_shortfall_mwh),
            -pct(sums.availability_mwh),
            -pct(sums.curtailment_mwh),
            -pct(sums.temperature_mwh),
            -pct(sums.other_mwh),
            pct(sums.actual_mwh),
        ];
        unit = '%';
    }
    Plotly.react('drill-loss-chart', [{
        type: 'waterfall',
        x: labels,
        y: values,
        measure: measures,
        text: values.map(function(v) {
            return (DRILL_LOSS_MODE === 'mwh' ? fmtNum(v, 0) : fmtNum(v, 1)) + ' ' + unit;
        }),
        textposition: 'outside',
        connector: { line: { color: '#C0BBA8' } },
        increasing: { marker: { color: '#92B53D' } },
        decreasing: { marker: { color: '#B14E45' } },
        totals: { marker: { color: '#2E5C4D' } },
        hovertemplate: '%{x}<br><b>%{y:.1f}</b> ' + unit + '<extra></extra>',
    }], makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: unit, font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 24, b: 70, l: 64, r: 24 },
        showlegend: false,
    }), PLOTLY_CFG);
}

function bindLossModeControls() {
    var seg = el('drill-loss-mode');
    if (!seg || seg.dataset.bound) return;
    seg.querySelectorAll('button').forEach(function(b) {
        b.addEventListener('click', function() {
            var m = b.dataset.mode;
            if (m === DRILL_LOSS_MODE) return;
            DRILL_LOSS_MODE = m;
            seg.querySelectorAll('button').forEach(function(x) {
                x.setAttribute('aria-selected', x.dataset.mode === m ? 'true' : 'false');
            });
            // Re-render
            var pk = ASSETS_STATE.selectedPark;
            var park = ASSETS.parks[pk];
            renderLossWaterfall(park, drillPeriodKeys(park));
        });
    });
    seg.dataset.bound = '1';
}
```

I `renderDrilldown` lägg till efter befintliga charts:

```javascript
bindLossModeControls();
renderLossWaterfall(p, keys);
```

**Verify:** Öppna en park, scrolla — waterfall med 7 staplar visas, MWh/%-toggle fungerar.

**Commit:** `feat(assets): loss waterfall card in drilldown (MWh/% toggle)`

---

### Task 3.4: Revenue waterfall card i drilldown

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` HTML + JS

**Vad:** Decompose `actual revenue` vs en "what-if budget revenue" basline:
- **Budget revenue baseline** = budget_mwh × baseload_eur_mwh (vad vi skulle ha tjänat med budget-volym till genomsnittlig spot)
- **+/- Volume effect** = (actual_volume − budget_mwh) × baseload_eur_mwh
- **+/- Price effect** = actual_volume × (capture − baseload)
- **= Actual revenue**

Negativ-pris-effekt går automatiskt in i "price effect" (lägre capture).

**Implementation:**

HTML (efter loss waterfall-card):

```html
<div class="card">
    <div class="card-head">
        <div><div class="card-title">Revenue decomposition</div><div class="card-sub">Budget-revenue → volume effect → price effect → realized.</div></div>
    </div>
    <div class="chart" id="drill-revenue-chart"></div>
</div>
```

JS:

```javascript
function renderRevenueWaterfall(park, keys) {
    var host = el('drill-revenue-chart');
    var rows = (park.months || []).filter(function(m) {
        return keys.indexOf(m.year + '-' + pad2(m.month)) !== -1;
    });
    var hasRev = rows.some(function(r) { return r.revenue_eur != null; });
    if (!hasRev) {
        Plotly.purge('drill-revenue-chart');
        host.innerHTML = '<div class="empty-note">No revenue data for selected period (spot/Bazefield join unavailable).</div>';
        return;
    }
    var actualRev = 0, actualVol = 0, baselineRev = 0, baselineVolWeightedSpot = 0, baselineVolDen = 0;
    var budgetMwh = 0;
    rows.forEach(function(r) {
        if (r.revenue_eur != null) actualRev += r.revenue_eur;
        if (r.bazefield_volume_mwh != null) actualVol += r.bazefield_volume_mwh;
        if (r.budget_mwh != null) budgetMwh += r.budget_mwh;
        if (r.baseload_eur_mwh != null && r.bazefield_volume_mwh != null) {
            baselineVolWeightedSpot += r.baseload_eur_mwh * r.bazefield_volume_mwh;
            baselineVolDen += r.bazefield_volume_mwh;
        }
    });
    var baseload = baselineVolDen > 0 ? baselineVolWeightedSpot / baselineVolDen : null;
    if (baseload == null) {
        host.innerHTML = '<div class="empty-note">Insufficient baseload data.</div>';
        return;
    }
    var budgetRev = budgetMwh * baseload;  // What-if
    var capture = actualVol > 0 ? actualRev / actualVol : null;
    var volumeEffect = (actualVol - budgetMwh) * baseload;
    var priceEffect = capture != null ? actualVol * (capture - baseload) : 0;
    // Sanity: budgetRev + volumeEffect + priceEffect ≈ actualRev

    var labels = ['Budget rev.\n(@baseload)', 'Volume effect', 'Price effect', 'Realized rev.'];
    var measures = ['absolute', 'relative', 'relative', 'total'];
    var values = [budgetRev, volumeEffect, priceEffect, actualRev];
    Plotly.react('drill-revenue-chart', [{
        type: 'waterfall',
        x: labels,
        y: values,
        measure: measures,
        text: values.map(function(v) { return fmtNum(v / 1000, 1) + ' k€'; }),
        textposition: 'outside',
        connector: { line: { color: '#C0BBA8' } },
        increasing: { marker: { color: '#92B53D' } },
        decreasing: { marker: { color: '#B14E45' } },
        totals: { marker: { color: '#2E5C4D' } },
        hovertemplate: '%{x}<br><b>%{y:,.0f}</b> €<extra></extra>',
    }], makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EUR', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 24, b: 70, l: 80, r: 24 },
        showlegend: false,
    }), PLOTLY_CFG);
}
```

I `renderDrilldown` efter loss-waterfall:

```javascript
renderRevenueWaterfall(p, keys);
```

**Verify:** Öppna en park, kontrollera waterfall med 4 staplar.

**Commit:** `feat(assets): revenue waterfall (volume vs price decomposition) in drilldown`

---

### Task 3.5: "About this park"-panel (collapsible)

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` HTML + JS + CSS

**Vad:** En `<details>`-element under drill-hero som visar park-fakta som tabell. Default kollapsad. Använder data från `park.facts`.

**Implementation:**

HTML — efter `drill-hero` div, innan `drill-period-bar`:

```html
<details class="park-facts" id="drill-facts">
    <summary>About this park</summary>
    <div class="facts-grid" id="drill-facts-grid"></div>
</details>
```

JS i `renderDrilldown`:

```javascript
renderParkFacts(p);
```

Ny funktion:

```javascript
function renderParkFacts(park) {
    var f = park.facts;
    var host = el('drill-facts-grid');
    if (!host) return;
    if (!f) { host.innerHTML = '<div class="empty-note">No metadata available.</div>'; return; }
    var rows = [
        ['Location', f.location || '–'],
        ['Commissioning', f.commissioning_date || '–'],
        ['Module', (f.module_type || '–') + (f.module_wp ? ' · ' + f.module_wp + ' Wp' : '')],
        ['# Modules', f.num_modules != null ? fmtNum(f.num_modules, 0) : '–'],
        ['Inverter', (f.inverter_manufacturer ? f.inverter_manufacturer + ' ' : '') + (f.inverter_model || '–')],
        ['# Inverters', f.num_inverters != null ? fmtNum(f.num_inverters, 0) : '–'],
        ['Tilt / Azimuth', (f.tilt_angle != null ? f.tilt_angle + '°' : '–') + ' / ' + (f.azimuth != null ? f.azimuth + '°' : '–')],
        ['Tracking', f.tracking ? (f.tracking_type || 'tracker') : 'Fixed'],
        ['AC capacity', f.ac_capacity_mwac != null ? fmtNum(f.ac_capacity_mwac, 2) + ' MWac' : '–'],
        ['Grid limit', f.grid_limit_mwac != null ? fmtNum(f.grid_limit_mwac, 2) + ' MWac' : '–'],
        ['Transformer', f.transformer_count != null && f.transformer_capacity_kva != null
            ? f.transformer_count + ' × ' + fmtNum(f.transformer_capacity_kva, 0) + ' kVA' : '–'],
        ['Expected PR', f.expected_pr_pct != null ? fmtNum(f.expected_pr_pct, 1) + ' %' : '–'],
        ['Expected yield', f.expected_annual_yield_kwh_kwp != null
            ? fmtNum(f.expected_annual_yield_kwh_kwp, 0) + ' kWh/kWp/yr' : '–'],
        ['PVsyst profile', f.profile_type || '–'],
    ];
    host.innerHTML = rows.map(function(r) {
        return '<div class="fact-cell"><div class="fact-k">' + htmlEsc(r[0]) +
            '</div><div class="fact-v">' + htmlEsc(String(r[1])) + '</div></div>';
    }).join('');
}
```

CSS:

```css
.park-facts {
    background: var(--surface-2, #FBF8F2);
    border: 1px solid var(--border, #E5DFD0);
    border-radius: var(--radius-md, 12px);
    padding: 12px 18px;
    margin: 12px 0 18px;
}
.park-facts > summary {
    cursor: pointer;
    font-family: var(--font-display, 'Newsreader', serif);
    font-size: var(--fs-md, 15px);
    font-weight: 500;
    color: var(--ink-1);
}
.facts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px 24px;
    margin-top: 14px;
}
.fact-cell { font-size: var(--fs-sm, 13px); }
.fact-k {
    font-size: var(--fs-xs, 11px);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink-3, #7C7560);
    margin-bottom: 2px;
}
.fact-v {
    font-family: var(--font-display, 'Newsreader', serif);
    font-size: var(--fs-md, 15px);
    color: var(--ink-1);
}
```

**Verify:** Öppna en park, klicka "About this park" — fält visas.

**Commit:** `feat(assets): collapsible "About this park" facts panel in drilldown`

---

### Task 3.6: Auto-insight text i drill-hero

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` `renderDrilldown` + CSS

**Vad:** En kort, automatiskt genererad mening direkt under park-namnet som sammanfattar vad som driver perioden. Format: "Above budget driven by PR (+3.2pp), despite irradiance −5%". Logik:
1. Om `vs_budget_pct >= 5`: "Above budget" (good).
2. Om `vs_budget_pct <= -5`: "Below budget" (bad).
3. Annars "On budget".
4. Driver: jämför `vs_budget_irr_pct` och `actual_pr_pct − budget_pr_pct` — vilken har störst absolut bidrag?

**Implementation:**

```javascript
function buildInsightText(agg) {
    if (!agg) return '';
    var vs = agg.vs_budget_pct;
    if (vs == null) return '';
    var verdict;
    if (vs >= 5) verdict = 'Above budget';
    else if (vs <= -5) verdict = 'Below budget';
    else verdict = 'On budget';
    var dPr = (agg.actual_pr_pct != null && agg.budget_pr_pct != null)
        ? (agg.actual_pr_pct - agg.budget_pr_pct) : null;
    var dIrr = agg.vs_budget_irr_pct;
    var driver = '';
    if (dPr != null && Math.abs(dPr) >= 1) {
        driver += ' driven by PR ' + (dPr >= 0 ? '+' : '') + fmtNum(dPr, 1) + 'pp';
    }
    if (dIrr != null && Math.abs(dIrr) >= 2) {
        var conn = driver ? (Math.sign(dPr || 0) === Math.sign(dIrr) ? ' and ' : ' despite ') : ' driven by ';
        driver += conn + 'irradiance ' + (dIrr >= 0 ? '+' : '') + fmtNum(dIrr, 1) + '%';
    }
    return verdict + driver + '.';
}
```

I `renderDrilldown` efter `el('drill-meta').innerHTML = ...`:

```javascript
var insight = buildInsightText(agg);
var insightEl = el('drill-insight');
if (insightEl) {
    insightEl.textContent = insight;
    insightEl.style.display = insight ? '' : 'none';
}
```

HTML — lägg till i drill-hero:

```html
<div class="drill-hero">
    <div>
        <h1 class="drill-name"><span id="drill-name"></span><span id="drill-period-suffix" class="page-title-suffix"></span></h1>
        <div class="drill-meta" id="drill-meta"></div>
        <div class="drill-insight" id="drill-insight"></div>
    </div>
</div>
```

CSS:

```css
.drill-insight {
    margin-top: 8px;
    font-family: var(--font-display, 'Newsreader', serif);
    font-style: italic;
    font-size: var(--fs-md, 15px);
    color: var(--ink-2, #5C5848);
    max-width: 60ch;
}
```

**Verify:** Öppna olika parker — texten bör skifta efter prestanda.

**Commit:** `feat(assets): auto-generated insight tagline in drill hero`

---

## Phase 4 — CAPTURE-fliken cross-link

### Task 4.1: Lägg till "Fleet realized capture"-overlay på CAPTURE-fliken

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` capture main chart-rendering

**Vad:** På CAPTURE-flikens "Price evolution"-chart, lägg till en tunn streckad linje per zon som visar `assets.fleet_capture_by_zone[zone]` när användaren har valt SE3 eller SE4 (övriga zoner saknar parker).

Sök i koden efter `capture-main-chart` och hitta var traces byggs. Lägg till en extra trace som hämtas från `DATA.assets.fleet_capture_by_zone[selectedZone]`.

**Implementation steps:**

1. Hitta funktionen som renderar capture-main-chart (sök på `'capture-main-chart'` i filen).
2. Efter befintliga zone-baseload + capture-traces, lägg till:

```javascript
// Fleet realized capture overlay (only when assets data exists for this zone)
var fleetCap = (DATA.assets && DATA.assets.fleet_capture_by_zone && DATA.assets.fleet_capture_by_zone[selectedZone]) || null;
if (fleetCap && fleetCap.length) {
    // Filter to range matching x-axis
    var fxs = fleetCap.map(function(r) { return r.month; });
    var fys = fleetCap.map(function(r) { return r.fleet_capture_eur_mwh; });
    traces.push({
        x: fxs,
        y: fys,
        name: 'Fleet realized (' + selectedZone + ')',
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#5B6BA8', dash: 'dot', width: 2 },
        marker: { size: 5, symbol: 'diamond' },
        hovertemplate: '%{x}<br>Fleet realized: <b>%{y:.1f}</b> €/MWh<extra></extra>',
    });
}
```

(Variabelnamnen `traces` och `selectedZone` ska anpassas till kodens faktiska struktur — läs först.)

**Verify:** Öppna CAPTURE-fliken, växla till SE3 eller SE4, kontrollera att en streckad linje "Fleet realized (SE3)" visas. För SE1/SE2 ska den inte synas.

**Commit:** `feat(capture): overlay fleet realized capture line for SE3/SE4`

---

## Phase 5 — Validation

### Task 5.1: Generera dashboard, full visuell genomgång

**Steg:**

```bash
cd /Users/pontusskog/Documents/Developer/electricity-price
python3 generate_unified_dashboard.py
ls -la Resultat/rapporter/dashboard_unified_v3_*.html | tail -2
open Resultat/rapporter/dashboard_unified_v3_$(date +%Y%m%d).html
```

**Verifieringschecklista:**

- [ ] Sidan laddar utan JS-fel (öppna devtools console)
- [ ] Assets-fliken visar 7 KPI-kort i fleet-strip (Parks, Cap, Energy, Revenue, Capture, vs Budget, Neg-h)
- [ ] Park-tabellen har 11 kolumner inklusive PR/Avail/Capture/Revenue
- [ ] Sortering fungerar på alla nya kolumner
- [ ] CSV-export inkluderar nya kolumner
- [ ] Klick på en park-tile öppnar drilldown
- [ ] Drill-down KPI-strip visar 11 kort (Energy, Revenue, Realized capture, Capture vs baseload, vs Budget, PR, Avail, POA, Yield, Neg-h, Tracker)
- [ ] "About this park"-panel öppnas och visar park-fakta
- [ ] Insight-text visas under park-namn
- [ ] Daily-chart har PR-linje (blå)
- [ ] Loss waterfall-card visas med 7 staplar och MWh/%-toggle fungerar
- [ ] Revenue waterfall-card visas med 4 staplar
- [ ] CAPTURE-fliken visar "Fleet realized"-linjen för SE3/SE4
- [ ] Stale-indikator (gul/röd prick) visas om någon park har data > 36h gammalt
- [ ] Period-toggle (Month/YTD/Year) påverkar alla nya KPIs/grafer korrekt

### Task 5.2: Testa edge-cases

- [ ] Park med saknad spot-data (fram till 2021-11-01): revenue/capture-fält ska visa "–", inte krascha
- [ ] Park med saknad availability: tile ska visa "—" med "no data"
- [ ] Period innan data finns: tom-state-meddelanden visas
- [ ] Resize fönster — chart-layouten ska fortfarande funka

### Task 5.3: Köra existerande tester

```bash
python3 -m pytest tests/ -v 2>&1 | tail -30
```

Ingen regression. Om något test bryts pga ny kolumn i CSV-export — uppdatera testet.

### Task 5.4: Commit final dashboard rebuild

```bash
git add -A
git status
git diff --stat HEAD~10 HEAD
```

Granska att inget oväntat finns med. Verifiera att:
- `elpris/park_revenue.py` är ny
- `elpris/unified_dashboard_data.py` är ändrad
- `elpris/unified_dashboard_v3_html.py` är ändrad
- `tests/test_park_revenue.py` är ny
- Genererad HTML i `Resultat/rapporter/` (inte i git)

---

## Bilagor

### A. Färgsystem (Nordic Editorial)

| Token | Hex | Användning |
|---|---|---|
| `--good` | grön | ≥ +5% mot budget, positiv premium |
| `--warn` | gul/orange | ±5% |
| `--bad` | röd | ≤ −5%, stale data |
| `#2E5C4D` | mörkgrön | Actual energi |
| `#92B53D` | ljusgrön | Yield, totals |
| `#C9A53C` | gul | Budget, POA-irr |
| `#5B6BA8` | blå | PR, fleet realized line |
| `#C16E40` | rost | Expected, actual irr |
| `#B14E45` | röd | Decreasing waterfall |

### B. Identifierad teknisk skuld (för framtiden, inte denna plan)

1. `daily_by_month` håller bara 3 månader — för YTD-vy med dagdata behöver vi öka. Öka `DAILY_HISTORY_MONTHS` till 13 vid behov, men håll koll på JSON-storleken (~17 MB idag, kanske blir 25 MB).
2. Sektion 13 "Top 5 Best/Worst" i `performance_report_html.py` är 100% redundant med drill-down. Ta bort eller etikettera.
3. Inverter-CSV (per-inverter daily yield) finns inte ännu — när Bazefield-extraktorn körs kan inverter-heatmap läggas till.
4. Forward NTM revenue-tile (Nasdaq EPAD × P50) — utmärkt nästa steg när hedge-positioner finns.

### C. Skipped (medvetet bortvalt från denna plan)

- **Intraday 15-min-vy** i drilldown — kräver separat datapayload (~MB per park) och egen UI; bättre som senare separat plan.
- **Hedge ratio** — kräver inputdata om faktiska sälj-positioner som inte finns i repo.
- **Forward NTM revenue** — kräver P50/P90-prognos-logik; defer till separat task.
- **Yesterday's performance-strip** — meningsfullt först när inkrementell daglig pipeline är på plats.
