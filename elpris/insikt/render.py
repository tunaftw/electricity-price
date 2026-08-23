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


def _render_section_marknad(data: Dict[str, Any]) -> str:
    """Sektion 2: Marknad & intäkt — intäkt/PPA, obalans, kannibalisering,
    forward-läge. Innehållet fylls lazy via ``data-render``-renderers."""
    return """
<section id="marknad">
  <div class="sec-head">
    <div class="kicker">Insikt · Marknad</div>
    <h1>Marknad &amp; intäkt</h1>
  </div>

  <div class="card block-card" id="blk-intakt" data-render="intakt">
    <div class="card-head"><h3>Intäkt &amp; PPA</h3>
      <p>Realiserat capture (Bazefield-volym × spot) mot baseload och PPA —
         flottnivå, 13 månader. PPA-boken jämförs mot senaste forward.</p></div>
    <div class="callouts blk-callouts" id="intakt-insights"></div>
    <div class="blk-chart" id="intakt-chart"></div>
    <h4 class="blk-sub">PPA-boken</h4>
    <div class="tbl-wrap" id="intakt-ppa-tbl"></div>
  </div>

  <div class="card block-card" id="blk-obalans" data-render="obalans">
    <div class="card-head"><h3>Obalanskostnad</h3>
      <p>Simulerad avräkning mot eSett:s 15-min-priser, senaste 12 månaderna.
         Spannet går från naiv D-1-persistens (a) till budgetform utan
         väderinformation (b).</p></div>
    <div class="callouts blk-callouts" id="obalans-insights"></div>
    <div class="obalans-grid">
      <div class="tbl-wrap" id="obalans-tbl"></div>
      <div class="blk-chart" id="obalans-chart"></div>
    </div>
    <p class="blk-foot" id="obalans-method"></p>
  </div>

  <div class="card block-card" id="blk-kanni" data-render="kanni">
    <div class="card-head"><h3>Kannibalisering</h3>
      <p>Capture ratio (sydvänd TMY-profil) mot installerad solkapacitet
         per elområde och år — OLS-lutning, 95 %-KI och framskrivning.</p></div>
    <div class="callouts blk-callouts" id="kanni-insights"></div>
    <div class="kanni-grid" id="kanni-charts"></div>
    <p class="blk-foot" id="kanni-foot"></p>
    <details class="blk-details" id="kanni-assumptions"><summary>Antaganden</summary>
      <ul id="kanni-assumptions-list"></ul></details>
  </div>

  <div class="card block-card" id="blk-forward" data-render="forward">
    <div class="card-head"><h3>Forward-läge</h3>
      <p>Hur terminspriset konvergerade mot utfallet — SYS, zone-implied
         (SYS + EPAD) och realiserad spot per kontrakt.</p></div>
    <div class="callouts blk-callouts" id="fwd-insights"></div>
    <div class="fwd-controls">
      <select id="fwd-contract" class="sel"></select>
      <div class="zone-btns" id="fwd-zones"></div>
    </div>
    <div class="blk-chart" id="fwd-conv"></div>
    <p class="note-warn" id="fwd-clean-note" hidden></p>
    <h4 class="blk-sub">Lookback — vad sa marknaden före leverans?</h4>
    <p class="chart-note">Zone-implied (SYS + EPAD) närmast T−X månader före
      leveransstart (±7 dagar). Fel = slutfix − realiserat; färgas bara för
      levererade kontrakt (grön &lt; 5, gul 5–15, röd &gt; 15 €/MWh).</p>
    <div class="tbl-wrap" id="fwd-lookback"></div>
    <p class="note-warn" id="fwd-health" hidden></p>
  </div>
</section>
"""


def _render_section_bess(data: Dict[str, Any]) -> str:
    """Sektion 3: Batteri & investering — stacking, känslighet, kalkyl, BTM."""
    return """
<section id="bess">
  <div class="sec-head">
    <div class="kicker">Insikt · Investering</div>
    <h1>Batteri &amp; investering</h1>
  </div>
  <div class="callouts" id="bess-insights"></div>

  <div class="card block-card" id="blk-stack" data-render="bessStack">
    <div class="card-head"><h3>Revenue stacking — arbitrage + stödtjänster i samma optimering</h3>
      <p>1 MW-batteri, senaste hela året per zon × duration. Uplift = stackad
         intäkt över bästa enskilda strategi. Mix = reservtimmar per produkt.</p></div>
    <div class="tbl-wrap" id="stack-tbl"></div>
  </div>

  <div class="card block-card" id="blk-acc" data-render="bessAcc">
    <div class="card-head"><h3>Känslighet för budacceptans</h3>
      <p>Stackad årsintäkt när bara 100 / 70 / 40 % av budad reservkapacitet
         antas bli antagen — DP:n körs om och flyttar timmar mot arbitrage.</p></div>
    <div class="blk-chart" id="acc-chart"></div>
  </div>

  <div class="card block-card" id="blk-kalkyl" data-render="bessKalkyl">
    <div class="card-head"><h3>Investeringskalkyl</h3>
      <p>IRR/NPV/payback per zon × duration på huvudacceptansnivån.
         <b>Break-even</b> är beslutssiffran: hur stor andel av årets intäkt
         som räcker för att nå avkastningskravet — IRR-nivåerna är tak.</p></div>
    <div class="callouts blk-callouts" id="kalkyl-insights"></div>
    <div class="tbl-wrap" id="kalkyl-tbl"></div>
    <p class="blk-foot" id="kalkyl-params"></p>
  </div>

  <div class="card block-card" id="blk-btm" data-render="bessBtm">
    <div class="card-head"><h3>Behind-the-meter per park — verklig profil vs TMY</h3>
      <p>Sol + batteri (0,25 MW per MWp, C-rate 1) på parkens faktiska
         15-min-produktion och zonens verkliga spot, senaste 12 hela
         månaderna. TMY-kolumnen: samma dagar och batteri, sol_syd-profil
         skalad till samma energi — skillnaden isolerar profilformen.</p></div>
    <div class="tbl-wrap" id="btm-tbl"></div>
  </div>
</section>
"""


