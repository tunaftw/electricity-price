# Unified Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a single-file unified dashboard combining CAPTURE / BESS / FUTURES / ASSETS, in two parallel visual tracks (A = Bloomberg-dark extension of existing v2; C = fresh modern design via frontend-design skill), with `update_all.py` regenerating everything in one command.

**Architecture:** Shared backend (`unified_dashboard_data.py`) produces a single JSON consumed by two HTML renderers. Backend re-uses `dashboard_v2_data`, `operations_dashboard_data`, and `performance_report_data`. Track A surgically extends `dashboard_v2`'s renderer. Track C is built fresh using the `frontend-design` skill.

**Tech Stack:** Python 3.9, Plotly.js (CDN), vanilla JS, no frameworks. Tests via `pytest` (existing pattern in `tests/test_quality.py`).

**Reference design:** `docs/plans/2026-05-02-unified-dashboard-design.md`

---

## Phase 1: Backend Data Layer (~2h)

### Task 1.1: Create `unified_dashboard_data.py` skeleton

**Files:**
- Create: `elpris/unified_dashboard_data.py`
- Create: `tests/test_unified_dashboard_data.py`

**Step 1: Write the failing test**

```python
# tests/test_unified_dashboard_data.py
"""Tester för elpris.unified_dashboard_data."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.unified_dashboard_data import build_unified_data


def test_build_unified_data_returns_dict_with_required_top_level_keys():
    data = build_unified_data()
    assert isinstance(data, dict)
    assert "generated" in data
    assert "market" in data    # CAPTURE/BESS/FUTURES wrapper
    assert "assets" in data    # NEW assets section
    assert "meta" in data      # zone list, profile colors, etc.
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_unified_dashboard_data.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'elpris.unified_dashboard_data'`

**Step 3: Minimal implementation**

```python
# elpris/unified_dashboard_data.py
"""Unified dashboard data aggregator.

Combines market data (CAPTURE/BESS/FUTURES from dashboard_v2_data) with
asset data (per-park monthly KPIs from performance_report_data and
operations_dashboard_data) into a single JSON structure consumed by
both Track A and Track C HTML renderers.
"""
from __future__ import annotations

from datetime import datetime


def build_unified_data() -> dict:
    """Build the complete data dict for the unified dashboard."""
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "market": {},
        "assets": {},
        "meta": {},
    }
```

**Step 4: Run test, verify pass**

```bash
pytest tests/test_unified_dashboard_data.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add elpris/unified_dashboard_data.py tests/test_unified_dashboard_data.py
git commit -m "feat(dashboard): scaffold unified_dashboard_data module"
```

---

### Task 1.2: Wire market data (re-use dashboard_v2_data)

**Files:**
- Modify: `elpris/unified_dashboard_data.py`
- Modify: `tests/test_unified_dashboard_data.py`

**Step 1: Add failing test**

```python
def test_market_section_contains_v2_keys():
    """Market section must include all keys produced by dashboard_v2_data."""
    data = build_unified_data()
    market = data["market"]
    # dashboard_v2 produces these top-level keys
    for k in ("zones", "profiles", "colors", "yearly", "monthly", "daily"):
        assert k in market, f"market missing key: {k}"
```

**Step 2: Run, verify fail**

```bash
pytest tests/test_unified_dashboard_data.py::test_market_section_contains_v2_keys -v
```

**Step 3: Implement**

```python
from .dashboard_v2_data import calculate_dashboard_v2_data

def build_unified_data() -> dict:
    market = calculate_dashboard_v2_data()
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "market": market,
        "assets": {},
        "meta": {
            "zones": market.get("zones", []),
            "profiles": market.get("profiles", {}),
            "colors": market.get("colors", {}),
        },
    }
```

**Step 4: Run, verify pass**

**Step 5: Commit**

```bash
git add elpris/unified_dashboard_data.py tests/test_unified_dashboard_data.py
git commit -m "feat(dashboard): wire market data via dashboard_v2_data"
```

---

