# Capture per-graf kontroller — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Flytta Zone, Period, Range och Profiles från globala sid-kontroller in i varje graf på Capture-fliken, med oberoende state per graf.

**Architecture:** Splittra global `CAPTURE_STATE` i tre per-graf objekt (`CAPTURE_STATES.main` / `.spread` / `.heatmap`). Refaktorera render-funktioner att ta state-parameter. Bygg ny HTML-struktur där varje kort har en kompakt kontrollrad (Zone/Period/Range chips + range-nav) under card-head plus en kompakt Profiles-popover uppe till höger. Heatmap-kortet får bara Zone. KPI-stripen följer main-grafen.

**Tech Stack:** Inline HTML/CSS/JS i `elpris/unified_dashboard_v3_html.py`. Plotly.js via CDN. Ingen extern data-källa berörs. Verifiering sker via preview-server och visuell inspektion (renderingen är HTML/JS — pytest täcker inte detta).

**Sub-Skill för verifiering:** Använd `mcp__Claude_Preview__preview_*`-tools för att starta preview-servern och köra klick-tester på den genererade HTML:en. Verifiera enligt acceptanskriterierna i designdokumentet.

---

## Task 0: Baseline — verifiera dagens beteende

**Files:** Inga ändringar.

**Step 1:** Säkerställ att vi är på branchen `capture-per-chart-controls`.

```bash
git status -sb
```

Förväntat: `## capture-per-chart-controls`.

**Step 2:** Generera dashboard från huvudbranchens kod (oförändrat). Använd `--preview` så vi får filen i preview-servern.

```bash
python3 generate_unified_dashboard.py --preview
```

Förväntat: Ingen Python-traceback. Filen skrivs till `/private/tmp/dashboard.html` (om `--preview` används enligt minne `dashboard-preview-verify.md`) eller `Resultat/rapporter/dashboard_unified_v3_YYYYMMDD.html`.

**Step 3:** Öppna preview, klicka in på Capture-fliken, screenshot för baseline.

```
preview_start(file_path)  # om inte redan startad
preview_eval('window.location.hash = "#capture"; window.scrollTo(0, 0); "ok"')
preview_screenshot()
```

Spara i tanken: hur ser dagens Capture-flik ut visuellt (page-head med Zone+Period, Profiles-kort, range-bar, två grafer, heatmap).

**Step 4:** Notera ner exakt vad som visas vid default-state (SE-zon, vilken period, vilka profiler aktiva) så vi kan jämföra efter Task 9.

---

## Task 1: Refaktorera helper-funktioner att ta state-parameter

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` lines 1468–1526 (helper-funktioner)

**Mål:** Refaktorera `captureLatestDateMs`, `captureCurrentWindow`, `captureNavRange` att ta state-objekt som första parameter istället för att läsa global `CAPTURE_STATE`. `captureRowDate`, `captureSliceRows` och `captureWindowLabel` tar inte state idag — de förblir oförändrade.

**Step 1:** Läs nuvarande implementation av `captureLatestDateMs` (lines ~1475–1484) och `captureCurrentWindow` (lines ~1486–1497) och `captureNavRange` (lines ~1512–1526).

**Step 2:** Ändra signaturer:

```javascript
function captureLatestDateMs(state) {
    var z = (DATA.data && DATA.data[state.zone]) || {};
    var period = state.period;
    var maxMs = null;
    state.profiles.forEach(function(k) {
        var rows = z[k] && z[k][period];
        if (!rows || !rows.length) return;
        var ms = captureRowDate(rows[rows.length - 1], period).getTime();
        if (maxMs == null || ms > maxMs) maxMs = ms;
    });
    return maxMs;
}

