# Datadriven Excel-export V2 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the hardcoded Excel export with a data-driven version that auto-discovers profiles and supports yearly/monthly/daily/hourly granularity.

**Architecture:** Add `granularities` parameter to `calculate_dashboard_v2_data()`. Capture hourly data alongside daily in the same iteration loop. Rewrite `excel_export_v2.py` to iterate over whatever profiles and granularities the data dict contains.

**Tech Stack:** Python 3, openpyxl (write_only mode for hourly sheets)

---

### Task 1: Add `granularities` parameter to `calculate_dashboard_v2_data()`

**Files:**
- Modify: `elpris/dashboard_v2_data.py:563-695`

**Step 1: Add parameter with default**

Change the function signature at line 563:

```python
def calculate_dashboard_v2_data(
    granularities: list[str] | None = None,
) -> dict:
```

Add at the top of the function body (after the docstring):

```python
    if granularities is None:
        granularities = ["yearly", "monthly", "daily"]
    valid = {"yearly", "monthly", "daily", "hourly"}
    granularities = [g for g in granularities if g in valid]
```

**Step 2: Gate existing aggregation calls**

Replace the zone_data assembly blocks. For baseload (lines 617-621):

```python
        zone_data["baseload"] = {}
        if "yearly" in granularities:
            zone_data["baseload"]["yearly"] = _aggregate_to_yearly(baseload_daily)
        if "monthly" in granularities:
            zone_data["baseload"]["monthly"] = _aggregate_to_monthly(baseload_daily)
        if "daily" in granularities:
            zone_data["baseload"]["daily"] = _aggregate_daily(baseload_daily)
```

Same pattern for solar profiles (lines 634-638) and ENTSO-E (lines 646-651):

```python
                zone_data[key] = {}
                if "yearly" in granularities:
                    zone_data[key]["yearly"] = _aggregate_to_yearly(daily)
                if "monthly" in granularities:
                    zone_data[key]["monthly"] = _aggregate_to_monthly(daily)
                if "daily" in granularities:
                    zone_data[key]["daily"] = _aggregate_daily(daily)
```

**Step 3: Verify dashboard still works**

Run: `python3 generate_dashboard_v2.py`
Expected: Same output as before (default granularities unchanged).

**Step 4: Commit**

```
feat: add granularities parameter to calculate_dashboard_v2_data
```

---

### Task 2: Add hourly data collection

**Files:**
- Modify: `elpris/dashboard_v2_data.py`

Hourly data is collected inside the same loops that build daily data, gated behind `"hourly" in granularities`.

**Step 1: Add `_collect_hourly_baseload` helper**

Add after `_aggregate_daily` (around line 300):

```python
def _collect_hourly_baseload(
    spot_prices: dict[str, list[dict]],
) -> list[dict]:
    """Collect hourly baseload prices (no aggregation needed)."""
    result = []
    for date_key in sorted(spot_prices):
        for h_rec in spot_prices[date_key]:
            result.append({
                "date": date_key,
                "hour": h_rec["utc_hour"],
                "baseload": round(h_rec["eur_mwh"], 2),
                "capture": None,
                "weight": None,
                "ratio": None,
            })
    return result
```

**Step 2: Add `_collect_hourly_capture` helper**