### Task 1.3: Add per-park monthly KPI aggregation

**Files:**
- Modify: `elpris/unified_dashboard_data.py`
- Modify: `tests/test_unified_dashboard_data.py`

**Context:** `performance_report_data.generate_report(park_key, year, month)` returns a `MonthlyReport` with all KPIs for one park, one month. We loop over all 8 parks × N months.

**Step 1: Add failing test**

```python
def test_assets_section_has_per_park_monthly_data():
    data = build_unified_data()
    assets = data["assets"]
    assert "parks" in assets
    parks = assets["parks"]
    # All 8 parks present
    for pk in ("horby", "fjallskar", "agerum", "hova",
               "skakelbacken", "stenstorp", "tangen", "bjorke"):
        assert pk in parks, f"missing park: {pk}"
        park = parks[pk]
        assert "name" in park
        assert "zone" in park
        assert "capacity_mwp" in park
        assert "months" in park  # list of monthly records
```

**Step 2: Run, verify fail**

**Step 3: Implement**

```python
from .config import PARK_CAPACITY_KWP, PARK_ZONES
from .park_config import PARK_DISPLAY_NAMES  # if exists, else hardcode
from .performance_report_data import generate_report

PARK_KEYS = ["horby", "fjallskar", "agerum", "hova",
             "skakelbacken", "stenstorp", "tangen", "bjorke"]

def _build_park_months(park_key: str, num_months: int = 13) -> list[dict]:
    """Generate last N monthly KPI records for a park."""
    today = datetime.now()
    results = []
    # Walk backward from latest complete month
    year, month = today.year, today.month - 1
    if month == 0:
        year, month = year - 1, 12
    for _ in range(num_months):
        try:
            r = generate_report(park_key, year, month)
            if r is not None:
                results.append({
                    "year": year,
                    "month": month,
                    "energy_mwh": r.actual_energy_mwh,
                    "budget_mwh": r.budget_energy_mwh,
                    "vs_budget_pct": (
                        100 * (r.actual_energy_mwh - r.budget_energy_mwh)
                        / r.budget_energy_mwh
                    ) if r.budget_energy_mwh else None,
                    "yield_kwh_kwp": r.norm_yield_mwh_mwp,
                    "pr_pct": r.actual_pr_pct,
                })
        except Exception:
            pass  # skip months without data
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(results))  # chronological order


def _build_assets_section() -> dict:
    parks = {}
    for pk in PARK_KEYS:
        zone = PARK_ZONES.get(pk)
        cap_kwp = PARK_CAPACITY_KWP.get(pk, 0)
        months = _build_park_months(pk)
        parks[pk] = {
            "name": pk.capitalize(),  # placeholder; refine later
            "zone": zone,
            "capacity_mwp": round(cap_kwp / 1000, 3),
            "months": months,
        }
    return {"parks": parks}


def build_unified_data() -> dict:
    market = calculate_dashboard_v2_data()
    assets = _build_assets_section()
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "market": market,
        "assets": assets,
        "meta": {
            "zones": market.get("zones", []),
            "profiles": market.get("profiles", {}),
            "colors": market.get("colors", {}),
            "park_keys": PARK_KEYS,
        },
    }
```

**Step 4: Run test, verify pass**

```bash
pytest tests/test_unified_dashboard_data.py -v
```

**Step 5: Commit**

```bash
git add elpris/unified_dashboard_data.py tests/test_unified_dashboard_data.py
git commit -m "feat(dashboard): aggregate per-park monthly KPIs"
```

---

### Task 1.4: Add fleet-level summary KPIs

**Files:**
- Modify: `elpris/unified_dashboard_data.py`
- Modify: `tests/test_unified_dashboard_data.py`

**Step 1: Add failing test**

```python
def test_fleet_overview_kpis_for_latest_month():
    data = build_unified_data()
    fleet = data["assets"].get("fleet")
    assert fleet is not None
    assert "latest_month" in fleet  # e.g. "2026-04"
    assert "park_count" in fleet
    assert fleet["park_count"] == 8
    assert "total_capacity_mwp" in fleet
    assert "total_energy_mwh" in fleet
    assert "vs_budget_pct" in fleet
```

