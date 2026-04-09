# Operations Dashboard Phase 1 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add park constants, extend Bazefield sync with more data points, create operations data module with Fas 1 features (Specific Yield, Negative Price, Tracker Gain, Meter Loss), and wire up a new "Operations" tab in dashboard v2.

**Architecture:** Extend `elpris/bazefield.py` to fetch multiple data points per park + weather station data, store in expanded CSV format. New `elpris/operations_dashboard_data.py` computes feature metrics. New "Operations" tab in `generate_dashboard_v2.py` with green color theme.

**Tech Stack:** Python 3, requests, csv, Plotly.js (already in project)

**Design doc:** `docs/plans/2026-04-09-operations-dashboard-design.md`

---

### Task 1: Add park constants to config

**Files:**
- Modify: `elpris/config.py:88-91`

**Step 1: Add park metadata constants**

Add after `PARKS_PROFILE_DIR` (line 91), before `CSV_FIELDS`:

```python
# Solar park installed capacities (kWp DC)
PARK_CAPACITY_KWP = {
    "horby": 18116,
    "fjallskar": 20745,
    "bjorke": 6943,
    "agerum": 8846,
    "hova": 5917,
    "skakelbacken": 6500,
    "stenstorp": 1133,
    "tangen": 6727,
}

# Export limit as fraction of DC capacity (grid connection constraint)
PARK_EXPORT_LIMIT = {
    "horby": 0.70,
    "fjallskar": 0.70,
    "bjorke": 0.70,
    "agerum": 0.70,
    "hova": 0.70,
    "skakelbacken": 1.00,
    "stenstorp": 1.00,
    "tangen": 0.70,
}

# Park zone mapping (duplicated from bazefield.py for convenience)
PARK_ZONES = {
    "horby": "SE4",
    "fjallskar": "SE3",
    "bjorke": "SE3",
    "agerum": "SE4",
    "hova": "SE3",
    "skakelbacken": "SE3",
    "stenstorp": "SE3",
    "tangen": "SE4",
}
```

**Step 2: Verify**

Run: `python3 -c "from elpris.config import PARK_CAPACITY_KWP, PARK_ZONES; print(len(PARK_CAPACITY_KWP), 'parks')"`
Expected: `8 parks`

**Step 3: Commit**

```bash
git add elpris/config.py
git commit -m "feat: add park capacity, export limit, and zone constants"
```

---

### Task 2: Add weather station IDs to bazefield.py

**Files:**
- Modify: `elpris/bazefield.py`

**Step 1: Add weather station mapping after PARKS dict**

Add after the PARKS dict (after the `"tangen"` entry):

```python
# Weather station Bazefield Object IDs (physical on-site sensors)
PARK_WEATHER_STATIONS = {
    "horby": "1164CB70FB89D000",        # HRB-WS1
    "fjallskar": "117FF1B6A549D000",    # FJL-WS1
    "bjorke": "11BC1241DC89D000",       # BJK-WS1
    "agerum": "11BD1FBAEB49D000",       # AGR-WS1
    "hova": "125F466AA2C9D000",         # HOV-WS3 (primary)
    "skakelbacken": "136768CBEC49D000", # SKB-WS2
    "stenstorp": "12C074165009D000",    # STT-WS1
    "tangen": "13F2E032BE49D000",       # TNG-WS2
}

# Data points to fetch per object type
PARK_POINTS = ["ActivePowerMeter", "ActivePower", "IrradiancePOA", "Availability"]
WEATHER_POINTS = ["IrradianceGHI", "WindSpeed", "Humidity"]
```

**Step 2: Verify**

Run: `python3 -c "from elpris.bazefield import PARK_WEATHER_STATIONS; print(len(PARK_WEATHER_STATIONS), 'weather stations')"`
Expected: `8 weather stations`

**Step 3: Commit**

```bash
git add elpris/bazefield.py
git commit -m "feat: add weather station IDs and data point constants"
```

---

### Task 3: Extend fetch_timeseries to return multiple data points

**Files:**
- Modify: `elpris/bazefield.py` — `fetch_timeseries()` function (lines 90-151)

**Step 1: Modify fetch_timeseries to accept custom points**

