"""Renderare för Insikt — slutsats först, grafen under är beviset.

Visuellt en vidareutveckling av Nordic Clarity (rework-dashboarden):
samma :root-tokens, kicker/takeaway/kpi-strip-mönster, Inter + Source
Serif 4, Plotly via CDN och IntersectionObserver-lazy-render. Data
injiceras som ``const DATA = __DATA_JSON__`` via
``dashboard_common.script_json``.

Arkitektur — sektionsregistret
------------------------------

Sidan byggs av :data:`SECTIONS`: en lista av ``(id, titel,
render-funktion)``. Varje render-funktion tar hela datastrukturen och
returnerar sektionens HTML-skelett (JS fyller innehållet från DATA).
Toppnavigeringen genereras ur registret. **Nya sektioner (marknad,
BESS, …) läggs till genom att appenda till SECTIONS** — stommen
(_shell, CSS, JS-helpers) röres inte. Sektionens JS registreras i
``RENDERERS`` (lazy via IntersectionObserver) eller körs i ``init()``.

Publik ingång::

    >>> from elpris.insikt.parkoversikt import build_parkoversikt_data
    >>> from elpris.insikt.render import render_insikt
    >>> html = render_insikt(build_parkoversikt_data())
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from ..dashboard_common import JS_HELPERS, esc, script_json


# ---------------------------------------------------------------------------
# Sektionsregister
# ---------------------------------------------------------------------------

def _render_section_parker(data: Dict[str, Any]) -> str:
    """Sektion 1: Parkerna — hero, league table, parkkort med drilldown."""
    return """
<section id="parker">
  <div class="sec-head">
    <div class="kicker">Insikt · Asset management</div>
    <h1>Parkerna</h1>
  </div>
  <div class="callouts" id="portfolio-insights"></div>
  <div class="kpi-strip" id="kpi-strip"></div>

  <div class="card league-card">
    <div class="card-head"><h3 id="league-title">Parkerna — senaste stängda månad</h3>
      <p>Sortera med klick på kolumnrubrik. Klicka på en rad för att hoppa till parkens kort.
         PR-gap = faktisk PR − budget-PR (procentenheter).</p></div>
    <div class="tbl-wrap" id="tbl-league"></div>
  </div>

  <div class="park-grid" id="park-grid"></div>
</section>
"""


#: (id, titel, render-funktion) — nav + <main> genereras härifrån.
SECTIONS: List[Tuple[str, str, Callable[[Dict[str, Any]], str]]] = [
    ("parker", "Parkerna", _render_section_parker),
]


def render_insikt(data: Dict[str, Any]) -> str:
    """Rendera Insikt som fristående HTML-sträng."""
    nav = "".join(
        f'<a href="#{esc(sid)}" data-sec="{esc(sid)}">{esc(title)}</a>'
        for sid, title, _ in SECTIONS
    )
    sections = "".join(fn(data) for _, _, fn in SECTIONS)

    html = _SHELL
    html = html.replace("__GENERATED__", esc(data.get("generated", "")))
    html = html.replace("__NAV__", nav)
    html = html.replace("__SECTIONS__", sections)
    html = html.replace("__CSS__", _CSS)
    html = html.replace("__DATA_JSON__", script_json(data))
    html = html.replace("__JS__", _JS.replace("__COMMON_HELPERS__", JS_HELPERS))
    return html


# ---------------------------------------------------------------------------
# HTML-skal
# ---------------------------------------------------------------------------

_SHELL = """<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Insikt — Parkerna</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%230e7c86'/%3E%3Cpath d='M8 22 13 14 18 18 24 9' stroke='%23de9b26' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>__CSS__</style>
</head>
<body>

<header class="topbar">
  <div class="brand">
    <span class="brand-mark"></span>
    <div>
      <div class="brand-title">Svea Solar · Insikt</div>
      <div class="brand-sub">Genererad __GENERATED__</div>
    </div>
  </div>
  <nav class="topnav" id="topnav">__NAV__</nav>
</header>

<main>
__SECTIONS__
</main>

