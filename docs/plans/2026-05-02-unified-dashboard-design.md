# Unified Dashboard — Design Document

**Date:** 2026-05-02
**Status:** Validated, ready for implementation
**Author:** Brainstorming session (Pontus + Claude)

## Background

The project has accumulated multiple disconnected output artefacts:

- `dashboard_elpris_*.html` (v1, ~126 KB) — basic baseload + capture per zone
- `dashboard_v2_*.html` (~16 MB) — drill-down dashboard with 4 tabs (CAPTURE, BESS, FUTURES, OPERATIONS), last generated 2026-04-05
- `performance_<park>_<zone>_YYYY-MM.html` (~70 KB each) — per-park monthly deep-dive (19 sections)
- Excel reports (`capture_prices_*.xlsx`, `battery_arbitrage_*.xlsx`)

The team needs a **single source of truth** combining all market data, asset performance, capture rates, battery economics, and futures into one explorable interface.

## Goals

- One HTML file the team uses for everything
- Automatic regeneration via single command (`update_all.py`)
- Build on existing code, no rewrite-from-scratch
- Compare two visual approaches (Track A & Track C) side-by-side

## Non-goals

- Live hosting (start with local HTML, migrate to authenticated site later)
- Server-side rendering
- Real-time updates (daily refresh is sufficient)

## Architecture

### Tab structure (4 tabs)

| Tab | Content | Source |
|---|---|---|
| **CAPTURE** | Baseload + capture prices per zone, profile (sol syd / öst-väst / tracker, vind, hydro, nuclear), year/month drill-down | Existing `dashboard_v2` CAPTURE |
| **BESS** | Battery arbitrage 1h/2h/3h/4h, sol+BESS combinations, ancillary services revenue | Existing `dashboard_v2` BESS |
| **FUTURES** | Nasdaq forward curve, EPAD spreads SE1-SE4, fwd-vs-spot | Existing `dashboard_v2` FUTURES |
| **ASSETS** *(new)* | Park fleet overview + drill-down per park. Merges old OPERATIONS tab content. | NEW |

### File layout

```
Resultat/rapporter/
├── dashboard_unified_YYYYMMDD.html       ← Track A output
├── dashboard_unified_v3_YYYYMMDD.html    ← Track C output
└── performance_<park>_<zone>_YYYY-MM.html  (existing, kept as deep-dive annex)

elpris/
├── unified_dashboard_data.py    ← NEW — shared backend, produces JSON
├── unified_dashboard_html.py    ← NEW — Track A renderer (extends v2)
└── unified_dashboard_v3_html.py ← NEW — Track C renderer (frontend-design-driven)

generate_unified_dashboard.py    ← NEW entrypoint (--track A|C|both)
```

### Data backend (`unified_dashboard_data.py`)

Re-uses existing modules:
- `dashboard_v2_data.calculate_dashboard_v2_data()` — CAPTURE/BESS/FUTURES JSON
- `operations_dashboard_data.*` — Specific Yield, negative price exposure, tracker gain
- `performance_report_data.generate_report()` — per-park monthly KPIs (called for each of 8 parks × N months)

Outputs single JSON consumed by both renderers.

## ASSETS tab design

### Landing view ("Park Fleet")

```
┌─ FLEET OVERVIEW ────────────────────────── [April 2026 ▾] [Zone: All ▾] ┐
│                                                                          │
│  [8 parks]  [78 MWp installed]  [10 776 MWh / month]  [+3.2% vs budget]  │
└──────────────────────────────────────────────────────────────────────────┘

┌─ PARK CARDS (8, clickable) ───────────────────────────────────────────┐
│  HOVA SE3 ⭐+19.7%   HÖRBY SE4 ✓+1.6%   FJÄLLSKÄR SE3 ✓+2.1%   ...   │
│  1 115 MWh           2 638 MWh           2 923 MWh                     │
│  188 kWh/kWp         146 kWh/kWp         141 kWh/kWp                   │
│  ▁▂▃▅█▅▃▂▁  (12mo)  ▁▁▂▃▅▆█▇▅▃▂▁         ▂▃▅▇█▆▄▃▂▁                    │
└────────────────────────────────────────────────────────────────────────┘

┌─ COMPARISON TABLE  (sortable, CSV-exportable) ─────────────────────────┐
│ Park | Zone | Cap MWp | MWh month | vs Budget | YTD MWh | Yield kWh/kWp │
│ ...                                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Drill-down (click on park card)

```
< Back to Park Fleet                              HOVA — SE3, Tracker
─────────────────────────────────────────────────────────────────────
[April 2026 ▾]                                       [📄 Full report]

