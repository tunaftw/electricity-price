# Dashboard v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an interactive drill-down electricity price dashboard with capture prices for all power types, dark Bloomberg theme, and Excel export.

**Architecture:** Python data module calculates all capture prices (solar profiles, wind/hydro/nuclear from actual ENTSO-E data) aggregated to day/month/year. HTML generator embeds JSON data in a self-contained HTML file with Plotly.js. JavaScript handles drill-down navigation, zone switching, and series filtering.

**Tech Stack:** Python 3.11+, Plotly.js 2.35 (CDN), openpyxl for Excel

**Key data alignment:** Spot prices are CET/CEST (quarterly/15-min). ENTSO-E generation is UTC (hourly). Must convert to common timezone for join. For hourly ENTSO-E data, each hour maps to 4 quarterly periods.

---

### Task 1: Data module — `elpris/dashboard_v2_data.py`

**Files:**
- Create: `elpris/dashboard_v2_data.py`

This module replaces `dashboard_data.py` with expanded capture price calculations for all power types and daily aggregation.

**Step 1: Create the data module skeleton**

```python
"""Dashboard v2 data module.

Calculates capture prices for all power types:
- Solar (PVsyst profiles: syd, öst-väst, tracker + auto-discovered parks)
- Wind (ENTSO-E actual generation)
- Hydro (ENTSO-E actual generation)
- Nuclear (ENTSO-E actual generation)

Aggregates to day/month/year for drill-down navigation.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import QUARTERLY_DIR, ENTSOE_DATA_DIR, ZONES, RESULTAT_DIR

SWEDEN_TZ = ZoneInfo("Europe/Stockholm")
ENTSOE_GEN_DIR = ENTSOE_DATA_DIR / "generation"
PROFILES_DIR = RESULTAT_DIR / "profiler" / "beraknade"
PARKS_DIR = RESULTAT_DIR / "profiler" / "parker"

# Standard PVsyst solar profiles
STANDARD_SOLAR_PROFILES = {
    "sol_syd": ("south_lundby", "Sol Syd"),
    "sol_ov": ("ew_boda", "Sol Öst-Väst"),
    "sol_tracker": ("tracker_sweden", "Sol Tracker"),
}

# ENTSO-E generation types for capture calculation
ENTSOE_CAPTURE_TYPES = {
    "wind": ("wind_onshore", "Vind"),
    "hydro": ("hydro_water_reservoir", "Vattenkraft"),
    "nuclear": ("nuclear", "Kärnkraft"),
}
```

**Step 2: Implement spot price loading**

Load quarterly prices and index by UTC hour for efficient joining with ENTSO-E data.

```python
def load_spot_prices(zone: str) -> dict[str, list[dict]]:
    """Load quarterly spot prices for a zone.
    
    Returns dict keyed by ISO date (YYYY-MM-DD) containing lists of
    {utc_hour: int, eur_mwh: float, timestamp: datetime} records.
    Groups 15-min records to hourly by averaging.
    """
    zone_dir = QUARTERLY_DIR / zone
    if not zone_dir.exists():
        return {}

    # Collect all 15-min records, group by UTC hour
    hourly_acc: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    
    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["time_start"])
                # Convert to UTC for alignment with ENTSO-E
                ts_utc = ts.astimezone(ZoneInfo("UTC"))
                date_key = ts_utc.strftime("%Y-%m-%d")
                hour = ts_utc.hour
                eur_mwh = float(row["EUR_per_kWh"]) * 1000
                hourly_acc[date_key][hour].append(eur_mwh)

    # Average to hourly
    result: dict[str, list[dict]] = {}
    for date_key in sorted(hourly_acc):
        hours = hourly_acc[date_key]
        result[date_key] = []
        for h in sorted(hours):
            vals = hours[h]
            result[date_key].append({
                "utc_hour": h,
                "eur_mwh": sum(vals) / len(vals),
            })
    return result
```

**Step 3: Implement ENTSO-E generation loading**

