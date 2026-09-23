"""Renderare för Översikt — en fristående HTML-sida.

Principer (docs/plans/2026-09-22-oversikt-design.md):

* Varje sektion öppnar med en mening i klartext; diagrammen är beviset.
* Varje tal visas med enhet, period och jämförelse. Allt i EUR/MWh.
* SE3/SE4 är standard; övriga zoner kan slås på.
* Om underlaget är trasigt visas en flagga i stället för ett värde.
* Signatur: datatäckning syns bredvid siffrorna (dagremsor per park).

Data injiceras som ``const D = …``; all presentation sker i JS nedan.
Plotly bäddas in från vendor/plotly.min.js (CDN som reserv).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ..dashboard_common import esc, script_json

# Plotly bäddas in (vendor/plotly.min.js) så att sidan fungerar offline och i
# förhandsvisningar som blockerar externa skript. Saknas filen: CDN.
PLOTLY_VENDOR = Path(__file__).parent / "vendor" / "plotly.min.js"
PLOTLY_URL = "https://cdn.plot.ly/plotly-basic-2.35.2.min.js"
FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Next:wght@400;500;700"
    "&family=Schibsted+Grotesk:wght@500;600;700&display=swap"
)

CSS = r"""
:root {
  color-scheme: light;
  --paper: #fcfcfb;
  --paper-2: #f3f4f1;
  --ink: #15202a;
  --ink-2: #47525d;
  --ink-3: #737d88;
  --rule: #dfe2de;
  --grid: #eceeea;
  --accent: #15202a;
  --good: #0a7d0a;
  --bad: #c23434;
  --warn-bg: #fff6e0;
  --warn-ink: #7a5200;
  --s-SE3: #2a78d6; --s-SE4: #eb6834; --s-SE1: #1baf7a; --s-SE2: #eda100;
  --s-DK1: #e87ba4; --s-DK2: #008300; --s-SYS: #737d88;
  --bar: #2a78d6; --bar-partial: #9ec5f4; --bar-missing: #c9ceca;
  --strip-ok: #47525d; --strip-part: #9aa3ac; --strip-miss: #c23434;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --paper: #1a1a19; --paper-2: #232322;
    --ink: #f4f3ee; --ink-2: #c3c2b7; --ink-3: #9a998f;
    --rule: #3a3a37; --grid: #2c2c2a; --accent: #f4f3ee;
    --good: #3fbf3f; --bad: #e66767; --warn-bg: #3a2f14; --warn-ink: #f2c66b;
    --s-SE3: #3987e5; --s-SE4: #d95926; --s-SE1: #199e70; --s-SE2: #c98500;
    --s-DK1: #d55181; --s-DK2: #008300; --s-SYS: #9a998f;
    --bar: #3987e5; --bar-partial: #1c5cab; --bar-missing: #4a4a46;
    --strip-ok: #c3c2b7; --strip-part: #6f6e67; --strip-miss: #e66767;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --paper: #1a1a19; --paper-2: #232322;
  --ink: #f4f3ee; --ink-2: #c3c2b7; --ink-3: #9a998f;
  --rule: #3a3a37; --grid: #2c2c2a; --accent: #f4f3ee;
  --good: #3fbf3f; --bad: #e66767; --warn-bg: #3a2f14; --warn-ink: #f2c66b;
  --s-SE3: #3987e5; --s-SE4: #d95926; --s-SE1: #199e70; --s-SE2: #c98500;
  --s-DK1: #d55181; --s-DK2: #008300; --s-SYS: #9a998f;
  --bar: #3987e5; --bar-partial: #1c5cab; --bar-missing: #4a4a46;
  --strip-ok: #c3c2b7; --strip-part: #6f6e67; --strip-miss: #e66767;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 64px; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font: 16px/1.55 "Atkinson Hyperlegible Next", "Atkinson Hyperlegible", system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, .display { font-family: "Schibsted Grotesk", system-ui, sans-serif; letter-spacing: -0.01em; }
a { color: inherit; }
:focus-visible { outline: 2px solid var(--s-SE3); outline-offset: 2px; border-radius: 3px; }

.wrap { max-width: 1160px; margin: 0 auto; padding: 0 24px; }

/* Topp */
.masthead { padding: 36px 0 20px; border-bottom: 1px solid var(--rule); }
.masthead .eyebrow { font-size: 13px; color: var(--ink-3); letter-spacing: .04em; text-transform: uppercase; }
.masthead h1 { font-size: 34px; line-height: 1.1; margin: 6px 0 10px; font-weight: 700; }
.masthead .meta { color: var(--ink-2); font-size: 14px; }
.masthead .meta b { color: var(--ink); font-weight: 700; }

nav.sections {
  position: sticky; top: 0; z-index: 10; background: color-mix(in srgb, var(--paper) 92%, transparent);
  backdrop-filter: blur(6px); border-bottom: 1px solid var(--rule);
}
nav.sections .wrap { display: flex; gap: 4px; overflow-x: auto; padding-top: 6px; padding-bottom: 6px; scrollbar-width: none; }
nav.sections .wrap::-webkit-scrollbar { display: none; }
nav.sections a {
  text-decoration: none; font: 600 14px "Schibsted Grotesk", system-ui, sans-serif; color: var(--ink-2);
  padding: 8px 12px; border-radius: 6px; white-space: nowrap;
}
nav.sections a:hover { background: var(--paper-2); color: var(--ink); }
nav.sections a.issues { margin-left: auto; color: var(--warn-ink); }

/* Sektioner */
section.block { padding: 48px 0 24px; border-bottom: 1px solid var(--rule); }
.sec-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.sec-head h2 { font-size: 26px; margin: 0; font-weight: 700; }
.sec-head .scope { color: var(--ink-3); font-size: 14px; }
.lede {
  font-family: "Schibsted Grotesk", system-ui, sans-serif; font-weight: 500;
  font-size: 23px; line-height: 1.4; max-width: 60ch; margin: 18px 0 8px; color: var(--ink);
}
.lede b { font-weight: 700; }
.lede .up { color: var(--good); } .lede .down { color: var(--bad); }
.note { color: var(--ink-2); font-size: 14px; max-width: 75ch; }
.note.warn, .flag {
  background: var(--warn-bg); color: var(--warn-ink); padding: 8px 12px; border-radius: 6px;
  font-size: 14px; margin: 10px 0;
}
.flag::before { content: "⚠ "; }

/* Kontroller */
.controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 20px 0 8px; }
.controls label { font-size: 14px; color: var(--ink-2); }
select, button.chip, button.seg {
  font: 500 14px "Atkinson Hyperlegible Next", system-ui, sans-serif; color: var(--ink);
  background: var(--paper); border: 1px solid var(--rule); border-radius: 999px; padding: 6px 12px; cursor: pointer;
}
select { border-radius: 6px; padding: 6px 10px; }
button.chip { display: inline-flex; align-items: center; gap: 6px; }
button.chip .sw { width: 10px; height: 10px; border-radius: 50%; background: var(--c); }
button.chip[aria-pressed="false"] { color: var(--ink-3); }
button.chip[aria-pressed="false"] .sw { background: transparent; box-shadow: inset 0 0 0 1.5px var(--c); }
button.seg[aria-pressed="true"] { background: var(--ink); color: var(--paper); border-color: var(--ink); }

/* Nyckeltal */
.kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0; margin: 24px 0 8px;
  border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
.kpi { padding: 16px 18px 16px 0; }
.kpi + .kpi { padding-left: 18px; border-left: 1px solid var(--rule); }
.kpi .label { font: 600 14px "Schibsted Grotesk", system-ui, sans-serif; color: var(--ink); }
.kpi .value { font: 700 30px/1.15 "Schibsted Grotesk", system-ui, sans-serif; margin: 6px 0 2px; letter-spacing: -0.02em; }
.kpi .value.up { color: var(--good); } .kpi .value.down { color: var(--bad); }
.kpi .value small { font-size: 15px; font-weight: 600; color: var(--ink-2); letter-spacing: 0; }
.kpi .def { font-size: 13px; color: var(--ink-3); line-height: 1.4; min-height: 2.8em; }
.kpi .sub { font-size: 13px; color: var(--ink-2); margin-top: 8px; }
.kpi .sub b { color: var(--ink); }
@media (max-width: 900px) {
  .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .kpi, .kpi + .kpi { padding: 14px 12px 14px 0; border-left: 0; border-bottom: 1px solid var(--rule); }
}