**Step 2-3: Implement `_build_fleet_overview()`**

```python
def _build_fleet_overview(parks: dict) -> dict | None:
    """Compute fleet-level KPIs for the most recent month with data."""
    # Find the latest month that ALL parks have data for
    all_months = set()
    for park in parks.values():
        for m in park["months"]:
            all_months.add((m["year"], m["month"]))
    if not all_months:
        return None
    latest = max(all_months)
    year, month = latest

    total_actual = 0
    total_budget = 0
    total_cap_mwp = 0
    park_count = 0
    for pk, park in parks.items():
        total_cap_mwp += park["capacity_mwp"]
        for m in park["months"]:
            if (m["year"], m["month"]) == latest:
                total_actual += m["energy_mwh"] or 0
                total_budget += m["budget_mwh"] or 0
                park_count += 1
                break

    return {
        "latest_month": f"{year}-{month:02d}",
        "park_count": len(parks),
        "total_capacity_mwp": round(total_cap_mwp, 2),
        "total_energy_mwh": round(total_actual, 1),
        "vs_budget_pct": round(
            100 * (total_actual - total_budget) / total_budget, 1
        ) if total_budget else None,
    }


def _build_assets_section() -> dict:
    parks = { ... }  # as before
    fleet = _build_fleet_overview(parks)
    return {"parks": parks, "fleet": fleet}
```

**Step 4: Run, verify pass**

**Step 5: Commit**

```bash
git commit -am "feat(dashboard): compute fleet-level summary KPIs"
```

---

### Task 1.5: Add operations metrics (negative price exposure, tracker gain) per park

**Files:**
- Modify: `elpris/unified_dashboard_data.py`
- Modify: `tests/test_unified_dashboard_data.py`

**Step 1: Test**

```python
def test_park_data_includes_operations_metrics():
    data = build_unified_data()
    horby = data["assets"]["parks"]["horby"]
    # latest month should have these enriched fields
    latest = horby["months"][-1] if horby["months"] else None
    if latest:
        # These come from operations_dashboard_data
        assert "neg_price_hours" in latest or "neg_price_volume_mwh" in latest
```

**Step 2-3: Implement** — call `operations_dashboard_data.calculate_negative_price_exposure()` once, then merge per (park, year, month) into the existing `_build_park_months` records.

**Step 4: Verify pass**

**Step 5: Commit**

```bash
git commit -am "feat(dashboard): add operations metrics per park-month"
```

---

### Task 1.6: Add tracker-gain (Hova vs Björke+Skäkelbacken) summary

**Step 1: Test that `data["assets"]["tracker_gain"]` exists with `monthly` list.**

**Step 2-3: Re-use `operations_dashboard_data.calculate_tracker_gain()`.**

**Step 4-5: Verify, commit.**

---

### Task 1.7: Validate full data build with smoke test

**Files:**
- Modify: `tests/test_unified_dashboard_data.py`

**Step 1: Add integration test**

```python
def test_build_unified_data_no_errors_and_serializable():
    import json
    data = build_unified_data()
    # Must be JSON serializable (no datetime, sets, etc.)
    s = json.dumps(data, default=str)
    assert len(s) > 1000  # non-trivial size
```

**Step 2-5: Run, verify pass, commit.**

---

## Phase 2: Track A — Extend dashboard_v2 (~6h)

### Task 2.1: Create entrypoint script

**Files:**
- Create: `generate_unified_dashboard.py`
- Create: `elpris/unified_dashboard_html.py`

**Step 1: Skeleton**

