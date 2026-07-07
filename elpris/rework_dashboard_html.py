"""Renderare för rework-dashboarden — "Nordic Clarity".

Egen visuell identitet, avsiktligt skild från Track C (Nordic
Editorial): sval ljus bas, petrol/teal-accent, bärnsten för sol,
toppnavigering med sticky sektionslänkar och en rapportlik läsordning
— klartext först, graf sen.

Publik ingång:

    >>> from elpris.rework_dashboard_data import build_rework_data
    >>> from elpris.rework_dashboard_html import render_rework
    >>> html = render_rework(build_rework_data())

Self-contained HTML: Plotly + Google Fonts via CDN, all data inbäddad
som JSON, all CSS/JS inline. Grafer lazy-renderas via
IntersectionObserver så initial load är snabb trots ~25 grafer.
"""

from __future__ import annotations

from typing import Any, Dict

from .dashboard_common import esc, script_json


def render_rework(data: Dict[str, Any]) -> str:
    """Rendera rework-dashboarden som en HTML-sträng."""
    data_json = script_json(data)

    html = _SHELL
    html = html.replace("__GENERATED__", esc(data.get("generated", "")))
    html = html.replace("__CSS__", _CSS)
    html = html.replace("__DATA_JSON__", data_json)
    html = html.replace("__JS__", _JS)
    return html


# ---------------------------------------------------------------------------
# HTML-skal
# ---------------------------------------------------------------------------