/* Tabeller */
.tbl-wrap { overflow-x: auto; margin: 16px 0; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { padding: 9px 10px; text-align: right; border-bottom: 1px solid var(--grid); white-space: nowrap; }
th { font: 600 13px "Schibsted Grotesk", system-ui, sans-serif; color: var(--ink-2); border-bottom: 1px solid var(--rule); vertical-align: bottom; }
th .u { display: block; font-weight: 500; color: var(--ink-3); font-size: 12px; }
th:first-child, td:first-child { text-align: left; }
td { font-variant-numeric: tabular-nums; }
td.muted, span.muted { color: var(--ink-3); }
td .tag { font-size: 12px; color: var(--ink-3); margin-left: 6px; }
th.sortable { cursor: pointer; }
th.sortable:hover { color: var(--ink); }
th[aria-sort] { color: var(--ink); }
tr.park { cursor: pointer; }
tr.park:hover td { background: var(--paper-2); }
tr.park.open td { background: var(--paper-2); }
tr.park td:first-child { font-weight: 700; }
tr.group td { font: 600 12px "Schibsted Grotesk", system-ui, sans-serif; color: var(--ink-3); text-transform: uppercase;
  letter-spacing: .05em; padding-top: 16px; border-bottom: 1px solid var(--rule); background: none; }
tr.total td { font-weight: 700; border-top: 2px solid var(--ink); border-bottom: 0; }
.delta.up { color: var(--good); } .delta.down { color: var(--bad); }
.delta.up::before { content: "▲ "; font-size: 10px; } .delta.down::before { content: "▼ "; font-size: 10px; }
.warnmark { color: var(--warn-ink); font-size: 12px; margin-left: 4px; }

/* Signatur: dagremsa för datatäckning */
.strip { display: inline-flex; align-items: flex-end; gap: 1.5px; height: 16px; vertical-align: middle; margin-left: 8px; }
.strip i { display: block; width: 3.5px; border-radius: 1px; }
.strip i.ok { height: 16px; background: var(--strip-ok); }
.strip i.part { height: 9px; background: var(--strip-part); }
.strip i.miss { height: 16px; background: transparent; box-shadow: inset 0 0 0 1px var(--strip-miss); }
.strip i.none { height: 3px; background: var(--grid); }
.strip-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 12px; color: var(--ink-3); align-items: center; }
.strip-legend .strip { margin-left: 4px; height: 12px; }
.strip-legend .strip i { height: 12px; } .strip-legend .strip i.part { height: 7px; }

/* Diagram */
.charts { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 28px; margin: 12px 0; }
.charts.one { grid-template-columns: 1fr; }
@media (max-width: 900px) { .charts { grid-template-columns: 1fr; } }
figure { margin: 0; min-width: 0; }
figcaption h3 { font-size: 17px; margin: 0; font-weight: 600; }
figcaption p { margin: 2px 0 0; font-size: 13px; color: var(--ink-3); }
.plot { height: 320px; width: 100%; }
.plot.tall { height: 360px; }
details.data { margin-top: 6px; font-size: 13px; color: var(--ink-2); }
details.data summary { cursor: pointer; color: var(--ink-3); }
details.data table { font-size: 12px; }

/* Parkdetalj */
.park-detail { border: 1px solid var(--rule); border-radius: 10px; padding: 20px 22px; margin: 8px 0 24px; background: var(--paper); }
.park-detail h3.pd { font-size: 22px; margin: 0; }
.park-detail .facts { color: var(--ink-2); font-size: 14px; margin: 4px 0 8px; }
.park-detail .close { float: right; }

.split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 28px; }
.split > * { min-width: 0; }
@media (max-width: 900px) { .split { grid-template-columns: 1fr; } }
.defs dt { font: 600 15px "Schibsted Grotesk", system-ui, sans-serif; margin-top: 14px; }
.defs dd { margin: 2px 0 0; color: var(--ink-2); font-size: 14px; max-width: 80ch; }
.status-ok::before { content: "● "; color: var(--good); }
.status-gammal::before, .status-saknas::before { content: "● "; color: var(--bad); }
ul.issues { padding-left: 18px; } ul.issues li { margin: 6px 0; }
footer { padding: 32px 0 60px; color: var(--ink-3); font-size: 13px; }

@media (max-width: 600px) {
  .wrap { padding: 0 16px; }
  .masthead h1 { font-size: 27px; }
  .lede { font-size: 19px; }
  .kpi .value { font-size: 25px; }
}
@media print {
  nav.sections, .controls, details.data, .park-detail .close { display: none !important; }
  section.block { break-inside: avoid-page; }
  .plot { height: 280px; }
}
"""

BODY = r"""
<header class="masthead">
  <div class="wrap">
    <div class="eyebrow">Översikt · internt</div>
    <h1>Solportföljen och elmarknaden</h1>
    <div class="meta" id="meta"></div>
  </div>
</header>
<nav class="sections" aria-label="Sektioner">
  <div class="wrap">
    <a href="#portfoljen">Portföljen</a>
    <a href="#marknaden">Elmarknaden</a>
    <a href="#terminer">Terminer</a>
    <a href="#batteri">Batteri</a>
    <a href="#datastatus" id="nav-status">Datastatus</a>
  </div>
</nav>
<main>
  <section class="block" id="portfoljen">
    <div class="wrap">
      <div class="sec-head">
        <h2>Portföljen</h2>
        <div class="controls" style="margin:0">
          <label for="month">Månad</label>
          <select id="month"></select>
        </div>
      </div>
      <p class="lede" id="p-lede"></p>
      <div id="p-flags"></div>
      <div class="kpis" id="p-kpis"></div>
      <div class="tbl-wrap"><table id="p-table"></table></div>
      <div class="strip-legend" id="p-strip-legend"></div>
      <div id="p-detail"></div>
      <div class="charts">
        <figure>
          <figcaption><h3>Portföljen månad för månad</h3><p>Stapel = uppmätt produktion, alla parker. Streck = budget för samma tid som har mätdata.</p></figcaption>
          <div class="plot" id="p-months"></div>
          <details class="data"><summary>Visa siffrorna</summary><div class="tbl-wrap" id="p-months-tbl"></div></details>
        </figure>
        <figure>
          <figcaption><h3>Vad elen var värd per månad</h3><p>Portföljens capturepris mot spotpriset i parkernas zoner (viktat med produktionen), EUR/MWh.</p></figcaption>
          <div class="plot" id="p-value"></div>
          <details class="data"><summary>Visa siffrorna</summary><div class="tbl-wrap" id="p-value-tbl"></div></details>
        </figure>
      </div>
    </div>
  </section>

  <section class="block" id="marknaden">
    <div class="wrap">
      <div class="sec-head"><h2>Elmarknaden</h2><span class="scope" id="m-scope"></span></div>
      <p class="lede" id="m-lede"></p>
      <div class="controls" id="m-zones" role="group" aria-label="Elområden"></div>
      <div class="charts">
        <figure>
          <figcaption><h3>Spotpris per månad</h3><p>Genomsnittligt day-ahead-pris, EUR/MWh</p></figcaption>
          <div class="plot" id="m-price"></div>
          <details class="data"><summary>Visa siffrorna</summary><div class="tbl-wrap" id="m-price-tbl"></div></details>
        </figure>
        <figure>
          <figcaption><h3>Solens capture rate per månad</h3><p>Vad solel fick betalt i procent av månadens spotpris. Vintermånader utelämnas.</p></figcaption>
          <div class="plot" id="m-capture"></div>
          <details class="data"><summary>Visa siffrorna</summary><div class="tbl-wrap" id="m-capture-tbl"></div></details>
        </figure>
      </div>
      <h3 style="margin-top:28px">Per år</h3>
      <p class="note" id="m-year-note"></p>
      <div class="split" id="m-years"></div>
      <p class="note" id="m-spread"></p>
    </div>
  </section>

  <section class="block" id="terminer">
    <div class="wrap">
      <div class="sec-head"><h2>Terminer</h2><span class="scope" id="f-scope"></span></div>
      <p class="lede" id="f-lede"></p>
      <div id="f-flags"></div>
      <div class="split" id="f-tables"></div>
      <div class="controls" id="f-contracts" role="group" aria-label="Kontrakt"></div>
      <div class="charts one">
        <figure>
          <figcaption><h3 id="f-chart-title">Terminspris över tid</h3><p>Områdespris = systempris (SYS) + områdestillägg (EPAD), EUR/MWh. Luckor = inga noteringar.</p></figcaption>
          <div class="plot tall" id="f-history"></div>
          <details class="data"><summary>Visa siffrorna</summary><div class="tbl-wrap" id="f-history-tbl"></div></details>
        </figure>
      </div>
      <h3 style="margin-top:28px">Vad marknaden trodde – och vad det blev</h3>
      <p class="note">Sista områdespriset före leveransstart jämfört med det faktiska genomsnittliga spotpriset under kvartalet.</p>
      <div class="tbl-wrap" id="f-convergence"></div>
    </div>
  </section>

  <section class="block" id="batteri">
    <div class="wrap">
      <div class="sec-head"><h2>Batteri</h2><span class="scope" id="b-scope"></span></div>
      <p class="lede" id="b-lede"></p>
      <div class="controls" id="b-zones" role="group" aria-label="Elområden"></div>
      <div class="charts">
        <figure>
          <figcaption><h3>Dagsspread per månad</h3><p>Dygnets 2 dyraste timmar minus dygnets 2 billigaste, månadsmedel, EUR/MWh</p></figcaption>
          <div class="plot" id="b-spread"></div>
          <details class="data"><summary>Visa siffrorna</summary><div class="tbl-wrap" id="b-spread-tbl"></div></details>
        </figure>
        <figure>
          <figcaption><h3>Arbitrage-tak per månad</h3><p>1 MW / 2 MWh, en cykel per dag, perfekt framförhållning. EUR per MW.</p></figcaption>
          <div class="plot" id="b-rev"></div>
          <details class="data"><summary>Visa siffrorna</summary><div class="tbl-wrap" id="b-rev-tbl"></div></details>
        </figure>
      </div>
      <h3 style="margin-top:28px">Arbitrage-tak per år</h3>
      <div class="tbl-wrap" id="b-years"></div>
      <p class="note" id="b-notes"></p>
    </div>
  </section>

  <section class="block" id="datastatus">
    <div class="wrap">
      <div class="sec-head"><h2>Datastatus</h2><span class="scope" id="d-scope"></span></div>
      <div class="split">
        <div>
          <h3>Kända problem</h3>
          <ul class="issues" id="d-issues"></ul>
        </div>
        <div>
          <h3>Källor</h3>
          <div class="tbl-wrap" id="d-sources"></div>
        </div>
      </div>
      <h3 style="margin-top:28px">Så räknar vi</h3>
      <dl class="defs" id="d-defs"></dl>
    </div>
  </section>
