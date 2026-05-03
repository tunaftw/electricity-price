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

/* page title suffix (period in title, e.g. "Asset Performance · April 2026") */
.page-title-suffix {
  font-style: normal;
  font-weight: 400;
  color: var(--ink-3);
  font-size: 0.78em;
  letter-spacing: -0.01em;
  margin-left: 0.5ch;
}
.page-title-suffix::before {
  content: " · ";
  color: var(--ink-4);
  margin-right: 0.25ch;
}
.page-title-suffix:empty { display: none; }
.page-title-suffix:empty::before { content: ""; }

/* sticky period bar (assets tab) */
.period-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-4);
  flex-wrap: wrap;
  padding: var(--sp-3) var(--sp-4);
  margin-bottom: var(--sp-5);
  background: var(--surface-raised);
  border: 1px solid var(--ink-5);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-rest);
}
.period-bar[hidden] { display: none; }
.period-bar-left, .period-bar-right {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
}
.period-stepper {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 3px 6px;
  background: var(--surface-sunken);
  border-radius: var(--radius-pill);
}
.period-stepper button {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: var(--ink-3);
  border-radius: 50%;
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
}
.period-stepper button:hover:not(:disabled) { background: var(--surface-raised); color: var(--ink-1); }
.period-stepper button:disabled { opacity: 0.3; cursor: not-allowed; }
.period-stepper-value {
  font-family: var(--font-display);
  font-size: var(--fs-md);
  font-weight: 500;
  color: var(--ink-1);
  min-width: 4ch;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.period-toast {
  margin-bottom: var(--sp-4);
  padding: var(--sp-3) var(--sp-4);
  background: var(--surface-sunken);
  border-left: 3px solid var(--warn);
  border-radius: var(--radius-md);
  font-size: var(--fs-sm);
  color: var(--ink-2);
}
.period-toast[hidden] { display: none; }
.partial-data-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--warn);
  margin-left: 6px;
  vertical-align: middle;
}
.freshness-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  vertical-align: middle;
  margin-left: 4px;
  border: 1px solid rgba(0,0,0,0.06);
}
.freshness-dot.warn { background: var(--warn); }
.freshness-dot.bad  { background: var(--bad); }
.drill-insight {
  margin-top: var(--sp-2);
  font-family: var(--font-display, 'Newsreader', serif);
  font-style: italic;
  font-size: var(--fs-md);
  color: var(--ink-2);
  max-width: 65ch;
}
.park-facts {
  background: var(--surface-raised);
  border: 1px solid var(--border, rgba(0,0,0,0.08));
  border-radius: var(--radius-md);
  padding: var(--sp-3) var(--sp-4);
  margin: var(--sp-3) 0 var(--sp-4);
}
.park-facts > summary {
  cursor: pointer;
  font-family: var(--font-display, 'Newsreader', serif);
  font-size: var(--fs-md);
  font-weight: 500;
  color: var(--ink-1);
  list-style: none;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.park-facts > summary::before {
  content: '▸';
  font-size: 0.8em;
  color: var(--ink-3, var(--ink-2));
  transition: transform 0.15s;
}
.park-facts[open] > summary::before { transform: rotate(90deg); }
.park-facts > summary::-webkit-details-marker { display: none; }
.facts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--sp-3) var(--sp-5);
  margin-top: var(--sp-3);
}
.fact-cell { font-size: var(--fs-sm); }
.fact-k {
  font-size: var(--fs-xs, 11px);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-3, var(--ink-2));
  margin-bottom: 2px;
}
.fact-v {
  font-family: var(--font-display, 'Newsreader', serif);
  font-size: var(--fs-md);
  color: var(--ink-1);
}
/* time-window range bar (above grid-2 charts) */
.range-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  background: var(--surface-raised);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-rest);
  margin-bottom: var(--sp-5);
  flex-wrap: wrap;
}
.range-nav {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-xs);
  color: var(--ink-3);
}
.range-nav button {
  padding: 5px 10px;
  border-radius: var(--radius-pill);
  background: var(--surface-sunken);
  color: var(--ink-1);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1px solid transparent;
  transition: background var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease);
}
.range-nav button:hover:not(:disabled) { background: var(--surface-base); border-color: var(--ink-5); }
.range-nav button:disabled { opacity: 0.35; cursor: not-allowed; }
.range-nav .range-arrow { padding: 5px 12px; font-size: 14px; line-height: 1; }
.range-label {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: var(--fs-xs);
  color: var(--ink-2);
  letter-spacing: 0.04em;
  min-width: 18ch;
  text-align: center;
}

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
.drill-chart-grid { display: grid; grid-template-columns: 1fr; gap: var(--sp-5); }
@media (min-width: 900px) {
  .drill-chart-grid { grid-template-columns: 1fr 1fr; }
}

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

/* methodology / caveat note — small editorial disclaimer */
.method-note {
  display: flex;
  gap: var(--sp-3);
  align-items: flex-start;
  padding: var(--sp-3) var(--sp-4);
  margin: 0 0 var(--sp-5);
  background: var(--surface-sunken);
  border-left: 2px solid var(--ink-4);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: var(--fs-sm);
  color: var(--ink-2);
  line-height: var(--lh-snug);
}
.method-note .method-icon {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 15px;
  color: var(--ink-3);
  flex-shrink: 0;
  line-height: 1;
  padding-top: 1px;
}
.method-note .method-label {
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 10.5px;
  color: var(--ink-3);
  margin-right: var(--sp-2);
}
.method-note em { font-style: italic; color: var(--ink-1); }

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
// Track C runs on a cream/light surface. Override profile colors that were
// picked for the dark Track A background (notably baseload which is white).
var V3_COLOR_OVERRIDES = {
    baseload: '#1A1814',
};
function profileColor(k) {
    if (V3_COLOR_OVERRIDES[k]) return V3_COLOR_OVERRIDES[k];
    return (DATA.colors && DATA.colors[k]) || null;
}
var CAPTURE_STATE = {
    zone: null,
    period: 'monthly',     // 'yearly' | 'monthly' | 'daily'
    profiles: ['baseload', 'sol_syd'],
    range: 'all',          // 'all' | '10y' | '5y' | '2y' | '1y' | '6m' | '3m' | '1m'
    rangeEnd: null,        // epoch ms anchor for window end; null = follow latest data
};
var CAPTURE_RANGE_OPTIONS = {
    yearly:  ['all', '10y', '5y'],
    monthly: ['all', '5y', '2y', '1y', '6m'],
    daily:   ['all', '1y', '6m', '3m', '1m'],
};
var CAPTURE_RANGE_LABELS = { all:'All', '10y':'10Y', '5y':'5Y', '2y':'2Y', '1y':'1Y', '6m':'6M', '3m':'3M', '1m':'1M' };
var CAPTURE_RANGE_MONTHS = { '10y':120, '5y':60, '2y':24, '1y':12, '6m':6, '3m':3, '1m':1 };