function captureCurrentWindow(state) {
    if (state.range === 'all') return null;
    var months = CAPTURE_RANGE_MONTHS[state.range];
    if (!months) return null;
    var latestMs = captureLatestDateMs(state);
    if (latestMs == null) return null;
    var endMs = state.rangeEnd != null ? state.rangeEnd : latestMs;
    if (endMs > latestMs) endMs = latestMs;
    var endDate = new Date(endMs);
    var startDate = new Date(endDate);
    startDate.setUTCMonth(startDate.getUTCMonth() - months);
    return { startMs: startDate.getTime(), endMs: endMs, months: months, atLatest: endMs === latestMs };
}
```

`captureNavRange` får två argument: `state` och `direction`. Den tar bort sina interna render-anrop (de tar `wireCaptureCard` istället i Task 5).

```javascript
function captureNavRange(state, direction) {
    var months = CAPTURE_RANGE_MONTHS[state.range];
    if (!months) return;
    var latestMs = captureLatestDateMs(state);
    if (latestMs == null) return;
    var endMs = state.rangeEnd != null ? state.rangeEnd : latestMs;
    var d = new Date(endMs);
    d.setUTCMonth(d.getUTCMonth() + direction * months);
    var newEnd = d.getTime();
    if (newEnd > latestMs) newEnd = latestMs;
    state.rangeEnd = newEnd;
}
```

**Step 3:** Uppdatera alla call-sites i `renderCapture`, `renderCaptureChart`, `renderCaptureSpreadChart`, `renderCaptureRangeBar` att passera `CAPTURE_STATE` som parameter (tillfälligt — de blir per-graf i Task 3).

Sök i filen efter `captureLatestDateMs()`, `captureCurrentWindow()`, `captureNavRange(` och uppdatera till `captureLatestDateMs(CAPTURE_STATE)`, `captureCurrentWindow(CAPTURE_STATE)`, `captureNavRange(CAPTURE_STATE, -1)`, etc.

**Step 4:** Generera dashboard och verifiera att inget syns annorlunda.

```bash
python3 generate_unified_dashboard.py --preview
```

Reload preview, klicka igenom Zone/Period/Range/profiles — allt ska bete sig identiskt med Task 0-baseline.

```
preview_eval('window.location.reload(); "ok"')
preview_console_logs()  # ska vara tom på fel
preview_screenshot()
```

**Step 5:** Commit.

```bash
git add elpris/unified_dashboard_v3_html.py
git commit -m "refactor(capture): helpers tar state-parameter

Inget visuellt beteende ändrat. Förberedelse för per-graf state.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Refaktorera render-funktioner att ta state-parameter

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` (renderCaptureChart ~1720-1800, renderCaptureSpreadChart ~1802-1841, renderHeatmap ~1843-1880, renderCaptureKPIs ~1646-1683)

**Step 1:** Ändra signaturer:

```javascript
function renderCaptureChart(state)       { /* ersätt CAPTURE_STATE → state */ }
function renderCaptureSpreadChart(state) { /* ersätt CAPTURE_STATE → state */ }
function renderHeatmap(state)            { /* ersätt CAPTURE_STATE → state */ }
function renderCaptureKPIs(state)        { /* ersätt CAPTURE_STATE → state */ }
```

I funktionsbody:
- `CAPTURE_STATE.zone` → `state.zone`
- `CAPTURE_STATE.period` → `state.period`
- `CAPTURE_STATE.profiles` → `state.profiles`
- `CAPTURE_STATE.range` → `state.range`
- `captureLatestDateMs()` → `captureLatestDateMs(state)`
- `captureCurrentWindow()` → `captureCurrentWindow(state)`

`renderCaptureKPIs` kommer i Task 7 att alltid få main-state — den signaturen är samma.

**Step 2:** Uppdatera anrop i `renderCapture` (lines ~1641–1644 idag):

```javascript
    renderCaptureKPIs(CAPTURE_STATE);
    renderCaptureRangeBar();  // ej refaktorerad än
    renderCaptureChart(CAPTURE_STATE);
    renderCaptureSpreadChart(CAPTURE_STATE);
    renderHeatmap(CAPTURE_STATE);
```

**Step 3:** Generera + reload preview + klick-test (samma som Task 1 Step 4). Inget visuellt ska ha ändrats.

**Step 4:** Commit.

```bash
git add elpris/unified_dashboard_v3_html.py
git commit -m "refactor(capture): render-funktioner tar state-parameter

Inget visuellt beteende ändrat. CAPTURE_STATE passeras explicit till
renderCaptureChart, renderCaptureSpreadChart, renderHeatmap, renderCaptureKPIs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Skapa per-graf state-container

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` (state-deklaration ~1453–1457)

**Step 1:** Ersätt `CAPTURE_STATE`-deklarationen med `CAPTURE_STATES`-container:

```javascript
var CAPTURE_STATES = {
    main: {
        zone: null,
        period: 'monthly',
        profiles: ['baseload', 'sol_syd'],
        range: 'all',
        rangeEnd: null,
    },
    spread: {
        zone: null,
        period: 'monthly',
        profiles: ['baseload', 'sol_syd'],
        range: 'all',
        rangeEnd: null,
    },
    heatmap: {
        zone: null,
    },
};
```

Behåll en `CAPTURE_STATE`-alias som peklar på `CAPTURE_STATES.main` tillfälligt:

```javascript
var CAPTURE_STATE = CAPTURE_STATES.main;  // legacy alias, tas bort i Task 9
```

Det gör att gamla wire-bindningar fortfarande fungerar tills vi byter ut HTML-strukturen i Task 4–5.

**Step 2:** Generera + reload + klick-test. Inget beteende ska ha ändrats (alla render-funktioner får fortfarande main-state via aliaset).

**Step 3:** Commit.

```bash
git add elpris/unified_dashboard_v3_html.py
git commit -m "refactor(capture): per-graf state-container CAPTURE_STATES

CAPTURE_STATE blir alias för CAPTURE_STATES.main under övergången.
Inget visuellt beteende ändrat.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Ny HTML-struktur för Capture-sektionen

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` (HTML-mall lines ~4713–4770)

**Mål:** Ta bort globala kontroller, lägg till per-kort kontrollblock och profiles-knappar inuti card-head. Behåll DOM-ID för chart-elementen (`capture-main-chart`, `capture-spread-chart`, `capture-heatmap`).

**Step 1:** Ersätt hela `<section id="page-capture">`-blocket. Den nya strukturen:

```html
    <section class="page" id="page-capture" role="tabpanel" aria-labelledby="tab-capture">
      <header class="page-head">
        <div class="page-head-left">
          <div class="page-eyebrow">Market</div>
          <h1 class="page-title">Capture Prices</h1>
          <p class="page-sub">Solar-weighted price realisation across the four Swedish bidding zones, by profile and time horizon.</p>
        </div>
      </header>
      <div id="capture-content">
        <div class="kpi-strip" id="capture-kpis"></div>

        <div class="grid-2">
          <!-- Price evolution -->
          <div class="card capture-card">
            <div class="card-head">
              <div><div class="card-title">Price evolution</div><div class="card-sub">Baseload &amp; capture, EUR/MWh.</div></div>
              <button type="button" class="profiles-trigger" id="capture-main-profiles-btn" aria-haspopup="true" aria-expanded="false">
                <span class="profiles-trigger-label" id="capture-main-profiles-label">Profiles</span>
                <span class="profiles-trigger-caret">▾</span>
              </button>
              <div class="profiles-popover" id="capture-main-profiles-pop" hidden></div>
            </div>
            <div class="chart-controls">
              <span class="label-control">Zone <div class="seg" id="capture-main-zones"></div></span>
              <span class="label-control">Period <div class="seg" id="capture-main-period"></div></span>
              <span class="label-control range-control">
                Range <div class="seg" id="capture-main-range"></div>
                <span class="range-nav" id="capture-main-range-nav">
                  <button type="button" class="range-arrow" id="capture-main-range-prev" aria-label="Previous window">‹</button>
                  <span class="range-label" id="capture-main-range-label">All time</span>
                  <button type="button" class="range-arrow" id="capture-main-range-next" aria-label="Next window">›</button>
                  <button type="button" id="capture-main-range-now">Latest</button>
                </span>
              </span>
            </div>
            <div class="chart chart-tall" id="capture-main-chart"></div>
          </div>

          <!-- Capture spread -->
          <div class="card capture-card">
            <div class="card-head">
              <div><div class="card-title">Capture spread</div><div class="card-sub">Capture price minus baseload, EUR/MWh. Positive = profile captures premium; negative = discount (cannibalisation).</div></div>
              <button type="button" class="profiles-trigger" id="capture-spread-profiles-btn" aria-haspopup="true" aria-expanded="false">
                <span class="profiles-trigger-label" id="capture-spread-profiles-label">Profiles</span>
                <span class="profiles-trigger-caret">▾</span>
              </button>
              <div class="profiles-popover profiles-popover-right" id="capture-spread-profiles-pop" hidden></div>
            </div>
            <div class="chart-controls">
              <span class="label-control">Zone <div class="seg" id="capture-spread-zones"></div></span>
              <span class="label-control">Period <div class="seg" id="capture-spread-period"></div></span>
              <span class="label-control range-control">
                Range <div class="seg" id="capture-spread-range"></div>
                <span class="range-nav" id="capture-spread-range-nav">
                  <button type="button" class="range-arrow" id="capture-spread-range-prev" aria-label="Previous window">‹</button>
                  <span class="range-label" id="capture-spread-range-label">All time</span>
                  <button type="button" class="range-arrow" id="capture-spread-range-next" aria-label="Next window">›</button>
                  <button type="button" id="capture-spread-range-now">Latest</button>
                </span>
              </span>
            </div>
            <div class="chart chart-tall" id="capture-spread-chart"></div>
          </div>
        </div>

        <!-- Heatmap -->
        <div class="card capture-card">
          <div class="card-head">
            <div><div class="card-title">Hour × month heatmap</div><div class="card-sub">All-time mean spot price by hour of day &amp; month for the selected zone.</div></div>
          </div>
          <div class="chart-controls chart-controls-compact">
            <span class="label-control">Zone <div class="seg" id="capture-heatmap-zones"></div></span>
          </div>
          <div class="chart chart-tall" id="capture-heatmap"></div>
        </div>
      </div>
    </section>
```

**Förändringar:**
- `page-head` saknar `page-controls` (Zone/Period borttagna)
- Fristående Profiles-kortet borta
- Fristående `range-bar` borta
- Varje kort har `chart-controls`-block under card-head
- Varje main/spread-kort har `profiles-trigger` knapp + `profiles-popover` div i card-head
- Heatmap-kortet har bara Zone (klassen `chart-controls-compact` ger mindre padding)

**Step 2:** Sök i filen efter gamla DOM-IDs `capture-zones`, `capture-period`, `capture-range`, `capture-range-bar`, `capture-range-prev`, `capture-range-next`, `capture-range-now`, `capture-range-label`, `capture-range-nav`, `capture-profiles` — ska bara förekomma i JS (som behöver bytas i Task 6), inte i HTML-mallen.

```bash
grep -n "capture-zones\|capture-period\|capture-range\|capture-profiles" elpris/unified_dashboard_v3_html.py
```

Förväntat: JS-referenser kvar (de tas i Task 6), men inga HTML-träffar.

**Step 3:** Generera dashboard. Den kommer i detta läge att vara *trasig* — JS försöker fortfarande hitta gamla IDs som inte finns. Det är förväntat och OK.

```bash
python3 generate_unified_dashboard.py --preview
```

Förväntat: Python-output utan fel. JS-konsolen i preview kommer säga något i stil med `Cannot set properties of null (setting 'innerHTML')` när `renderCapture` försöker fylla `capture-zones`. Det är medvetet.

**Step 4:** Commit (intermediate, breaks UI med flit — alla efterföljande tasks fixar det).

```bash
git add elpris/unified_dashboard_v3_html.py
git commit -m "refactor(capture): ny HTML-struktur med per-kort kontroller

Tar bort globala page-controls, fristående Profiles-kort och range-bar.
Lägger in chart-controls + profiles-trigger i varje kort. JS följer i
nästa commits — Capture-fliken renderar fel mellan denna och Task 6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: CSS för chart-controls + profiles-popover

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` (CSS-block, lägg till efter `.range-bar`-blocket lines ~764)

**Step 1:** Lägg till nya CSS-regler. Hitta `.range-bar`-blocket (lines ~724-764), lägg de nya reglerna direkt efter:

```css
/* === Per-card chart controls (Capture) === */
.chart-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2) var(--sp-3);
  margin: 0 0 var(--sp-4) 0;
  padding: var(--sp-3) var(--sp-3) var(--sp-3) 0;
  border-bottom: 1px dashed var(--ink-5);
  padding-bottom: var(--sp-4);
}
.chart-controls .label-control { margin-right: var(--sp-2); }
.chart-controls .range-control { display: inline-flex; align-items: center; gap: var(--sp-2); flex-wrap: wrap; }
.chart-controls .range-nav { margin-left: var(--sp-2); }
.chart-controls-compact { padding: var(--sp-2) 0; }