```python
# generate_unified_dashboard.py
#!/usr/bin/env python3
"""Generate the unified dashboard (Track A and/or Track C)."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from elpris.unified_dashboard_data import build_unified_data
from elpris.unified_dashboard_html import render_track_a

OUT_DIR = Path(__file__).parent / "Resultat" / "rapporter"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--track", choices=["A", "C", "both"], default="both")
    args = p.parse_args()

    data = build_unified_data()
    today = datetime.now().strftime("%Y%m%d")

    if args.track in ("A", "both"):
        html = render_track_a(data)
        out = OUT_DIR / f"dashboard_unified_{today}.html"
        out.write_text(html, encoding="utf-8")
        print(f"  Track A: {out}")

    if args.track in ("C", "both"):
        from elpris.unified_dashboard_v3_html import render_track_c
        html = render_track_c(data)
        out = OUT_DIR / f"dashboard_unified_v3_{today}.html"
        out.write_text(html, encoding="utf-8")
        print(f"  Track C: {out}")


if __name__ == "__main__":
    main()
```

```python
# elpris/unified_dashboard_html.py — STARTING POINT
"""Track A renderer: extends dashboard_v2 with ASSETS tab."""
from __future__ import annotations
import json


def render_track_a(data: dict) -> str:
    return f"<!DOCTYPE html><html><body>WIP — data has {len(data)} top-level keys</body></html>"
```

**Step 2: Smoke test it runs**

```bash
python3 generate_unified_dashboard.py --track A
```
Expected: file written to `Resultat/rapporter/dashboard_unified_20260502.html`

**Step 3: Commit**

```bash
git add generate_unified_dashboard.py elpris/unified_dashboard_html.py
git commit -m "feat(dashboard): scaffold unified dashboard entrypoint"
```

---

### Task 2.2: Port dashboard_v2 HTML body into Track A renderer

**Files:**
- Modify: `elpris/unified_dashboard_html.py`

**Approach:** Read `generate_dashboard_v2.py`, extract the HTML/CSS/JS body into `render_track_a(data)` as a single f-string. Keep CAPTURE/BESS/FUTURES tabs as-is. Replace the OPERATIONS tab DOM scaffold with an empty ASSETS placeholder.

**Step 1: Open `generate_dashboard_v2.py`** — note that `_build_html(data)` is the function. Copy its body.

**Step 2: Adapt:**
- Rename topbar tab `tab-operations` → `tab-assets`
- Rename label "OPERATIONS" → "ASSETS"
- Rename function `renderOperations()` → `renderAssets()` (keep stubbed for now)
- Wire `switchDashboard('assets')` accordingly

**Step 3: Smoke test — file generates and opens in browser**

```bash
python3 generate_unified_dashboard.py --track A
open Resultat/rapporter/dashboard_unified_20260502.html
```
Expected: 4 tabs visible, CAPTURE works as before, ASSETS tab opens but empty.

**Step 4: Commit**

```bash
git commit -am "feat(dashboard): port v2 layout into unified Track A"
```

---

### Task 2.3: Build Fleet Overview KPI tiles in ASSETS tab

**Files:**
- Modify: `elpris/unified_dashboard_html.py`

**Step 1: Add HTML scaffold** inside the assets-view div:

```html
<div id="assets-view" style="display:none">
  <div class="card">
    <div class="card-title">Fleet Overview</div>
    <div id="fleet-kpi-row" style="display:flex;gap:1rem;margin-top:1rem"></div>
  </div>
  <div class="card">
    <div class="card-title">Park Cards</div>
    <div id="park-cards-grid"></div>
  </div>
  <div class="card">
    <div class="card-title">Comparison</div>
    <div id="park-comparison-table"></div>
  </div>
</div>
```

**Step 2: Add JS render function**

```javascript
function renderFleetKPIs() {
  const fleet = DATA.assets.fleet;
  if (!fleet) return;
  const tiles = [
    { label: 'Parks', value: fleet.park_count },
    { label: 'Installed', value: fleet.total_capacity_mwp + ' MWp' },
    { label: fleet.latest_month + ' Energy', value: fleet.total_energy_mwh.toLocaleString() + ' MWh' },
    { label: 'vs Budget', value: (fleet.vs_budget_pct >= 0 ? '+' : '') + fleet.vs_budget_pct + '%',
      cls: fleet.vs_budget_pct >= 5 ? 'green' : fleet.vs_budget_pct <= -5 ? 'red' : 'yellow' },
  ];
  document.getElementById('fleet-kpi-row').innerHTML = tiles.map(t =>
    `<div class="kpi-tile ${t.cls || ''}">
       <div class="kpi-label">${t.label}</div>
       <div class="kpi-value">${t.value}</div>
     </div>`
  ).join('');
}
```