<footer>
  <div class="foot-note">Svea Solar · Insikt · intern analys · genererad __GENERATED__ ·
    slutsatserna är regelgenererade ur PVsyst-budget, Bazefield-produktion och spotpriser.</div>
</footer>

<script>const DATA = __DATA_JSON__;</script>
<script>__JS__</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# CSS — Nordic Clarity, varsamt vidareutvecklad för Insikt
# ---------------------------------------------------------------------------

_CSS = r"""
:root {
  --bg: #f6f8f9;
  --card: #ffffff;
  --ink: #16242f;
  --muted: #5b6b78;
  --faint: #8a98a4;
  --line: #e3e9ed;
  --teal: #0e7c86;
  --teal-deep: #0a5961;
  --teal-soft: #d8ecee;
  --amber: #de9b26;
  --coral: #d95f4c;
  --green: #2e9e6b;
  --navy: #1d3a4f;
  --radius: 10px;
  --shadow: 0 1px 2px rgba(22,36,47,.05), 0 4px 16px rgba(22,36,47,.06);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 84px; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 14.5px; line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

/* ---------- Toppbar ---------- */
.topbar {
  position: sticky; top: 0; z-index: 50;
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 12px 28px;
  background: rgba(246,248,249,.88); backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: 12px; }
.brand-mark {
  width: 34px; height: 34px; border-radius: 9px; flex: 0 0 auto;
  background: conic-gradient(from 220deg, var(--teal-deep), var(--teal) 55%, var(--amber));
}
.brand-title { font-weight: 700; font-size: 15px; letter-spacing: -.01em; }
.brand-sub { font-size: 11.5px; color: var(--faint); }
.topnav { display: flex; gap: 2px; flex-wrap: wrap; }
.topnav a {
  padding: 7px 13px; border-radius: 8px; text-decoration: none;
  color: var(--muted); font-weight: 600; font-size: 13px;
}
.topnav a:hover { background: var(--teal-soft); color: var(--teal-deep); }
.topnav a.active { background: var(--navy); color: #fff; }

/* ---------- Layout ---------- */
main { max-width: 1240px; margin: 0 auto; padding: 12px 28px 80px; }
section { padding-top: 36px; }
.sec-head { max-width: 860px; margin-bottom: 14px; }
.kicker {
  text-transform: uppercase; letter-spacing: .14em; font-size: 11px;
  font-weight: 700; color: var(--teal); margin-bottom: 6px;
}
h1, h2 { margin: 0 0 10px; letter-spacing: -.02em; line-height: 1.15; }
h1 { font-size: 34px; font-weight: 800; }
h2 { font-size: 24px; font-weight: 800; }

/* ---------- Klartextinsikter (hero) ---------- */
.callouts { display: grid; gap: 10px; margin: 14px 0 8px; max-width: 980px; }
.callout {
  background: var(--card); border: 1px solid var(--line);
  border-left: 4px solid var(--teal); border-radius: 8px;
  padding: 11px 16px; font-family: 'Source Serif 4', serif;
  font-size: 15.5px; box-shadow: var(--shadow);
}
.callout.pos { border-left-color: var(--green); }
.callout.neg { border-left-color: var(--coral); }

/* ---------- KPI-strip ---------- */
.kpi-strip {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px; margin: 18px 0 22px;
}
.kpi {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 14px 16px; box-shadow: var(--shadow);
}
.kpi .lbl { font-size: 11px; text-transform: uppercase; letter-spacing: .09em;
  color: var(--faint); font-weight: 700; }
.kpi .val { font-size: 24px; font-weight: 800; letter-spacing: -.02em;
  font-variant-numeric: tabular-nums; margin-top: 3px; }
.kpi .sub { font-size: 12px; color: var(--muted); margin-top: 2px;
  font-variant-numeric: tabular-nums; }
.kpi .val .unit { font-size: 13px; font-weight: 600; color: var(--faint); }
.delta-pos { color: var(--green); } .delta-neg { color: var(--coral); }

/* ---------- Kort & tabell ---------- */
.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 16px 18px 12px; min-width: 0;
}
.league-card { margin-bottom: 26px; }
.card-head h3 { margin: 0 0 4px; font-size: 15.5px; font-weight: 700; }
.card-head p { margin: 0 0 8px; color: var(--muted); font-size: 12.5px; }
.tbl-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { padding: 8px 10px; text-align: right; white-space: nowrap;
  font-variant-numeric: tabular-nums; }
th:first-child, td:first-child { text-align: left; }
thead th {
  border-bottom: 2px solid var(--ink); font-size: 11px; text-transform: uppercase;
  letter-spacing: .06em; color: var(--muted); cursor: pointer; user-select: none;
}
thead th:hover { color: var(--teal-deep); }
tbody tr { border-bottom: 1px solid var(--line); cursor: pointer; }
tbody tr:hover { background: #f2f7f8; }
td.pos { color: var(--green); font-weight: 600; }
td.neg { color: var(--coral); font-weight: 600; }
.zone-tag { display: inline-block; padding: 1px 7px; border-radius: 5px;
  font-size: 11px; font-weight: 700; background: var(--teal-soft);
  color: var(--teal-deep); margin-left: 6px; }
.status-dot { display: inline-block; width: 10px; height: 10px;
  border-radius: 50%; }
.status-dot.pos { background: var(--green); }
.status-dot.neg { background: var(--coral); }
.status-dot.neutral { background: var(--faint); }

/* ---------- Parkkort ---------- */
.park-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.park-card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 16px 18px 14px; min-width: 0;
  scroll-margin-top: 90px;
}
.pc-head { display: flex; align-items: baseline; justify-content: space-between;
  gap: 10px; }
.pc-head h3 { margin: 0; font-size: 16.5px; font-weight: 800;
  letter-spacing: -.01em; }
.pc-cap { font-size: 12px; color: var(--faint); font-weight: 600;
  white-space: nowrap; }
.pc-insight {
  font-family: 'Source Serif 4', serif; font-size: 15px; line-height: 1.5;
  margin: 8px 0 12px; padding-left: 12px;
  border-left: 3px solid var(--teal);
}
.pc-insight.pos { border-left-color: var(--green); }
.pc-insight.neg { border-left-color: var(--coral); }
.spark { width: 100%; height: 64px; display: block; }
.spark-cap { display: flex; justify-content: space-between;
  font-size: 10.5px; color: var(--faint); margin-top: 2px; }
.mtd-row { font-size: 12.5px; color: var(--muted); margin-top: 10px;
  font-variant-numeric: tabular-nums; }
.mtd-row b { color: var(--ink); }
.dd-toggle {
  margin-top: 12px; border: 1px solid var(--line); background: var(--bg);
  border-radius: 8px; padding: 6px 14px; cursor: pointer;
  font: 600 12.5px 'Inter', sans-serif; color: var(--teal-deep);
}
.dd-toggle:hover { background: var(--teal-soft); }
.dd { margin-top: 14px; border-top: 1px solid var(--line); padding-top: 12px; }
.dd h4 { margin: 12px 0 2px; font-size: 13px; font-weight: 700; }
.dd .chart-note { margin: 0 0 6px; color: var(--muted); font-size: 12px; }
.dd-chart { width: 100%; min-height: 260px; }
.facts { display: flex; gap: 18px; flex-wrap: wrap; font-size: 12px;
  color: var(--muted); margin-top: 10px; }
.facts b { color: var(--ink); display: block; font-size: 13px; }

/* ---------- Footer ---------- */
footer { border-top: 1px solid var(--line); background: var(--card);
  padding: 24px 28px 32px; }
.foot-note { max-width: 1240px; margin: 0 auto; color: var(--faint);
  font-size: 12px; }

@media (max-width: 880px) {
  .park-grid { grid-template-columns: 1fr; }
  main { padding: 12px 14px 60px; }
  .topbar { padding: 10px 14px; }
}
@media print {
  .topbar { position: static; } .topnav { display: none; }
  .card, .park-card { break-inside: avoid; box-shadow: none; }
  .dd-toggle { display: none; }
}
"""