/* Profiles trigger button (in card-head, top-right) */
.profiles-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: var(--radius-pill);
  background: var(--surface-sunken);
  color: var(--ink-2);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1px solid transparent;
  transition: background var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease);
  cursor: pointer;
}
.profiles-trigger:hover { background: var(--surface-base); border-color: var(--ink-5); }
.profiles-trigger[aria-expanded="true"] { background: var(--surface-raised); border-color: var(--ink-4); }
.profiles-trigger-caret { font-size: 10px; opacity: 0.7; }

/* Profiles popover panel */
.profiles-popover {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 50;
  min-width: 280px;
  max-width: 360px;
  padding: var(--sp-4);
  background: var(--surface-raised);
  border: 1px solid var(--ink-5);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-pop, 0 8px 24px rgba(0,0,0,0.12));
}
.profiles-popover[hidden] { display: none; }
.profiles-popover-right { right: 0; left: auto; }

/* Ensure card-head can host an absolutely-positioned popover */
.capture-card .card-head { position: relative; }
```

**Step 2:** Generera dashboard och reload preview. Capture-fliken är fortfarande trasig (JS inte uppdaterad), men CSS-block ska ge inga konsolfel.

```bash
python3 generate_unified_dashboard.py --preview
```

Reload, kolla preview_console_logs() — om felmeddelanden kommer från CSS (`unknown property` el. dyl.), åtgärda.

**Step 3:** Commit.

```bash
git add elpris/unified_dashboard_v3_html.py
git commit -m "style(capture): CSS för chart-controls + profiles-popover

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Bygg + wire per-kort kontroller (zone/period/range/nav)

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` (JS-block)

**Mål:** Skriv en gemensam `wireCaptureCard(opts)` som monterar zone/period/range/range-nav chips för ett kort, binder klick-handlers och kallar render-funktionen vid ändring. Kalla den tre gånger från `renderCapture()` (en gång per state-block).

**Step 1:** Lägg till en ny funktion `wireCaptureCard` i JS-blocket, i närheten av `renderCaptureRangeBar` (som ska tas bort i Task 9). Skriv den ovanför `renderCaptureRangeBar`:

```javascript
/**
 * Mount per-chart controls (zone, period, range, range-nav) for a Capture card.
 *
 * opts = {
 *   prefix:    'capture-main' | 'capture-spread' | 'capture-heatmap',
 *   state:     CAPTURE_STATES.main (etc),
 *   controls:  { zone: true, period: bool, range: bool },
 *   render:    function() { renderCaptureChart(state); ... } // re-render this card's chart
 * }
 */
