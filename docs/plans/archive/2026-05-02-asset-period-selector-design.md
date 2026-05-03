# Asset Performance — Period Selector Redesign

**Date:** 2026-05-02
**Scope:** Track C unified dashboard (`elpris/unified_dashboard_v3_html.py`), `ASSETS` tab.
**Status:** Design approved, ready for implementation.

## Problem

Today the ASSETS tab supports only single-month views. The month selector
sits as a small `<select>` in the top-right of the page header, and the
chosen period appears only in a faint eyebrow line (`Fleet · 2026-04`).

Two issues:

1. **Missing period types.** Users want Year-to-Date and full-year
   ("2024", "2023", …) aggregations in addition to single months.
2. **Easy to miss.** The current control reads as decoration; users
   don't immediately know which period the KPIs and table reflect.

## Goals

- Add YTD and full-year period types alongside single-month.
- Make the active period self-evident — visible in the page title and
  in a sticky control bar.
- Keep the change small: no rebuild of drill-down, no URL state, no
  comparison views, no quarterly granularity.

## Non-goals

- YTD/Year inside the drill-down view (drill-down stays monthly).
- Cross-period comparison ("YTD 2026 vs YTD 2025 side-by-side").
- Persisting period state across sessions.
- Quarter granularity.

## Design

### 1. UI: title, period bar, controls

Page header becomes self-documenting:

```
Fleet                                  ← eyebrow (now plain, no month)
Asset Performance · YTD 2026 (Jan–Apr) ← title with period suffix
Per-park energy, yield and budget...
```

Period suffix formatter:

| Granularity | Suffix                      |
|-------------|-----------------------------|
| `month`     | `· April 2026`              |
| `ytd`       | `· YTD 2026 (Jan–Apr)`      |
| `year`      | `· Full year 2024`          |

Directly below the title sits a **sticky period bar** (full width):

```
┌──────────────────────────────────────────────────────────────┐
│ [ Month ] [ YTD ] [ Year ]   ◀ 2026 ▶   April ▾   Zone ▾    │
└──────────────────────────────────────────────────────────────┘
```

- Left: segmented control for granularity (reuses `.seg` style from
  CAPTURE tab).
- Mid: year stepper (◀ year ▶); arrows disabled at edges.
- Mid-right: month dropdown — **shown only when `granularity === 'month'`**.
- Right: zone dropdown (moved here from the old top-right slot).

CSS: `position: sticky; top: 0; z-index: 10; background: var(--bg-1);
border-bottom: 1px solid var(--line);`.

The old `<select id="assets-month-sel">` and the eyebrow's
`<span id="assets-month-label">` are removed.

### 2. State and period model

Extend `ASSETS_STATE`:

```js
var ASSETS_STATE = {
    mode: 'fleet',
    selectedPark: null,
    zone: 'ALL',
    tableParks: null,

    // NEW
    period: {
        granularity: 'month',  // 'month' | 'ytd' | 'year'
        year: null,            // initialised to latest year with data
        month: null            // 1–12, used only when granularity === 'month'
    },

    drillMonth: null
};
```

**Init** (first render after `ASSETS` is loaded):

1. `latestYM()` → `{ year, month }` from `ASSETS.parks[*].months`.
2. `period.granularity = 'month'`, `period.year = latestYM.year`,
   `period.month = latestYM.month`. Equivalent to today's "Latest".
3. `currentMonthOfYear()` = month number from `latestYM` — used for
   YTD symmetry across years.

**`periodKeys(period)`** returns the list of `"YYYY-MM"` keys the
period covers:

```js
function periodKeys(p) {
    if (p.granularity === 'month') return [p.year + '-' + pad(p.month)];
    if (p.granularity === 'year')  return monthsInYear(p.year);
    if (p.granularity === 'ytd') {
        var endMonth = currentMonthOfYear();
        return monthsInYear(p.year).filter(function(k) {
            return parseInt(k.split('-')[1], 10) <= endMonth;
        });
    }
}
```

YTD semantics: **symmetric**. `YTD 2025` when today is 2026-05 means
Jan–Apr 2025 — directly comparable to `YTD 2026 (Jan–Apr)`. For closed
historical years YTD becomes shorter than Year, by design.

### 3. Aggregation (KPI, grid, table)

`aggregatePark(park, keys)` replaces today's `parkMonth(park, key)`.
It returns a record with the same shape as a single month so existing
renderers stay almost untouched.

```js
function aggregatePark(park, keys) {
    var rows = (park.months || []).filter(function(m) {
        return keys.indexOf(m.year + '-' + pad(m.month)) !== -1;
    });
    if (!rows.length) return null;

    var energy = sum(rows, 'energy_mwh');
    var budget = sum(rows, 'budget_mwh');

    return {
        period_keys: keys,
        months_present: rows.length,
        months_expected: keys.length,
        energy_mwh: energy,
        budget_mwh: budget,
        vs_budget_pct: budget > 0 ? 100*(energy-budget)/budget : null,
        neg_price_hours: sum(rows, 'neg_price_hours'),
        pr_pct: weightedAvg(rows, 'pr_pct', 'energy_mwh'),
        irradiation_kwh_m2: sum(rows, 'irradiation_kwh_m2'),
        specific_yield: energy / (park.capacity_mwp || 1)
    };
}
```

