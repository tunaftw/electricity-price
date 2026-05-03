# Bazefield Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Sync solar park production data from Bazefield API and calculate actual capture prices per park.

**Architecture:** New module `elpris/bazefield.py` fetches 15-min ActivePowerMeter data from Bazefield REST API, stores as timestamped CSV in `Resultat/profiler/parker/`. Dashboard v2 already auto-discovers park CSVs but currently expects PVsyst format (month/day/hour). We modify the dashboard to load park data as actual timestamped data (like ENTSO-E) and route to `_calculate_entsoe_capture` instead of `_calculate_profile_capture`. This gives true capture prices based on actual production.

**Tech Stack:** Python 3, requests, tenacity, csv (all already in project)

**Key insight:** Dashboard v2 has two capture engines: `_calculate_profile_capture` (PVsyst typical-year: `month,day,hour → weight`) and `_calculate_entsoe_capture` (actual dated data: `date_str → {hour: mw}`). Park actual data must use the ENTSO-E engine, not the PVsyst engine.

---

### Task 1: Add Bazefield config to `elpris/config.py`

**Files:**
- Modify: `elpris/config.py`

**Step 1: Add PARKS_PROFILE_DIR constant**

Add after `NASDAQ_DATA_DIR` (line 88):

```python
# Park production profiles (Bazefield actual data)
PARKS_PROFILE_DIR = RESULTAT_DIR / "profiler" / "parker"
```

**Step 2: Verify**

Run: `python3 -c "from elpris.config import PARKS_PROFILE_DIR; print(PARKS_PROFILE_DIR)"`
Expected: path ending in `Resultat/profiler/parker`

**Step 3: Commit**

```bash
git add elpris/config.py
git commit -m "feat: add PARKS_PROFILE_DIR to config"
```

---

### Task 2: Create `elpris/bazefield.py` — API client

**Files:**
- Create: `elpris/bazefield.py`

**Step 1: Write the module**

```python
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
        print(f"  Period: {start_date} → {end_date}")

    total_records = 0
    current = start_date

    # Download in 30-day chunks
    while current < end_date:
        chunk_end = min(current + timedelta(days=30), end_date)

        if verbose:
            print(f"  {current} → {chunk_end}...", end=" ", flush=True)

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
```

**Step 2: Verify module imports**

Run: `python3 -c "from elpris.bazefield import PARKS, BAZEFIELD_API_KEY; print(f'Parks: {len(PARKS)}, Key: {BAZEFIELD_API_KEY[:8]}...')"`
Expected: `Parks: 8, Key: U8i782AJ...`

**Step 3: Commit**

```bash
git add elpris/bazefield.py
git commit -m "feat: add Bazefield API client for solar park production data"
```

---

### Task 3: Create `bazefield_download.py` — CLI script

**Files:**
- Create: `bazefield_download.py`

**Step 1: Write the CLI script**

```python
#!/usr/bin/env python3
"""Download solar park production data from Bazefield monitoring platform.

Requires BAZEFIELD_API_KEY environment variable or .env file.
"""

from __future__ import annotations

import argparse

from elpris.bazefield import (
    BAZEFIELD_API_KEY,
    PARKS,
    download_all_parks,
    print_status,
)


def main():
    parser = argparse.ArgumentParser(
        description="Download solar park production data from Bazefield"
    )
    parser.add_argument(
        "--parks",
        nargs="+",
        choices=list(PARKS.keys()),
        default=None,
        help="Parks to download (default: all)",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Search for first available data and download full history",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show sync status and exit",
    )
    parser.add_argument(
        "--start",
        type=lambda s: __import__("datetime").date.fromisoformat(s),
        default=None,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=lambda s: __import__("datetime").date.fromisoformat(s),
        default=None,
        help="End date (YYYY-MM-DD)",
    )

    args = parser.parse_args()

    if args.status:
        print_status()
        return 0

    if not BAZEFIELD_API_KEY:
        print("Error: BAZEFIELD_API_KEY not set.")
        print()
        print("Add to .env file:")
        print("  BAZEFIELD_API_KEY=your-api-key-here")
        return 1

    parks = args.parks or list(PARKS.keys())

    print("Bazefield Solar Park Downloader")
    print("=" * 50)
    print(f"Parker: {', '.join(parks)}")
    if args.backfill:
        print("Läge: Full historik (backfill)")
    else:
        print("Läge: Inkrementell uppdatering")
    print("=" * 50)

    results = download_all_parks(
        park_keys=parks,
        start_date=args.start,
        end_date=args.end,
        backfill=args.backfill,
        verbose=True,
    )

    print("\n" + "=" * 50)
    print("Nedladdning klar!")
    print()
    total = sum(r["total_records"] for r in results)
    print(f"Totalt nya poster: {total}")

    print_status()

    return 0


if __name__ == "__main__":
    exit(main())
```