function wireCaptureCard(opts) {
    var p = opts.prefix;
    var state = opts.state;
    var controls = opts.controls || { zone: true };

    // --- Zone chips ---
    var zones = (DATA.zones || []);
    if (!zones.length) return;
    if (!state.zone || zones.indexOf(state.zone) === -1) state.zone = zones[0];
    var zoneEl = el(p + '-zones');
    if (zoneEl) {
        zoneEl.innerHTML = zones.map(function(z) {
            return '<button type="button" data-zone="' + htmlEsc(z) + '" aria-pressed="' + (z === state.zone) + '">' + htmlEsc(z) + '</button>';
        }).join('');
        zoneEl.querySelectorAll('button').forEach(function(b) {
            b.onclick = function() {
                state.zone = b.dataset.zone;
                wireCaptureCard(opts);   // re-render chips
                opts.render();           // re-render chart
            };
        });
    }

    // --- Period chips ---
    if (controls.period) {
        var periodEl = el(p + '-period');
        if (periodEl) {
            periodEl.innerHTML = ['yearly','monthly','daily'].map(function(per) {
                return '<button type="button" data-period="' + per + '" aria-pressed="' + (per === state.period) + '">' + per + '</button>';
            }).join('');
            periodEl.querySelectorAll('button').forEach(function(b) {
                b.onclick = function() {
                    state.period = b.dataset.period;
                    state.rangeEnd = null;
                    wireCaptureCard(opts);
                    opts.render();
                };
            });
        }
    }

    // --- Range chips + nav ---
    if (controls.range) {
        var rangeEl = el(p + '-range');
        var opts2 = CAPTURE_RANGE_OPTIONS[state.period] || ['all'];
        if (opts2.indexOf(state.range) === -1) { state.range = 'all'; state.rangeEnd = null; }
        if (rangeEl) {
            rangeEl.innerHTML = opts2.map(function(r) {
                return '<button type="button" data-range="' + r + '" aria-pressed="' + (r === state.range) + '">' + CAPTURE_RANGE_LABELS[r] + '</button>';
            }).join('');
            rangeEl.querySelectorAll('button').forEach(function(b) {
                b.onclick = function() {
                    state.range = b.dataset.range;
                    state.rangeEnd = null;
                    wireCaptureCard(opts);
                    opts.render();
                };
            });
        }

        var win = captureCurrentWindow(state);
        var nav = el(p + '-range-nav');
        var prevBtn = el(p + '-range-prev');
        var nextBtn = el(p + '-range-next');
        var nowBtn  = el(p + '-range-now');
        var labelEl = el(p + '-range-label');
        if (nav) {
            if (!win) {
                nav.style.visibility = 'hidden';
                if (labelEl) labelEl.textContent = 'All time';
            } else {
                nav.style.visibility = 'visible';
                if (labelEl) labelEl.textContent = captureWindowLabel(win) + (win.atLatest ? ' · latest' : '');
                if (prevBtn) prevBtn.onclick = function() { captureNavRange(state, -1); wireCaptureCard(opts); opts.render(); };
                if (nextBtn) nextBtn.onclick = function() { captureNavRange(state, +1); wireCaptureCard(opts); opts.render(); };
                if (nowBtn)  nowBtn.onclick  = function() { state.rangeEnd = null; wireCaptureCard(opts); opts.render(); };
                if (nextBtn) nextBtn.disabled = !!win.atLatest;
                if (nowBtn)  nowBtn.disabled  = !!win.atLatest;
            }
        }
    }
}
```

**Step 2:** Refaktorera `renderCapture()` (lines ~1580–1644) helt. Den nya versionen:

```javascript
function renderCapture() {
    var zones = (DATA.zones || []);
    if (!zones.length) {
        el('capture-content').innerHTML = '<div class="empty-note">No spot price data available.</div>';
        return;
    }

    var mainOpts = {
        prefix: 'capture-main',
        state: CAPTURE_STATES.main,
        controls: { zone: true, period: true, range: true },
        render: function() {
            renderCaptureChart(CAPTURE_STATES.main);
            renderCaptureKPIs(CAPTURE_STATES.main);  // KPI follows main
        },
    };
    var spreadOpts = {
        prefix: 'capture-spread',
        state: CAPTURE_STATES.spread,
        controls: { zone: true, period: true, range: true },
        render: function() { renderCaptureSpreadChart(CAPTURE_STATES.spread); },
    };
    var heatmapOpts = {
        prefix: 'capture-heatmap',
        state: CAPTURE_STATES.heatmap,
        controls: { zone: true },
        render: function() { renderHeatmap(CAPTURE_STATES.heatmap); },
    };

    wireCaptureCard(mainOpts);
    wireCaptureCard(spreadOpts);
    wireCaptureCard(heatmapOpts);

    wireProfilesPopover(mainOpts);     // see Task 7
    wireProfilesPopover(spreadOpts);   // see Task 7

    // Initial render of all three charts + KPI
    renderCaptureChart(CAPTURE_STATES.main);
    renderCaptureSpreadChart(CAPTURE_STATES.spread);
    renderHeatmap(CAPTURE_STATES.heatmap);
    renderCaptureKPIs(CAPTURE_STATES.main);
}
```

**Notera:** `wireProfilesPopover` definieras i Task 7. För att inte bryta `renderCapture` i Task 6 commit, lägg in en placeholder:

```javascript
function wireProfilesPopover(opts) { /* defined in Task 7 */ }
```

i samma fil ovan `wireCaptureCard`.

**Step 3:** Generera dashboard. Profiles-knapparna fungerar inte än, men Zone/Period/Range ska fungera per kort.

```bash
python3 generate_unified_dashboard.py --preview
```

Reload preview, klicka:
- SE4 i main-kortet → bara main-grafen ska byta
- Yearly i spread-kortet → bara spread-grafen ska byta
- 5Y i main-kortet → bara main-grafen ska byta
- Zone i heatmap-kortet → bara heatmap

```
preview_eval('document.querySelector("#capture-main-zones button[data-zone=\\"SE4\\"]").click(); "clicked"')
preview_screenshot()
```

**Step 4:** Verifiera att Profiles fortfarande visar något (även om popovern inte är funktionell ännu, någon form av init bör hända). Det är OK om popovern är trasig.

**Step 5:** Commit.

```bash
git add elpris/unified_dashboard_v3_html.py
git commit -m "feat(capture): per-kort wire för zone/period/range