</main>
<footer><div class="wrap" id="footer"></div></footer>
"""

JS = r"""
const MONTHS = ['januari','februari','mars','april','maj','juni','juli','augusti','september','oktober','november','december'];
const MSHORT = ['jan','feb','mar','apr','maj','jun','jul','aug','sep','okt','nov','dec'];
const ZONE_NAMES = {SE1:'SE1 Luleå', SE2:'SE2 Sundsvall', SE3:'SE3 Stockholm', SE4:'SE4 Malmö', DK1:'DK1 Västdanmark', DK2:'DK2 Östdanmark'};
const PLOT_CFG = {displayModeBar: false, responsive: true, locale: 'sv'};
if (window.Plotly) Plotly.register({moduleType: 'locale', name: 'sv', dictionary: {}, format: {
  days: ['söndag','måndag','tisdag','onsdag','torsdag','fredag','lördag'], shortDays: ['sön','mån','tis','ons','tor','fre','lör'],
  months: ['januari','februari','mars','april','maj','juni','juli','augusti','september','oktober','november','december'],
  shortMonths: ['jan','feb','mar','apr','maj','jun','jul','aug','sep','okt','nov','dec'], date: '%Y-%m-%d', decimal: ',', thousands: '\u00a0'}});

// ---------- formattering ----------
function isNum(v) { return v !== null && v !== undefined && !Number.isNaN(Number(v)) && v !== ''; }
function fmt(v, d) {
  if (!isNum(v)) return '–';
  d = d || 0;
  return Number(v).toLocaleString('sv-SE', {minimumFractionDigits: d, maximumFractionDigits: d});
}
function pct(v, d, sign) {
  if (!isNum(v)) return '–';
  d = (d === undefined) ? 0 : d;
  const s = fmt(v * 100, d);
  return (sign && v > 0 ? '+' : '') + s + ' %';
}
function signed(v, d) { if (!isNum(v)) return '–'; return (v > 0 ? '+' : '') + fmt(v, d); }
function eur(v, d) { return isNum(v) ? fmt(v, d === undefined ? 1 : d) + ' €/MWh' : '–'; }
function money(v) { return isNum(v) ? fmt(v, 0) + ' €' : '–'; }
function mLabel(mk, short) { const [y, m] = mk.split('-'); return (short ? MSHORT : MONTHS)[+m - 1] + ' ' + y; }
function dLabel(day) { if (!day) return '–'; const [y, m, d] = day.split('-'); return (+d) + ' ' + MSHORT[+m - 1] + ' ' + y; }
function dShort(day) { const [y, m, d] = day.split('-'); return (+d) + ' ' + MSHORT[+m - 1]; }
function esc(s) { return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]); }
function deltaCls(v, eps) { eps = eps || 0; return !isNum(v) ? '' : (v > eps ? 'up' : (v < -eps ? 'down' : '')); }
function el(id) { return document.getElementById(id); }

// ---------- tema ----------
function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function zc(z) { return css('--s-' + z) || '#888'; }
function layout(extra) {
  const base = {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: {family: '"Atkinson Hyperlegible Next", system-ui, sans-serif', size: 12, color: css('--ink-2')},
    margin: {l: 52, r: 12, t: 8, b: 36}, separators: ', ', showlegend: false,
    hovermode: 'x unified', hoverlabel: {bgcolor: css('--paper'), bordercolor: css('--rule'), font: {color: css('--ink'), size: 12}},
    xaxis: {gridcolor: css('--grid'), linecolor: css('--rule'), tickcolor: css('--rule'), zeroline: false, showgrid: false, fixedrange: true},
    yaxis: {gridcolor: css('--grid'), linecolor: css('--rule'), zerolinecolor: css('--rule'), zeroline: true, fixedrange: true, rangemode: 'tozero', tickformat: ',.0f'},
  };
  for (const k in (extra || {})) {
    if (typeof extra[k] === 'object' && !Array.isArray(extra[k]) && base[k]) base[k] = Object.assign({}, base[k], extra[k]);
    else base[k] = extra[k];
  }
  return base;
}
const RENDERERS = [];
// Ett trasigt diagram får aldrig stoppa resten av sidan.
function safe(fn) { try { fn(); } catch (e) { console.error(e); } }
function draw(fn) { RENDERERS.push(fn); safe(fn); }
function redrawAll() { RENDERERS.forEach(safe); }
function plot(id, data, lay) {
  const node = el(id);
  if (!node) return;
  if (!window.Plotly) {
    node.style.height = 'auto';
    node.innerHTML = '<p class="note">Diagrammet kunde inte laddas. Siffrorna finns under "Visa siffrorna".</p>';
    return;
  }
  Plotly.react(node, data, lay, PLOT_CFG);
}
if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', redrawAll);

function dataTable(target, head, rows) {
  const h = '<table><thead><tr>' + head.map(x => '<th>' + x + '</th>').join('') + '</tr></thead><tbody>' +
    rows.map(r => '<tr>' + r.map(c => '<td>' + c + '</td>').join('') + '</tr>').join('') + '</tbody></table>';
  el(target).innerHTML = h;
}

// ---------- tillstånd ----------
const STATE = {month: D.portfolj.default_month, park: null, zones: new Set(D.marknad.main_zones), contract: null, range: '36'};
(function readHash() {
  if (!location.hash.includes('=')) return;
  const h = new URLSearchParams(location.hash.slice(1));
  if (h.get('m') && D.portfolj.portfolio[h.get('m')]) STATE.month = h.get('m');
  if (h.get('park') && D.portfolj.parks[h.get('park')]) STATE.park = h.get('park');
})();
function writeHash() {
  const p = new URLSearchParams();
  if (STATE.month !== D.portfolj.default_month) p.set('m', STATE.month);
  if (STATE.park) p.set('park', STATE.park);
  const s = p.toString();
  history.replaceState(null, '', s ? '#' + s : location.pathname + location.search);
}

// =====================================================================
// Huvud
// =====================================================================
function renderMeta() {
  el('meta').innerHTML = 'Parkdata t.o.m. <b>' + dLabel(D.portfolj.data_end) + '</b> · spotpriser t.o.m. <b>' +
    dLabel(D.marknad.data_end) + '</b> · terminer t.o.m. <b>' + dLabel(D.terminer && D.terminer.latest_date) +
    '</b> · skapad ' + esc(D.generated) + '. Alla priser i EUR/MWh, svensk tid.';
  const n = D.datastatus.issues.length;
  if (n) { const a = el('nav-status'); a.textContent = 'Datastatus · ' + n + (n === 1 ? ' problem' : ' problem'); a.classList.add('issues'); }
}

