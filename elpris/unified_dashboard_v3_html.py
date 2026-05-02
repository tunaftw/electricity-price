"""Track C renderer — Nordic Editorial.

A fresh single-file HTML dashboard that consumes the same data dict as
Track A (via :mod:`elpris.unified_dashboard_data`) but wears a completely
different visual identity: light "warm paper" theme, serif display +
grotesque UI + mono numerals, single chartreuse accent, persistent dark
sidebar rail with section navigation.

Design tokens documented in ``docs/plans/2026-05-02-track-c-design-tokens.md``.

Public entry point:

    >>> from elpris.unified_dashboard_data import build_unified_data
    >>> from elpris.unified_dashboard_v3_html import render_track_c
    >>> html = render_track_c(build_unified_data())

The output is a self-contained HTML string (Plotly via CDN, fonts via
Google Fonts CDN, all other CSS/JS inlined).
"""
from __future__ import annotations

import json
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Top-level renderer
# ---------------------------------------------------------------------------

def render_track_c(data: Dict[str, Any]) -> str:
    """Render the Track C unified dashboard as a single HTML string.

    Parameters
    ----------
    data : dict
        Output of :func:`elpris.unified_dashboard_data.build_unified_data`.
        Must contain top-level keys ``market``, ``assets``, ``meta``,
        ``generated``.
    """
    # The frontend reads a single global ``DATA`` object whose root is the
    # market dict; ``assets`` and ``meta`` ride alongside (mirrors Track A's
    # _merge_data convention so the same JS can work either way).
    market = data.get("market", {}) or {}
    payload: Dict[str, Any] = dict(market)
    payload["assets"] = data.get("assets", {})
    payload["meta"] = data.get("meta", {})
    payload["generated"] = data.get("generated", "")

    data_json = json.dumps(payload, default=str, ensure_ascii=False)
    generated = data.get("generated", "")

    return _SHELL.format(
        data_json=data_json,
        generated=_html_escape(generated),
        css=_CSS,
        js=_JS,
    )


def _html_escape(s: str) -> str:
    """Defensive HTML escape for header text we splat into the shell."""
    if s is None:
        return ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


# ---------------------------------------------------------------------------
# CSS — design tokens + components
# ---------------------------------------------------------------------------

_CSS = r"""
/* ============================================================
   Track C — Nordic Editorial · design tokens
   ============================================================ */
:root {
  /* surfaces — warm paper */
  --surface-base:    #F7F5F0;
  --surface-raised:  #FFFFFF;
  --surface-sunken:  #EFEBE2;
  --surface-rail:    #1A1814;
  --surface-rail-2:  #2A2620;

  /* ink */
  --ink-1: #1A1814;
  --ink-2: #45413A;
  --ink-3: #6B6660;
  --ink-4: #9A958C;
  --ink-5: #C9C4B9;

  /* accent — electric chartreuse */
  --accent:        #C7F26A;
  --accent-deep:   #92B53D;
  --accent-glow:   rgba(199, 242, 106, 0.25);
  --accent-soft:   rgba(199, 242, 106, 0.12);

  /* semantic */
  --good:    #4F8A4D;
  --good-bg: #E5F0DF;
  --warn:    #B0832C;
  --warn-bg: #F5EBD2;
  --bad:     #B14E45;
  --bad-bg:  #F4DDD8;

  /* viz palette */
  --viz-1: #2E5C4D;
  --viz-2: #C16E40;
  --viz-3: #5B6BA8;
  --viz-4: #B14F75;
  --viz-5: #C9A53C;
  --viz-6: #6E5B85;
  --viz-7: #4A8C7B;
  --viz-8: #A85838;

  /* typography */
  --font-display: 'Newsreader', 'Charter', 'Iowan Old Style', Georgia, serif;
  --font-ui:      'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --font-mono:    'JetBrains Mono', 'SF Mono', ui-monospace, Menlo, monospace;

  --fs-xs:   11px;
  --fs-sm:   12.5px;
  --fs-md:   13.5px;
  --fs-lg:   15px;
  --fs-xl:   20px;
  --fs-2xl:  28px;
  --fs-3xl:  40px;
  --fs-4xl:  56px;

  --lh-tight:  1.15;
  --lh-snug:   1.35;
  --lh-normal: 1.55;

  /* spacing */
  --sp-1:  4px;
  --sp-2:  8px;
  --sp-3:  12px;
  --sp-4:  16px;
  --sp-5:  24px;
  --sp-6:  32px;
  --sp-7:  48px;
  --sp-8:  64px;

  /* radii */
  --radius-sm:  4px;
  --radius-md:  8px;
  --radius-lg:  12px;
  --radius-pill: 999px;

  /* shadows */
  --shadow-hair:  0 0 0 1px rgba(26, 24, 20, 0.06);
  --shadow-rest:  0 1px 2px rgba(26, 24, 20, 0.04), 0 0 0 1px rgba(26, 24, 20, 0.05);
  --shadow-hover: 0 4px 12px rgba(26, 24, 20, 0.08), 0 0 0 1px rgba(26, 24, 20, 0.06);
  --shadow-focus: 0 0 0 3px var(--accent-glow);

  /* motion */
  --ease:      cubic-bezier(0.4, 0, 0.2, 1);
  --ease-out:  cubic-bezier(0.16, 1, 0.3, 1);
  --dur-fast:  120ms;
  --dur-med:   220ms;
  --dur-slow:  400ms;

  /* layout */
  --rail-w: 64px;
}

/* ============================================================
   Reset + base
   ============================================================ */
*, *::before, *::after { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  background: var(--surface-base);
  color: var(--ink-2);
  font-family: var(--font-ui);
  font-size: var(--fs-md);
  line-height: var(--lh-normal);
  font-feature-settings: 'ss01', 'ss02', 'cv11';
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body { min-height: 100vh; }

a { color: var(--ink-1); text-decoration: underline; text-decoration-color: var(--ink-5); text-underline-offset: 2px; }
a:hover { text-decoration-color: var(--accent-deep); }

button {
  font-family: inherit;
  cursor: pointer;
  border: 0;
  background: transparent;
  color: inherit;
}
button:focus-visible { outline: none; box-shadow: var(--shadow-focus); }

select, input {
  font-family: inherit;
  font-size: inherit;
  background: var(--surface-raised);
  border: 1px solid var(--ink-5);
  color: var(--ink-1);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-md);
}
select:focus, input:focus { outline: none; border-color: var(--accent-deep); box-shadow: var(--shadow-focus); }

::selection { background: var(--accent); color: var(--ink-1); }

/* numerals — always tabular */
.num, .num * {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum', 'ss01';
}

/* small caps eyebrow */
.eyebrow {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: var(--ink-3);
}

/* ============================================================
   App shell — rail + content
   ============================================================ */
.app {
  display: grid;
  grid-template-columns: var(--rail-w) 1fr;
  min-height: 100vh;
}

.rail {
  background: var(--surface-rail);
  color: #E8E4DA;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--sp-4) 0 var(--sp-4);
  position: sticky;
  top: 0;
  height: 100vh;
}

.rail-mark {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
  font-style: italic;
  color: var(--accent);
  margin-bottom: var(--sp-7);
  letter-spacing: -0.02em;
  line-height: 1;
}

.rail-tabs {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  flex: 1;
}

.rail-tab {
  width: 44px;
  height: 44px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 500;
  font-style: italic;
  color: rgba(232, 228, 218, 0.55);
  border-radius: var(--radius-md);
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
  position: relative;
  cursor: pointer;
}
.rail-tab:hover { background: var(--surface-rail-2); color: #E8E4DA; }
.rail-tab[aria-selected="true"] {
  background: var(--surface-rail-2);
  color: var(--accent);
}
.rail-tab[aria-selected="true"]::after {
  content: '';
  position: absolute;
  right: -1px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  background: var(--accent);
  border-radius: 3px 0 0 3px;
}
.rail-tab-name {
  position: absolute;
  left: 100%;
  margin-left: var(--sp-3);
  background: var(--surface-rail-2);
  color: #E8E4DA;
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-style: normal;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transform: translateX(-4px);
  transition: opacity var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  z-index: 1000;
}
.rail-tab:hover .rail-tab-name { opacity: 1; transform: translateX(0); }

.rail-foot {
  font-family: var(--font-mono);
  font-size: 9px;
  color: rgba(232, 228, 218, 0.35);
  text-align: center;
  line-height: 1.4;
  margin-top: auto;
}

/* ============================================================
   Content column
   ============================================================ */
.content {
  padding: var(--sp-6) var(--sp-7) var(--sp-8);
  max-width: 1640px;
  width: 100%;
}

@media (max-width: 900px) {
  .content { padding: var(--sp-4) var(--sp-4) var(--sp-7); }
}

.page {
  animation: fade-up var(--dur-slow) var(--ease-out) both;
}
.page[hidden] { display: none; }

@keyframes fade-up {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* page header */
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--sp-5);
  flex-wrap: wrap;
  margin-bottom: var(--sp-6);
  padding-bottom: var(--sp-4);
  border-bottom: 1px solid var(--ink-5);
}
.page-head-left { min-width: 0; }
.page-eyebrow {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--ink-3);
  margin-bottom: var(--sp-2);
}
.page-title {
  font-family: var(--font-display);
  font-size: var(--fs-3xl);
  font-weight: 500;
  font-style: italic;
  color: var(--ink-1);
  line-height: var(--lh-tight);
  letter-spacing: -0.02em;
  margin: 0;
}
.page-sub {
  font-size: var(--fs-md);
  color: var(--ink-3);
  margin-top: var(--sp-2);
  max-width: 60ch;
}
.page-controls {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
  flex-wrap: wrap;
}

/* segmented control + pills */
.seg {
  display: inline-flex;
  background: var(--surface-sunken);
  padding: 3px;
  border-radius: var(--radius-pill);
  border: 1px solid transparent;
}
.seg button {
  font-size: var(--fs-xs);
  font-weight: 600;
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  color: var(--ink-3);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
}
.seg button:hover { color: var(--ink-1); }
.seg button[aria-pressed="true"] {
  background: var(--surface-raised);
  color: var(--ink-1);
  box-shadow: var(--shadow-rest);
}

.label-control {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--ink-3);
  text-transform: uppercase;
  letter-spacing: 0.10em;
}
.label-control select { padding: 5px 28px 5px 10px; font-size: var(--fs-sm); font-weight: 500; text-transform: none; letter-spacing: 0; color: var(--ink-1); }

/* card */
.card {
  background: var(--surface-raised);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-rest);
  padding: var(--sp-5);
  margin-bottom: var(--sp-5);
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--sp-4);
  margin-bottom: var(--sp-4);
  flex-wrap: wrap;
}
.card-title {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 500;
  color: var(--ink-1);
  line-height: var(--lh-snug);
  letter-spacing: -0.01em;
}
.card-sub {
  font-size: var(--fs-xs);
  color: var(--ink-3);
  margin-top: 3px;
}
.card-actions { display: flex; gap: var(--sp-2); align-items: center; flex-wrap: wrap; }

/* hero KPI strip */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 0;
  background: var(--surface-raised);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-rest);
  margin-bottom: var(--sp-5);
  overflow: hidden;
}
.kpi {
  padding: var(--sp-5) var(--sp-5);
  border-right: 1px solid var(--ink-5);
}
.kpi:last-child { border-right: 0; }
.kpi-label {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--ink-3);
  margin-bottom: var(--sp-3);
}
.kpi-value {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--fs-2xl);
  font-weight: 500;
  color: var(--ink-1);
  line-height: 1;
  letter-spacing: -0.02em;
}
.kpi-unit {
  font-family: var(--font-ui);
  font-size: var(--fs-md);
  font-weight: 500;
  color: var(--ink-3);
  margin-left: 4px;
}
.kpi-sub {
  margin-top: var(--sp-2);
  font-size: var(--fs-xs);
  color: var(--ink-3);
  line-height: var(--lh-snug);
}

/* status pills (vs budget) */
.pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--fs-xs);
  font-weight: 500;
  letter-spacing: 0;
  white-space: nowrap;
}
.pill.good { background: var(--good-bg); color: var(--good); }
.pill.warn { background: var(--warn-bg); color: var(--warn); }
.pill.bad  { background: var(--bad-bg);  color: var(--bad); }
.pill.neutral { background: var(--surface-sunken); color: var(--ink-3); }

/* chart container */
.chart {
  width: 100%;
  height: 360px;
  border-radius: var(--radius-md);
  overflow: hidden;
}
.chart-tall { height: 460px; }
.chart-short { height: 240px; }
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: var(--sp-5); }

/* tables — editorial */
table.editorial {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-sm);
}
table.editorial thead th {
  text-align: left;
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: var(--ink-3);
  padding: var(--sp-3) var(--sp-3);
  border-bottom: 1px solid var(--ink-5);
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
}
table.editorial thead th .arrow { color: var(--accent-deep); margin-left: 4px; opacity: 0; }
table.editorial thead th[aria-sort="ascending"] .arrow,
table.editorial thead th[aria-sort="descending"] .arrow { opacity: 1; }
table.editorial thead th:hover { color: var(--ink-1); }
table.editorial thead th.num { text-align: right; }
table.editorial tbody td {
  padding: var(--sp-3);
  border-bottom: 1px solid var(--ink-5);
  color: var(--ink-1);
}
table.editorial tbody td.num {
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--ink-1);
}
table.editorial tbody tr {
  transition: background var(--dur-fast) var(--ease);
}
table.editorial tbody tr:hover { background: var(--surface-sunken); cursor: pointer; }
table.editorial tbody tr:last-child td { border-bottom: 0; }

/* park card grid */
.park-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--sp-4);
}
.park-tile {
  background: var(--surface-raised);
  border-radius: var(--radius-lg);
  padding: var(--sp-5);
  box-shadow: var(--shadow-rest);
  cursor: pointer;
  transition: box-shadow var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease);
  position: relative;
  overflow: hidden;
}
.park-tile:hover { box-shadow: var(--shadow-hover); transform: translateY(-1px); }
.park-tile::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--ink-5);
}
.park-tile.good::before { background: var(--good); }
.park-tile.warn::before { background: var(--warn); }
.park-tile.bad::before  { background: var(--bad); }
.park-tile-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: var(--sp-4);
}
.park-tile-name {
  font-family: var(--font-display);
  font-size: var(--fs-xl);
  font-weight: 500;
  font-style: italic;
  color: var(--ink-1);
  letter-spacing: -0.01em;
  line-height: var(--lh-tight);
}
.park-tile-zone {
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  font-weight: 500;
  color: var(--ink-3);
  background: var(--surface-sunken);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  letter-spacing: 0.06em;
}
.park-tile-stat {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin: 6px 0;
}
.park-tile-stat-k {
  font-size: var(--fs-xs);
  color: var(--ink-3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}
.park-tile-stat-v {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--fs-md);
  color: var(--ink-1);
  font-weight: 500;
}
.park-tile-spark {
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px dashed var(--ink-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}
.park-tile-spark svg { display: block; }

/* park chip filter (Comparison table) */
.park-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: var(--sp-3) 0 var(--sp-4) 0;
  padding-bottom: var(--sp-3);
  border-bottom: 1px dashed var(--ink-5);
}
.park-chips-label {
  font-size: var(--fs-xs);
  color: var(--ink-3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  margin-right: 4px;
}
.park-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--ink-5);
  background: transparent;
  font-family: var(--font-sans);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--ink-3);
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease);
}
.park-chip:hover { border-color: var(--accent-deep); color: var(--ink-1); }
.park-chip[aria-pressed="true"] {
  background: var(--accent);
  color: var(--ink-1);
  border-color: var(--accent-deep);
}
.park-chip-reset {
  margin-left: auto;
  padding: 5px 12px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--ink-5);
  background: var(--surface-sunken);
  font-family: var(--font-sans);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--ink-2);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  cursor: pointer;
}
.park-chip-reset:hover { color: var(--ink-1); border-color: var(--accent-deep); }

/* drilldown */
.crumb {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-5);
  font-size: var(--fs-xs);
  color: var(--ink-3);
  text-transform: uppercase;
  letter-spacing: 0.10em;
  font-weight: 600;
}
.crumb a {
  color: var(--ink-1);
  text-decoration: none;
  padding: 6px 12px;
  border-radius: var(--radius-pill);
  background: var(--accent);
  font-weight: 600;
  letter-spacing: 0.06em;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: background var(--dur-fast) var(--ease);
}
.crumb a:hover { background: var(--accent-deep); color: var(--ink-1); }
.crumb-sep { color: var(--ink-4); }

.drill-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--sp-5);
  margin-bottom: var(--sp-6);
  padding-bottom: var(--sp-4);
  border-bottom: 1px solid var(--ink-5);
  flex-wrap: wrap;
}
.drill-name {
  font-family: var(--font-display);
  font-size: var(--fs-4xl);
  font-style: italic;
  font-weight: 500;
  letter-spacing: -0.03em;
  color: var(--ink-1);
  line-height: 1;
  margin: 0;
}
.drill-meta {
  font-size: var(--fs-md);
  color: var(--ink-3);
  margin-top: var(--sp-3);
  display: flex;
  gap: var(--sp-4);
  flex-wrap: wrap;
}

/* best/worst day mini-tables */
.bw-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--sp-5);
}
.bw-title {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  margin-bottom: var(--sp-3);
}
.bw-title.good { color: var(--good); }
.bw-title.bad  { color: var(--bad); }

/* footer */
.app-foot {
  margin-top: var(--sp-7);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--ink-5);
  font-size: var(--fs-xs);
  color: var(--ink-4);
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--sp-3);
}
.app-foot .num { font-family: var(--font-mono); }

/* note for empty states */
.empty-note {
  padding: var(--sp-6);
  text-align: center;
  color: var(--ink-3);
  font-style: italic;
}

/* utility */
.hide { display: none !important; }
.flex { display: flex; }
.flex-grow { flex: 1; }
.gap-2 { gap: var(--sp-2); }
.gap-3 { gap: var(--sp-3); }
.gap-4 { gap: var(--sp-4); }
.muted { color: var(--ink-3); }
.right { text-align: right; }

/* color legend */
.legend {
  display: flex;
  gap: var(--sp-4);
  font-size: var(--fs-xs);
  color: var(--ink-3);
  flex-wrap: wrap;
}
.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: 1px;
}

/* invest card */
.invest-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--sp-4);
  align-items: center;
  padding: var(--sp-3) 0;
  border-bottom: 1px dashed var(--ink-5);
}
.invest-row:last-child { border-bottom: 0; }
.invest-row label { font-size: var(--fs-xs); color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }
.invest-row input { width: 130px; text-align: right; font-family: var(--font-mono); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
""".strip()


