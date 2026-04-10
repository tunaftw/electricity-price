"""Bazefield monitoring platform API client.

Syncs actual production data (ActivePowerMeter, 15-min) from Svea Solar's
solar parks for capture price calculations.

API base: https://sveasolar.bazefield.com/BazeField.Services/api/
Auth: Bearer token via BAZEFIELD_API_KEY in .env
"""

from __future__ import annotations

import csv
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import PARKS_PROFILE_DIR, PROJECT_ROOT, REQUEST_DELAY

# Bazefield API configuration
BAZEFIELD_BASE_URL = "https://sveasolar.bazefield.com/BazeField.Services/api"


def _load_env_file() -> dict[str, str]:
    """Load environment variables from .env file if it exists."""
    env_path = PROJECT_ROOT / ".env"
    env_vars = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def _get_api_key() -> str:
    """Get Bazefield API key from environment or .env file."""
    key = os.environ.get("BAZEFIELD_API_KEY", "")
    if key:
        return key
    env_vars = _load_env_file()
    return env_vars.get("BAZEFIELD_API_KEY", "")


BAZEFIELD_API_KEY = _get_api_key()

# Solar park definitions
PARKS = {
    "horby":        {"id": "1164AFE219C9D000", "zone": "SE4", "name": "Hörby"},
    "fjallskar":    {"id": "117FEB196CC9D000", "zone": "SE3", "name": "Fjällskär"},
    "bjorke":       {"id": "11BC114AFFC9D000", "zone": "SE3", "name": "Björke"},
    "agerum":       {"id": "11BD1C992309D000", "zone": "SE4", "name": "Agerum"},
    "hova":         {"id": "1226CE0630C9D000", "zone": "SE3", "name": "Hova"},
    "skakelbacken": {"id": "12BC5B932DC9D000", "zone": "SE3", "name": "Skakelbacken"},
    "stenstorp":    {"id": "12C0707193C9D000", "zone": "SE3", "name": "Stenstorp"},
    "tangen":       {"id": "13F29EF630C9D000", "zone": "SE4", "name": "Tången"},
}

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

# Per-park irradiance source override (POA workaround)
# Bazefield's IrradiancePOA on the park object averages multiple sensors,
# some of which report 0 — yielding values ~50% of reality. Workaround:
# fetch IrradiancePOA from a dedicated child object (TS = transformer
# station, WS = weather station, SATWST = satellite weather station).
# Auto-discovered 2026-04-10 by checking IrradiancePOA on all child objects
# of each park and picking the one with the highest peak value.
#
# Format: park_key → either a single object_id (str) for static mapping,
# or a list of (start_date_iso, object_id) tuples for time-dependent
# switching. The list must be sorted ascending by start_date. For a
# given timestamp, the latest entry where start_date <= timestamp wins.
PARK_IRRADIANCE_OVERRIDES: dict[str, str | list[tuple[str, str]]] = {
    # Hörby: HRB-TS1 stopped working ~2026-04-01 per AM team. Use HRB-TS2
    # from April onwards (will be reconfigured during SCADA migration).
    "horby": [
        ("2024-01-01", "11661A83D009D000"),  # HRB-TS1 from start
        ("2026-04-01", "11662CA0D4C9D000"),  # HRB-TS2 from April 2026
    ],
    "fjallskar":    "124DEAB2C9C9D000",  # FJL-SATWST (max ~346 W/m²)
    "bjorke":       "1271E821AE89D000",  # BJK-SATWST1 (max ~294 W/m²)
    "agerum":       "1271E8586F49D000",  # AGR-SATWST1 (max ~263 W/m²)
    "hova":         "1271E89EAF89D000",  # HOV-SATWST1 (peak 810 W/m², total 84.3 kWh/m² mar)
    "skakelbacken": "13A6D2E2E989D000",  # SKB-SATWST1 (max ~201 W/m²)
    "stenstorp":    "13A6D7CFA309D000",  # STT-SATWST1 (max ~185 W/m²)
    "tangen":       "1400FCE2BFC9D000",  # TNG-SATWST (max ~266 W/m²)
}