// =====================================================================
// Portföljen
// =====================================================================
const P = D.portfolj;
const PARK_KEYS = Object.keys(P.parks);
const SORT = {key: null, dir: -1};

function monthOptions() {
  const sel = el('month');
  sel.innerHTML = P.months.slice().reverse().map(mk => {
    const pm = P.portfolio[mk];
    const lbl = mLabel(mk) + (pm.partial ? ' (t.o.m. ' + dShort(P.data_end) + ')' : '');
    return '<option value="' + mk + '"' + (mk === STATE.month ? ' selected' : '') + '>' + lbl + '</option>';
  }).join('');
  sel.addEventListener('change', () => { STATE.month = sel.value; writeHash(); renderPortfolio(); });
}

function periodName(mk) {
  const pm = P.portfolio[mk];
  return pm.partial ? mLabel(mk).replace(/^./, c => c.toUpperCase()) + ' t.o.m. ' + dShort(P.data_end) : mLabel(mk).replace(/^./, c => c.toUpperCase());
}

function renderPortfolio() {
  const mk = STATE.month, pm = P.portfolio[mk], y = P.ytd[mk];
  const names = k => P.parks[k].info.name;
  const excl = pm.parks_excluded.map(names);
  // Klartext
  let s = 'I ' + (pm.partial ? mLabel(mk) + ' (t.o.m. ' + dShort(P.data_end) + ')' : mLabel(mk)) +
          ' producerade portföljen <b>' + fmt(pm.energy_mwh) + ' MWh</b>. ';
  if (isNum(pm.vs_budget)) {
    const v = pm.vs_budget;
    s += 'Det är <b class="' + (v >= 0 ? 'up' : 'down') + '">' + pct(Math.abs(v), 1) + (v >= 0 ? ' mer' : ' mindre') + '</b> än budget för den tid vi har mätdata. ';
  }
  if (isNum(pm.capture_eur)) {
    s += 'Elen var värd <b>' + eur(pm.capture_eur) + '</b> på spotmarknaden, <b>' + pct(pm.capture_ratio) + '</b> av genomsnittspriset.';
  }
  el('p-lede').innerHTML = s;
  el('p-flags').innerHTML = excl.length
    ? '<div class="flag">' + esc(excl.join(', ')) + (excl.length === 1 ? ' saknar' : ' saknar') +
      ' mätdata för mer än 20 % av dagsljuset och ingår inte i budgetjämförelsen. Produktionen räknas ändå med i totalen där den är uppmätt.</div>'
    : '';

  const ytdName = 'Hittills i år (jan–' + MSHORT[+mk.slice(5) - 1] + ')';
  const kpis = [
    {label: 'Produktion', value: fmt(pm.energy_mwh), unit: 'MWh', def: 'Uppmätt leverans till nätet, alla parker.',
     sub: ytdName + ': <b>' + fmt(y.energy_mwh) + ' MWh</b>'},
    {label: 'Mot budget', value: isNum(pm.vs_budget) ? pct(pm.vs_budget, 1, true) : '–', unit: '',
     cls: deltaCls(pm.vs_budget), def: 'Jämfört med PVsyst-budget för samma tid som har mätdata.',
     sub: (pm.parks_included.length + ' av ' + (pm.parks_included.length + pm.parks_excluded.length) + ' parker · ') +
          ytdName.split(' (')[0] + ': <b>' + pct(y.vs_budget, 1, true) + '</b>'},
    {label: 'Spotvärde', value: fmt(pm.value_eur), unit: '€', def: 'Produktionen gånger spotpriset, kvart för kvart. Inte PPA-intäkt.',
     sub: ytdName.split(' (')[0] + ': <b>' + money(y.value_eur) + '</b>'},
    {label: 'Capturepris', value: fmt(pm.capture_eur, 1), unit: '€/MWh', def: 'Vad en MWh från portföljen var värd i snitt på spotmarknaden.',
     sub: '<b>' + pct(pm.capture_ratio) + '</b> av spotpriset (' + eur(pm.baseload_mix_eur) + ')'},
    {label: 'Datatäckning', value: pct(pm.coverage), unit: '', def: 'Andel av dagsljuset med trovärdig mätning. Resten är okänt, inte noll.',
     sub: ytdName.split(' (')[0] + ': <b>' + pct(y.coverage) + '</b>'},
  ];
  el('p-kpis').innerHTML = kpis.map(k =>
    '<div class="kpi"><div class="label">' + k.label + '</div><div class="value ' + (k.cls || '') + '">' +
    k.value + (k.unit ? ' <small>' + k.unit + '</small>' : '') + '</div><div class="def">' + k.def + '</div><div class="sub">' + k.sub + '</div></div>'
  ).join('');

  renderParkTable();
  renderParkDetail();
  renderPortfolioTrend();
}

let TREND_DRAWN = false;
function renderPortfolioTrend() {
  const fn = () => {
    const months = P.months.filter(x => x <= STATE.month).slice(-13);
    const x = months.map(m => mLabel(m, true));
    const ticks = months.map((m, i) => (i === 0 || m.slice(5) === '01') ? MSHORT[+m.slice(5) - 1] + '<br>' + m.slice(0, 4) : MSHORT[+m.slice(5) - 1]);
    const pm = m => P.portfolio[m];
    plot('p-months', [
      {type: 'bar', name: 'Uppmätt', x, y: months.map(m => pm(m).energy_mwh), marker: {color: months.map(m => pm(m).coverage >= 0.95 ? css('--bar') : css('--bar-partial'))},
       customdata: months.map(m => [pct(pm(m).coverage)]),
       hovertemplate: '%{y:,.0f} MWh · datatäckning %{customdata[0]}<extra></extra>'},
      {type: 'scatter', mode: 'markers', name: 'Budget (tid med data)', x, y: months.map(m => pm(m).budget_obs_mwh),
       marker: {symbol: 'line-ew', size: 26, line: {width: 3, color: css('--ink')}}, hovertemplate: 'budget %{y:,.0f} MWh<extra></extra>'},
    ], layout({xaxis: {tickmode: 'array', tickvals: x, ticktext: ticks, tickangle: 0}, yaxis: {title: {text: 'MWh', standoff: 6}}, bargap: 0.35,
               margin: {l: 52, r: 12, t: 8, b: 44}}), PLOT_CFG);
    dataTable('p-months-tbl', ['Månad', 'Produktion MWh', 'Budget (tid med data) MWh', 'Mot budget', 'Datatäckning'],
      months.slice().reverse().map(m => [mLabel(m, true), fmt(pm(m).energy_mwh), fmt(pm(m).budget_obs_mwh), pct(pm(m).vs_budget, 1, true), pct(pm(m).coverage)]));
    plot('p-value', [
      {type: 'scatter', mode: 'lines+markers', name: 'Spotpris', x, y: months.map(m => pm(m).baseload_mix_eur), line: {color: css('--s-SYS'), width: 2}, marker: {size: 6},
       hovertemplate: 'spotpris %{y:,.1f} €/MWh<extra></extra>'},
      {type: 'scatter', mode: 'lines+markers', name: 'Capturepris', x, y: months.map(m => pm(m).capture_eur), line: {color: css('--bar'), width: 2.5}, marker: {size: 7},
       customdata: months.map(m => [pct(pm(m).capture_ratio)]), hovertemplate: 'capturepris %{y:,.1f} €/MWh (%{customdata[0]})<extra></extra>'},
    ], layout({xaxis: {tickmode: 'array', tickvals: x, ticktext: ticks, tickangle: 0}, yaxis: {title: {text: 'EUR/MWh', standoff: 6}}, showlegend: true,
               legend: {orientation: 'h', y: 1.1, x: 0}, margin: {l: 52, r: 12, t: 24, b: 44}}), PLOT_CFG);
    dataTable('p-value-tbl', ['Månad', 'Capturepris €/MWh', 'Spotpris €/MWh', 'Capture-kvot'],
      months.slice().reverse().map(m => [mLabel(m, true), fmt(pm(m).capture_eur, 1), fmt(pm(m).baseload_mix_eur, 1), pct(pm(m).capture_ratio)]));
  };
  if (!TREND_DRAWN) { TREND_DRAWN = true; draw(fn); } else fn();
}