_SHELL = """<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Svea Solar — Portfölj &amp; Marknad</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%230e7c86'/%3E%3Ccircle cx='22' cy='10' r='5' fill='%23de9b26'/%3E%3C/svg%3E">
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
      <div class="brand-title">Svea Solar · Portfölj &amp; Marknad</div>
      <div class="brand-sub">Genererad __GENERATED__ · <span id="coverage-line"></span></div>
    </div>
  </div>
  <nav class="topnav" id="topnav">
    <a href="#oversikt" data-sec="oversikt">Översikt</a>
    <a href="#marknad" data-sec="marknad">Marknaden</a>
    <a href="#capture" data-sec="capture">Capture</a>
    <a href="#parker" data-sec="parker">Parkerna</a>
    <a href="#risk" data-sec="risk">Risk &amp; intäkt</a>
    <a href="#datakvalitet" data-sec="datakvalitet">Datakvalitet</a>
  </nav>
</header>

<main>

<!-- ============ 1. ÖVERSIKT ============ -->
<section id="oversikt">
  <div class="sec-head">
    <div class="kicker">Portföljen</div>
    <h1 id="hero-title">Översikt</h1>
    <p class="takeaway" id="oversikt-takeaway"></p>
  </div>
  <div class="kpi-strip" id="kpi-strip"></div>
  <div class="callouts" id="callouts-oversikt"></div>
  <div class="grid">
    <div class="card span2">
      <div class="card-head"><h3>Produktion mot budget — senaste 13 månaderna</h3>
        <p>Staplar = faktisk produktion (MWh), linje = PVsyst-budget. Pågående månad visas tonad (MTD, pro-ratad budget).</p></div>
      <div class="chart" id="ch-fleet-series" data-render="fleetSeries"></div>
    </div>
    <div class="card span2">
      <div class="card-head"><h3>Parkerna hittills i år</h3>
        <p>Sorterbar — klicka på kolumnrubrik.</p></div>
      <div class="tbl-wrap" id="tbl-park-ytd"></div>
    </div>
  </div>
</section>

<!-- ============ 2. MARKNADEN ============ -->
<section id="marknad">
  <div class="sec-head">
    <div class="kicker">Elmarknaden</div>
    <h2>Strukturella pristrender</h2>
    <p class="takeaway">Kris, normalisering, återhämtning — och en duck curve som fördjupas i takt med solutbyggnaden.</p>
  </div>
  <div class="callouts" id="callouts-marknad"></div>
  <div class="grid">
    <div class="card span2">
      <div class="card-head"><h3>Spotpris per elområde — månadssnitt</h3>
        <p>EUR/MWh sedan 2021-11. Energikrisen 2021–22 följdes av normalisering och en gradvis återhämtning.</p></div>
      <div class="chart" id="ch-spot-monthly" data-render="spotMonthly"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>Duck curve — prisprofil över dygnet</h3>
        <p>Snittpris per timme (lokal tid) och år. Middagsgropen är solens fotavtryck.</p>
        <div class="seg" id="seg-duck-zone"></div></div>
      <div class="chart" id="ch-duck" data-render="duckCurve"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>Negativa pristimmar per år</h3>
        <p>Antal timmar med negativt spotpris. Ofullständiga år markerade med *.</p></div>
      <div class="chart" id="ch-neg-hours" data-render="negHours"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>Intradagsspread — flexvärdets puls</h3>
        <p>Genomsnittlig daglig spread (dyraste − billigaste timme), månadsvis. Det BESS och styrbar förbrukning lever av.</p></div>
      <div class="chart" id="ch-spread-daily" data-render="spreadDaily"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>Zonspreadar</h3>
        <p>Månadssnitt av prisskillnaden mellan elområden — flaskhalsarnas pris.</p></div>
      <div class="chart" id="ch-zone-spreads" data-render="zoneSpreads"></div>
    </div>
    <div class="card span2">
      <div class="card-head"><h3>Prislandskapet — månad × timme</h3>
        <p>Snittpris (EUR/MWh, lokal tid).</p>
        <div class="seg-row"><div class="seg" id="seg-heat-zone"></div><div class="seg" id="seg-heat-year"></div></div></div>
      <div class="chart" id="ch-heatmap" data-render="heatmap"></div>
    </div>
  </div>
</section>

<!-- ============ 3. CAPTURE ============ -->
<section id="capture">
  <div class="sec-head">
    <div class="kicker">Solens marknadsvärde</div>
    <h2>Capture &amp; cannibalisering</h2>
    <p class="takeaway">Varje ny megawatt sol pressar priset i just de timmar solen levererar. Orientering och tracking är motmedlen.</p>
  </div>
  <div class="callouts" id="callouts-capture"></div>
  <div class="grid">
    <div class="card">
      <div class="card-head"><h3>Capture ratio per år</h3>
        <p>Sydvänd solprofil: capture-pris / baseload. Under 1,0 = sol tjänar mindre än snittpriset.</p></div>
      <div class="chart" id="ch-ratio-yearly" data-render="ratioYearly"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>Capture-pris vs baseload, månadsvis</h3>
        <div class="seg" id="seg-capm-zone"></div></div>
      <div class="chart" id="ch-capture-monthly" data-render="captureMonthly"></div>
    </div>
    <div class="card span2">
      <div class="card-head"><h3>Cannibalisering — installerad sol mot capture ratio</h3>
        <p>Staplar = installerad solkapacitet i zonen (Energimyndigheten, t.o.m. 2024, län→zon-approximation). Linje = capture ratio sol syd.</p>
        <div class="seg" id="seg-cann-zone"></div></div>
      <div class="chart" id="ch-cannibal" data-render="cannibal"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>Orienteringspremie mot syd</h3>
        <p>Capture-pris för öst-väst och tracker relativt sydvänd profil, per år.</p>
        <div class="seg" id="seg-orient-zone"></div></div>
      <div class="chart" id="ch-orient-premium" data-render="orientPremium"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>€ per kWp och år — det som räknas</h3>
        <p>Capture-pris × specifik TMY-produktion (911/1012/1202 kWh/kWp för öst-väst/syd/tracker).</p></div>
      <div class="chart" id="ch-orient-eurkwp" data-render="orientEurKwp"></div>
    </div>
    <div class="card span2">
      <div class="card-head"><h3>Varför orientering spelar roll — juniprofil mot junipris</h3>
        <p>Normaliserade TMY-produktionsprofiler (vänster axel) mot junidygnets snittpris (höger axel). Öst-väst flyttar produktion till dygnets dyrare flanker.</p></div>
      <div class="chart" id="ch-profile-shapes" data-render="profileShapes"></div>
    </div>
    <div class="card span2">
      <div class="card-head"><h3>Sanity check — PVsyst-profiler mot faktisk ENTSO-E-sol</h3>
        <p>Capture beräknat på modellprofiler vs verklig solproduktion i zonen. Litet fel = trovärdiga modellsiffror ovan.</p></div>
      <div class="tbl-wrap" id="tbl-validation"></div>
    </div>
  </div>
</section>

<!-- ============ 4. PARKERNA ============ -->
<section id="parker">
  <div class="sec-head">
    <div class="kicker">Asset management</div>
    <h2>Parkerna</h2>
    <p class="takeaway" id="parker-takeaway"></p>
  </div>
  <div class="grid">
    <div class="card span2">
      <div class="card-head"><h3 id="league-title">Senaste stängda månad</h3>
        <p>Sorterbar league table. Capture = realiserad (Bazefield-volym × spot, effective power).</p></div>
      <div class="tbl-wrap" id="tbl-league"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>Specifik produktion, kWh/kWp</h3>
        <p>Månadsvis per park — klicka i legenden för att isolera.</p></div>
      <div class="chart" id="ch-specific-yield" data-render="specificYield"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>Tracker-effekten — Hova mot fast montage</h3>
        <p>Hova är portföljens enda tracker; merproduktion mot Björke + Skäkelbacken (fast, SE3) är väntad och visar teknikens värde.</p></div>
      <div class="chart" id="ch-tracker-gain" data-render="trackerGain"></div>
    </div>
    <div class="card span2">
      <div class="card-head"><h3>Produktion i negativa pristimmar</h3>
        <p>MWh exporterad vid negativt spotpris, per park och månad. Curtailment-kandidaten nummer ett.</p></div>
      <div class="chart" id="ch-neg-exposure" data-render="negExposure"></div>
    </div>
  </div>

  <div class="park-detail-head">
    <h2>Djupdyk per park</h2>
    <div class="seg seg-lg" id="seg-park"></div>
  </div>
  <div id="park-detail"></div>
</section>

<!-- ============ 5. RISK & INTÄKT ============ -->
<section id="risk">
  <div class="sec-head">
    <div class="kicker">Prissäkring &amp; exponering</div>
    <h2>Risk &amp; intäkt</h2>
    <p class="takeaway" id="risk-takeaway">Terminskurvan, PPA-böckerna och obalanskostnaden — portföljens marknadsexponering i tre vyer.</p>
  </div>
  <div class="callouts" id="callouts-risk"></div>
  <div class="grid">
    <div class="card">
      <div class="card-head"><h3>Forwardkurvan per elområde</h3>
        <p id="fwd-note">SYS + EPAD per kontrakt.</p></div>
      <div class="chart" id="ch-forward-curve" data-render="forwardCurve"></div>
    </div>
    <div class="card">
      <div class="card-head"><h3>Forwardens träffsäkerhet</h3>
        <p>Sista forward-fix mot realiserat spotsnitt för levererade kontrakt.</p>
        <div class="seg" id="seg-fwdacc-zone"></div></div>
      <div class="chart" id="ch-forward-accuracy" data-render="forwardAccuracy"></div>
    </div>
    <div class="card span2">
      <div class="card-head"><h3>PPA-boken mot marknaden</h3>
        <p id="ppa-note">Kontrakterat PPA-pris (EUR-konverterat, tidsviktat) mot realiserad spot-capture och forwardkurvan.</p></div>
      <div class="chart" id="ch-ppa" data-render="ppaChart"></div>
      <div class="tbl-wrap" id="tbl-ppa"></div>
    </div>
    <div class="card span2">
      <div class="card-head"><h3>Obalanskostnad (eSett) — vad prognosfel kostar</h3>
        <p>Månadssnitt av |obalanspris − spot| per zon. Streckad linje = P90 för SE3 (svansrisken).</p></div>
      <div class="chart" id="ch-imbalance" data-render="imbalance"></div>
    </div>
  </div>
</section>

<!-- ============ 6. DATAKVALITET ============ -->
<section id="datakvalitet">
  <div class="sec-head">
    <div class="kicker">Ops-hygien</div>
    <h2>Datakvalitet</h2>
    <p class="takeaway">Tyst sensorröta förstör analyser långt innan någon märker det. Senaste 90 dagarna per park.</p>
  </div>
  <div class="grid">
    <div class="card span2">
      <div class="tbl-wrap" id="tbl-quality"></div>
    </div>
  </div>
</section>

</main>

<footer>
  <div class="foot-grid">
    <div>
      <h4>Datakällor</h4>
      <ul id="foot-sources"></ul>
    </div>
    <div>
      <h4>Ordlista</h4>
      <ul class="glossary">
        <li><b>Capture-pris</b> — produktionsviktat snittpris: Σ(pris × volym) / Σ(volym).</li>
        <li><b>Capture ratio</b> — capture-pris / baseload (tidsviktat snittpris). &lt; 1,0 = profilen tjänar mindre än snittet.</li>
        <li><b>Specifik produktion</b> — kWh per installerad kWp.</li>
        <li><b>PR</b> — Performance Ratio: faktisk produktion / (instrålning × kapacitet).</li>
        <li><b>EPAD</b> — termin på prisskillnaden mellan elområde och systempris.</li>
        <li><b>Effective power</b> — grid-mätare när den finns, annars inverter-summa (hanterar mätarbortfall).</li>
      </ul>
    </div>
  </div>
  <div class="foot-note">Svea Solar · intern analys · genererad __GENERATED__</div>
</footer>

<script>const DATA = __DATA_JSON__;</script>
<script>__JS__</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# CSS — Nordic Clarity
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
section { padding-top: 44px; }
.sec-head { max-width: 860px; margin-bottom: 18px; }
.kicker {
  text-transform: uppercase; letter-spacing: .14em; font-size: 11px;
  font-weight: 700; color: var(--teal); margin-bottom: 6px;
}
h1, h2 { margin: 0 0 10px; letter-spacing: -.02em; line-height: 1.15; }
h1 { font-size: 34px; font-weight: 800; }
h2 { font-size: 27px; font-weight: 800; }
.takeaway {
  font-family: 'Source Serif 4', serif; font-size: 17.5px;
  color: var(--muted); margin: 0;
}

/* ---------- KPI-strip ---------- */
.kpi-strip {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px; margin: 22px 0 6px;
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

/* ---------- Callouts (klartext) ---------- */
.callouts { display: grid; gap: 10px; margin: 18px 0 8px; max-width: 980px; }
.callout {
  background: var(--card); border: 1px solid var(--line);
  border-left: 4px solid var(--teal); border-radius: 8px;
  padding: 11px 16px; font-family: 'Source Serif 4', serif;
  font-size: 15.5px; box-shadow: var(--shadow);
}
.callout.pos { border-left-color: var(--green); }
.callout.neg { border-left-color: var(--coral); }

/* ---------- Kortgrid ---------- */
.grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 18px;
}
.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 16px 18px 12px; min-width: 0;
}
.card.span2 { grid-column: span 2; }
.card-head h3 { margin: 0 0 4px; font-size: 15.5px; font-weight: 700; }
.card-head p { margin: 0 0 8px; color: var(--muted); font-size: 12.5px; }
.chart { width: 100%; min-height: 340px; }
.chart.tall { min-height: 420px; }

/* ---------- Segmented controls ---------- */
.seg-row { display: flex; gap: 10px; flex-wrap: wrap; }
.seg { display: inline-flex; gap: 2px; background: var(--bg);
  border: 1px solid var(--line); border-radius: 8px; padding: 2px; margin: 4px 0; }
.seg button {
  border: 0; background: transparent; padding: 5px 12px; border-radius: 6px;
  font: 600 12.5px 'Inter', sans-serif; color: var(--muted); cursor: pointer;
}
.seg button.on { background: var(--navy); color: #fff; }
.seg-lg button { padding: 7px 15px; font-size: 13.5px; }

/* ---------- Tabeller ---------- */
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
tbody tr { border-bottom: 1px solid var(--line); }
tbody tr:hover { background: #f2f7f8; }
td.pos { color: var(--green); font-weight: 600; }
td.neg { color: var(--coral); font-weight: 600; }
.badge { display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 11.5px; font-weight: 700; }
.badge.ok { background: #e2f3ea; color: #1d7a4e; }
.badge.warn { background: #fcf0d8; color: #9a6c10; }
.badge.bad { background: #fbe5e1; color: #b03a28; }
.zone-tag { display: inline-block; padding: 1px 7px; border-radius: 5px;
  font-size: 11px; font-weight: 700; background: var(--teal-soft);
  color: var(--teal-deep); margin-left: 6px; }

/* ---------- Parkdetalj ---------- */
.park-detail-head { margin-top: 44px; }
.park-detail-head h2 { margin-bottom: 12px; }
#park-detail .facts {
  display: flex; gap: 22px; flex-wrap: wrap; background: var(--card);
  border: 1px solid var(--line); border-radius: var(--radius);
  box-shadow: var(--shadow); padding: 14px 18px; margin: 14px 0;
  font-size: 12.5px; color: var(--muted);
}
#park-detail .facts b { color: var(--ink); display: block; font-size: 13.5px; }
#park-detail .grid { margin-top: 12px; }

/* ---------- Footer ---------- */
footer { border-top: 1px solid var(--line); background: var(--card);
  padding: 32px 28px 40px; }
.foot-grid { max-width: 1240px; margin: 0 auto; display: grid;
  grid-template-columns: 1fr 1fr; gap: 32px; }
footer h4 { margin: 0 0 8px; font-size: 13px; }
footer ul { margin: 0; padding-left: 18px; color: var(--muted); font-size: 12.5px; }
footer li { margin-bottom: 4px; }
.foot-note { max-width: 1240px; margin: 24px auto 0; color: var(--faint);
  font-size: 12px; }

@media (max-width: 880px) {
  .grid { grid-template-columns: 1fr; }
  .card.span2 { grid-column: span 1; }
  .foot-grid { grid-template-columns: 1fr; }
}
@media print {
  .topbar { position: static; } .topnav { display: none; }
  .card { break-inside: avoid; box-shadow: none; }
}
"""