```python
def _collect_hourly_entsoe(
    spot_prices: dict[str, list[dict]],
    generation: dict[str, dict[int, float]],
) -> list[dict]:
    """Collect hourly capture data from ENTSO-E generation."""
    result = []
    for date_key in sorted(spot_prices):
        if date_key not in generation:
            continue
        gen = generation[date_key]
        for h_rec in spot_prices[date_key]:
            h = h_rec["utc_hour"]
            price = h_rec["eur_mwh"]
            gen_mw = gen.get(h, 0.0)
            baseload = round(price, 2)
            capture = round(price * gen_mw, 4) if gen_mw > 0 else 0.0
            result.append({
                "date": date_key,
                "hour": h,
                "baseload": baseload,
                "capture": capture,
                "weight": round(gen_mw, 2),
                "ratio": None,  # calculated in Excel
            })
    return result


def _collect_hourly_profile(
    spot_prices: dict[str, list[dict]],
    profile: dict[tuple[int, int, int], float],
) -> list[dict]:
    """Collect hourly capture data from PVsyst profile."""
    result = []
    for date_key in sorted(spot_prices):
        d = date.fromisoformat(date_key)
        for h_rec in spot_prices[date_key]:
            price = h_rec["eur_mwh"]
            utc_dt = datetime(
                d.year, d.month, d.day, h_rec["utc_hour"], tzinfo=UTC_TZ
            )
            local_dt = utc_dt.astimezone(SWEDEN_TZ)
            key = (local_dt.month, local_dt.day, local_dt.hour)
            weight = profile.get(key, 0.0)
            result.append({
                "date": date_key,
                "hour": h_rec["utc_hour"],
                "baseload": round(price, 2),
                "capture": round(price * weight, 4) if weight > 0 else 0.0,
                "weight": round(weight, 4),
                "ratio": None,
            })
    return result
```

**Step 3: Wire hourly into `calculate_dashboard_v2_data()`**

For baseload section (after daily gate):

```python
        if "hourly" in granularities:
            zone_data["baseload"]["hourly"] = _collect_hourly_baseload(spot)
```

For solar profiles (inside the `for key, profile in pvsyst_loaded.items():` loop):

```python
            if "hourly" in granularities:
                zone_data[key]["hourly"] = _collect_hourly_profile(spot, profile)
```

For ENTSO-E (inside the `for key, (gen_type, _) in ENTSOE_CAPTURE_TYPES.items():` loop):

```python
            if "hourly" in granularities:
                zone_data[key]["hourly"] = _collect_hourly_entsoe(spot, gen)
```

**Step 4: Quick smoke test**

```python
python3 -c "
from elpris.dashboard_v2_data import calculate_dashboard_v2_data
d = calculate_dashboard_v2_data(granularities=['yearly', 'hourly'])
zone = d['zones'][0]
first_profile = list(d['data'][zone].keys())[0]
hourly = d['data'][zone][first_profile].get('hourly', [])
print(f'Zone: {zone}, profile: {first_profile}')
print(f'Hourly records: {len(hourly)}')
if hourly:
    print(f'First: {hourly[0]}')
    print(f'Last: {hourly[-1]}')
"
```

Expected: Thousands of hourly records per zone/profile.

**Step 5: Commit**

```
feat: add hourly data collection to dashboard v2 data pipeline
```

---

### Task 3: Rewrite `excel_export_v2.py` as data-driven serialization

**Files:**
- Rewrite: `elpris/excel_export_v2.py`

The new implementation iterates over `data["profiles"]` and available granularity levels. It creates one sheet per zone × granularity. No hardcoded profile knowledge.

**Step 1: Write the new `excel_export_v2.py`**