```python
def load_entsoe_generation(zone: str, gen_type: str) -> dict[str, dict[int, float]]:
    """Load ENTSO-E actual generation data.
    
    Returns dict keyed by ISO date (YYYY-MM-DD) → {utc_hour: generation_mw}.
    """
    zone_dir = ENTSOE_GEN_DIR / zone
    if not zone_dir.exists():
        return {}

    result: dict[str, dict[int, float]] = defaultdict(dict)
    
    for csv_file in sorted(zone_dir.glob(f"{gen_type}_*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row["time_start"].replace("Z", "+00:00")
                ts = datetime.fromisoformat(ts_str)
                date_key = ts.strftime("%Y-%m-%d")
                result[date_key][ts.hour] = float(row["generation_mw"])

    return dict(result)
```

**Step 4: Implement PVsyst profile loading**

```python
def load_pvsyst_profile(name: str) -> dict[tuple[int, int, int], float]:
    """Load PVsyst profile: (month, day, hour) → power_mw."""
    filepath = PROFILES_DIR / f"{name}.csv"
    if not filepath.exists():
        return {}
    
    profile = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row["month"]), int(row["day"]), int(row["hour"]))
            profile[key] = float(row["power_mw"])
    return profile


def discover_park_profiles() -> dict[str, tuple[str, str]]:
    """Auto-discover park profiles from Resultat/profiler/parker/.
    
    Naming convention: parkname_SE3.csv → zone SE3
    Returns {key: (filename_stem, display_name)}.
    """
    if not PARKS_DIR.exists():
        return {}
    
    parks = {}
    for f in sorted(PARKS_DIR.glob("*.csv")):
        stem = f.stem  # e.g. "boda_SE3"
        parts = stem.rsplit("_", 1)
        if len(parts) == 2 and parts[1] in ZONES:
            park_name = parts[0].replace("_", " ").title()
            zone = parts[1]
            parks[f"park_{stem}"] = (stem, f"{park_name} ({zone})")
    return parks
```

**Step 5: Implement the main capture calculation engine**

```python
def _calculate_entsoe_capture(
    spot_prices: dict[str, list[dict]],
    generation: dict[str, dict[int, float]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Calculate capture prices using actual ENTSO-E generation data.
    
    Returns nested dict: {date: {month_key: ..., year: ..., 
    sum_weighted: ..., sum_gen: ..., sum_price: ..., count: ...}}
    
    Each date entry has accumulator fields for aggregation.
    """
    daily: dict[str, dict] = {}
    
    for date_key in sorted(spot_prices):
        if date_key not in generation:
            continue
            
        hours = spot_prices[date_key]
        gen = generation[date_key]
        
        d = date.fromisoformat(date_key)
        sum_weighted = 0.0
        sum_gen = 0.0
        sum_price = 0.0
        count = 0
        
        for h_rec in hours:
            h = h_rec["utc_hour"]
            price = h_rec["eur_mwh"]
            gen_mw = gen.get(h, 0.0)
            
            sum_weighted += price * gen_mw
            sum_gen += gen_mw
            sum_price += price
            count += 1
        
        if count > 0:
            daily[date_key] = {
                "date": d,
                "year": d.year,
                "month": d.month,
                "sum_weighted": sum_weighted,
                "sum_gen": sum_gen,
                "sum_price": sum_price,
                "count": count,
            }
    
    return daily


def _calculate_profile_capture(
    spot_prices: dict[str, list[dict]],
    profile: dict[tuple[int, int, int], float],
) -> dict[str, dict]:
    """Calculate capture prices using a PVsyst profile (month/day/hour weights).
    
    Converts UTC hours back to Swedish local time for profile lookup.
    """
    daily: dict[str, dict] = {}
    
    for date_key in sorted(spot_prices):
        hours = spot_prices[date_key]
        d = date.fromisoformat(date_key)
        
        sum_weighted = 0.0
        sum_weight = 0.0
        sum_price = 0.0
        count = 0
        
        for h_rec in hours:
            price = h_rec["eur_mwh"]
            # Convert UTC hour to Swedish local time for profile lookup
            utc_dt = datetime(d.year, d.month, d.day, h_rec["utc_hour"],
                            tzinfo=ZoneInfo("UTC"))
            local_dt = utc_dt.astimezone(SWEDEN_TZ)
            
            key = (local_dt.month, local_dt.day, local_dt.hour)
            weight = profile.get(key, 0.0)
            
            sum_weighted += price * weight
            sum_weight += weight
            sum_price += price
            count += 1
        
        if count > 0:
            daily[date_key] = {
                "date": d,
                "year": d.year,
                "month": d.month,
                "sum_weighted": sum_weighted,
                "sum_gen": sum_weight,
                "sum_price": sum_price,
                "count": count,
            }
    
    return daily
```