function stripHtml(parkKey, mk) {
  const days = (P.parks[parkKey].days[mk] || []);
  return '<span class="strip" aria-hidden="true">' + days.map(d => {
    let c = 'none';
    if (isNum(d.coverage)) c = d.coverage >= 0.95 ? 'ok' : (d.coverage >= 0.5 ? 'part' : 'miss');
    return '<i class="' + c + '" title="' + dShort(d.date) + ': ' + (isNum(d.coverage) ? pct(d.coverage) + ' täckning, ' + fmt(d.energy_mwh, 1) + ' MWh' : 'ingen dagsljusdata') + '"></i>';
  }).join('') + '</span>';
}

function parkRow(k, mk) {
  const p = P.parks[k], m = p.months[mk];
  if (!m) return {k, html: '<tr class="park" data-park="' + k + '"><td>' + esc(p.info.name) + '</td><td>' + p.info.zone + '</td><td colspan="5" class="muted">Ingen data för perioden</td></tr>', sortv: {}};
  const low = isNum(m.coverage) && m.coverage < P.rules.good_coverage;
  const wm = low ? '<span class="warnmark" title="Ofullständig data – värdet är sannolikt för lågt">⚠</span>' : '';
  const vs = isNum(m.vs_budget)
    ? '<span class="delta ' + deltaCls(m.vs_budget, 0.005) + '">' + pct(m.vs_budget, 0, true) + '</span>'
    : '<span class="muted" title="Mindre än 80 % datatäckning">för lite data</span>';
  const html = '<tr class="park' + (STATE.park === k ? ' open' : '') + '" data-park="' + k + '" tabindex="0" aria-expanded="' + (STATE.park === k) + '">' +
    '<td>' + esc(p.info.name) + (p.info.type === 'tracker' ? '<span class="tag">tracker</span>' : '') + '</td>' +
    '<td>' + p.info.zone + '</td>' +
    '<td>' + fmt(m.energy_mwh) + wm + '</td>' +
    '<td>' + vs + '</td>' +
    '<td>' + fmt(m.yield_kwh_kwp, 0) + wm + '</td>' +
    '<td>' + fmt(m.capture_eur, 1) + '</td>' +
    '<td>' + pct(m.capture_ratio) + '</td>' +
    '<td>' + pct(m.coverage) + stripHtml(k, mk) + '</td></tr>';
  return {k, html, sortv: {name: p.info.name, zone: p.info.zone, energy: m.energy_mwh, vs: m.vs_budget, yield: m.yield_kwh_kwp,
    capture: m.capture_eur, ratio: m.capture_ratio, cov: m.coverage}};
}

function renderParkTable() {
  const mk = STATE.month, pm = P.portfolio[mk];
  const cols = [['name', 'Park', ''], ['zone', 'Zon', ''], ['energy', 'Produktion', 'MWh'], ['vs', 'Mot budget', 'för tid med data'],
    ['yield', 'Specifik yield', 'kWh/kWp'], ['capture', 'Capturepris', '€/MWh'], ['ratio', 'Capture-kvot', 'av spotpris'], ['cov', 'Datatäckning', 'dagsljus · per dag']];
  let rows = PARK_KEYS.map(k => parkRow(k, mk));
  let body = '';
  if (SORT.key) {
    rows.sort((a, b) => {
      const x = a.sortv[SORT.key], y = b.sortv[SORT.key];
      if (!isNum(x) && typeof x !== 'string') return 1;
      if (!isNum(y) && typeof y !== 'string') return -1;
      return (x > y ? 1 : x < y ? -1 : 0) * SORT.dir;
    });
    body = rows.map(r => r.html).join('');
  } else {
    ['SE4', 'SE3'].forEach(z => {
      const zr = rows.filter(r => P.parks[r.k].info.zone === z);
      if (zr.length) body += '<tr class="group"><td colspan="8">' + ZONE_NAMES[z] + '</td></tr>' + zr.map(r => r.html).join('');
    });
  }
  const total = '<tr class="total"><td>Portföljen</td><td></td><td>' + fmt(pm.energy_mwh) + '</td><td>' +
    (isNum(pm.vs_budget) ? '<span class="delta ' + deltaCls(pm.vs_budget, 0.005) + '">' + pct(pm.vs_budget, 0, true) + '</span>' : '–') +
    '</td><td>' + fmt(pm.yield_kwh_kwp, 0) + '</td><td>' + fmt(pm.capture_eur, 1) + '</td><td>' + pct(pm.capture_ratio) +
    '</td><td>' + pct(pm.coverage) + '</td></tr>';
  el('p-table').innerHTML = '<thead><tr>' + cols.map(c => '<th class="sortable" data-k="' + c[0] + '"' +
    (SORT.key === c[0] ? ' aria-sort="' + (SORT.dir > 0 ? 'ascending' : 'descending') + '"' : '') + '>' + c[1] +
    (c[2] ? '<span class="u">' + c[2] + '</span>' : '') + '</th>').join('') + '</tr></thead><tbody>' + body + total + '</tbody>';
  el('p-table').querySelectorAll('th.sortable').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.k;
    if (SORT.key === k) { if (SORT.dir === -1) SORT.dir = 1; else { SORT.key = null; } } else { SORT.key = k; SORT.dir = (k === 'name' || k === 'zone') ? 1 : -1; }
    renderParkTable();
  }));
  el('p-table').querySelectorAll('tr.park').forEach(tr => {
    const open = () => { STATE.park = STATE.park === tr.dataset.park ? null : tr.dataset.park; writeHash(); renderParkTable(); renderParkDetail(true); };
    tr.addEventListener('click', open);
    tr.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
  });
  el('p-strip-legend').innerHTML = 'Datatäckning per dag:' +
    '<span>Komplett<span class="strip"><i class="ok"></i></span></span>' +
    '<span>Delvis (50–95 %)<span class="strip"><i class="part"></i></span></span>' +
    '<span>Saknas<span class="strip"><i class="miss"></i></span></span>' +
    '<span>⚠ = under 95 % täckning, värdet är sannolikt för lågt</span>';
}

