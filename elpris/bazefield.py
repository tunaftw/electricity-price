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
    park_key: str,
    from_date: date,
    to_date: date,
    api_key: str | None = None,
) -> list[dict]:
    """Fetch ActivePowerMeter timeseries from Bazefield.

    Args:
        park_key: Key from PARKS dict (e.g. "horby")
        from_date: Start date (inclusive)
        to_date: End date (exclusive — data up to midnight before this date)
        api_key: Override API key (default: from env)

    Returns:
        List of {timestamp: str, power_mw: float} records
    """
    key = api_key or BAZEFIELD_API_KEY
    if not key:
        raise ValueError("BAZEFIELD_API_KEY not set. Add it to .env file.")

    park = PARKS[park_key]

    url = f"{BAZEFIELD_BASE_URL}/json/reply/GetDomainPointTimeSeriesAggregated"
    payload = {
        "ObjectIds": [park["id"]],
        "Points": ["ActivePowerMeter"],
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
    obj_data = data.get("objects", {}).get(park["id"], {})
    points = obj_data.get("points", {}).get("ActivePowerMeter", [])

    if not points:
        return []

    ts_list = points[0].get("timeSeries", [])

    records = []
    for point in ts_list:
        t_local = point.get("t_local")
        v = point.get("v")
        if t_local is not None and v is not None:
            records.append({
                "timestamp": t_local,
                "power_mw": round(v, 4),
            })

    return records


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
    test_data = fetch_timeseries(park_key, today - timedelta(days=30), today, key)
    has_production = any(r["power_mw"] > 0 for r in test_data)
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
        probe = fetch_timeseries(park_key, mid_date, probe_end, key)
        if any(r["power_mw"] > 0 for r in probe):
            high = mid_date
        else:
            low = mid_date + timedelta(days=7)

    # Refine: check week by week in the found range
    current = low
    while current <= high:
        time.sleep(REQUEST_DELAY)
        probe = fetch_timeseries(park_key, current, current + timedelta(days=7), key)
        if any(r["power_mw"] > 0 for r in probe):
            # Found it — refine to day level
            for day_offset in range(7):
                day = current + timedelta(days=day_offset)
                time.sleep(REQUEST_DELAY)
                probe = fetch_timeseries(park_key, day, day + timedelta(days=1), key)
                if any(r["power_mw"] > 0 for r in probe):
                    return day
        current += timedelta(days=7)

    return low


def save_park_data(park_key: str, records: list[dict]) -> int:
    """Append records to park CSV, avoiding duplicates.

    Returns number of new records written.
    """
    if not records:
        return 0

    csv_path = get_park_csv_path(park_key)
    PARKS_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    # Read existing timestamps
    existing_timestamps: set[str] = set()
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_timestamps.add(row["timestamp"])

    # Filter new records
    new_records = [r for r in records if r["timestamp"] not in existing_timestamps]
    if not new_records:
        return 0

    # If file doesn't exist, write header
    write_header = not csv_path.exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "power_mw"])
        if write_header:
            writer.writeheader()
        writer.writerows(new_records)

    return len(new_records)


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
            records = fetch_timeseries(park_key, current, chunk_end, key)

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