def _get_irradiance_segments(
    park_key: str,
    park_object_id: str,
    from_date: date,
    to_date: date,
) -> list[tuple[str, date, date]]:
    """Returnera lista med (object_id, segment_start, segment_end) för POA-fetch.

    Hanterar både statiska och tidsbaserade overrides. Om parken inte har
    någon override returnerar den ett enda segment med park-objektets ID.
    """
    override = PARK_IRRADIANCE_OVERRIDES.get(park_key)

    # No override: fetch from park object itself
    if override is None:
        return [(park_object_id, from_date, to_date)]

    # Static override (single string)
    if isinstance(override, str):
        return [(override, from_date, to_date)]

    # Time-dependent override (list of tuples)
    entries = sorted(override, key=lambda e: e[0])
    segments: list[tuple[str, date, date]] = []
    current_start = from_date
    current_object: str | None = None

    for entry_start_iso, entry_object_id in entries:
        entry_start = date.fromisoformat(entry_start_iso)
        if entry_start >= to_date:
            break
        if entry_start > current_start:
            if current_object is not None:
                segments.append((current_object, current_start, entry_start))
            current_start = entry_start
        current_object = entry_object_id

    if current_object is not None and current_start < to_date:
        segments.append((current_object, current_start, to_date))

    # If first entry was after from_date, fall back to park object for the gap
    if segments and segments[0][1] > from_date:
        segments.insert(0, (park_object_id, from_date, segments[0][1]))

    return segments or [(park_object_id, from_date, to_date)]


def get_park_csv_path(park_key: str) -> Path:
    """Get CSV file path for a park's production profile."""
    park = PARKS[park_key]
    return PARKS_PROFILE_DIR / f"{park_key}_{park['zone']}.csv"


def get_latest_synced_date(park_key: str) -> date | None:
    """Read the last timestamp from existing CSV to find where we left off."""
    csv_path = get_park_csv_path(park_key)
    if not csv_path.exists():
        return None

    last_ts = None
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            last_ts = row["timestamp"]

    if last_ts:
        dt = datetime.fromisoformat(last_ts)
        return dt.date()

    return None


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
                # Bazefield kan returnera numeriska värden eller strängar
                # (t.ex. fault codes). Konvertera och hoppa över ogiltiga.
                try:
                    val = round(float(v), 4)
                except (TypeError, ValueError):
                    continue
                records.append({"timestamp": t_local, "value": val})
        result[point_name] = records

    return result


