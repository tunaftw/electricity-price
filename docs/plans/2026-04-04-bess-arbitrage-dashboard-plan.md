# BESS Arbitrage Dashboard — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add BESS arbitrage analysis (standalone DP-optimal, spread, solar+BESS) to dashboard v2 as a new sidebar category with three duration presets (1h, 2h, 4h).

**Architecture:** New calculation module `elpris/bess_dashboard_data.py` with hourly-resolution DP arbitrage optimizer. Integrates into existing `dashboard_v2_data.py` data pipeline. Frontend gets new BESS sidebar section, dual y-axis for revenue metrics, and spread visualization.

**Tech Stack:** Python (DP optimizer), Plotly.js (charts), existing dashboard v2 HTML/JS framework.

**Design doc:** `docs/plans/2026-04-04-bess-arbitrage-dashboard-design.md`

---

## Task 1: Create BESS calculation module — hourly DP arbitrage

**Files:**
- Create: `elpris/bess_dashboard_data.py`

**Step 1: Write the hourly DP arbitrage optimizer**

Create `elpris/bess_dashboard_data.py` with the core DP function and module constants:

```python
"""BESS arbitrage analysis for dashboard v2.

Calculates:
- Standalone arbitrage revenue (DP-optimal) for 1h, 2h, 4h batteries
- Daily price spread (max-min)
- Solar+BESS (BTM) capture price uplift

All calculations use hourly price resolution.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean
from typing import Optional

# Battery parameters
ROUND_TRIP_EFFICIENCY = 0.88
DURATION_PRESETS = [1, 2, 4]  # hours (= MWh at 1 MW)
POWER_MW = 1.0  # Reference power rating

# Profile definitions
ARBITRAGE_PROFILES = {
    f"arb_{d}h": f"Arbitrage {d}h" for d in DURATION_PRESETS
}
SPREAD_PROFILES = {
    "spread": "Spread (min/max)",
}
SOL_BESS_PROFILES = {
    f"sol_bess_{d}h": f"Sol+BESS {d}h" for d in DURATION_PRESETS
}

# Colors: amber/gold for arbitrage, teal for sol+BESS, gray for spread
BESS_COLORS = {
    "arb_1h": "#f59e0b",
    "arb_2h": "#d97706",
    "arb_4h": "#b45309",
    "spread": "#94a3b8",
    "sol_bess_1h": "#2dd4bf",
    "sol_bess_2h": "#14b8a6",
    "sol_bess_4h": "#0d9488",
}

# Profile metadata (tells frontend how to render)
BESS_PROFILE_META = {
    "arb_1h": {"type": "revenue", "unit": "EUR/MW"},
    "arb_2h": {"type": "revenue", "unit": "EUR/MW"},
    "arb_4h": {"type": "revenue", "unit": "EUR/MW"},
    "spread": {"type": "spread", "unit": "EUR/MWh"},
    "sol_bess_1h": {"type": "capture", "unit": "EUR/MWh"},
    "sol_bess_2h": {"type": "capture", "unit": "EUR/MWh"},
    "sol_bess_4h": {"type": "capture", "unit": "EUR/MWh"},
}


def optimize_hourly_arbitrage(
    prices: list[float],
    capacity_mwh: float,
    power_mw: float = POWER_MW,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> tuple[float, float, float, float]:
    """Optimal battery arbitrage on hourly prices using DP.

    Args:
        prices: Hourly prices in EUR/MWh (typically 24 values)
        capacity_mwh: Battery energy capacity in MWh
        power_mw: Battery power rating in MW (1C = capacity_mwh)
        efficiency: Round-trip efficiency (applied at discharge)

    Returns:
        (revenue_eur, cycles, avg_buy_price, avg_sell_price)
        Revenue is for 1 MW of battery power.
    """
    n = len(prices)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0

    energy_per_step = power_mw  # MWh per hour at rated power
    n_soc = int(round(capacity_mwh / energy_per_step)) + 1

    INF = float("inf")

    # Backward DP: dp[s] = max revenue from here to end at SoC index s
    dp_next = [0.0] * n_soc
    decisions: list[list[int]] = []

    for t in range(n - 1, -1, -1):
        p = prices[t]
        dp_curr = [-INF] * n_soc
        dec_t = [0] * n_soc  # 0=idle, 1=charge, -1=discharge

        for s in range(n_soc):
            # Idle
            best = dp_next[s]
            best_action = 0

            # Charge (if not full)
            if s + 1 < n_soc:
                v = -p * energy_per_step + dp_next[s + 1]
                if v > best:
                    best = v
                    best_action = 1

            # Discharge (if not empty)
            if s - 1 >= 0:
                v = p * energy_per_step * efficiency + dp_next[s - 1]
                if v > best:
                    best = v
                    best_action = -1

            dp_curr[s] = best
            dec_t[s] = best_action

        decisions.insert(0, dec_t)
        dp_next = dp_curr

    total_revenue = max(0.0, dp_next[0])

    if total_revenue <= 0:
        return 0.0, 0.0, 0.0, 0.0

    # Forward pass: reconstruct schedule
    s = 0
    buy_prices: list[float] = []
    sell_prices: list[float] = []

    for t in range(n):
        action = decisions[t][s]
        if action == 1:
            buy_prices.append(prices[t])
            s += 1
        elif action == -1:
            sell_prices.append(prices[t])
            s -= 1

    discharge_mwh = len(sell_prices) * energy_per_step
    cycles = discharge_mwh / capacity_mwh if capacity_mwh > 0 else 0.0
    avg_buy = mean(buy_prices) if buy_prices else 0.0
    avg_sell = mean(sell_prices) if sell_prices else 0.0

    return round(total_revenue, 2), round(cycles, 2), round(avg_buy, 2), round(avg_sell, 2)
```