**Step 6: Implement aggregation functions**

```python
def _aggregate_daily(daily_data: dict[str, dict]) -> list[dict]:
    """Convert daily accumulators to final daily capture prices."""
    result = []
    for date_key in sorted(daily_data):
        d = daily_data[date_key]
        baseload = d["sum_price"] / d["count"] if d["count"] > 0 else None
        capture = d["sum_weighted"] / d["sum_gen"] if d["sum_gen"] > 0 else None
        ratio = capture / baseload if capture and baseload and baseload > 0 else None
        
        result.append({
            "date": date_key,
            "year": d["year"],
            "month": d["month"],
            "baseload": round(baseload, 2) if baseload else None,
            "capture": round(capture, 2) if capture else None,
            "ratio": round(ratio, 3) if ratio else None,
        })
    return result


def _aggregate_to_monthly(daily_data: dict[str, dict]) -> list[dict]:
    """Aggregate daily accumulators to monthly."""
    monthly_acc: dict[tuple[int,int], dict] = defaultdict(
        lambda: {"sum_weighted": 0.0, "sum_gen": 0.0, "sum_price": 0.0, "count": 0}
    )
    for d in daily_data.values():
        key = (d["year"], d["month"])
        acc = monthly_acc[key]
        acc["sum_weighted"] += d["sum_weighted"]
        acc["sum_gen"] += d["sum_gen"]
        acc["sum_price"] += d["sum_price"]
        acc["count"] += d["count"]
    
    result = []
    for (year, month) in sorted(monthly_acc):
        acc = monthly_acc[(year, month)]
        baseload = acc["sum_price"] / acc["count"] if acc["count"] > 0 else None
        capture = acc["sum_weighted"] / acc["sum_gen"] if acc["sum_gen"] > 0 else None
        ratio = capture / baseload if capture and baseload and baseload > 0 else None
        result.append({
            "year": year, "month": month,
            "baseload": round(baseload, 2) if baseload else None,
            "capture": round(capture, 2) if capture else None,
            "ratio": round(ratio, 3) if ratio else None,
        })
    return result


def _aggregate_to_yearly(daily_data: dict[str, dict]) -> list[dict]:
    """Aggregate daily accumulators to yearly."""
    yearly_acc: dict[int, dict] = defaultdict(
        lambda: {"sum_weighted": 0.0, "sum_gen": 0.0, "sum_price": 0.0, "count": 0}
    )
    for d in daily_data.values():
        acc = yearly_acc[d["year"]]
        acc["sum_weighted"] += d["sum_weighted"]
        acc["sum_gen"] += d["sum_gen"]
        acc["sum_price"] += d["sum_price"]
        acc["count"] += d["count"]
    
    result = []
    for year in sorted(yearly_acc):
        acc = yearly_acc[year]
        baseload = acc["sum_price"] / acc["count"] if acc["count"] > 0 else None
        capture = acc["sum_weighted"] / acc["sum_gen"] if acc["sum_gen"] > 0 else None
        ratio = capture / baseload if capture and baseload and baseload > 0 else None
        result.append({
            "year": year,
            "baseload": round(baseload, 2) if baseload else None,
            "capture": round(capture, 2) if capture else None,
            "ratio": round(ratio, 3) if ratio else None,
        })
    return result
```

**Step 7: Implement main entry point**