function captureRowDate(r, period) {
    if (period === 'yearly')  return new Date(Date.UTC(r.year, 6, 1));
    if (period === 'monthly') return new Date(Date.UTC(r.year, r.month - 1, 15));
    var p = String(r.date).split('-');
    return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
}
function captureLatestDateMs() {
    var z = (DATA.data && DATA.data[CAPTURE_STATE.zone]) || {};
    var period = CAPTURE_STATE.period;
    var maxMs = null;
    CAPTURE_STATE.profiles.forEach(function(k) {
        var rows = z[k] && z[k][period];
        if (!rows || !rows.length) return;
        var ms = captureRowDate(rows[rows.length - 1], period).getTime();
        if (maxMs == null || ms > maxMs) maxMs = ms;
    });
    return maxMs;
}
function captureCurrentWindow() {
    if (CAPTURE_STATE.range === 'all') return null;
    var months = CAPTURE_RANGE_MONTHS[CAPTURE_STATE.range];
    if (!months) return null;
    var latestMs = captureLatestDateMs();
    if (latestMs == null) return null;
    var endMs = CAPTURE_STATE.rangeEnd != null ? CAPTURE_STATE.rangeEnd : latestMs;
    if (endMs > latestMs) endMs = latestMs;
    var endDate = new Date(endMs);
    var startDate = new Date(endDate);
    startDate.setUTCMonth(startDate.getUTCMonth() - months);
    return { startMs: startDate.getTime(), endMs: endMs, months: months, atLatest: endMs === latestMs };
}
function captureSliceRows(rows, period, win) {
    if (!win) return rows;
    return rows.filter(function(r) {
        var ms = captureRowDate(r, period).getTime();
        return ms >= win.startMs && ms <= win.endMs;
    });
}
function captureWindowLabel(win) {
    if (!win) return 'All time';
    var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var fmt = function(ms) { var d = new Date(ms); return months[d.getUTCMonth()] + ' ' + d.getUTCFullYear(); };
    return fmt(win.startMs) + ' – ' + fmt(win.endMs);
}
function captureNavRange(direction) {
    var months = CAPTURE_RANGE_MONTHS[CAPTURE_STATE.range];
    if (!months) return;
    var latestMs = captureLatestDateMs();
    if (latestMs == null) return;
    var endMs = CAPTURE_STATE.rangeEnd != null ? CAPTURE_STATE.rangeEnd : latestMs;
    var d = new Date(endMs);
    d.setUTCMonth(d.getUTCMonth() + direction * months);
    var newEnd = d.getTime();
    if (newEnd > latestMs) newEnd = latestMs;
    CAPTURE_STATE.rangeEnd = newEnd;
    renderCaptureRangeBar();
    renderCaptureChart();
    renderCaptureRatioChart();
}
function renderCaptureRangeBar() {
    var period = CAPTURE_STATE.period;
    var opts = CAPTURE_RANGE_OPTIONS[period] || ['all'];
    if (opts.indexOf(CAPTURE_STATE.range) === -1) {
        CAPTURE_STATE.range = 'all';
        CAPTURE_STATE.rangeEnd = null;
    }
    var rangeHtml = opts.map(function(r) {
        return '<button type="button" data-range="' + r + '" aria-pressed="' + (r === CAPTURE_STATE.range) + '">' + CAPTURE_RANGE_LABELS[r] + '</button>';
    }).join('');
    el('capture-range').innerHTML = rangeHtml;
    el('capture-range').querySelectorAll('button').forEach(function(b) {
        b.onclick = function() {
            CAPTURE_STATE.range = b.dataset.range;
            CAPTURE_STATE.rangeEnd = null;
            renderCaptureRangeBar();
            renderCaptureChart();
            renderCaptureRatioChart();
        };
    });
    var win = captureCurrentWindow();
    var nav = el('capture-range-nav');
    var prev = el('capture-range-prev');
    var next = el('capture-range-next');
    var now  = el('capture-range-now');
    var label = el('capture-range-label');
    if (!win) {
        nav.style.visibility = 'hidden';
        label.textContent = 'All time';
    } else {
        nav.style.visibility = 'visible';
        label.textContent = captureWindowLabel(win) + (win.atLatest ? ' · latest' : '');
        prev.onclick = function() { captureNavRange(-1); };
        next.onclick = function() { captureNavRange(+1); };
        now.onclick  = function() {
            CAPTURE_STATE.rangeEnd = null;
            renderCaptureRangeBar();
            renderCaptureChart();
            renderCaptureRatioChart();
        };
        next.disabled = !!win.atLatest;
        now.disabled  = !!win.atLatest;
    }
}

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
        b.onclick = function() {
            CAPTURE_STATE.period = b.dataset.period;
            CAPTURE_STATE.rangeEnd = null;  // reset window anchor when granularity changes
            renderCapture();
        };
    });

    // Build profile checkboxes by group
    var availableProfiles = Object.keys((DATA.data && DATA.data[CAPTURE_STATE.zone]) || {});
    var groupsHtml = CAPTURE_PROFILE_GROUPS.map(function(g) {
        var present = g.keys.filter(function(k) { return availableProfiles.indexOf(k) !== -1; });
        if (!present.length) return '';
        var btns = present.map(function(k) {
            var label = (DATA.profiles && DATA.profiles[k]) || k;
            var sel = CAPTURE_STATE.profiles.indexOf(k) !== -1;
            var color = profileColor(k) || '#999';
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
    renderCaptureRangeBar();
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
    var win = captureCurrentWindow();
    var traces = [];
    var unit = 'EUR/MWh';

    CAPTURE_STATE.profiles.forEach(function(k) {
        var p = z[k];
        if (!p || !p[period]) return;
        var rows = captureSliceRows(p[period], period, win);
        var xs = rows.map(function(r) {
            if (period === 'yearly')  return String(r.year);
            if (period === 'monthly') return r.year + '-' + String(r.month).padStart(2, '0');
            return r.date;
        });
        var ys = rows.map(function(r) { return k === 'baseload' ? r.baseload : (r.capture != null ? r.capture : null); });
        var meta = (DATA.profile_meta && DATA.profile_meta[k]) || {};
        var color = profileColor(k);
        var label = (DATA.profiles && DATA.profiles[k]) || k;
        var isBaseload = k === 'baseload';
        var trace = {
            x: xs,
            y: ys,
            name: label,
            mode: period === 'daily' ? 'lines' : 'lines+markers',
            type: 'scatter',
            line: { width: isBaseload ? 2.5 : 1.8, color: color, shape: 'spline' },
            marker: { size: period === 'daily' ? 0 : 5, color: color },
        };
        if (isBaseload) {
            trace.hovertemplate = '%{x}<br>' + htmlEsc(label) + ': <b>%{y:.1f}</b> ' + (meta.unit || unit) + '<extra></extra>';
        } else {
            trace.customdata = rows.map(function(r) {
                return r.ratio != null ? '  ·  <b>' + (r.ratio * 100).toFixed(1) + '%</b> of baseload' : '';
            });
            trace.hovertemplate = '%{x}<br>' + htmlEsc(label) + ': <b>%{y:.1f}</b> ' + (meta.unit || unit) + '%{customdata}<extra></extra>';
        }
        traces.push(trace);
    });

    // Fleet realized capture overlay — only for monthly view and zones
    // where SveaSolar parks exist (SE3 / SE4).
    if (period === 'monthly'
        && DATA.assets
        && DATA.assets.fleet_capture_by_zone
        && DATA.assets.fleet_capture_by_zone[zone]) {
        var fcz = DATA.assets.fleet_capture_by_zone[zone];
        var winRows = fcz.filter(function(r) {
            if (!win) return true;
            // r.month is "YYYY-MM" — convert to UTC ms (month start)
            var parts = r.month.split('-');
            var ms = Date.UTC(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, 1);
            return ms >= win.startMs && ms <= win.endMs;
        });
        if (winRows.length) {
            traces.push({
                x: winRows.map(function(r) { return r.month; }),
                y: winRows.map(function(r) { return r.fleet_capture_eur_mwh; }),
                name: 'Fleet realized (' + zone + ')',
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#5B6BA8', dash: 'dot', width: 2 },
                marker: { size: 5, symbol: 'diamond' },
                hovertemplate: '%{x}<br>Fleet realized: <b>%{y:.1f}</b> EUR/MWh<extra></extra>',
            });
        }
    }

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
    var win = captureCurrentWindow();
    var traces = [];
    CAPTURE_STATE.profiles.filter(function(k) { return k !== 'baseload'; }).forEach(function(k) {
        var p = z[k];
        if (!p || !p[period]) return;
        var rows = captureSliceRows(p[period], period, win);
        var xs = rows.map(function(r) {
            if (period === 'yearly')  return String(r.year);
            if (period === 'monthly') return r.year + '-' + String(r.month).padStart(2, '0');
            return r.date;
        });
        var ys = rows.map(function(r) { return r.ratio != null ? r.ratio * 100 : null; });
        var color = profileColor(k);
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
    renderBessDimReturnsChart();
    renderBessIncrementalChart();
    renderBessUpliftPctChart();
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
        var color = profileColor(k);
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
        var color = profileColor(k);
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

// ----- Sol+BESS · Diminishing returns (chart A) ---------------------------
function renderBessDimReturnsChart() {
    var zone = BESS_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var solOnly = z['sol_only'] && z['sol_only'].yearly;
    var h1 = z['sol_bess_1h'] && z['sol_bess_1h'].yearly;
    var h2 = z['sol_bess_2h'] && z['sol_bess_2h'].yearly;
    var h3 = z['sol_bess_3h'] && z['sol_bess_3h'].yearly;
    var h4 = z['sol_bess_4h'] && z['sol_bess_4h'].yearly;
    if (!solOnly || !h1 || !h2 || !h3 || !h4) {
        Plotly.purge('bess-dimret-chart');
        el('bess-dimret-chart').innerHTML = '<div class="empty-note">No sol+BESS data.</div>';
        return;
    }
    // Build {year: {sol_only, h1..h4}}
    var byYear = {};
    function add(arr, key) { arr.forEach(function(r) {
        byYear[r.year] = byYear[r.year] || { year: r.year };
        byYear[r.year][key] = r.capture;
    }); }
    add(solOnly, 'sol_only'); add(h1, 'h1'); add(h2, 'h2'); add(h3, 'h3'); add(h4, 'h4');

    // Determine partial years: yearly aggregate from monthly; assume current year is partial
    var nowYear = new Date().getFullYear();
    var years = Object.keys(byYear).map(Number).sort(function(a,b){return a-b;});
    // Skip pure-partial first year if it has zero capture (e.g. 2021 only Oct-Dec — already shown)
    // We render every year; partial years use dotted line.

    // Sequential teal palette (oldest = darkest, newest = lightest), current year accent.
    var palette = ['#0d9488', '#14b8a6', '#2dd4bf', '#5eead4', '#7BD7C8', '#A8E6DA'];
    var xs = [0, 1, 2, 3, 4];
    var xLabels = ['Sol only', '+1h', '+2h', '+3h', '+4h'];

    var traces = [];
    years.forEach(function(year, i) {
        var row = byYear[year];
        if (row.sol_only == null || row.h1 == null) return;
        var ys = [row.sol_only, row.h1, row.h2, row.h3, row.h4];
        var partial = (year === nowYear);
        var color = (year === nowYear) ? '#92B53D' : palette[Math.min(i, palette.length - 1)];
        traces.push({
            x: xs, y: ys,
            name: partial ? (year + ' YTD') : String(year),
            mode: 'lines+markers',
            type: 'scatter',
            line: { color: color, width: 2.4, shape: 'spline', dash: partial ? 'dot' : 'solid' },
            marker: { size: 8, color: color, line: { color: '#FFFFFF', width: 1.5 }, symbol: partial ? 'diamond' : 'circle' },
            hovertemplate: '<b>' + year + (partial ? ' YTD' : '') + '</b><br>%{text}: <b>%{y:.1f}</b> EUR/MWh<extra></extra>',
            text: xLabels,
        });
    });

    Plotly.react('bess-dimret-chart', traces, makeLayout({
        xaxis: Object.assign({}, PLOTLY_BASE.xaxis, {
            tickmode: 'array', tickvals: xs, ticktext: xLabels,
            gridcolor: 'transparent',
        }),
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'Capture EUR/MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 70, l: 64, r: 24 },
    }), PLOTLY_CFG);
}

// ----- Sol+BESS · Incremental stacked bars (chart B) ----------------------
function renderBessIncrementalChart() {
    var zone = BESS_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var solOnly = z['sol_only'] && z['sol_only'].yearly;
    var h1 = z['sol_bess_1h'] && z['sol_bess_1h'].yearly;
    var h2 = z['sol_bess_2h'] && z['sol_bess_2h'].yearly;
    var h3 = z['sol_bess_3h'] && z['sol_bess_3h'].yearly;
    var h4 = z['sol_bess_4h'] && z['sol_bess_4h'].yearly;
    if (!solOnly || !h1 || !h2 || !h3 || !h4) {
        Plotly.purge('bess-incr-chart');
        el('bess-incr-chart').innerHTML = '<div class="empty-note">No sol+BESS data.</div>';
        return;
    }
    var byYear = {};
    function add(arr, key) { arr.forEach(function(r) {
        byYear[r.year] = byYear[r.year] || { year: r.year, baseload: r.baseload };
        byYear[r.year][key] = r.capture;
    }); }
    add(solOnly, 'sol_only'); add(h1, 'h1'); add(h2, 'h2'); add(h3, 'h3'); add(h4, 'h4');

    var nowYear = new Date().getFullYear();
    var years = Object.keys(byYear).map(Number).sort(function(a,b){return a-b;});
    var labels = years.map(function(y) { return y === nowYear ? (y + ' YTD') : String(y); });

    var seg_sol = years.map(function(y) { return byYear[y].sol_only || 0; });
    var seg_1h  = years.map(function(y) { return Math.max(0, (byYear[y].h1 || 0) - (byYear[y].sol_only || 0)); });
    var seg_2h  = years.map(function(y) { return Math.max(0, (byYear[y].h2 || 0) - (byYear[y].h1 || 0)); });
    var seg_3h  = years.map(function(y) { return Math.max(0, (byYear[y].h3 || 0) - (byYear[y].h2 || 0)); });
    var seg_4h  = years.map(function(y) { return Math.max(0, (byYear[y].h4 || 0) - (byYear[y].h3 || 0)); });
    var baseload = years.map(function(y) { return byYear[y].baseload != null ? byYear[y].baseload : null; });

    var traces = [
        { x: labels, y: seg_sol, type: 'bar', name: 'Sol only',
          marker: { color: '#9A958C' },
          hovertemplate: '<b>%{x}</b><br>Sol only: <b>%{y:.1f}</b> EUR/MWh<extra></extra>' },
        { x: labels, y: seg_1h, type: 'bar', name: '+1st hour',
          marker: { color: '#5eead4' },
          hovertemplate: '<b>%{x}</b><br>1st hour adds: <b>+%{y:.1f}</b><extra></extra>' },
        { x: labels, y: seg_2h, type: 'bar', name: '+2nd hour',
          marker: { color: '#2dd4bf' },
          hovertemplate: '<b>%{x}</b><br>2nd hour adds: <b>+%{y:.1f}</b><extra></extra>' },
        { x: labels, y: seg_3h, type: 'bar', name: '+3rd hour',
          marker: { color: '#14b8a6' },
          hovertemplate: '<b>%{x}</b><br>3rd hour adds: <b>+%{y:.1f}</b><extra></extra>' },
        { x: labels, y: seg_4h, type: 'bar', name: '+4th hour',
          marker: { color: '#0d9488' },
          hovertemplate: '<b>%{x}</b><br>4th hour adds: <b>+%{y:.1f}</b><extra></extra>' },
        { x: labels, y: baseload, type: 'scatter', mode: 'markers', name: 'Baseload',
          marker: { color: '#1A1814', symbol: 'line-ew-open', size: 28, line: { width: 2.4 } },
          hovertemplate: '<b>%{x}</b><br>Baseload: <b>%{y:.1f}</b> EUR/MWh<extra></extra>' },
    ];

    Plotly.react('bess-incr-chart', traces, makeLayout({
        barmode: 'stack',
        bargap: 0.35,
        xaxis: Object.assign({}, PLOTLY_BASE.xaxis, { gridcolor: 'transparent' }),
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'Capture EUR/MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 70, l: 64, r: 24 },
    }), PLOTLY_CFG);
}

// ----- Sol+BESS · Uplift % over time (chart C) ----------------------------
function renderBessUpliftPctChart() {
    var zone = BESS_STATE.zone;
    var z = (DATA.data && DATA.data[zone]) || {};
    var solOnly = z['sol_only'] && z['sol_only'].monthly;
    if (!solOnly || !solOnly.length) {
        Plotly.purge('bess-uplift-chart');
        el('bess-uplift-chart').innerHTML = '<div class="empty-note">No sol+BESS data.</div>';
        return;
    }
    // Index sol-only by year-month for uplift calc
    function key(r) { return r.year + '-' + String(r.month).padStart(2, '0'); }
    var solMap = {};
    solOnly.forEach(function(r) { solMap[key(r)] = r.capture; });

    // Mask months with sol_only <= 5 EUR/MWh — division becomes unstable.
    var validKeys = Object.keys(solMap).filter(function(k) { return solMap[k] > 5; }).sort();
    if (!validKeys.length) {
        Plotly.purge('bess-uplift-chart');
        el('bess-uplift-chart').innerHTML = '<div class="empty-note">No sol+BESS data above noise floor.</div>';
        return;
    }

    function rolling(arr, w) {
        w = w || 3;
        var half = Math.floor(w / 2);
        return arr.map(function(_, i) {
            var start = Math.max(0, i - half);
            var end = Math.min(arr.length, i + half + 1);
            var slice = arr.slice(start, end).filter(function(v) { return v != null; });
            if (!slice.length) return null;
            return slice.reduce(function(a,b){return a+b;}, 0) / slice.length;
        });
    }

    function buildSeries(profKey) {
        var prof = z[profKey] && z[profKey].monthly;
        if (!prof) return null;
        var profMap = {};
        prof.forEach(function(r) { profMap[key(r)] = r.capture; });
        var raw = validKeys.map(function(k) {
            var sol = solMap[k]; var bat = profMap[k];
            if (sol == null || bat == null || sol <= 0) return null;
            return ((bat - sol) / sol) * 100;
        });
        return rolling(raw, 3);
    }

    var traces = [];
    [['sol_bess_1h', 'Sol+BESS 1h', '#5eead4', 1.8],
     ['sol_bess_2h', 'Sol+BESS 2h', '#2dd4bf', 2.0],
     ['sol_bess_3h', 'Sol+BESS 3h', '#14b8a6', 2.0],
     ['sol_bess_4h', 'Sol+BESS 4h', '#0d9488', 2.4]].forEach(function(spec) {
        var ys = buildSeries(spec[0]);
        if (!ys) return;
        traces.push({
            x: validKeys, y: ys, name: spec[1],
            type: 'scatter', mode: 'lines',
            line: { color: spec[2], width: spec[3], shape: 'spline' },
            hovertemplate: '%{x}<br>' + spec[1] + ': <b>+%{y:.1f}%</b> vs sol-only<extra></extra>',
        });
    });
    // Reference line at 0 % (sol-only baseline)
    traces.push({
        x: validKeys, y: validKeys.map(function() { return 0; }),
        name: 'Sol only', type: 'scatter', mode: 'lines',
        line: { color: '#9A958C', width: 1.4, dash: 'dash' },
        hoverinfo: 'skip',
    });

    Plotly.react('bess-uplift-chart', traces, makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, {
            title: { text: 'Uplift over sol-only', font: PLOTLY_BASE.yaxis.title.font },
            ticksuffix: ' %',
        }),
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
        var color = profileColor(k);
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
var FUTURES_STATE = { zone: 'SE3', convergenceContract: null };

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
    document.querySelectorAll('.futures-zone-seg').forEach(function(seg) {
        seg.innerHTML = zoneOpts;
        seg.querySelectorAll('button').forEach(function(b) {
            b.onclick = function() { FUTURES_STATE.zone = b.dataset.zone; renderFutures(); };
        });
    });

    renderFuturesKPIs(fwd);
    renderSysForwardChart(fwd);
    renderZoneForwardVsRealisedChart(fwd);
    renderEpadChart(fwd);
    renderForwardTable(fwd);
    renderConvergenceChart(fwd);
    renderLookbackTable(fwd);
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

function _futuresCategoryArray(fwd) {
    var contracts = (fwd.contracts || []).slice();
    var allContracts = (fwd.expired_contracts || []).concat(contracts);
    allContracts.sort(function(a, b) {
        var s = (a.start || '').localeCompare(b.start || '');
        if (s !== 0) return s;
        var ra = a.type === 'quarter' ? 0 : 1;
        var rb = b.type === 'quarter' ? 0 : 1;
        return ra - rb;
    });
    return allContracts.map(function(c) { return c.label; });
}

function renderSysForwardChart(fwd) {
    var contracts = (fwd.contracts || []).slice();
    var labels = contracts.map(function(c) { return c.label; });
    var sysSeries = labels.map(function(l) { return (fwd.sys && fwd.sys[l] != null) ? fwd.sys[l] : null; });
    var traces = [
        { x: labels, y: sysSeries, name: 'SYS baseload', mode: 'lines+markers', type: 'scatter', line: { color: '#2E5C4D', width: 2, shape: 'spline' }, marker: { size: 6 }, hovertemplate: '%{x}<br>SYS: <b>%{y:.2f}</b> EUR/MWh<extra></extra>' },
    ];
    Plotly.react('futures-sys-chart', traces, makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EUR / MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 86, l: 64, r: 24 },
        xaxis: Object.assign({}, PLOTLY_BASE.xaxis, { tickangle: -45, type: 'category', categoryorder: 'array', categoryarray: _futuresCategoryArray(fwd) }),
        showlegend: false,
    }), PLOTLY_CFG);
}

function renderZoneForwardVsRealisedChart(fwd) {
    var zone = FUTURES_STATE.zone;
    var contracts = (fwd.contracts || []).slice();
    var labels = contracts.map(function(c) { return c.label; });

    var sysSeries  = labels.map(function(l) { return (fwd.sys && fwd.sys[l] != null) ? fwd.sys[l] : null; });
    var epadSeries = labels.map(function(l) { return (fwd.epad && fwd.epad[zone] && fwd.epad[zone][l] != null) ? fwd.epad[zone][l] : null; });
    var zoneSeries = labels.map(function(l, i) { return (sysSeries[i] != null && epadSeries[i] != null) ? sysSeries[i] + epadSeries[i] : null; });

    var realLabels = (fwd.expired_contracts || []).map(function(c) { return c.label; });
    var realSeries = realLabels.map(function(l) { return (fwd.spot_realized[zone] && fwd.spot_realized[zone][l]) ? fwd.spot_realized[zone][l].spot_avg : null; });

    var traces = [
        { x: labels, y: zoneSeries, name: zone + ' implied', mode: 'lines+markers', type: 'scatter', line: { color: '#C16E40', width: 2, shape: 'spline' }, marker: { size: 6 }, hovertemplate: '%{x}<br>' + zone + ': <b>%{y:.2f}</b> EUR/MWh<extra></extra>' },
    ];
    if (realLabels.length) {
        traces.push({ x: realLabels, y: realSeries, name: 'Realised ' + zone, type: 'scatter', mode: 'markers', marker: { color: '#B14F75', size: 9, symbol: 'diamond' }, hovertemplate: '%{x}<br>Realised: <b>%{y:.2f}</b> EUR/MWh<extra></extra>' });
    }
    Plotly.react('futures-zone-chart', traces, makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EUR / MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 86, l: 64, r: 24 },
        xaxis: Object.assign({}, PLOTLY_BASE.xaxis, { tickangle: -45, type: 'category', categoryorder: 'array', categoryarray: _futuresCategoryArray(fwd) }),
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
    rows.sort(function(a, b) { return (a.start || '').localeCompare(b.start || ''); });

    var head = '<thead><tr>' +
        '<th>Contract</th>' +
        '<th>Start</th>' +
        '<th>End</th>' +
        '<th class="num">SYS</th>' +
        '<th class="num">EPAD ' + zone + '</th>' +
        '<th class="num">Implied ' + zone + '</th>' +
        '</tr></thead>';
    function rowHtml(r) {
        return '<tr>' +
            '<td>' + htmlEsc(r.label) + '</td>' +
            '<td class="muted">' + htmlEsc(r.start || '') + '</td>' +
            '<td class="muted">' + htmlEsc(r.end || '') + '</td>' +
            '<td class="num">' + fmtNum(r.sys, 2) + '</td>' +
            '<td class="num">' + fmtNum(r.epad, 2) + '</td>' +
            '<td class="num"><b>' + fmtNum(r.zone, 2) + '</b></td>' +
            '</tr>';
    }
    function buildBody(filteredRows) {
        if (!filteredRows.length) {
            return '<tbody><tr><td colspan="6" class="muted" style="text-align:center;padding:24px">No active contracts.</td></tr></tbody>';
        }
        return '<tbody>' + filteredRows.map(rowHtml).join('') + '</tbody>';
    }

    var quarterRows = rows.filter(function(r) { return r.type === 'quarter'; });
    var yearRows = rows.filter(function(r) { return r.type === 'year'; });

    el('futures-table-quarter').innerHTML = head + buildBody(quarterRows);
    el('futures-table-year').innerHTML = head + buildBody(yearRows);
}

// ---- Forward convergence + lookback ----

function _convergenceContractList(fwd) {
    var hist = fwd.forward_history || {};
    var labels = Object.keys(hist);
    labels.sort(function(a, b) {
        return (hist[a].delivery_start || '').localeCompare(hist[b].delivery_start || '');
    });
    return labels;
}

function _findFixNear(series, targetDate, windowDays) {
    if (!series || !series.length) return null;
    var target = new Date(targetDate).getTime();
    var bestRow = null;
    var bestDiff = Infinity;
    for (var i = 0; i < series.length; i++) {
        var d = new Date(series[i].date).getTime();
        var diff = Math.abs(d - target);
        if (diff <= windowDays * 86400000 && diff < bestDiff) {
            bestDiff = diff;
            bestRow = series[i];
        }
    }
    return bestRow;
}

function _shiftIso(iso, months) {
    var d = new Date(iso);
    d.setMonth(d.getMonth() - months);
    return d.toISOString().slice(0, 10);
}

function renderConvergenceChart(fwd) {
    var hist = fwd.forward_history || {};
    var labels = _convergenceContractList(fwd);
    if (!labels.length) {
        Plotly.purge('futures-convergence-chart');
        el('convergence-contract').innerHTML = '<option>—</option>';
        return;
    }

    if (!FUTURES_STATE.convergenceContract || !hist[FUTURES_STATE.convergenceContract]) {
        // Default to most recent delivered contract, else most recent overall.
        var todayIso = new Date().toISOString().slice(0, 10);
        var delivered = labels.filter(function(l) { return hist[l].delivery_end < todayIso; });
        FUTURES_STATE.convergenceContract = delivered.length
            ? delivered[delivered.length - 1]
            : labels[labels.length - 1];
    }

    // Populate selector
    var sel = el('convergence-contract');
    sel.innerHTML = labels.map(function(l) {
        return '<option value="' + l + '"' + (l === FUTURES_STATE.convergenceContract ? ' selected' : '') + '>' + htmlEsc(l) + '</option>';
    }).join('');
    sel.onchange = function() {
        FUTURES_STATE.convergenceContract = sel.value;
        renderConvergenceChart(fwd);
    };

    var contract = hist[FUTURES_STATE.convergenceContract];
    var zone = FUTURES_STATE.zone;

    var sysSeries = contract.sys_series || [];
    var epadSeries = (contract.epad_series && contract.epad_series[zone]) || [];

    // Build implied series by joining SYS and EPAD on date
    var epadByDate = {};
    epadSeries.forEach(function(r) { epadByDate[r.date] = r.price; });
    var impliedDates = [];
    var impliedPrices = [];
    sysSeries.forEach(function(r) {
        if (epadByDate[r.date] != null) {
            impliedDates.push(r.date);
            impliedPrices.push(r.price + epadByDate[r.date]);
        }
    });

    var realised = (contract.realised_spot && contract.realised_spot[zone] != null)
        ? contract.realised_spot[zone] : null;

    var traces = [
        {
            x: sysSeries.map(function(r) { return r.date; }),
            y: sysSeries.map(function(r) { return r.price; }),
            name: 'SYS forward',
            type: 'scatter', mode: 'lines',
            line: { color: '#2E5C4D', width: 2 },
            hovertemplate: '%{x}<br>SYS: <b>%{y:.2f}</b> EUR/MWh<extra></extra>',
        },
        {
            x: impliedDates,
            y: impliedPrices,
            name: zone + ' implied',
            type: 'scatter', mode: 'lines',
            line: { color: '#C16E40', width: 2 },
            hovertemplate: '%{x}<br>' + zone + ' implied: <b>%{y:.2f}</b> EUR/MWh<extra></extra>',
        },
    ];

    var shapes = [
        {
            type: 'line', xref: 'x', yref: 'paper',
            x0: contract.delivery_start, x1: contract.delivery_start,
            y0: 0, y1: 1,
            line: { color: '#999', width: 1, dash: 'dot' },
        },
    ];
    var annotations = [
        {
            x: contract.delivery_start, y: 1, xref: 'x', yref: 'paper',
            text: 'Delivery starts', showarrow: false,
            font: { size: 10, color: '#666' },
            xanchor: 'left', yanchor: 'top', xshift: 4,
        },
    ];

    if (realised != null) {
        traces.push({
            x: [contract.delivery_start, contract.delivery_end],
            y: [realised, realised],
            name: 'Realised ' + zone,
            type: 'scatter', mode: 'lines+markers',
            line: { color: '#B14F75', width: 2, dash: 'dash' },
            marker: { color: '#B14F75', size: 9, symbol: 'diamond' },
            hovertemplate: '%{x}<br>Realised: <b>%{y:.2f}</b> EUR/MWh<extra></extra>',
        });
    }

    // Sub-title: warn if final is stale
    var sub = 'Daily settlement path for ' + FUTURES_STATE.convergenceContract +
        ', delivery ' + contract.delivery_start + ' → ' + contract.delivery_end +
        '. Final fix ' + (contract.final_settlement_date || '–') + '.';
    if (contract.is_clean_final === false) {
        var lastDate = new Date(contract.final_settlement_date);
        var startDate = new Date(contract.delivery_start);
        var daysGap = Math.round((startDate - lastDate) / 86400000);
        sub += ' ⚠ Last fix ' + daysGap + ' days before delivery — possible coverage gap.';
    }
    el('convergence-sub').textContent = sub;

    Plotly.react('futures-convergence-chart', traces, makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EUR / MWh', font: PLOTLY_BASE.yaxis.title.font } }),
        xaxis: Object.assign({}, PLOTLY_BASE.xaxis, { title: { text: 'Settlement date', font: PLOTLY_BASE.xaxis.title.font } }),
        margin: { t: 12, b: 60, l: 64, r: 24 },
        shapes: shapes,
        annotations: annotations,
    }), PLOTLY_CFG);
}

function renderLookbackTable(fwd) {
    var hist = fwd.forward_history || {};
    var todayIso = new Date().toISOString().slice(0, 10);
    var labels = _convergenceContractList(fwd);
    var zones = ['SE1', 'SE2', 'SE3', 'SE4'];
    var lookbacks = [
        { key: 'tm12', label: 'T-12mo', months: 12 },
        { key: 'tm6',  label: 'T-6mo',  months: 6 },
        { key: 'tm3',  label: 'T-3mo',  months: 3 },
        { key: 'tm1',  label: 'T-1mo',  months: 1 },
    ];

    var rows = [];
    labels.forEach(function(label) {
        var c = hist[label];
        var deliveredOrInDelivery = c.delivery_start <= todayIso;
        if (!deliveredOrInDelivery) return;
        zones.forEach(function(zone) {
            var sysSeries = c.sys_series || [];
            var epadSeries = (c.epad_series && c.epad_series[zone]) || [];
            var epadByDate = {};
            epadSeries.forEach(function(r) { epadByDate[r.date] = r.price; });
            // Implied series for lookback math
            var impliedSeries = sysSeries.filter(function(r) { return epadByDate[r.date] != null; })
                .map(function(r) { return { date: r.date, price: r.price + epadByDate[r.date] }; });
            var sysFinalSeries = sysSeries.length
                ? [{ date: sysSeries[sysSeries.length - 1].date, price: sysSeries[sysSeries.length - 1].price + (epadByDate[sysSeries[sysSeries.length - 1].date] || 0) }]
                : [];
            // Final value: last available implied (falling back to "—" if no overlap)
            var finalRow = impliedSeries.length ? impliedSeries[impliedSeries.length - 1] : null;

            var realised = (c.realised_spot && c.realised_spot[zone] != null)
                ? c.realised_spot[zone] : null;

            var row = {
                contract: label,
                zone: zone,
                final: finalRow ? finalRow.price : null,
                realised: realised,
                delivery_start: c.delivery_start,
            };
            lookbacks.forEach(function(lb) {
                var target = _shiftIso(c.delivery_start, lb.months);
                var hit = _findFixNear(impliedSeries, target, 7);
                row[lb.key] = hit ? hit.price : null;
            });
            row.error_eur = (row.final != null && row.realised != null)
                ? row.final - row.realised : null;
            row.error_pct = (row.error_eur != null && row.realised)
                ? (row.error_eur / row.realised * 100) : null;
            rows.push(row);
        });
    });
    rows.sort(function(a, b) {
        var s = (b.delivery_start || '').localeCompare(a.delivery_start || '');
        if (s !== 0) return s;
        return a.zone.localeCompare(b.zone);
    });

    function colorFor(absErr) {
        if (absErr == null) return '';
        if (absErr < 5)  return 'color:var(--good)';
        if (absErr < 15) return 'color:var(--warn)';
        return 'color:var(--bad)';
    }
    function fmt(v, dp) { return v == null ? '—' : v.toFixed(dp || 2); }

    var head = '<thead><tr>' +
        '<th>Contract</th><th>Zone</th>' +
        lookbacks.map(function(lb) { return '<th class="num">' + lb.label + '</th>'; }).join('') +
        '<th class="num">Final</th><th class="num">Realised</th>' +
        '<th class="num">Error €/MWh</th><th class="num">Error %</th>' +
        '</tr></thead>';

    var body = '<tbody>' + rows.map(function(r) {
        var absErr = r.error_eur != null ? Math.abs(r.error_eur) : null;
        var style = colorFor(absErr);
        return '<tr>' +
            '<td>' + htmlEsc(r.contract) + '</td>' +
            '<td>' + r.zone + '</td>' +
            lookbacks.map(function(lb) { return '<td class="num">' + fmt(r[lb.key]) + '</td>'; }).join('') +
            '<td class="num">' + fmt(r.final) + '</td>' +
            '<td class="num">' + fmt(r.realised) + '</td>' +
            '<td class="num" style="' + style + '">' + (r.error_eur == null ? '—' : (r.error_eur > 0 ? '+' : '') + r.error_eur.toFixed(2)) + '</td>' +
            '<td class="num" style="' + style + '">' + (r.error_pct == null ? '—' : (r.error_pct > 0 ? '+' : '') + r.error_pct.toFixed(1) + '%') + '</td>' +
            '</tr>';
    }).join('') + '</tbody>';

    el('futures-lookback-table').innerHTML = head + body;
}


// ============================================================
//  ASSETS TAB
// ============================================================
var ASSETS = (DATA && DATA.assets) ? DATA.assets : null;
var ASSETS_STATE = {
    mode: 'fleet',
    selectedPark: null,
    zone: 'ALL',
    tableParks: null,
    period: { granularity: 'month', year: null, month: null },
    drillPeriod: { granularity: 'month', year: null, month: null }
};
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

function freshnessIndicator(isoTs) {
    if (!isoTs) return '';
    var t = Date.parse(isoTs);
    if (isNaN(t)) return '';
    var ageH = (Date.now() - t) / 3600000;
    if (ageH <= 36) return '';
    var cls, label;
    if (ageH <= 96) { cls = 'warn'; label = Math.round(ageH) + 'h since last data'; }
    else { cls = 'bad'; label = Math.round(ageH / 24) + 'd since last data'; }
    return ' <span class="freshness-dot ' + cls + '" title="' + label + '" aria-label="' + label + '"></span>';
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

function pad2(n) { return String(n).padStart(2, '0'); }
function latestYM() {
    if (!ASSETS || !ASSETS.parks) return null;
    var maxYr = null, maxMo = null;
    Object.values(ASSETS.parks).forEach(function(p) {
        (p.months || []).forEach(function(m) {
            if (maxYr === null || m.year > maxYr || (m.year === maxYr && m.month > maxMo)) {
                maxYr = m.year; maxMo = m.month;
            }
        });
    });
    return maxYr === null ? null : { year: maxYr, month: maxMo };
}
function latestMonthKey() {
    var ym = latestYM();
    return ym ? (ym.year + '-' + pad2(ym.month)) : null;
}
function currentMonthOfYear() {
    var ym = latestYM();
    return ym ? ym.month : 12;
}
function availableYears() {
    if (!ASSETS || !ASSETS.parks) return [];
    var s = {};
    Object.values(ASSETS.parks).forEach(function(p) {
        (p.months || []).forEach(function(m) { s[m.year] = true; });
    });
    return Object.keys(s).map(function(y) { return parseInt(y, 10); }).sort(function(a, b) { return a - b; });
}
function availableMonthsInYear(yr) {
    if (!ASSETS || !ASSETS.parks) return [];
    var s = {};
    Object.values(ASSETS.parks).forEach(function(p) {
        (p.months || []).forEach(function(m) { if (m.year === yr) s[m.month] = true; });
    });
    return Object.keys(s).map(function(n) { return parseInt(n, 10); }).sort(function(a, b) { return a - b; });
}
function monthsInYearKeys(yr) {
    return availableMonthsInYear(yr).map(function(mo) { return yr + '-' + pad2(mo); });
}
function ensurePeriodInit() {
    var p = ASSETS_STATE.period;
    if (p.year !== null && p.month !== null) return;
    var ym = latestYM();
    if (!ym) return;
    p.granularity = p.granularity || 'month';
    p.year = ym.year;
    p.month = ym.month;
}
function periodKeys(p) {
    p = p || ASSETS_STATE.period;
    if (!p || p.year == null) return [];
    if (p.granularity === 'month') {
        return p.month != null ? [p.year + '-' + pad2(p.month)] : [];
    }
    if (p.granularity === 'year') {
        return monthsInYearKeys(p.year);
    }
    if (p.granularity === 'ytd') {
        var endMonth = currentMonthOfYear();
        return monthsInYearKeys(p.year).filter(function(k) {
            return parseInt(k.split('-')[1], 10) <= endMonth;
        });
    }
    return [];
}
function expectedMonthsForPeriod(p) {
    p = p || ASSETS_STATE.period;
    if (!p || p.year == null) return 0;
    if (p.granularity === 'month') return 1;
    if (p.granularity === 'year') {
        // expected = months in calendar year that are <= today's reference (closed years = 12)
        var ymRef = latestYM();
        if (!ymRef) return 12;
        if (p.year < ymRef.year) return 12;
        if (p.year === ymRef.year) return ymRef.month;
        return 0;
    }
    if (p.granularity === 'ytd') return currentMonthOfYear();
    return 0;
}
function formatPeriodSuffix(p) {
    p = p || ASSETS_STATE.period;
    if (!p || p.year == null) return '';
    var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    if (p.granularity === 'month') {
        return p.month != null ? monthNames[p.month - 1] + ' ' + p.year : String(p.year);
    }
    if (p.granularity === 'year') {
        return 'Full year ' + p.year;
    }
    if (p.granularity === 'ytd') {
        var keys = periodKeys(p);
        if (!keys.length) return 'YTD ' + p.year + ' (no data)';
        var firstMo = parseInt(keys[0].split('-')[1], 10);
        var lastMo  = parseInt(keys[keys.length - 1].split('-')[1], 10);
        if (firstMo === lastMo) return 'YTD ' + p.year + ' (' + monthNames[firstMo - 1] + ')';
        return 'YTD ' + p.year + ' (' + monthNames[firstMo - 1] + '–' + monthNames[lastMo - 1] + ')';
    }
    return '';
}
function showPeriodToast(msg) {
    var t = el('assets-period-toast');
    if (!t) return;
    t.textContent = msg;
    t.hidden = false;
    if (t._timer) clearTimeout(t._timer);
    t._timer = setTimeout(function() {
        t.hidden = true;
        t.textContent = '';
        t._timer = null;
    }, 4500);
}
function filteredEntries() {
    var entries = Object.entries((ASSETS && ASSETS.parks) || {});
    if (ASSETS_STATE.zone !== 'ALL') entries = entries.filter(function(e) { return e[1].zone === ASSETS_STATE.zone; });
    return entries;
}
function parkMonth(park, key) {
    return (park.months || []).find(function(m) { return (m.year + '-' + String(m.month).padStart(2, '0')) === key; });
}
function aggregatePark(park, keys) {
    if (!keys || !keys.length) return null;
    var rows = (park.months || []).filter(function(m) {
        return keys.indexOf(m.year + '-' + pad2(m.month)) !== -1;
    });
    if (!rows.length) return null;

    var sum = function(field) {
        var s = 0, has = false;
        rows.forEach(function(r) { if (r[field] != null) { s += r[field]; has = true; } });
        return has ? s : null;
    };
    var weightedAvg = function(field, weightField) {
        var num = 0, den = 0;
        rows.forEach(function(r) {
            if (r[field] != null && r[weightField] != null) {
                num += r[field] * r[weightField];
                den += r[weightField];
            }
        });
        return den > 0 ? (num / den) : null;
    };

    var energy = sum('energy_mwh');
    var budget = sum('budget_mwh');
    var vsBudget = (budget != null && budget > 0 && energy != null)
        ? 100 * (energy - budget) / budget
        : null;

    var irrActual = sum('actual_irr_kwh_m2');
    var irrBudget = sum('budget_irr_kwh_m2');
    var vsBudgetIrr = (irrBudget != null && irrBudget > 0 && irrActual != null)
        ? 100 * (irrActual - irrBudget) / irrBudget
        : null;

    var capacity = park.capacity_mwp || 0;
    var yieldKwhKwp = (capacity > 0 && energy != null) ? (energy / capacity) : null;

    var revenue = sum('revenue_eur');
    var bzVolume = sum('bazefield_volume_mwh');
    var realizedCapture = (revenue != null && bzVolume != null && bzVolume > 0)
        ? (revenue / bzVolume) : null;

    return {
        period_keys: keys,
        months_present: rows.length,
        rows: rows,
        energy_mwh: energy,
        budget_mwh: budget,
        vs_budget_pct: vsBudget,
        neg_price_hours: sum('neg_price_hours'),
        neg_price_volume_mwh: sum('neg_price_volume_mwh'),
        actual_irr_kwh_m2: irrActual,
        budget_irr_kwh_m2: irrBudget,
        vs_budget_irr_pct: vsBudgetIrr,
        yield_kwh_kwp: yieldKwhKwp,
        pr_pct: weightedAvg('pr_pct', 'energy_mwh'),
        actual_pr_pct: weightedAvg('actual_pr_pct', 'energy_mwh'),
        budget_pr_pct: weightedAvg('budget_pr_pct', 'energy_mwh'),
        availability_pct: weightedAvg('availability_pct', 'energy_mwh'),
        revenue_eur: revenue,
        bazefield_volume_mwh: bzVolume,
        realized_capture_eur_mwh: realizedCapture,
        baseload_eur_mwh: weightedAvg('baseload_eur_mwh', 'bazefield_volume_mwh')
    };
}
function partialDataDot(agg, expected) {
    if (!agg) return '';
    if (expected <= 1) return '';
    if (agg.months_present >= expected) return '';
    return '<span class="partial-data-dot" title="' + agg.months_present + ' of ' + expected + ' months present"></span>';
}

function renderFleetMode() {
    el('fleet-mode').hidden = false;
    el('drill-mode').hidden = true;
    var bar = el('assets-period-bar');
    if (bar) bar.hidden = false;

    ensurePeriodInit();
    bindPeriodControls();
    refreshPeriodControls();

    var keys = periodKeys();
    var expected = expectedMonthsForPeriod();
    el('assets-period-suffix').textContent = formatPeriodSuffix();
    updatePartialDataBanner(keys, expected);

    renderFleetKPIs(keys, expected);
    renderParkGrid(keys, expected);
    renderParkChips();
    renderParkTable(keys, expected);
}

function bindPeriodControls() {
    var gran = el('assets-granularity');
    if (gran && !gran.dataset.bound) {
        gran.querySelectorAll('button').forEach(function(b) {
            b.addEventListener('click', function() {
                var newGran = b.dataset.gran;
                if (newGran === ASSETS_STATE.period.granularity) return;
                ASSETS_STATE.period.granularity = newGran;
                if (newGran === 'month') {
                    var avail = availableMonthsInYear(ASSETS_STATE.period.year);
                    if (avail.length && avail.indexOf(ASSETS_STATE.period.month) === -1) {
                        ASSETS_STATE.period.month = avail[avail.length - 1];
                    }
                }
                renderFleetMode();
            });
        });
        gran.dataset.bound = '1';
    }
    var prev = el('assets-year-prev');
    var next = el('assets-year-next');
    if (prev && !prev.dataset.bound) {
        prev.addEventListener('click', function() { stepYear(-1); });
        prev.dataset.bound = '1';
    }
    if (next && !next.dataset.bound) {
        next.addEventListener('click', function() { stepYear(1); });
        next.dataset.bound = '1';
    }
    var monthSel = el('assets-month-sel');
    if (monthSel && !monthSel.dataset.bound) {
        monthSel.addEventListener('change', function() {
            var v = parseInt(monthSel.value, 10);
            if (!isNaN(v)) ASSETS_STATE.period.month = v;
            renderFleetMode();
        });
        monthSel.dataset.bound = '1';
    }
    var zoneSel = el('assets-zone-sel');
    if (zoneSel && !zoneSel.dataset.bound) {
        zoneSel.value = ASSETS_STATE.zone;
        zoneSel.addEventListener('change', function() {
            ASSETS_STATE.zone = zoneSel.value;
            renderFleetMode();
        });
        zoneSel.dataset.bound = '1';
    }
}
function stepYear(direction) {
    var years = availableYears();
    if (!years.length) return;
    var idx = years.indexOf(ASSETS_STATE.period.year);
    if (idx === -1) idx = years.length - 1;
    var newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= years.length) return;
    var newYear = years[newIdx];
    var oldMonth = ASSETS_STATE.period.month;
    ASSETS_STATE.period.year = newYear;
    if (ASSETS_STATE.period.granularity === 'month') {
        var avail = availableMonthsInYear(newYear);
        if (!avail.length) {
            renderFleetMode();
            return;
        }
        if (avail.indexOf(oldMonth) === -1) {
            // snap to latest available month in new year
            var snapped = avail[avail.length - 1];
            ASSETS_STATE.period.month = snapped;
            var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            showPeriodToast('Snapped to ' + newYear + '-' + pad2(snapped) +
                ' — ' + monthNames[oldMonth - 1] + ' ' + newYear + ' missing.');
        }
    }
    renderFleetMode();
}
function refreshPeriodControls() {
    var p = ASSETS_STATE.period;
    el('assets-granularity').querySelectorAll('button').forEach(function(b) {
        b.setAttribute('aria-selected', b.dataset.gran === p.granularity ? 'true' : 'false');
        b.setAttribute('aria-pressed', b.dataset.gran === p.granularity ? 'true' : 'false');
    });
    el('assets-year-value').textContent = p.year != null ? String(p.year) : '—';
    var years = availableYears();
    var yIdx = years.indexOf(p.year);
    el('assets-year-prev').disabled = (yIdx <= 0);
    el('assets-year-next').disabled = (yIdx === -1 || yIdx >= years.length - 1);
    var monthWrap = el('assets-month-wrap');
    var monthSel = el('assets-month-sel');
    if (p.granularity === 'month') {
        monthWrap.style.display = '';
        var avail = availableMonthsInYear(p.year);
        var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        monthSel.innerHTML = avail.map(function(mo) {
            return '<option value="' + mo + '"' + (mo === p.month ? ' selected' : '') + '>' +
                monthNames[mo - 1] + ' (' + p.year + '-' + pad2(mo) + ')</option>';
        }).join('');
    } else {
        monthWrap.style.display = 'none';
    }
    var zoneSel = el('assets-zone-sel');
    if (zoneSel) zoneSel.value = ASSETS_STATE.zone;
}
function updatePartialDataBanner(keys, expected) {
    var t = el('assets-period-toast');
    if (!t) return;
    // Don't override an active snap-toast (it has its own timeout)
    if (t._timer) return;
    var gran = ASSETS_STATE.period.granularity;
    if (gran === 'month' || !keys || keys.length === 0 || keys.length >= expected) {
        t.hidden = true;
        t.textContent = '';
        return;
    }
    var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var have = keys.map(function(k) { return parseInt(k.split('-')[1], 10); });
    var missing = [];
    for (var mo = 1; mo <= expected; mo++) { if (have.indexOf(mo) === -1) missing.push(monthNames[mo - 1]); }
    if (!missing.length) {
        t.hidden = true;
        t.textContent = '';
        return;
    }
    t.textContent = formatPeriodSuffix() + ' · ' + keys.length + ' of ' + expected +
        ' months (missing: ' + missing.join(', ') + ').';
    t.hidden = false;
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
            renderParkTable(periodKeys(), expectedMonthsForPeriod());
        });
    });
    var resetBtn = el('park-chips-reset');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            ASSETS_STATE.tableParks = null;
            renderParkChips();
            renderParkTable(periodKeys(), expectedMonthsForPeriod());
        });
    }
}