function renderParkDetail(scroll) {
  const k = STATE.park, box = el('p-detail');
  if (!k) { box.innerHTML = ''; return; }
  const p = P.parks[k], info = p.info, mk = STATE.month, m = p.months[mk], y = p.ytd[mk];
  const flags = D.datastatus.issues.filter(i => i.park === info.name).map(i => '<div class="flag">' + esc(i.text) + '</div>').join('');
  box.innerHTML = '<div class="park-detail" id="park-detail">' +
    '<button class="seg close" id="pd-close" aria-label="Stäng parkdetalj">Stäng ✕</button>' +
    '<h3 class="pd">' + esc(info.name) + '</h3>' +
    '<div class="facts">' + [info.zone, fmt(info.kwp / 1000, 1) + ' MWp', info.type === 'tracker' ? 'enaxlig tracker' : 'fast montage',
      info.grid_limit_mw ? 'nätgräns ' + fmt(info.grid_limit_mw, 1) + ' MW' : null, info.location, 'data sedan ' + dLabel(info.first_data)]
      .filter(Boolean).map(esc).join(' · ') + '</div>' + flags +
    '<div class="charts"><figure><figcaption><h3>Produktion per månad</h3><p>Stapel = uppmätt. Streck = budget för samma tid som har mätdata.</p></figcaption><div class="plot" id="pd-months"></div></figure>' +
    '<figure><figcaption><h3>Produktion per dag, ' + mLabel(mk) + '</h3><p>Stapel = uppmätt (ljus = ofullständig dag). Streck = dagens budget.</p></figcaption><div class="plot" id="pd-days"></div></figure></div>' +
    '<div class="tbl-wrap"><table><thead><tr><th>Period</th><th>Produktion<span class="u">MWh</span></th><th>Budget<span class="u">tid med data, MWh</span></th><th>Mot budget</th><th>Specifik yield<span class="u">kWh/kWp</span></th><th>Capturepris<span class="u">€/MWh</span></th><th>Datatäckning</th></tr></thead><tbody>' +
    (m ? '<tr><td>' + periodName(mk) + '</td><td>' + fmt(m.energy_mwh) + '</td><td>' + fmt(m.budget_obs_mwh) + '</td><td>' + pct(m.vs_budget, 1, true) + '</td><td>' + fmt(m.yield_kwh_kwp, 0) + '</td><td>' + fmt(m.capture_eur, 1) + '</td><td>' + pct(m.coverage) + '</td></tr>' : '') +
    (y ? '<tr><td>Hittills i år</td><td>' + fmt(y.energy_mwh) + '</td><td>' + fmt(y.compared_budget_mwh) + '</td><td>' + pct(y.vs_budget, 1, true) + '</td><td>' + fmt(y.yield_kwh_kwp, 0) + '</td><td>' + fmt(y.capture_eur, 1) + '</td><td>' + pct(y.coverage) + '</td></tr>' : '') +
    '</tbody></table></div><p class="note">Hittills i år jämförs bara månader med minst 80 % datatäckning mot budget; kolumnen Budget visar då budgeten för just de mätta perioderna.</p></div>';
  el('pd-close').addEventListener('click', () => { STATE.park = null; writeHash(); renderParkTable(); renderParkDetail(); });

  const months = Object.keys(p.months).filter(x => x <= mk).slice(-13);
  const mTicks = months.map((x, i) => (i === 0 || x.slice(5) === '01') ? MSHORT[+x.slice(5) - 1] + '<br>' + x.slice(0, 4) : MSHORT[+x.slice(5) - 1]);
  const barColor = cov => !isNum(cov) || cov < 0.8 ? css('--bar-missing') : (cov < 0.95 ? css('--bar-partial') : css('--bar'));
  plot('pd-months', [
    {type: 'bar', name: 'Uppmätt', x: months.map(x => mLabel(x, true)), y: months.map(x => p.months[x].energy_mwh),
     marker: {color: months.map(x => barColor(p.months[x].coverage))},
     customdata: months.map(x => [pct(p.months[x].coverage), pct(p.months[x].vs_budget, 1, true)]),
     hovertemplate: '%{y:,.0f} MWh · täckning %{customdata[0]} · mot budget %{customdata[1]}<extra></extra>'},
    {type: 'scatter', mode: 'markers', name: 'Budget (tid med data)', x: months.map(x => mLabel(x, true)), y: months.map(x => p.months[x].budget_obs_mwh),
     marker: {symbol: 'line-ew', size: 26, line: {width: 3, color: css('--ink')}}, hovertemplate: 'budget %{y:,.0f} MWh<extra></extra>'},
  ], layout({xaxis: {tickmode: 'array', tickvals: months.map(x => mLabel(x, true)), ticktext: mTicks, tickangle: 0},
              yaxis: {title: {text: 'MWh', standoff: 6}}, bargap: 0.35, margin: {l: 52, r: 12, t: 8, b: 44}}), PLOT_CFG);

  const days = p.days[mk] || [];
  plot('pd-days', [
    {type: 'bar', name: 'Uppmätt', x: days.map(d => d.date), y: days.map(d => d.energy_mwh),
     marker: {color: days.map(d => barColor(d.coverage === null ? null : (d.coverage >= 0.95 ? 1 : (d.coverage >= 0.5 ? 0.9 : 0))))},
     customdata: days.map(d => [pct(d.coverage)]), hovertemplate: '%{y:,.1f} MWh · täckning %{customdata[0]}<extra></extra>'},
    {type: 'scatter', mode: 'markers', name: 'Budget', x: days.map(d => d.date), y: days.map(d => d.budget_mwh),
     marker: {symbol: 'line-ew', size: 10, line: {width: 2.5, color: css('--ink')}}, hovertemplate: 'budget %{y:,.1f} MWh<extra></extra>'},
  ], layout({xaxis: {type: 'date', tickformat: '%-d %b', dtick: 7 * 86400000}, yaxis: {title: {text: 'MWh', standoff: 6}}, bargap: 0.25}), PLOT_CFG);
  if (scroll) el('park-detail').scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

// =====================================================================
// Elmarknaden
// =====================================================================
const M = D.marknad;
function zoneChips(target, zones, onChange) {
  const box = el(target);
  box.innerHTML = zones.map(z => '<button class="chip" style="--c:' + zc(z) + '" data-z="' + z + '" aria-pressed="' + STATE.zones.has(z) + '"><span class="sw"></span>' + ZONE_NAMES[z] + '</button>').join('');
  box.querySelectorAll('button.chip').forEach(b => b.addEventListener('click', () => {
    const z = b.dataset.z;
    if (STATE.zones.has(z)) { if (STATE.zones.size > 1) STATE.zones.delete(z); } else STATE.zones.add(z);
    syncChips(); onChange();
  }));
}
function rangeButtons(target) {
  const box = el(target);
  const wrap = document.createElement('span');
  wrap.style.marginLeft = 'auto';
  wrap.setAttribute('role', 'group');
  wrap.setAttribute('aria-label', 'Tidsperiod');
  wrap.innerHTML = [['36', 'Senaste 3 åren'], ['all', 'Sedan 2022']].map(([v, l]) => '<button class="seg" data-r="' + v + '" aria-pressed="' + (STATE.range === v) + '">' + l + '</button>').join(' ');
  box.appendChild(wrap);
  wrap.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    STATE.range = b.dataset.r;
    wrap.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x.dataset.r === STATE.range));
    redrawAll();
  }));
}
function syncChips() {
  document.querySelectorAll('button.chip[data-z]').forEach(b => { b.setAttribute('aria-pressed', STATE.zones.has(b.dataset.z)); b.style.setProperty('--c', zc(b.dataset.z)); });
}
function activeZones(zones) { return zones.filter(z => STATE.zones.has(z)); }

function renderMarket() {
  const ty = M.this_year, ly = String(+ty - 1);
  const parts = M.main_zones.map(z => {
    const cur = M.yearly[z][ty] || {}, prev = M.ytd_compare[z] || {};
    return '<b>' + z + '</b>: <b>' + pct(cur.capture_rate) + '</b> (samma period ' + ly + ': ' + pct(prev.capture_rate) + ')';
  });
  el('m-lede').innerHTML = 'Solel har i år fått ' + parts.join(', ') + ' av det genomsnittliga spotpriset. ' +
    'Spotpriset har samtidigt varit ' + M.main_zones.map(z => '<b>' + eur((M.yearly[z][ty] || {}).base) + '</b> i ' + z).join(' och ') + '.';
  el('m-scope').textContent = 'Från jan 2022 t.o.m. ' + dLabel(M.data_end);

  draw(() => {
    const months = STATE.range === 'all' ? M.months : M.months.slice(-(+STATE.range));
    const zs = activeZones(M.zones);
    plot('m-price', zs.map(z => ({type: 'scatter', mode: 'lines', name: z, x: months.map(mk => mk + '-15'),
      y: months.map(mk => (M.monthly[z][mk] || {}).base), line: {color: zc(z), width: 2}, connectgaps: false,
      hovertemplate: z + ': %{y:,.1f} €/MWh<extra></extra>'})),
      layout({xaxis: {type: 'date', tickformat: STATE.range === 'all' ? '%Y' : '%b %Y', dtick: STATE.range === 'all' ? 'M12' : 'M6', hoverformat: '%b %Y'}, yaxis: {title: {text: 'EUR/MWh', standoff: 6}}}), PLOT_CFG);
    dataTable('m-price-tbl', ['Månad'].concat(zs), months.slice().reverse().map(mk => [mLabel(mk, true)].concat(zs.map(z => fmt((M.monthly[z][mk] || {}).base, 1)))));

    const shown = months.filter(mk => zs.some(z => isNum((M.monthly[z][mk] || {}).capture_rate)));
    const cmax = Math.max(1.1, ...[].concat(...zs.map(z => months.map(mk => (M.monthly[z][mk] || {}).capture_rate).filter(isNum))));
    plot('m-capture', zs.map(z => ({type: 'scatter', mode: 'lines+markers', name: z, x: months.map(mk => mk + '-15'),
      y: months.map(mk => (M.monthly[z][mk] || {}).capture_rate), line: {color: zc(z), width: 2}, marker: {size: 5, color: zc(z)},
      connectgaps: false, hovertemplate: z + ': %{y:.0%}<extra></extra>'})),
      layout({xaxis: {type: 'date', tickformat: STATE.range === 'all' ? '%Y' : '%b %Y', dtick: STATE.range === 'all' ? 'M12' : 'M6', hoverformat: '%b %Y'},
              yaxis: {tickformat: '.0%', range: [0, cmax * 1.05], rangemode: 'normal'},
              shapes: [{type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 1, y1: 1, line: {color: css('--ink-3'), width: 1}}],
              annotations: [{xref: 'paper', x: 1, y: 1, yanchor: 'bottom', xanchor: 'right', text: '100 % = spotpriset', showarrow: false, font: {size: 11, color: css('--ink-3')}}]}), PLOT_CFG);
    dataTable('m-capture-tbl', ['Månad'].concat(zs), shown.slice().reverse().map(mk => [mLabel(mk, true)].concat(zs.map(z => pct((M.monthly[z][mk] || {}).capture_rate)))));
    renderMarketYears();
  });
  const sp = M.spread_se4_se3, spy = sp[ty], spl = sp[ly], spo = sp[String(+ty - 2)];
  if (spy) el('m-spread').innerHTML = 'SE4 har i år varit dyrare än SE3 <b>' + pct(spy.share_se4_higher) + '</b> av tiden, i snitt <b>' +
    signed(spy.mean_eur, 1) + ' €/MWh</b>. ' + ly + ': ' + pct(spl && spl.share_se4_higher) + ' av tiden (' + signed(spl && spl.mean_eur, 1) + ' €/MWh)' +
    (spo ? ', ' + (+ty - 2) + ': ' + pct(spo.share_se4_higher) + '.' : '.');
}