```python
"""Data-driven Excel export for Dashboard v2.

Generates .xlsx with one sheet per zone × granularity level.
Auto-discovers profiles from the data dict — new profiles appear as columns
without code changes.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, numbers
from openpyxl.utils import get_column_letter

LEVEL_ORDER = ["yearly", "monthly", "daily", "hourly"]

LEVEL_LABELS = {
    "yearly": "Årsvis",
    "monthly": "Månadsvis",
    "daily": "Daglig",
    "hourly": "Timvis",
}

# Time columns per granularity level
LEVEL_TIME_COLS = {
    "yearly": [("year", "År")],
    "monthly": [("year", "År"), ("month", "Månad")],
    "daily": [("date", "Datum")],
    "hourly": [("date", "Datum"), ("hour", "Timme (UTC)")],
}

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "Maj", "Jun",
    "Jul", "Aug", "Sep", "Okt", "Nov", "Dec",
]

# Styles
HEADER_FONT = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")
BODY_FONT = Font(name="Calibri", size=10)
TITLE_FONT = Font(name="Calibri", bold=True, size=11, color="4A9EFF")
NUM_FMT_PRICE = '#,##0.00'
NUM_FMT_RATIO = '0.000'
NUM_FMT_WEIGHT = '0.0000'

ZONE_TAB_COLORS = {
    "SE1": "3B82F6",
    "SE2": "10B981",
    "SE3": "F59E0B",
    "SE4": "EF4444",
}

# Profiles in these categories use generation weight, not ratio
WEIGHT_PROFILES = set()  # all non-baseload profiles have weight


def generate_dashboard_excel(data: dict, output_path: Path) -> None:
    """Generate Excel report from dashboard v2 data.

    Creates one sheet per zone × granularity level.
    Profiles are auto-discovered from data["profiles"].
    """
    wb = Workbook(write_only=False)
    # Remove default sheet
    if wb.active:
        wb.remove(wb.active)

    zones = data.get("zones", [])
    profiles = data.get("profiles", {})
    profile_meta = data.get("profile_meta", {})
    all_data = data.get("data", {})

    for zone in zones:
        zone_data = all_data.get(zone, {})
        if not zone_data:
            continue

        # Determine which profiles have data for this zone
        available_profiles = [k for k in profiles if k in zone_data and k != "baseload"]

        # Filter out BESS profiles for the Excel export
        available_profiles = [
            k for k in available_profiles
            if not profile_meta.get(k, {}).get("category", "").startswith("bess")
        ]

        # Determine which granularities exist
        sample_profile = zone_data.get("baseload", {})
        available_levels = [lv for lv in LEVEL_ORDER if lv in sample_profile]

        for level in available_levels:
            sheet_name = f"{zone} {LEVEL_LABELS.get(level, level)}"
            # Excel sheet names max 31 chars
            if len(sheet_name) > 31:
                sheet_name = sheet_name[:31]

            ws = wb.create_sheet(title=sheet_name)
            ws.sheet_properties.tabColor = ZONE_TAB_COLORS.get(zone, "888888")

            _write_level_sheet(ws, zone, level, zone_data, profiles,
                               available_profiles, profile_meta)

    # Summary sheet
    _write_summary(wb, data)

    wb.save(output_path)


def _write_level_sheet(
    ws, zone: str, level: str, zone_data: dict,
    profiles: dict, available_profiles: list[str],
    profile_meta: dict,
) -> None:
    """Write one granularity level for one zone."""
    time_cols = LEVEL_TIME_COLS[level]
    is_hourly = level == "hourly"

    # Build header
    headers = [label for _, label in time_cols]
    headers.append("Baseload")

    # For each profile: capture column + weight/ratio column
    col_map = []  # list of (profile_key, "capture"|"weight"|"ratio")
    for pk in available_profiles:
        name = profiles.get(pk, pk)
        headers.append(f"{name}")
        col_map.append((pk, "capture"))
        if is_hourly:
            headers.append("Vikt")
            col_map.append((pk, "weight"))
        else:
            headers.append("Ratio")
            col_map.append((pk, "ratio"))

    # Write header row
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    # Collect baseload rows as reference for ordering
    baseload_rows = zone_data.get("baseload", {}).get(level, [])
    if not baseload_rows:
        return

    # Build lookup dicts per profile: key -> row
    profile_lookups = {}
    for pk in available_profiles:
        rows = zone_data.get(pk, {}).get(level, [])
        lookup = {}
        for r in rows:
            lk = _level_key(level, r)
            lookup[lk] = r
        profile_lookups[pk] = lookup

    # Write data rows
    for row_idx, bl_row in enumerate(baseload_rows, 2):
        col = 1

        # Time columns
        for field, _ in time_cols:
            val = bl_row.get(field)
            if field == "month" and isinstance(val, int) and 1 <= val <= 12:
                val = MONTH_NAMES[val - 1]
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.font = BODY_FONT
            col += 1

        # Baseload price
        _write_price_cell(ws, row_idx, col, bl_row.get("baseload"))
        col += 1

        # Profile columns
        lk = _level_key(level, bl_row)
        for pk, col_type in col_map:
            p_row = profile_lookups.get(pk, {}).get(lk)
            val = p_row.get(col_type) if p_row else None
            if col_type == "capture":
                _write_price_cell(ws, row_idx, col, val)
            elif col_type == "ratio":
                _write_ratio_cell(ws, row_idx, col, val)
            elif col_type == "weight":
                _write_weight_cell(ws, row_idx, col, val)
            col += 1

    # Freeze top row + auto-filter
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(baseload_rows) + 1}"

    # Column widths
    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 14


def _write_summary(wb: Workbook, data: dict) -> None:
    """Write a summary sheet with latest year per zone."""
    ws = wb.create_sheet(title="Sammanfattning", index=0)

    profiles = data.get("profiles", {})
    profile_meta = data.get("profile_meta", {})
    all_data = data.get("data", {})
    zones = data.get("zones", [])

    # Collect available profiles across all zones (non-BESS)
    all_available = []
    for zone in zones:
        zd = all_data.get(zone, {})
        for k in profiles:
            if (k != "baseload" and k in zd and k not in all_available
                    and not profile_meta.get(k, {}).get("category", "").startswith("bess")):
                all_available.append(k)

    # Header
    headers = ["Zon", "År", "Baseload"]
    for pk in all_available:
        headers.append(profiles.get(pk, pk))
        headers.append("Ratio")

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    row = 2
    for zone in zones:
        zd = all_data.get(zone, {})
        yearly = zd.get("baseload", {}).get("yearly", [])
        if not yearly:
            continue

        # Latest year
        latest = yearly[-1]
        col = 1
        ws.cell(row=row, column=col, value=zone).font = Font(
            name="Calibri", bold=True, size=11)
        col += 1
        ws.cell(row=row, column=col, value=latest["year"]).font = BODY_FONT
        col += 1
        _write_price_cell(ws, row, col, latest.get("baseload"))
        col += 1

        for pk in all_available:
            pk_yearly = zd.get(pk, {}).get("yearly", [])
            match = next(
                (r for r in pk_yearly if r["year"] == latest["year"]), None
            )
            _write_price_cell(ws, row, col, match["capture"] if match else None)
            col += 1
            _write_ratio_cell(ws, row, col, match["ratio"] if match else None)
            col += 1

        row += 1

    ws.freeze_panes = "A2"
    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 14


def _level_key(level: str, row: dict) -> tuple:
    """Create a lookup key for a row at a given level."""
    if level == "yearly":
        return (row.get("year"),)
    elif level == "monthly":
        return (row.get("year"), row.get("month"))
    elif level == "daily":
        return (row.get("date"),)
    elif level == "hourly":
        return (row.get("date"), row.get("hour"))
    return ()


def _write_price_cell(ws, row: int, col: int, value) -> None:
    cell = ws.cell(row=row, column=col)
    if value is not None:
        cell.value = value
        cell.number_format = NUM_FMT_PRICE
    else:
        cell.value = "–"
    cell.font = BODY_FONT
    cell.alignment = Alignment(horizontal="right")


def _write_ratio_cell(ws, row: int, col: int, value) -> None:
    cell = ws.cell(row=row, column=col)
    if value is not None:
        cell.value = value
        cell.number_format = NUM_FMT_RATIO
        if value >= 0.9:
            cell.font = Font(name="Calibri", size=10, color="059669")
        elif value >= 0.7:
            cell.font = Font(name="Calibri", size=10, color="D97706")
        else:
            cell.font = Font(name="Calibri", size=10, color="DC2626")
    else:
        cell.value = "–"
        cell.font = BODY_FONT
    cell.alignment = Alignment(horizontal="right")


def _write_weight_cell(ws, row: int, col: int, value) -> None:
    cell = ws.cell(row=row, column=col)
    if value is not None:
        cell.value = value
        cell.number_format = NUM_FMT_WEIGHT
    else:
        cell.value = "–"
    cell.font = BODY_FONT
    cell.alignment = Alignment(horizontal="right")
```