# ---------------------------------------------------------------------------
# JavaScript — all rendering logic
# ---------------------------------------------------------------------------

_JS = r"""
'use strict';

// ============================================================
//  Defensive helpers
// ============================================================
function htmlEsc(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, function(c) {
        return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c];
    });
}
function fmtNum(v, d) {
    if (v === null || v === undefined || v === '' || isNaN(v)) return '–';
    var n = Number(v);
    return n.toLocaleString('sv-SE', {
        minimumFractionDigits: d == null ? 0 : d,
        maximumFractionDigits: d == null ? 0 : d,
    }).replace(/ /g, ' ');
}
function fmtPct(v, d) {
    if (v === null || v === undefined || isNaN(v)) return '–';
    var sign = v >= 0 ? '+' : '';
    return sign + Number(v).toFixed(d == null ? 1 : d) + '%';
}
function vsClass(pct) {
    if (pct === null || pct === undefined || isNaN(pct)) return 'neutral';
    if (pct >= 5) return 'good';
    if (pct <= -5) return 'bad';
    return 'warn';
}
function el(id) { return document.getElementById(id); }

// ============================================================
//  Plotly editorial theme
// ============================================================
var PLOTLY_BASE = {
    paper_bgcolor: '#FFFFFF',
    plot_bgcolor: '#FFFFFF',
    font: {
        family: "'Geist', -apple-system, system-ui, sans-serif",
        size: 12,
        color: '#45413A'
    },
    margin: { t: 24, b: 56, l: 64, r: 24 },
    xaxis: {
        gridcolor: 'rgba(201, 196, 185, 0.45)',
        linecolor: 'rgba(201, 196, 185, 0.8)',
        tickcolor: 'rgba(201, 196, 185, 0.8)',
        zeroline: false,
        tickfont: { family: "'JetBrains Mono', ui-monospace, monospace", size: 11, color: '#6B6660' },
        title: { font: { family: "'Geist', sans-serif", size: 11, color: '#6B6660' } },
    },
    yaxis: {
        gridcolor: 'rgba(201, 196, 185, 0.35)',
        linecolor: 'rgba(201, 196, 185, 0.0)',
        tickcolor: 'rgba(201, 196, 185, 0.0)',
        zeroline: true,
        zerolinecolor: 'rgba(26, 24, 20, 0.10)',
        tickfont: { family: "'JetBrains Mono', ui-monospace, monospace", size: 11, color: '#6B6660' },
        title: { font: { family: "'Geist', sans-serif", size: 11, color: '#6B6660' } },
    },
    legend: {
        orientation: 'h',
        x: 0,
        y: -0.18,
        font: { family: "'Geist', sans-serif", size: 11, color: '#45413A' },
    },
    hoverlabel: {
        bgcolor: '#FFFFFF',
        bordercolor: '#C9C4B9',
        font: { family: "'JetBrains Mono', monospace", size: 11, color: '#1A1814' },
        align: 'left',
    },
    colorway: ['#2E5C4D', '#C16E40', '#5B6BA8', '#B14F75', '#C9A53C', '#6E5B85', '#4A8C7B', '#A85838'],
};
var PLOTLY_CFG = { responsive: true, displayModeBar: false };

function makeLayout(extra) {
    var copy = JSON.parse(JSON.stringify(PLOTLY_BASE));
    return Object.assign(copy, extra || {});
}

// ============================================================
//  Tab navigation
// ============================================================
var TABS = ['capture', 'bess', 'futures', 'assets'];
var TAB_TITLES = {
    capture: { eyebrow: 'Market', title: 'Capture Prices', sub: 'Solar-weighted price realisation across SE1–SE4 zones, profiles and time horizons.' },
    bess:    { eyebrow: 'Storage', title: 'Battery Economics', sub: 'Arbitrage revenue, sol-plus-storage capture and ancillary services revenue across battery durations.' },
    futures: { eyebrow: 'Forward', title: 'Forward Curve', sub: 'Nasdaq settlement prices for SYS baseload and zonal EPADs, with realised spot for delivered contracts.' },
    assets:  { eyebrow: 'Fleet',   title: 'Asset Performance', sub: 'Per-park energy, yield and budget variance across the SveaSolar utility-scale fleet.' },
};

function switchTab(name) {
    if (TABS.indexOf(name) === -1) return;
    document.querySelectorAll('.rail-tab').forEach(function(t) {
        t.setAttribute('aria-selected', t.dataset.tab === name ? 'true' : 'false');
    });
    document.querySelectorAll('.page').forEach(function(p) { p.hidden = true; });
    var page = el('page-' + name);
    if (page) {
        page.hidden = false;
        // restart fade-up animation
        page.style.animation = 'none';
        // eslint-disable-next-line no-unused-expressions
        page.offsetHeight;
        page.style.animation = '';
    }
    if (location.hash !== '#' + name) {
        history.replaceState(null, '', '#' + name);
    }
    if (name === 'capture') renderCapture();
    if (name === 'bess')    renderBess();
    if (name === 'futures') renderFutures();
    if (name === 'assets')  renderAssets();
}

// ============================================================
//  CAPTURE TAB
// ============================================================
var CAPTURE_STATE = {
    zone: null,
    period: 'monthly',     // 'yearly' | 'monthly' | 'daily'
    profiles: ['baseload', 'sol_syd'],
};
var CAPTURE_PROFILE_GROUPS = [
    { label: 'Reference', keys: ['baseload'] },
    { label: 'Solar PV',  keys: ['sol_syd', 'sol_ov', 'sol_tracker'] },
    { label: 'Wind',      keys: ['wind'] },
    { label: 'Hydro',     keys: ['hydro_water_reservoir'] },
    { label: 'Nuclear',   keys: ['nuclear'] },
];

function renderCapture() {
    var zones = (DATA.zones || []);
    if (!zones.length) {
        el('capture-content').innerHTML = '<div class="empty-note">No spot price data available.</div>';
        return;
    }
    if (!CAPTURE_STATE.zone || zones.indexOf(CAPTURE_STATE.zone) === -1) {
        CAPTURE_STATE.zone = zones[0];
    }
    // Build controls
    var zoneOpts = zones.map(function(z) {
        return '<button type="button" data-zone="' + htmlEsc(z) + '" aria-pressed="' + (z === CAPTURE_STATE.zone) + '">' + htmlEsc(z) + '</button>';
    }).join('');
    var periodOpts = ['yearly', 'monthly', 'daily'].map(function(p) {
        return '<button type="button" data-period="' + p + '" aria-pressed="' + (p === CAPTURE_STATE.period) + '">' + p + '</button>';
    }).join('');

    el('capture-zones').innerHTML = zoneOpts;
    el('capture-period').innerHTML = periodOpts;

    el('capture-zones').querySelectorAll('button').forEach(function(b) {
        b.onclick = function() { CAPTURE_STATE.zone = b.dataset.zone; renderCapture(); };
    });
    el('capture-period').querySelectorAll('button').forEach(function(b) {
        b.onclick = function() { CAPTURE_STATE.period = b.dataset.period; renderCapture(); };
    });

    // Build profile checkboxes by group
    var availableProfiles = Object.keys((DATA.data && DATA.data[CAPTURE_STATE.zone]) || {});
    var groupsHtml = CAPTURE_PROFILE_GROUPS.map(function(g) {
        var present = g.keys.filter(function(k) { return availableProfiles.indexOf(k) !== -1; });
        if (!present.length) return '';
        var btns = present.map(function(k) {
            var label = (DATA.profiles && DATA.profiles[k]) || k;
            var sel = CAPTURE_STATE.profiles.indexOf(k) !== -1;
            var color = (DATA.colors && DATA.colors[k]) || '#999';
            return '<button type="button" class="profile-chip" data-key="' + htmlEsc(k) + '" aria-pressed="' + sel + '" ' +
                'style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:999px;border:1px solid var(--ink-5);background:' + (sel ? 'var(--surface-sunken)' : 'transparent') + ';font-size:var(--fs-xs);font-weight:600;color:var(--ink-1);letter-spacing:0.04em;margin:0 4px 4px 0">' +
                '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + htmlEsc(color) + '"></span>' +
                htmlEsc(label) + '</button>';
        }).join('');
        return '<div style="margin-bottom:8px"><span class="eyebrow" style="margin-right:10px">' + htmlEsc(g.label) + '</span>' + btns + '</div>';
    }).join('');
    el('capture-profiles').innerHTML = groupsHtml || '<span class="muted">No profiles available.</span>';
    el('capture-profiles').querySelectorAll('.profile-chip').forEach(function(b) {
        b.onclick = function() {
            var k = b.dataset.key;
            var idx = CAPTURE_STATE.profiles.indexOf(k);
            if (idx === -1) CAPTURE_STATE.profiles.push(k);
            else CAPTURE_STATE.profiles.splice(idx, 1);
            renderCapture();
        };
    });

    // KPI strip — latest baseload + each chosen profile latest capture
    renderCaptureKPIs();
    renderCaptureChart();
    renderCaptureRatioChart();
    renderHeatmap();
}

function renderCaptureKPIs() {
    var zone = CAPTURE_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var latest = function(list) { return list && list.length ? list[list.length - 1] : null; };
    var monthlyBase = latest(z.baseload && z.baseload.monthly);
    var monthlyPrev = z.baseload && z.baseload.monthly && z.baseload.monthly.length >= 2 ? z.baseload.monthly[z.baseload.monthly.length - 2] : null;

    var monthLabel = monthlyBase ? (monthlyBase.year + '-' + String(monthlyBase.month).padStart(2, '0')) : '—';
    var change = (monthlyBase && monthlyPrev && monthlyPrev.baseload) ? (100 * (monthlyBase.baseload - monthlyPrev.baseload) / monthlyPrev.baseload) : null;

    var tiles = [];
    tiles.push(kpiTile('Latest baseload · ' + zone, monthlyBase ? fmtNum(monthlyBase.baseload, 1) : '–', 'EUR/MWh', monthLabel + (change != null ? ' · ' + fmtPct(change) + ' MoM' : '')));

    // Capture for each chosen profile (latest monthly)
    CAPTURE_STATE.profiles.filter(function(k) { return k !== 'baseload'; }).slice(0, 3).forEach(function(k) {
        var p = z[k];
        if (!p || !p.monthly) return;
        var rec = latest(p.monthly);
        if (!rec) return;
        var label = (DATA.profiles && DATA.profiles[k]) || k;
        var ratio = rec.ratio != null ? fmtPct((rec.ratio - 1) * 100, 1) + ' vs baseload' : '';
        tiles.push(kpiTile(label, fmtNum(rec.capture, 1), 'EUR/MWh', ratio));
    });

    // YTD baseload average
    var ytdBase = null;
    if (z.baseload && z.baseload.monthly && z.baseload.monthly.length) {
        var lastY = z.baseload.monthly[z.baseload.monthly.length - 1].year;
        var ytd = z.baseload.monthly.filter(function(m) { return m.year === lastY; });
        if (ytd.length) {
            var sum = ytd.reduce(function(a, b) { return a + (b.baseload || 0); }, 0);
            ytdBase = sum / ytd.length;
        }
    }
    tiles.push(kpiTile('YTD avg baseload', ytdBase != null ? fmtNum(ytdBase, 1) : '–', 'EUR/MWh', monthlyBase ? monthlyBase.year + ' to date' : ''));

    el('capture-kpis').innerHTML = tiles.join('');
}

function kpiTile(label, value, unit, sub) {
    return '<div class="kpi">' +
        '<div class="kpi-label">' + htmlEsc(label) + '</div>' +
        '<div><span class="kpi-value">' + htmlEsc(value) + '</span>' + (unit ? '<span class="kpi-unit">' + htmlEsc(unit) + '</span>' : '') + '</div>' +
        (sub ? '<div class="kpi-sub">' + htmlEsc(sub) + '</div>' : '') +
        '</div>';
}

function renderCaptureChart() {
    var zone = CAPTURE_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var period = CAPTURE_STATE.period;
    var traces = [];
    var unit = 'EUR/MWh';

    CAPTURE_STATE.profiles.forEach(function(k) {
        var p = z[k];
        if (!p || !p[period]) return;
        var rows = p[period];
        var xs = rows.map(function(r) {
            if (period === 'yearly')  return String(r.year);
            if (period === 'monthly') return r.year + '-' + String(r.month).padStart(2, '0');
            return r.date;
        });
        var ys = rows.map(function(r) { return k === 'baseload' ? r.baseload : (r.capture != null ? r.capture : null); });
        var meta = (DATA.profile_meta && DATA.profile_meta[k]) || {};
        var color = (DATA.colors && DATA.colors[k]) || null;
        var label = (DATA.profiles && DATA.profiles[k]) || k;
        traces.push({
            x: xs,
            y: ys,
            name: label,
            mode: period === 'daily' ? 'lines' : 'lines+markers',
            type: 'scatter',
            line: { width: k === 'baseload' ? 2.5 : 1.8, color: color, shape: 'spline' },
            marker: { size: period === 'daily' ? 0 : 5, color: color },
            hovertemplate: '%{x}<br>' + htmlEsc(label) + ': <b>%{y:.1f}</b> ' + (meta.unit || unit) + '<extra></extra>',
        });
    });

    if (!traces.length) {
        Plotly.purge('capture-main-chart');
        el('capture-main-chart').innerHTML = '<div class="empty-note">Select at least one profile.</div>';
        return;
    }

    Plotly.react('capture-main-chart', traces, makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EUR / MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 70, l: 64, r: 24 },
    }), PLOTLY_CFG);
}

function renderCaptureRatioChart() {
    var zone = CAPTURE_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var period = CAPTURE_STATE.period;
    var traces = [];
    CAPTURE_STATE.profiles.filter(function(k) { return k !== 'baseload'; }).forEach(function(k) {
        var p = z[k];
        if (!p || !p[period]) return;
        var rows = p[period];
        var xs = rows.map(function(r) {
            if (period === 'yearly')  return String(r.year);
            if (period === 'monthly') return r.year + '-' + String(r.month).padStart(2, '0');
            return r.date;
        });
        var ys = rows.map(function(r) { return r.ratio != null ? r.ratio * 100 : null; });
        var color = (DATA.colors && DATA.colors[k]) || null;
        var label = (DATA.profiles && DATA.profiles[k]) || k;
        traces.push({
            x: xs, y: ys, name: label, mode: 'lines+markers', type: 'scatter',
            line: { width: 1.8, color: color, shape: 'spline' },
            marker: { size: period === 'daily' ? 0 : 4, color: color },
            hovertemplate: '%{x}<br>' + htmlEsc(label) + ': <b>%{y:.1f}%</b> of baseload<extra></extra>',
        });
    });
    if (!traces.length) {
        Plotly.purge('capture-ratio-chart');
        el('capture-ratio-chart').innerHTML = '<div class="empty-note">No capture profiles selected.</div>';
        return;
    }
    // Add 100% reference line via shapes
    var shape = { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 100, y1: 100, line: { color: '#9A958C', dash: 'dot', width: 1 } };
    Plotly.react('capture-ratio-chart', traces, makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'Capture / Baseload (%)', font: PLOTLY_BASE.yaxis.title.font }, ticksuffix: '%' }),
        shapes: [shape],
        margin: { t: 12, b: 70, l: 64, r: 24 },
    }), PLOTLY_CFG);
}

function renderHeatmap() {
    var zone = CAPTURE_STATE.zone;
    var hm = (DATA.heatmap && DATA.heatmap[zone] && DATA.heatmap[zone].all) || null;
    if (!hm || !hm.length) {
        Plotly.purge('capture-heatmap');
        el('capture-heatmap').innerHTML = '<div class="empty-note">No heatmap data.</div>';
        return;
    }
    // hm is a 12 x 24 matrix: hm[month-1][hour] = mean EUR/MWh, or null.
    var hours = []; for (var h = 0; h < 24; h++) hours.push(h);
    var monthLabels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var matrix = hm; // already a list of rows
    Plotly.react('capture-heatmap', [{
        type: 'heatmap',
        x: hours,
        y: monthLabels,
        z: matrix,
        colorscale: [
            [0,    '#F7F5F0'],
            [0.25, '#E5DCC5'],
            [0.5,  '#C9A53C'],
            [0.75, '#A85838'],
            [1,    '#5B2D24'],
        ],
        colorbar: {
            tickfont: { family: "'JetBrains Mono', monospace", size: 10, color: '#6B6660' },
            title: { text: 'EUR/MWh', font: { size: 10, color: '#6B6660' } },
            outlinewidth: 0,
            thickness: 12,
            len: 0.85,
        },
        hovertemplate: 'Month: %{y}<br>Hour: %{x}:00<br>Avg: <b>%{z:.1f}</b> EUR/MWh<extra></extra>',
    }], makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { autorange: 'reversed', gridcolor: 'transparent' }),
        xaxis: Object.assign({}, PLOTLY_BASE.xaxis, { dtick: 2, gridcolor: 'transparent', title: { text: 'Hour of day', font: PLOTLY_BASE.xaxis.title.font } }),
        margin: { t: 12, b: 56, l: 64, r: 90 },
    }), PLOTLY_CFG);
}


// ============================================================
//  BESS TAB
// ============================================================
var BESS_STATE = {
    zone: null,
    duration: '2h',
    invest: { capex: 280000, opex: 8000, lifetime: 15, discount: 6 },
};

function renderBess() {
    var zones = (DATA.zones || []);
    if (!zones.length) {
        el('bess-content').innerHTML = '<div class="empty-note">No spot price data available.</div>';
        return;
    }
    if (!BESS_STATE.zone || zones.indexOf(BESS_STATE.zone) === -1) BESS_STATE.zone = zones[0];

    var zoneOpts = zones.map(function(z) {
        return '<button type="button" data-zone="' + htmlEsc(z) + '" aria-pressed="' + (z === BESS_STATE.zone) + '">' + htmlEsc(z) + '</button>';
    }).join('');
    var durOpts = ['1h','2h','3h','4h'].map(function(d) {
        return '<button type="button" data-dur="' + d + '" aria-pressed="' + (d === BESS_STATE.duration) + '">' + d + '</button>';
    }).join('');

    el('bess-zones').innerHTML = zoneOpts;
    el('bess-durations').innerHTML = durOpts;
    el('bess-zones').querySelectorAll('button').forEach(function(b) {
        b.onclick = function() { BESS_STATE.zone = b.dataset.zone; renderBess(); };
    });
    el('bess-durations').querySelectorAll('button').forEach(function(b) {
        b.onclick = function() { BESS_STATE.duration = b.dataset.dur; renderBess(); };
    });

    renderBessKPIs();
    renderArbitrageChart();
    renderSolBessChart();
    renderAncillaryChart();
    renderInvestPanel();
}

function lastYearly(rows) {
    if (!rows || !rows.length) return null;
    return rows[rows.length - 1];
}

function renderBessKPIs() {
    var zone = BESS_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var arbKey = 'arb_' + BESS_STATE.duration;
    var sbKey = 'sol_bess_' + BESS_STATE.duration;
    var arbY = lastYearly(z[arbKey] && z[arbKey].yearly);
    var sbY  = lastYearly(z[sbKey]  && z[sbKey].yearly);
    var solOnly = lastYearly(z['sol_only'] && z['sol_only'].yearly);

    var tiles = [];
    tiles.push(kpiTile('Arbitrage revenue ' + BESS_STATE.duration, arbY ? fmtNum(arbY.capture || arbY.baseload, 0) : '–', 'EUR/MW·yr', zone + (arbY ? ' · ' + arbY.year : '')));
    tiles.push(kpiTile('Sol+BESS capture ' + BESS_STATE.duration, sbY ? fmtNum(sbY.capture, 1) : '–', 'EUR/MWh', solOnly ? 'Sol-only: ' + fmtNum(solOnly.capture, 1) : ''));
    var uplift = (sbY && solOnly && solOnly.capture) ? (sbY.capture - solOnly.capture) : null;
    tiles.push(kpiTile('Storage uplift', uplift != null ? '+' + fmtNum(uplift, 1) : '–', 'EUR/MWh', 'vs sol-only capture'));

    // FCR-N latest yearly
    var fcr = lastYearly(z['anc_fcr_n'] && z['anc_fcr_n'].yearly);
    tiles.push(kpiTile('FCR-N price', fcr ? fmtNum(fcr.baseload || fcr.capture, 0) : '–', 'EUR/MW', fcr ? 'Yearly avg ' + fcr.year : ''));

    el('bess-kpis').innerHTML = tiles.join('');
}

function renderArbitrageChart() {
    var zone = BESS_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var traces = [];
    ['arb_1h', 'arb_2h', 'arb_3h', 'arb_4h'].forEach(function(k) {
        var p = z[k];
        if (!p || !p.monthly) return;
        var color = (DATA.colors && DATA.colors[k]) || null;
        var label = (DATA.profiles && DATA.profiles[k]) || k;
        var xs = p.monthly.map(function(r) { return r.year + '-' + String(r.month).padStart(2, '0'); });
        var ys = p.monthly.map(function(r) { return r.capture != null ? r.capture : r.baseload; });
        traces.push({
            x: xs, y: ys, name: label, type: 'bar',
            marker: { color: color },
            hovertemplate: '%{x}<br>' + htmlEsc(label) + ': <b>%{y:,.0f}</b> EUR/MW<extra></extra>',
        });
    });
    if (!traces.length) {
        Plotly.purge('bess-arb-chart');
        el('bess-arb-chart').innerHTML = '<div class="empty-note">No BESS data available.</div>';
        return;
    }
    Plotly.react('bess-arb-chart', traces, makeLayout({
        barmode: 'group',
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EUR / MW · month', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 70, l: 76, r: 24 },
    }), PLOTLY_CFG);
}

function renderSolBessChart() {
    var zone = BESS_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var traces = [];
    var solOnly = z['sol_only'];
    if (solOnly && solOnly.monthly) {
        var xs = solOnly.monthly.map(function(r) { return r.year + '-' + String(r.month).padStart(2, '0'); });
        var ys = solOnly.monthly.map(function(r) { return r.capture; });
        traces.push({
            x: xs, y: ys, name: 'Sol only', type: 'scatter', mode: 'lines',
            line: { color: '#9A958C', dash: 'dash', width: 2 },
            hovertemplate: '%{x}<br>Sol only: <b>%{y:.1f}</b> EUR/MWh<extra></extra>',
        });
    }
    ['sol_bess_1h', 'sol_bess_2h', 'sol_bess_3h', 'sol_bess_4h'].forEach(function(k) {
        var p = z[k];
        if (!p || !p.monthly) return;
        var color = (DATA.colors && DATA.colors[k]) || null;
        var label = (DATA.profiles && DATA.profiles[k]) || k;
        var xs = p.monthly.map(function(r) { return r.year + '-' + String(r.month).padStart(2, '0'); });
        var ys = p.monthly.map(function(r) { return r.capture; });
        traces.push({
            x: xs, y: ys, name: label, type: 'scatter', mode: 'lines',
            line: { color: color, width: 2, shape: 'spline' },
            hovertemplate: '%{x}<br>' + htmlEsc(label) + ': <b>%{y:.1f}</b> EUR/MWh<extra></extra>',
        });
    });
    if (!traces.length) {
        Plotly.purge('bess-solbess-chart');
        el('bess-solbess-chart').innerHTML = '<div class="empty-note">No sol+BESS data.</div>';
        return;
    }
    Plotly.react('bess-solbess-chart', traces, makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'Capture EUR/MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 70, l: 64, r: 24 },
    }), PLOTLY_CFG);
}

function renderAncillaryChart() {
    var zone = BESS_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var traces = [];
    ['anc_fcr_n','anc_fcr_d_up','anc_fcr_d_down','anc_afrr_up','anc_afrr_down','anc_mfrr_cm_up','anc_mfrr_cm_down'].forEach(function(k) {
        var p = z[k];
        if (!p || !p.monthly) return;
        var color = (DATA.colors && DATA.colors[k]) || null;
        var label = (DATA.profiles && DATA.profiles[k]) || k;
        var xs = p.monthly.map(function(r) { return r.year + '-' + String(r.month).padStart(2, '0'); });
        var ys = p.monthly.map(function(r) { return r.baseload != null ? r.baseload : r.capture; });
        traces.push({
            x: xs, y: ys, name: label, type: 'scatter', mode: 'lines',
            line: { color: color, width: 1.6, shape: 'spline' },
            hovertemplate: '%{x}<br>' + htmlEsc(label) + ': <b>%{y:,.0f}</b> EUR/MW<extra></extra>',
        });
    });
    if (!traces.length) {
        Plotly.purge('bess-anc-chart');
        el('bess-anc-chart').innerHTML = '<div class="empty-note">No ancillary data for ' + htmlEsc(zone) + '.</div>';
        return;
    }
    Plotly.react('bess-anc-chart', traces, makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EUR / MW · month', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 70, l: 76, r: 24 },
    }), PLOTLY_CFG);
}

function renderInvestPanel() {
    var s = BESS_STATE.invest;
    el('inv-capex').value = s.capex;
    el('inv-opex').value  = s.opex;
    el('inv-life').value  = s.lifetime;
    el('inv-disc').value  = s.discount;

    function bind(id, key, parse) {
        var elx = el(id);
        if (!elx.dataset.bound) {
            elx.addEventListener('input', function() {
                BESS_STATE.invest[key] = Math.max(0, parse(elx.value) || 0);
                computeInvest();
            });
            elx.dataset.bound = '1';
        }
    }
    bind('inv-capex', 'capex', parseFloat);
    bind('inv-opex',  'opex',  parseFloat);
    bind('inv-life',  'lifetime', parseInt);
    bind('inv-disc',  'discount', parseFloat);
    computeInvest();
}

function computeInvest() {
    var s = BESS_STATE.invest;
    var zone = BESS_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var arbKey = 'arb_' + BESS_STATE.duration;
    // Latest yearly arbitrage revenue per MW
    var arbY = lastYearly(z[arbKey] && z[arbKey].yearly);
    var revPerMw = arbY ? (arbY.capture != null ? arbY.capture : arbY.baseload) : null;

    // Battery sized 1 MW power × Nh capacity. Capex input is EUR/MWh storage.
    var dur = parseInt(BESS_STATE.duration) || 2;
    var capacity = dur; // MWh
    var capex = Math.max(0, s.capex || 0) * capacity;
    var opex  = Math.max(0, s.opex  || 0); // per MW
    var disc  = Math.max(0, s.discount || 0) / 100;
    var n     = Math.max(0, s.lifetime || 0);

    var html = '';
    if (revPerMw == null) {
        html = '<div class="empty-note">No arbitrage revenue data available for ' + htmlEsc(zone) + ' to compute economics.</div>';
        el('invest-output').innerHTML = html;
        return;
    }

    var annualNet = revPerMw - opex;
    // NPV of annualNet at discount over n years
    var npv = -capex;
    for (var t = 1; t <= n; t++) {
        npv += annualNet / Math.pow(1 + disc, t);
    }
    // Payback (undiscounted, simple)
    var payback = annualNet > 0 ? (capex / annualNet) : null;
    // Levelised cost ish — capex annuitised over life ÷ revenue
    var crf = disc > 0 ? (disc * Math.pow(1+disc, n)) / (Math.pow(1+disc, n) - 1) : 1 / n;
    var annuitised = capex * crf + opex;

    html =
        '<div class="invest-row"><label>Annual gross revenue</label><span class="num">' + fmtNum(revPerMw, 0) + ' EUR</span></div>' +
        '<div class="invest-row"><label>Annual net (after OPEX)</label><span class="num">' + fmtNum(annualNet, 0) + ' EUR</span></div>' +
        '<div class="invest-row"><label>Total CAPEX (' + dur + 'h × 1 MW)</label><span class="num">' + fmtNum(capex, 0) + ' EUR</span></div>' +
        '<div class="invest-row"><label>Annuitised cost</label><span class="num">' + fmtNum(annuitised, 0) + ' EUR/yr</span></div>' +
        '<div class="invest-row"><label>Simple payback</label><span class="num">' + (payback != null ? fmtNum(payback, 1) + ' yr' : '–') + '</span></div>' +
        '<div class="invest-row"><label>NPV (' + n + 'yr · ' + s.discount + '%)</label><span class="num" style="color:' + (npv >= 0 ? 'var(--good)' : 'var(--bad)') + '">' + fmtNum(npv, 0) + ' EUR</span></div>';
    el('invest-output').innerHTML = html;
}


// ============================================================
//  FUTURES TAB
// ============================================================
var FUTURES_STATE = { zone: 'SE3' };

function renderFutures() {
    var fwd = DATA.forward;
    if (!fwd) {
        el('futures-content').innerHTML = '<div class="empty-note">No forward curve data loaded. Run <span class="num">nasdaq_download.py</span> to fetch settlement prices.</div>';
        return;
    }
    var zones = ['SE1', 'SE2', 'SE3', 'SE4'];
    var zoneOpts = zones.map(function(z) {
        return '<button type="button" data-zone="' + z + '" aria-pressed="' + (z === FUTURES_STATE.zone) + '">' + z + '</button>';
    }).join('');
    el('futures-zones').innerHTML = zoneOpts;
    el('futures-zones').querySelectorAll('button').forEach(function(b) {
        b.onclick = function() { FUTURES_STATE.zone = b.dataset.zone; renderFutures(); };
    });

    renderFuturesKPIs(fwd);
    renderForwardChart(fwd);
    renderEpadChart(fwd);
    renderForwardTable(fwd);
}

function renderFuturesKPIs(fwd) {
    var zone = FUTURES_STATE.zone;
    var sysContracts = (fwd.contracts || []).filter(function(c) { return c.type === 'year'; });
    var nextYr = sysContracts[0];
    var sysPrice = nextYr ? (fwd.sys && fwd.sys[nextYr.label]) : null;
    var epadPrice = (nextYr && fwd.epad && fwd.epad[zone]) ? fwd.epad[zone][nextYr.label] : null;
    if (sysPrice === undefined) sysPrice = null;
    if (epadPrice === undefined) epadPrice = null;
    var zonePrice = (sysPrice != null && epadPrice != null) ? (sysPrice + epadPrice) : null;

    // realised spot for current year
    var realLatest = null;
    var realLabel = null;
    if (fwd.spot_realized && fwd.spot_realized[zone]) {
        var keys = Object.keys(fwd.spot_realized[zone]);
        if (keys.length) {
            realLabel = keys[keys.length - 1];
            realLatest = fwd.spot_realized[zone][realLabel].spot_avg;
        }
    }

    var tiles = [];
    tiles.push(kpiTile('Settlement date', htmlEsc(fwd.settlement_date || '–'), '', 'Latest Nasdaq daily fix'));
    tiles.push(kpiTile('SYS ' + (nextYr ? nextYr.label : ''), sysPrice != null ? fmtNum(sysPrice, 2) : '–', 'EUR/MWh', 'Nordic baseload future'));
    tiles.push(kpiTile('EPAD ' + zone, epadPrice != null ? fmtNum(epadPrice, 2) : '–', 'EUR/MWh', 'Zone differential'));
    tiles.push(kpiTile(zone + ' implied', zonePrice != null ? fmtNum(zonePrice, 2) : '–', 'EUR/MWh', 'SYS + EPAD'));
    tiles.push(kpiTile('Realised spot', realLatest != null ? fmtNum(realLatest, 2) : '–', 'EUR/MWh', realLabel ? 'YTD ' + realLabel : ''));
    el('futures-kpis').innerHTML = tiles.join('');
}

function renderForwardChart(fwd) {
    var zone = FUTURES_STATE.zone;
    var contracts = (fwd.contracts || []).slice();
    var labels = contracts.map(function(c) { return c.label; });

    var sysSeries  = labels.map(function(l) { return (fwd.sys && fwd.sys[l] != null) ? fwd.sys[l] : null; });
    var epadSeries = labels.map(function(l) { return (fwd.epad && fwd.epad[zone] && fwd.epad[zone][l] != null) ? fwd.epad[zone][l] : null; });
    var zoneSeries = labels.map(function(l, i) { return (sysSeries[i] != null && epadSeries[i] != null) ? sysSeries[i] + epadSeries[i] : null; });

    var realLabels = (fwd.expired_contracts || []).map(function(c) { return c.label; });
    var realSeries = realLabels.map(function(l) { return (fwd.spot_realized[zone] && fwd.spot_realized[zone][l]) ? fwd.spot_realized[zone][l].spot_avg : null; });

    var traces = [
        { x: labels, y: sysSeries,  name: 'SYS baseload',     mode: 'lines+markers', type: 'scatter', line: { color: '#2E5C4D', width: 2, shape: 'spline' }, marker: { size: 6 }, hovertemplate: '%{x}<br>SYS: <b>%{y:.2f}</b> EUR/MWh<extra></extra>' },
        { x: labels, y: zoneSeries, name: zone + ' implied',  mode: 'lines+markers', type: 'scatter', line: { color: '#C16E40', width: 2, shape: 'spline' }, marker: { size: 6 }, hovertemplate: '%{x}<br>' + zone + ': <b>%{y:.2f}</b> EUR/MWh<extra></extra>' },
    ];
    if (realLabels.length) {
        traces.push({ x: realLabels, y: realSeries, name: 'Realised ' + zone, type: 'scatter', mode: 'markers', marker: { color: '#B14F75', size: 9, symbol: 'diamond' }, hovertemplate: '%{x}<br>Realised: <b>%{y:.2f}</b> EUR/MWh<extra></extra>' });
    }
    Plotly.react('futures-forward-chart', traces, makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EUR / MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 86, l: 64, r: 24 },
        xaxis: Object.assign({}, PLOTLY_BASE.xaxis, { tickangle: -45 }),
    }), PLOTLY_CFG);
}

function renderEpadChart(fwd) {
    var contracts = (fwd.contracts || []).slice();
    var labels = contracts.map(function(c) { return c.label; });
    var traces = ['SE1','SE2','SE3','SE4'].map(function(z, i) {
        var ys = labels.map(function(l) { return (fwd.epad && fwd.epad[z] && fwd.epad[z][l] != null) ? fwd.epad[z][l] : null; });
        var palette = ['#5B6BA8', '#4A8C7B', '#C9A53C', '#B14F75'];
        return {
            x: labels, y: ys, name: z, type: 'bar',
            marker: { color: palette[i] },
            hovertemplate: '%{x}<br>' + z + ': <b>%{y:.2f}</b> EUR/MWh<extra></extra>',
        };
    });
    Plotly.react('futures-epad-chart', traces, makeLayout({
        barmode: 'group',
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EPAD EUR / MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 86, l: 64, r: 24 },
        xaxis: Object.assign({}, PLOTLY_BASE.xaxis, { tickangle: -45 }),
    }), PLOTLY_CFG);
}

function renderForwardTable(fwd) {
    var zone = FUTURES_STATE.zone;
    var contracts = (fwd.contracts || []).slice();
    var rows = contracts.map(function(c) {
        var sys = (fwd.sys && fwd.sys[c.label] != null) ? fwd.sys[c.label] : null;
        var epad = (fwd.epad && fwd.epad[zone] && fwd.epad[zone][c.label] != null) ? fwd.epad[zone][c.label] : null;
        var z = (sys != null && epad != null) ? sys + epad : null;
        return { label: c.label, type: c.type, start: c.start, end: c.end, sys: sys, epad: epad, zone: z };
    });
    var head = '<thead><tr>' +
        '<th>Contract</th>' +
        '<th>Type</th>' +
        '<th>Start</th>' +
        '<th>End</th>' +
        '<th class="num">SYS</th>' +
        '<th class="num">EPAD ' + zone + '</th>' +
        '<th class="num">Implied ' + zone + '</th>' +
        '</tr></thead>';
    var body = '<tbody>' + rows.map(function(r) {
        return '<tr>' +
            '<td>' + htmlEsc(r.label) + '</td>' +
            '<td>' + htmlEsc(r.type) + '</td>' +
            '<td class="muted">' + htmlEsc(r.start || '') + '</td>' +
            '<td class="muted">' + htmlEsc(r.end || '') + '</td>' +
            '<td class="num">' + fmtNum(r.sys, 2) + '</td>' +
            '<td class="num">' + fmtNum(r.epad, 2) + '</td>' +
            '<td class="num"><b>' + fmtNum(r.zone, 2) + '</b></td>' +
            '</tr>';
    }).join('') + '</tbody>';
    el('futures-table').innerHTML = head + body;
}


// ============================================================
//  ASSETS TAB
// ============================================================
var ASSETS = (DATA && DATA.assets) ? DATA.assets : null;
var ASSETS_STATE = { mode: 'fleet', selectedPark: null, monthKey: 'latest', zone: 'ALL', drillMonth: null, tableParks: null };
var TABLE_STATE = { sortKey: 'energy_mwh', sortDir: 'desc' };

function allParkKeysSorted() {
    if (!ASSETS || !ASSETS.parks) return [];
    return Object.entries(ASSETS.parks)
        .sort(function(a, b) { return (a[1].name || a[0]).localeCompare(b[1].name || b[0]); })
        .map(function(e) { return e[0]; });
}
function tableParkSet() {
    // null = all selected (default)
    if (ASSETS_STATE.tableParks === null) return null;
    return ASSETS_STATE.tableParks;
}

function renderAssets() {
    if (!ASSETS) {
        el('assets-content').innerHTML = '<div class="empty-note">No asset data available.</div>';
        return;
    }
    if (ASSETS_STATE.mode === 'drilldown') {
        renderDrilldown();
    } else {
        renderFleetMode();
    }
}

function latestMonthKey() {
    if (!ASSETS || !ASSETS.parks) return null;
    var maxKey = null;
    Object.values(ASSETS.parks).forEach(function(p) {
        (p.months || []).forEach(function(m) {
            var k = m.year + '-' + String(m.month).padStart(2, '0');
            if (maxKey === null || k > maxKey) maxKey = k;
        });
    });
    return maxKey;
}
function activeMonthKey() { return ASSETS_STATE.monthKey === 'latest' ? latestMonthKey() : ASSETS_STATE.monthKey; }
function allMonthKeys() {
    if (!ASSETS || !ASSETS.parks) return [];
    var s = {};
    Object.values(ASSETS.parks).forEach(function(p) {
        (p.months || []).forEach(function(m) { s[m.year + '-' + String(m.month).padStart(2, '0')] = true; });
    });
    return Object.keys(s).sort();
}
function filteredEntries() {
    var entries = Object.entries((ASSETS && ASSETS.parks) || {});
    if (ASSETS_STATE.zone !== 'ALL') entries = entries.filter(function(e) { return e[1].zone === ASSETS_STATE.zone; });
    return entries;
}
function parkMonth(park, key) {
    return (park.months || []).find(function(m) { return (m.year + '-' + String(m.month).padStart(2, '0')) === key; });
}

function renderFleetMode() {
    el('fleet-mode').hidden = false;
    el('drill-mode').hidden = true;

    // Filter controls
    var monthSel = el('assets-month-sel');
    if (!monthSel.dataset.bound) {
        var keys = allMonthKeys();
        monthSel.innerHTML = '<option value="latest">Latest</option>' +
            keys.slice().reverse().map(function(k) {
                return '<option value="' + htmlEsc(k) + '">' + htmlEsc(k) + '</option>';
            }).join('');
        monthSel.value = ASSETS_STATE.monthKey;
        monthSel.addEventListener('change', function() {
            ASSETS_STATE.monthKey = monthSel.value;
            renderFleetMode();
        });
        monthSel.dataset.bound = '1';
    }
    var zoneSel = el('assets-zone-sel');
    if (!zoneSel.dataset.bound) {
        zoneSel.value = ASSETS_STATE.zone;
        zoneSel.addEventListener('change', function() {
            ASSETS_STATE.zone = zoneSel.value;
            renderFleetMode();
        });
        zoneSel.dataset.bound = '1';
    }

    var monthKey = activeMonthKey();
    el('assets-month-label').textContent = monthKey || '—';

    renderFleetKPIs(monthKey);
    renderParkGrid(monthKey);
    renderParkChips();
    renderParkTable(monthKey);
}

function renderParkChips() {
    var host = el('park-chips');
    if (!host) return;
    var keys = allParkKeysSorted();
    if (!keys.length) { host.innerHTML = ''; return; }
    var sel = tableParkSet();
    var html = '<span class="park-chips-label">Parks in table</span>' +
        keys.map(function(k) {
            var p = ASSETS.parks[k];
            var isOn = (sel === null) || (sel.indexOf(k) !== -1);
            return '<button type="button" class="park-chip" data-key="' + htmlEsc(k) + '" aria-pressed="' + isOn + '">' +
                htmlEsc(p.name || k) +
            '</button>';
        }).join('') +
        '<button type="button" class="park-chip-reset" id="park-chips-reset">All</button>';
    host.innerHTML = html;
    host.querySelectorAll('.park-chip').forEach(function(b) {
        b.addEventListener('click', function() {
            var k = b.dataset.key;
            var current = ASSETS_STATE.tableParks;
            if (current === null) {
                // start from "all", then drop this one
                current = allParkKeysSorted().filter(function(x) { return x !== k; });
            } else {
                var idx = current.indexOf(k);
                if (idx === -1) current = current.concat([k]);
                else { current = current.slice(); current.splice(idx, 1); }
            }
            ASSETS_STATE.tableParks = current;
            renderParkChips();
            renderParkTable(activeMonthKey());
        });
    });
    var resetBtn = el('park-chips-reset');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            ASSETS_STATE.tableParks = null;
            renderParkChips();
            renderParkTable(activeMonthKey());
        });
    }
}

function renderFleetKPIs(monthKey) {
    var entries = filteredEntries();
    if (!entries.length) {
        el('fleet-kpis').innerHTML = '<div class="kpi"><div class="kpi-label">No parks</div><div class="kpi-value">—</div></div>';
        return;
    }
    var totalCap = 0, totalActual = 0, totalBudget = 0, totalNeg = 0;
    entries.forEach(function(e) {
        var p = e[1];
        totalCap += (p.capacity_mwp || 0);
        var m = parkMonth(p, monthKey);
        if (m) {
            totalActual += (m.energy_mwh || 0);
            totalBudget += (m.budget_mwh || 0);
            totalNeg += (m.neg_price_hours || 0);
        }
    });
    var vsBudget = totalBudget > 0 ? 100 * (totalActual - totalBudget) / totalBudget : null;
    var vsCls = vsClass(vsBudget);
    var pillHtml = vsBudget != null ? '<span class="pill ' + vsCls + '">' + fmtPct(vsBudget) + '</span>' : '<span class="pill neutral">–</span>';

    var tiles = [
        kpiTile('Parks', String(entries.length), '', 'Active in fleet view'),
        kpiTile('Installed capacity', fmtNum(totalCap, 1), 'MWp', 'DC, sum across selection'),
        kpiTile('Energy ' + (monthKey || ''), fmtNum(totalActual, 0), 'MWh', 'Budget: ' + fmtNum(totalBudget, 0) + ' MWh'),
        '<div class="kpi"><div class="kpi-label">vs Budget</div><div class="kpi-value">' + (vsBudget != null ? fmtPct(vsBudget) : '–') + '</div><div class="kpi-sub">' + pillHtml + '</div></div>',
        kpiTile('Negative-price hours', fmtNum(totalNeg, 0), 'h', 'Sum across selection'),
    ];
    el('fleet-kpis').innerHTML = tiles.join('');
}

function sparkline(months) {
    if (!months || months.length < 2) return '';
    var W = 110, H = 28;
    var n = months.length;
    var BARW = Math.max(2, Math.floor((W - n) / n));
    var maxV = Math.max.apply(null, months.map(function(m) { return m.energy_mwh || 0; })) || 1;
    var bars = months.map(function(m, i) {
        var v = (m.energy_mwh || 0) / maxV;
        var h = Math.max(1, Math.round(H * v));
        var fill = '#92B53D';
        if (m.vs_budget_pct != null) {
            if (m.vs_budget_pct <= -5) fill = '#B14E45';
            else if (m.vs_budget_pct < 5) fill = '#B0832C';
        }
        return '<rect x="' + (i * (BARW + 1)) + '" y="' + (H - h) + '" width="' + BARW + '" height="' + h + '" fill="' + fill + '" opacity="0.85"></rect>';
    }).join('');
    return '<svg width="' + W + '" height="' + H + '" aria-hidden="true">' + bars + '</svg>';
}

function renderParkGrid(monthKey) {
    var entries = filteredEntries();
    if (!entries.length) {
        el('park-grid').innerHTML = '<div class="empty-note">No parks match this filter.</div>';
        return;
    }
    el('park-grid').innerHTML = entries.map(function(e) {
        var pk = e[0], p = e[1];
        var m = parkMonth(p, monthKey);
        var vs = m ? m.vs_budget_pct : null;
        var cls = vsClass(vs);
        var pillHtml = vs != null ? '<span class="pill ' + cls + '">' + fmtPct(vs) + '</span>' : '<span class="pill neutral">–</span>';
        return '<div class="park-tile ' + cls + '" data-park="' + htmlEsc(pk) + '" tabindex="0" role="button">' +
            '<div class="park-tile-head">' +
                '<div class="park-tile-name">' + htmlEsc(p.name || pk) + '</div>' +
                '<div class="park-tile-zone">' + htmlEsc(p.zone || '') + '</div>' +
            '</div>' +
            '<div class="park-tile-stat"><span class="park-tile-stat-k">Capacity</span><span class="park-tile-stat-v">' + fmtNum(p.capacity_mwp, 2) + ' MWp</span></div>' +
            '<div class="park-tile-stat"><span class="park-tile-stat-k">Energy</span><span class="park-tile-stat-v">' + (m ? fmtNum(m.energy_mwh, 0) + ' MWh' : '–') + '</span></div>' +
            '<div class="park-tile-stat"><span class="park-tile-stat-k">Budget</span><span class="park-tile-stat-v">' + (m ? fmtNum(m.budget_mwh, 0) + ' MWh' : '–') + '</span></div>' +
            '<div class="park-tile-stat"><span class="park-tile-stat-k">vs Budget</span>' + pillHtml + '</div>' +
            '<div class="park-tile-spark"><span class="park-tile-stat-k">12-month energy</span>' + sparkline(p.months || []) + '</div>' +
        '</div>';
    }).join('');
    el('park-grid').querySelectorAll('.park-tile').forEach(function(t) {
        t.addEventListener('click', function() { openDrilldown(t.dataset.park); });
        t.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDrilldown(t.dataset.park); }
        });
    });
}

function ytdSum(park, monthKey) {
    if (!monthKey) return 0;
    var yr = parseInt(monthKey.split('-')[0]);
    var mo = parseInt(monthKey.split('-')[1]);
    var sum = 0;
    (park.months || []).forEach(function(m) {
        if (m.year === yr && m.month <= mo && m.energy_mwh) sum += m.energy_mwh;
    });
    return sum;
}

function tableRows(monthKey) {
    var sel = tableParkSet();
    return filteredEntries().filter(function(e) {
        return sel === null || sel.indexOf(e[0]) !== -1;
    }).map(function(e) {
        var pk = e[0], p = e[1];
        var m = parkMonth(p, monthKey);
        return {
            key: pk, name: p.name || pk, zone: p.zone || '',
            capacity_mwp: p.capacity_mwp || 0,
            energy_mwh: m ? m.energy_mwh : null,
            budget_mwh: m ? m.budget_mwh : null,
            vs_budget_pct: m ? m.vs_budget_pct : null,
            ytd_mwh: ytdSum(p, monthKey),
            yield_kwh_kwp: m ? m.yield_kwh_kwp : null,
        };
    });
}

function renderParkTable(monthKey) {
    var rows = tableRows(monthKey);
    var dir = TABLE_STATE.sortDir === 'asc' ? 1 : -1;
    var sk = TABLE_STATE.sortKey;
    rows.sort(function(a, b) {
        var av = a[sk], bv = b[sk];
        if (av == null) return 1;
        if (bv == null) return -1;
        if (typeof av === 'string') return dir * av.localeCompare(bv);
        return dir * (av - bv);
    });
    var cols = [
        { k: 'name',          label: 'Park',            fmt: htmlEsc },
        { k: 'zone',          label: 'Zone',            fmt: htmlEsc, cls: '' },
        { k: 'capacity_mwp',  label: 'Cap MWp',         fmt: function(v) { return fmtNum(v, 2); }, cls: 'num' },
        { k: 'energy_mwh',    label: 'MWh (latest)',    fmt: function(v) { return fmtNum(v, 0); }, cls: 'num' },
        { k: 'vs_budget_pct', label: 'vs Budget',       fmt: function(v) { if (v == null) return '–'; var c = vsClass(v); return '<span class="pill ' + c + '">' + fmtPct(v) + '</span>'; }, cls: 'num', html: true },
        { k: 'ytd_mwh',       label: 'YTD MWh',         fmt: function(v) { return fmtNum(v, 0); }, cls: 'num' },
        { k: 'yield_kwh_kwp', label: 'Yield kWh/kWp',   fmt: function(v) { return fmtNum(v, 1); }, cls: 'num' },
    ];
    var head = '<thead><tr>' + cols.map(function(c) {
        var sortAttr = (c.k === sk) ? (dir > 0 ? 'ascending' : 'descending') : 'none';
        var arrow = (sortAttr === 'ascending' ? '▲' : (sortAttr === 'descending' ? '▼' : '◇'));
        return '<th class="' + (c.cls || '') + '" data-key="' + htmlEsc(c.k) + '" aria-sort="' + sortAttr + '">' + htmlEsc(c.label) + ' <span class="arrow">' + arrow + '</span></th>';
    }).join('') + '</tr></thead>';
    var body = '<tbody>' + rows.map(function(r) {
        return '<tr data-park="' + htmlEsc(r.key) + '">' +
            cols.map(function(c) {
                var v = r[c.k];
                var disp = c.fmt ? c.fmt(v) : (v == null ? '–' : v);
                if (!c.html && typeof disp === 'string' && c.fmt !== htmlEsc && c.cls !== 'num') {
                    // numeric formatters return digit strings — safe
                }
                return '<td class="' + (c.cls || '') + '">' + disp + '</td>';
            }).join('') +
        '</tr>';
    }).join('') + '</tbody>';
    var t = el('park-table');
    t.innerHTML = head + body;
    t.querySelectorAll('thead th').forEach(function(th) {
        th.addEventListener('click', function() {
            var k = th.dataset.key;
            if (TABLE_STATE.sortKey === k) TABLE_STATE.sortDir = TABLE_STATE.sortDir === 'asc' ? 'desc' : 'asc';
            else { TABLE_STATE.sortKey = k; TABLE_STATE.sortDir = 'desc'; }
            renderParkTable(monthKey);
        });
    });
    t.querySelectorAll('tbody tr').forEach(function(tr) {
        tr.addEventListener('click', function() { openDrilldown(tr.dataset.park); });
    });
}

function exportParkCsv() {
    var monthKey = activeMonthKey();
    var header = ['Park','Zone','Capacity_MWp','Energy_MWh_' + monthKey,'vs_Budget_pct','YTD_MWh','Yield_kWh_kWp'];
    var rows = [header];
    tableRows(monthKey).forEach(function(r) {
        rows.push([r.name, r.zone, r.capacity_mwp, r.energy_mwh, r.vs_budget_pct, r.ytd_mwh, r.yield_kwh_kwp]);
    });
    var csv = rows.map(function(r) {
        return r.map(function(c) {
            if (c == null) return '';
            var s = String(c);
            if (s.indexOf(',') !== -1 || s.indexOf('"') !== -1 || s.indexOf('\n') !== -1) {
                return '"' + s.replace(/"/g, '""') + '"';
            }
            return s;
        }).join(',');
    }).join('\n');
    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'park_comparison_' + monthKey + '.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
}
window.exportParkCsv = exportParkCsv;

// ----- Drill-down -----
function openDrilldown(pk) {
    if (!pk || !ASSETS.parks[pk]) return;
    ASSETS_STATE.mode = 'drilldown';
    ASSETS_STATE.selectedPark = pk;
    ASSETS_STATE.drillMonth = null;
    renderDrilldown();
}
window.exitDrilldown = function() {
    ASSETS_STATE.mode = 'fleet';
    ASSETS_STATE.selectedPark = null;
    renderAssets();
};

function captureForZoneMonth(zone, monthKey) {
    if (!ASSETS || !ASSETS.capture_by_zone || !zone || !monthKey) return null;
    var arr = ASSETS.capture_by_zone[zone];
    if (!arr) return null;
    var rec = arr.find(function(r) { return r.month === monthKey; });
    return rec ? rec.capture_eur_mwh : null;
}
function captureSeriesForZone(zone, keys) {
    return keys.map(function(k) { return captureForZoneMonth(zone, k); });
}
function trackerGainForMonth(monthKey) {
    if (!ASSETS || !ASSETS.tracker_gain || !ASSETS.tracker_gain.monthly || !monthKey) return null;
    var yr = parseInt(monthKey.split('-')[0]);
    var mo = parseInt(monthKey.split('-')[1]);
    var rec = ASSETS.tracker_gain.monthly.find(function(r) { return r.year === yr && r.month === mo; });
    return rec && rec.gain_pct != null ? rec.gain_pct : null;
}

function renderDrilldown() {
    var pk = ASSETS_STATE.selectedPark;
    var p = ASSETS.parks[pk];
    if (!p) return;
    el('fleet-mode').hidden = true;
    el('drill-mode').hidden = false;

    var monthKey = ASSETS_STATE.drillMonth || activeMonthKey();
    if (!parkMonth(p, monthKey)) {
        var available = (p.months || []).map(function(mm) { return mm.year + '-' + String(mm.month).padStart(2, '0'); }).sort();
        if (available.length) monthKey = available[available.length - 1];
    }
    ASSETS_STATE.drillMonth = monthKey;
    var m = parkMonth(p, monthKey);

    el('drill-name').textContent = p.name || pk;
    el('drill-meta').innerHTML =
        '<span><span class="eyebrow">Zone</span> ' + htmlEsc(p.zone || '') + '</span>' +
        '<span><span class="eyebrow">Capacity</span> <span class="num">' + fmtNum(p.capacity_mwp, 2) + '</span> MWp</span>' +
        '<span><span class="eyebrow">Period</span> <span class="num">' + htmlEsc(monthKey || '–') + '</span></span>';

    // Month selector
    var sel = el('drill-month-sel');
    var keys = Object.keys(p.daily_by_month || {}).sort();
    if (!keys.length) {
        keys = (p.months || []).map(function(mm) { return mm.year + '-' + String(mm.month).padStart(2, '0'); }).sort();
    }
    sel.innerHTML = keys.slice().reverse().map(function(k) {
        return '<option value="' + htmlEsc(k) + '"' + (k === monthKey ? ' selected' : '') + '>' + htmlEsc(k) + '</option>';
    }).join('');
    if (!sel.dataset.bound) {
        sel.addEventListener('change', function() {
            ASSETS_STATE.drillMonth = sel.value;
            renderDrilldown();
        });
        sel.dataset.bound = '1';
    }

    // KPI strip
    var captureZone = captureForZoneMonth(p.zone, monthKey);
    var trackerPct = trackerGainForMonth(monthKey);
    var isHova = (pk === 'hova');
    var trackerTile = isHova
        ? kpiTile('Tracker gain', trackerPct != null ? fmtPct(trackerPct, 1) : '–', '', 'vs SE3 fixed-tilt')
        : '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Tracker gain</div><div class="kpi-value">—</div><div class="kpi-sub">Hova only</div></div>';

    var pillHtml = '';
    if (m && m.vs_budget_pct != null) {
        pillHtml = '<span class="pill ' + vsClass(m.vs_budget_pct) + '">' + fmtPct(m.vs_budget_pct) + '</span>';
    } else {
        pillHtml = '<span class="pill neutral">–</span>';
    }
    var vsTile = '<div class="kpi"><div class="kpi-label">vs Budget</div><div class="kpi-value">' +
        (m && m.vs_budget_pct != null ? fmtPct(m.vs_budget_pct) : '–') + '</div><div class="kpi-sub">' + pillHtml + '</div></div>';

    var tiles = [
        kpiTile('Energy', m ? fmtNum(m.energy_mwh, 0) : '–', 'MWh', monthKey || ''),
        vsTile,
        kpiTile('Yield', m ? fmtNum(m.yield_kwh_kwp, 1) : '–', 'kWh/kWp', ''),
        kpiTile('Capture · ' + (p.zone || ''), captureZone != null ? fmtNum(captureZone, 1) : '–', 'EUR/MWh', ''),
        kpiTile('Negative-price h', m && m.neg_price_hours != null ? fmtNum(m.neg_price_hours, 0) : '–', 'h', m && m.neg_price_volume_mwh != null ? fmtNum(m.neg_price_volume_mwh, 0) + ' MWh forgone' : ''),
        trackerTile,
    ];
    el('drill-kpis').innerHTML = tiles.join('');

    // Charts
    var months = (p.months || []).slice();
    var xs = months.map(function(mm) { return mm.year + '-' + String(mm.month).padStart(2, '0'); });

    Plotly.react('drill-energy-chart', [
        { x: xs, y: months.map(function(mm) { return mm.energy_mwh; }), name: 'Actual', type: 'bar', marker: { color: '#2E5C4D' }, hovertemplate: '%{x}<br>Actual: <b>%{y:,.0f}</b> MWh<extra></extra>' },
        { x: xs, y: months.map(function(mm) { return mm.budget_mwh; }), name: 'Budget', type: 'bar', marker: { color: '#C9A53C', opacity: 0.55 }, hovertemplate: '%{x}<br>Budget: <b>%{y:,.0f}</b> MWh<extra></extra>' },
    ], makeLayout({
        barmode: 'group',
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 70, l: 64, r: 24 },
    }), PLOTLY_CFG);

    Plotly.react('drill-yield-chart', [
        { x: xs, y: months.map(function(mm) { return mm.yield_kwh_kwp; }), type: 'scatter', mode: 'lines+markers', line: { color: '#92B53D', width: 2.4, shape: 'spline' }, marker: { size: 6 }, hovertemplate: '%{x}<br>Yield: <b>%{y:.1f}</b> kWh/kWp<extra></extra>', name: 'Yield' },
    ], makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'kWh / kWp', font: PLOTLY_BASE.yaxis.title.font } }),
        showlegend: false,
        margin: { t: 12, b: 70, l: 64, r: 24 },
    }), PLOTLY_CFG);

    var days = (p.daily_by_month && p.daily_by_month[monthKey]) || [];
    if (days.length) {
        var dxs = days.map(function(d) { return d.date; });
        Plotly.react('drill-daily-chart', [
            { x: dxs, y: days.map(function(d) { return d.energy_mwh; }), name: 'Actual', type: 'bar', marker: { color: '#2E5C4D' }, hovertemplate: '%{x}<br>Actual: <b>%{y:.2f}</b> MWh<extra></extra>' },
            { x: dxs, y: days.map(function(d) { return d.expected_mwh; }), name: 'Expected', type: 'scatter', mode: 'lines', line: { color: '#C16E40', dash: 'dash', width: 2 }, hovertemplate: '%{x}<br>Expected: <b>%{y:.2f}</b> MWh<extra></extra>' },
        ], makeLayout({
            yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'MWh', font: PLOTLY_BASE.yaxis.title.font } }),
            margin: { t: 12, b: 70, l: 64, r: 24 },
        }), PLOTLY_CFG);
    } else {
        Plotly.purge('drill-daily-chart');
        el('drill-daily-chart').innerHTML = '<div class="empty-note">No daily data for ' + htmlEsc(monthKey) + '.</div>';
    }

    Plotly.react('drill-capture-chart', [
        { x: xs, y: captureSeriesForZone(p.zone, xs), type: 'scatter', mode: 'lines+markers', line: { color: '#5B6BA8', width: 2.4, shape: 'spline' }, marker: { size: 6 }, name: 'Capture ' + (p.zone || ''), hovertemplate: '%{x}<br>Capture: <b>%{y:.1f}</b> EUR/MWh<extra></extra>' },
    ], makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EUR / MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        showlegend: false,
        margin: { t: 12, b: 70, l: 64, r: 24 },
    }), PLOTLY_CFG);

    renderBestWorst(p, monthKey);

    var reportPath = 'performance_' + pk + '_' + (p.zone || '') + '_' + monthKey + '.html';
    el('drill-links').innerHTML =
        '<a href="' + htmlEsc(reportPath) + '" target="_blank" rel="noopener">' + htmlEsc(reportPath) + '</a> <span class="muted">— if generated</span>';
}

function renderBestWorst(p, monthKey) {
    var c = el('drill-bestworst');
    var days = (p.daily_by_month && p.daily_by_month[monthKey]) || [];
    if (!days.length) {
        c.innerHTML = '<div class="empty-note">No daily data for ' + htmlEsc(monthKey) + '.</div>';
        return;
    }
    var sorted = days.slice().sort(function(a, b) { return (b.energy_mwh || 0) - (a.energy_mwh || 0); });
    var top = sorted.slice(0, 5);
    var bottom = sorted.slice(-5).reverse();
    function tableHtml(title, rows, cls) {
        var head = '<thead><tr>' +
            '<th>Date</th><th>Day</th><th class="num">MWh</th><th class="num">kWh/kWp</th>' +
            '</tr></thead>';
        var body = '<tbody>' + rows.map(function(r) {
            return '<tr>' +
                '<td>' + htmlEsc(r.date || '–') + '</td>' +
                '<td class="muted">' + htmlEsc(r.weekday || '') + '</td>' +
                '<td class="num">' + fmtNum(r.energy_mwh, 2) + '</td>' +
                '<td class="num">' + fmtNum(r.yield_kwh_kwp, 1) + '</td>' +
                '</tr>';
        }).join('') + '</tbody>';
        return '<div><div class="bw-title ' + cls + '">' + title + '</div>' +
            '<table class="editorial">' + head + body + '</table></div>';
    }
    c.innerHTML = tableHtml('Top 5', top, 'good') + tableHtml('Bottom 5', bottom, 'bad');
}


// ============================================================
//  Boot
// ============================================================
function init() {
    // Footer
    var f = el('foot-generated');
    if (f && DATA.generated) f.textContent = DATA.generated;

    // Wire rail tabs
    document.querySelectorAll('.rail-tab').forEach(function(t) {
        t.addEventListener('click', function() { switchTab(t.dataset.tab); });
        t.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); switchTab(t.dataset.tab); }
        });
    });

    // Initial tab from hash, fallback to capture
    var initial = (location.hash || '#capture').slice(1);
    if (TABS.indexOf(initial) === -1) initial = 'capture';
    switchTab(initial);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
""".strip()