function renderFleetKPIs(keys, expected) {
    var entries = filteredEntries();
    if (!entries.length) {
        el('fleet-kpis').innerHTML = '<div class="kpi"><div class="kpi-label">No parks</div><div class="kpi-value">—</div></div>';
        return;
    }
    var totalCap = 0, totalActual = 0, totalBudget = 0, totalNeg = 0;
    var totalRevenue = 0, totalVolume = 0, totalBaseloadWeighted = 0;
    var anyData = false, hasRevenue = false;
    entries.forEach(function(e) {
        var p = e[1];
        totalCap += (p.capacity_mwp || 0);
        var agg = aggregatePark(p, keys);
        if (agg) {
            anyData = true;
            if (agg.energy_mwh != null) totalActual += agg.energy_mwh;
            if (agg.budget_mwh != null) totalBudget += agg.budget_mwh;
            if (agg.neg_price_hours != null) totalNeg += agg.neg_price_hours;
            if (agg.revenue_eur != null) { totalRevenue += agg.revenue_eur; hasRevenue = true; }
            if (agg.bazefield_volume_mwh != null) totalVolume += agg.bazefield_volume_mwh;
            if (agg.baseload_eur_mwh != null && agg.bazefield_volume_mwh != null) {
                totalBaseloadWeighted += agg.baseload_eur_mwh * agg.bazefield_volume_mwh;
            }
        }
    });
    var vsBudget = totalBudget > 0 ? 100 * (totalActual - totalBudget) / totalBudget : null;
    var vsCls = vsClass(vsBudget);
    var pillHtml = vsBudget != null ? '<span class="pill ' + vsCls + '">' + fmtPct(vsBudget) + '</span>' : '<span class="pill neutral">–</span>';

    var fleetCapture = (totalVolume > 0 && hasRevenue) ? (totalRevenue / totalVolume) : null;
    var fleetBaseload = (totalVolume > 0) ? (totalBaseloadWeighted / totalVolume) : null;
    var capturePremium = (fleetCapture != null && fleetBaseload != null && fleetBaseload !== 0)
        ? (fleetCapture / fleetBaseload - 1) * 100 : null;
    var premiumPill = capturePremium != null
        ? '<span class="pill ' + vsClass(capturePremium) + '">' + fmtPct(capturePremium, 1) + ' vs baseload</span>'
        : '<span class="pill neutral">–</span>';

    var suffix = formatPeriodSuffix();
    var energyLabel = 'Energy · ' + suffix;
    var negLabel = 'Negative-price hours · ' + suffix;
    var energySub = anyData ? ('Budget: ' + fmtNum(totalBudget, 0) + ' MWh') : 'No data for period';

    var revenueTile = '<div class="kpi"><div class="kpi-label">Revenue · ' + suffix + '</div>' +
        '<div><span class="kpi-value">' +
        (hasRevenue ? fmtNum(totalRevenue / 1000, 0) : '–') +
        '</span><span class="kpi-unit">k€</span></div>' +
        '<div class="kpi-sub">' + (hasRevenue ? fmtNum(totalVolume, 0) + ' MWh sold' : 'no spot data') + '</div></div>';

    var captureTile = '<div class="kpi"><div class="kpi-label">Realized capture</div>' +
        '<div><span class="kpi-value">' +
        (fleetCapture != null ? fmtNum(fleetCapture, 1) : '–') +
        '</span><span class="kpi-unit">€/MWh</span></div>' +
        '<div class="kpi-sub">' + premiumPill + '</div></div>';

    var tiles = [
        kpiTile('Parks', String(entries.length), '', 'Active in fleet view'),
        kpiTile('Installed capacity', fmtNum(totalCap, 1), 'MWp', 'DC, sum across selection'),
        kpiTile(energyLabel, anyData ? fmtNum(totalActual, 0) : '–', 'MWh', energySub),
        revenueTile,
        captureTile,
        '<div class="kpi"><div class="kpi-label">vs Budget</div><div class="kpi-value">' + (vsBudget != null ? fmtPct(vsBudget) : '–') + '</div><div class="kpi-sub">' + pillHtml + '</div></div>',
        kpiTile(negLabel, anyData ? fmtNum(totalNeg, 0) : '–', 'h', 'Sum across selection'),
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

function renderParkGrid(keys, expected) {
    var entries = filteredEntries();
    if (!entries.length) {
        el('park-grid').innerHTML = '<div class="empty-note">No parks match this filter.</div>';
        return;
    }
    el('park-grid').innerHTML = entries.map(function(e) {
        var pk = e[0], p = e[1];
        var agg = aggregatePark(p, keys);
        var vs = agg ? agg.vs_budget_pct : null;
        var cls = vsClass(vs);
        var pillHtml = vs != null ? '<span class="pill ' + cls + '">' + fmtPct(vs) + '</span>' : '<span class="pill neutral">–</span>';
        var dot = partialDataDot(agg, expected);
        return '<div class="park-tile ' + cls + '" data-park="' + htmlEsc(pk) + '" tabindex="0" role="button">' +
            '<div class="park-tile-head">' +
                '<div class="park-tile-name">' + htmlEsc(p.name || pk) + dot + freshnessIndicator(p.last_data_ts) + '</div>' +
                '<div class="park-tile-zone">' + htmlEsc(p.zone || '') + '</div>' +
            '</div>' +
            '<div class="park-tile-stat"><span class="park-tile-stat-k">Capacity</span><span class="park-tile-stat-v">' + fmtNum(p.capacity_mwp, 2) + ' MWp</span></div>' +
            '<div class="park-tile-stat"><span class="park-tile-stat-k">Energy</span><span class="park-tile-stat-v">' + (agg && agg.energy_mwh != null ? fmtNum(agg.energy_mwh, 0) + ' MWh' : '–') + '</span></div>' +
            '<div class="park-tile-stat"><span class="park-tile-stat-k">Budget</span><span class="park-tile-stat-v">' + (agg && agg.budget_mwh != null ? fmtNum(agg.budget_mwh, 0) + ' MWh' : '–') + '</span></div>' +
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

function tableRows(keys, expected) {
    var sel = tableParkSet();
    return filteredEntries().filter(function(e) {
        return sel === null || sel.indexOf(e[0]) !== -1;
    }).map(function(e) {
        var pk = e[0], p = e[1];
        var agg = aggregatePark(p, keys);
        return {
            key: pk, name: p.name || pk, zone: p.zone || '',
            capacity_mwp: p.capacity_mwp || 0,
            energy_mwh: agg ? agg.energy_mwh : null,
            budget_mwh: agg ? agg.budget_mwh : null,
            vs_budget_pct: agg ? agg.vs_budget_pct : null,
            yield_kwh_kwp: agg ? agg.yield_kwh_kwp : null,
            actual_irr_kwh_m2: agg ? agg.actual_irr_kwh_m2 : null,
            vs_budget_irr_pct: agg ? agg.vs_budget_irr_pct : null,
            pr_pct: agg ? agg.actual_pr_pct : null,
            availability_pct: agg ? agg.availability_pct : null,
            revenue_eur: agg ? agg.revenue_eur : null,
            capture_eur_mwh: agg ? agg.realized_capture_eur_mwh : null,
            baseload_eur_mwh: agg ? agg.baseload_eur_mwh : null,
            months_present: agg ? agg.months_present : 0,
            months_expected: expected || 1,
            last_data_ts: p.last_data_ts || null
        };
    });
}

function renderParkTable(keys, expected) {
    var rows = tableRows(keys, expected);
    var dir = TABLE_STATE.sortDir === 'asc' ? 1 : -1;
    var sk = TABLE_STATE.sortKey;
    rows.sort(function(a, b) {
        var av = a[sk], bv = b[sk];
        if (av == null) return 1;
        if (bv == null) return -1;
        if (typeof av === 'string') return dir * av.localeCompare(bv);
        return dir * (av - bv);
    });
    var suffix = formatPeriodSuffix();
    var energyLabel = 'MWh · ' + suffix;
    var nameFormatter = function(v) {
        // we render the partial-data dot via separate column-data on the row
        return htmlEsc(v);
    };
    var cols = [
        { k: 'name',          label: 'Park',            fmt: nameFormatter, cls: '', html: true, withDot: true, withFreshness: true },
        { k: 'zone',          label: 'Zone',            fmt: htmlEsc, cls: '' },
        { k: 'capacity_mwp',  label: 'Cap MWp',         fmt: function(v) { return fmtNum(v, 2); }, cls: 'num' },
        { k: 'energy_mwh',    label: energyLabel,       fmt: function(v) { return fmtNum(v, 0); }, cls: 'num' },
        { k: 'vs_budget_pct', label: 'vs Budget',       fmt: function(v) { if (v == null) return '–'; var c = vsClass(v); return '<span class="pill ' + c + '">' + fmtPct(v) + '</span>'; }, cls: 'num', html: true },
        { k: 'pr_pct',        label: 'PR %',            fmt: function(v) { return v == null ? '–' : fmtNum(v, 1); }, cls: 'num' },
        { k: 'availability_pct', label: 'Avail %',      fmt: function(v) { return v == null ? '–' : fmtNum(v, 1); }, cls: 'num' },
        { k: 'capture_eur_mwh', label: 'Capture €/MWh', fmt: function(v) { return v == null ? '–' : fmtNum(v, 1); }, cls: 'num' },
        { k: 'revenue_eur',   label: 'Revenue k€',      fmt: function(v) { return v == null ? '–' : fmtNum(v / 1000, 1); }, cls: 'num' },
        { k: 'actual_irr_kwh_m2', label: 'Irr (kWh/m²)', fmt: function(v) { return fmtNum(v, 1); }, cls: 'num' },
        { k: 'vs_budget_irr_pct', label: 'vs Bdg',      fmt: function(v) { if (v == null) return '–'; var c = vsClass(v); return '<span class="pill ' + c + '">' + fmtPct(v) + '</span>'; }, cls: 'num', html: true },
        { k: 'yield_kwh_kwp', label: 'Yield kWh/kWp',   fmt: function(v) { return fmtNum(v, 1); }, cls: 'num' },
    ];
    var head = '<thead><tr>' + cols.map(function(c) {
        var sortAttr = (c.k === sk) ? (dir > 0 ? 'ascending' : 'descending') : 'none';
        var arrow = (sortAttr === 'ascending' ? '▲' : (sortAttr === 'descending' ? '▼' : '◇'));
        return '<th class="' + (c.cls || '') + '" data-key="' + htmlEsc(c.k) + '" aria-sort="' + sortAttr + '">' + htmlEsc(c.label) + ' <span class="arrow">' + arrow + '</span></th>';
    }).join('') + '</tr></thead>';
    var body = '<tbody>' + rows.map(function(r) {
        var dot = (r.months_expected > 1 && r.months_present < r.months_expected && r.months_present > 0)
            ? '<span class="partial-data-dot" title="' + r.months_present + ' of ' + r.months_expected + ' months present"></span>'
            : '';
        var fresh = freshnessIndicator(r.last_data_ts);
        return '<tr data-park="' + htmlEsc(r.key) + '">' +
            cols.map(function(c) {
                var v = r[c.k];
                var disp = c.fmt ? c.fmt(v) : (v == null ? '–' : v);
                if (c.withDot) disp = disp + dot;
                if (c.withFreshness) disp = disp + fresh;
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
            renderParkTable(keys, expected);
        });
    });
    t.querySelectorAll('tbody tr').forEach(function(tr) {
        tr.addEventListener('click', function() { openDrilldown(tr.dataset.park); });
    });
}

function exportParkCsv() {
    var keys = periodKeys();
    var expected = expectedMonthsForPeriod();
    var periodSlug = (function() {
        var p = ASSETS_STATE.period;
        if (p.granularity === 'month') return p.year + '-' + pad2(p.month);
        if (p.granularity === 'year') return p.year + '-FY';
        if (p.granularity === 'ytd') return p.year + '-YTD';
        return 'period';
    })();
    var header = ['Park','Zone','Capacity_MWp','Energy_MWh_' + periodSlug,'vs_Budget_pct',
                  'PR_pct','Availability_pct','Capture_EUR_MWh','Revenue_EUR','Baseload_EUR_MWh',
                  'Irr_kWh_m2','vs_Budget_Irr_pct','Yield_kWh_kWp','Months_present','Months_expected','Last_data_ts'];
    var rows = [header];
    tableRows(keys, expected).forEach(function(r) {
        rows.push([r.name, r.zone, r.capacity_mwp, r.energy_mwh, r.vs_budget_pct,
                   r.pr_pct, r.availability_pct, r.capture_eur_mwh, r.revenue_eur, r.baseload_eur_mwh,
                   r.actual_irr_kwh_m2, r.vs_budget_irr_pct, r.yield_kwh_kwp,
                   r.months_present, r.months_expected, r.last_data_ts]);
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
    a.download = 'park_comparison_' + periodSlug + '.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
}
window.exportParkCsv = exportParkCsv;

// ----- Drill-down -----
function openDrilldown(pk) {
    if (!pk || !ASSETS.parks[pk]) return;
    ASSETS_STATE.mode = 'drilldown';
    ASSETS_STATE.selectedPark = pk;

    var park = ASSETS.parks[pk];
    var p = ASSETS_STATE.period;
    var dp;
    if (p && p.year != null) {
        dp = { granularity: p.granularity || 'month', year: p.year, month: p.month };
    } else {
        var ym = latestYM();
        dp = ym ? { granularity: 'month', year: ym.year, month: ym.month }
                : { granularity: 'month', year: null, month: null };
    }
    // Snap month if park has no data for that month/year
    snapDrillPeriodToPark(park, dp);
    ASSETS_STATE.drillPeriod = dp;
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
function captureForPeriod(zone, keys) {
    if (!keys || !keys.length) return null;
    var sum = 0, n = 0;
    keys.forEach(function(k) {
        var v = captureForZoneMonth(zone, k);
        if (v != null) { sum += v; n += 1; }
    });
    return n > 0 ? (sum / n) : null;
}
function trackerGainForMonth(monthKey) {
    if (!ASSETS || !ASSETS.tracker_gain || !ASSETS.tracker_gain.monthly || !monthKey) return null;
    var yr = parseInt(monthKey.split('-')[0]);
    var mo = parseInt(monthKey.split('-')[1]);
    var rec = ASSETS.tracker_gain.monthly.find(function(r) { return r.year === yr && r.month === mo; });
    return rec && rec.gain_pct != null ? rec.gain_pct : null;
}
function trackerGainForPeriod(keys) {
    if (!keys || !keys.length) return null;
    var sum = 0, n = 0;
    keys.forEach(function(k) {
        var v = trackerGainForMonth(k);
        if (v != null) { sum += v; n += 1; }
    });
    return n > 0 ? (sum / n) : null;
}

// ----- Park-scoped period helpers -----
function parkAvailableYears(park) {
    var s = {};
    (park.months || []).forEach(function(m) { s[m.year] = true; });
    return Object.keys(s).map(function(y) { return parseInt(y, 10); }).sort(function(a, b) { return a - b; });
}
function parkAvailableMonthsInYear(park, yr) {
    var s = {};
    (park.months || []).forEach(function(m) { if (m.year === yr) s[m.month] = true; });
    return Object.keys(s).map(function(n) { return parseInt(n, 10); }).sort(function(a, b) { return a - b; });
}
function parkMonthsInYearKeys(park, yr) {
    return parkAvailableMonthsInYear(park, yr).map(function(mo) { return yr + '-' + pad2(mo); });
}
function drillPeriodKeys(park, dp) {
    dp = dp || ASSETS_STATE.drillPeriod;
    if (!dp || dp.year == null) return [];
    if (dp.granularity === 'month') {
        return dp.month != null ? [dp.year + '-' + pad2(dp.month)] : [];
    }
    if (dp.granularity === 'year') {
        return parkMonthsInYearKeys(park, dp.year);
    }
    if (dp.granularity === 'ytd') {
        var endMonth = currentMonthOfYear();
        return parkMonthsInYearKeys(park, dp.year).filter(function(k) {
            return parseInt(k.split('-')[1], 10) <= endMonth;
        });
    }
    return [];
}
function drillExpectedMonthsForPeriod(dp) {
    dp = dp || ASSETS_STATE.drillPeriod;
    if (!dp || dp.year == null) return 0;
    if (dp.granularity === 'month') return 1;
    if (dp.granularity === 'year') {
        var ymRef = latestYM();
        if (!ymRef) return 12;
        if (dp.year < ymRef.year) return 12;
        if (dp.year === ymRef.year) return ymRef.month;
        return 0;
    }
    if (dp.granularity === 'ytd') return currentMonthOfYear();
    return 0;
}
function drillFormatPeriodSuffix(park, dp) {
    dp = dp || ASSETS_STATE.drillPeriod;
    if (!dp || dp.year == null) return '';
    var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    if (dp.granularity === 'month') {
        return dp.month != null ? monthNames[dp.month - 1] + ' ' + dp.year : String(dp.year);
    }
    if (dp.granularity === 'year') {
        return 'Full year ' + dp.year;
    }
    if (dp.granularity === 'ytd') {
        var keys = drillPeriodKeys(park, dp);
        if (!keys.length) return 'YTD ' + dp.year + ' (no data)';
        var firstMo = parseInt(keys[0].split('-')[1], 10);
        var lastMo  = parseInt(keys[keys.length - 1].split('-')[1], 10);
        if (firstMo === lastMo) return 'YTD ' + dp.year + ' (' + monthNames[firstMo - 1] + ')';
        return 'YTD ' + dp.year + ' (' + monthNames[firstMo - 1] + '–' + monthNames[lastMo - 1] + ')';
    }
    return '';
}
function snapDrillPeriodToPark(park, dp) {
    var years = parkAvailableYears(park);
    if (!years.length) return;
    if (years.indexOf(dp.year) === -1) {
        dp.year = years[years.length - 1];
    }
    if (dp.granularity === 'month') {
        var avail = parkAvailableMonthsInYear(park, dp.year);
        if (!avail.length) {
            dp.year = years[years.length - 1];
            avail = parkAvailableMonthsInYear(park, dp.year);
        }
        if (avail.length && avail.indexOf(dp.month) === -1) {
            dp.month = avail[avail.length - 1];
        }
    }
}
function showDrillToast(msg) {
    var t = el('drill-period-toast');
    if (!t) return;
    t.textContent = msg;
    t.hidden = false;
    if (t._timer) clearTimeout(t._timer);
    t._timer = setTimeout(function() {
        t.hidden = true;
        t.textContent = '';
        t._timer = null;
    }, 4500);
}
function updateDrillPartialBanner(keys, expected, suffix) {
    var t = el('drill-period-toast');
    if (!t) return;
    if (t._timer) return;  // don't override active snap toast
    var gran = ASSETS_STATE.drillPeriod.granularity;
    if (gran === 'month' || !keys || keys.length === 0 || keys.length >= expected) {
        t.hidden = true;
        t.textContent = '';
        return;
    }
    var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var have = keys.map(function(k) { return parseInt(k.split('-')[1], 10); });
    var missing = [];
    for (var mo = 1; mo <= expected; mo++) { if (have.indexOf(mo) === -1) missing.push(monthNames[mo - 1]); }
    if (!missing.length) {
        t.hidden = true;
        t.textContent = '';
        return;
    }
    t.textContent = suffix + ' · ' + keys.length + ' of ' + expected +
        ' months (missing: ' + missing.join(', ') + ').';
    t.hidden = false;
}
function bindDrillPeriodControls() {
    var park = ASSETS.parks[ASSETS_STATE.selectedPark];
    if (!park) return;
    var gran = el('drill-granularity');
    if (gran && !gran.dataset.bound) {
        gran.querySelectorAll('button').forEach(function(b) {
            b.addEventListener('click', function() {
                var newGran = b.dataset.gran;
                if (newGran === ASSETS_STATE.drillPeriod.granularity) return;
                ASSETS_STATE.drillPeriod.granularity = newGran;
                if (newGran === 'month') {
                    var pk2 = ASSETS.parks[ASSETS_STATE.selectedPark];
                    var avail = parkAvailableMonthsInYear(pk2, ASSETS_STATE.drillPeriod.year);
                    if (avail.length && avail.indexOf(ASSETS_STATE.drillPeriod.month) === -1) {
                        ASSETS_STATE.drillPeriod.month = avail[avail.length - 1];
                    }
                }
                renderDrilldown();
            });
        });
        gran.dataset.bound = '1';
    }
    var prev = el('drill-year-prev');
    var next = el('drill-year-next');
    if (prev && !prev.dataset.bound) {
        prev.addEventListener('click', function() { stepDrillYear(-1); });
        prev.dataset.bound = '1';
    }
    if (next && !next.dataset.bound) {
        next.addEventListener('click', function() { stepDrillYear(1); });
        next.dataset.bound = '1';
    }
    var monthSel = el('drill-month-sel');
    if (monthSel && !monthSel.dataset.bound) {
        monthSel.addEventListener('change', function() {
            var v = parseInt(monthSel.value, 10);
            if (!isNaN(v)) ASSETS_STATE.drillPeriod.month = v;
            renderDrilldown();
        });
        monthSel.dataset.bound = '1';
    }
}
function stepDrillYear(direction) {
    var park = ASSETS.parks[ASSETS_STATE.selectedPark];
    if (!park) return;
    var years = parkAvailableYears(park);
    if (!years.length) return;
    var dp = ASSETS_STATE.drillPeriod;
    var idx = years.indexOf(dp.year);
    if (idx === -1) idx = years.length - 1;
    var newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= years.length) return;
    var newYear = years[newIdx];
    var oldMonth = dp.month;
    dp.year = newYear;
    if (dp.granularity === 'month') {
        var avail = parkAvailableMonthsInYear(park, newYear);
        if (!avail.length) { renderDrilldown(); return; }
        if (avail.indexOf(oldMonth) === -1) {
            var snapped = avail[avail.length - 1];
            dp.month = snapped;
            var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            showDrillToast('Snapped to ' + newYear + '-' + pad2(snapped) +
                ' — ' + monthNames[oldMonth - 1] + ' ' + newYear + ' missing.');
        }
    }
    renderDrilldown();
}
function refreshDrillPeriodControls(park) {
    var dp = ASSETS_STATE.drillPeriod;
    el('drill-granularity').querySelectorAll('button').forEach(function(b) {
        b.setAttribute('aria-selected', b.dataset.gran === dp.granularity ? 'true' : 'false');
        b.setAttribute('aria-pressed', b.dataset.gran === dp.granularity ? 'true' : 'false');
    });
    el('drill-year-value').textContent = dp.year != null ? String(dp.year) : '—';
    var years = parkAvailableYears(park);
    var yIdx = years.indexOf(dp.year);
    el('drill-year-prev').disabled = (yIdx <= 0);
    el('drill-year-next').disabled = (yIdx === -1 || yIdx >= years.length - 1);
    var monthWrap = el('drill-month-wrap');
    var monthSel = el('drill-month-sel');
    if (dp.granularity === 'month') {
        monthWrap.style.display = '';
        var avail = parkAvailableMonthsInYear(park, dp.year);
        var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        monthSel.innerHTML = avail.map(function(mo) {
            return '<option value="' + mo + '"' + (mo === dp.month ? ' selected' : '') + '>' +
                monthNames[mo - 1] + ' (' + dp.year + '-' + pad2(mo) + ')</option>';
        }).join('');
    } else {
        monthWrap.style.display = 'none';
    }
}
function daysInDrillPeriod(park, keys) {
    var out = [];
    keys.forEach(function(k) {
        var arr = (park.daily_by_month && park.daily_by_month[k]) || [];
        out = out.concat(arr);
    });
    out.sort(function(a, b) { return (a.date || '').localeCompare(b.date || ''); });
    return out;
}

function renderDrilldown() {
    var pk = ASSETS_STATE.selectedPark;
    var p = ASSETS.parks[pk];
    if (!p) return;
    el('fleet-mode').hidden = true;
    el('drill-mode').hidden = false;

    snapDrillPeriodToPark(p, ASSETS_STATE.drillPeriod);
    bindDrillPeriodControls();
    refreshDrillPeriodControls(p);

    var dp = ASSETS_STATE.drillPeriod;
    var keys = drillPeriodKeys(p, dp);
    var expected = drillExpectedMonthsForPeriod(dp);
    var suffix = drillFormatPeriodSuffix(p, dp);

    el('drill-name').textContent = p.name || pk;
    el('drill-period-suffix').textContent = suffix;
    el('drill-meta').innerHTML =
        '<span><span class="eyebrow">Zone</span> ' + htmlEsc(p.zone || '') + '</span>' +
        '<span><span class="eyebrow">Capacity</span> <span class="num">' + fmtNum(p.capacity_mwp, 2) + '</span> MWp</span>' +
        '<span><span class="eyebrow">Period</span> <span class="num">' + htmlEsc(suffix) + '</span></span>';

    updateDrillPartialBanner(keys, expected, suffix);

    // Aggregated KPIs
    var agg = aggregatePark(p, keys);
    var captureAgg = captureForPeriod(p.zone, keys);
    var trackerPctAgg = trackerGainForPeriod(keys);
    var isHova = (pk === 'hova');
    var trackerSub = (dp.granularity === 'month') ? 'vs SE3 fixed-tilt' : 'avg vs SE3 fixed-tilt';
    var trackerTile = isHova
        ? kpiTile('Tracker gain', trackerPctAgg != null ? fmtPct(trackerPctAgg, 1) : '–', '', trackerSub)
        : '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Tracker gain</div><div class="kpi-value">—</div><div class="kpi-sub">Hova only</div></div>';

    var pillHtml;
    if (agg && agg.vs_budget_pct != null) {
        pillHtml = '<span class="pill ' + vsClass(agg.vs_budget_pct) + '">' + fmtPct(agg.vs_budget_pct) + '</span>';
    } else {
        pillHtml = '<span class="pill neutral">–</span>';
    }
    var vsTile = '<div class="kpi"><div class="kpi-label">vs Budget</div><div class="kpi-value">' +
        (agg && agg.vs_budget_pct != null ? fmtPct(agg.vs_budget_pct) : '–') + '</div><div class="kpi-sub">' + pillHtml + '</div></div>';

    var irrTile;
    if (agg && agg.actual_irr_kwh_m2 != null) {
        var irrSubHtml;
        if (agg.vs_budget_irr_pct != null) {
            irrSubHtml = '<span class="pill ' + vsClass(agg.vs_budget_irr_pct) + '">' + fmtPct(agg.vs_budget_irr_pct) + '</span>';
        } else {
            irrSubHtml = '<span class="pill neutral">vs Budget –</span>';
        }
        irrTile = '<div class="kpi"><div class="kpi-label">POA Irradiation</div>' +
            '<div><span class="kpi-value">' + fmtNum(agg.actual_irr_kwh_m2, 1) + '</span><span class="kpi-unit">kWh/m²</span></div>' +
            '<div class="kpi-sub">' + irrSubHtml + '</div></div>';
    } else {
        irrTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">POA Irradiation</div>' +
            '<div class="kpi-value">—</div><div class="kpi-sub">no data</div></div>';
    }

    var captureSub = (dp.granularity === 'month') ? '' : 'monthly avg';
    var dot = (expected > 1 && agg && agg.months_present < expected && agg.months_present > 0)
        ? ' <span class="partial-data-dot" title="' + agg.months_present + ' of ' + expected + ' months present"></span>'
        : '';
    var energyTile = '<div class="kpi"><div class="kpi-label">Energy</div>' +
        '<div><span class="kpi-value">' + (agg && agg.energy_mwh != null ? fmtNum(agg.energy_mwh, 0) : '–') + '</span><span class="kpi-unit">MWh</span></div>' +
        '<div class="kpi-sub">' + htmlEsc(suffix) + dot + '</div></div>';

    var revenueTile;
    if (agg && agg.revenue_eur != null) {
        revenueTile = '<div class="kpi"><div class="kpi-label">Revenue</div>' +
            '<div><span class="kpi-value">' + fmtNum(agg.revenue_eur / 1000, 1) +
            '</span><span class="kpi-unit">k€</span></div>' +
            '<div class="kpi-sub">' + (agg.bazefield_volume_mwh != null ? fmtNum(agg.bazefield_volume_mwh, 0) + ' MWh sold' : '') + '</div></div>';
    } else {
        revenueTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Revenue</div><div class="kpi-value">—</div><div class="kpi-sub">no spot match</div></div>';
    }

    var realizedCap = agg ? agg.realized_capture_eur_mwh : null;
    var baseload = agg ? agg.baseload_eur_mwh : null;
    var realizedTile;
    if (realizedCap != null) {
        var vsZone = (captureAgg != null) ? (realizedCap - captureAgg) : null;
        var vsZonePill = vsZone != null
            ? '<span class="pill ' + vsClass(vsZone) + '">' + (vsZone >= 0 ? '+' : '') + fmtNum(vsZone, 1) + ' vs zone gen.</span>'
            : '<span class="pill neutral">vs zone –</span>';
        realizedTile = '<div class="kpi"><div class="kpi-label">Realized capture</div>' +
            '<div><span class="kpi-value">' + fmtNum(realizedCap, 1) + '</span><span class="kpi-unit">€/MWh</span></div>' +
            '<div class="kpi-sub">' + vsZonePill + '</div></div>';
    } else {
        realizedTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Realized capture</div><div class="kpi-value">—</div></div>';
    }

    var premiumTile;
    if (realizedCap != null && baseload != null && baseload !== 0) {
        var prem = (realizedCap / baseload - 1) * 100;
        var premPill = '<span class="pill ' + vsClass(prem) + '">' + fmtPct(prem, 1) + '</span>';
        premiumTile = '<div class="kpi"><div class="kpi-label">Baseload spot</div>' +
            '<div><span class="kpi-value">' + fmtNum(baseload, 1) + '</span><span class="kpi-unit">€/MWh</span></div>' +
            '<div class="kpi-sub">' + premPill + ' capture vs baseload</div></div>';
    } else {
        premiumTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Baseload spot</div><div class="kpi-value">—</div></div>';
    }

    var prTile;
    if (agg && agg.actual_pr_pct != null) {
        var dPr = (agg.budget_pr_pct != null) ? (agg.actual_pr_pct - agg.budget_pr_pct) : null;
        var prPill = dPr != null
            ? '<span class="pill ' + vsClass(dPr) + '">' + (dPr >= 0 ? '+' : '') + fmtNum(dPr, 1) + ' pp vs budget</span>'
            : '<span class="pill neutral">–</span>';
        prTile = '<div class="kpi"><div class="kpi-label">Performance Ratio</div>' +
            '<div><span class="kpi-value">' + fmtNum(agg.actual_pr_pct, 1) + '</span><span class="kpi-unit">%</span></div>' +
            '<div class="kpi-sub">' + prPill + '</div></div>';
    } else {
        prTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Performance Ratio</div><div class="kpi-value">—</div></div>';
    }

    var availTile;
    if (agg && agg.availability_pct != null) {
        availTile = '<div class="kpi"><div class="kpi-label">Availability</div>' +
            '<div><span class="kpi-value">' + fmtNum(agg.availability_pct, 1) + '</span><span class="kpi-unit">%</span></div>' +
            '<div class="kpi-sub">irradiance-weighted</div></div>';
    } else {
        availTile = '<div class="kpi" style="opacity:0.55"><div class="kpi-label">Availability</div><div class="kpi-value">—</div><div class="kpi-sub">no data</div></div>';
    }

    var tiles = [
        energyTile,
        revenueTile,
        realizedTile,
        premiumTile,
        vsTile,
        prTile,
        availTile,
        irrTile,
        kpiTile('Yield', agg && agg.yield_kwh_kwp != null ? fmtNum(agg.yield_kwh_kwp, 1) : '–', 'kWh/kWp', ''),
        kpiTile('Negative-price h', agg && agg.neg_price_hours != null ? fmtNum(agg.neg_price_hours, 0) : '–', 'h', agg && agg.neg_price_volume_mwh != null ? fmtNum(agg.neg_price_volume_mwh, 0) + ' MWh forgone' : ''),
        trackerTile,
    ];
    el('drill-kpis').innerHTML = tiles.join('');

    // Charts (Energy vs Budget, Yield, POA Irradiation are always last 13 months)
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

    // Daily chart spans the selected period
    var dailySub = el('drill-daily-sub');
    if (dailySub) dailySub.textContent = suffix + ' · actual vs expected.';
    var days = daysInDrillPeriod(p, keys);
    if (days.length) {
        var dxs = days.map(function(d) { return d.date; });
        Plotly.react('drill-daily-chart', [
            { x: dxs, y: days.map(function(d) { return d.energy_mwh; }), name: 'Actual', type: 'bar', marker: { color: '#2E5C4D' }, hovertemplate: '%{x}<br>Actual: <b>%{y:.2f}</b> MWh<extra></extra>' },
            { x: dxs, y: days.map(function(d) { return d.expected_mwh; }), name: 'Expected', type: 'scatter', mode: 'lines', line: { color: '#C16E40', dash: 'dash', width: 2 }, hovertemplate: '%{x}<br>Expected: <b>%{y:.2f}</b> MWh<extra></extra>' },
            { x: dxs, y: days.map(function(d) { return d.irradiation_kwh_m2; }), name: 'POA Irr', type: 'scatter', mode: 'lines', line: { color: '#C9A53C', width: 1.6, shape: 'spline' }, yaxis: 'y2', connectgaps: false, hovertemplate: '%{x}<br>POA Irr: <b>%{y:.2f}</b> kWh/m²<extra></extra>' },
            { x: dxs, y: days.map(function(d) { return d.pr_pct; }), name: 'PR %', type: 'scatter', mode: 'lines+markers', line: { color: '#5B6BA8', width: 1.8, shape: 'spline' }, marker: { size: 4 }, yaxis: 'y3', connectgaps: false, hovertemplate: '%{x}<br>PR: <b>%{y:.1f}</b> %<extra></extra>' },
        ], makeLayout({
            yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'MWh', font: PLOTLY_BASE.yaxis.title.font } }),
            yaxis2: Object.assign({}, PLOTLY_BASE.yaxis, {
                title: { text: 'kWh / m²', font: PLOTLY_BASE.yaxis.title.font },
                overlaying: 'y',
                side: 'right',
                gridcolor: 'transparent',
                showgrid: false,
            }),
            yaxis3: Object.assign({}, PLOTLY_BASE.yaxis, {
                title: { text: 'PR %', font: PLOTLY_BASE.yaxis.title.font },
                overlaying: 'y',
                side: 'right',
                position: 0.94,
                anchor: 'free',
                range: [0, 110],
                gridcolor: 'transparent',
                showgrid: false,
            }),
            margin: { t: 12, b: 70, l: 64, r: 96 },
        }), PLOTLY_CFG);
    } else {
        Plotly.purge('drill-daily-chart');
        el('drill-daily-chart').innerHTML = '<div class="empty-note">No daily data for ' + htmlEsc(suffix) + '.</div>';
    }

    Plotly.react('drill-capture-chart', [
        { x: xs, y: months.map(function(mm) { return mm.actual_irr_kwh_m2; }), type: 'scatter', mode: 'lines+markers', line: { color: '#C16E40', width: 2.4, shape: 'spline' }, marker: { size: 6 }, name: 'Actual', hovertemplate: '%{x}<br>Actual: <b>%{y:.1f}</b> kWh/m²<extra></extra>', connectgaps: false },
        { x: xs, y: months.map(function(mm) { return mm.budget_irr_kwh_m2; }), type: 'scatter', mode: 'lines+markers', line: { color: '#5B6BA8', width: 2, dash: 'dash', shape: 'spline' }, marker: { size: 5, symbol: 'square-open' }, name: 'Budget', hovertemplate: '%{x}<br>Budget: <b>%{y:.1f}</b> kWh/m²<extra></extra>' },
    ], makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'kWh / m²', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 12, b: 70, l: 64, r: 24 },
    }), PLOTLY_CFG);

    var bwSub = el('drill-bestworst-sub');
    if (bwSub) bwSub.textContent = suffix + ' · ranked by energy.';
    renderBestWorst(p, days, suffix);

    // Loss + revenue waterfalls
    bindLossModeControls();
    renderLossWaterfall(p, keys);
    renderRevenueWaterfall(p, keys);

    // About this park
    renderParkFacts(p);

    // Auto insight tagline
    var insight = buildInsightText(agg);
    var insightEl = el('drill-insight');
    if (insightEl) {
        insightEl.textContent = insight;
        insightEl.style.display = insight ? '' : 'none';
    }

    // Performance report link — only meaningful for a single month
    var linksHost = el('drill-links');
    if (dp.granularity === 'month' && dp.year != null && dp.month != null) {
        var monthKey = dp.year + '-' + pad2(dp.month);
        var reportPath = 'performance_' + pk + '_' + (p.zone || '') + '_' + monthKey + '.html';
        linksHost.innerHTML =
            '<a href="' + htmlEsc(reportPath) + '" target="_blank" rel="noopener">' + htmlEsc(reportPath) + '</a> <span class="muted">— if generated</span>';
    } else {
        linksHost.innerHTML = '<span class="muted">Per-month report — switch to Month view to open the standalone HTML report.</span>';
    }
}

var DRILL_LOSS_MODE = 'mwh';

function aggregateLosses(park, keys) {
    var fields = ['budget_mwh','actual_mwh','irradiance_shortfall_mwh',
                  'availability_mwh','curtailment_mwh','temperature_mwh','other_mwh'];
    var sums = {};
    fields.forEach(function(f) { sums[f] = 0; });
    var any = false;
    (park.months || []).forEach(function(m) {
        if (keys.indexOf(m.year + '-' + pad2(m.month)) === -1) return;
        if (!m.losses) return;
        any = true;
        fields.forEach(function(f) {
            var v = m.losses[f];
            if (v != null) sums[f] += v;
        });
    });
    return any ? sums : null;
}

function renderLossWaterfall(park, keys) {
    var host = el('drill-loss-chart');
    if (!host) return;
    var sums = aggregateLosses(park, keys);
    if (!sums) {
        Plotly.purge('drill-loss-chart');
        host.innerHTML = '<div class="empty-note">No loss data for selected period.</div>';
        return;
    }
    var budget = sums.budget_mwh;
    var labels = ['Budget', 'Irr shortfall', 'Availability', 'Curtailment', 'Temperature', 'Other', 'Actual'];
    var measures = ['absolute', 'relative', 'relative', 'relative', 'relative', 'relative', 'total'];
    var values, unit;
    if (DRILL_LOSS_MODE === 'mwh') {
        values = [
            budget,
            -sums.irradiance_shortfall_mwh,
            -sums.availability_mwh,
            -sums.curtailment_mwh,
            -sums.temperature_mwh,
            -sums.other_mwh,
            sums.actual_mwh,
        ];
        unit = 'MWh';
    } else {
        var pct = function(x) { return budget > 0 ? (x / budget * 100) : 0; };
        values = [
            100,
            -pct(sums.irradiance_shortfall_mwh),
            -pct(sums.availability_mwh),
            -pct(sums.curtailment_mwh),
            -pct(sums.temperature_mwh),
            -pct(sums.other_mwh),
            pct(sums.actual_mwh),
        ];
        unit = '%';
    }
    Plotly.react('drill-loss-chart', [{
        type: 'waterfall',
        x: labels,
        y: values,
        measure: measures,
        text: values.map(function(v) {
            return (DRILL_LOSS_MODE === 'mwh' ? fmtNum(v, 0) : fmtNum(v, 1)) + ' ' + unit;
        }),
        textposition: 'outside',
        connector: { line: { color: '#C0BBA8' } },
        increasing: { marker: { color: '#92B53D' } },
        decreasing: { marker: { color: '#B14E45' } },
        totals: { marker: { color: '#2E5C4D' } },
        hovertemplate: '%{x}<br><b>%{y:.1f}</b> ' + unit + '<extra></extra>',
    }], makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: unit, font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 24, b: 70, l: 64, r: 24 },
        showlegend: false,
    }), PLOTLY_CFG);
}