**Aggregation rules:**

| Field type        | Rule                                       |
|-------------------|--------------------------------------------|
| Volumes           | Sum (energy, budget, neg-price hours, irradiation, downtime) |
| Percentages       | Weighted avg, weighted on energy (PR %, capture EUR) |
| Vs budget %       | Recompute from summed totals (NOT mean of monthly %) |
| Specific yield    | Σ energy / capacity                        |

**Renderers:**

- `renderFleetKPIs(keys)` — uses `aggregatePark`. Tile labels gain a
  dynamic suffix: *"Energy · April 2026"* / *"Energy · YTD 2026"*.
- `renderParkGrid(keys)` — period totals on each tile. The 13-month
  sparkline is unchanged (always last 13 months — period-agnostic
  context indicator).
- `renderParkTable(keys)` — one row per park, values from
  `aggregatePark`. Sorting unchanged.

**Partial data:** if `months_present < months_expected`, render a
small yellow dot `●` next to the park name with a tooltip
*"3 of 4 months, March missing"*. The KPI strip gets a summary line
*"YTD 2025 · 3 of 4 months (April missing)"*. Never blank rows.

### 4. Drill-down (smooth handoff, otherwise unchanged)

```js
function enterDrilldown(parkKey) {
    ASSETS_STATE.mode = 'drilldown';
    ASSETS_STATE.selectedPark = parkKey;

    var p = ASSETS_STATE.period;
    if (p.granularity === 'month') {
        ASSETS_STATE.drillMonth = p.year + '-' + pad(p.month);
    } else {
        ASSETS_STATE.drillMonth = latestMonthForPark(parkKey);
    }
    renderAssets();
}
```

When entering drill-down from YTD/Year mode, a small breadcrumb hint
appears:

```
← Fleet  /  Assets  /  Hörby
Showing single month. Came from YTD 2026 ·
[Back to YTD 2026]
```

The "Back to YTD 2026" link is just `exitDrilldown()` with a
human-readable label — confirms the period state survives the trip.
From `month` granularity no extra row appears (transition is already
seamless).

The period bar is hidden in drill-down (it controls fleet view, not
the park view). Drill-down's own `<select id="drill-month-sel">`
stays exactly as it is.

### 5. Edge cases, defaults, accessibility

**Defaults:** `month` granularity, latest year/month with data —
identical to today's "Latest". Zero regression for existing users.

**Year/month lists derived from data:**

- `availableYears()` — unique years across all parks' `months`.
- `availableMonthsInYear(y)` — unique months for that year.
- Year stepper arrows disable at edges. Month dropdown only lists
  months present in the data for the chosen year.

**Snap behavior:**

- `Month · 2026 · April` → user changes year to 2024. If 2024-04 is
  missing, snap to the latest available month in 2024 with a brief
  toast: *"Snapped to 2024-12 — April 2024 missing"*.
- `YTD · 2022` when 2022 has only Jul–Dec → YTD computed on the
  months that exist within `≤ currentMonthOfYear`; if zero, show
  `empty-note` *"No data for this period"*.

**Accessibility:**

- Segmented control: `role="tablist"`, each button `role="tab"` +
  `aria-selected`. Arrow keys cycle granularity.
- Year stepper buttons: `aria-label="Previous year"` /
  `"Next year"`.
- Period bar container: `aria-label="Period filter"`.

**CSS:** `.seg` style already exists. New rules limited to the sticky
container.

## Out of scope (deferred)

- Quarter granularity.
- Cross-period comparison views.
- URL/localStorage persistence of period state.
- YTD/Year inside drill-down (would require redesigning daily
  charts and best/worst-day logic — separate plan if requested).

## Implementation notes

Single file affected: `elpris/unified_dashboard_v3_html.py`.

Touch points:

- HTML template: replace top-right month/zone selects with the new
  period bar; update title to render dynamic suffix; remove
  `assets-month-label` span.
- JS: extend `ASSETS_STATE`; add `periodKeys`, `aggregatePark`,
  `availableYears`, `availableMonthsInYear`, `formatPeriodSuffix`,
  `currentMonthOfYear`. Replace `activeMonthKey()` call sites.
- CSS: sticky rules for the new bar.

Tests by inspection in browser (no automated UI tests today):

1. Default load → identical KPIs/table to today's "Latest".
2. Month + arrow-stepping years → snap toast when month missing.
3. YTD 2026 → KPIs sum Jan–Apr, table totals match.
4. YTD 2025 → KPIs sum Jan–Apr 2025 (symmetric), partial-data dots
   absent if all 4 months exist.
5. Year 2024 → full-year totals, sparkline still last 13 months.
6. Drill-down from Month preserves the chosen month; from YTD/Year
   jumps to the park's latest month with the breadcrumb hint.