wireCaptureCard monterar och binder chips för ett kort. renderCapture
kallar den för main, spread och heatmap. Klick på SE4 i main ändrar
bara main-grafen. Profiles-popover följer i nästa commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Profiles-popover

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` (JS-block)

**Step 1:** Skriv `wireProfilesPopover` (ersätt placeholder från Task 6):

```javascript
function wireProfilesPopover(opts) {
    var p = opts.prefix;
    var state = opts.state;
    var btn = el(p + '-profiles-btn');
    var pop = el(p + '-profiles-pop');
    var labelSpan = el(p + '-profiles-label');
    if (!btn || !pop) return;

    function render() {
        // Update label e.g. "Sol Syd, Vind +1"
        if (labelSpan) {
            if (!state.profiles.length) {
                labelSpan.textContent = 'Profiles';
            } else {
                var names = state.profiles.map(function(k) { return (DATA.profiles && DATA.profiles[k]) || k; });
                var label = names.slice(0, 2).join(', ');
                if (names.length > 2) label += ' +' + (names.length - 2);
                labelSpan.textContent = label;
            }
        }
        // Build popover content
        var availableProfiles = Object.keys((DATA.data && DATA.data[state.zone]) || {});
        var groupsHtml = CAPTURE_PROFILE_GROUPS.map(function(g) {
            var present = g.keys.filter(function(k) { return availableProfiles.indexOf(k) !== -1; });
            if (!present.length) return '';
            var btns = present.map(function(k) {
                var lbl = (DATA.profiles && DATA.profiles[k]) || k;
                var sel = state.profiles.indexOf(k) !== -1;
                var color = profileColor(k) || '#999';
                return '<button type="button" class="profile-chip" data-key="' + htmlEsc(k) + '" aria-pressed="' + sel + '" ' +
                    'style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:999px;border:1px solid var(--ink-5);background:' + (sel ? 'var(--surface-sunken)' : 'transparent') + ';font-size:var(--fs-xs);font-weight:600;color:var(--ink-1);letter-spacing:0.04em;margin:0 4px 4px 0">' +
                    '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + htmlEsc(color) + '"></span>' +
                    htmlEsc(lbl) + '</button>';
            }).join('');
            return '<div style="margin-bottom:8px"><span class="eyebrow" style="margin-right:10px">' + htmlEsc(g.label) + '</span>' + btns + '</div>';
        }).join('');
        pop.innerHTML = groupsHtml || '<span class="muted">No profiles available.</span>';
        pop.querySelectorAll('.profile-chip').forEach(function(chipBtn) {
            chipBtn.onclick = function() {
                var k = chipBtn.dataset.key;
                var idx = state.profiles.indexOf(k);
                if (idx === -1) state.profiles.push(k);
                else state.profiles.splice(idx, 1);
                render();
                opts.render();   // re-render chart
            };
        });
    }

    function open()  { pop.hidden = false; btn.setAttribute('aria-expanded', 'true');  render(); }
    function close() { pop.hidden = true;  btn.setAttribute('aria-expanded', 'false'); }

    btn.onclick = function(e) {
        e.stopPropagation();
        if (pop.hidden) open(); else close();
    };

    // Close on outside click + Escape — registered once per popover
    document.addEventListener('click', function(e) {
        if (!pop.hidden && !pop.contains(e.target) && e.target !== btn && !btn.contains(e.target)) close();
    });
    document.addEventListener('keydown', function(e) { if (e.key === 'Escape' && !pop.hidden) close(); });

    render();   // initial label + popover content
}
```

**Step 2:** Generera + reload. Klick på Profiles-knappen ska visa/dölja popovern. Klick på en profil-chip ska toggla och uppdatera grafen.

```bash
python3 generate_unified_dashboard.py --preview
```

```
preview_eval('document.querySelector("#capture-main-profiles-btn").click(); "clicked"')
preview_screenshot()  # popover ska vara synlig
preview_eval('document.querySelector("#capture-main-profiles-pop button[data-key=\\"sol_syd\\"]").click(); "toggled"')
preview_screenshot()  # graf ska uppdateras
preview_eval('document.body.click(); "clicked outside"')
preview_screenshot()  # popover ska vara stängd
```

**Step 3:** Testa spread-popovern (höger kortet) — den ska öppnas mot vänster, inte klippas av sidkanten.

**Step 4:** Commit.

```bash
git add elpris/unified_dashboard_v3_html.py
git commit -m "feat(capture): profiles-popover per kort