**Step 3: Wire into `switchDashboard('assets')`**

**Step 4: Smoke test — KPIs render with real data**

**Step 5: Commit**

```bash
git commit -am "feat(dashboard): Track A — Fleet Overview KPI tiles"
```

---

### Task 2.4: Build Park Cards grid (8 cards w/ sparklines)

**Files:**
- Modify: `elpris/unified_dashboard_html.py`

Render 8 cards. Each card shows: park name, zone badge, vs budget %, MWh, yield, mini-sparkline (12-month bars via SVG, no Plotly to keep cards lightweight). Click card → calls `drillIntoPark(parkKey)`.

**Step 1-3: Implement `renderParkCards()` + simple SVG sparkline helper**

**Step 4: Test — 8 cards visible, click logs to console**

**Step 5: Commit**

```bash
git commit -am "feat(dashboard): Track A — Park Cards with sparklines"
```

---

### Task 2.5: Build sortable Comparison Table

**Files:**
- Modify: `elpris/unified_dashboard_html.py`

Columns: Park | Zone | Cap MWp | MWh (latest) | vs Budget | YTD MWh | Yield. Click column header → sort. CSV export button.

**Step 1-3: Implement `renderParkTable()` with vanilla JS sort**

**Step 4: Test sort + CSV export**

**Step 5: Commit**

```bash
git commit -am "feat(dashboard): Track A — sortable park comparison table"
```

---

### Task 2.6: Build per-park drill-down view

**Files:**
- Modify: `elpris/unified_dashboard_html.py`

State: `state.assetsView = 'fleet' | 'drilldown'`, `state.drilldownPark = parkKey`.

When drill-down active, hide Fleet/Cards/Table and show:
- Header with back-button + park name + zone + month selector
- KPI row (6 tiles)
- 4 Plotly chart panels (Energy vs Budget bars, Yield line, Daily generation, Capture price)
- Best/worst days table
- Link to existing `performance_<park>_<zone>_<month>.html`

**Step 1-3: Implement `renderDrilldown(parkKey)` with 4 Plotly charts**

**Step 4: Test — click park card → drill-down visible**

**Step 5: Commit**

```bash
git commit -am "feat(dashboard): Track A — per-park drill-down view"
```

---

### Task 2.7: Add filters (month + zone)

**Files:**
- Modify: `elpris/unified_dashboard_html.py`

Top of ASSETS view: `<select id="assets-month">` + `<select id="assets-zone">`. Filter cards/table on change.

**Step 1-5: Implement, test, commit**

```bash
git commit -am "feat(dashboard): Track A — month and zone filters"
```

---

### Task 2.8: Apply color coding consistently

**Step 1-5:** CSS classes `.green`, `.yellow`, `.red` for KPI tiles, table cells, card borders. Apply based on `vs_budget_pct` thresholds (±5%).

```bash
git commit -am "feat(dashboard): Track A — vs-budget color coding"
```

---

### Task 2.9: Smoke-test Track A end-to-end

**Step 1: Generate**
```bash
python3 generate_unified_dashboard.py --track A
```

**Step 2: Open and click through every tab and drill-down**

**Step 3: Document any issues, fix, commit**

```bash
git commit -am "feat(dashboard): Track A — final polish"
```

---

## Phase 3: Track C — Fresh Design (~8h)

### Task 3.1: Invoke frontend-design skill for visual direction

**Step 1: Use frontend-design skill**