**Step 2: Verify with a manual test**

Run:
```bash
python3 -c "
from elpris.bess_dashboard_data import optimize_hourly_arbitrage
# Simple case: 6 hours, clear buy-low sell-high
prices = [10, 10, 10, 50, 50, 50]
rev, cycles, buy, sell = optimize_hourly_arbitrage(prices, capacity_mwh=1.0)
print(f'Revenue: {rev} EUR, Cycles: {cycles}, Buy: {buy}, Sell: {sell}')
assert rev > 0, 'Should have positive revenue'
assert buy < sell, 'Buy price should be less than sell price'
print('OK')
"
```

Expected: Revenue ~34 EUR (sell 50×0.88 - buy 10 = 34), 1.0 cycle, buy ~10, sell ~50.

**Step 3: Commit**

```bash
git add elpris/bess_dashboard_data.py
git commit -m "feat(bess): add hourly DP arbitrage optimizer for dashboard"
```

---

## Task 2: Add spread and BTM solar+BESS calculations

**Files:**
- Modify: `elpris/bess_dashboard_data.py`

**Step 1: Add spread calculation**

Add to `bess_dashboard_data.py`:

```python
def calculate_daily_spread(prices: list[float]) -> tuple[float, float, float]:
    """Calculate daily price spread.

    Args:
        prices: Hourly prices in EUR/MWh

    Returns:
        (spread, min_price, max_price)
    """
    if not prices:
        return 0.0, 0.0, 0.0
    min_p = min(prices)
    max_p = max(prices)
    return round(max_p - min_p, 2), round(min_p, 2), round(max_p, 2)
```

**Step 2: Add BTM solar+BESS optimizer**

Add to `bess_dashboard_data.py`:

```python
def optimize_btm_hourly(
    prices: list[float],
    solar_mw: list[float],
    capacity_mwh: float,
    power_mw: float = POWER_MW,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> tuple[float, float]:
    """BTM solar+battery optimization on hourly data.

    Battery can only charge from solar production (no grid import).
    Battery can discharge to grid at any time.

    Args:
        prices: Hourly prices in EUR/MWh
        solar_mw: Hourly solar output in MW
        capacity_mwh: Battery capacity in MWh
        power_mw: Battery power in MW
        efficiency: Round-trip efficiency

    Returns:
        (revenue_direct_eur, revenue_with_battery_eur)
    """
    n = len(prices)
    if n == 0 or len(solar_mw) != n:
        return 0.0, 0.0

    energy_per_step = power_mw
    n_soc = int(round(capacity_mwh / energy_per_step)) + 1

    # Direct revenue (sell all solar immediately)
    revenue_direct = sum(solar_mw[t] * prices[t] for t in range(n))

    if capacity_mwh <= 0:
        return round(revenue_direct, 2), round(revenue_direct, 2)

    INF = float("inf")
    dp_next = [0.0] * n_soc
    decisions: list[list[tuple[int, int]]] = []

    for t in range(n - 1, -1, -1):
        p = prices[t]
        solar = solar_mw[t]
        dp_curr = [-INF] * n_soc
        dec_t: list[tuple[int, int]] = [(0, 0)] * n_soc

        for s in range(n_soc):
            # Sell all solar, idle battery
            best = solar * p + dp_next[s]
            best_dec = (0, 0)

            # Charge from solar
            max_charge = min(
                int(solar / energy_per_step) if energy_per_step > 0 else 0,
                n_soc - 1 - s,
            )
            for cs in range(1, max_charge + 1):
                charged_mwh = cs * energy_per_step
                sold_solar = solar - charged_mwh
                v = sold_solar * p + dp_next[s + cs]
                if v > best:
                    best = v
                    best_dec = (cs, 0)

            # Discharge battery
            for ds in range(1, s + 1):
                discharged_mwh = ds * energy_per_step * efficiency
                v = (solar + discharged_mwh) * p + dp_next[s - ds]
                if v > best:
                    best = v
                    best_dec = (0, ds)

            dp_curr[s] = best
            dec_t[s] = best_dec

        decisions.insert(0, dec_t)
        dp_next = dp_curr

    revenue_with_battery = max(revenue_direct, dp_next[0])

    return round(revenue_direct, 2), round(revenue_with_battery, 2)
```

**Step 3: Verify BTM with a manual test**

Run:
```bash
python3 -c "
from elpris.bess_dashboard_data import optimize_btm_hourly, calculate_daily_spread

# Spread test
spread, lo, hi = calculate_daily_spread([10, 20, 30, 40, 50])
assert spread == 40.0
print(f'Spread: {spread}, Lo: {lo}, Hi: {hi}')

# BTM test: solar produces in cheap hours, battery stores for expensive hours
prices = [10, 10, 10, 50, 50, 50]
solar =  [2,  2,  2,  0,  0,  0]  # 6 MWh total solar in cheap hours
rev_d, rev_b = optimize_btm_hourly(prices, solar, capacity_mwh=1.0)
print(f'Direct: {rev_d}, With battery: {rev_b}, Gain: {rev_b - rev_d}')
assert rev_b > rev_d, 'Battery should add value'
print('OK')
"
```

**Step 4: Commit**

```bash
git add elpris/bess_dashboard_data.py
git commit -m "feat(bess): add spread calculation and BTM solar+battery optimizer"
```

---

## Task 3: Add dashboard data integration function

**Files:**
- Modify: `elpris/bess_dashboard_data.py`

**Step 1: Add the main entry point that calculates BESS data for all zones**

Add to `bess_dashboard_data.py`:

```python
def calculate_bess_data(
    spot_prices_by_zone: dict[str, dict[str, list[dict]]],
    pvsyst_profiles: dict[str, dict[tuple[int, int, int], float]],
    zones: list[str],
) -> dict:
    """Calculate all BESS data for the dashboard.

    Args:
        spot_prices_by_zone: {zone: {date_key: [{utc_hour, eur_mwh}]}}
            Same format as loaded by dashboard_v2_data.load_spot_prices
        pvsyst_profiles: {profile_key: {(month,day,hour): power_mw}}
            Loaded PVsyst profiles (using local time keys)
        zones: List of zones to calculate

    Returns:
        Dict with:
        - profiles: {key: label}
        - colors: {key: hex}
        - profile_meta: {key: {type, unit}}
        - data: {zone: {profile_key: {yearly, monthly, daily}}}
    """
    from zoneinfo import ZoneInfo
    from datetime import datetime

    SWEDEN_TZ = ZoneInfo("Europe/Stockholm")
    UTC_TZ = ZoneInfo("UTC")

    all_profiles = {}
    all_profiles.update(ARBITRAGE_PROFILES)
    all_profiles.update(SPREAD_PROFILES)
    all_profiles.update(SOL_BESS_PROFILES)

    data: dict[str, dict] = {}

    for zone in zones:
        spot = spot_prices_by_zone.get(zone, {})
        if not spot:
            continue

        print(f"  BESS {zone}...")
        zone_data: dict[str, dict] = {}

        # Group hourly prices by date
        daily_prices: dict[str, list[float]] = {}
        for date_key in sorted(spot):
            hours = spot[date_key]
            # Build price array indexed by UTC hour
            price_by_hour: dict[int, float] = {}
            for h in hours:
                price_by_hour[h["utc_hour"]] = h["eur_mwh"]
            # Create ordered list (hours 0-23)
            prices_ordered = [price_by_hour.get(h, 0.0) for h in range(24)]
            daily_prices[date_key] = prices_ordered

        # === Standalone Arbitrage ===
        for duration in DURATION_PRESETS:
            key = f"arb_{duration}h"
            daily_data: dict[str, dict] = {}

            for date_key, prices in daily_prices.items():
                d = date.fromisoformat(date_key)
                rev, cycles, avg_buy, avg_sell = optimize_hourly_arbitrage(
                    prices, capacity_mwh=float(duration)
                )
                daily_data[date_key] = {
                    "date": d,
                    "year": d.year,
                    "month": d.month,
                    "revenue": rev,
                    "cycles": cycles,
                    "avg_buy": avg_buy,
                    "avg_sell": avg_sell,
                }

            zone_data[key] = _aggregate_bess(daily_data, "revenue")

        # === Spread ===
        spread_daily: dict[str, dict] = {}
        for date_key, prices in daily_prices.items():
            d = date.fromisoformat(date_key)
            spread, min_p, max_p = calculate_daily_spread(prices)
            spread_daily[date_key] = {
                "date": d,
                "year": d.year,
                "month": d.month,
                "spread": spread,
                "min_price": min_p,
                "max_price": max_p,
            }
        zone_data["spread"] = _aggregate_bess(spread_daily, "spread")

        # === Solar+BESS ===
        # Use sol_syd (south_lundby) profile as default
        sol_profile = pvsyst_profiles.get("sol_syd", {})
        if sol_profile:
            for duration in DURATION_PRESETS:
                key = f"sol_bess_{duration}h"
                btm_daily: dict[str, dict] = {}

                for date_key, prices in daily_prices.items():
                    d = date.fromisoformat(date_key)

                    # Convert UTC prices to local solar production
                    solar_mw = []
                    for utc_hour in range(24):
                        utc_dt = datetime(d.year, d.month, d.day, utc_hour, tzinfo=UTC_TZ)
                        local_dt = utc_dt.astimezone(SWEDEN_TZ)
                        profile_key = (local_dt.month, local_dt.day, local_dt.hour)
                        solar_mw.append(sol_profile.get(profile_key, 0.0))

                    rev_direct, rev_batt = optimize_btm_hourly(
                        prices, solar_mw, capacity_mwh=float(duration)
                    )

                    # Calculate effective capture prices
                    total_solar = sum(solar_mw)
                    sum_price = sum(prices)

                    btm_daily[date_key] = {
                        "date": d,
                        "year": d.year,
                        "month": d.month,
                        "sum_weighted_direct": rev_direct,
                        "sum_weighted_battery": rev_batt,
                        "sum_gen": total_solar,
                        "sum_price": sum_price,
                        "count": len(prices),
                    }

                zone_data[key] = _aggregate_sol_bess(btm_daily)

        data[zone] = zone_data

    return {
        "profiles": all_profiles,
        "colors": dict(BESS_COLORS),
        "profile_meta": dict(BESS_PROFILE_META),
        "data": data,
    }
```

**Step 2: Add aggregation helpers**

Add before `calculate_bess_data`:

```python
def _aggregate_bess(daily_data: dict[str, dict], value_field: str) -> dict:
    """Aggregate BESS daily data to yearly/monthly/daily.

    For revenue-type: sums values.
    For spread-type: averages values.
    """
    is_revenue = value_field == "revenue"

    # Daily output
    daily_list = []
    for date_key in sorted(daily_data):
        d = daily_data[date_key]
        entry = {
            "date": date_key,
            "year": d["year"],
            "month": d["month"],
            "capture": d[value_field],  # reuse "capture" field for frontend compat
        }
        # Extra fields for hover tooltips
        if "cycles" in d:
            entry["cycles"] = d["cycles"]
            entry["avg_buy"] = d["avg_buy"]
            entry["avg_sell"] = d["avg_sell"]
        if "min_price" in d:
            entry["min_price"] = d["min_price"]
            entry["max_price"] = d["max_price"]
        daily_list.append(entry)

    # Monthly
    monthly_acc: dict[tuple[int, int], list] = defaultdict(list)
    for d in daily_data.values():
        monthly_acc[(d["year"], d["month"])].append(d)

    monthly_list = []
    for (year, month) in sorted(monthly_acc):
        days = monthly_acc[(year, month)]
        values = [d[value_field] for d in days]
        if is_revenue:
            val = round(sum(values), 2)
        else:
            val = round(mean(values), 2) if values else 0
        entry = {"year": year, "month": month, "capture": val}
        if "cycles" in days[0]:
            entry["cycles"] = round(sum(d["cycles"] for d in days), 1)
        monthly_list.append(entry)

    # Yearly
    yearly_acc: dict[int, list] = defaultdict(list)
    for d in daily_data.values():
        yearly_acc[d["year"]].append(d)

    yearly_list = []
    for year in sorted(yearly_acc):
        days = yearly_acc[year]
        values = [d[value_field] for d in days]
        if is_revenue:
            val = round(sum(values), 2)
        else:
            val = round(mean(values), 2) if values else 0
        entry = {"year": year, "capture": val}
        if "cycles" in days[0]:
            entry["cycles"] = round(sum(d["cycles"] for d in days), 1)
        yearly_list.append(entry)

    return {"yearly": yearly_list, "monthly": monthly_list, "daily": daily_list}


def _aggregate_sol_bess(daily_data: dict[str, dict]) -> dict:
    """Aggregate sol+BESS data to capture price format (matching existing profiles)."""

    def _finalize(sw, sg, sp, c):
        baseload = sp / c if c > 0 else None
        capture = sw / sg if sg > 0 else None
        ratio = capture / baseload if capture and baseload and baseload > 0 else None
        r = lambda v, d=2: round(v, d) if v is not None else None
        return r(baseload), r(capture), r(ratio, 3)

    # Daily
    daily_list = []
    for date_key in sorted(daily_data):
        d = daily_data[date_key]
        baseload, capture, ratio = _finalize(
            d["sum_weighted_battery"], d["sum_gen"], d["sum_price"], d["count"]
        )
        daily_list.append({
            "date": date_key,
            "year": d["year"],
            "month": d["month"],
            "baseload": baseload,
            "capture": capture,
            "ratio": ratio,
        })

    # Monthly
    monthly_acc: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"sw": 0.0, "sg": 0.0, "sp": 0.0, "c": 0}
    )
    for d in daily_data.values():
        key = (d["year"], d["month"])
        acc = monthly_acc[key]
        acc["sw"] += d["sum_weighted_battery"]
        acc["sg"] += d["sum_gen"]
        acc["sp"] += d["sum_price"]
        acc["c"] += d["count"]

    monthly_list = []
    for (year, month) in sorted(monthly_acc):
        acc = monthly_acc[(year, month)]
        baseload, capture, ratio = _finalize(acc["sw"], acc["sg"], acc["sp"], acc["c"])
        monthly_list.append({"year": year, "month": month, "baseload": baseload, "capture": capture, "ratio": ratio})

    # Yearly
    yearly_acc: dict[int, dict] = defaultdict(
        lambda: {"sw": 0.0, "sg": 0.0, "sp": 0.0, "c": 0}
    )
    for d in daily_data.values():
        acc = yearly_acc[d["year"]]
        acc["sw"] += d["sum_weighted_battery"]
        acc["sg"] += d["sum_gen"]
        acc["sp"] += d["sum_price"]
        acc["c"] += d["count"]

    yearly_list = []
    for year in sorted(yearly_acc):
        acc = yearly_acc[year]
        baseload, capture, ratio = _finalize(acc["sw"], acc["sg"], acc["sp"], acc["c"])
        yearly_list.append({"year": year, "baseload": baseload, "capture": capture, "ratio": ratio})

    return {"yearly": yearly_list, "monthly": monthly_list, "daily": daily_list}
```

**Step 3: Verify with real data (SE3, single year)**

Run:
```bash
python3 -c "
from elpris.dashboard_v2_data import load_spot_prices, load_pvsyst_profile
from elpris.bess_dashboard_data import calculate_bess_data

spot = {'SE3': load_spot_prices('SE3')}
profiles = {'sol_syd': load_pvsyst_profile('south_lundby')}
result = calculate_bess_data(spot, profiles, ['SE3'])

for key in result['data']['SE3']:
    yearly = result['data']['SE3'][key]['yearly']
    if yearly:
        last = yearly[-1]
        print(f'{key:15} {last.get(\"year\")}: capture={last.get(\"capture\", \"n/a\"):>10}, cycles={last.get(\"cycles\", \"\")}')
print('OK')
"
```