def fetch_park_data(
    park_key: str,
    from_date: date,
    to_date: date,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch extended park data (power, irradiance, availability).

    Returns list of {timestamp, power_mw, active_power_mw, irradiance_poa, availability}.

    If the park has a PARK_IRRADIANCE_OVERRIDES entry, IrradiancePOA is fetched
    from the override object(s) instead of the park object — workaround for the
    broken averaged POA point on the park object. Override can be a single
    object_id or a time-dependent list of (start_date, object_id) tuples.
    """
    park = PARKS[park_key]

    # Fetch power and availability from park object (always)
    park_points = ["ActivePowerMeter", "ActivePower", "Availability"]
    raw = fetch_timeseries(park["id"], park_points, from_date, to_date, api_key)

    # Fetch IrradiancePOA from override segments (handles time-dependent
    # switching when a sensor stops working and we need to use another)
    segments = _get_irradiance_segments(park_key, park["id"], from_date, to_date)
    all_irr_records: list[dict] = []
    for obj_id, seg_start, seg_end in segments:
        seg_raw = fetch_timeseries(
            obj_id, ["IrradiancePOA"], seg_start, seg_end, api_key
        )
        all_irr_records.extend(seg_raw.get("IrradiancePOA", []))
    raw["IrradiancePOA"] = all_irr_records

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


def find_first_data_date(park_key: str, api_key: str | None = None) -> date | None:
    """Binary search backwards to find the first date with non-zero production data.

    Searches from today backwards. Returns None if no data found.
    """
    key = api_key or BAZEFIELD_API_KEY

    # Start with a coarse search: check month-by-month going back
    today = date.today()
    # Go back up to 3 years
    earliest_probe = today - timedelta(days=3 * 365)

    # First: check if there's any data at all (test recent month)
    test_data = fetch_park_data(park_key, today - timedelta(days=30), today, key)
    has_production = any(r.get("power_mw", 0) > 0 for r in test_data)
    if not has_production:
        return None

    # Binary search for the first month with data
    low = earliest_probe
    high = today - timedelta(days=30)

    while (high - low).days > 35:
        mid = low + (high - low) / 2
        # Normalize to date
        mid_date = date(mid.year, mid.month, mid.day)
        probe_end = mid_date + timedelta(days=7)

        time.sleep(REQUEST_DELAY)
        probe = fetch_park_data(park_key, mid_date, probe_end, key)
        if any(r.get("power_mw", 0) > 0 for r in probe):
            high = mid_date
        else:
            low = mid_date + timedelta(days=7)

    # Refine: check week by week in the found range
    current = low
    while current <= high:
        time.sleep(REQUEST_DELAY)
        probe = fetch_park_data(park_key, current, current + timedelta(days=7), key)
        if any(r.get("power_mw", 0) > 0 for r in probe):
            # Found it — refine to day level
            for day_offset in range(7):
                day = current + timedelta(days=day_offset)
                time.sleep(REQUEST_DELAY)
                probe = fetch_park_data(park_key, day, day + timedelta(days=1), key)
                if any(r.get("power_mw", 0) > 0 for r in probe):
                    return day
        current += timedelta(days=7)

    return low


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


# ---------------------------------------------------------------------------
# Inverter-level data (Phase 6: SCADA via Bazefield)
# ---------------------------------------------------------------------------

INVERTER_DAILY_FIELDS = [
    "date", "inverter_name", "energy_kwh", "max_power_kw",
    "rated_kw", "capacity_factor_pct",
]

INVERTER_EVENT_FIELDS = [
    "inverter_name", "event_name", "event_code", "event_type",
    "time_start_utc", "time_end_utc", "duration_min", "description",
]

INVERTER_DIR = PARKS_PROFILE_DIR / "inverters"


def get_inverter_yield_csv_path(park_key: str) -> Path:
    """Returnera CSV-sökväg för en parks dagliga inverter-yield."""
    return INVERTER_DIR / f"{park_key}_daily_yield.csv"


def get_inverter_events_csv_path(park_key: str) -> Path:
    """Returnera CSV-sökväg för en parks alarm-events."""
    return INVERTER_DIR / f"{park_key}_events.csv"


def fetch_inverter_daily_yield(
    park_key: str,
    from_date: date,
    to_date: date,
    api_key: str | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Hämta daglig yield per inverter för en park.

    För varje inverter i parken hämtas TotalEnergyProduced.1h (timvärden)
    och ActivePower (15-min) från Bazefield, sedan aggregeras till
    dagliga totaler.

    Returns: [{date, inverter_name, energy_kwh, max_power_kw, rated_kw,
               capacity_factor_pct}, ...]
    """
    from .inverter_registry import get_inverters

    inverters = get_inverters(park_key)
    if not inverters:
        return []

    all_records: list[dict] = []
    for idx, inv in enumerate(inverters, 1):
        if verbose:
            print(f"    [{idx}/{len(inverters)}] {inv['name']}...", end=" ", flush=True)

        try:
            time.sleep(REQUEST_DELAY)
            raw = fetch_timeseries(
                inv["id"],
                ["TotalEnergyProduced.1h", "ActivePower"],
                from_date,
                to_date,
                api_key,
            )
        except Exception as e:
            if verbose:
                print(f"FEL: {e}")
            continue

        # Aggregera per datum
        daily_energy: dict[str, float] = {}
        daily_max_power: dict[str, float] = {}

        # Energi-poster (timvärden) — summera per dag
        for rec in raw.get("TotalEnergyProduced.1h", []):
            date_str = rec["timestamp"][:10]
            daily_energy[date_str] = daily_energy.get(date_str, 0.0) + float(rec["value"])

        # Max power per dag (från ActivePower 15-min)
        for rec in raw.get("ActivePower", []):
            date_str = rec["timestamp"][:10]
            v = float(rec["value"])
            if date_str not in daily_max_power or v > daily_max_power[date_str]:
                daily_max_power[date_str] = v

        # Bygg dagliga rader
        rated = inv["rated_kw"]
        all_dates = sorted(set(daily_energy.keys()) | set(daily_max_power.keys()))
        for date_str in all_dates:
            energy = daily_energy.get(date_str, 0.0)
            max_p = daily_max_power.get(date_str, 0.0)
            cf_pct = (energy / (rated * 24.0) * 100.0) if rated > 0 else 0.0
            # Sanity cap (Sineng kan kortvarigt peaka över rated)
            if cf_pct > 110:
                cf_pct = 110
            all_records.append({
                "date": date_str,
                "inverter_name": inv["name"],
                "energy_kwh": round(energy, 2),
                "max_power_kw": round(max_p, 2),
                "rated_kw": rated,
                "capacity_factor_pct": round(cf_pct, 2),
            })

        if verbose:
            print(f"{len(all_dates)} dagar")

    return all_records


# Event-namn som ska filtreras bort som "brus" — operationella status-ändringar
# rapporteras som eventType=='Alarm' men är inte verkliga fel
_NOISE_EVENT_PATTERNS = (
    "Idle",                       # Huawei: Idle: No irradiation, etc.
    "On-grid",                    # Huawei: On-grid (normal drift), undantag: Power limit
    "Starting",                   # Huawei: Starting (uppstart)
    "Standby",                    # Huawei/Sungrow: Standby
    "Inspecting",                 # Huawei: Inspecting
    "EVENT-",                     # Generiska EVENT- (NightHours, DaylightHours)
)

# Specifika namn att alltid filtrera (inte mönster)
_NOISE_EVENT_NAMES = {
    "Asset_no_comm",              # Sineng: kommunikationsfel (inte produktionsfel)
    "Comm_error",                 # Sineng: dito
}

# Patterns att ALLTID behålla även om de matchar brus-patterns
_KEEP_PATTERNS = (
    "Fault",                      # Allt med Fault i namnet är ett verkligt fel
    "Error",                      # Allt med Error
    "Power limit",                # Curtailment är intressant
    "Curtailment",
)


def _is_noise_event(event_name: str) -> bool:
    """Avgör om en event är operationellt brus snarare än verkligt fel."""
    if not event_name:
        return True

    # Alltid behåll om matchar keep-pattern
    for keep in _KEEP_PATTERNS:
        if keep in event_name:
            return False

    # Specifika namn alltid brus
    if event_name in _NOISE_EVENT_NAMES:
        return True

    # Pattern-baserad filtrering
    for pattern in _NOISE_EVENT_PATTERNS:
        if pattern in event_name:
            return True

    return False


def fetch_inverter_events(
    park_key: str,
    from_date: date,
    to_date: date,
    api_key: str | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Hämta alarm-events per inverter för en park.

    Använder ObjectEventsHistoryGetRequest. Filtrerar till eventType=='Alarm'
    OCH _is_noise_event()=False (exkluderar idle-states, kommunikationsglitches
    och andra operationella brus-events).

    Returns: [{inverter_name, event_name, event_code, event_type,
               time_start_utc, time_end_utc, duration_min, description}, ...]
    """
    from .inverter_registry import get_inverters

    inverters = get_inverters(park_key)
    if not inverters:
        return []

    key = api_key or BAZEFIELD_API_KEY
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    url = f"{BAZEFIELD_BASE_URL}/json/reply/ObjectEventsHistoryGetRequest"

    all_events: list[dict] = []
    for idx, inv in enumerate(inverters, 1):
        if verbose:
            print(f"    [{idx}/{len(inverters)}] {inv['name']}...", end=" ", flush=True)

        payload = {
            "ObjectIds": [inv["id"]],
            "From": f"{from_date.isoformat()}T00:00:00Z",
            "To": f"{to_date.isoformat()}T23:59:59Z",
        }

        try:
            time.sleep(REQUEST_DELAY)
            r = requests.post(url, json=payload, headers=headers, timeout=60)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            if verbose:
                print(f"FEL: {e}")
            continue

        events = data if isinstance(data, list) else data.get("events", [])
        if not isinstance(events, list):
            events = []

        kept = 0
        for evt in events:
            event_type = evt.get("eventType", "")
            if event_type != "Alarm":
                continue  # Skippa Status, EVENT-NightHours etc.

            event_name = evt.get("eventName", "")
            if _is_noise_event(event_name):
                continue  # Skippa brus (idle, on-grid, comm errors)

            event_code_obj = evt.get("eventCode", {})
            event_code = event_code_obj.get("code", 0) if isinstance(event_code_obj, dict) else 0
            time_start = evt.get("timeStart", "")
            time_end = evt.get("timeEnd", "")
            description = evt.get("eventDescription", "")

            # Beräkna duration i minuter
            duration_min = 0.0
            if time_start and time_end:
                try:
                    ts_start = datetime.fromisoformat(time_start.replace("Z", "+00:00"))
                    ts_end = datetime.fromisoformat(time_end.replace("Z", "+00:00"))
                    duration_min = round((ts_end - ts_start).total_seconds() / 60.0, 2)
                except (ValueError, TypeError):
                    pass

            all_events.append({
                "inverter_name": inv["name"],
                "event_name": event_name,
                "event_code": event_code,
                "event_type": event_type,
                "time_start_utc": time_start,
                "time_end_utc": time_end,
                "duration_min": duration_min,
                "description": description,
            })
            kept += 1

        if verbose:
            print(f"{kept} alarms")

    return all_events


def save_inverter_yield_csv(park_key: str, records: list[dict]) -> int:
    """Spara daglig inverter-yield till CSV (upsert med deduplicering).

    Dedup-nyckel: (date, inverter_name).
    Returnerar antal nya rader skrivna.
    """
    if not records:
        return 0

    csv_path = get_inverter_yield_csv_path(park_key)
    INVERTER_DIR.mkdir(parents=True, exist_ok=True)

    # Läs befintliga rader och bygg dedup-set
    existing: dict[tuple[str, str], dict] = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["date"], row["inverter_name"])
                existing[key] = row

    # Lägg till/uppdatera nya rader
    for rec in records:
        key = (rec["date"], rec["inverter_name"])
        existing[key] = {k: rec.get(k, "") for k in INVERTER_DAILY_FIELDS}

    # Skriv ut allt sorterat
    sorted_rows = sorted(existing.values(), key=lambda r: (r["date"], r["inverter_name"]))
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INVERTER_DAILY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted_rows)

    return len(records)


def save_inverter_events_csv(park_key: str, records: list[dict]) -> int:
    """Spara alarm-events till CSV (upsert med deduplicering).

    Dedup-nyckel: (inverter_name, event_name, time_start_utc).
    Returnerar antal nya rader skrivna.
    """
    if not records:
        return 0

    csv_path = get_inverter_events_csv_path(park_key)
    INVERTER_DIR.mkdir(parents=True, exist_ok=True)

    existing: dict[tuple, dict] = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["inverter_name"], row["event_name"], row["time_start_utc"])
                existing[key] = row

    for rec in records:
        key = (rec["inverter_name"], rec["event_name"], rec["time_start_utc"])
        existing[key] = {k: rec.get(k, "") for k in INVERTER_EVENT_FIELDS}

    sorted_rows = sorted(
        existing.values(),
        key=lambda r: (r["time_start_utc"], r["inverter_name"]),
    )
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INVERTER_EVENT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted_rows)

    return len(records)


def download_park_inverters(
    park_key: str,
    start_date: date | None = None,
    end_date: date | None = None,
    api_key: str | None = None,
    verbose: bool = True,
) -> dict:
    """Hämta inverter-nivå data + alarm-events för en park.

    Args:
        park_key: Park-nyckel (t.ex. "horby")
        start_date: Start-datum (default: 2026-01-01)
        end_date: Slut-datum (default: idag)
        api_key: Override API-nyckel
        verbose: Logga progress

    Returns:
        dict med statistik (yield_records, event_records)
    """
    park = PARKS[park_key]

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        # Default: senaste 100 dagarna
        start_date = end_date - timedelta(days=100)

    if verbose:
        print(f"\n{park['name']} ({park_key}, {park['zone']}) — invertrar")
        print("-" * 50)
        print(f"  Period: {start_date} -> {end_date}")
        print(f"  Hämtar daglig yield per inverter...")

    yield_records = fetch_inverter_daily_yield(
        park_key, start_date, end_date, api_key, verbose=verbose
    )
    yield_saved = save_inverter_yield_csv(park_key, yield_records)

    if verbose:
        print(f"  Sparade {yield_saved} yield-rader")
        print(f"  Hämtar alarm-events per inverter...")

    event_records = fetch_inverter_events(
        park_key, start_date, end_date, api_key, verbose=verbose
    )
    event_saved = save_inverter_events_csv(park_key, event_records)

    if verbose:
        print(f"  Sparade {event_saved} alarm-events")

    return {
        "park": park_key,
        "yield_records": yield_saved,
        "event_records": event_saved,
    }


def download_park(
    park_key: str,
    start_date: date | None = None,
    end_date: date | None = None,
    backfill: bool = False,
    verbose: bool = True,
    api_key: str | None = None,
) -> dict:
    """Download production data for a single park.

    Args:
        park_key: Key from PARKS dict
        start_date: Override start date
        end_date: Override end date (default: today)
        backfill: If True, search for first available data date
        verbose: Print progress
        api_key: Override API key

    Returns:
        Dict with download statistics
    """
    key = api_key or BAZEFIELD_API_KEY
    park = PARKS[park_key]

    if verbose:
        print(f"\n{park['name']} ({park_key}, {park['zone']})")
        print("-" * 40)

    if end_date is None:
        end_date = date.today()

    if start_date is None:
        if backfill:
            if verbose:
                print("  Söker första datum med data...", end=" ", flush=True)
            first = find_first_data_date(park_key, key)
            if first is None:
                if verbose:
                    print("ingen data hittad")
                return {"park": park_key, "total_records": 0, "status": "no_data"}
            start_date = first
            if verbose:
                print(f"{first}")
        else:
            latest = get_latest_synced_date(park_key)
            if latest:
                start_date = latest  # Re-download last day to fill gaps
                if verbose:
                    print(f"  Befintlig data t.o.m. {latest}, fortsätter därifrån")
            else:
                if verbose:
                    print("  Ingen befintlig data — kör med --backfill för historik")
                    print("  Laddar ner senaste 30 dagarna som start...")
                start_date = end_date - timedelta(days=30)

    if start_date >= end_date:
        if verbose:
            print("  Redan uppdaterad!")
        return {"park": park_key, "total_records": 0, "status": "up_to_date"}

    if verbose:
        print(f"  Period: {start_date} -> {end_date}")

    total_records = 0
    current = start_date

    # Download in 30-day chunks
    while current < end_date:
        chunk_end = min(current + timedelta(days=30), end_date)

        if verbose:
            print(f"  {current} -> {chunk_end}...", end=" ", flush=True)

        try:
            time.sleep(REQUEST_DELAY)
            records = fetch_park_data(park_key, current, chunk_end, key)

            if records:
                saved = save_park_data(park_key, records)
                total_records += saved
                if verbose:
                    print(f"{len(records)} hämtade, {saved} nya")
            else:
                if verbose:
                    print("ingen data")

        except Exception as e:
            if verbose:
                print(f"fel: {e}")

        current = chunk_end

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

    if verbose:
        print(f"  Totalt: {total_records} nya poster")

    return {
        "park": park_key,
        "start_date": start_date,
        "end_date": end_date,
        "total_records": total_records,
        "status": "ok",
    }


def download_all_parks(
    park_keys: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    backfill: bool = False,
    verbose: bool = True,
    api_key: str | None = None,
) -> list[dict]:
    """Download production data for multiple parks.

    Args:
        park_keys: List of park keys (default: all)
        start_date: Override start date
        end_date: Override end date
        backfill: Search for first available data per park
        verbose: Print progress
        api_key: Override API key

    Returns:
        List of download statistics per park
    """
    if park_keys is None:
        park_keys = list(PARKS.keys())

    results = []
    for park_key in park_keys:
        result = download_park(
            park_key=park_key,
            start_date=start_date,
            end_date=end_date,
            backfill=backfill,
            verbose=verbose,
            api_key=api_key,
        )
        results.append(result)

    return results


def print_status():
    """Print sync status for all parks."""
    print("\nBazefield Park Sync Status")
    print("=" * 60)
    print(f"{'Park':<15} {'Zon':<5} {'Senaste data':<15} {'Fil'}")
    print("-" * 60)

    for key, park in PARKS.items():
        csv_path = get_park_csv_path(key)
        latest = get_latest_synced_date(key)

        if latest:
            status = str(latest)
        elif csv_path.exists():
            status = "(tom fil)"
        else:
            status = "(ej synkad)"

        filename = csv_path.name if csv_path.exists() else "-"
        print(f"{park['name']:<15} {park['zone']:<5} {status:<15} {filename}")