**Step 2: Verify it works with existing data (no hourly)**

```bash
python3 -c "
from elpris.dashboard_v2_data import calculate_dashboard_v2_data
from elpris.excel_export_v2 import generate_dashboard_excel
from pathlib import Path
data = calculate_dashboard_v2_data()
generate_dashboard_excel(data, Path('/tmp/test_excel_v2.xlsx'))
print('OK')
"
```

**Step 3: Commit**

```
feat: rewrite excel_export_v2 as data-driven serialization
```

---

### Task 4: Wire hourly into Excel generation

**Files:**
- Modify: `generate_dashboard_v2.py:1323-1329`

**Step 1: Generate separate data for Excel with hourly**

Replace the Excel section (lines 1323-1329) with:

```python
    # Excel (with hourly data)
    print("Genererar Excel (inkl. timdata)...")
    from elpris.excel_export_v2 import generate_dashboard_excel
    excel_data = calculate_dashboard_v2_data(
        granularities=["yearly", "monthly", "daily", "hourly"]
    )
    xlsx_path = output_dir / f"dashboard_v2_{today}.xlsx"
    generate_dashboard_excel(excel_data, xlsx_path)
    size_mb = xlsx_path.stat().st_size / (1024 * 1024)
    print(f"  Excel: {xlsx_path} ({size_mb:.1f} MB)")
```