```python
def calculate_dashboard_v2_data() -> dict:
    """Calculate all data for Dashboard v2.
    
    Returns JSON-serializable dict with structure:
    {
        "generated": "2026-04-04T...",
        "zones": ["SE1", ...],
        "profiles": {"baseload": "Baseload", "sol_syd": "Sol Syd", ...},
        "colors": {"baseload": "#ffffff", ...},
        "data": {
            "SE1": {
                "baseload": {"yearly": [...], "monthly": [...], "daily": [...]},
                "sol_syd": {"yearly": [...], "monthly": [...], "daily": [...]},
                ...
            }
        }
    }
    """
    # Discover all profiles
    profiles = {"baseload": "Baseload"}
    for key, (_, label) in STANDARD_SOLAR_PROFILES.items():
        profiles[key] = label
    for key, (_, label) in ENTSOE_CAPTURE_TYPES.items():
        profiles[key] = label
    park_profiles = discover_park_profiles()
    for key, (_, label) in park_profiles.items():
        profiles[key] = label

    # Load PVsyst profiles
    pvsyst_loaded = {}
    for key, (filename, _) in STANDARD_SOLAR_PROFILES.items():
        pvsyst_loaded[key] = load_pvsyst_profile(filename)
    for key, (stem, _) in park_profiles.items():
        park_file = PARKS_DIR / f"{stem}.csv"
        if park_file.exists():
            pvsyst_loaded[key] = load_pvsyst_profile_from_path(park_file)

    colors = {
        "baseload": "#ffffff",
        "sol_syd": "#ffd700",
        "sol_ov": "#ff8c00",
        "sol_tracker": "#ff6347",
        "wind": "#00d4aa",
        "hydro": "#4169e1",
        "nuclear": "#dc143c",
    }

    data = {}
    for zone in ZONES:
        print(f"Beräknar {zone}...")
        spot = load_spot_prices(zone)
        if not spot:
            continue

        zone_data = {}

        # Baseload (just prices, no weighting)
        baseload_daily = {}
        for date_key, hours in spot.items():
            d = date.fromisoformat(date_key)
            s = sum(h["eur_mwh"] for h in hours)
            c = len(hours)
            baseload_daily[date_key] = {
                "date": d, "year": d.year, "month": d.month,
                "sum_weighted": s, "sum_gen": c,  # gen=count for baseload
                "sum_price": s, "count": c,
            }
        zone_data["baseload"] = {
            "yearly": _aggregate_to_yearly(baseload_daily),
            "monthly": _aggregate_to_monthly(baseload_daily),
            "daily": _aggregate_daily(baseload_daily),
        }

        # Solar profiles (PVsyst)
        for key in pvsyst_loaded:
            # For park profiles, check zone matches
            if key.startswith("park_"):
                stem = park_profiles[key][0]
                park_zone = stem.rsplit("_", 1)[1]
                if park_zone != zone:
                    continue
            
            daily = _calculate_profile_capture(spot, pvsyst_loaded[key])
            zone_data[key] = {
                "yearly": _aggregate_to_yearly(daily),
                "monthly": _aggregate_to_monthly(daily),
                "daily": _aggregate_daily(daily),
            }

        # ENTSO-E actual generation (wind, hydro, nuclear)
        for key, (gen_type, _) in ENTSOE_CAPTURE_TYPES.items():
            gen = load_entsoe_generation(zone, gen_type)
            if not gen:
                continue
            daily = _calculate_entsoe_capture(spot, gen)
            zone_data[key] = {
                "yearly": _aggregate_to_yearly(daily),
                "monthly": _aggregate_to_monthly(daily),
                "daily": _aggregate_daily(daily),
            }

        data[zone] = zone_data

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "zones": [z for z in ZONES if z in data],
        "profiles": profiles,
        "colors": colors,
        "data": data,
    }
```

**Step 8: Test the data module**

Run: `python3 -c "from elpris.dashboard_v2_data import calculate_dashboard_v2_data; import json; d = calculate_dashboard_v2_data(); print(json.dumps({z: list(d['data'][z].keys()) for z in d['zones']}, indent=2))"`

Expected: Each zone lists baseload + available profiles.

**Step 9: Commit**

```bash
git add elpris/dashboard_v2_data.py
git commit -m "feat: add dashboard v2 data module with all capture types"
```

---

### Task 2: HTML generator — Dark theme skeleton + drill-down

**Files:**
- Create: `generate_dashboard_v2.py`

This is the main HTML generator. The HTML/CSS/JS is all generated as a Python string with embedded data JSON.

**Step 1: Create generator with dark theme CSS**

Create `generate_dashboard_v2.py` with:
- Dark theme CSS (bg: `#1a1a2e`, graph bg: `#16213e`, text: `#e0e0e0`)
- Layout: topbar (title + zone buttons), sidebar (checkboxes), main area, breadcrumb bar
- Responsive design

**Step 2: Add JavaScript — data loading and state management**

