# BESS Arbitrage Dashboard — Design

## Overview

Add BESS arbitrage analysis as a new section in dashboard v2. Three use cases:
1. **Investment screening** — Is standalone BESS viable given historical spreads?
2. **Operational insight** — How have arbitrage spreads evolved over time?
3. **Co-located solar+BESS** — What's the incremental value of adding storage to solar?

Scope: Arbitrage only (no ancillary services in v1). All four zones (SE1–SE4).

## Configuration

- **Duration presets:** 1h, 2h, 4h (parameterized, user toggles in sidebar)
- **Round-trip efficiency:** 88%
- **Reference power:** 1 MW (revenue expressed per MW installed)

## Data Layer

New module: `elpris/bess_dashboard_data.py`

Inputs: Hourly spot prices per zone + solar profiles (both already loaded by dashboard v2).

### A. Standalone Arbitrage (DP-optimal)

Reuses existing `battery.py` DP algorithm. For each day, finds optimal charge/discharge schedule given spot prices. Runs for each zone x duration preset (1h, 2h, 4h).

Outputs per day: revenue (EUR/MW), number of cycles, average buy price, average sell price.

### B. Spread Analysis

Simple daily metric: max price - min price. No optimization needed. Provides context for why arbitrage revenue varies.

### C. Solar+BESS (BTM Constrained)

Reuses existing `solar_battery.py` logic. Battery can only charge from excess solar production (no grid import). Uses south-facing profile as default, sidebar toggle for others.

Outputs: effective capture price with battery vs without, daily revenue uplift.

### Aggregation

Same hierarchy as existing dashboard: daily -> monthly -> yearly, preserving sums for correct weighted averages. Output structure mirrors existing `DATA.data[zone][profile_key]` pattern.

## Dashboard UI

### Sidebar

New category "BESS" below "PRODUKTION":

```
BESS
  Arbitrage 1h
  Arbitrage 2h
  Arbitrage 4h
  Spread (min/max)
  Sol+BESS 1h
  Sol+BESS 2h
  Sol+BESS 4h
```

### Stat Cards

When BESS profiles enabled:
- Arbitrage: annual revenue (EUR/MW) + equivalent full cycles
- Spread: average daily spread (EUR/MWh)
- Sol+BESS: capture price with battery + uplift % vs solar-only

### Colors

Amber/gold tones for standalone arbitrage. Teal for sol+BESS. Distinct from existing blue/orange/green profiles.

## Chart Behavior

### Yearly View

Grouped bars: arbitrage revenue (EUR/MW/year) per zone for each enabled duration. Sol+BESS capture prices alongside existing solar captures. Ratio chart shows spread trend when enabled.

### Monthly View

Same grouped bars per month. Reveals seasonality:
- Summer: higher solar+BESS uplift (more curtailed solar to store)
- Winter: higher arbitrage revenue (larger price swings)

### Daily View

- Arbitrage/Sol+BESS: line chart of daily revenue. Hover tooltip: revenue, cycles, avg buy/sell price.
- Spread: dual-line (daily high/low) with shaded area between them.

### Axis Handling

- Existing profiles + Sol+BESS capture: left y-axis (EUR/MWh)
- Arbitrage revenue: right y-axis (EUR/MW per period)
- Spread: ratio chart axis (EUR/MWh)

## File Changes

### New

- `elpris/bess_dashboard_data.py` — BESS calculation engine

### Modified

- `generate_dashboard_v2.py` — BESS sidebar category, colors, right y-axis, spread chart, stat cards, tooltips
- `elpris/dashboard_v2_data.py` — Call bess_dashboard_data, merge into DATA structure

### Unchanged

- `battery.py`, `solar_battery.py` — reused as-is
- Existing dashboard profiles
- Data download scripts

## Performance

DP optimization: ~22,000 solves (5 years x 4 zones x 3 durations x ~365 days). Each is 24 hourly steps — completes in seconds. Solar+BESS similarly fast.