function bindLossModeControls() {
    var seg = el('drill-loss-mode');
    if (!seg || seg.dataset.bound) return;
    seg.querySelectorAll('button').forEach(function(b) {
        b.addEventListener('click', function() {
            var m = b.dataset.mode;
            if (m === DRILL_LOSS_MODE) return;
            DRILL_LOSS_MODE = m;
            seg.querySelectorAll('button').forEach(function(x) {
                x.setAttribute('aria-selected', x.dataset.mode === m ? 'true' : 'false');
                x.setAttribute('aria-pressed', x.dataset.mode === m ? 'true' : 'false');
            });
            var pk = ASSETS_STATE.selectedPark;
            var park = ASSETS.parks[pk];
            renderLossWaterfall(park, drillPeriodKeys(park));
        });
    });
    seg.dataset.bound = '1';
}

function renderRevenueWaterfall(park, keys) {
    var host = el('drill-revenue-chart');
    if (!host) return;
    var rows = (park.months || []).filter(function(m) {
        return keys.indexOf(m.year + '-' + pad2(m.month)) !== -1;
    });
    var hasRev = rows.some(function(r) { return r.revenue_eur != null; });
    if (!hasRev) {
        Plotly.purge('drill-revenue-chart');
        host.innerHTML = '<div class="empty-note">No revenue data for selected period (Bazefield × spot join unavailable).</div>';
        return;
    }
    var actualRev = 0, actualVol = 0, baselineWeighted = 0, baselineDen = 0;
    var budgetMwh = 0;
    rows.forEach(function(r) {
        if (r.revenue_eur != null) actualRev += r.revenue_eur;
        if (r.bazefield_volume_mwh != null) actualVol += r.bazefield_volume_mwh;
        if (r.budget_mwh != null) budgetMwh += r.budget_mwh;
        if (r.baseload_eur_mwh != null && r.bazefield_volume_mwh != null) {
            baselineWeighted += r.baseload_eur_mwh * r.bazefield_volume_mwh;
            baselineDen += r.bazefield_volume_mwh;
        }
    });
    var baseload = baselineDen > 0 ? baselineWeighted / baselineDen : null;
    if (baseload == null) {
        Plotly.purge('drill-revenue-chart');
        host.innerHTML = '<div class="empty-note">Insufficient baseload data for decomposition.</div>';
        return;
    }
    var capture = actualVol > 0 ? actualRev / actualVol : null;
    var budgetRev = budgetMwh * baseload;
    var volumeEffect = (actualVol - budgetMwh) * baseload;
    var priceEffect = (capture != null) ? actualVol * (capture - baseload) : 0;

    var labels = ['Budget rev.<br>(@baseload)', 'Volume effect', 'Price effect', 'Realized rev.'];
    var measures = ['absolute', 'relative', 'relative', 'total'];
    var values = [budgetRev, volumeEffect, priceEffect, actualRev];
    Plotly.react('drill-revenue-chart', [{
        type: 'waterfall',
        x: labels,
        y: values,
        measure: measures,
        text: values.map(function(v) { return fmtNum(v / 1000, 1) + ' k€'; }),
        textposition: 'outside',
        connector: { line: { color: '#C0BBA8' } },
        increasing: { marker: { color: '#92B53D' } },
        decreasing: { marker: { color: '#B14E45' } },
        totals: { marker: { color: '#2E5C4D' } },
        hovertemplate: '%{x}<br><b>%{y:,.0f}</b> €<extra></extra>',
    }], makeLayout({
        yaxis: Object.assign({}, PLOTLY_BASE.yaxis, { title: { text: 'EUR', font: PLOTLY_BASE.yaxis.title.font } }),
        margin: { t: 24, b: 70, l: 80, r: 24 },
        showlegend: false,
    }), PLOTLY_CFG);
}

