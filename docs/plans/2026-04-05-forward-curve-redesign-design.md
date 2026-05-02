# Forward Curve Redesign — Continuous Time Axis

**Date:** 2026-04-05
**Status:** Design validated, ready for implementation
**File:** `generate_dashboard_v2.py` (function `renderForwardCurve`)

## Problem

The current forward curve chart mixes quarter contracts (Q2-26, Q3-26, ...) and
year contracts (YR-27, YR-28, ...) on a single categorical x-axis. This is
visually confusing because:

- YR-27 represents the same period as Q1-27+Q2-27+Q3-27+Q4-27 combined, but
  they appear as separate bars side-by-side on the axis.
- The categorical x-axis obscures the actual time relationship between
  contracts.
- No visual cue separates high-granularity data (quarters, 2026-2028) from
  low-granularity data (years only, 2029-2036).

## Design Decision

Replace the categorical x-axis with a **continuous time axis**. Quarters and
years then coexist naturally on the same chart because they map to real date
ranges.

### Visualization

**Quarter contracts** — rendered as stacked bars (unchanged from today):
- Bar spans the quarter's date range (3 months wide)
- SYS (blue `#4a9eff`, opacity 0.7) as base
- EPAD (green `#10b981` if positive, red `#ef4444` if negative, opacity 0.85)
  stacked on top
- Top of stack represents the zone price (SYS + EPAD)
- Text label above bar shows zone price in EUR/MWh

**Year contracts** — rendered as horizontal line segments ("plateaus"):
- Single white (`#ffffff`) solid line, 2.5–3px thick
- Spans the year's date range (Jan 1 → Dec 31)
- Positioned at the zone price level (SYS + EPAD)
- Text label above the segment midpoint: `YR-XX: {price}`

**Coexistence rule:**
- For periods with both quarters and years (Q2-26 → Q3-28 + YR-27, YR-28):
  year plateaus are drawn *over* the quarter bars on the same date range
- For periods with only years (YR-29 → YR-36): only plateaus are drawn, no
  bars below them

### X-axis
- Type: date (continuous)
- Major gridlines at year boundaries (Jan 1 each year), subtle color `#2a3550`
- Minor tick labels below: quarter labels where present (e.g. "Q2-26"),
  year labels where no quarters exist ("YR-29")
- Labels rotated -45°

### Y-axis
- Unchanged: "EUR/MWh", `rangemode: tozero`

### Removed elements
- The dashed white zone-price line that connected all categorical points is
  removed. Its function is replaced by the quarter-bar tops (for quarters) and
  the year plateaus (for years).

### Legend
Three entries:
- `SYS` (blue square)
- `EPAD` (green square)
- `YR-kontrakt` (white line)

The existing "SE3 zonpris" entry is removed.

### Hover interaction
- `hovermode: 'closest'` — Plotly picks the nearest trace when quarter bars
  and year plateaus overlap.
- **Quarter bar tooltip:**
  ```
  SE3 Q2-26
  Period: apr–jun 2026
  Zonpris: 47.15 EUR/MWh
  SYS: 48.20
  EPAD: -1.05
  ```
- **Year plateau tooltip:**
  ```
  SE3 YR-27
  Period: jan–dec 2027
  Zonpris: 41.90 EUR/MWh
  SYS: 44.50
  EPAD: -2.60
  ```

### Filtering
No custom filter UI is needed. Plotly's built-in legend click-to-toggle
provides the filtering:
- Click "YR-kontrakt" → hide all year plateaus (quarter view only)
- Click "SYS" / "EPAD" → hide quarter bars (year view only)

## Alternatives Considered

**Two separate charts (quarter + year stacked vertically)** — rejected.
Loses direct visual comparison between the year plateau and its underlying
quarters.

**Single chart with explicit toggle buttons [Quarter] [Year] [Both]** —
rejected. The continuous time axis makes both views visually distinct enough
that explicit toggling is redundant. Legend click-to-toggle is sufficient.

**Continuous axis with year contracts as wide transparent bars** — rejected.
Overlapping solid bars at different widths create visual clutter. Horizontal
line segments communicate "reference level" more clearly.

**Staircase line (quarters as primary line, year as thick reference line)** —
rejected. Loses the SYS/EPAD decomposition which is useful signal.

## Implementation Notes

**Data structure:** No backend changes needed. `load_forward_curve_data()` in
`elpris/dashboard_v2_data.py` already emits `contracts` with `type`, `start`,
and `end` fields. The redesign is purely a change to `renderForwardCurve()` in
`generate_dashboard_v2.py`.

**Plotly specifics:**
- `xaxis.type = 'date'`
- Quarter bar width: `width` property in milliseconds (quarter length minus
  small margin). Plotly's bar width on date axes is specified in ms.
- Year plateau: use a `scatter` trace with `mode: 'lines+text'` and two points
  per year (start, end) at the same y-value. Each year is its own trace entry
  OR a single trace with `null` gaps between years.

**Label positioning:**
- Quarter bar labels: use existing bar `text` with `textposition: 'outside'`.
- Year plateau labels: use `text` on the scatter trace, positioned at the
  midpoint of each segment.

## Files to Modify

- `generate_dashboard_v2.py` — rewrite `renderForwardCurve()` (lines ~1395–1488).
  No changes to `renderForwardVsSpot()` or `renderEpadSpread()`.

## Out of Scope

- Changes to the "Forward vs Realiserat Spot" chart
- Changes to the "EPAD-spread" chart
- Backend data changes in `dashboard_v2_data.py`