#: (id, titel, render-funktion) — nav + <main> genereras härifrån.
SECTIONS: List[Tuple[str, str, Callable[[Dict[str, Any]], str]]] = [
    ("parker", "Parkerna", _render_section_parker),
    ("marknad", "Marknad & intäkt", _render_section_marknad),
    ("bess", "Batteri & investering", _render_section_bess),
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
<title>Insikt</title>
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

/* ---------- Blockkort (Marknad & BESS) ---------- */
.block-card { margin: 0 0 26px; padding-bottom: 16px; }
.blk-callouts { margin: 10px 0 14px; }
.blk-callouts .callout { font-size: 14.5px; padding: 9px 14px; }
.blk-chart { width: 100%; min-height: 300px; }
.blk-sub { margin: 18px 0 4px; font-size: 14px; font-weight: 700; }
.blk-foot { color: var(--faint); font-size: 11.5px; margin: 10px 0 0;
  line-height: 1.5; }
.blk-details { margin-top: 10px; font-size: 12px; color: var(--muted); }
.blk-details summary { cursor: pointer; font-weight: 600;
  color: var(--teal-deep); }
.blk-details ul { margin: 6px 0 0; padding-left: 18px; }
.blk-details li { margin-bottom: 4px; }
.note-warn {
  margin: 10px 0 0; padding: 8px 12px; border-radius: 8px;
  background: #fdf3e7; border: 1px solid #f0d9b8; color: #8a5a14;
  font-size: 12.5px;
}
tfoot td { font-weight: 700; border-top: 2px solid var(--ink); }
tbody tr.plain { cursor: default; }
tbody tr.plain:hover { background: transparent; }

/* Obalans: tabell + graf sida vid sida */
.obalans-grid { display: grid; grid-template-columns: 3fr 2fr; gap: 18px;
  align-items: start; }
.obalans-grid .blk-chart { min-height: 260px; }

/* Kannibalisering: en graf per signifikant zon */
.kanni-grid { display: grid; grid-template-columns: 1fr; gap: 14px; }
.kanni-grid.two { grid-template-columns: 1fr 1fr; }
.kanni-chart { width: 100%; min-height: 320px; }
.kanni-chart-title { font-size: 13px; font-weight: 700; margin: 2px 0 0; }

/* Forward-kontroller */
.fwd-controls { display: flex; gap: 10px; align-items: center;
  flex-wrap: wrap; margin: 4px 0 8px; }
.sel {
  font: 600 13px 'Inter', sans-serif; color: var(--ink);
  padding: 7px 10px; border-radius: 8px; border: 1px solid var(--line);
  background: var(--bg);
}
.zone-btns { display: flex; gap: 4px; }
.zone-btns button {
  font: 600 12px 'Inter', sans-serif; padding: 6px 11px;
  border-radius: 7px; border: 1px solid var(--line); background: var(--bg);
  color: var(--muted); cursor: pointer;
}
.zone-btns button:hover { background: var(--teal-soft);
  color: var(--teal-deep); }
.zone-btns button.on { background: var(--navy); color: #fff;
  border-color: var(--navy); }

/* Lookback-felfärgning */
td.err-ok { color: var(--green); font-weight: 700; }
td.err-mid { color: var(--amber); font-weight: 700; }
td.err-bad { color: var(--coral); font-weight: 700; }
.tag-pend { display: inline-block; padding: 1px 7px; border-radius: 5px;
  font-size: 10.5px; font-weight: 700; background: #eef1f4;
  color: var(--faint); }

/* PPA in/out-of-money-badge */
.badge { display: inline-block; padding: 1px 8px; border-radius: 5px;
  font-size: 11px; font-weight: 700; }
.badge.itm { background: #e2f3ea; color: #1c6b47; }
.badge.otm { background: #fbe9e5; color: #a4402f; }

/* Produktmix-miniatyr (BESS-stacking) */
.mixbar { display: inline-flex; width: 130px; height: 12px;
  border-radius: 3px; overflow: hidden; vertical-align: middle;
  background: #eef1f4; }
.mixbar span { display: block; height: 100%; }

/* Break-even framhävd */
td.be-col { background: var(--teal-soft); font-weight: 700;
  color: var(--teal-deep); }
th.be-col { color: var(--teal-deep); }

@media (max-width: 880px) {
  .obalans-grid { grid-template-columns: 1fr; }
  .kanni-grid.two { grid-template-columns: 1fr; }
}

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

/* ================================================================
   Sektion 2: Marknad & intäkt (lazy via data-render)
   ================================================================ */
const MARKNAD = DATA.marknad || {};
const BESS = DATA.bess || {};

function calloutsHtml(list) {
  return (list || []).map(i =>
    '<div class="callout ' + toneClass(i.tone) + '">' + esc(i.text) + '</div>'
  ).join('');
}
function kEur(v) { return v == null ? '–' : fmt(v / 1000.0, 0); }

/* ---------- Block 1: Intäkt & PPA ---------- */
RENDERERS.intakt = function () {
  const I = MARKNAD.intakt || {};
  document.getElementById('intakt-insights').innerHTML =
    calloutsHtml(I.insights);

  const fs = I.fleet_series || [];
  if (fs.length) {
    const x = fs.map(m => mLabel(m.month));
    plot('intakt-chart', [
      { type: 'bar', name: 'Capture (spot)', x, y: fs.map(m => m.capture),
        marker: { color: fs.map(m => m.is_partial ? 'rgba(14,124,134,.35)' : C.teal) },
        hovertemplate: '%{y:.1f} €/MWh<extra>Capture spot</extra>' },
      { type: 'scatter', mode: 'lines+markers', name: 'Capture med PPA', x,
        y: fs.map(m => m.capture_ppa), line: { color: C.amber, width: 2 },
        marker: { size: 5 },
        hovertemplate: '%{y:.1f} €/MWh<extra>Med PPA</extra>' },
      { type: 'scatter', mode: 'lines+markers', name: 'Baseload (zonsnitt)', x,
        y: fs.map(m => m.baseload),
        line: { color: C.navy, width: 2, dash: 'dot' }, marker: { size: 4 },
        hovertemplate: '%{y:.1f} €/MWh<extra>Baseload</extra>' },
    ], baseLayout({
      yaxis: { title: { text: '€/MWh' }, gridcolor: C.line, rangemode: 'tozero' },
    }));
  } else {
    document.getElementById('intakt-chart').innerHTML =
      '<p class="chart-note">Ingen intäktsdata.</p>';
  }

  const pv = I.ppa_view || {};
  const fwdLbl = pv.fwd_label || 'forward';
  const rows = (pv.rows || []).map(r => {
    if (!r.has_ppa) {
      return '<tr class="plain"><td data-v="' + esc(r.name) + '"><b>' + esc(r.name) + '</b>' +
        '<span class="zone-tag">' + esc(r.zone) + '</span></td>' +
        '<td data-v="" style="text-align:left;color:var(--faint)">ingen PPA — 100 % spot</td>' +
        '<td data-v=""></td><td data-v=""></td>' +
        '<td data-v="' + (r.capture_spot_eur_mwh ?? '') + '">' + fmt(r.capture_spot_eur_mwh, 1) + '</td>' +
        '<td data-v="' + (r.fwd_eur_mwh ?? '') + '">' + fmt(r.fwd_eur_mwh, 1) + '</td>' +
        '<td data-v=""></td><td data-v=""></td></tr>';
    }
    const itm = (r.ppa_price_eur_mwh != null && r.fwd_eur_mwh != null)
      ? r.ppa_price_eur_mwh > r.fwd_eur_mwh : null;
    const badge = itm == null ? '–'
      : '<span class="badge ' + (itm ? 'itm">in-the-money' : 'otm">out-of-money') + '</span>';
    return '<tr class="plain">' +
      '<td data-v="' + esc(r.name) + '"><b>' + esc(r.name) + '</b>' +
        '<span class="zone-tag">' + esc(r.zone) + '</span></td>' +
      '<td data-v="' + (r.ppa_price_sek_mwh ?? '') + '">' + fmt(r.ppa_price_sek_mwh, 0) + '</td>' +
      '<td data-v="' + (r.ppa_share_pct ?? '') + '">' + fmt(r.ppa_share_pct, 0) + ' %</td>' +
      '<td data-v="' + (r.ppa_price_eur_mwh ?? '') + '">' + fmt(r.ppa_price_eur_mwh, 1) + '</td>' +
      '<td data-v="' + (r.capture_spot_eur_mwh ?? '') + '">' + fmt(r.capture_spot_eur_mwh, 1) + '</td>' +
      '<td data-v="' + (r.fwd_eur_mwh ?? '') + '">' + fmt(r.fwd_eur_mwh, 1) + '</td>' +
      '<td data-v="' + (itm == null ? '' : (itm ? 1 : 0)) + '">' + badge + '</td>' +
      '<td data-v="' + (r.uplift_ytd_eur ?? '') + '"' +
        (r.uplift_ytd_eur > 0 ? ' class="pos"' : (r.uplift_ytd_eur < 0 ? ' class="neg"' : '')) +
        '>' + kEur(r.uplift_ytd_eur) + '</td>' +
      '</tr>';
  }).join('');
  document.getElementById('intakt-ppa-tbl').innerHTML =
    '<table id="ppa-tbl"><thead><tr>' +
    '<th>Park</th><th>PPA SEK/MWh</th><th>Andel</th><th>PPA €/MWh</th>' +
    '<th>Capture spot</th><th>' + esc(fwdLbl) + ' €/MWh</th>' +
    '<th>Läge vs forward</th><th>PPA-effekt YTD k€</th>' +
    '</tr></thead><tbody>' + rows + '</tbody></table>';
  makeSortable(document.getElementById('ppa-tbl'));
};

/* ---------- Block 2: Obalanskostnad ---------- */
RENDERERS.obalans = function () {
  const O = MARKNAD.obalans || {};
  document.getElementById('obalans-insights').innerHTML =
    calloutsHtml(O.insights);

  const parks = O.parks || [];
  const spann = (a, b, d, scale) => {
    if (a == null || b == null) return '–';
    const s = scale || 1;
    const lo = Math.min(a, b) / s, hi = Math.max(a, b) / s;
    return fmt(lo, d) + ' – ' + fmt(hi, d);
  };
  const rows = parks.map(p => {
    const a = p.last12 || {};
    return '<tr class="plain">' +
      '<td data-v="' + esc(p.name) + '"><b>' + esc(p.name) + '</b>' +
        '<span class="zone-tag">' + esc(p.zone) + '</span></td>' +
      '<td data-v="' + (a.cost_per_mwh_a ?? '') + '">' + fmt(a.cost_per_mwh_a, 2) + '</td>' +
      '<td data-v="' + (a.cost_per_mwh_b ?? '') + '">' + fmt(a.cost_per_mwh_b, 2) + '</td>' +
      '<td data-v="' + ((a.cost_eur_a ?? 0) + (a.cost_eur_b ?? 0)) + '">' +
        spann(a.cost_eur_a, a.cost_eur_b, 1, 1000) + '</td>' +
      '<td data-v="' + (a.volume_mwh ?? '') + '">' + fmt(a.volume_mwh, 0) + '</td>' +
      '<td data-v="' + (a.months ?? '') + '">' + fmt(a.months, 0) + '</td>' +
      '</tr>';
  }).join('');
  const port = O.portfolio_last12;
  const foot = port
    ? '<tfoot><tr><td>Portfölj (' + fmt(port.park_count, 0) + ' parker)</td>' +
      '<td>' + fmt(port.cost_per_mwh_a, 2) + '</td>' +
      '<td>' + fmt(port.cost_per_mwh_b, 2) + '</td>' +
      '<td>' + spann(port.cost_eur_a, port.cost_eur_b, 1, 1000) + '</td>' +
      '<td>' + fmt(port.volume_mwh, 0) + '</td><td></td></tr></tfoot>'
    : '';
  document.getElementById('obalans-tbl').innerHTML =
    '<table id="obalans-table"><thead><tr>' +
    '<th>Park</th><th>€/MWh persistens</th><th>€/MWh budgetform</th>' +
    '<th>Netto k€ (spann)</th><th>Volym MWh</th><th>Mån</th>' +
    '</tr></thead><tbody>' + rows + '</tbody>' + foot + '</table>';
  makeSortable(document.getElementById('obalans-table'));

  if (parks.length) {
    const names = parks.map(p => p.name);
    plot('obalans-chart', [
      { type: 'bar', name: 'Persistens (D-1)', x: names,
        y: parks.map(p => (p.last12 || {}).cost_per_mwh_a),
        marker: { color: C.teal },
        hovertemplate: '%{y:.2f} €/MWh<extra>Persistens</extra>' },
      { type: 'bar', name: 'Budgetform', x: names,
        y: parks.map(p => (p.last12 || {}).cost_per_mwh_b),
        marker: { color: C.amber },
        hovertemplate: '%{y:.2f} €/MWh<extra>Budgetform</extra>' },
    ], baseLayout({
      barmode: 'group',
      yaxis: { title: { text: '€/MWh producerad' }, gridcolor: C.line },
      xaxis: { tickangle: -30, gridcolor: C.line, tickfont: { size: 10.5 } },
      margin: { l: 48, r: 14, t: 10, b: 64 },
    }));
  }

  const m = O.method || {};
  document.getElementById('obalans-method').textContent =
    'Metod: (a) ' + (m.proxy_a || '') + ' (b) ' + (m.proxy_b || '') +
    ' Kostnad: ' + (m.cost_definition || '');
};

/* ---------- Block 3: Kannibalisering ---------- */
RENDERERS.kanni = function () {
  const K = MARKNAD.kannibalisering || {};
  document.getElementById('kanni-insights').innerHTML =
    calloutsHtml(K.insights);

  const zones = K.zones || {};
  const sig = Object.values(zones).filter(z => z.status === 'ok' && z.significant);
  const grid = document.getElementById('kanni-charts');
  if (sig.length === 2) grid.classList.add('two');
  grid.innerHTML = sig.map(z =>
    '<div><p class="kanni-chart-title">' + esc(z.zone) + ' — ' +
    fmt(z.slope_pp_per_gw, 1) + ' p.e. per GW (R² ' + fmt(z.r2, 2) + ')</p>' +
    '<div class="kanni-chart" id="kanni-' + esc(z.zone) + '"></div></div>'
  ).join('') || '<p class="chart-note">Ingen zon med signifikant samband.</p>';

  sig.forEach(z => {
    const pts = z.points || [];
    const proj = z.projection || [];
    const xs = pts.map(p => p.installed_gw);
    const xAll = xs.concat(proj.map(p => p.installed_gw));
    const xMin = Math.min(...xAll), xMax = Math.max(...xAll);
    const traces = [];

    // Extrapoleringsband (ritas först så scatter hamnar ovanpå)
    if (proj.length && proj[0].ratio_pp_low != null) {
      const lastPt = pts[pts.length - 1];
      const bx = [lastPt.installed_gw].concat(proj.map(p => p.installed_gw));
      const bLow = [lastPt.ratio_pp].concat(proj.map(p => p.ratio_pp_low));
      const bHigh = [lastPt.ratio_pp].concat(proj.map(p => p.ratio_pp_high));
      traces.push({
        type: 'scatter', mode: 'none', x: bx.concat([...bx].reverse()),
        y: bHigh.concat([...bLow].reverse()),
        fill: 'toself', fillcolor: 'rgba(222,155,38,.15)',
        line: { width: 0 }, hoverinfo: 'skip', showlegend: false,
      });
      traces.push({
        type: 'scatter', mode: 'lines+markers+text', name: 'Framskrivning',
        x: proj.map(p => p.installed_gw), y: proj.map(p => p.ratio_pp),
        text: proj.map(p => String(p.year)), textposition: 'bottom center',
        textfont: { size: 10, color: C.amber },
        line: { color: C.amber, width: 1.6, dash: 'dash' },
        marker: { size: 7, symbol: 'diamond', color: C.amber },
        hovertemplate: '%{text}: %{y:.1f} % vid %{x:.2f} GW<extra>Framskrivning</extra>',
      });
    }

    // Regressionslinje
    traces.push({
      type: 'scatter', mode: 'lines', name: 'OLS-fit',
      x: [xMin, xMax],
      y: [z.intercept_pp + z.slope_pp_per_gw * xMin,
          z.intercept_pp + z.slope_pp_per_gw * xMax],
      line: { color: C.navy, width: 1.6 }, hoverinfo: 'skip',
    });

    // Observationer
    traces.push({
      type: 'scatter', mode: 'markers+text', name: 'Observerade år',
      x: xs, y: pts.map(p => p.ratio_pp),
      text: pts.map(p => String(p.year)), textposition: 'top center',
      textfont: { size: 10, color: C.muted },
      marker: {
        size: 9, color: C.teal,
        symbol: pts.map(p => p.installed_extrapolated ? 'circle-open' : 'circle'),
        line: { width: 1.5, color: C.tealDeep },
      },
      hovertemplate: '%{text}: %{y:.1f} % vid %{x:.2f} GW installerad' +
        '<extra>Capture ratio</extra>',
    });

    plot('kanni-' + z.zone, traces, baseLayout({
      xaxis: { title: { text: 'Installerad sol (GW)' }, gridcolor: C.line },
      yaxis: { title: { text: 'Capture ratio (%)' }, gridcolor: C.line },
      hovermode: 'closest',
    }));
  });

  const notSig = Object.values(zones)
    .filter(z => z.status === 'ok' && !z.significant)
    .map(z => z.zone + ' ' + fmt(z.slope_pp_per_gw, 1) + ' p.e./GW (ej signifikant — 95 %-KI spänner över noll)');
  const insuff = Object.values(zones)
    .filter(z => z.status && z.status !== 'ok')
    .map(z => z.zone + ': ' + (z.reason || 'otillräckligt underlag'));
  document.getElementById('kanni-foot').textContent =
    (notSig.length ? 'Ej signifikanta zoner: ' + notSig.join('; ') + '. ' : '') +
    (insuff.length ? 'Utan regression: ' + insuff.join('; ') + '.' : '');
  document.getElementById('kanni-assumptions-list').innerHTML =
    (K.assumptions || []).map(a => '<li>' + esc(a) + '</li>').join('');
};

/* ---------- Block 4: Forward-läge ---------- */
const FWD_STATE = { contract: null, zone: null };

function fwdImplied(h, zone) {
  const epad = {};
  ((h.epad_series || {})[zone] || []).forEach(r => { epad[r.date] = r.price; });
  const out = [];
  (h.sys_series || []).forEach(r => {
    if (epad[r.date] != null) out.push({ date: r.date, price: r.price + epad[r.date] });
  });
  return out;
}

function renderConvergence() {
  const F = MARKNAD.forward || {};
  const h = (F.history || {})[FWD_STATE.contract];
  if (!h) return;
  const zone = FWD_STATE.zone;
  const sys = h.sys_series || [];
  const implied = fwdImplied(h, zone);
  const realised = (h.realised_spot || {})[zone];

  const traces = [
    { type: 'scatter', mode: 'lines', name: 'SYS forward',
      x: sys.map(r => r.date), y: sys.map(r => r.price),
      line: { color: C.navy, width: 1.8 },
      hovertemplate: '%{y:.1f} €/MWh<extra>SYS</extra>' },
    { type: 'scatter', mode: 'lines', name: zone + ' implied (SYS+EPAD)',
      x: implied.map(r => r.date), y: implied.map(r => r.price),
      line: { color: C.teal, width: 2 },
      hovertemplate: '%{y:.1f} €/MWh<extra>' + zone + ' implied</extra>' },
  ];
  if (realised != null) {
    traces.push({
      type: 'scatter', mode: 'lines+markers', name: 'Realiserat ' + zone,
      x: [h.delivery_start, h.delivery_end], y: [realised, realised],
      line: { color: C.coral, width: 2, dash: 'dash' },
      marker: { size: [0, 10], symbol: 'diamond', color: C.coral },
      hovertemplate: fmt(realised, 1) + ' €/MWh<extra>Realiserad spot</extra>',
    });
  }
  plot('fwd-conv', traces, baseLayout({
    yaxis: { title: { text: '€/MWh' }, gridcolor: C.line },
    xaxis: { type: 'date', gridcolor: C.line },
    hovermode: 'x unified',
    shapes: [{
      type: 'line', x0: h.delivery_start, x1: h.delivery_start,
      y0: 0, y1: 1, yref: 'paper',
      line: { color: C.faint, width: 1.2, dash: 'dot' },
    }],
    annotations: [{
      x: h.delivery_start, y: 1, yref: 'paper', yanchor: 'bottom',
      text: 'Leverans startar', showarrow: false,
      font: { size: 10.5, color: C.faint },
    }],
  }));

  const note = document.getElementById('fwd-clean-note');
  if (h.is_clean_final === false) {
    note.hidden = false;
    note.textContent = 'Sista notering ' + h.final_settlement_date +
      ' — långt före leveransstart ' + h.delivery_start +
      '. Historiken är ofullständig (kontraktet försvann ur källan); ' +
      'konvergensen kan inte utvärderas.';
  } else { note.hidden = true; }
}

RENDERERS.forward = function () {
  const F = MARKNAD.forward || {};
  document.getElementById('fwd-insights').innerHTML = calloutsHtml(F.insights);

  const hist = F.history || {};
  const labels = Object.keys(hist).sort((a, b) =>
    (hist[b].delivery_start || '').localeCompare(hist[a].delivery_start || ''));
  const sel = document.getElementById('fwd-contract');
  if (!labels.length) {
    document.getElementById('fwd-conv').innerHTML =
      '<p class="chart-note">Ingen forwardhistorik tillgänglig.</p>';
    return;
  }
  sel.innerHTML = labels.map(l => {
    const h = hist[l];
    return '<option value="' + esc(l) + '">' + esc(l) + ' (' +
      esc(h.delivery_start) + ' → ' + esc(h.delivery_end) + ')</option>';
  }).join('');
  FWD_STATE.contract = labels[0];

  const zonesOf = (h) => ['SE1', 'SE2', 'SE3', 'SE4']
    .filter(z => ((h.epad_series || {})[z] || []).length);
  const zBox = document.getElementById('fwd-zones');
  function renderZoneBtns() {
    const zs = zonesOf(hist[FWD_STATE.contract]);
    if (!zs.includes(FWD_STATE.zone)) FWD_STATE.zone = zs[0] || null;
    zBox.innerHTML = zs.map(z =>
      '<button class="' + (z === FWD_STATE.zone ? 'on' : '') +
      '" data-z="' + z + '">' + z + '</button>').join('');
    zBox.querySelectorAll('button').forEach(b => {
      b.addEventListener('click', () => {
        FWD_STATE.zone = b.dataset.z;
        renderZoneBtns(); renderConvergence();
      });
    });
  }
  sel.addEventListener('change', () => {
    FWD_STATE.contract = sel.value;
    renderZoneBtns(); renderConvergence();
  });
  renderZoneBtns();
  renderConvergence();

  // Lookback-tabell
  const errCls = (r) => {
    if (!r.delivered || r.error == null) return '';
    const a = Math.abs(r.error);
    return a < 5 ? ' class="err-ok"' : (a <= 15 ? ' class="err-mid"' : ' class="err-bad"');
  };
  const cell = (v) => '<td data-v="' + (v ?? '') + '">' + fmt(v, 1) + '</td>';
  const rows = (F.lookback || []).map(r =>
    '<tr class="plain">' +
    '<td data-v="' + esc(r.contract) + '"><b>' + esc(r.contract) + '</b>' +
      (r.delivered ? '' : ' <span class="tag-pend">pågår</span>') +
      (r.is_clean_final === false ? ' <span class="tag-pend">lucka</span>' : '') +
    '</td>' +
    '<td data-v="' + esc(r.zone) + '">' + esc(r.zone) + '</td>' +
    cell(r.t12) + cell(r.t6) + cell(r.t3) + cell(r.t1) +
    cell(r.final) + cell(r.realised) +
    '<td data-v="' + (r.error ?? '') + '"' + errCls(r) + '>' +
      (r.error == null ? '–' : fmtSign(r.error, 1).replace(' %', '')) + '</td>' +
    '<td data-v="' + (r.error_pct ?? '') + '"' + errCls(r) + '>' +
      (r.error_pct == null ? '–' : fmtSign(r.error_pct, 1)) + '</td>' +
    '</tr>'
  ).join('');
  document.getElementById('fwd-lookback').innerHTML =
    '<table id="lookback-tbl"><thead><tr>' +
    '<th>Kontrakt</th><th>Zon</th><th>T−12 mån</th><th>T−6</th><th>T−3</th>' +
    '<th>T−1</th><th>Slutfix</th><th>Realiserat</th><th>Fel €/MWh</th>' +
    '<th>Fel %</th></tr></thead><tbody>' + rows + '</tbody></table>';
  makeSortable(document.getElementById('lookback-tbl'));

  const hl = F.health || {};
  const warn = [];
  (hl.stale_finals || []).forEach(s => warn.push(
    s.contract + ': sista fix ' + s.last_fix + ' (väntad nära ' + s.expected_near + ')'));
  (hl.approaching_expiry || []).forEach(s => warn.push(
    s.contract + ': leverans ' + s.delivery_start + ' närmar sig, fixen är ' +
    s.days_stale + ' dagar gammal — synka innan kontraktet försvinner ur källan'));
  const hEl = document.getElementById('fwd-health');
  if (warn.length) { hEl.hidden = false; hEl.textContent = 'Datavarningar: ' + warn.join(' · '); }
};

/* ================================================================
   Sektion 3: Batteri & investering
   ================================================================ */
const MIX_COLORS = {
  fcr_n: '#0e7c86', fcr_d_up: '#2e9e6b', fcr_d_down: '#8fd0c6',
  afrr_up: '#de9b26', afrr_down: '#ecc98a',
  mfrr_cm_up: '#1d3a4f', mfrr_cm_down: '#8aa2b5',
};

function mixbarHtml(mix, labels) {
  const entries = Object.entries(mix || {});
  const tot = entries.reduce((s, [, h]) => s + h, 0);
  if (!tot) return '<span class="mixbar"></span>';
  return '<span class="mixbar">' + entries.map(([p, h]) =>
    '<span style="width:' + (100 * h / tot).toFixed(1) + '%;background:' +
    (MIX_COLORS[p] || '#c3ccd3') + '" title="' +
    esc((labels[p] || p) + ': ' + fmt(h, 0) + ' h') + '"></span>'
  ).join('') + '</span>';
}

RENDERERS.bessStack = function () {
  const rows = BESS.stack_rows || [];
  const labels = BESS.product_labels || {};
  if (!rows.length) {
    document.getElementById('stack-tbl').innerHTML =
      '<p class="chart-note">Ingen stackingdata.</p>';
    return;
  }
  const html = rows.map(r =>
    '<tr class="plain">' +
    '<td data-v="' + esc(r.zone) + '"><b>' + esc(r.zone) + '</b> ' +
      r.duration_h + 'h <span class="zone-tag">' + r.year + '</span></td>' +
    '<td data-v="' + (r.stacked_eur ?? '') + '"><b>' + fmt(r.stacked_eur, 0) + '</b></td>' +
    '<td data-v="' + (r.arb_only_eur ?? '') + '">' + fmt(r.arb_only_eur, 0) + '</td>' +
    '<td data-v="' + (r.best_ancillary_only_eur ?? '') + '">' +
      fmt(r.best_ancillary_only_eur, 0) + '<span style="color:var(--faint);font-size:11px"> ' +
      esc(labels[r.best_ancillary_product] || '') + '</span></td>' +
    '<td data-v="' + (r.uplift_vs_best_single_pct ?? '') + '"' +
      ((r.uplift_vs_best_single_pct || 0) > 3 ? ' class="pos"' : '') + '>' +
      fmtSign(r.uplift_vs_best_single_pct, 1) + '</td>' +
    '<td data-v="' + (r.reserve_share_pct ?? '') + '">' + fmt(r.reserve_share_pct, 0) + ' %</td>' +
    '<td data-v="' + (r.cycles ?? '') + '">' + fmt(r.cycles, 0) + '</td>' +
    '<td data-v="">' + mixbarHtml(r.top_product_mix, labels) + '</td>' +
    '</tr>'
  ).join('');
  const legend = Object.entries(MIX_COLORS)
    .filter(([p]) => rows.some(r => (r.top_product_mix || {})[p]))
    .map(([p, c]) =>
      '<span style="white-space:nowrap"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' +
      c + ';margin-right:4px"></span>' + esc(labels[p] || p) + '</span>'
    ).join(' · ');
  document.getElementById('stack-tbl').innerHTML =
    '<table id="stack-table"><thead><tr>' +
    '<th>Zon × duration</th><th>Stackad EUR/MW·år</th><th>Bara arbitrage</th>' +
    '<th>Bästa stödtjänst</th><th>Uplift</th><th>Reservandel</th>' +
    '<th>Cykler</th><th>Reservmix</th></tr></thead><tbody>' + html +
    '</tbody></table>' +
    '<p class="blk-foot">Reservmix: ' + legend + '</p>';
  makeSortable(document.getElementById('stack-table'));
};

RENDERERS.bessAcc = function () {
  const rows = BESS.stack_rows || [];
  if (!rows.length) return;
  const accKeys = [...new Set(rows.flatMap(r =>
    Object.keys(r.acceptance_sensitivity || {})))].sort((a, b) => b - a);
  const x = rows.map(r => r.zone + ' ' + r.duration_h + 'h');
  const accColor = (k, i) => [C.navy, C.teal, C.amber, C.coral][i] || C.faint;
  plot('acc-chart', accKeys.map((k, i) => ({
    type: 'bar', name: Math.round(parseFloat(k) * 100) + ' % acceptans',
    x, y: rows.map(r => (r.acceptance_sensitivity || {})[k]),
    marker: { color: accColor(k, i) },
    hovertemplate: '%{y:.0f} EUR/MW<extra>' +
      Math.round(parseFloat(k) * 100) + ' %</extra>',
  })), baseLayout({
    barmode: 'group',
    yaxis: { title: { text: 'EUR/MW·år (stackad)' }, gridcolor: C.line },
    xaxis: { gridcolor: C.line, tickfont: { size: 11 } },
  }));
};

RENDERERS.bessKalkyl = function () {
  document.getElementById('kalkyl-insights').innerHTML =
    calloutsHtml(BESS.kalkyl_insights);
  const rows = BESS.kalkyl_rows || [];
  if (!rows.length) {
    document.getElementById('kalkyl-tbl').innerHTML =
      '<p class="chart-note">Ingen kalkyldata.</p>';
    return;
  }
  const best = BESS.kalkyl_best || {};
  const html = rows.map(r => {
    const isBest = r.zone === best.zone && r.duration_h === best.duration_h;
    return '<tr class="plain"' + (isBest ? ' style="background:#f2f7f8"' : '') + '>' +
      '<td data-v="' + esc(r.zone) + '"><b>' + esc(r.zone) + '</b> ' +
        r.duration_h + 'h' + (isBest ? ' <span class="zone-tag">bäst</span>' : '') + '</td>' +
      '<td data-v="' + (r.capex_eur ?? '') + '">' + fmt(r.capex_eur, 0) + '</td>' +
      '<td data-v="' + (r.annual_gross_eur ?? '') + '">' + fmt(r.annual_gross_eur, 0) + '</td>' +
      '<td data-v="' + (r.irr_pct ?? '') + '">' + fmt(r.irr_pct, 1) + ' %</td>' +
      '<td data-v="' + (r.npv_eur ?? '') + '"' +
        ((r.npv_eur || 0) < 0 ? ' class="neg"' : '') + '>' + fmt(r.npv_eur, 0) + '</td>' +
      '<td data-v="' + (r.payback_yr ?? '') + '">' + fmt(r.payback_yr, 1) + '</td>' +
      '<td data-v="' + (r.breakeven_revenue_pct ?? '') + '" class="be-col">' +
        fmt(r.breakeven_revenue_pct, 0) + ' %</td>' +
      '<td data-v="' + (r.viable ? 1 : 0) + '"><span class="status-dot ' +
        (r.viable ? 'pos' : 'neg') + '"></span></td>' +
      '</tr>';
  }).join('');
  document.getElementById('kalkyl-tbl').innerHTML =
    '<table id="kalkyl-table"><thead><tr>' +
    '<th>Zon × duration</th><th>CAPEX EUR/MW</th><th>Årsintäkt EUR/MW</th>' +
    '<th>IRR</th><th>NPV EUR/MW</th><th>Payback år</th>' +
    '<th class="be-col">Break-even % av intäkt</th><th>Klarar krav</th>' +
    '</tr></thead><tbody>' + html + '</tbody></table>';
  makeSortable(document.getElementById('kalkyl-table'));

  const p = BESS.kalkyl_params || {};
  document.getElementById('kalkyl-params').textContent =
    'Antaganden: CAPEX ' + fmt(p.capex_eur_per_mwh, 0) + ' EUR/MWh · OPEX ' +
    fmt(p.opex_eur_per_mw_yr, 0) + ' EUR/MW·år · ' + p.lifetime_yr +
    ' års livslängd · ' + fmt((p.discount || 0) * 100, 0) +
    ' % avkastningskrav · intäktsbas: ' + (p.revenue_basis || '') +
    ' · break-even = andel av årsintäkten som ger NPV 0.';
};

RENDERERS.bessBtm = function () {
  const parks = (BESS.btm || {}).parks || {};
  const keys = Object.keys(parks).sort((a, b) =>
    (parks[b].uplift_eur_mwh || 0) - (parks[a].uplift_eur_mwh || 0));
  if (!keys.length) {
    document.getElementById('btm-tbl').innerHTML =
      '<p class="chart-note">Ingen BTM-data (kräver parkprofiler).</p>';
    return;
  }
  const html = keys.map(k => {
    const p = parks[k];
    const tmy = p.tmy || {};
    const diff = (p.uplift_eur_mwh != null && tmy.uplift_eur_mwh != null)
      ? p.uplift_eur_mwh - tmy.uplift_eur_mwh : null;
    const name = ((DATA.parks || {})[k] || {}).name || (k.charAt(0).toUpperCase() + k.slice(1));
    return '<tr class="plain">' +
      '<td data-v="' + esc(name) + '"><b>' + esc(name) + '</b>' +
        '<span class="zone-tag">' + esc(p.zone) + '</span></td>' +
      '<td data-v="' + (p.battery_mw ?? '') + '">' + fmt(p.battery_mw, 1) + ' MW / ' +
        fmt(p.battery_mwh, 1) + ' MWh</td>' +
      '<td data-v="' + (p.capture_no_batt_eur_mwh ?? '') + '">' +
        fmt(p.capture_no_batt_eur_mwh, 1) + '</td>' +
      '<td data-v="' + (p.capture_with_batt_eur_mwh ?? '') + '">' +
        fmt(p.capture_with_batt_eur_mwh, 1) + '</td>' +
      '<td data-v="' + (p.uplift_eur_mwh ?? '') + '"><b>' +
        fmtSign(p.uplift_eur_mwh, 2).replace(' %', '') + '</b></td>' +
      '<td data-v="' + (tmy.uplift_eur_mwh ?? '') + '">' +
        (tmy.uplift_eur_mwh == null ? '–' : fmtSign(tmy.uplift_eur_mwh, 2).replace(' %', '')) + '</td>' +
      '<td data-v="' + (diff ?? '') + '"' +
        (diff > 0 ? ' class="pos"' : (diff < 0 ? ' class="neg"' : '')) + '>' +
        (diff == null ? '–' : fmtSign(diff, 2).replace(' %', '')) + '</td>' +
      '<td data-v="' + (p.uplift_eur_year ?? '') + '">' + fmt(p.uplift_eur_year, 0) + '</td>' +
      '</tr>';
  }).join('');
  document.getElementById('btm-tbl').innerHTML =
    '<table id="btm-table"><thead><tr>' +
    '<th>Park</th><th>Batteri</th><th>Capture utan batteri €/MWh</th>' +
    '<th>Med batteri</th><th>Lyft €/MWh</th><th>TMY-lyft</th>' +
    '<th>Verklig − TMY</th><th>EUR/år</th>' +
    '</tr></thead><tbody>' + html + '</tbody></table>';
  makeSortable(document.getElementById('btm-table'));
};

/* ================= Init ================= */
function init() {
  renderHero();
  renderLeague();
  renderParkGrid();
  // BESS-sektionens hero-insikter (ingen tung rendering — direkt).
  const bessBox = document.getElementById('bess-insights');
  if (bessBox) {
    bessBox.innerHTML = calloutsHtml(
      (BESS.stack_insights || []).concat([])
    );
  }
  lazyInit();
}
document.addEventListener('DOMContentLoaded', init);
"""