**Step 2: Test CLI help**

Run: `python3 bazefield_download.py --help`
Expected: argparse help text listing --parks, --backfill, --status, etc.

**Step 3: Test status (should show all parks as not synced)**

Run: `python3 bazefield_download.py --status`
Expected: table showing all 8 parks with "(ej synkad)" status

**Step 4: Commit**

```bash
git add bazefield_download.py
git commit -m "feat: add Bazefield CLI download script"
```

---

### Task 4: Test actual download with one park

**Step 1: Test downloading recent data for Hörby**

Run: `python3 bazefield_download.py --parks horby --start 2025-06-01 --end 2025-06-03`
Expected: downloads ~192 records (2 days × 96 intervals/day), creates `Resultat/profiler/parker/horby_SE4.csv`

**Step 2: Verify CSV format**

Run: `head -5 Resultat/profiler/parker/horby_SE4.csv`
Expected:
```
timestamp,power_mw
2025-06-01T00:00:00.0000000+02:00,0.0
2025-06-01T00:15:00.0000000+02:00,0.0
...
```

**Step 3: Test incremental (re-run should add 0 new)**

Run: `python3 bazefield_download.py --parks horby --start 2025-06-01 --end 2025-06-03`
Expected: "0 nya" for each chunk (dedup working)

**Step 4: Clean up test file** (delete it — we'll do a proper backfill later)

Run: `rm Resultat/profiler/parker/horby_SE4.csv`

**Step 5: Commit** (no file changes — just verification)

No commit needed.

---

### Task 5: Modify dashboard v2 to load park data as actual timestamped data

**Files:**
- Modify: `elpris/dashboard_v2_data.py`

This is the critical change. Currently park profiles are loaded via `load_pvsyst_profile_from_path` which expects `month,day,hour,power_mw` (typical-year). But our Bazefield data is actual timestamped production. We need to load it like ENTSO-E data and route to `_calculate_entsoe_capture`.

**Step 1: Add `load_park_actual_data` function**

Add after `load_pvsyst_profile_from_path` (after line 151):

```python
def load_park_actual_data(
    filepath: Path,
) -> dict[str, dict[int, float]]:
    """Load actual park production data from timestamped CSV.

    Bazefield format: timestamp,power_mw
    Returns dict keyed by ISO date -> {utc_hour: avg_power_mw}.
    Aggregates 15-min data to hourly averages to match spot price resolution.
    """
    from collections import defaultdict

    # Collect all 15-min values per (date, hour)
    hourly_values: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row["timestamp"])
            # Convert to UTC for consistency with spot prices
            ts_utc = ts.astimezone(UTC_TZ)
            date_key = ts_utc.strftime("%Y-%m-%d")
            hourly_values[date_key][ts_utc.hour].append(float(row["power_mw"]))

    # Average 15-min values to hourly
    result: dict[str, dict[int, float]] = {}
    for date_key, hours in hourly_values.items():
        result[date_key] = {
            hour: sum(vals) / len(vals)
            for hour, vals in hours.items()
        }

    return result
```

**Step 2: Detect park CSV format and route appropriately**

In the main `calculate_dashboard_data` function, replace the park profile loading block (around lines 792-795):

Replace:
```python
    for key, (stem, _) in park_profiles.items():
        park_file = PARKS_DIR / f"{stem}.csv"
        if park_file.exists():
            pvsyst_loaded[key] = load_pvsyst_profile_from_path(park_file)
```

With:
```python
    park_actual_data: dict[str, dict[str, dict[int, float]]] = {}
    for key, (stem, _) in park_profiles.items():
        park_file = PARKS_DIR / f"{stem}.csv"
        if park_file.exists():
            # Check if file has timestamped data (Bazefield) or PVsyst format
            with open(park_file, "r", encoding="utf-8") as f:
                header = f.readline().strip()
            if "timestamp" in header:
                park_actual_data[key] = load_park_actual_data(park_file)
            else:
                pvsyst_loaded[key] = load_pvsyst_profile_from_path(park_file)
```

**Step 3: Route park actual data to ENTSO-E capture engine**

In the zone calculation loop (around lines 832-851), replace the solar profiles block:

Replace:
```python
        # Solar profiles (PVsyst)
        for key, profile in pvsyst_loaded.items():
            # Park profiles: only calculate for matching zone
            if key.startswith("park_"):
                stem = park_profiles[key][0]
                park_zone = stem.rsplit("_", 1)[1]
                if park_zone != zone:
                    continue

            daily = _calculate_profile_capture(spot, profile)
            if daily:
                zone_data[key] = {}
                if "yearly" in granularities:
                    zone_data[key]["yearly"] = _aggregate_to_yearly(daily)
                if "monthly" in granularities:
                    zone_data[key]["monthly"] = _aggregate_to_monthly(daily)
                if "daily" in granularities:
                    zone_data[key]["daily"] = _aggregate_daily(daily)
                if "hourly" in granularities:
                    zone_data[key]["hourly"] = _collect_hourly_profile(spot, profile)
```

With:
```python
        # Solar profiles (PVsyst)
        for key, profile in pvsyst_loaded.items():
            # Park profiles: only calculate for matching zone
            if key.startswith("park_"):
                stem = park_profiles[key][0]
                park_zone = stem.rsplit("_", 1)[1]
                if park_zone != zone:
                    continue

            daily = _calculate_profile_capture(spot, profile)
            if daily:
                zone_data[key] = {}
                if "yearly" in granularities:
                    zone_data[key]["yearly"] = _aggregate_to_yearly(daily)
                if "monthly" in granularities:
                    zone_data[key]["monthly"] = _aggregate_to_monthly(daily)
                if "daily" in granularities:
                    zone_data[key]["daily"] = _aggregate_daily(daily)
                if "hourly" in granularities:
                    zone_data[key]["hourly"] = _collect_hourly_profile(spot, profile)

        # Park actual production data (Bazefield — timestamped)
        for key in park_actual_data:
            stem = park_profiles[key][0]
            park_zone = stem.rsplit("_", 1)[1]
            if park_zone != zone:
                continue

            gen = park_actual_data[key]
            daily = _calculate_entsoe_capture(spot, gen)
            if daily:
                zone_data[key] = {}
                if "yearly" in granularities:
                    zone_data[key]["yearly"] = _aggregate_to_yearly(daily)
                if "monthly" in granularities:
                    zone_data[key]["monthly"] = _aggregate_to_monthly(daily)
                if "daily" in granularities:
                    zone_data[key]["daily"] = _aggregate_daily(daily)
                if "hourly" in granularities:
                    zone_data[key]["hourly"] = _collect_hourly_entsoe(spot, gen)
```

**Step 4: Verify no import errors**

Run: `python3 -c "from elpris.dashboard_v2_data import load_park_actual_data; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add elpris/dashboard_v2_data.py
git commit -m "feat: support actual timestamped park data in dashboard capture calc"
```

---

### Task 6: Integration with `update_all.py`

**Files:**
- Modify: `update_all.py`

**Step 1: Add Bazefield step after spot prices (step 1)**

Add a `BAZEFIELD_API_KEY` check at the top (after the ENTSOE_TOKEN check around line 39):

```python
# Check for Bazefield API key
BAZEFIELD_API_KEY = os.getenv("BAZEFIELD_API_KEY")
if not BAZEFIELD_API_KEY:
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("BAZEFIELD_API_KEY="):
                    BAZEFIELD_API_KEY = line.strip().split("=", 1)[1]
                    break
```

**Step 2: Add `--skip-bazefield` argument**

Add after the `--skip-esett` argument:

```python
    parser.add_argument(
        "--skip-bazefield",
        action="store_true",
        help="Skip Bazefield solar park sync",
    )
```

**Step 3: Update total_steps from 9 to 10**

Change: `total_steps = 9` → `total_steps = 10`

**Step 4: Add Bazefield step as step 2 (shift subsequent numbers)**

Insert after the spot price step (step 1), before ENTSO-E:

```python
    # Step 2: Sync Bazefield solar park data
    current_step += 1
    if args.skip_bazefield:
        step(current_step, total_steps, "Bazefield solar parks (SKIPPED)")
    elif not BAZEFIELD_API_KEY:
        step(current_step, total_steps, "Bazefield solar parks (SKIPPED - no API key)")
        print("  Set BAZEFIELD_API_KEY in .env to enable")
    else:
        step(current_step, total_steps, "Syncing Bazefield solar park data")
        if run_script("bazefield_download.py", quiet=args.quiet):
            success_count += 1
            print("  Done!")
        else:
            print("  Failed or no updates needed")
```

**Step 5: Update the docstring** at the top of the file to include the Bazefield step.

**Step 6: Verify**

Run: `python3 update_all.py --help`
Expected: `--skip-bazefield` appears in help output

**Step 7: Commit**

```bash
git add update_all.py
git commit -m "feat: add Bazefield sync to master update pipeline"
```

---

### Task 7: Create slash command `.claude/commands/elpris-bazefield.md`

**Files:**
- Create: `.claude/commands/elpris-bazefield.md`

**Step 1: Write the skill file**

```markdown
# Synka solparksdata från Bazefield

Ladda ner produktionsdata (ActivePowerMeter, 15-min) från Svea Solars solparker via Bazefield API.

## Om Bazefield

Bazefield är Svea Solars monitoreringsportal. API-nyckel krävs (`BAZEFIELD_API_KEY` i `.env`).

**Parker:** Hörby (SE4), Fjällskär (SE3), Agerum (SE4), Hova (SE3), Björke (SE3), Skakelbacken (SE3), Stenstorp (SE3), Tången (SE4)

## Instruktioner

1. Kör `python3 bazefield_download.py` för inkrementell synk av alla parker

### Flaggor

- `--parks horby fjallskar` - Specifika parker
- `--backfill` - Sök upp första datum med data och ladda ner all historik
- `--status` - Visa synkstatus per park
- `--start 2025-01-01 --end 2025-12-31` - Specifikt datumintervall

### Initial setup (första gången)

Kör backfill för att hämta all tillgänglig historik:
```
python3 bazefield_download.py --backfill
```

### Inkrementell uppdatering

Kör utan flaggor — scriptet fortsätter från senaste synkade datum:
```
python3 bazefield_download.py
```

## Dataformat

Kolumner i nedladdad data:
- `timestamp` - ISO 8601 lokal tid (ex: 2025-06-15T10:00:00.0000000+02:00)
- `power_mw` - Genomsnittlig effekt vid mätare (MW)

Data sparas till: `Resultat/profiler/parker/<park>_<zon>.csv`

Dashboard v2 upptäcker parkprofiler automatiskt och beräknar capture price.
```

**Step 2: Commit**

```bash
git add .claude/commands/elpris-bazefield.md
git commit -m "feat: add /elpris-bazefield slash command"
```

---

### Task 8: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add Bazefield to the project structure** (in the `elpris/` section)

Add `bazefield.py` entry:
```
│   ├── bazefield.py           # Bazefield solparksdata API
```

**Step 2: Add Bazefield to Datakatalog** section

Under `marknadsdata/`, add reference to profiler/parker.

**Step 3: Add section "7. Solparksproduktion (Bazefield)"** after the Nasdaq section in Datakällor

```markdown
### 7. Solparksproduktion (Bazefield)
- **Parker:** Hörby, Fjällskär, Agerum, Hova, Björke, Skakelbacken, Stenstorp, Tången
- **Data:** ActivePowerMeter (MW) i 15-min upplösning
- **API:** `https://sveasolar.bazefield.com/BazeField.Services/api/`
- **Nyckel:** Kräver `BAZEFIELD_API_KEY` i `.env`
```

**Step 4: Add CLI commands section**

```markdown
### Synka solparksdata (Bazefield)
\`\`\`bash
# Inkrementell synk alla parker
python3 bazefield_download.py

# Full historik
python3 bazefield_download.py --backfill

# Specifik park
python3 bazefield_download.py --parks horby fjallskar

# Visa status
python3 bazefield_download.py --status
\`\`\`
```

**Step 5: Add `/elpris-bazefield` to the Slash Commands section**

**Step 6: Add BAZEFIELD_API_KEY to the API keys table**

**Step 7: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Bazefield integration to CLAUDE.md"
```

---

### Task 9: Run backfill and verify end-to-end

**Step 1: Run backfill for active parks**

Run: `python3 bazefield_download.py --parks horby fjallskar agerum hova --backfill`
Expected: finds first data date per park, downloads full history

**Step 2: Check status**

Run: `python3 bazefield_download.py --status`
Expected: shows dates for the 4 active parks, "(ej synkad)" for the others

**Step 3: Test that dashboard v2 picks up park profiles**

Run: `python3 -c "from elpris.dashboard_v2_data import discover_park_profiles; print(discover_park_profiles())"`
Expected: dict with park keys for the downloaded parks

**Step 4: Try remaining parks**

Run: `python3 bazefield_download.py --parks bjorke skakelbacken stenstorp tangen --backfill`
Expected: some may have no data (prints "ingen data hittad"), others may have recent data

**Step 5: Commit data files**

```bash
git add Resultat/profiler/parker/*.csv
git commit -m "data: add Bazefield solar park production profiles"
```

---

### Task 10: Final integration test

**Step 1: Generate dashboard v2 to verify capture prices appear**

Run: `python3 generate_dashboard_v2.py`
Expected: park capture prices calculated alongside PVsyst profiles, output to `Resultat/rapporter/`

**Step 2: Verify park names appear in dashboard output**

Look for park names (Hörby, Fjällskär, etc.) in console output during dashboard generation.

**Step 3: Final commit if any adjustments needed**

```bash
git add -A
git commit -m "feat: complete Bazefield integration with dashboard v2"
```