Klick på Profiles-knappen öppnar/stänger en popover med teknik-toggles.
Click outside + Escape stänger. Toggla en profil uppdaterar bara den
egna grafen.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Säkerställ KPI-strip följer main

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py` (just verify — gjordes redan i Task 6)

**Step 1:** Bekräfta i `renderCapture` (Task 6 Step 2) att `renderCaptureKPIs(CAPTURE_STATES.main)` kallas, och att `mainOpts.render` inkluderar `renderCaptureKPIs(CAPTURE_STATES.main)`. Då uppdateras KPI:erna när main ändras, men inte när spread/heatmap ändras.

**Step 2:** Verifiera i preview:
- Klick på SE4 i main → KPI-tilen byter till "Latest baseload · SE4"
- Klick på SE4 i spread → KPI förblir på main-zonen (SE3 om main inte ändrats)

```
preview_eval('document.querySelector("#capture-main-zones button[data-zone=\\"SE4\\"]").click(); "clicked"')
preview_eval('document.querySelector("#capture-kpis").innerText')
# expect: contains "SE4"

preview_eval('document.querySelector("#capture-spread-zones button[data-zone=\\"SE1\\"]").click(); "clicked"')
preview_eval('document.querySelector("#capture-kpis").innerText')
# expect: STILL contains "SE4" (main unchanged), not "SE1"
```

**Step 3:** Om något inte stämmer, fixa och commit.

---

## Task 9: Cleanup — ta bort gamla globala funktioner och alias

**Files:**
- Modify: `elpris/unified_dashboard_v3_html.py`

**Step 1:** Ta bort gamla funktioner som inte längre används:

- `renderCaptureRangeBar()` — ersatt av `wireCaptureCard`
- `CAPTURE_STATE`-aliaset (`var CAPTURE_STATE = CAPTURE_STATES.main;`) — ta bort om inget annat refererar till den
- Eventuella kvarvarande referenser till `capture-zones`, `capture-period`, `capture-range`, `capture-range-bar`, `capture-range-prev/next/now/label/nav`, `capture-profiles` (utan prefix). Dessa IDs finns inte längre i HTML — JS-refer till dem är döda referenser.

**Step 2:** Sök efter dead code:

```bash
grep -n "renderCaptureRangeBar\|'capture-zones'\|'capture-period'\|'capture-range'\|'capture-range-bar'\|'capture-range-prev'\|'capture-range-next'\|'capture-range-now'\|'capture-range-label'\|'capture-range-nav'\|'capture-profiles'" elpris/unified_dashboard_v3_html.py
```

Förväntat: inga JS-träffar utöver `capture-main-*`, `capture-spread-*`, `capture-heatmap-*`.

**Step 3:** Kör generate + reload + full klick-test:

```bash
python3 generate_unified_dashboard.py --preview
```

```
preview_eval('window.location.reload(); "ok"')
preview_console_logs()  # tomt på fel
preview_eval('document.querySelectorAll("#page-capture button").length')  # antal knappar
preview_screenshot()
```

**Step 4:** Commit.

```bash
git add elpris/unified_dashboard_v3_html.py
git commit -m "chore(capture): ta bort död kod (gamla globala kontroller)