function renderMarketYears() {
  const ty = M.this_year, ly = String(+ty - 1);
  el('m-year-note').innerHTML = ty + ' gäller 1 jan–' + dShort(M.data_end) + ' och jämförs med samma period ' + ly +
    '. Jämför inte delåret med hela år: hösten och vintern har högre priser och högre capture rate.';
  const zs = activeZones(M.zones);
  el('m-years').innerHTML = zs.map(z => {
    const yrs = Object.keys(M.yearly[z]).filter(y => y >= '2022');
    const rows = yrs.map(y => [y === ty ? '<b>' + y + '</b> <span class="muted">t.o.m. ' + dShort(M.data_end) + '</span>' : y, M.yearly[z][y]]);
    rows.push([ly + ' <span class="muted">samma period</span>', M.ytd_compare[z] || {}]);
    let partial = false;
    const body = rows.map(([lbl, c]) => {
      const weak = c && isNum(c.solar_data_share) && c.solar_data_share < 0.9;
      partial = partial || weak;
      return '<tr><td>' + lbl + '</td><td>' + fmt(c.base, 1) + '</td><td>' + fmt(c.solar_price, 1) + '</td><td>' + pct(c.capture_rate) +
        (weak ? '<span class="warnmark" title="ENTSO-E saknar soldata för ' + pct(1 - c.solar_data_share) + ' av perioden">⚠</span>' : '') +
        '</td><td>' + fmt(c.neg_hours, 0) + '</td></tr>';
    }).join('');
    return '<div><h3 style="font-size:16px;margin:8px 0 0"><span style="color:' + zc(z) + '">●</span> ' + ZONE_NAMES[z] + '</h3><div class="tbl-wrap"><table><thead><tr><th>År</th>' +
      '<th>Spotpris<span class="u">€/MWh</span></th><th>Solpris<span class="u">€/MWh</span></th><th>Capture rate<span class="u">sol / spot</span></th><th>Negativa timmar<span class="u">h</span></th></tr></thead><tbody>' +
      body + '</tbody></table></div>' + (partial ? '<p class="note">⚠ ENTSO-E saknar soldata för mer än 10 % av perioden. Capture rate är osäker.</p>' : '') + '</div>';
  }).join('');
}

// =====================================================================
// Terminer
// =====================================================================
const F = D.terminer;
function renderFutures() {
  if (!F || !F.table) { el('f-lede').textContent = 'Terminsdata saknas.'; return; }
  el('f-scope').textContent = 'Senaste notering ' + dLabel(F.latest_date);
  if (F.lede) el('f-lede').innerHTML = F.lede;
  el('f-flags').innerHTML = (F.flags || []).map(f => '<div class="flag">' + esc(f) + '</div>').join('');
  const hz = F.zones;
  el('f-tables').innerHTML = hz.map(z => {
    const rows = F.contracts.map(c => {
      const r = F.table[z][c.label];
      if (!r) return '';
      const ch = key => {
        const x = r.changes[key];
        if (!x || !isNum(x.delta)) return '<td class="muted">–</td>';
        const stale = x.stale ? '<span class="warnmark" title="Närmaste notering före måldatum är från ' + dLabel(x.ref_date) + '">†</span>' : '';
        return '<td title="Mot ' + fmt(x.ref_value, 1) + ' €/MWh den ' + dLabel(x.ref_date) + '"><span class="delta ' + deltaCls(x.delta, 0.05) + '">' + signed(x.delta, 1) + '</span>' + stale + '</td>';
      };
      return '<tr><td>' + c.label + ' <span class="muted">' + esc(c.delivery) + '</span></td><td><b>' + fmt(r.value, 1) + '</b>' +
        (r.date !== F.latest_date ? '<span class="warnmark" title="Senaste kompletta notering ' + dLabel(r.date) + '">*</span>' : '') + '</td>' +
        ch('1v') + ch('1m') + ch('3m') + ch('12m') + '</tr>';
    }).join('');
    return '<div><h3 style="font-size:16px;margin:8px 0 0"><span style="color:' + zc(z) + '">●</span> ' + ZONE_NAMES[z] + ' — områdespris</h3><div class="tbl-wrap"><table><thead><tr><th>Kontrakt</th><th>Pris<span class="u">€/MWh</span></th><th>1 vecka</th><th>1 månad</th><th>3 månader</th><th>12 månader</th></tr></thead><tbody>' +
      rows + '</tbody></table></div></div>';
  }).join('') + '<p class="note" style="grid-column:1/-1">Förändring i €/MWh mot senaste notering på eller före samma datum tidigare. † = närmaste notering ligger mer än 10 dagar före måldatumet (lucka i datat). * = senaste dag där både SYS och EPAD finns.</p>';

  if (!STATE.contract) STATE.contract = F.default_contract;
  el('f-contracts').innerHTML = Object.keys(F.history).map(c => '<button class="seg" data-c="' + c + '" aria-pressed="' + (c === STATE.contract) + '">' + c + '</button>').join('');
  el('f-contracts').querySelectorAll('button').forEach(b => b.addEventListener('click', () => { STATE.contract = b.dataset.c; renderFutures(); }));
  draw(() => {
    const h = F.history[STATE.contract];
    if (!h) return;
    el('f-chart-title').textContent = STATE.contract + ' (' + (F.contract_meta[STATE.contract] || {}).delivery + ') över tid';
    const series = hz.map(z => ({type: 'scatter', mode: 'lines', name: z, x: h.dates, y: h[z], line: {color: zc(z), width: 2}, connectgaps: false,
      hovertemplate: z + ': %{y:,.1f} €/MWh<extra></extra>'}));
    series.push({type: 'scatter', mode: 'lines', name: 'SYS', x: h.dates, y: h.SYS, line: {color: css('--s-SYS'), width: 1.5}, connectgaps: false,
      hovertemplate: 'Systempris: %{y:,.1f} €/MWh<extra></extra>'});
    const gaps = (F.gaps || []).map(g => ({type: 'rect', xref: 'x', yref: 'paper', x0: g.from, x1: g.to, y0: 0, y1: 1, fillcolor: css('--grid'), line: {width: 0}, layer: 'below'}));
    plot('f-history', series, layout({xaxis: {type: 'date', hoverformat: '%-d %b %Y'}, yaxis: {title: {text: 'EUR/MWh', standoff: 6}, rangemode: 'normal'},
      shapes: gaps, showlegend: true, legend: {orientation: 'h', y: 1.08, x: 0}}), PLOT_CFG);
    dataTable('f-history-tbl', ['Datum'].concat(hz).concat(['SYS']), h.dates.map((d, i) => [dLabel(d)].concat(hz.map(z => fmt(h[z][i], 2))).concat([fmt(h.SYS[i], 2)])).reverse());
  });

  const cv = F.convergence || [];
  el('f-convergence').innerHTML = cv.length ? '<table><thead><tr><th>Kvartal</th>' + hz.map(z => '<th>' + z + ' termin<span class="u">sista före leverans</span></th><th>' + z + ' utfall<span class="u">spot</span></th><th>' + z + ' skillnad<span class="u">utfall − termin</span></th>').join('') + '</tr></thead><tbody>' +
    cv.map(r => '<tr><td>' + r.label + (r.partial ? ' <span class="muted">t.o.m. ' + dShort(r.partial) + '</span>' : '') + '</td>' + hz.map(z => {
      const x = r[z] || {};
      return '<td>' + fmt(x.forward, 1) + (x.forward_date ? ' <span class="muted">' + dShort(x.forward_date) + '</span>' : '') + '</td><td>' + fmt(x.realized, 1) + '</td><td><span class="delta ' + deltaCls(x.diff, 0.5) + '">' + signed(x.diff, 1) + '</span></td>';
    }).join('') + '</tr>').join('') + '</tbody></table>' : '<p class="note">Inga levererade kvartal med terminsdata.</p>';
}