# ---------------------------------------------------------------------------
# HTML shell
# ---------------------------------------------------------------------------

_SHELL = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SveaSolar · Asset Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400;1,6..72,500;1,6..72,600&family=Geist:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>{css}</style>
</head>
<body>
<div class="app">
  <!-- ============== Rail (left navigation) ============== -->
  <aside class="rail" aria-label="Primary navigation">
    <div class="rail-mark" title="SveaSolar">Sv</div>
    <div class="rail-tabs" role="tablist">
      <div class="rail-tab" data-tab="capture" role="tab" aria-selected="true" tabindex="0" title="Capture Prices">
        C<span class="rail-tab-name">Capture</span>
      </div>
      <div class="rail-tab" data-tab="bess" role="tab" aria-selected="false" tabindex="0" title="Battery Economics">
        B<span class="rail-tab-name">BESS</span>
      </div>
      <div class="rail-tab" data-tab="futures" role="tab" aria-selected="false" tabindex="0" title="Forward Curve">
        F<span class="rail-tab-name">Futures</span>
      </div>
      <div class="rail-tab" data-tab="assets" role="tab" aria-selected="false" tabindex="0" title="Asset Performance">
        A<span class="rail-tab-name">Assets</span>
      </div>
    </div>
    <div class="rail-foot">
      v3<br>
      Track C
    </div>
  </aside>

  <!-- ============== Content column ============== -->
  <main class="content">

    <!-- ===== CAPTURE ===== -->
    <section class="page" id="page-capture" role="tabpanel" aria-labelledby="tab-capture">
      <header class="page-head">
        <div class="page-head-left">
          <div class="page-eyebrow">Market</div>
          <h1 class="page-title">Capture Prices</h1>
          <p class="page-sub">Solar-weighted price realisation across the four Swedish bidding zones, by profile and time horizon.</p>
        </div>
        <div class="page-controls">
          <span class="label-control">Zone <div class="seg" id="capture-zones"></div></span>
          <span class="label-control">Period <div class="seg" id="capture-period"></div></span>
        </div>
      </header>
      <div id="capture-content">
        <div class="kpi-strip" id="capture-kpis"></div>

        <div class="card">
          <div class="card-head">
            <div>
              <div class="card-title">Profiles</div>
              <div class="card-sub">Toggle technology profiles to overlay on the chart.</div>
            </div>
          </div>
          <div id="capture-profiles"></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-head">
              <div><div class="card-title">Price evolution</div><div class="card-sub">Baseload &amp; capture, EUR/MWh.</div></div>
            </div>
            <div class="chart chart-tall" id="capture-main-chart"></div>
          </div>
          <div class="card">
            <div class="card-head">
              <div><div class="card-title">Capture ratio</div><div class="card-sub">Capture price as % of zone baseload.</div></div>
            </div>
            <div class="chart chart-tall" id="capture-ratio-chart"></div>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Hour × month heatmap</div><div class="card-sub">All-time mean spot price by hour of day &amp; month for the selected zone.</div></div>
          </div>
          <div class="chart chart-tall" id="capture-heatmap"></div>
        </div>
      </div>
    </section>

    <!-- ===== BESS ===== -->
    <section class="page" id="page-bess" role="tabpanel" aria-labelledby="tab-bess" hidden>
      <header class="page-head">
        <div class="page-head-left">
          <div class="page-eyebrow">Storage</div>
          <h1 class="page-title">Battery Economics</h1>
          <p class="page-sub">Arbitrage revenue, sol-plus-storage capture, ancillary services and investment economics for grid-scale batteries.</p>
        </div>
        <div class="page-controls">
          <span class="label-control">Zone <div class="seg" id="bess-zones"></div></span>
          <span class="label-control">Duration <div class="seg" id="bess-durations"></div></span>
        </div>
      </header>
      <div id="bess-content">
        <div class="kpi-strip" id="bess-kpis"></div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Arbitrage revenue</div><div class="card-sub">Optimised intraday DP per MW installed power, monthly.</div></div>
          </div>
          <div class="chart chart-tall" id="bess-arb-chart"></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-head">
              <div><div class="card-title">Sol + storage capture</div><div class="card-sub">Capture uplift from co-located battery vs. sol-only.</div></div>
            </div>
            <div class="chart" id="bess-solbess-chart"></div>
          </div>
          <div class="card">
            <div class="card-head">
              <div><div class="card-title">Ancillary services</div><div class="card-sub">FCR / aFRR / mFRR-CM clearing prices.</div></div>
            </div>
            <div class="chart" id="bess-anc-chart"></div>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Investment economics</div><div class="card-sub">Single-zone, single-duration screening NPV / payback.</div></div>
          </div>
          <div class="grid-2">
            <div>
              <div class="invest-row"><label for="inv-capex">CAPEX (EUR / MWh)</label><input type="number" id="inv-capex" min="0" step="1000"></div>
              <div class="invest-row"><label for="inv-opex">OPEX (EUR / MW · yr)</label><input type="number" id="inv-opex" min="0" step="500"></div>
              <div class="invest-row"><label for="inv-life">Lifetime (years)</label><input type="number" id="inv-life" min="1" max="40" step="1"></div>
              <div class="invest-row"><label for="inv-disc">Discount rate (%)</label><input type="number" id="inv-disc" min="0" max="30" step="0.5"></div>
            </div>
            <div id="invest-output"></div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== FUTURES ===== -->
    <section class="page" id="page-futures" role="tabpanel" aria-labelledby="tab-futures" hidden>
      <header class="page-head">
        <div class="page-head-left">
          <div class="page-eyebrow">Forward</div>
          <h1 class="page-title">Forward Curve</h1>
          <p class="page-sub">Nasdaq Nordic settlement prices for the SYS baseload future, EPAD differentials per Swedish zone, and realised spot for delivered contracts.</p>
        </div>
        <div class="page-controls">
          <span class="label-control">Zone focus <div class="seg" id="futures-zones"></div></span>
        </div>
      </header>
      <div id="futures-content">
        <div class="kpi-strip" id="futures-kpis"></div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Forward vs realised</div><div class="card-sub">SYS, zone-implied (SYS + EPAD) and realised YTD spot for delivered contracts.</div></div>
          </div>
          <div class="chart chart-tall" id="futures-forward-chart"></div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">EPAD differentials</div><div class="card-sub">All four zones, per contract.</div></div>
          </div>
          <div class="chart" id="futures-epad-chart"></div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Contract table</div><div class="card-sub">Active forwards and their components.</div></div>
          </div>
          <div style="overflow-x:auto">
            <table class="editorial" id="futures-table"></table>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== ASSETS ===== -->
    <section class="page" id="page-assets" role="tabpanel" aria-labelledby="tab-assets" hidden>
      <div id="fleet-mode">
        <header class="page-head">
          <div class="page-head-left">
            <div class="page-eyebrow">Fleet · <span id="assets-month-label">—</span></div>
            <h1 class="page-title">Asset Performance</h1>
            <p class="page-sub">Per-park monthly energy, yield and budget variance across the SveaSolar utility-scale fleet. Click any park to drill down.</p>
          </div>
          <div class="page-controls">
            <span class="label-control">Month
              <select id="assets-month-sel"></select>
            </span>
            <span class="label-control">Zone
              <select id="assets-zone-sel">
                <option value="ALL">All zones</option>
                <option value="SE1">SE1</option>
                <option value="SE2">SE2</option>
                <option value="SE3">SE3</option>
                <option value="SE4">SE4</option>
              </select>
            </span>
          </div>
        </header>

        <div id="assets-content">
          <div class="kpi-strip" id="fleet-kpis"></div>

          <div class="card">
            <div class="card-head">
              <div>
                <div class="card-title">Parks</div>
                <div class="card-sub">Click a tile to drill down. Sparkline shows last 13 months of energy.</div>
              </div>
              <div class="legend">
                <span><span class="legend-dot" style="background:var(--good)"></span>≥ +5% vs budget</span>
                <span><span class="legend-dot" style="background:var(--warn)"></span>±5%</span>
                <span><span class="legend-dot" style="background:var(--bad)"></span>≤ -5%</span>
              </div>
            </div>
            <div class="park-grid" id="park-grid"></div>
          </div>

          <div class="card">
            <div class="card-head">
              <div><div class="card-title">Comparison table</div><div class="card-sub">Sortable. Click any row for drill-down.</div></div>
              <div class="card-actions">
                <button type="button" class="seg" style="padding:6px 14px;background:var(--accent);color:var(--ink-1);border-radius:var(--radius-pill);font-size:var(--fs-xs);font-weight:600;text-transform:uppercase;letter-spacing:0.06em" onclick="exportParkCsv()">Export CSV</button>
              </div>
            </div>
            <div class="park-chips" id="park-chips" role="group" aria-label="Filter parks shown in table"></div>
            <div style="overflow-x:auto">
              <table class="editorial" id="park-table"></table>
            </div>
          </div>
        </div>
      </div>

      <!-- Drilldown -->
      <div id="drill-mode" hidden>
        <div class="crumb">
          <a href="#assets" onclick="event.preventDefault(); exitDrilldown();">← Fleet</a>
          <span class="crumb-sep">/</span>
          <span>Assets</span>
          <span class="crumb-sep">/</span>
          <span id="drill-name-crumb"></span>
        </div>
        <div class="drill-hero">
          <div>
            <h1 class="drill-name" id="drill-name"></h1>
            <div class="drill-meta" id="drill-meta"></div>
          </div>
          <div class="page-controls">
            <span class="label-control">Month <select id="drill-month-sel"></select></span>
          </div>
        </div>

        <div class="kpi-strip" id="drill-kpis"></div>

        <div class="grid-2">
          <div class="card">
            <div class="card-head"><div><div class="card-title">Energy vs Budget</div><div class="card-sub">Last 13 months.</div></div></div>
            <div class="chart" id="drill-energy-chart"></div>
          </div>
          <div class="card">
            <div class="card-head"><div><div class="card-title">Specific Yield</div><div class="card-sub">kWh / kWp · month.</div></div></div>
            <div class="chart" id="drill-yield-chart"></div>
          </div>
          <div class="card">
            <div class="card-head"><div><div class="card-title">Daily generation</div><div class="card-sub">Selected month, actual vs expected.</div></div></div>
            <div class="chart" id="drill-daily-chart"></div>
          </div>
          <div class="card">
            <div class="card-head"><div><div class="card-title">Capture price · zone</div><div class="card-sub">Zone-level solar capture, last 13 months.</div></div></div>
            <div class="chart" id="drill-capture-chart"></div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><div><div class="card-title">Best &amp; worst days</div><div class="card-sub">Selected month, ranked by energy.</div></div></div>
          <div class="bw-grid" id="drill-bestworst"></div>
        </div>

        <div class="card">
          <div class="card-head"><div><div class="card-title">Performance report</div><div class="card-sub">Direct link to the standalone monthly HTML report (if generated).</div></div></div>
          <div id="drill-links"></div>
        </div>
      </div>
    </section>

    <footer class="app-foot">
      <div>SveaSolar Asset Intelligence · Track C · Nordic Editorial</div>
      <div>Data generated <span class="num" id="foot-generated">{generated}</span></div>
    </footer>
  </main>
</div>

<script>
const DATA = {data_json};
{js}
</script>
</body>
</html>
"""