renderCaptureRangeBar och CAPTURE_STATE-aliaset borttagna. Inga JS-refer
till capture-zones/capture-period/capture-range/capture-profiles utan
graf-prefix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Verifiering enligt acceptanskriterier

**Files:** Inga ändringar (bara verifiering).

**Step 1:** Generera dashboard från scratch och öppna i preview.

```bash
python3 generate_unified_dashboard.py --preview
```

**Step 2:** Gå igenom acceptanskriterierna från designdokumentet:

1. **Page-head har bara title + subtitle, inga kontroller.**
   ```
   preview_eval('!!document.querySelector("#page-capture .page-controls")')
   # expect: false
   ```

2. **Fristående Profiles-kort + range-bar är borta.**
   ```
   preview_eval('!!document.getElementById("capture-profiles") || !!document.getElementById("capture-range-bar")')
   # expect: false
   ```

3. **Main + spread har egen Zone + Period + Range + range-nav + profiles-popover. Heatmap bara Zone.**
   ```
   preview_eval('[!!document.getElementById("capture-main-zones"), !!document.getElementById("capture-main-period"), !!document.getElementById("capture-main-range"), !!document.getElementById("capture-main-range-nav"), !!document.getElementById("capture-main-profiles-btn"), !!document.getElementById("capture-spread-zones"), !!document.getElementById("capture-spread-profiles-btn"), !!document.getElementById("capture-heatmap-zones"), !document.getElementById("capture-heatmap-period")].every(Boolean)')
   # expect: true
   ```