```
Skill: frontend-design
Prompt: Design a modern data dashboard for renewable energy operations.
Context: 4 tabs (electricity prices, battery revenue, futures, asset
performance). Audience: internal team — operations, finance, executives.
Style: NOT Bloomberg-dark, NOT marketing-fluffy. Inspiration: Linear,
Vercel, Stripe dashboards. Constraint: single-file HTML with inline
CSS, Plotly via CDN. Provide design tokens (colors, type scale, spacing).
```

**Step 2: Save the design tokens output to `docs/plans/2026-05-02-track-c-design-tokens.md`**

**Step 3: Commit the tokens document**

---

### Task 3.2: Build Track C base HTML scaffold

**Files:**
- Create: `elpris/unified_dashboard_v3_html.py`

**Step 1: Create skeleton with design tokens applied as CSS variables.** Top-level structure: navigation bar (4 tabs), main content area, footer.

**Step 2: Wire `render_track_c(data)` to entrypoint**

**Step 3: Generate, open in browser — empty but styled**

**Step 4: Commit**

```bash
git commit -am "feat(dashboard): Track C — base scaffold with design tokens"
```

---

### Task 3.3: Build Track C CAPTURE tab

**Step 1-5:** Reuse JSON, implement chart layouts using same Plotly traces but with new theme/typography. Smoke test, commit.

---

### Task 3.4: Build Track C BESS tab

(Same pattern.)

---

### Task 3.5: Build Track C FUTURES tab

(Same pattern.)

---

### Task 3.6: Build Track C ASSETS tab

**Step 1-5:** Fleet overview (potentially as a hero section with large numbers), card grid (different styling than Track A), drill-down. Same data, different presentation.

```bash
git commit -am "feat(dashboard): Track C — ASSETS tab complete"
```

---

### Task 3.7: Smoke-test Track C end-to-end

```bash
python3 generate_unified_dashboard.py --track C
open Resultat/rapporter/dashboard_unified_v3_20260502.html
```

Click through, fix issues, commit.

---

## Phase 4: Pipeline Integration (~1h)

### Task 4.1: Update `update_all.py` — add Bazefield as step 2

**Files:**
- Modify: `update_all.py`

**Step 1:** Insert step 2 after spotpriser, before ENTSO-E. Skip silently if `BAZEFIELD_API_KEY` not set.

```python
# Step 2: Bazefield park data
current_step += 1
if not BAZEFIELD_API_KEY or args.skip_bazefield:
    step(current_step, total_steps, "Bazefield park data (SKIPPED)")
else:
    step(current_step, total_steps, "Updating Bazefield park data")
    if run_script("bazefield_download.py", quiet=args.quiet):
        success_count += 1
        print("  Done!")
```

Bump `total_steps` from 11 to 12.

**Step 2: Test**

```bash
python3 update_all.py --skip-bazefield
```
Expected: step 2 shows SKIPPED, rest runs normally.

**Step 3: Commit**

```bash
git commit -am "feat(update_all): integrate Bazefield as step 2"
```

---

### Task 4.2: Update `update_all.py` — replace dashboard v1 step with unified

**Files:**
- Modify: `update_all.py`

**Step 1:** Replace step `[10/12] Generating HTML dashboard` (currently calls `generate_dashboard.py`) with:

```python
# Step 10: Unified dashboard (Track A + C)
current_step += 1
step(current_step, total_steps, "Generating Unified Dashboard (Track A + C)")
if run_script("generate_unified_dashboard.py", quiet=args.quiet):
    success_count += 1
    print("  Done!")
```

**Step 2:** Add deprecation warning to `generate_dashboard.py`:

```python
# generate_dashboard.py top:
import sys
print("⚠️  DEPRECATED: dashboard v1 will be removed. Use generate_unified_dashboard.py", file=sys.stderr)
```

**Step 3: Test**

```bash
python3 update_all.py --skip-bazefield
```
Expected: step 10 generates unified dashboard.

**Step 4: Commit**

```bash
git commit -am "feat(update_all): replace dashboard v1 with unified"
```

---

### Task 4.3: Add `--reports` flag to `update_all.py`

**Files:**
- Modify: `update_all.py`