# ---------------------------------------------------------------------------
# JS — rendering
# ---------------------------------------------------------------------------

_JS = r"""
'use strict';

/* ================= Tokens & helpers ================= */
const C = {
  ink: '#16242f', muted: '#5b6b78', faint: '#8a98a4', line: '#e3e9ed',
  teal: '#0e7c86', tealDeep: '#0a5961', amber: '#de9b26', coral: '#d95f4c',
  green: '#2e9e6b', navy: '#1d3a4f',
  zones: { SE1: '#9db4c4', SE2: '#5b87a6', SE3: '#0e7c86', SE4: '#d97742' },
  parks: ['#0e7c86','#d97742','#5b87a6','#de9b26','#7c6cae','#2e9e6b',
          '#c25674','#8a98a4'],
};
const MONTHS_SV = ['jan','feb','mar','apr','maj','jun','jul','aug','sep','okt','nov','dec'];
const nf = (d) => new Intl.NumberFormat('sv-SE', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmt = (x, d=0) => (x === null || x === undefined || Number.isNaN(x)) ? '–' : nf(d).format(x);
const fmtSign = (x, d=1) => (x === null || x === undefined) ? '–'
  : (x >= 0 ? '+' : '−') + nf(d).format(Math.abs(x)) + ' %';
const mLabel = (ym) => { const [y, m] = ym.split('-'); return MONTHS_SV[+m-1] + ' ' + y.slice(2); };
const esc = (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

function baseLayout(over) {
  return Object.assign({
    font: { family: 'Inter, sans-serif', size: 12, color: C.ink },
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { l: 52, r: 18, t: 12, b: 40 },
    xaxis: { gridcolor: C.line, zerolinecolor: C.line, tickfont: { size: 11 } },
    yaxis: { gridcolor: C.line, zerolinecolor: C.line, tickfont: { size: 11 } },
    legend: { orientation: 'h', y: 1.12, x: 0, font: { size: 11.5 } },
    hovermode: 'x unified',
    hoverlabel: { bgcolor: '#fff', bordercolor: C.line, font: { size: 12, color: C.ink } },
  }, over || {});
}
const PCONF = { displayModeBar: false, responsive: true };
function plot(id, traces, layout) {
  const el = document.getElementById(id);
  if (el) Plotly.newPlot(el, traces, layout, PCONF);
}

/* Segmented control */
function seg(containerId, options, def, onChange) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '';
  options.forEach(opt => {
    const b = document.createElement('button');
    b.textContent = opt.label ?? opt;
    const val = opt.value ?? opt;
    if (val === def) b.classList.add('on');
    b.onclick = () => {
      el.querySelectorAll('button').forEach(x => x.classList.remove('on'));
      b.classList.add('on');
      onChange(val);
    };
    el.appendChild(b);
  });
}

/* Sorterbar tabell */
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

/* ================= Lazy rendering ================= */
const RENDERERS = {};
const rendered = new Set();
function lazyInit() {
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const fn = e.target.dataset.render;
      if (fn && RENDERERS[fn] && !rendered.has(e.target.id)) {
        rendered.add(e.target.id);
        try { RENDERERS[fn](); } catch (err) {
          console.error('render', fn, err);
          e.target.innerHTML = '<p style="color:#b03a28;padding:20px">Kunde inte rendera: ' + esc(err.message) + '</p>';
        }
      }
      obs.unobserve(e.target);
    });
  }, { rootMargin: '300px' });
  document.querySelectorAll('[data-render]').forEach(el => obs.observe(el));
}

/* ================= Gemensam data ================= */
const PF = DATA.portfolio || {};
const MA = (DATA.market_analysis || {}).zones || {};
const MA_ZONES = Object.keys(MA);
const HOME = MA_ZONES.includes('SE3') ? 'SE3' : MA_ZONES[0];
const PARKS = (DATA.assets || {}).parks || {};
const PARK_KEYS = Object.keys(PARKS)
  .sort((a, b) => (PARKS[b].capacity_mwp || 0) - (PARKS[a].capacity_mwp || 0));
const parkColor = {};
PARK_KEYS.forEach((k, i) => parkColor[k] = C.parks[i % C.parks.length]);

function lastCompleteYear(zone) {
  const ys = (MA[zone] || {}).yearly || [];
  const compl = ys.filter(y => y.complete);
  return compl.length ? compl[compl.length - 1].year : (ys.length ? ys[ys.length-1].year : null);
}

/* ================= Header / footer ================= */
function renderHeader() {
  const cov = (DATA.meta || {}).coverage || {};
  document.getElementById('coverage-line').textContent =
    'spot t.o.m. ' + (cov.spot_through || '–') + ' · parker t.o.m. ' + (cov.parks_through || '–');
  const src = document.getElementById('foot-sources');
  const rows = [
    ['Spotpriser (elprisetjustnu.se)', cov.spot_through],
    ['Solparker (Bazefield, 15 min)', cov.parks_through],
    ['Futures (Nasdaq SYS + EPAD)', cov.futures_through],
    ['Obalanspriser (eSett)', cov.esett_through],
    ['Installerad kapacitet (Energimyndigheten)', cov.installed_through],
    ['Produktion (ENTSO-E)', cov.spot_through],
  ];
  src.innerHTML = rows.map(([n, d]) =>
    '<li>' + esc(n) + ' — t.o.m. <b>' + esc(d ?? '–') + '</b></li>').join('');
}

function renderCallouts() {
  const ins = DATA.insights || {};
  [['oversikt','callouts-oversikt'], ['marknad','callouts-marknad'],
   ['capture','callouts-capture'], ['risk','callouts-risk']].forEach(([k, id]) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = (ins[k] || []).map(c =>
      '<div class="callout ' + esc(c.tone) + '">' + esc(c.text) + '</div>').join('');
  });
}

/* ================= 1. Översikt ================= */
function renderKpis() {
  const ytd = PF.ytd || {}, lc = PF.latest_closed || {};
  const el = document.getElementById('kpi-strip');
  const vsCls = (x) => (x ?? 0) >= 0 ? 'delta-pos' : 'delta-neg';
  const cells = [
    { lbl: 'Installerad kapacitet', val: fmt(PF.total_capacity_mwp, 1), unit: 'MWp',
      sub: PF.park_count + ' parker · SE3 + SE4' },
    { lbl: 'Produktion ' + (ytd.year ?? ''), val: fmt(ytd.energy_mwh), unit: 'MWh',
      sub: '<span class="' + vsCls(ytd.vs_budget_pct) + '">' + fmtSign(ytd.vs_budget_pct) + '</span> mot budget' },
    { lbl: 'Intäkt ' + (ytd.year ?? '') + ' (PPA-mix)', val: fmt((ytd.revenue_ppa_eur ?? 0) / 1000), unit: 'k€',
      sub: 'spot: ' + fmt((ytd.revenue_eur ?? 0) / 1000) + ' k€' },
    { lbl: 'Capture ' + (lc.month ? mLabel(lc.month) : ''), val: fmt(lc.capture, 1), unit: '€/MWh',
      sub: '<span class="' + vsCls(lc.capture_premium_pct) + '">' + fmtSign(lc.capture_premium_pct) + '</span> mot baseload' },
    { lbl: 'Tillgänglighet ' + (lc.month ? mLabel(lc.month) : ''), val: fmt(lc.availability_pct, 1), unit: '%',
      sub: 'kapacitetsviktad' },
  ];
  el.innerHTML = cells.map(c =>
    '<div class="kpi"><div class="lbl">' + c.lbl + '</div>' +
    '<div class="val">' + c.val + ' <span class="unit">' + c.unit + '</span></div>' +
    '<div class="sub">' + c.sub + '</div></div>').join('');

  const t = document.getElementById('oversikt-takeaway');
  if (ytd.year) {
    const rel = (ytd.vs_budget_pct ?? 0) >= 0 ? 'över' : 'under';
    t.textContent = 'Portföljen ligger ' + fmt(Math.abs(ytd.vs_budget_pct ?? 0), 1) +
      ' % ' + rel + ' budget hittills ' + ytd.year + '. Allt nedan är läsbart uppifrån och ner — siffrorna förklarar sig själva i klartext.';
  }
}

RENDERERS.fleetSeries = function () {
  const s = PF.fleet_series || [];
  const x = s.map(m => mLabel(m.month));
  plot('ch-fleet-series', [
    { type: 'bar', x, y: s.map(m => m.energy_mwh), name: 'Produktion',
      marker: { color: s.map(m => m.is_partial ? 'rgba(14,124,134,.35)' : C.teal) },
      hovertemplate: '%{y:.0f} MWh<extra>Produktion</extra>' },
    { type: 'scatter', mode: 'lines+markers', x, y: s.map(m => m.budget_mwh),
      name: 'Budget (PVsyst)', line: { color: C.navy, width: 2, dash: 'dot' },
      marker: { size: 5 }, hovertemplate: '%{y:.0f} MWh<extra>Budget</extra>' },
  ], baseLayout({ yaxis: { title: { text: 'MWh' }, gridcolor: C.line, rangemode: 'tozero' } }));
};

function renderParkYtdTable() {
  const rows = PF.park_ytd || [];
  const el = document.getElementById('tbl-park-ytd');
  el.innerHTML = '<table><thead><tr>' +
    '<th>Park</th><th>Zon</th><th>MWp</th><th>MWh</th><th>vs budget</th>' +
    '<th>kWh/kWp</th><th>Capture €/MWh</th><th>Neg.pris-MWh</th></tr></thead><tbody>' +
    rows.map(r => {
      const vs = r.vs_budget_pct;
      return '<tr><td data-v="' + esc(r.name) + '">' + esc(r.name) + '</td>' +
      '<td data-v="' + r.zone + '"><span class="zone-tag">' + r.zone + '</span></td>' +
      '<td data-v="' + r.capacity_mwp + '">' + fmt(r.capacity_mwp, 1) + '</td>' +
      '<td data-v="' + r.energy_mwh + '">' + fmt(r.energy_mwh) + '</td>' +
      '<td data-v="' + (vs ?? -999) + '" class="' + ((vs ?? 0) >= 0 ? 'pos' : 'neg') + '">' + fmtSign(vs) + '</td>' +
      '<td data-v="' + (r.yield_kwh_kwp ?? -1) + '">' + fmt(r.yield_kwh_kwp) + '</td>' +
      '<td data-v="' + (r.capture ?? -1) + '">' + fmt(r.capture, 1) + '</td>' +
      '<td data-v="' + (r.neg_volume_mwh ?? 0) + '">' + fmt(r.neg_volume_mwh, 1) + '</td></tr>';
    }).join('') + '</tbody></table>';
  makeSortable(el.querySelector('table'));
}

/* ================= 2. Marknaden ================= */
RENDERERS.spotMonthly = function () {
  const traces = MA_ZONES.map(z => {
    const m = MA[z].monthly || [];
    return { type: 'scatter', mode: 'lines', name: z,
      x: m.map(r => r.month), y: m.map(r => r.avg),
      line: { color: C.zones[z], width: z === HOME ? 2.6 : 1.6 },
      hovertemplate: '%{y:.1f} €/MWh<extra>' + z + '</extra>' };
  });
  plot('ch-spot-monthly', traces, baseLayout({
    yaxis: { title: { text: '€/MWh' }, gridcolor: C.line },
  }));
};

RENDERERS.duckCurve = function () { renderDuck(HOME); };
function renderDuck(zone) {
  const duck = (MA[zone] || {}).duck_by_year || {};
  const years = Object.keys(duck).sort();
  const n = years.length;
  const traces = years.map((y, i) => {
    const t = n > 1 ? i / (n - 1) : 1;
    const col = 'rgba(' + Math.round(160 - 150*t) + ',' + Math.round(190 - 100*t) + ',' +
      Math.round(200 - 70*t) + ',' + (0.45 + 0.55*t) + ')';
    return { type: 'scatter', mode: 'lines', name: y,
      x: [...Array(24).keys()], y: duck[y],
      line: { color: i === n-1 ? C.teal : col, width: i === n-1 ? 3 : 1.6 },
      hovertemplate: 'kl %{x}: %{y:.1f} €/MWh<extra>' + y + '</extra>' };
  });
  plot('ch-duck', traces, baseLayout({
    xaxis: { title: { text: 'Timme (lokal tid)' }, gridcolor: C.line, dtick: 3 },
    yaxis: { title: { text: '€/MWh' }, gridcolor: C.line },
    hovermode: 'closest',
  }));
}

RENDERERS.negHours = function () {
  const traces = MA_ZONES.map(z => {
    const ys = (MA[z].yearly || []);
    return { type: 'bar', name: z,
      x: ys.map(r => String(r.year) + (r.complete ? '' : '*')),
      y: ys.map(r => r.neg_hours),
      marker: { color: C.zones[z] },
      hovertemplate: '%{y:.0f} h<extra>' + z + '</extra>' };
  });
  plot('ch-neg-hours', traces, baseLayout({
    barmode: 'group', yaxis: { title: { text: 'timmar' }, gridcolor: C.line },
  }));
};

RENDERERS.spreadDaily = function () {
  const traces = MA_ZONES.map(z => {
    const m = (MA[z].monthly || []).filter(r => r.avg_daily_spread !== null);
    return { type: 'scatter', mode: 'lines', name: z,
      x: m.map(r => r.month), y: m.map(r => r.avg_daily_spread),
      line: { color: C.zones[z], width: z === HOME ? 2.6 : 1.4 },
      hovertemplate: '%{y:.1f} €/MWh<extra>' + z + '</extra>' };
  });
  plot('ch-spread-daily', traces, baseLayout({
    yaxis: { title: { text: '€/MWh per dygn' }, gridcolor: C.line },
  }));
};

RENDERERS.zoneSpreads = function () {
  const sp = (DATA.market_analysis || {}).spreads_monthly || [];
  const pairs = ['SE4-SE3', 'SE3-SE1', 'SE2-SE1'];
  const cols = [C.coral, C.teal, C.faint];
  const traces = pairs.map((p, i) => ({
    type: 'scatter', mode: 'lines', name: p,
    x: sp.map(r => r.month), y: sp.map(r => r[p]),
    line: { color: cols[i], width: 1.8 },
    hovertemplate: '%{y:.1f} €/MWh<extra>' + p + '</extra>',
  }));
  plot('ch-zone-spreads', traces, baseLayout({
    yaxis: { title: { text: '€/MWh' }, gridcolor: C.line },
  }));
};

let heatZone = null, heatYear = null;
RENDERERS.heatmap = function () {
  heatZone = HOME;
  const years = Object.keys((MA[HOME] || {}).month_hour_by_year || {}).sort();
  heatYear = years[years.length - 1];
  seg('seg-heat-zone', MA_ZONES, heatZone, v => { heatZone = v; drawHeat(); refreshHeatYears(); });
  refreshHeatYears();
  drawHeat();
};
function refreshHeatYears() {
  const years = Object.keys((MA[heatZone] || {}).month_hour_by_year || {}).sort();
  if (!years.includes(heatYear)) heatYear = years[years.length - 1];
  seg('seg-heat-year', years, heatYear, v => { heatYear = v; drawHeat(); });
}
function drawHeat() {
  const mh = ((MA[heatZone] || {}).month_hour_by_year || {})[heatYear];
  if (!mh) return;
  plot('ch-heatmap', [{
    type: 'heatmap', z: mh, x: [...Array(24).keys()], y: MONTHS_SV,
    colorscale: [[0, '#1d3a4f'], [0.35, '#7fb6bd'], [0.55, '#f2ede2'], [1, '#d95f4c']],
    colorbar: { thickness: 12, outlinewidth: 0, tickfont: { size: 10 } },
    hovertemplate: '%{y} kl %{x}: %{z:.0f} €/MWh<extra></extra>',
  }], baseLayout({
    xaxis: { title: { text: 'Timme (lokal tid)' }, dtick: 3 },
    yaxis: { autorange: 'reversed' },
    margin: { l: 50, r: 10, t: 10, b: 42 },
  }));
}

/* ================= 3. Capture ================= */
RENDERERS.ratioYearly = function () {
  const cap = DATA.capture || {};
  const traces = Object.keys(cap).map(z => {
    const ys = ((cap[z].sol_syd || {}).yearly || []);
    return { type: 'scatter', mode: 'lines+markers', name: z,
      x: ys.map(r => r.year), y: ys.map(r => r.ratio),
      line: { color: C.zones[z], width: z === HOME ? 2.6 : 1.6 },
      marker: { size: 6 },
      hovertemplate: '%{y:.2f}<extra>' + z + '</extra>' };
  });
  const layout = baseLayout({
    yaxis: { title: { text: 'capture ratio' }, gridcolor: C.line },
    shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 1, y1: 1,
      line: { color: C.faint, width: 1, dash: 'dash' } }],
    annotations: [{ xref: 'paper', x: 0.01, y: 1, yshift: 10, showarrow: false,
      text: 'paritet med baseload', font: { size: 10.5, color: C.faint } }],
  });
  plot('ch-ratio-yearly', traces, layout);
};

RENDERERS.captureMonthly = function () {
  seg('seg-capm-zone', Object.keys(DATA.capture || {}), HOME, drawCaptureMonthly);
  drawCaptureMonthly(HOME);
};
function drawCaptureMonthly(zone) {
  const zd = (DATA.capture || {})[zone] || {};
  const syd = (zd.sol_syd || {}).monthly || [];
  const x = syd.map(r => r.year + '-' + String(r.month).padStart(2, '0'));
  plot('ch-capture-monthly', [
    { type: 'scatter', mode: 'lines', name: 'Baseload',
      x, y: syd.map(r => r.baseload), line: { color: C.faint, width: 1.5 },
      hovertemplate: '%{y:.1f} €/MWh<extra>Baseload</extra>' },
    { type: 'scatter', mode: 'lines', name: 'Capture sol syd',
      x, y: syd.map(r => r.capture), line: { color: C.amber, width: 2.4 },
      fill: 'tonexty', fillcolor: 'rgba(222,155,38,.10)',
      hovertemplate: '%{y:.1f} €/MWh<extra>Capture</extra>' },
  ], baseLayout({ yaxis: { title: { text: '€/MWh' }, gridcolor: C.line } }));
}

RENDERERS.cannibal = function () {
  const zones = Object.keys((DATA.cannibalization || {}).ratio_yearly || {})
    .filter(z => ((DATA.cannibalization.installed || {}).solar || {})[z]);
  seg('seg-cann-zone', zones, zones.includes(HOME) ? HOME : zones[0], drawCannibal);
  drawCannibal(zones.includes(HOME) ? HOME : zones[0]);
};
function drawCannibal(zone) {
  const cn = DATA.cannibalization || {};
  const inst = ((cn.installed || {}).solar || {})[zone] || [];
  const ratio = (cn.ratio_yearly || {})[zone] || [];
  plot('ch-cannibal', [
    { type: 'bar', name: 'Installerad sol (MW)',
      x: inst.map(r => r.year), y: inst.map(r => r.mw),
      marker: { color: 'rgba(222,155,38,.55)' }, yaxis: 'y',
      hovertemplate: '%{y:.0f} MW<extra>Installerad sol</extra>' },
    { type: 'scatter', mode: 'lines+markers', name: 'Capture ratio (sol syd)',
      x: ratio.map(r => r.year), y: ratio.map(r => r.ratio),
      line: { color: C.tealDeep, width: 2.6 }, marker: { size: 7 }, yaxis: 'y2',
      hovertemplate: '%{y:.2f}<extra>Capture ratio</extra>' },
  ], baseLayout({
    margin: { l: 52, r: 64, t: 12, b: 40 },
    yaxis: { title: { text: 'MW installerat' }, gridcolor: C.line, rangemode: 'tozero' },
    yaxis2: { title: { text: 'capture ratio', standoff: 14 }, overlaying: 'y',
      side: 'right', automargin: true,
      gridcolor: 'rgba(0,0,0,0)', zeroline: false },
    legend: { orientation: 'h', y: 1.14, x: 0 },
    hovermode: 'x',
  }));
}

RENDERERS.orientPremium = function () {
  const zones = Object.keys((DATA.orientation || {}).premium_vs_syd || {});
  const def = zones.includes('SE4') ? 'SE4' : zones[0];
  seg('seg-orient-zone', zones, def, drawOrient);
  drawOrient(def);
};
let orientZone = 'SE4';
function drawOrient(zone) {
  orientZone = zone;
  const prem = ((DATA.orientation || {}).premium_vs_syd || {})[zone] || [];
  plot('ch-orient-premium', [
    { type: 'bar', name: 'Öst-väst vs syd', x: prem.map(r => r.year),
      y: prem.map(r => r.ov_pct), marker: { color: C.amber },
      hovertemplate: '%{y:.1f} %<extra>Öst-väst</extra>' },
    { type: 'bar', name: 'Tracker vs syd', x: prem.map(r => r.year),
      y: prem.map(r => r.tracker_pct), marker: { color: C.teal },
      hovertemplate: '%{y:.1f} %<extra>Tracker</extra>' },
  ], baseLayout({
    barmode: 'group',
    yaxis: { title: { text: 'capture-premie, %' }, gridcolor: C.line },
  }));
  drawEurKwp(zone);
}
function drawEurKwp(zone) {
  const ek = ((DATA.orientation || {}).eur_per_kwp || {})[zone] || [];
  plot('ch-orient-eurkwp', [
    { type: 'bar', name: 'Syd', x: ek.map(r => r.year), y: ek.map(r => r.syd),
      marker: { color: C.navy }, hovertemplate: '%{y:.1f} €/kWp<extra>Syd</extra>' },
    { type: 'bar', name: 'Öst-väst', x: ek.map(r => r.year), y: ek.map(r => r.ov),
      marker: { color: C.amber }, hovertemplate: '%{y:.1f} €/kWp<extra>Öst-väst</extra>' },
    { type: 'bar', name: 'Tracker', x: ek.map(r => r.year), y: ek.map(r => r.tracker),
      marker: { color: C.teal }, hovertemplate: '%{y:.1f} €/kWp<extra>Tracker</extra>' },
  ], baseLayout({
    barmode: 'group',
    yaxis: { title: { text: '€ per kWp och år' }, gridcolor: C.line },
  }));
}
RENDERERS.orientEurKwp = function () { /* renderas av drawOrient */ };

RENDERERS.profileShapes = function () {
  const shapes = ((DATA.orientation || {}).profile_shapes || {})['6'] || {};
  const labels = (DATA.orientation || {}).labels || {};
  const cols = { sol_syd: C.navy, sol_ov: C.amber, sol_tracker: C.teal };
  const traces = Object.keys(shapes).map(k => ({
    type: 'scatter', mode: 'lines', name: labels[k] || k,
    x: [...Array(24).keys()], y: shapes[k],
    line: { color: cols[k] || C.faint, width: 2.2 },
    hovertemplate: '%{y:.2f}<extra>' + (labels[k] || k) + '</extra>',
  }));
  // Junipris (senaste kompletta år, hemmazon) på höger axel
  const y = lastCompleteYear(HOME);
  const mh = ((MA[HOME] || {}).month_hour_by_year || {})[String(y)];
  if (mh && mh[5]) {
    traces.push({
      type: 'scatter', mode: 'lines', name: 'Junipris ' + HOME + ' ' + y,
      x: [...Array(24).keys()], y: mh[5], yaxis: 'y2',
      line: { color: C.coral, width: 2, dash: 'dot' },
      hovertemplate: '%{y:.1f} €/MWh<extra>Junipris</extra>',
    });
  }
  plot('ch-profile-shapes', traces, baseLayout({
    margin: { l: 52, r: 64, t: 12, b: 40 },
    xaxis: { title: { text: 'Timme (lokal tid)' }, gridcolor: C.line, dtick: 3 },
    yaxis: { title: { text: 'produktion (normaliserad)' }, gridcolor: C.line },
    yaxis2: { title: { text: '€/MWh', standoff: 14 }, overlaying: 'y',
      side: 'right', automargin: true,
      gridcolor: 'rgba(0,0,0,0)', zeroline: false },
    hovermode: 'x',
  }));
};

function renderValidation() {
  const val = DATA.validation || {};
  const el = document.getElementById('tbl-validation');
  const zones = Object.keys(val);
  if (!zones.length) { el.innerHTML = '<p style="color:var(--muted)">Ingen valideringsdata.</p>'; return; }
  let html = '';
  zones.forEach(z => {
    const v = val[z];
    html += '<h4 style="margin:10px 0 4px">' + z + '</h4>' +
      '<table><thead><tr><th>År</th><th>PVsyst-snitt €/MWh</th><th>ENTSO-E faktisk €/MWh</th><th>Avvikelse</th></tr></thead><tbody>' +
      v.years.map((y, i) =>
        '<tr><td>' + y + '</td><td>' + fmt(v.pvsyst_avg[i], 1) + '</td>' +
        '<td>' + fmt(v.entsoe[i], 1) + '</td>' +
        '<td class="' + (Math.abs(v.deviation_pct[i]) <= 5 ? 'pos' : 'neg') + '">' +
        fmtSign(v.deviation_pct[i]) + '</td></tr>').join('') +
      '</tbody></table>';
  });
  el.innerHTML = html;
}

/* ================= 4. Parkerna ================= */
function latestClosedYM() {
  const lc = PF.latest_closed;
  return lc ? lc.month : null;
}

function renderLeague() {
  const ym = latestClosedYM();
  const el = document.getElementById('tbl-league');
  if (!ym) { el.innerHTML = '<p>Ingen stängd månad med data.</p>'; return; }
  const [yy, mm] = ym.split('-').map(Number);
  document.getElementById('league-title').textContent =
    'League table — ' + MONTHS_SV[mm-1] + ' ' + yy;
  const rows = PARK_KEYS.map(k => {
    const p = PARKS[k];
    const m = (p.months || []).find(x => x.year === yy && x.month === mm) || {};
    return { k, name: p.name, zone: p.zone, ...m };
  });
  el.innerHTML = '<table><thead><tr>' +
    '<th>Park</th><th>Zon</th><th>MWh</th><th>vs budget</th><th>kWh/kWp</th>' +
    '<th>PR %</th><th>Tillg. %</th><th>Capture €/MWh</th><th>vs baseload</th><th>Neg.pris-MWh</th>' +
    '</tr></thead><tbody>' +
    rows.map(r => {
      const vs = r.vs_budget_pct;
      return '<tr>' +
      '<td data-v="' + esc(r.name) + '"><span style="display:inline-block;width:9px;height:9px;border-radius:3px;background:' + parkColor[r.k] + ';margin-right:7px"></span>' + esc(r.name) + '</td>' +
      '<td data-v="' + r.zone + '"><span class="zone-tag">' + r.zone + '</span></td>' +
      '<td data-v="' + (r.energy_mwh ?? -1) + '">' + fmt(r.energy_mwh) + '</td>' +
      '<td data-v="' + (vs ?? -999) + '" class="' + ((vs ?? 0) >= 0 ? 'pos' : 'neg') + '">' + fmtSign(vs) + '</td>' +
      '<td data-v="' + (r.yield_kwh_kwp ?? -1) + '">' + fmt(r.yield_kwh_kwp, 1) + '</td>' +
      '<td data-v="' + (r.pr_pct ?? -1) + '">' + fmt(r.pr_pct, 1) + '</td>' +
      '<td data-v="' + (r.availability_pct ?? -1) + '">' + fmt(r.availability_pct, 1) + '</td>' +
      '<td data-v="' + (r.capture_eur_mwh ?? -1) + '">' + fmt(r.capture_eur_mwh, 1) + '</td>' +
      '<td data-v="' + (r.capture_premium_pct ?? -999) + '" class="' + ((r.capture_premium_pct ?? 0) >= 0 ? 'pos' : 'neg') + '">' + fmtSign(r.capture_premium_pct) + '</td>' +
      '<td data-v="' + (r.neg_price_volume_mwh ?? 0) + '">' + fmt(r.neg_price_volume_mwh, 1) + '</td>' +
      '</tr>';
    }).join('') + '</tbody></table>';
  makeSortable(el.querySelector('table'));

  const tk = document.getElementById('parker-takeaway');
  const best = rows.filter(r => r.vs_budget_pct != null)
    .sort((a, b) => b.vs_budget_pct - a.vs_budget_pct);
  if (best.length) {
    tk.textContent = MONTHS_SV[mm-1] + ' ' + yy + ': bäst mot budget var ' +
      best[0].name + ' (' + fmtSign(best[0].vs_budget_pct) + '), svagast ' +
      best[best.length-1].name + ' (' + fmtSign(best[best.length-1].vs_budget_pct) + ').';
  }
}

RENDERERS.specificYield = function () {
  const sy = (DATA.operations || {}).specific_yield || {};
  const traces = PARK_KEYS.filter(k => sy[k]).map(k => {
    const rows = sy[k];
    return { type: 'scatter', mode: 'lines', name: PARKS[k].name,
      x: rows.map(r => r.year + '-' + String(r.month).padStart(2, '0')),
      y: rows.map(r => r.yield_kwh_kwp),
      line: { color: parkColor[k], width: 1.7 },
      hovertemplate: '%{y:.0f} kWh/kWp<extra>' + PARKS[k].name + '</extra>' };
  });
  plot('ch-specific-yield', traces, baseLayout({
    yaxis: { title: { text: 'kWh/kWp' }, gridcolor: C.line },
    legend: { orientation: 'h', y: 1.18, x: 0, font: { size: 10.5 } },
  }));
};

RENDERERS.trackerGain = function () {
  const tg = (DATA.operations || {}).tracker_gain || [];
  const x = tg.map(r => r.year + '-' + String(r.month).padStart(2, '0'));
  plot('ch-tracker-gain', [
    { type: 'bar', name: 'Tracker-gain %', x, y: tg.map(r => r.gain_pct),
      marker: { color: tg.map(r => r.gain_pct >= 0 ? C.teal : C.coral) },
      hovertemplate: '%{y:.1f} %<extra>Hova vs fast</extra>' },
  ], baseLayout({
    yaxis: { title: { text: 'merproduktion, %' }, gridcolor: C.line },
    showlegend: false,
  }));
};

RENDERERS.negExposure = function () {
  const months = new Set();
  PARK_KEYS.forEach(k => (PARKS[k].months || []).forEach(m => {
    if ((m.neg_price_volume_mwh || 0) > 0) months.add(m.year + '-' + String(m.month).padStart(2, '0'));
  }));
  const x = [...months].sort();
  const traces = PARK_KEYS.map(k => {
    const lookup = {};
    (PARKS[k].months || []).forEach(m => {
      lookup[m.year + '-' + String(m.month).padStart(2, '0')] = m.neg_price_volume_mwh || 0;
    });
    return { type: 'bar', name: PARKS[k].name, x, y: x.map(m => lookup[m] ?? 0),
      marker: { color: parkColor[k] },
      hovertemplate: '%{y:.1f} MWh<extra>' + PARKS[k].name + '</extra>' };
  });
  plot('ch-neg-exposure', traces, baseLayout({
    barmode: 'stack', yaxis: { title: { text: 'MWh i negativa timmar' }, gridcolor: C.line },
    legend: { orientation: 'h', y: 1.18, x: 0, font: { size: 10.5 } },
  }));
};

/* ---------- Parkdetalj ---------- */
function initParkDetail() {
  seg('seg-park', PARK_KEYS.map(k => ({ value: k, label: PARKS[k].name })),
    PARK_KEYS[0], renderParkDetail);
  renderParkDetail(PARK_KEYS[0]);
}

function renderParkDetail(key) {
  const p = PARKS[key];
  const el = document.getElementById('park-detail');
  const f = p.facts || {};
  const ppa = p.ppa;
  el.innerHTML =
    '<div class="facts">' +
      '<div><b>' + esc(p.name) + '</b>' + esc(f.location || '') + '</div>' +
      '<div><b>' + fmt(p.capacity_mwp, 2) + ' MWp</b>' + esc(p.zone) + ' · ' + esc(f.profile_type === 'tracker' ? 'tracker' : 'fast montage, syd') + '</div>' +
      '<div><b>' + fmt(f.num_modules) + ' moduler</b>' + esc(f.module_type || '') + '</div>' +
      '<div><b>' + fmt(f.num_inverters) + ' växelriktare</b>' + esc(f.inverter_model || '') + '</div>' +
      '<div><b>' + (f.tilt_angle != null ? f.tilt_angle + '° lutning' : '–') + '</b>azimut ' + esc(f.azimuth ?? '–') + '</div>' +
      '<div><b>' + (ppa ? fmt(ppa.price_sek_mwh) + ' SEK/MWh' : 'Ingen PPA') + '</b>' +
        (ppa ? 'PPA, ' + fmt(ppa.share_pct) + ' % av volymen' : '100 % spot') + '</div>' +
      '<div><b>Data t.o.m.</b>' + esc((p.last_data_ts || '').slice(0, 10)) + '</div>' +
    '</div>' +
    '<div class="grid">' +
      '<div class="card"><div class="card-head"><h3>Produktion mot budget</h3></div><div class="chart" id="pd-prod"></div></div>' +
      '<div class="card"><div class="card-head"><h3>PR och tillgänglighet</h3></div><div class="chart" id="pd-pr"></div></div>' +
      '<div class="card"><div class="card-head"><h3>Realiserad capture mot baseload</h3></div><div class="chart" id="pd-capture"></div></div>' +
      '<div class="card"><div class="card-head"><h3>Förlustvattenfall — senaste stängda månad</h3></div><div class="chart" id="pd-waterfall"></div></div>' +
      '<div class="card span2"><div class="card-head"><h3>Daglig produktion — senaste månaderna</h3></div><div class="chart" id="pd-daily"></div></div>' +
    '</div>';

  const months = p.months || [];
  const x = months.map(m => mLabel(m.year + '-' + String(m.month).padStart(2, '0')));

  plot('pd-prod', [
    { type: 'bar', name: 'Produktion', x, y: months.map(m => m.energy_mwh),
      marker: { color: months.map(m => m.is_partial ? 'rgba(14,124,134,.35)' : parkColor[key]) },
      hovertemplate: '%{y:.0f} MWh<extra>Produktion</extra>' },
    { type: 'scatter', mode: 'lines+markers', name: 'Budget', x,
      y: months.map(m => m.budget_mwh), line: { color: C.navy, width: 2, dash: 'dot' },
      marker: { size: 4 }, hovertemplate: '%{y:.0f} MWh<extra>Budget</extra>' },
  ], baseLayout({ yaxis: { title: { text: 'MWh' }, gridcolor: C.line, rangemode: 'tozero' } }));

  plot('pd-pr', [
    { type: 'scatter', mode: 'lines+markers', name: 'PR %', x,
      y: months.map(m => m.pr_pct), line: { color: C.teal, width: 2.2 },
      hovertemplate: '%{y:.1f} %<extra>PR</extra>' },
    { type: 'scatter', mode: 'lines+markers', name: 'Budget-PR %', x,
      y: months.map(m => m.budget_pr_pct), line: { color: C.faint, width: 1.4, dash: 'dot' },
      hovertemplate: '%{y:.1f} %<extra>Budget-PR</extra>' },
    { type: 'scatter', mode: 'lines+markers', name: 'Tillgänglighet %', x,
      y: months.map(m => m.availability_pct), line: { color: C.amber, width: 1.8 },
      hovertemplate: '%{y:.1f} %<extra>Tillgänglighet</extra>' },
  ], baseLayout({ yaxis: { title: { text: '%' }, gridcolor: C.line } }));

  const traces = [
    { type: 'scatter', mode: 'lines', name: 'Baseload (zon)', x,
      y: months.map(m => m.baseload_eur_mwh), line: { color: C.faint, width: 1.5 },
      hovertemplate: '%{y:.1f} €/MWh<extra>Baseload</extra>' },
    { type: 'scatter', mode: 'lines+markers', name: 'Realiserad capture', x,
      y: months.map(m => m.capture_eur_mwh), line: { color: parkColor[key], width: 2.4 },
      hovertemplate: '%{y:.1f} €/MWh<extra>Capture</extra>' },
  ];
  if (ppa) {
    traces.push({ type: 'scatter', mode: 'lines', name: 'PPA-pris (EUR-konv.)', x,
      y: months.map(m => m.ppa_price_eur_mwh_avg),
      line: { color: C.navy, width: 1.6, dash: 'dash' },
      hovertemplate: '%{y:.1f} €/MWh<extra>PPA</extra>' });
  }
  plot('pd-capture', traces, baseLayout({
    yaxis: { title: { text: '€/MWh' }, gridcolor: C.line },
  }));

  // Waterfall för senaste stängda månad med förlustdata
  const closed = months.filter(m => !m.is_partial && m.losses && m.losses.budget_mwh);
  const wfm = closed[closed.length - 1];
  if (wfm) {
    const L = wfm.losses;
    plot('pd-waterfall', [{
      type: 'waterfall', orientation: 'v',
      measure: ['absolute', 'relative', 'relative', 'relative', 'total'],
      x: ['Budget', 'Instrålning', 'Tillgänglighet', 'Övrigt/curtailment', 'Faktisk'],
      y: [L.budget_mwh, -(L.irradiance_shortfall_mwh || 0), -(L.availability_mwh || 0),
          -(L.curtailment_mwh || 0), null],
      text: [fmt(L.budget_mwh), fmt(-(L.irradiance_shortfall_mwh || 0)),
             fmt(-(L.availability_mwh || 0)), fmt(-(L.curtailment_mwh || 0)), fmt(L.actual_mwh)],
      textposition: 'outside',
      connector: { line: { color: C.line } },
      increasing: { marker: { color: C.green } },
      decreasing: { marker: { color: C.coral } },
      totals: { marker: { color: C.navy } },
      hoverinfo: 'skip',
    }], baseLayout({
      yaxis: { title: { text: 'MWh' }, gridcolor: C.line },
      showlegend: false,
      annotations: [{ xref: 'paper', yref: 'paper', x: 0.99, y: 1.08, showarrow: false,
        text: mLabel(wfm.year + '-' + String(wfm.month).padStart(2, '0')),
        font: { size: 12, color: C.muted } }],
    }));
  } else {
    document.getElementById('pd-waterfall').innerHTML =
      '<p style="color:var(--muted);padding:20px">Ingen förlustdata för stängd månad.</p>';
  }

  // Daglig produktion (senaste månaderna)
  const dbm = p.daily_by_month || {};
  const dKeys = Object.keys(dbm).sort();
  const dx = [], dy = [], de = [];
  dKeys.forEach(mk => (dbm[mk] || []).forEach(d => {
    dx.push(d.date); dy.push(d.energy_mwh); de.push(d.expected_mwh);
  }));
  plot('pd-daily', [
    { type: 'bar', name: 'Produktion', x: dx, y: dy,
      marker: { color: parkColor[key] }, hovertemplate: '%{y:.1f} MWh<extra>%{x}</extra>' },
    { type: 'scatter', mode: 'lines', name: 'Förväntat (POA × PR)', x: dx, y: de,
      line: { color: C.navy, width: 1.6, dash: 'dot' },
      hovertemplate: '%{y:.1f} MWh<extra>Förväntat</extra>' },
  ], baseLayout({ yaxis: { title: { text: 'MWh/dag' }, gridcolor: C.line, rangemode: 'tozero' } }));
}

/* ================= 5. Risk & intäkt ================= */
RENDERERS.forwardCurve = function () {
  const fwd = DATA.forward;
  const el = document.getElementById('ch-forward-curve');
  if (!fwd) { el.innerHTML = '<p style="color:var(--muted);padding:20px">Ingen forwarddata.</p>'; return; }
  document.getElementById('fwd-note').textContent =
    'SYS + EPAD per kontrakt. Settlement ' + fwd.settlement_date + ' (Nasdaq, handeln flyttad till Euronext).';
  const labels = (fwd.contracts || []).map(c => c.label);
  const traces = Object.keys(fwd.zone_fwd || {}).map(z => ({
    type: 'scatter', mode: 'lines+markers', name: z,
    x: labels, y: labels.map(l => (fwd.zone_fwd[z] || {})[l] ?? null),
    line: { color: C.zones[z], width: z === HOME ? 2.6 : 1.6 }, marker: { size: 5 },
    hovertemplate: '%{y:.1f} €/MWh<extra>' + z + '</extra>',
  }));
  traces.push({
    type: 'scatter', mode: 'lines', name: 'SYS',
    x: labels, y: labels.map(l => (fwd.sys || {})[l] ?? null),
    line: { color: C.faint, width: 1.4, dash: 'dash' },
    hovertemplate: '%{y:.1f} €/MWh<extra>SYS</extra>',
  });
  plot('ch-forward-curve', traces, baseLayout({
    yaxis: { title: { text: '€/MWh' }, gridcolor: C.line },
    xaxis: { tickangle: -38, gridcolor: C.line },
  }));
};

RENDERERS.forwardAccuracy = function () {
  const fwd = DATA.forward || {};
  const zones = Object.keys(fwd.spot_realized || {});
  if (!zones.length) {
    document.getElementById('ch-forward-accuracy').innerHTML =
      '<p style="color:var(--muted);padding:20px">Inga levererade kontrakt med data.</p>';
    return;
  }
  const def = zones.includes(HOME) ? HOME : zones[0];
  seg('seg-fwdacc-zone', zones, def, drawFwdAcc);
  drawFwdAcc(def);
};
function drawFwdAcc(zone) {
  const fwd = DATA.forward || {};
  const sr = (fwd.spot_realized || {})[zone] || {};
  const labels = (fwd.expired_contracts || []).map(c => c.label).filter(l => sr[l]);
  plot('ch-forward-accuracy', [
    { type: 'bar', name: 'Forward (sista fix)', x: labels,
      y: labels.map(l => sr[l].forward), marker: { color: C.navy },
      hovertemplate: '%{y:.1f} €/MWh<extra>Forward</extra>' },
    { type: 'bar', name: 'Realiserat spotsnitt', x: labels,
      y: labels.map(l => sr[l].spot_avg), marker: { color: C.teal },
      hovertemplate: '%{y:.1f} €/MWh<extra>Spot</extra>' },
  ], baseLayout({
    barmode: 'group', yaxis: { title: { text: '€/MWh' }, gridcolor: C.line },
  }));
}

RENDERERS.ppaChart = function () {
  const ppa = DATA.ppa || {};
  const rows = (ppa.rows || []).filter(r => r.has_ppa);
  document.getElementById('ppa-note').textContent =
    'Kontrakterat PPA-pris (EUR-konverterat, tidsviktat ' + (rows[0]?.capture_month ?? '') +
    ') mot realiserad spot-capture samma månad och forwardkurvan (' + (ppa.fwd_label ?? '–') + ').';
  plot('ch-ppa', [
    { type: 'bar', name: 'PPA-pris €/MWh', x: rows.map(r => r.name),
      y: rows.map(r => r.ppa_price_eur_mwh), marker: { color: C.navy },
      hovertemplate: '%{y:.1f} €/MWh<extra>PPA</extra>' },
    { type: 'bar', name: 'Spot-capture (senaste stängda mån)', x: rows.map(r => r.name),
      y: rows.map(r => r.capture_spot_eur_mwh), marker: { color: C.amber },
      hovertemplate: '%{y:.1f} €/MWh<extra>Capture</extra>' },
    { type: 'bar', name: 'Forward ' + (ppa.fwd_label ?? ''), x: rows.map(r => r.name),
      y: rows.map(r => r.fwd_eur_mwh), marker: { color: C.teal },
      hovertemplate: '%{y:.1f} €/MWh<extra>Forward</extra>' },
  ], baseLayout({
    barmode: 'group', yaxis: { title: { text: '€/MWh' }, gridcolor: C.line },
  }));
  renderPpaTable();
};

function renderPpaTable() {
  const ppa = DATA.ppa || {};
  const el = document.getElementById('tbl-ppa');
  el.innerHTML = '<table><thead><tr>' +
    '<th>Park</th><th>PPA SEK/MWh</th><th>Andel %</th><th>PPA €/MWh</th>' +
    '<th>Spot-capture €/MWh</th><th>Forward ' + esc(ppa.fwd_label ?? '') + '</th>' +
    '<th>PPA-uplift ' + esc(ppa.ytd_year ?? '') + ' (€)</th></tr></thead><tbody>' +
    (ppa.rows || []).map(r => {
      const up = r.uplift_ytd_eur;
      return '<tr><td data-v="' + esc(r.name) + '">' + esc(r.name) +
        '<span class="zone-tag">' + esc(r.zone) + '</span></td>' +
        '<td data-v="' + (r.ppa_price_sek_mwh ?? -1) + '">' + fmt(r.ppa_price_sek_mwh) + '</td>' +
        '<td data-v="' + (r.ppa_share_pct ?? 0) + '">' + fmt(r.ppa_share_pct) + '</td>' +
        '<td data-v="' + (r.ppa_price_eur_mwh ?? -1) + '">' + fmt(r.ppa_price_eur_mwh, 1) + '</td>' +
        '<td data-v="' + (r.capture_spot_eur_mwh ?? -1) + '">' + fmt(r.capture_spot_eur_mwh, 1) + '</td>' +
        '<td data-v="' + (r.fwd_eur_mwh ?? -1) + '">' + fmt(r.fwd_eur_mwh, 1) + '</td>' +
        '<td data-v="' + (up ?? -999999) + '" class="' + ((up ?? 0) >= 0 ? 'pos' : 'neg') + '">' +
        (up == null ? '–' : (up >= 0 ? '+' : '−') + fmt(Math.abs(up))) + '</td></tr>';
    }).join('') + '</tbody></table>';
  makeSortable(el.querySelector('table'));
}

RENDERERS.imbalance = function () {
  const zones = (DATA.imbalance || {}).zones || {};
  const traces = Object.keys(zones).map(z => {
    const m = zones[z].monthly || [];
    return { type: 'scatter', mode: 'lines', name: z,
      x: m.map(r => r.month), y: m.map(r => r.mean_abs_diff),
      line: { color: C.zones[z], width: z === HOME ? 2.6 : 1.4 },
      hovertemplate: '%{y:.1f} €/MWh<extra>' + z + '</extra>' };
  });
  const home = zones[HOME];
  if (home) {
    const m = home.monthly || [];
    traces.push({ type: 'scatter', mode: 'lines', name: 'P90 ' + HOME,
      x: m.map(r => r.month), y: m.map(r => r.p90_abs_diff),
      line: { color: C.coral, width: 1.4, dash: 'dot' },
      hovertemplate: '%{y:.1f} €/MWh<extra>P90</extra>' });
  }
  plot('ch-imbalance', traces, baseLayout({
    yaxis: { title: { text: '€/MWh avvikelse mot spot' }, gridcolor: C.line },
  }));
};

/* ================= 6. Datakvalitet ================= */
function renderQuality() {
  const rows = DATA.data_quality || [];
  const el = document.getElementById('tbl-quality');
  const ageBadge = (ts) => {
    if (!ts) return '<span class="badge bad">saknas</span>';
    const days = (Date.now() - new Date(ts).getTime()) / 864e5;
    const cls = days <= 9 ? 'ok' : days <= 21 ? 'warn' : 'bad';
    return '<span class="badge ' + cls + '">' + ts.slice(0, 10) + '</span>';
  };
  const pctBadge = (v, okLim, warnLim) => {
    if (v == null) return '<span class="badge bad">–</span>';
    const cls = v >= okLim ? 'ok' : v >= warnLim ? 'warn' : 'bad';
    return '<span class="badge ' + cls + '">' + fmt(v, 1) + ' %</span>';
  };
  el.innerHTML = '<table><thead><tr>' +
    '<th>Park</th><th>Zon</th><th>Senaste data</th><th>Mätartäckning (energi)</th>' +
    '<th>Stuck-dagar</th><th>Availability-signal</th><th>Väderstation</th></tr></thead><tbody>' +
    rows.map(r => {
      const name = (PARKS[r.park] || {}).name || r.park;
      const stuck = r.stuck_days == null ? '–'
        : '<span class="badge ' + (r.stuck_days === 0 ? 'ok' : r.stuck_days <= 3 ? 'warn' : 'bad') + '">' + r.stuck_days + '</span>';
      return '<tr><td data-v="' + esc(name) + '">' + esc(name) + '</td>' +
        '<td data-v="' + r.zone + '"><span class="zone-tag">' + r.zone + '</span></td>' +
        '<td data-v="' + (r.last_ts ?? '') + '">' + ageBadge(r.last_ts) + '</td>' +
        '<td data-v="' + (r.meter_share_pct ?? -1) + '">' + pctBadge(r.meter_share_pct, 95, 70) + '</td>' +
        '<td data-v="' + (r.stuck_days ?? 999) + '">' + stuck + '</td>' +
        '<td data-v="' + (r.availability_coverage_pct ?? -1) + '">' + pctBadge(r.availability_coverage_pct, 90, 50) + '</td>' +
        '<td data-v="' + (r.has_weather ? 1 : 0) + '">' + (r.has_weather ? '<span class="badge ok">ja</span>' : '<span class="badge warn">nej</span>') + '</td></tr>';
    }).join('') + '</tbody></table>' +
    '<p style="color:var(--muted);font-size:12px;margin-top:8px">Fönster: senaste ' +
    (rows[0]?.window_days ?? 90) + ' dagarna. Mätartäckning &lt; 100 % betyder att energi ' +
    'räknas via inverter-fallback (effective power) — siffrorna är fortfarande korrekta, ' +
    'men grid-mätaren bör felsökas.</p>';
  makeSortable(el.querySelector('table'));
}

/* ================= Nav-highlight ================= */
function navInit() {
  const links = document.querySelectorAll('#topnav a');
  const obs = new IntersectionObserver((es) => {
    es.forEach(e => {
      if (e.isIntersecting) {
        links.forEach(l => l.classList.toggle('active', l.dataset.sec === e.target.id));
      }
    });
  }, { rootMargin: '-30% 0px -60% 0px' });
  document.querySelectorAll('main section').forEach(s => obs.observe(s));
}

/* ================= Init ================= */
function safe(name, fn) {
  try { fn(); } catch (err) { console.error('init:' + name, err); }
}
safe('header', renderHeader);
safe('callouts', renderCallouts);
safe('kpis', renderKpis);
safe('parkYtd', renderParkYtdTable);
safe('league', renderLeague);
safe('validation', renderValidation);
safe('quality', renderQuality);
safe('parkDetail', initParkDetail);
safe('duckSeg', () => seg('seg-duck-zone', MA_ZONES, HOME, renderDuck));
safe('lazy', lazyInit);
safe('nav', navInit);
"""