4. **Klick på SE4 i main påverkar bara main.**
   Klick på SE4 i main-kortet. Inspektera `CAPTURE_STATES.main.zone === 'SE4'` och `CAPTURE_STATES.spread.zone !== 'SE4'`.
   ```
   preview_eval('document.querySelector("#capture-main-zones button[data-zone=\\"SE4\\"]").click(); JSON.stringify({main: CAPTURE_STATES.main.zone, spread: CAPTURE_STATES.spread.zone, heatmap: CAPTURE_STATES.heatmap.zone})')
   # expect: {"main":"SE4","spread":"SE3","heatmap":"SE3"}
   ```

5. **Profiles-popover öppnas/stängs på klick + Escape.**
   ```
   preview_eval('document.querySelector("#capture-main-profiles-btn").click(); !document.getElementById("capture-main-profiles-pop").hidden')
   # expect: true
   preview_eval('document.dispatchEvent(new KeyboardEvent("keydown", {key:"Escape"})); document.getElementById("capture-main-profiles-pop").hidden')
   # expect: true
   ```

6. **Defaults — Reload preview och inspektera state.**
   ```
   preview_eval('window.location.reload(); "ok"')
   # wait a moment
   preview_eval('JSON.stringify(CAPTURE_STATES)')
   # expect: main + spread have period:"monthly", range:"all", profiles:["baseload","sol_syd"]
   ```

7. **Generate utan fel.** (Already proven by `--preview` not erroring.)

8. **Ingen JS-konsolfel.**
   ```
   preview_console_logs()
   # expect: no error entries from Capture
   ```

**Step 3:** Screenshots för proof.

```
preview_eval('window.location.hash = "#capture"; window.scrollTo(0, 0); "ok"')
preview_screenshot()  # before — default view

preview_eval('document.querySelector("#capture-main-zones button[data-zone=\\"SE4\\"]").click(); "clicked"')
preview_eval('document.querySelector("#capture-main-period button[data-period=\\"yearly\\"]").click(); "clicked"')
preview_screenshot()  # after — main is SE4 yearly, spread is SE3 monthly
```

**Step 4:** Om allt OK — skapa final commit och pull request.

```bash
git log --oneline capture-per-chart-controls
# inspect: list of commits

# Push branch
git push -u origin capture-per-chart-controls

# Open PR
gh pr create --base main --head capture-per-chart-controls \
  --title "Capture-fliken: per-graf kontroller (Zone/Period/Range/Profiles)" \
  --body "$(cat <<'BODY'
Flyttar globala Zone/Period/Range-kontroller och fristående Profiles-kort
från sidhuvudet in i varje graf på Capture-fliken i unified dashboard.

**Beteende:**
- Varje graf (Price evolution, Capture spread, Hour × month heatmap) har
  oberoende state. Klick på SE4 i main-grafen påverkar inte spread.
- Heatmapen har bara Zone-väljare (period/range gäller inte för all-time
  hour × month-aggregat).
- Profiles bakom kompakt popover per graf (open/close på knappklick +
  click-outside + Escape).
- KPI-strip följer main-grafens state.

**Out of scope:**
- URL-hash sync för per-graf state (v2).
- Heatmap Period/Range.
- BESS / FUTURES / ASSETS-flikar.

Design: docs/plans/2026-05-13-capture-per-chart-controls-design.md
Plan:   docs/plans/2026-05-13-capture-per-chart-controls-plan.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)"
```

(Fråga användaren först innan push + PR.)

---

## Risker att vara uppmärksam på under exekvering

- **Mellan Task 4 och Task 6** är dashboarden trasig (HTML uppdaterad, JS inte). Det är medvetet men inget att panika över.
- **Plotly.react** kan ge en tom div första gången om data tar tid att binda. Om grafer inte ritas, kolla preview_console_logs efter `Plotly is not defined` (CDN-issue) eller saknade `DATA`-nycklar.
- **Profiles-popover positioning:** Spread-kortet ligger till höger i grid-2. `.profiles-popover-right { right: 0 }` ska räcka; om popovern klipps utanför, justera till `right: 0; left: auto` och kontrollera `position: relative` på `.card-head`.
- **Helper-funktion call-sites:** Task 1 ändrar signatur på `captureLatestDateMs/captureCurrentWindow/captureNavRange`. Grep efter alla anrop och uppdatera; om någon missas bryter dashboarden.

---

## Sammanfattning av commits

1. `refactor(capture): helpers tar state-parameter`
2. `refactor(capture): render-funktioner tar state-parameter`
3. `refactor(capture): per-graf state-container CAPTURE_STATES`
4. `refactor(capture): ny HTML-struktur med per-kort kontroller`
5. `style(capture): CSS för chart-controls + profiles-popover`
6. `feat(capture): per-kort wire för zone/period/range`
7. `feat(capture): profiles-popover per kort`
8. (verifiering — ingen commit om allt redan klart)
9. `chore(capture): ta bort död kod (gamla globala kontroller)`
10. (verifiering + PR — ingen ny commit)

Tio task, ~7 logiska commits. Varje commit lämnar repo i ett konsistent eller medvetet-trasigt state.