**Step 1:** Add argparse flag, add conditional step 11.

```python
p.add_argument("--reports", action="store_true",
               help="Also regenerate park performance reports")
p.add_argument("--month", help="Month for park reports (YYYY-MM)")
```

```python
# Step 11: Park performance reports (conditional)
current_step += 1
if args.reports:
    step(current_step, total_steps, "Generating park performance reports")
    cmd = ["python3", "generate_performance_report.py", "--all"]
    if args.month:
        cmd += ["--month", args.month]
    if subprocess.run(cmd).returncode == 0:
        success_count += 1
        print("  Done!")
else:
    step(current_step, total_steps, "Park reports (SKIPPED — use --reports)")
```

**Step 2: Test both branches**

```bash
python3 update_all.py --skip-bazefield --skip-entsoe       # no reports
python3 update_all.py --reports --month 2026-04 --skip-bazefield --skip-entsoe
```

**Step 3: Commit**

```bash
git commit -am "feat(update_all): add --reports flag for park reports"
```

---

### Task 4.4: Update slash commands

**Files:**
- Modify: `.claude/commands/elpris-update-all.md`
- Create: `.claude/commands/elpris-dashboard.md`
- Create: `.claude/commands/elpris-reports.md`

**Step 1:** Update `elpris-update-all.md` to mention 12 steps and `--reports` flag.

**Step 2:** Create new commands:

```markdown
# elpris-dashboard.md
Generate the unified dashboard (Track A + Track C).

## Instructions
Run `python3 generate_unified_dashboard.py`

### Flags
- `--track A` — only Bloomberg-dark variant
- `--track C` — only fresh modern variant
- `--track both` — both (default)
```

```markdown
# elpris-reports.md
Generate per-park performance reports for the latest complete month.

## Instructions
Run `python3 generate_performance_report.py --all`

### Flags
- `--month YYYY-MM` — specific month
- `--park <key>` — single park
```

**Step 3: Commit**

```bash
git add .claude/commands/
git commit -m "docs(commands): add elpris-dashboard and elpris-reports skills"
```

---

## Phase 5: Documentation (~30min)

### Task 5.1: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

**Step 1:** Update the "Slash Commands" section, add `/elpris-dashboard` and `/elpris-reports`. Update "Datakatalog" to mention new `dashboard_unified_*.html` outputs. Add note in "Framtida utveckling" that v1 dashboard is deprecated.

**Step 2: Commit**

```bash
git commit -am "docs: update CLAUDE.md for unified dashboard"
```

---

### Task 5.2: Final integration test

**Step 1: Clean run**

```bash
python3 update_all.py --reports
```

**Step 2: Verify all artifacts exist**

```bash
ls -la Resultat/rapporter/dashboard_unified_*.html
ls -la Resultat/rapporter/dashboard_unified_v3_*.html
ls -la Resultat/rapporter/performance_*_2026-04.html
```

**Step 3: Open both unified HTMLs, click through every tab**

**Step 4: Commit any final fixes, then push to main**

```bash
git push origin main
```

---

## Definition of Done

- [ ] Both unified HTMLs (Track A + C) generate successfully
- [ ] All 4 tabs functional (CAPTURE / BESS / FUTURES / ASSETS)
- [ ] ASSETS tab: Fleet KPIs + Park Cards + Table + Drill-down + Filters all work
- [ ] `python3 update_all.py` produces both dashboards in <10 min
- [ ] `python3 update_all.py --reports` additionally produces 8 park reports
- [ ] `pytest tests/` passes
- [ ] Existing dashboards (v1, v2) still importable, v1 prints deprecation warning
- [ ] CLAUDE.md updated
- [ ] Pushed to main

## Out of scope (explicit YAGNI)

- Inverter-level data per park (requires SCADA)
- Weather correlation in drill-down
- Financial figures (SEK revenue) — could be added later
- Hosted version with auth — explicit phase 2 of project
- Mobile-responsive design (Track C only attempts this; Track A stays desktop)