Replace the existing `fetch_timeseries` function with:

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_timeseries(
    object_id: str,
    points: list[str],
    from_date: date,
    to_date: date,
    api_key: str | None = None,
) -> dict[str, list[dict]]:
    """Fetch timeseries data from Bazefield for any object.

    Args:
        object_id: Bazefield object ID
        points: List of point names (e.g. ["ActivePowerMeter", "IrradiancePOA"])
        from_date: Start date (inclusive)
        to_date: End date (exclusive)
        api_key: Override API key

    Returns:
        Dict mapping point_name -> list of {timestamp: str, value: float}
    """
    key = api_key or BAZEFIELD_API_KEY
    if not key:
        raise ValueError("BAZEFIELD_API_KEY not set. Add it to .env file.")

    url = f"{BAZEFIELD_BASE_URL}/json/reply/GetDomainPointTimeSeriesAggregated"
    payload = {
        "ObjectIds": [object_id],
        "Points": points,
        "Aggregates": ["AVERAGE"],
        "From": from_date.isoformat(),
        "To": to_date.isoformat(),
        "Interval": "15m",
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()

    data = response.json()
    obj_data = data.get("objects", {}).get(object_id, {}).get("points", {})

    result: dict[str, list[dict]] = {}
    for point_name in points:
        point_series = obj_data.get(point_name, [])
        if not point_series:
            result[point_name] = []
            continue

        ts_list = point_series[0].get("timeSeries", [])
        records = []
        for point in ts_list:
            t_local = point.get("t_local")
            v = point.get("v")
            if t_local is not None and v is not None:
                records.append({"timestamp": t_local, "value": round(v, 4)})
        result[point_name] = records

    return result
```

**Step 2: Add convenience wrapper for park data**

Add right after the new `fetch_timeseries`:

```python
def fetch_park_data(
    park_key: str,
    from_date: date,
    to_date: date,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch extended park data (power, irradiance, availability).

    Returns list of {timestamp, power_mw, active_power_mw, irradiance_poa, availability}.
    """
    park = PARKS[park_key]
    raw = fetch_timeseries(park["id"], PARK_POINTS, from_date, to_date, api_key)

    # Merge all points by timestamp
    by_ts: dict[str, dict] = {}
    for point_name, records in raw.items():
        field_map = {
            "ActivePowerMeter": "power_mw",
            "ActivePower": "active_power_mw",
            "IrradiancePOA": "irradiance_poa",
            "Availability": "availability",
        }
        field = field_map.get(point_name, point_name)
        for rec in records:
            ts = rec["timestamp"]
            if ts not in by_ts:
                by_ts[ts] = {"timestamp": ts}
            by_ts[ts][field] = rec["value"]

    return [by_ts[ts] for ts in sorted(by_ts)]


def fetch_weather_data(
    park_key: str,
    from_date: date,
    to_date: date,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch weather station data for a park.

    Returns list of {timestamp, ghi, wind_speed, humidity}.
    """
    ws_id = PARK_WEATHER_STATIONS.get(park_key)
    if not ws_id:
        return []

    raw = fetch_timeseries(ws_id, WEATHER_POINTS, from_date, to_date, api_key)

    by_ts: dict[str, dict] = {}
    for point_name, records in raw.items():
        field_map = {
            "IrradianceGHI": "ghi",
            "WindSpeed": "wind_speed",
            "Humidity": "humidity",
        }
        field = field_map.get(point_name, point_name)
        for rec in records:
            ts = rec["timestamp"]
            if ts not in by_ts:
                by_ts[ts] = {"timestamp": ts}
            by_ts[ts][field] = rec["value"]

    return [by_ts[ts] for ts in sorted(by_ts)]
```

**Step 3: Update all callers of old fetch_timeseries signature**

The old signature was `fetch_timeseries(park_key, from_date, to_date, api_key)`. It's called by:
- `find_first_data_date()` — update to use `fetch_park_data()` instead
- `download_park()` — update to use `fetch_park_data()` instead

In `find_first_data_date`, replace all calls to `fetch_timeseries(park_key, ...)` with:
```python
test_data = fetch_park_data(park_key, today - timedelta(days=30), today, key)
has_production = any(r.get("power_mw", 0) > 0 for r in test_data)
```
And similarly for the binary search probes.

In `download_park`, the main download loop (around line 310) currently calls `fetch_timeseries(park_key, current, chunk_end, key)`. Replace with `fetch_park_data(park_key, current, chunk_end, key)`.

**Step 4: Update save_park_data for extended columns**

Replace `save_park_data` with:

```python
PARK_CSV_FIELDS = ["timestamp", "power_mw", "active_power_mw", "irradiance_poa", "availability"]

def save_park_data(park_key: str, records: list[dict]) -> int:
    """Append records to park CSV, avoiding duplicates.

    Handles both old format (timestamp, power_mw) and new extended format.
    Returns number of new records written.
    """
    if not records:
        return 0

    csv_path = get_park_csv_path(park_key)
    PARKS_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    # Read existing timestamps and detect format
    existing_timestamps: set[str] = set()
    existing_fields: list[str] = []
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_fields = reader.fieldnames or []
            for row in reader:
                existing_timestamps.add(row["timestamp"])

    # Filter new records
    new_records = [r for r in records if r["timestamp"] not in existing_timestamps]
    if not new_records:
        return 0

    # Determine fieldnames: use extended format for new files, match existing for appends
    if existing_fields and set(existing_fields) != set(PARK_CSV_FIELDS):
        # Old format file — need to rewrite with extended columns
        all_records = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_records.append(row)
        all_records.extend(new_records)
        all_records.sort(key=lambda x: x["timestamp"])

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=PARK_CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for rec in all_records:
                writer.writerow(rec)
    else:
        # Extended format — append
        write_header = not csv_path.exists()
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=PARK_CSV_FIELDS, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerows(new_records)

    return len(new_records)
```

**Step 5: Add weather data save function**

```python
WEATHER_CSV_FIELDS = ["timestamp", "ghi", "wind_speed", "humidity"]

def get_weather_csv_path(park_key: str) -> Path:
    """Get CSV path for weather station data."""
    park = PARKS[park_key]
    return PARKS_PROFILE_DIR / f"{park_key}_{park['zone']}_weather.csv"

def save_weather_data(park_key: str, records: list[dict]) -> int:
    """Save weather data to CSV, avoiding duplicates."""
    if not records:
        return 0

    csv_path = get_weather_csv_path(park_key)
    PARKS_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    existing_timestamps: set[str] = set()
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_timestamps.add(row["timestamp"])

    new_records = [r for r in records if r["timestamp"] not in existing_timestamps]
    if not new_records:
        return 0

    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=WEATHER_CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(new_records)

    return len(new_records)
```

**Step 6: Update download_park to also download weather**

In `download_park()`, after the existing park data download loop, add weather download:

```python
    # Also download weather station data
    if verbose:
        print(f"  Vader...", end=" ", flush=True)
    weather_records = 0
    current = start_date
    while current < end_date:
        chunk_end = min(current + timedelta(days=30), end_date)
        try:
            time.sleep(REQUEST_DELAY)
            w_records = fetch_weather_data(park_key, current, chunk_end, key)
            if w_records:
                saved = save_weather_data(park_key, w_records)
                weather_records += saved
        except Exception:
            pass  # Weather is optional
        current = chunk_end
    if verbose:
        print(f"{weather_records} vader-poster")
```

**Step 7: Verify**

Run: `python3 -c "from elpris.bazefield import fetch_park_data, PARKS; print('OK')"`
Expected: `OK`

Run: `python3 bazefield_download.py --parks horby --start 2025-06-01 --end 2025-06-02`
Expected: downloads park data with extended columns + weather data

**Step 8: Commit**

```bash
git add elpris/bazefield.py
git commit -m "feat: extend Bazefield sync with irradiance, availability, and weather data"
```

---

### Task 4: Run backfill with extended data

**Step 1: Delete old CSVs to force rewrite with new columns**

```bash
# Backup first
cp -r Resultat/profiler/parker/ /tmp/parker_backup/
# Delete to force clean rewrite
rm Resultat/profiler/parker/*.csv
```

**Step 2: Run full backfill**

```bash
python3 bazefield_download.py --backfill
```

This will take 10-20 minutes. All 8 parks re-downloaded with extended columns.

**Step 3: Verify CSV format**

```bash
head -3 Resultat/profiler/parker/horby_SE4.csv
```
Expected: `timestamp,power_mw,active_power_mw,irradiance_poa,availability`

```bash
head -3 Resultat/profiler/parker/horby_SE4_weather.csv
```
Expected: `timestamp,ghi,wind_speed,humidity`

**Step 4: Verify capture price still works (backwards compatibility)**

```bash
python3 -c "from elpris.dashboard_v2_data import load_park_actual_data, PARKS_DIR; d = load_park_actual_data(PARKS_DIR / 'horby_SE4.csv'); print(f'{len(d)} days')"
```
Expected: ~546 days (load_park_actual_data reads only timestamp + power_mw columns via DictReader — new columns ignored)

**Step 5: Commit data**

```bash
git add Resultat/profiler/parker/*.csv
git commit -m "data: re-sync park profiles with extended columns (irradiance, availability, weather)"
```

---

### Task 5: Create operations_dashboard_data.py with Fas 1 features

**Files:**
- Create: `elpris/operations_dashboard_data.py`

**Step 1: Write the module**

```python
"""Operations dashboard data calculations.

Computes metrics for the Operations section of dashboard v2:
- Specific Yield per park (kWh/kWp)
- Negative price exposure
- Tracker gain (Hova vs fixed-tilt)
- Meter loss analysis
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import (
    PARK_CAPACITY_KWP,
    PARK_EXPORT_LIMIT,
    PARK_ZONES,
    PARKS_PROFILE_DIR,
    QUARTERLY_DIR,
)

SWEDEN_TZ = ZoneInfo("Europe/Stockholm")
UTC_TZ = ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_park_15min(park_key: str) -> list[dict]:
    """Load 15-min park data from extended CSV.

    Returns list of {timestamp_utc: datetime, power_mw: float,
    active_power_mw: float|None, irradiance_poa: float|None,
    availability: float|None}.
    """
    zone = PARK_ZONES.get(park_key)
    if not zone:
        return []
    csv_path = PARKS_PROFILE_DIR / f"{park_key}_{zone}.csv"
    if not csv_path.exists():
        return []

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row["timestamp"])
            ts_utc = ts.astimezone(UTC_TZ)
            rec = {
                "timestamp_utc": ts_utc,
                "date": ts_utc.strftime("%Y-%m-%d"),
                "year": ts_utc.year,
                "month": ts_utc.month,
                "power_mw": float(row.get("power_mw") or 0),
            }
            if "active_power_mw" in row and row["active_power_mw"]:
                rec["active_power_mw"] = float(row["active_power_mw"])
            if "irradiance_poa" in row and row["irradiance_poa"]:
                rec["irradiance_poa"] = float(row["irradiance_poa"])
            if "availability" in row and row["availability"]:
                rec["availability"] = float(row["availability"])
            records.append(rec)
    return records


def load_spot_prices_15min(zone: str) -> dict[str, list[dict]]:
    """Load quarterly spot prices as 15-min data.

    Returns dict keyed by ISO date -> list of {timestamp_utc, eur_mwh}.
    """
    zone_dir = QUARTERLY_DIR / zone
    if not zone_dir.exists():
        return {}

    by_date: dict[str, list[dict]] = defaultdict(list)
    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["time_start"])
                ts_utc = ts.astimezone(UTC_TZ)
                date_key = ts_utc.strftime("%Y-%m-%d")
                eur_mwh = float(row["EUR_per_kWh"]) * 1000
                by_date[date_key].append({
                    "timestamp_utc": ts_utc,
                    "eur_mwh": eur_mwh,
                })
    return dict(by_date)


# ---------------------------------------------------------------------------
# Feature 2: Specific Yield
# ---------------------------------------------------------------------------

def calculate_specific_yield() -> dict[str, list[dict]]:
    """Calculate monthly specific yield (kWh/kWp) per park.

    Returns {park_key: [{year, month, yield_kwh_kwp, energy_mwh}, ...]}.
    """
    result: dict[str, list[dict]] = {}

    for park_key, capacity_kwp in PARK_CAPACITY_KWP.items():
        records = load_park_15min(park_key)
        if not records:
            continue

        # Aggregate energy per month
        monthly: dict[tuple[int, int], float] = defaultdict(float)
        for rec in records:
            # energy_mwh = power_mw * 0.25 (15-min interval)
            monthly[(rec["year"], rec["month"])] += rec["power_mw"] * 0.25

        park_data = []
        for (year, month), energy_mwh in sorted(monthly.items()):
            # specific yield: MWh / (kWp / 1000) = MWh / MWp = kWh/kWp
            sy = energy_mwh / (capacity_kwp / 1000)
            park_data.append({
                "year": year,
                "month": month,
                "yield_kwh_kwp": round(sy, 2),
                "energy_mwh": round(energy_mwh, 2),
            })

        result[park_key] = park_data

    return result


# ---------------------------------------------------------------------------
# Feature 10: Negative price exposure
# ---------------------------------------------------------------------------

def calculate_negative_price_exposure() -> dict[str, list[dict]]:
    """Calculate monthly negative price exposure per park.

    Returns {park_key: [{year, month, neg_hours, neg_volume_mwh, neg_revenue_eur}, ...]}.
    """
    result: dict[str, list[dict]] = {}

    for park_key in PARK_CAPACITY_KWP:
        zone = PARK_ZONES[park_key]
        park_data = load_park_15min(park_key)
        spot_data = load_spot_prices_15min(zone)

        if not park_data or not spot_data:
            continue

        # Index park data by timestamp for fast lookup
        park_by_ts: dict[str, float] = {}
        for rec in park_data:
            ts_key = rec["timestamp_utc"].strftime("%Y-%m-%dT%H:%M")
            park_by_ts[ts_key] = rec["power_mw"]

        monthly: dict[tuple[int, int], dict] = defaultdict(
            lambda: {"neg_hours": 0, "neg_volume_mwh": 0, "neg_revenue_eur": 0}
        )

        for date_key, prices in spot_data.items():
            for price_rec in prices:
                ts_key = price_rec["timestamp_utc"].strftime("%Y-%m-%dT%H:%M")
                power = park_by_ts.get(ts_key, 0)
                price = price_rec["eur_mwh"]

                if price < 0 and power > 0:
                    ym = (price_rec["timestamp_utc"].year, price_rec["timestamp_utc"].month)
                    monthly[ym]["neg_hours"] += 0.25
                    monthly[ym]["neg_volume_mwh"] += power * 0.25
                    monthly[ym]["neg_revenue_eur"] += power * 0.25 * price

        park_result = []
        for (year, month), data in sorted(monthly.items()):
            park_result.append({
                "year": year,
                "month": month,
                "neg_hours": round(data["neg_hours"], 2),
                "neg_volume_mwh": round(data["neg_volume_mwh"], 2),
                "neg_revenue_eur": round(data["neg_revenue_eur"], 2),
            })

        result[park_key] = park_result

    return result


# ---------------------------------------------------------------------------
# Feature 11: Tracker gain (Hova vs fixed-tilt SE3 parks)
# ---------------------------------------------------------------------------

def calculate_tracker_gain() -> list[dict]:
    """Calculate Hova tracker gain vs Bjorke + Skakelbacken (fixed SE3).

    Returns [{year, month, sy_hova, sy_fixed_avg, gain_pct}, ...].
    """
    sy_data = calculate_specific_yield()

    hova = {(r["year"], r["month"]): r["yield_kwh_kwp"] for r in sy_data.get("hova", [])}
    bjorke = {(r["year"], r["month"]): r["yield_kwh_kwp"] for r in sy_data.get("bjorke", [])}
    skakelbacken = {(r["year"], r["month"]): r["yield_kwh_kwp"] for r in sy_data.get("skakelbacken", [])}

    result = []
    for ym in sorted(hova):
        sy_h = hova[ym]
        # Need at least one fixed-tilt park for comparison
        fixed_vals = [v for v in [bjorke.get(ym), skakelbacken.get(ym)] if v is not None and v > 0]
        if not fixed_vals or sy_h <= 0:
            continue

        fixed_avg = sum(fixed_vals) / len(fixed_vals)
        gain = (sy_h / fixed_avg - 1) * 100

        result.append({
            "year": ym[0],
            "month": ym[1],
            "sy_hova": round(sy_h, 2),
            "sy_fixed_avg": round(fixed_avg, 2),
            "gain_pct": round(gain, 1),
        })

    return result


# ---------------------------------------------------------------------------
# Feature 14: Meter loss analysis
# ---------------------------------------------------------------------------

def calculate_meter_loss() -> dict[str, list[dict]]:
    """Calculate daily meter loss (inverter sum vs grid meter) per park.

    Returns {park_key: [{year, month, date, loss_pct}, ...]}.
    Only includes days with sufficient production (> 0.1 MW avg).
    """
    result: dict[str, list[dict]] = {}

    for park_key in PARK_CAPACITY_KWP:
        records = load_park_15min(park_key)
        if not records:
            continue

        # Aggregate daily: sum of (active_power - power_meter) / sum of active_power
        daily_inv: dict[str, float] = defaultdict(float)
        daily_meter: dict[str, float] = defaultdict(float)
        daily_count: dict[str, int] = defaultdict(int)

        for rec in records:
            ap = rec.get("active_power_mw")
            pm = rec.get("power_mw", 0)
            if ap is not None and ap > 0.1 and pm > 0:
                daily_inv[rec["date"]] += ap
                daily_meter[rec["date"]] += pm
                daily_count[rec["date"]] += 1

        park_data = []
        for date_key in sorted(daily_inv):
            if daily_count[date_key] < 4:  # Need at least 1 hour of data
                continue
            inv_total = daily_inv[date_key]
            meter_total = daily_meter[date_key]
            if inv_total > 0:
                loss_pct = (1 - meter_total / inv_total) * 100
                d = date.fromisoformat(date_key)
                park_data.append({
                    "year": d.year,
                    "month": d.month,
                    "date": date_key,
                    "loss_pct": round(loss_pct, 2),
                })

        if park_data:
            result[park_key] = park_data

    return result


# ---------------------------------------------------------------------------
# Main calculator
# ---------------------------------------------------------------------------

def calculate_operations_data() -> dict:
    """Calculate all operations dashboard data.

    Returns dict with all feature data for JSON embedding.
    """
    print("Beraknar Operations-data...")

    print("  Specific Yield...")
    specific_yield = calculate_specific_yield()

    print("  Negativ pris-exponering...")
    negative_price = calculate_negative_price_exposure()

    print("  Tracker-gain...")
    tracker_gain = calculate_tracker_gain()

    print("  Meterforlust...")
    meter_loss = calculate_meter_loss()

    return {
        "parks": list(PARK_CAPACITY_KWP.keys()),
        "park_zones": PARK_ZONES,
        "park_capacity_kwp": PARK_CAPACITY_KWP,
        "park_export_limit": PARK_EXPORT_LIMIT,
        "specific_yield": specific_yield,
        "negative_price": negative_price,
        "tracker_gain": tracker_gain,
        "meter_loss": meter_loss,
    }
```

**Step 2: Verify module loads**

Run: `python3 -c "from elpris.operations_dashboard_data import calculate_operations_data; print('OK')"`
Expected: `OK`

**Step 3: Test calculation with real data**

Run: `python3 -c "
from elpris.operations_dashboard_data import calculate_specific_yield
sy = calculate_specific_yield()
for park, data in sy.items():
    if data:
        latest = data[-1]
        print(f'{park}: {latest[\"year\"]}-{latest[\"month\"]:02d} = {latest[\"yield_kwh_kwp\"]:.1f} kWh/kWp')
"`
Expected: values between 0-150 kWh/kWp per month

**Step 4: Commit**

```bash
git add elpris/operations_dashboard_data.py
git commit -m "feat: add operations dashboard data module with Fas 1 features"
```

---

### Task 6: Wire up Operations tab in dashboard v2

**Files:**
- Modify: `generate_dashboard_v2.py`
- Modify: `elpris/dashboard_v2_data.py` (add operations data to main calc)

**Step 1: Import and call operations calculation**

In `elpris/dashboard_v2_data.py`, at the end of `calculate_dashboard_v2_data()`, add:

```python
    # Operations data
    print("Beraknar Operations-data...")
    from .operations_dashboard_data import calculate_operations_data
    operations = calculate_operations_data()
```

And include it in the return dict:
```python
    return {
        ...existing keys...,
        "operations": operations,
    }
```

**Step 2: In generate_dashboard_v2.py, add CSS for operations color theme**

After `body.product-futures` CSS block (around line 78), add:

```css
body.product-operations {
    --product: #4ADE80;
    --product-dim: rgba(74, 222, 128, 0.15);
    --product-glow: rgba(74, 222, 128, 0.35);
    --product-hint: rgba(74, 222, 128, 0.30);
    --product-contrast: #0b1220;
}
```

**Step 3: Add Operations tab button**

Find the existing tab buttons in the HTML (search for `Capture` tab button) and add a fourth:

```html
<button class="tab-btn" onclick="switchDashboard('operations')">Operations</button>
```

**Step 4: Add Operations sidebar container**

Add a hidden sidebar div for operations (similar to `#bess-sidebar`):

```html
<div id="operations-sidebar" style="display:none"></div>
```

**Step 5: Extend the render() function**

In the JavaScript `render()` function (line ~863), add operations case:

```javascript
}} else if (state.dashboard === 'operations') {{
    renderOperations();
}}
```

**Step 6: Add buildOperationsSidebar() function**

```javascript
function buildOperationsSidebar() {{
    const sidebar = document.getElementById('operations-sidebar');
    const OPS = DATA.operations;
    let html = '<div class="sidebar-section"><div class="sidebar-title">PARKER</div>';
    OPS.parks.forEach(pk => {{
        const zone = OPS.park_zones[pk];
        const checked = (state.ops_parks || new Set(OPS.parks)).has(pk) ? 'checked' : '';
        html += '<label class="sidebar-item"><input type="checkbox" data-ops-park="' + pk + '" ' + checked + '>';
        html += '<span class="color-dot" style="background:' + (parkColor(pk)) + '"></span>';
        html += pk.charAt(0).toUpperCase() + pk.slice(1) + ' (' + zone + ')';
        html += '</label>';
    }});
    html += '</div>';
    sidebar.innerHTML = html;

    sidebar.querySelectorAll('input[type="checkbox"]').forEach(cb => {{
        cb.addEventListener('change', () => {{
            const pk = cb.dataset.opsPark;
            if (!state.ops_parks) state.ops_parks = new Set(OPS.parks);
            if (cb.checked) state.ops_parks.add(pk);
            else state.ops_parks.delete(pk);
            renderOperations();
        }});
    }});
}}

function parkColor(pk) {{
    const colors = ['#a78bfa','#67e8f9','#86efac','#fde68a','#fca5a5','#c4b5fd','#99f6e4','#bbf7d0'];
    const idx = DATA.operations.parks.indexOf(pk);
    return colors[idx % colors.length];
}}
```

**Step 7: Add renderOperations() with Specific Yield chart**

```javascript
function renderOperations() {{
    const OPS = DATA.operations;
    const parks = state.ops_parks ? [...state.ops_parks] : OPS.parks;
    const container = document.getElementById('main-chart');

    // Feature selector
    if (!state.ops_feature) state.ops_feature = 'specific_yield';

    document.getElementById('chart-title').textContent = 'Operations - ' + featureLabel(state.ops_feature);

    if (state.ops_feature === 'specific_yield') renderSpecificYield(parks, OPS);
    else if (state.ops_feature === 'negative_price') renderNegativePrice(parks, OPS);
    else if (state.ops_feature === 'tracker_gain') renderTrackerGain(OPS);
    else if (state.ops_feature === 'meter_loss') renderMeterLoss(parks, OPS);
}}

function featureLabel(f) {{
    return {{
        'specific_yield': 'Specific Yield (kWh/kWp)',
        'negative_price': 'Negativ pris-exponering',
        'tracker_gain': 'Tracker-gain (Hova vs fast)',
        'meter_loss': 'Meterforlust (%)',
    }}[f] || f;
}}

function renderSpecificYield(parks, OPS) {{
    const traces = [];
    parks.forEach(pk => {{
        const data = OPS.specific_yield[pk] || [];
        traces.push({{
            x: data.map(d => d.year + '-' + String(d.month).padStart(2, '0')),
            y: data.map(d => d.yield_kwh_kwp),
            name: pk.charAt(0).toUpperCase() + pk.slice(1) + ' (' + OPS.park_zones[pk] + ')',
            type: 'bar',
            marker: {{ color: parkColor(pk) }},
        }});
    }});

    Plotly.react('main-chart', traces, {{
        ...darkLayout(),
        barmode: 'group',
        yaxis: {{ title: 'kWh/kWp', gridcolor: '#2a3550' }},
        xaxis: {{ title: 'Manad', gridcolor: '#2a3550' }},
    }});
}}

function renderNegativePrice(parks, OPS) {{
    const traces = [];
    parks.forEach(pk => {{
        const data = OPS.negative_price[pk] || [];
        if (data.length === 0) return;
        traces.push({{
            x: data.map(d => d.year + '-' + String(d.month).padStart(2, '0')),
            y: data.map(d => d.neg_revenue_eur),
            name: pk.charAt(0).toUpperCase() + pk.slice(1),
            type: 'bar',
            marker: {{ color: parkColor(pk) }},
        }});
    }});

    Plotly.react('main-chart', traces, {{
        ...darkLayout(),
        barmode: 'stack',
        yaxis: {{ title: 'Negativ intakt (EUR)', gridcolor: '#2a3550' }},
        xaxis: {{ title: 'Manad' }},
    }});
}}

function renderTrackerGain(OPS) {{
    const data = OPS.tracker_gain || [];
    Plotly.react('main-chart', [{{
        x: data.map(d => d.year + '-' + String(d.month).padStart(2, '0')),
        y: data.map(d => d.gain_pct),
        type: 'bar',
        marker: {{ color: data.map(d => d.gain_pct >= 0 ? '#4ADE80' : '#f87171') }},
        name: 'Tracker-gain',
    }}], {{
        ...darkLayout(),
        yaxis: {{ title: 'Gain (%)', zeroline: true, zerolinecolor: '#fff', gridcolor: '#2a3550' }},
        xaxis: {{ title: 'Manad' }},
        shapes: [{{ type: 'line', y0: 0, y1: 0, x0: 0, x1: 1, xref: 'paper', line: {{ color: '#fff', width: 1, dash: 'dash' }} }}],
    }});
}}

function renderMeterLoss(parks, OPS) {{
    const traces = [];
    parks.forEach(pk => {{
        const data = OPS.meter_loss[pk] || [];
        if (data.length === 0) return;
        // Aggregate to monthly average
        const monthly = {{}};
        data.forEach(d => {{
            const key = d.year + '-' + String(d.month).padStart(2, '0');
            if (!monthly[key]) monthly[key] = [];
            monthly[key].push(d.loss_pct);
        }});
        const keys = Object.keys(monthly).sort();
        traces.push({{
            x: keys,
            y: keys.map(k => monthly[k].reduce((a,b) => a+b, 0) / monthly[k].length),
            name: pk.charAt(0).toUpperCase() + pk.slice(1),
            type: 'scatter',
            mode: 'lines+markers',
            line: {{ color: parkColor(pk) }},
        }});
    }});

    Plotly.react('main-chart', traces, {{
        ...darkLayout(),
        yaxis: {{ title: 'Forlust (%)', gridcolor: '#2a3550' }},
        xaxis: {{ title: 'Manad' }},
        shapes: [
            {{ type: 'rect', y0: 0, y1: 2, x0: 0, x1: 1, xref: 'paper', fillcolor: 'rgba(74,222,128,0.1)', line: {{ width: 0 }} }},
            {{ type: 'rect', y0: 2, y1: 4, x0: 0, x1: 1, xref: 'paper', fillcolor: 'rgba(250,204,21,0.1)', line: {{ width: 0 }} }},
            {{ type: 'rect', y0: 4, y1: 10, x0: 0, x1: 1, xref: 'paper', fillcolor: 'rgba(248,113,113,0.1)', line: {{ width: 0 }} }},
        ],
    }});
}}
```

**Step 8: Update switchDashboard() to handle operations**

Find `switchDashboard` function and add operations sidebar visibility toggle (same pattern as bess/futures).

**Step 9: Add operations feature toggle buttons** in the sidebar or nav area.

**Step 10: Verify**

Run: `python3 generate_dashboard_v2.py`
Open the generated HTML, click "Operations" tab.

**Step 11: Commit**

```bash
git add elpris/dashboard_v2_data.py elpris/operations_dashboard_data.py generate_dashboard_v2.py
git commit -m "feat: add Operations tab with Specific Yield, Negative Price, Tracker Gain, Meter Loss"
```

---

### Task 7: Verify end-to-end and update docs

**Step 1: Generate full dashboard**

```bash
python3 generate_dashboard_v2.py
```

**Step 2: Open and verify each feature**

Open `Resultat/rapporter/dashboard_v2_*.html`:
- Operations tab visible with green theme
- Specific Yield chart shows monthly bars per park
- Negative Price shows revenue impact
- Tracker Gain shows Hova vs fixed percentages
- Meter Loss shows daily loss trends

**Step 3: Update CLAUDE.md**

Add Operations section to dashboard documentation.

**Step 4: Final commit**

```bash
git add -A
git commit -m "docs: update CLAUDE.md with Operations dashboard section"
```