Expected: Should print arbitrage revenue, spread, and sol+BESS capture values for each profile.

**Step 4: Commit**

```bash
git add elpris/bess_dashboard_data.py
git commit -m "feat(bess): add dashboard integration with aggregation and sol+BESS"
```

---

## Task 4: Integrate BESS into dashboard_v2_data.py

**Files:**
- Modify: `elpris/dashboard_v2_data.py` (lines ~356-454, `calculate_dashboard_v2_data`)

**Step 1: Import and call BESS calculations**

At the top of `dashboard_v2_data.py`, add import:

```python
from .bess_dashboard_data import calculate_bess_data, BESS_PROFILE_META
```

In `calculate_dashboard_v2_data()`, after the existing zone loop ends (after line ~446 `data[zone] = zone_data`), add:

```python
    # BESS arbitrage calculations
    print("Beräknar BESS arbitrage...")
    spot_by_zone = {}
    for zone in ZONES:
        s = load_spot_prices(zone)
        if s:
            spot_by_zone[zone] = s

    bess_result = calculate_bess_data(spot_by_zone, pvsyst_loaded, list(spot_by_zone.keys()))

    # Merge BESS data into main data
    profiles.update(bess_result["profiles"])
    colors.update(bess_result["colors"])
    for zone in bess_result["data"]:
        if zone in data:
            data[zone].update(bess_result["data"][zone])
        else:
            data[zone] = bess_result["data"][zone]
```

And in the return dict (line ~448), add `profile_meta`:

```python
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "zones": [z for z in ZONES if z in data],
        "profiles": profiles,
        "colors": colors,
        "profile_meta": dict(BESS_PROFILE_META),
        "data": data,
    }
```

**Step 2: Verify integration**

Run:
```bash
python3 -c "
from elpris.dashboard_v2_data import calculate_dashboard_v2_data
data = calculate_dashboard_v2_data()
print('Profiles:', list(data['profiles'].keys()))
print('Has profile_meta:', 'profile_meta' in data)
print('SE3 keys:', list(data['data'].get('SE3', {}).keys()))
assert 'arb_1h' in data['profiles']
assert 'spread' in data['data'].get('SE3', {})
print('OK')
"
```

**Step 3: Commit**

```bash
git add elpris/dashboard_v2_data.py
git commit -m "feat(bess): integrate BESS calculations into dashboard v2 data pipeline"
```

---

## Task 5: Frontend — Add BESS sidebar category

**Files:**
- Modify: `generate_dashboard_v2.py`

**Step 1: Update buildSidebar() to include BESS section**

In the JavaScript `buildSidebar()` function (~line 423), update the `sections` array:

Replace:
```javascript
    const sections = [
        ['PRISER', ['baseload']],
        ['SOL', Object.keys(DATA.profiles).filter(k => k.startsWith('sol_') && !k.startsWith('sol_bess'))],
        ['PRODUKTION', ['wind', 'hydro', 'nuclear']],
        ['PARKER', Object.keys(DATA.profiles).filter(k => k.startsWith('park_'))],
        ['BESS', Object.keys(DATA.profiles).filter(k => k.startsWith('arb_') || k === 'spread' || k.startsWith('sol_bess_'))],
    ];
```