Note: This calls `calculate_dashboard_v2_data()` a second time with hourly included. This is intentional — the HTML data dict should NOT contain hourly (it would bloat the HTML). The calculation takes ~10-20 seconds extra but keeps the two outputs cleanly separated.

**Step 2: Commit**

```
feat: generate Excel with hourly data in dashboard v2
```

---

### Task 5: End-to-end verification

**Step 1: Run full generation**

```bash
python3 generate_dashboard_v2.py
```

Expected:
- HTML file generated (same as before)
- Excel file generated with ~17 sheets (4 zones × 4 levels + 1 summary)
- Excel file size: ~15-25 MB

**Step 2: Verify Excel structure**

```python
python3 -c "
from openpyxl import load_workbook
wb = load_workbook('/tmp/test_path.xlsx', read_only=True)
for name in wb.sheetnames:
    ws = wb[name]
    print(f'{name}: {ws.max_row} rows × {ws.max_column} cols')
wb.close()
"
```

Expected: 
- Sammanfattning: 5 rows
- SE* Årsvis: ~5-6 rows
- SE* Månadsvis: ~60 rows
- SE* Daglig: ~1800 rows
- SE* Timvis: ~40000+ rows

**Step 3: Verify dashboard HTML still works**

Open `Resultat/rapporter/dashboard_v2_*.html` in browser. Verify all charts render correctly.

**Step 4: Commit**

```
chore: verify end-to-end Excel generation
```

---

## Performance note

Calling `calculate_dashboard_v2_data()` twice (once for HTML, once for Excel+hourly) doubles the calculation time. If this becomes a problem, a future optimization is to calculate with all granularities once and strip hourly before embedding in HTML. But for now, simplicity wins — the calculation takes ~20-30 seconds total, not a bottleneck.

## What NOT to change

- `elpris/dashboard_data.py` (V1 data) — untouched
- `elpris/excel_export.py` (V1 Excel) — untouched
- `generate_dashboard.py` (V1 generator) — untouched
- `update_all.py` — already calls `generate_dashboard_v2.py`
- Dashboard HTML template/JavaScript — untouched