KPI ROW (6 tiles):
  Energy MWh | vs Budget % | Yield kWh/kWp | Capture Price (zone) |
  Negative-price exposure (hours) | Tracker gain %

CHARTS (2x2 grid):
  ┌─ Energy vs Budget (12mo bars) ─┐ ┌─ Specific Yield (12mo line) ─┐
  └────────────────────────────────┘ └────────────────────────────────┘
  ┌─ Daily Generation (this month) ┐ ┌─ Capture Price (zone, 12mo) ──┐
  └────────────────────────────────┘ └────────────────────────────────┘

BEST/WORST DAYS table (top 5 + bottom 5 of selected month)

[📄 Open complete 19-section report →] (links to existing performance_*.html)
```

### Color coding (vs budget)

- 🟢 Green: ≥ +5% over budget
- 🟡 Yellow: ±5%
- 🔴 Red: ≤ -5% under budget

### Filters

- Month selector (default: latest complete month)
- Zone filter (All, SE1, SE2, SE3, SE4)
- Park filter on table view (multi-select)

## Update pipeline

### New `update_all.py` (12 steps)

```
[ 1/12] Spotpriser (elprisetjustnu.se)
[ 2/12] Bazefield park data           ← NEW (skipped if no API key)
[ 3/12] ENTSO-E generation
[ 4/12] Mimer regulation prices
[ 5/12] Nasdaq futures
[ 6/12] eSett imbalance prices
[ 7/12] Processing → quarterly
[ 8/12] Capture prices
[ 9/12] Excel reports
[10/12] Unified Dashboard (Track A + C)  ← REPLACES dashboard v1
[11/12] Park performance reports         ← CONDITIONAL (--reports flag only)
[12/12] Data status
```

### New flags

```bash
python3 update_all.py                    # standard sync + dashboard
python3 update_all.py --reports          # also regenerate all park reports
python3 update_all.py --reports --month 2026-03  # park reports for specific month
python3 update_all.py --skip-bazefield   # already exists pattern
python3 update_all.py --track A          # Track A dashboard only
python3 update_all.py --track C          # Track C dashboard only
```

### New slash commands

- `/elpris-update-all` — description updated (12 steps, mention `--reports`)
- `/elpris-dashboard` — NEW, runs `generate_unified_dashboard.py` standalone
- `/elpris-reports` — NEW, runs `generate_performance_report.py --all`

### Deprecation

- `generate_dashboard.py` (v1) — prints DEPRECATED warning, still runs
- Removed after ~2 weeks once unified is validated
- `generate_dashboard_v2.py` — kept as importable library, no longer standalone

## Track A vs Track C

### Track A — extend `dashboard_v2`

- Strategy: copy `generate_dashboard_v2.py` → `unified_dashboard_html.py`, surgical changes
- Theme: Bloomberg-dark (kept as-is)
- Code reuse: ~95%
- Estimate: 6–8 hours
- Output size: ~17 MB

### Track C — fresh design

- Strategy: brand new HTML, same JSON data as Track A
- Theme: driven by `frontend-design` skill (modern dashboard best practices, NOT Svea Solar light theme)
- Code reuse: data layer only
- Estimate: 8–12 hours
- Output size: ~17 MB

## Execution order

1. **Backend** (`unified_dashboard_data.py`) — ~2 h
2. **Track A** (`unified_dashboard_html.py`) — ~6 h
3. **Track C** (`unified_dashboard_v3_html.py`) — ~8 h, uses `frontend-design` skill
4. **Pipeline integration** (`update_all.py`, slash commands) — ~1 h
5. **Documentation** (`CLAUDE.md`) — ~30 min

**Total: ~17–18 hours.** Built sequentially, both HTMLs delivered together for comparison.

## Open questions / future work

- Add inverter-level data per park (requires SCADA integration — not in scope)
- Add weather correlation in drill-down (POA irradiance vs production)
- Financial figures (SEK revenue) — could be derived from capture × generation
- Once Track A or C is chosen, migrate to authenticated hosted version (Vercel/Netlify or internal)