Also update the initial `state.enabled` to NOT include BESS profiles by default (they're computationally heavy visually):

In the state initialization (~line 347), change to:

```javascript
let state = {
    zone: DATA.zones.includes('SE3') ? 'SE3' : DATA.zones[0],
    view: 'yearly',
    year: null,
    month: null,
    enabled: new Set(Object.keys(DATA.profiles).filter(k =>
        !k.startsWith('arb_') && k !== 'spread' && !k.startsWith('sol_bess_')
    )),
};
```

**Step 2: Verify sidebar renders**

Run `python3 generate_dashboard_v2.py` and open the HTML file. Check that BESS section appears in sidebar with all 7 entries unchecked by default.

**Step 3: Commit**

```bash
git add generate_dashboard_v2.py
git commit -m "feat(bess): add BESS sidebar section to dashboard v2"
```

---

## Task 6: Frontend — Dual y-axis for revenue profiles

**Files:**
- Modify: `generate_dashboard_v2.py`

**Step 1: Add helper to detect profile type**

Add to JavaScript section after the `fmt()` function (~line 388):

```javascript
function isRevenueProfile(k) {
    return (DATA.profile_meta || {})[k]?.type === 'revenue';
}
function isSpreadProfile(k) {
    return (DATA.profile_meta || {})[k]?.type === 'spread';
}
function isCaptureProfile(k) {
    return !isRevenueProfile(k) && !isSpreadProfile(k);
}
```

**Step 2: Update renderYearly() for dual y-axis**

In `renderYearly()` (~line 506), modify the trace-building and layout to use yaxis2 for revenue profiles:

Replace the `profileKeys.forEach` loop and layout with:

```javascript
    const hasRevenue = profileKeys.some(isRevenueProfile);

    profileKeys.forEach(k => {
        if (isSpreadProfile(k)) return; // spread goes on ratio chart
        const yearlyData = zoneData[k]?.yearly || [];
        const isRev = isRevenueProfile(k);
        const vals = years.map(y => {
            const r = yearlyData.find(d => d.year === y);
            return r ? (k === 'baseload' ? r.baseload : r.capture) : null;
        });

        traces.push({
            x: years.map(String),
            y: vals,
            name: DATA.profiles[k],
            type: 'bar',
            marker: { color: DATA.colors[k] || '#888', opacity: k === 'baseload' ? 0.5 : 0.85 },
            yaxis: isRev ? 'y2' : 'y',
            hovertemplate: isRev
                ? DATA.profiles[k] + '<br>%{x}: %{y:,.0f} EUR/MW<extra></extra>'
                : DATA.profiles[k] + '<br>%{x}: %{y:.1f} EUR/MWh<extra></extra>',
        });
    });

    const layout = {
        ...PLOTLY_DARK,
        barmode: 'group',
        xaxis: { ...PLOTLY_DARK.xaxis, type: 'category' },
        yaxis: { ...PLOTLY_DARK.yaxis, title: 'EUR/MWh', rangemode: 'tozero' },
    };

    if (hasRevenue) {
        layout.yaxis2 = {
            ...PLOTLY_DARK.yaxis,
            title: 'EUR/MW',
            overlaying: 'y',
            side: 'right',
            rangemode: 'tozero',
            showgrid: false,
        };
        layout.margin = { ...PLOTLY_DARK.margin, r: 60 };
    }
```

**Step 3: Apply same dual-axis pattern to renderMonthly()**

Same pattern: check `isRevenueProfile`, skip spread, assign `yaxis: 'y2'` for revenue traces, add `yaxis2` to layout when needed.

**Step 4: Apply same pattern to renderDaily()**

For daily view, revenue profiles use line charts with `yaxis: 'y2'`.

**Step 5: Commit**

```bash
git add generate_dashboard_v2.py
git commit -m "feat(bess): add dual y-axis for arbitrage revenue profiles"
```

---

## Task 7: Frontend — Spread visualization and BESS stat cards

**Files:**
- Modify: `generate_dashboard_v2.py`

**Step 1: Add spread to ratio chart**

In `renderRatioChart()` and `renderDailyRatioChart()`, add spread traces alongside ratio traces. When spread profile is enabled, render it as a bar or line on the ratio chart with its own y-axis label.

In `renderRatioChart()` for yearly/monthly views, add after the existing nonBaseload loop:

```javascript
    // Add spread if enabled
    if (state.enabled.has('spread') && zoneData.spread) {
        const spreadData = period === 'yearly' ? zoneData.spread.yearly : zoneData.spread.monthly;
        const vals = xValues.map(x => {
            const r = period === 'yearly'
                ? spreadData?.find(d => d.year === x)
                : spreadData?.find(d => d.year === state.year && d.month === x);
            return r ? r.capture : null;
        });
        traces.push({
            x: period === 'yearly' ? xValues.map(String) : xValues.map(m => MONTH_NAMES[m - 1]),
            y: vals,
            name: 'Spread',
            type: 'bar',
            marker: { color: DATA.colors.spread || '#94a3b8', opacity: 0.4 },
            yaxis: 'y2',
            hovertemplate: 'Spread<br>%{x}: %{y:.1f} EUR/MWh<extra></extra>',
        });
    }
```

Update ratio chart layout to support spread on y2:

```javascript
    if (state.enabled.has('spread') && zoneData.spread) {
        layout.yaxis2 = {
            ...PLOTLY_DARK.yaxis,
            title: 'Spread EUR/MWh',
            overlaying: 'y',
            side: 'right',
            rangemode: 'tozero',
            showgrid: false,
        };
        layout.margin = { ...PLOTLY_DARK.margin, r: 60, t: 20 };
    }
```

**Step 2: Add daily spread as shaded area**

In `renderDailyRatioChart()`, when spread is enabled, add high/low lines with fill between:

```javascript
    if (state.enabled.has('spread') && zoneData.spread) {
        const spreadDays = (zoneData.spread.daily || []).filter(
            d => d.year === state.year && d.month === state.month
        );
        if (spreadDays.length > 0) {
            const dates = spreadDays.map(d => d.date);
            traces.push({
                x: dates, y: spreadDays.map(d => d.max_price),
                name: 'Max pris', type: 'scatter', mode: 'lines',
                line: { color: '#94a3b8', width: 1 },
                yaxis: 'y2',
                hovertemplate: 'Max: %{y:.1f} EUR/MWh<extra></extra>',
            });
            traces.push({
                x: dates, y: spreadDays.map(d => d.min_price),
                name: 'Min pris', type: 'scatter', mode: 'lines',
                line: { color: '#94a3b8', width: 1 },
                fill: 'tonexty',
                fillcolor: 'rgba(148, 163, 184, 0.15)',
                yaxis: 'y2',
                hovertemplate: 'Min: %{y:.1f} EUR/MWh<extra></extra>',
            });
        }
    }
```

**Step 3: Update stat cards for BESS profiles**

In `updateStats()` (~line 558), add BESS-specific stat cards. After the existing profile loop, add:

```javascript
    // BESS stat cards
    Object.keys(DATA.profiles).forEach(k => {
        if (!state.enabled.has(k) || !zoneData[k]) return;

        if (isRevenueProfile(k)) {
            const d = zoneData[k].yearly?.find(r => r.year === latestYear);
            if (d) {
                const cycleStr = d.cycles ? ' (' + d.cycles + ' cykler)' : '';
                html += statCard(DATA.profiles[k] + ' ' + latestYear,
                    d.capture ? d.capture.toLocaleString('sv-SE', {maximumFractionDigits: 0}) : '–',
                    'EUR/MW' + cycleStr);
            }
        } else if (isSpreadProfile(k)) {
            const d = zoneData[k].yearly?.find(r => r.year === latestYear);
            if (d) {
                html += statCard('Spread ' + latestYear, fmt(d.capture), 'EUR/MWh');
            }
        }
    });
```

**Step 4: Commit**

```bash
git add generate_dashboard_v2.py
git commit -m "feat(bess): add spread visualization and BESS stat cards"
```

---

## Task 8: End-to-end verification

**Step 1: Generate full dashboard**

Run:
```bash
python3 generate_dashboard_v2.py
```

Expected output: Should print BESS calculation progress for each zone, then generate HTML and Excel files.

**Step 2: Open dashboard and verify**

Open the generated HTML file and verify:
- [ ] BESS section appears in sidebar with 7 entries (all unchecked by default)
- [ ] Checking "Arbitrage 1h" shows amber bars on right y-axis
- [ ] Checking "Spread" shows bars on ratio chart
- [ ] Checking "Sol+BESS 1h" shows teal bars alongside other capture prices
- [ ] Drill-down works for BESS profiles (yearly → monthly → daily)
- [ ] Stat cards update when BESS profiles are enabled
- [ ] Daily view shows spread as shaded area between min/max
- [ ] Hover tooltips show correct units (EUR/MW for arbitrage, EUR/MWh for others)

**Step 3: Commit all**

```bash
git add -A
git commit -m "feat(bess): complete BESS arbitrage dashboard integration"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Hourly DP arbitrage optimizer | Create `elpris/bess_dashboard_data.py` |
| 2 | Spread + BTM solar+BESS | Modify `elpris/bess_dashboard_data.py` |
| 3 | Dashboard data integration function | Modify `elpris/bess_dashboard_data.py` |
| 4 | Hook into dashboard_v2_data.py | Modify `elpris/dashboard_v2_data.py` |
| 5 | BESS sidebar category | Modify `generate_dashboard_v2.py` |
| 6 | Dual y-axis for revenue profiles | Modify `generate_dashboard_v2.py` |
| 7 | Spread visualization + stat cards | Modify `generate_dashboard_v2.py` |
| 8 | End-to-end verification | Run + visual check |