# ---------------------------------------------------------------------------
# JS
# ---------------------------------------------------------------------------

_JS = r"""
'use strict';

/* ================= Tokens & helpers ================= */
const C = {
  ink: '#16242f', muted: '#5b6b78', faint: '#8a98a4', line: '#e3e9ed',
  teal: '#0e7c86', tealDeep: '#0a5961', amber: '#de9b26', coral: '#d95f4c',
  green: '#2e9e6b', navy: '#1d3a4f',
};
const MONTHS_SV = ['jan','feb','mar','apr','maj','jun','jul','aug','sep','okt','nov','dec'];
const MONTHS_SV_FULL = ['januari','februari','mars','april','maj','juni','juli',
  'augusti','september','oktober','november','december'];
__COMMON_HELPERS__
const nf = (d) => new Intl.NumberFormat('sv-SE', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmt = fmtNum;
const fmtSign = (x, d=1) => (x === null || x === undefined || isNaN(x)) ? '–'
  : (x >= 0 ? '+' : '−') + nf(d).format(Math.abs(x)).replace(/ /g, ' ') + ' %';
const mLabel = (ym) => { const [y, m] = ym.split('-'); return MONTHS_SV[+m-1] + ' ' + y.slice(2); };
const esc = htmlEsc;
const ymKey = (m) => m.year + '-' + String(m.month).padStart(2, '0');

function baseLayout(over) {
  return Object.assign({
    font: { family: 'Inter, sans-serif', size: 12, color: C.ink },
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { l: 48, r: 14, t: 10, b: 36 },
    xaxis: { gridcolor: C.line, zerolinecolor: C.line, tickfont: { size: 11 } },
    yaxis: { gridcolor: C.line, zerolinecolor: C.line, tickfont: { size: 11 } },
    legend: { orientation: 'h', y: 1.14, x: 0, font: { size: 11.5 } },
    hovermode: 'x unified',
    hoverlabel: { bgcolor: '#fff', bordercolor: C.line, font: { size: 12, color: C.ink } },
  }, over || {});
}
const PCONF = { displayModeBar: false, responsive: true };
function plot(id, traces, layout) {
  const el = document.getElementById(id);
  if (el) Plotly.newPlot(el, traces, layout, PCONF);
}
function toneClass(t) { return t === 'pos' ? 'pos' : t === 'neg' ? 'neg' : 'neutral'; }

/* Sorterbar tabell (Nordic Clarity-mönstret) */
function makeSortable(tbl) {
  tbl.querySelectorAll('thead th').forEach((th, i) => {
    th.addEventListener('click', () => {
      const tb = tbl.querySelector('tbody');
      const rows = [...tb.querySelectorAll('tr')];
      const dir = th.dataset.dir === 'asc' ? -1 : 1;
      tbl.querySelectorAll('thead th').forEach(x => delete x.dataset.dir);
      th.dataset.dir = dir === 1 ? 'asc' : 'desc';
      rows.sort((a, b) => {
        const av = a.children[i].dataset.v, bv = b.children[i].dataset.v;
        const an = parseFloat(av), bn = parseFloat(bv);
        if (!Number.isNaN(an) && !Number.isNaN(bn)) return (an - bn) * dir;
        return String(av).localeCompare(String(bv), 'sv') * dir;
      });
      rows.forEach(r => tb.appendChild(r));
    });
  });
}

/* Lazy-render via IntersectionObserver (samma mönster som rework).
   Sektioner registrerar sina renderare i RENDERERS och markerar element
   med data-render="namn". */
const RENDERERS = {};
const rendered = new Set();
function lazyInit() {
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const fn = e.target.dataset.render;
      if (fn && RENDERERS[fn] && !rendered.has(e.target.id)) {
        rendered.add(e.target.id);
        try { RENDERERS[fn](e.target); } catch (err) {
          console.error('render', fn, err);
          e.target.innerHTML = '<p style="color:#b03a28;padding:20px">Kunde inte rendera: ' + esc(err.message) + '</p>';
        }
      }
      obs.unobserve(e.target);
    });
  }, { rootMargin: '300px' });
  document.querySelectorAll('[data-render]').forEach(el => obs.observe(el));
}

/* ================= Data ================= */
const PARKS = DATA.parks || {};
const PARK_KEYS = Object.keys(PARKS)
  .sort((a, b) => (PARKS[b].capacity_mwp || 0) - (PARKS[a].capacity_mwp || 0));
const KPIS = DATA.kpis || {};

/* ================= Hero: insikter + KPI:er ================= */
function renderHero() {
  const box = document.getElementById('portfolio-insights');
  box.innerHTML = (DATA.portfolio_insights || []).map(i =>
    '<div class="callout ' + toneClass(i.tone) + '">' + esc(i.text) + '</div>'
  ).join('');

  const k = KPIS;
  const cells = [];
  const mLbl = k.latest_closed_label || 'senaste månad';
  cells.push({ lbl: 'Produktion ' + mLbl, val: fmt(k.energy_mwh, 0),
    unit: 'MWh', sub: 'budget ' + fmt(k.budget_mwh, 0) + ' MWh' });
  cells.push({ lbl: 'Mot budget ' + mLbl, val: fmtSign(k.vs_budget_pct),
    unit: '', sub: k.park_count + ' parker · ' + fmt(k.total_capacity_mwp, 1) + ' MWp',
    tone: k.vs_budget_pct });
  cells.push({ lbl: 'Hittills i år mot budget', val: fmtSign(k.ytd_vs_budget_pct),
    unit: '', sub: fmt(k.ytd_energy_mwh, 0) + ' av ' + fmt(k.ytd_budget_mwh, 0) + ' MWh',
    tone: k.ytd_vs_budget_pct });
  if (k.capture_eur_mwh != null) {
    cells.push({ lbl: 'Realiserat capture ' + mLbl, val: fmt(k.capture_eur_mwh, 1),
      unit: '€/MWh', sub: 'Bazefield-volym × spot' });
  }
  document.getElementById('kpi-strip').innerHTML = cells.map(c => {
    const toneCls = (c.tone == null || Math.abs(c.tone) <= 3) ? ''
      : (c.tone > 0 ? ' delta-pos' : ' delta-neg');
    return '<div class="kpi"><div class="lbl">' + esc(c.lbl) + '</div>' +
      '<div class="val' + toneCls + '">' + esc(c.val) +
      (c.unit ? ' <span class="unit">' + esc(c.unit) + '</span>' : '') + '</div>' +
      '<div class="sub">' + esc(c.sub) + '</div></div>';
  }).join('');
}

/* ================= League table ================= */
function renderLeague() {
  if (KPIS.latest_closed_label) {
    document.getElementById('league-title').textContent =
      'Parkerna — ' + KPIS.latest_closed_label;
  }
  const rows = PARK_KEYS.map(key => {
    const p = PARKS[key];
    const lc = p.latest_closed || {};
    const prGap = (lc.pr_pct != null && lc.budget_pr_pct != null)
      ? lc.pr_pct - lc.budget_pr_pct : null;
    const ytdVs = (p.ytd || {}).vs_budget_pct;
    const tone = (p.insight || {}).tone || 'neutral';
    const vsCls = (v) => v == null ? '' : (v > 3 ? ' class="pos"' : (v < -3 ? ' class="neg"' : ''));
    return '<tr data-park="' + esc(key) + '">' +
      '<td data-v="' + esc(p.name) + '"><b>' + esc(p.name) + '</b>' +
        '<span class="zone-tag">' + esc(p.zone) + '</span></td>' +
      '<td data-v="' + (p.capacity_mwp ?? '') + '">' + fmt(p.capacity_mwp, 1) + '</td>' +
      '<td data-v="' + (lc.energy_mwh ?? '') + '">' + fmt(lc.energy_mwh, 0) + '</td>' +
      '<td data-v="' + (lc.vs_budget_pct ?? '') + '"' + vsCls(lc.vs_budget_pct) + '>' +
        fmtSign(lc.vs_budget_pct) + '</td>' +
      '<td data-v="' + (prGap ?? '') + '"' + vsCls(prGap) + '>' +
        (prGap == null ? '–' : fmtSign(prGap).replace(' %', '')) + '</td>' +
      '<td data-v="' + (lc.yield_kwh_kwp ?? '') + '">' + fmt(lc.yield_kwh_kwp, 0) + '</td>' +
      '<td data-v="' + (ytdVs ?? '') + '"' + vsCls(ytdVs) + '>' + fmtSign(ytdVs) + '</td>' +
      '<td data-v="' + esc(tone) + '"><span class="status-dot ' + toneClass(tone) + '"></span></td>' +
      '</tr>';
  }).join('');
  document.getElementById('tbl-league').innerHTML =
    '<table id="league"><thead><tr>' +
    '<th>Park</th><th>MWp</th><th>MWh</th><th>vs budget</th>' +
    '<th>PR-gap pp</th><th>kWh/kWp</th><th>YTD vs budget</th><th>Status</th>' +
    '</tr></thead><tbody>' + rows + '</tbody></table>';
  const tbl = document.getElementById('league');
  makeSortable(tbl);
  tbl.querySelectorAll('tbody tr').forEach(tr => {
    tr.addEventListener('click', () => {
      const card = document.getElementById('park-' + tr.dataset.park);
      if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

/* ================= Sparkline (ren SVG — skarp och lätt) ================= */
function sparklineSvg(months) {
  const W = 260, H = 48, PAD = 2;
  const ms = months || [];
  if (!ms.length) return '<svg class="spark" viewBox="0 0 260 48"></svg>';
  const maxV = Math.max(...ms.map(m => Math.max(m.energy_mwh || 0, m.budget_mwh || 0)), 1);
  const bw = (W - 2 * PAD) / ms.length;
  const sy = (v) => H - PAD - (v / maxV) * (H - 2 * PAD);
  let bars = '', line = '';
  ms.forEach((m, i) => {
    const x = PAD + i * bw;
    const e = m.energy_mwh || 0;
    const vs = m.vs_budget_pct;
    let fill = C.faint;
    if (vs != null) fill = vs > 3 ? C.green : (vs < -3 ? C.coral : C.teal);
    const op = m.is_partial ? '0.45' : '0.9';
    bars += '<rect x="' + (x + 0.5).toFixed(1) + '" y="' + sy(e).toFixed(1) +
      '" width="' + (bw - 1.5).toFixed(1) + '" height="' + (H - PAD - sy(e)).toFixed(1) +
      '" rx="1" fill="' + fill + '" fill-opacity="' + op + '">' +
      '<title>' + mLabel(ymKey(m)) + ': ' + fmt(e, 0) + ' MWh (budget ' +
      fmt(m.budget_mwh, 0) + ')</title></rect>';
    const bx = x + bw / 2, by = sy(m.budget_mwh || 0);
    line += (i === 0 ? 'M' : 'L') + bx.toFixed(1) + ' ' + by.toFixed(1);
  });
  return '<svg class="spark" viewBox="0 0 260 48" preserveAspectRatio="none">' +
    bars + '<path d="' + line + '" fill="none" stroke="' + C.navy +
    '" stroke-width="1.3" stroke-dasharray="3 2" vector-effect="non-scaling-stroke"/></svg>';
}

/* ================= Parkkort ================= */
function mtdRowHtml(p) {
  const m = p.mtd;
  if (!m) return '';
  const share = (m.budget_mwh > 0) ? (100 * m.energy_mwh / m.budget_mwh) : null;
  return '<div class="mtd-row"><b>' +
    esc(MONTHS_SV_FULL[m.month - 1].charAt(0).toUpperCase() + MONTHS_SV_FULL[m.month - 1].slice(1)) +
    ' hittills:</b> ' + fmt(m.energy_mwh, 0) + ' MWh, ' +
    (share == null ? '–' : fmt(share, 0)) + ' % av pro-rata-budget (' +
    fmt(m.budget_mwh, 0) + ' MWh)</div>';
}

function renderParkGrid() {
  const grid = document.getElementById('park-grid');
  grid.innerHTML = PARK_KEYS.map(key => {
    const p = PARKS[key];
    const ins = p.insight || { text: '', tone: 'neutral' };
    const months = p.months || [];
    const first = months.length ? mLabel(ymKey(months[0])) : '';
    const last = months.length ? mLabel(ymKey(months[months.length - 1])) : '';
    return '<div class="park-card" id="park-' + esc(key) + '">' +
      '<div class="pc-head"><h3>' + esc(p.name) +
        '<span class="zone-tag">' + esc(p.zone) + '</span></h3>' +
        '<span class="pc-cap">' + fmt(p.capacity_mwp, 1) + ' MWp</span></div>' +
      '<p class="pc-insight ' + toneClass(ins.tone) + '">' + esc(ins.text) + '</p>' +
      sparklineSvg(months) +
      '<div class="spark-cap"><span>' + esc(first) + '</span>' +
        '<span>staplar = MWh · streckad linje = budget</span>' +
        '<span>' + esc(last) + '</span></div>' +
      mtdRowHtml(p) +
      '<button class="dd-toggle" data-park="' + esc(key) + '" aria-expanded="false">Visa detaljer</button>' +
      '<div class="dd" id="dd-' + esc(key) + '" hidden></div>' +
      '</div>';
  }).join('');

  grid.querySelectorAll('.dd-toggle').forEach(btn => {
    btn.addEventListener('click', () => toggleDrilldown(btn));
  });
}

/* ================= Drilldown (renderas vid första öppning) ================= */
const ddRendered = new Set();
function toggleDrilldown(btn) {
  const key = btn.dataset.park;
  const dd = document.getElementById('dd-' + key);
  const open = dd.hidden;
  dd.hidden = !open;
  btn.textContent = open ? 'Dölj detaljer' : 'Visa detaljer';
  btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  if (open && !ddRendered.has(key)) {
    ddRendered.add(key);
    try { renderDrilldown(key, dd); } catch (err) {
      console.error('drilldown', key, err);
      dd.innerHTML = '<p style="color:#b03a28">Kunde inte rendera: ' + esc(err.message) + '</p>';
    }
  }
}

function factsHtml(p) {
  const f = p.facts || {};
  const ppa = p.ppa;
  const items = [
    ['Plats', f.location],
    ['Idrifttagen', f.commissioning_date],
    ['Moduler', f.num_modules != null ? fmt(f.num_modules) + ' × ' + (f.module_wp || '?') + ' Wp' : null],
    ['Växelriktare', f.num_inverters != null ? fmt(f.num_inverters) + ' st ' + (f.inverter_model || '') : null],
    ['Montage', f.tracking ? 'tracker' : (f.tilt_angle != null ? f.tilt_angle + '° lutning' : null)],
    ['Exportgräns', f.grid_limit_mwac != null ? fmt(f.grid_limit_mwac, 1) + ' MWac' : null],
    ['PPA', ppa ? fmt(ppa.price_sek_mwh, 0) + ' SEK/MWh · ' + fmt(ppa.share_pct, 0) + ' % av volymen' : 'ingen — 100 % spot'],
  ].filter(x => x[1] != null && x[1] !== '');
  return '<div class="facts">' + items.map(x =>
    '<div><b>' + esc(x[0]) + '</b>' + esc(x[1]) + '</div>').join('') + '</div>';
}

function renderDrilldown(key, dd) {
  const p = PARKS[key];
  const months = p.months || [];
  const lc = p.latest_closed;
  const lcLbl = lc ? MONTHS_SV_FULL[lc.month - 1] + ' ' + lc.year : '';

  dd.innerHTML =
    '<h4>Förlustkaskad — ' + esc(lcLbl) + '</h4>' +
    '<p class="chart-note">Budget → faktisk, uppdelad per orsak. Negativ stapel = bättre än budget.</p>' +
    '<div class="dd-chart" id="ddw-' + esc(key) + '"></div>' +
    '<h4>Produktion mot budget — 13 månader</h4>' +
    '<div class="dd-chart" id="ddm-' + esc(key) + '"></div>' +
    '<h4>Daglig produktion — ' + esc(lcLbl) + '</h4>' +
    '<div class="dd-chart" id="ddd-' + esc(key) + '"></div>' +
    factsHtml(p);

  /* Waterfall för senaste stängda månad */
  if (lc && lc.losses && lc.losses.budget_mwh) {
    const L = lc.losses;
    plot('ddw-' + key, [{
      type: 'waterfall', orientation: 'v',
      measure: ['absolute', 'relative', 'relative', 'relative', 'relative', 'relative', 'total'],
      x: ['Budget', 'Instrålning', 'Tillgänglighet', 'Temperatur', 'Clipping', 'Övrigt', 'Faktisk'],
      y: [L.budget_mwh, -(L.irradiance_shortfall_mwh || 0), -(L.availability_mwh || 0),
          -(L.temperature_mwh || 0), -(L.clipping_mwh || 0), -(L.residual_mwh || 0), null],
      text: [fmt(L.budget_mwh), fmt(-(L.irradiance_shortfall_mwh || 0)),
             fmt(-(L.availability_mwh || 0)), fmt(-(L.temperature_mwh || 0)),
             fmt(-(L.clipping_mwh || 0)), fmt(-(L.residual_mwh || 0)), fmt(L.actual_mwh)],
      textposition: 'outside',
      connector: { line: { color: C.line } },
      increasing: { marker: { color: C.green } },
      decreasing: { marker: { color: C.coral } },
      totals: { marker: { color: C.navy } },
      hoverinfo: 'skip',
    }], baseLayout({
      yaxis: { title: { text: 'MWh' }, gridcolor: C.line }, showlegend: false,
    }));
  } else {
    document.getElementById('ddw-' + key).innerHTML =
      '<p class="chart-note">Ingen förlustdata för stängd månad.</p>';
  }

  /* 13-mån energi vs budget */
  const x = months.map(m => mLabel(ymKey(m)));
  plot('ddm-' + key, [
    { type: 'bar', name: 'Produktion', x, y: months.map(m => m.energy_mwh),
      marker: { color: months.map(m => m.is_partial ? 'rgba(14,124,134,.35)' : C.teal) },
      hovertemplate: '%{y:.0f} MWh<extra>Produktion</extra>' },
    { type: 'scatter', mode: 'lines+markers', name: 'Budget', x,
      y: months.map(m => m.budget_mwh), line: { color: C.navy, width: 2, dash: 'dot' },
      marker: { size: 4 }, hovertemplate: '%{y:.0f} MWh<extra>Budget</extra>' },
  ], baseLayout({ yaxis: { title: { text: 'MWh' }, gridcolor: C.line, rangemode: 'tozero' } }));

  /* Dagligt energiband senaste stängda månad */
  const dailyKey = lc ? ymKey(lc) : null;
  const daily = (p.daily_by_month || {})[dailyKey] || [];
  if (daily.length) {
    plot('ddd-' + key, [
      { type: 'bar', name: 'Produktion', x: daily.map(d => d.day),
        y: daily.map(d => d.energy_mwh), marker: { color: C.teal },
        hovertemplate: '%{y:.1f} MWh<extra>dag %{x}</extra>' },
      { type: 'scatter', mode: 'lines', name: 'Förväntat (väderjusterat)',
        x: daily.map(d => d.day), y: daily.map(d => d.expected_mwh),
        line: { color: C.amber, width: 1.8 },
        hovertemplate: '%{y:.1f} MWh<extra>förväntat</extra>' },
    ], baseLayout({
      xaxis: { title: { text: 'dag i månaden' }, gridcolor: C.line, tickfont: { size: 11 } },
      yaxis: { title: { text: 'MWh' }, gridcolor: C.line, rangemode: 'tozero' },
    }));
  } else {
    document.getElementById('ddd-' + key).innerHTML =
      '<p class="chart-note">Ingen daglig data för månaden.</p>';
  }
}

/* ================= Init ================= */
function init() {
  renderHero();
  renderLeague();
  renderParkGrid();
  lazyInit();
}
document.addEventListener('DOMContentLoaded', init);
"""