// =====================================================================
// Batteri
// =====================================================================
const B = D.batteri;
function renderBattery() {
  const r12 = z => (B.per_zone[z] || {}).rolling_12m || {};
  const main = M.main_zones.filter(z => B.per_zone[z]);
  const best = main.slice().sort((a, b) => (r12(b).revenue_eur_mw || 0) - (r12(a).revenue_eur_mw || 0));
  if (best.length) {
    const z = best[0], o = best[1];
    el('b-lede').innerHTML = 'Ett batteri på 1 MW / 2 MWh i ' + z + ' hade kunnat tjäna högst <b>' + money(r12(z).revenue_eur_mw) + ' per MW</b> de senaste tolv månaderna' +
      (o ? ' (' + o + ': ' + money(r12(o).revenue_eur_mw) + ')' : '') + '. Det är ett tak med perfekt kännedom om priserna — inte en prognos.';
  }
  el('b-scope').textContent = 'Från jan 2023 t.o.m. ' + dLabel(r12(main[0]).to);
  draw(() => {
    const zs = activeZones(B.zones);
    const months = Array.from(new Set([].concat(...zs.map(z => Object.keys(B.per_zone[z].monthly))))).sort();
    plot('b-spread', zs.map(z => ({type: 'scatter', mode: 'lines', name: z, x: months.map(m => m + '-15'), y: months.map(m => (B.per_zone[z].monthly[m] || {}).spread_2h),
      line: {color: zc(z), width: 2}, hovertemplate: z + ': %{y:,.0f} €/MWh<extra></extra>'})),
      layout({xaxis: {type: 'date', tickformat: '%Y', dtick: 'M12', hoverformat: '%b %Y'}, yaxis: {title: {text: 'EUR/MWh', standoff: 6}}}), PLOT_CFG);
    dataTable('b-spread-tbl', ['Månad'].concat(zs), months.slice().reverse().map(m => [mLabel(m, true)].concat(zs.map(z => fmt((B.per_zone[z].monthly[m] || {}).spread_2h, 1)))));
    plot('b-rev', zs.map(z => ({type: 'scatter', mode: 'lines', name: z, x: months.map(m => m + '-15'), y: months.map(m => (B.per_zone[z].monthly[m] || {}).revenue_eur_mw),
      line: {color: zc(z), width: 2}, hovertemplate: z + ': %{y:,.0f} €/MW<extra></extra>'})),
      layout({xaxis: {type: 'date', tickformat: '%Y', dtick: 'M12', hoverformat: '%b %Y'}, yaxis: {title: {text: 'EUR per MW', standoff: 6}}}), PLOT_CFG);
    dataTable('b-rev-tbl', ['Månad'].concat(zs), months.slice().reverse().map(m => [mLabel(m, true)].concat(zs.map(z => fmt((B.per_zone[z].monthly[m] || {}).revenue_eur_mw, 0)))));
    const years = Array.from(new Set([].concat(...zs.map(z => Object.keys(B.per_zone[z].yearly))))).sort();
    const lastYear = years[years.length - 1];
    el('b-years').innerHTML = '<table><thead><tr><th>Elområde</th>' + years.map(y => '<th>' + y + '<span class="u">' +
      (y === lastYear ? 'jan–' + dShort(r12(zs[0]).to || '2026-01-01') : 'helår') + '</span></th>').join('') +
      '<th>Senaste 12 mån<span class="u">EUR per MW</span></th><th>Median per dag<span class="u">senaste 12 mån</span></th><th>Dagsspread<span class="u">snitt 12 mån, €/MWh</span></th></tr></thead><tbody>' +
      zs.map(z => '<tr><td><span style="color:' + zc(z) + '">●</span> ' + ZONE_NAMES[z] + '</td>' + years.map(y => '<td>' + fmt((B.per_zone[z].yearly[y] || {}).revenue_eur_mw) + '</td>').join('') +
        '<td><b>' + fmt(r12(z).revenue_eur_mw) + '</b></td><td>' + money(r12(z).daily_median) + '</td><td>' + fmt(r12(z).spread_2h, 0) + '</td></tr>').join('') + '</tbody></table>';
  });
  const notes = [];
  main.forEach(z => { const q = (B.per_zone[z] || {}).quarter_uplift; if (q && isNum(q.uplift)) notes.push(z + ' ' + pct(q.uplift, 0, true)); });
  const zz = best[0] ? r12(best[0]) : null;
  el('b-notes').innerHTML = 'Antaganden: 1 MW / 2 MWh, högst en full laddning per dygn, 88 % verkningsgrad tur och retur, timpriser. ' +
    'Ej med: nätavgifter, degradering, stödtjänster (FCR/aFRR) och att fler batterier pressar spreadarna. ' +
    (notes.length ? 'Handel på kvartspriser (sedan 1 okt 2025) höjer taket: ' + notes.join(', ') + '. ' : '') +
    (zz && isNum(zz.top10pct_share) ? 'De 10 % bästa dagarna står för ' + pct(zz.top10pct_share) + ' av intäkten i ' + best[0] + ' — intäkten bärs av vardagen, inte av några få toppar.' : '');
}

// =====================================================================
// Datastatus
// =====================================================================
function renderStatus() {
  const S = D.datastatus;
  el('d-scope').textContent = 'Kontrollerat ' + dLabel(S.ref_day);
  el('d-issues').innerHTML = S.issues.length ? S.issues.map(i => '<li><b>' + esc(i.park) + ':</b> ' + esc(i.text) + '</li>').join('') : '<li>Inga kända problem.</li>';
  const st = s => '<span class="status-' + s + '">' + ({ok: 'aktuell', gammal: 'inaktuell', saknas: 'saknas'})[s] + '</span>';
  el('d-sources').innerHTML = '<table><thead><tr><th>Källa</th><th>Senaste data</th><th>Status</th></tr></thead><tbody>' +
    S.sources.map(s => '<tr><td>' + esc(s.name) + ' <span class="muted">' + esc(s.source) + '</span></td><td>' + dLabel(s.last) + '</td><td>' + st(s.status) + '</td></tr>').join('') +
    S.parks.map(p => '<tr><td>' + esc(p.park) + ' <span class="muted">elmätare, Bazefield</span></td><td>' + dLabel(p.last_meter) + '</td><td>' + st(p.status) + '</td></tr>').join('') +
    '</tbody></table>';
  el('d-defs').innerHTML = D.definitions.map(d => '<dt>' + esc(d[0]) + '</dt><dd>' + d[1] + '</dd>').join('');
  el('footer').innerHTML = 'Genererad av <code>generate_oversikt.py</code> · data ' + esc(D.dataset) + '. Siffrorna är beräknade ur lokala filer i Resultat/ och kan återskapas.';
}

// ---------- start ----------
safe(renderMeta);
safe(monthOptions);
safe(renderPortfolio);
safe(() => { zoneChips('m-zones', M.zones, () => redrawAll()); rangeButtons('m-zones'); });
safe(() => zoneChips('b-zones', B.zones, () => redrawAll()));
safe(renderMarket);
safe(renderFutures);
safe(renderBattery);
safe(renderStatus);
safe(syncChips);
(function scrollToTarget() {
  const id = location.hash.slice(1);
  const target = STATE.park ? el('park-detail') : (id && /^[a-z]+$/.test(id) ? el(id) : null);
  if (target) requestAnimationFrame(() => window.scrollTo({top: target.getBoundingClientRect().top + window.scrollY - 64, behavior: 'auto'}));
})();
"""


def _plotly_tag() -> str:
    if PLOTLY_VENDOR.exists():
        source = PLOTLY_VENDOR.read_text(encoding="utf-8")
        if "</script" not in source.lower():
            return f"<script>{source}</script>"
    return f"<script src=\"{PLOTLY_URL}\" charset=\"utf-8\"></script>"


def render_oversikt(data: Dict[str, Any]) -> str:
    title = "Översikt — solportföljen och elmarknaden"
    return (
        "<!DOCTYPE html>\n<html lang=\"sv\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{esc(title)}</title>\n"
        "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">\n"
        "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>\n"
        f"<link rel=\"stylesheet\" href=\"{FONTS_URL}\">\n"
        f"<style>{CSS}</style>\n"
        f"{_plotly_tag()}\n"
        "</head>\n<body>\n"
        f"{BODY}\n"
        f"<script>const D = {script_json(data)};</script>\n"
        f"<script>{JS}</script>\n"
        "</body>\n</html>\n"
    )