function renderParkFacts(park) {
    var f = park && park.facts;
    var host = el('drill-facts-grid');
    if (!host) return;
    if (!f) { host.innerHTML = '<div class="empty-note">No metadata available.</div>'; return; }
    var rows = [
        ['Location', f.location || '–'],
        ['Commissioning', f.commissioning_date || '–'],
        ['Module', (f.module_type || '–') + (f.module_wp ? ' · ' + f.module_wp + ' Wp' : '')],
        ['# Modules', f.num_modules != null ? fmtNum(f.num_modules, 0) : '–'],
        ['Inverter', (f.inverter_manufacturer ? f.inverter_manufacturer + ' ' : '') + (f.inverter_model || '–')],
        ['# Inverters', f.num_inverters != null ? fmtNum(f.num_inverters, 0) : '–'],
        ['Tilt / Azimuth', (f.tilt_angle != null ? f.tilt_angle + '°' : '–') + ' / ' + (f.azimuth != null ? f.azimuth + '°' : '–')],
        ['Tracking', f.tracking ? (f.tracking_type || 'tracker') : 'Fixed'],
        ['AC capacity', f.ac_capacity_mwac != null ? fmtNum(f.ac_capacity_mwac, 2) + ' MWac' : '–'],
        ['Grid limit', f.grid_limit_mwac != null ? fmtNum(f.grid_limit_mwac, 2) + ' MWac' : '–'],
        ['Transformer', (f.transformer_count != null && f.transformer_capacity_kva != null)
            ? f.transformer_count + ' × ' + fmtNum(f.transformer_capacity_kva, 0) + ' kVA' : '–'],
        ['Expected PR', f.expected_pr_pct != null ? fmtNum(f.expected_pr_pct, 1) + ' %' : '–'],
        ['Expected yield', f.expected_annual_yield_kwh_kwp != null
            ? fmtNum(f.expected_annual_yield_kwh_kwp, 0) + ' kWh/kWp/yr' : '–'],
        ['PVsyst profile', f.profile_type || '–'],
    ];
    host.innerHTML = rows.map(function(r) {
        return '<div class="fact-cell"><div class="fact-k">' + htmlEsc(r[0]) +
            '</div><div class="fact-v">' + htmlEsc(String(r[1])) + '</div></div>';
    }).join('');
}