```javascript
// State
let currentZone = 'SE3';
let currentView = 'yearly';  // 'yearly' | 'monthly' | 'daily'
let currentYear = null;
let currentMonth = null;
let enabledProfiles = new Set(['baseload', 'sol_syd', 'sol_ov', 'sol_tracker', 'wind', 'hydro', 'nuclear']);

// Navigation
function drillDown(year, month) { ... }
function navigateTo(view, year, month) { ... }
function updateBreadcrumb() { ... }
```

**Step 3: Add JavaScript — yearly view (bar chart)**

Grouped bar chart with Plotly.js:
- X-axis: years
- Y-axis: EUR/MWh
- One bar group per enabled profile
- Click handler: `plotly_click` → drill down to monthly

**Step 4: Add JavaScript — monthly view (bar chart)**

Same pattern, X-axis: months (Jan-Dec), for selected year.
- Click handler → drill down to daily

**Step 5: Add JavaScript — daily view (line chart)**

Line chart: X-axis: days of month, Y-axis: EUR/MWh.
- One line per enabled profile
- Shows baseload as reference line

**Step 6: Add JavaScript — capture ratio secondary chart**

Below the main chart, a smaller line/bar chart showing capture ratios for the same period.

**Step 7: Add JavaScript — sidebar filtering and zone switching**

- Zone buttons toggle `currentZone`, re-render current view
- Checkboxes toggle profiles in `enabledProfiles` set
- Both trigger re-render without changing navigation state

**Step 8: Wire the generator to the data module**

```python
def main():
    from elpris.dashboard_v2_data import calculate_dashboard_v2_data
    data = calculate_dashboard_v2_data()
    html = build_html(data)
    # Write to Resultat/rapporter/dashboard_elpris_v2_YYYYMMDD.html
```

**Step 9: Test by generating and opening**

Run: `python3 generate_dashboard_v2.py`
Open the generated HTML file in browser. Verify:
- Dark theme renders correctly
- Zone switching works
- Drill-down year → month → day works
- Breadcrumb navigation works
- Sidebar filtering works
- Plotly charts are interactive (hover, zoom)

**Step 10: Commit**

```bash
git add generate_dashboard_v2.py
git commit -m "feat: add dashboard v2 HTML generator with dark theme and drill-down"
```

---

### Task 3: Excel export

**Files:**
- Create: `elpris/excel_export.py`

**Step 1: Implement Excel export**

Use openpyxl to generate a companion .xlsx file with:
- Sheet per zone (SE1-SE4)
- Yearly summary table: all capture prices and ratios
- Monthly detail table: all months × profiles
- Formatting: headers, number formats, conditional coloring for ratios

```python
def generate_excel(data: dict, output_path: Path) -> None:
    """Generate Excel report from dashboard v2 data."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, numbers
    # ... implementation
```

**Step 2: Integrate into generator**

Add Excel generation to `generate_dashboard_v2.py` main():
```python
from elpris.excel_export import generate_excel
generate_excel(data, output_dir / f"dashboard_elpris_v2_{today}.xlsx")
```

**Step 3: Test**

Run: `python3 generate_dashboard_v2.py`
Verify both HTML and Excel files are generated.

**Step 4: Commit**

```bash
git add elpris/excel_export.py generate_dashboard_v2.py
git commit -m "feat: add Excel export for dashboard v2"
```

---

### Task 4: Integration and polish

**Step 1: Create parks directory**

```bash
mkdir -p Resultat/profiler/parker
```

Add a README or .gitkeep so the directory is tracked.

**Step 2: Update `update_all.py` to include dashboard v2 generation**

Add dashboard v2 generation as final step in the update pipeline (check existing update_all.py first).

**Step 3: Final test — full pipeline**

Run: `python3 generate_dashboard_v2.py`
Open HTML, test all interactions thoroughly:
- [ ] All 4 zones load and display data
- [ ] Year drill-down works
- [ ] Month drill-down works  
- [ ] Breadcrumb back-navigation works
- [ ] All profile toggles work
- [ ] Capture ratios display correctly
- [ ] Hover tooltips show correct values
- [ ] Dark theme looks good
- [ ] Excel file opens correctly

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: dashboard v2 complete — dark theme, drill-down, all capture types"
```