function buildInsightText(agg) {
    if (!agg) return '';
    var vs = agg.vs_budget_pct;
    if (vs == null) return '';
    var verdict;
    if (vs >= 5) verdict = 'Above budget';
    else if (vs <= -5) verdict = 'Below budget';
    else verdict = 'On budget';
    var dPr = (agg.actual_pr_pct != null && agg.budget_pr_pct != null)
        ? (agg.actual_pr_pct - agg.budget_pr_pct) : null;
    var dIrr = agg.vs_budget_irr_pct;
    var driver = '';
    if (dPr != null && Math.abs(dPr) >= 1) {
        driver += ' driven by PR ' + (dPr >= 0 ? '+' : '') + fmtNum(dPr, 1) + 'pp';
    }
    if (dIrr != null && Math.abs(dIrr) >= 2) {
        var conn;
        if (driver) {
            conn = (dPr != null && Math.sign(dPr) === Math.sign(dIrr)) ? ' and ' : ' despite ';
        } else {
            conn = ' driven by ';
        }
        driver += conn + 'irradiance ' + (dIrr >= 0 ? '+' : '') + fmtNum(dIrr, 1) + '%';
    }
    return verdict + driver + '.';
}

function renderBestWorst(p, days, suffix) {
    var c = el('drill-bestworst');
    if (!days || !days.length) {
        c.innerHTML = '<div class="empty-note">No daily data for ' + htmlEsc(suffix) + '.</div>';
        return;
    }
    var sorted = days.slice().sort(function(a, b) { return (b.energy_mwh || 0) - (a.energy_mwh || 0); });
    var top = sorted.slice(0, 5);
    var bottom = sorted.slice(-5).reverse();
    function tableHtml(title, rows, cls) {
        var head = '<thead><tr>' +
            '<th>Date</th><th>Day</th><th class="num">MWh</th><th class="num">Irr (kWh/m²)</th><th class="num">kWh/kWp</th>' +
            '</tr></thead>';
        var body = '<tbody>' + rows.map(function(r) {
            return '<tr>' +
                '<td>' + htmlEsc(r.date || '–') + '</td>' +
                '<td class="muted">' + htmlEsc(r.weekday || '') + '</td>' +
                '<td class="num">' + fmtNum(r.energy_mwh, 2) + '</td>' +
                '<td class="num">' + fmtNum(r.irradiation_kwh_m2, 1) + '</td>' +
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

        <div class="range-bar" id="capture-range-bar">
          <span class="label-control">Range <div class="seg" id="capture-range"></div></span>
          <span class="range-nav" id="capture-range-nav">
            <button type="button" class="range-arrow" id="capture-range-prev" aria-label="Previous window">‹</button>
            <span class="range-label" id="capture-range-label">All time</span>
            <button type="button" class="range-arrow" id="capture-range-next" aria-label="Next window">›</button>
            <button type="button" id="capture-range-now">Latest</button>
          </span>
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
        <div class="method-note">
          <span class="method-icon">i</span>
          <div>
            <span class="method-label">Methodology</span>
            All BESS figures assume <em>perfect-foresight</em> dynamic-programming optimisation against day-ahead spot, 88 % round-trip efficiency, 1 MW power per MW installed, no degradation or cycle cost. Sol+BESS is <em>behind-the-meter</em> only — the battery cannot charge from the grid, which limits the marginal value of 2h+ durations. Arbitrage and ancillary revenue are shown <em>separately</em>; in reality they can be stacked on the same asset.
          </div>
        </div>

        <div class="kpi-strip" id="bess-kpis"></div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Arbitrage revenue</div><div class="card-sub">Optimised intraday DP per MW installed power, monthly.</div></div>
          </div>
          <div class="chart chart-tall" id="bess-arb-chart"></div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Sol + storage capture</div><div class="card-sub">Capture uplift from co-located battery vs. sol-only — monthly time series, all durations.</div></div>
          </div>
          <div class="chart" id="bess-solbess-chart"></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-head">
              <div><div class="card-title">Diminishing returns per year</div><div class="card-sub">Capture price as a function of battery duration. Shows where the marginal value flattens.</div></div>
            </div>
            <div class="chart" id="bess-dimret-chart"></div>
          </div>
          <div class="card">
            <div class="card-head">
              <div><div class="card-title">Incremental battery value</div><div class="card-sub">Sol-only baseline plus the contribution of each additional battery hour, stacked per year.</div></div>
            </div>
            <div class="chart" id="bess-incr-chart"></div>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Battery uplift over time</div><div class="card-sub">Monthly uplift in % over sol-only — separates 1h / 2h / 3h / 4h clearly without absolute price noise.</div></div>
          </div>
          <div class="chart" id="bess-uplift-chart"></div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Ancillary services</div><div class="card-sub">FCR / aFRR / mFRR-CM clearing prices.</div></div>
          </div>
          <div class="chart" id="bess-anc-chart"></div>
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
      </header>
      <div id="futures-content">
        <div class="kpi-strip" id="futures-kpis"></div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">SYS baseload — forward curve</div><div class="card-sub">Nordic system price futures across active contracts.</div></div>
          </div>
          <div class="chart" id="futures-sys-chart"></div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Zone forward vs realised</div><div class="card-sub">Zone-implied (SYS + EPAD) and realised YTD spot for delivered contracts.</div></div>
            <div class="card-actions">
              <span class="label-control">Zone <div class="seg futures-zone-seg" data-target="zone"></div></span>
            </div>
          </div>
          <div class="chart" id="futures-zone-chart"></div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">EPAD differentials</div><div class="card-sub">All four zones, per contract.</div></div>
          </div>
          <div class="chart" id="futures-epad-chart"></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-head">
              <div><div class="card-title">Quarterly forwards</div><div class="card-sub">Active quarter contracts and their components.</div></div>
              <div class="card-actions">
                <span class="label-control">Zone <div class="seg futures-zone-seg" data-target="quarter"></div></span>
              </div>
            </div>
            <div style="overflow-x:auto">
              <table class="editorial" id="futures-table-quarter"></table>
            </div>
          </div>
          <div class="card">
            <div class="card-head">
              <div><div class="card-title">Yearly forwards</div><div class="card-sub">Active year contracts and their components.</div></div>
              <div class="card-actions">
                <span class="label-control">Zone <div class="seg futures-zone-seg" data-target="year"></div></span>
              </div>
            </div>
            <div style="overflow-x:auto">
              <table class="editorial" id="futures-table-year"></table>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Forward convergence</div><div class="card-sub" id="convergence-sub">Daily settlement path for a single delivered or pending contract, with realised spot.</div></div>
            <div class="card-actions">
              <span class="label-control">Contract <select id="convergence-contract"></select></span>
              <span class="label-control">Zone <div class="seg futures-zone-seg" data-target="convergence"></div></span>
            </div>
          </div>
          <div class="chart chart-tall" id="futures-convergence-chart"></div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><div class="card-title">Lookback — forward vs realised</div><div class="card-sub">Zone-implied price (SYS + EPAD) at fixed lookback intervals before delivery, and the realised spot.</div></div>
          </div>
          <div style="overflow-x:auto">
            <table class="editorial" id="futures-lookback-table"></table>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== ASSETS ===== -->
    <section class="page" id="page-assets" role="tabpanel" aria-labelledby="tab-assets" hidden>
      <div id="fleet-mode">
        <header class="page-head">
          <div class="page-head-left">
            <div class="page-eyebrow">Fleet</div>
            <h1 class="page-title">Asset Performance<span id="assets-period-suffix" class="page-title-suffix"></span></h1>
            <p class="page-sub">Per-park energy, yield and budget variance across the SveaSolar utility-scale fleet. Click any park to drill down.</p>
          </div>
        </header>

        <div class="period-bar" id="assets-period-bar" role="group" aria-label="Period filter">
          <div class="period-bar-left">
            <div class="seg" id="assets-granularity" role="tablist" aria-label="Granularity">
              <button type="button" data-gran="month" role="tab" aria-selected="false">Month</button>
              <button type="button" data-gran="ytd" role="tab" aria-selected="false">YTD</button>
              <button type="button" data-gran="year" role="tab" aria-selected="false">Year</button>
            </div>
            <div class="period-stepper" id="assets-year-stepper" aria-label="Year">
              <button type="button" id="assets-year-prev" aria-label="Previous year">◀</button>
              <span class="period-stepper-value" id="assets-year-value">—</span>
              <button type="button" id="assets-year-next" aria-label="Next year">▶</button>
            </div>
            <span class="label-control" id="assets-month-wrap">Month
              <select id="assets-month-sel"></select>
            </span>
          </div>
          <div class="period-bar-right">
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
        </div>

        <div class="period-toast" id="assets-period-toast" hidden></div>

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
            <h1 class="drill-name"><span id="drill-name"></span><span id="drill-period-suffix" class="page-title-suffix"></span></h1>
            <div class="drill-meta" id="drill-meta"></div>
            <div class="drill-insight" id="drill-insight"></div>
          </div>
        </div>

        <details class="park-facts" id="drill-facts">
          <summary>About this park</summary>
          <div class="facts-grid" id="drill-facts-grid"></div>
        </details>

        <div class="period-bar" id="drill-period-bar" role="group" aria-label="Period filter">
          <div class="period-bar-left">
            <div class="seg" id="drill-granularity" role="tablist" aria-label="Granularity">
              <button type="button" data-gran="month" role="tab" aria-selected="false">Month</button>
              <button type="button" data-gran="ytd" role="tab" aria-selected="false">YTD</button>
              <button type="button" data-gran="year" role="tab" aria-selected="false">Year</button>
            </div>
            <div class="period-stepper" id="drill-year-stepper" aria-label="Year">
              <button type="button" id="drill-year-prev" aria-label="Previous year">◀</button>
              <span class="period-stepper-value" id="drill-year-value">—</span>
              <button type="button" id="drill-year-next" aria-label="Next year">▶</button>
            </div>
            <span class="label-control" id="drill-month-wrap">Month
              <select id="drill-month-sel"></select>
            </span>
          </div>
        </div>

        <div class="period-toast" id="drill-period-toast" hidden></div>

        <div class="kpi-strip" id="drill-kpis"></div>

        <div class="drill-chart-grid">
          <div class="card">
            <div class="card-head"><div><div class="card-title">Energy vs Budget</div><div class="card-sub">Last 13 months.</div></div></div>
            <div class="chart" id="drill-energy-chart"></div>
          </div>
          <div class="card">
            <div class="card-head"><div><div class="card-title">Specific Yield</div><div class="card-sub">kWh / kWp · month.</div></div></div>
            <div class="chart" id="drill-yield-chart"></div>
          </div>
          <div class="card">
            <div class="card-head"><div><div class="card-title">Daily generation</div><div class="card-sub" id="drill-daily-sub">Selected period, actual vs expected.</div></div></div>
            <div class="chart" id="drill-daily-chart"></div>
          </div>
          <div class="card">
            <div class="card-head"><div><div class="card-title">POA Irradiation: Actual vs Budget</div><div class="card-sub">kWh / m² · month, last 13 months.</div></div></div>
            <div class="chart" id="drill-capture-chart"></div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-head">
              <div><div class="card-title">Loss analysis</div><div class="card-sub">Budget → Actual cascade by loss type.</div></div>
              <div class="card-actions">
                <div class="seg" id="drill-loss-mode" role="tablist" aria-label="Loss display mode">
                  <button type="button" data-mode="mwh" role="tab" aria-selected="true" aria-pressed="true">MWh</button>
                  <button type="button" data-mode="pct" role="tab" aria-selected="false" aria-pressed="false">%</button>
                </div>
              </div>
            </div>
            <div class="chart" id="drill-loss-chart"></div>
          </div>
          <div class="card">
            <div class="card-head"><div><div class="card-title">Revenue decomposition</div><div class="card-sub">Budget revenue → volume effect → price effect → realized.</div></div></div>
            <div class="chart" id="drill-revenue-chart"></div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><div><div class="card-title">Best &amp; worst days</div><div class="card-sub" id="drill-bestworst-sub">Selected period, ranked by energy.</div></div></div>
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
