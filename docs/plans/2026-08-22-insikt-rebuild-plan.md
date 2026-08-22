# Insikt Rebuild — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Spec: `2026-08-22-insikt-produkt-spec.md` är domaren vid scope-frågor.

**Goal:** Bygga produkten "Insikt" (slutsats-först-dashboard + daglig puls + investerarexport) funktion för funktion ovanpå befintlig datapipeline, med trovärdig budgetgrund som steg 0.

**Architecture:** Nytt namespace `elpris/insikt/` som importerar befintliga loaders (`unified_dashboard_data`, `operations_dashboard_data`, `park_config`, m.fl.). Varje feature = data-modul + insiktsgenerator + renderarsektion. Gamla dashboards lämnas orörda tills ersatta.

**Tech Stack:** Python 3 stdlib (som övriga repot), Plotly via CDN i HTML, pytest.

**Delegering:** Varje våg körs av subagenter. Modell/effort per task anges nedan. Fable (huvudloop) skriver task-briefs, granskar diffar mellan vågor, kör validering (pytest + browser via Playwright) och committar. AI-commits hålls separata från ocommittade data-CSV:er (rör dem aldrig).

---

## Våg 1 — parallella, oberoende (inga delade filer)

### Task 1A: Futures-historikräddning (opus, high)
**Design:** `docs/plans/2026-05-03-futures-historical-tracking-design.md`, MEN: rendering-stegen (1, 3) i den designen SKIPPAS — visualiseringen byggs senare i Insikt steg 3/5, inte i unified. Implementeras: datalager + status-varningar + backfill-experiment.
- Modify: `elpris/dashboard_v2_data.py` (`load_forward_curve_data` → `forward_history`, `forward_health` enligt designens JSON-schema)
- Modify: `status.py` (pre-expiry-varning, post-expiry-granskning)
- Modify: `elpris/nasdaq.py` + `nasdaq_download.py` (`--backfill-expired`-experiment: testa om `instruments/{orderbookId}/price-history` ger data för delistade kontrakt; om ja, kör backfill en gång; om nej, dokumentera och behåll flaggan borttagen)
- Test: `tests/test_nasdaq.py` + ny `tests/test_forward_history.py` (parsning av delivery-perioder, `is_clean_final`, T-Xmo-fönsterlogik om den hjälpfunktionen skapas här)
- Validering: JSON-storleksökning < 200 KB; pytest grönt.
- Commit: `feat(futures): forward_history + forward_health datalager, expiry-varningar i status.py`

### Task 1B: PVsyst-månadsbudget från SharePoint (opus, high)
**Underlag:** `docs/plans/2026-04-10-cowork-monthly-budget-prompt.md` (filnamn, sökvägar, sanity-checks).
- Hämta de 8 SRC Forecast-PDF:erna via SharePoint MCP (`sharepoint_search`/`folder_search`, ladda ner), Hova finns även lokalt i `Resultat/sol-kalldata/`.
- Extrahera månadstabell (E_Grid, GlobInc, PR) per park med PDF-verktygen. OBS enhetskontroller enligt underlaget.
- Sanity per park: Σmånader ≈ årsyield×kapacitet ±2 %; energiviktat PR-medel ≈ års-PR; irradiation-total ≈ årsvärde. Avvikelser rapporteras, gissas inte bort.
- Modify: `elpris/park_config.py` → fyll `PARK_BUDGET_OVERRIDES` (nycklar "2026-01".."2026-12"; källkommentar per park med PDF-namn + simuleringsår). Lägg även `PARK_DEGRADATION_PCT_PER_YEAR = 0.5` som konstant + kommentar om COD-år-hantering (används i våg 2).
- Test: `tests/test_config.py`-tillägg: overrides kompletta (8 parker × 12 mån), värden inom rimliga spann, Σ≈årsbudget.
- Commit: `data: fyll PARK_BUDGET_OVERRIDES med månatliga PVsyst-värden (8 parker)`
- Fallback om SharePoint-access saknar filerna: extrahera Hova lokalt, rapportera vilka som saknas — commit blir partiell och flaggas i rapporten till Pontus.

### Task 1C: Lufttemperatur per park (opus, medium)
Väderstationerna saknar temperatur (`ghi,wind_speed,humidity`).
- Steg 1: proba Bazefield efter temperaturpunkt (t.ex. `AmbientTemp`/`TempAir`) via samma API som `discover_inverters.py`. Om punkt finns: utöka `WEATHER_POINTS` + inkrementell sync.
- Steg 2 (fallback/komplement): Open-Meteo ERA5 archive-API (gratis, ingen nyckel): timvis `temperature_2m` per parkkoordinat. Koordinater: geocoda parkens ort (`park_config` platsinfo) via Open-Meteo geocoding; hårdkoda resultatet i `elpris/park_config.py` som `PARK_COORDS` (lat/lon, källkommentar) efter rimlighetskontroll mot zon.
- Create: `elpris/temperature.py` (nedladdning + lagring `Resultat/marknadsdata/temperatur/{park}.csv`, timupplösning, loader-API `load_park_temperature(park, start, end)`)
- Create: `temperature_download.py` CLI + inkoppling i `update_all.py` som eget steg.
- Test: `tests/test_temperature.py` (parsning, inkrementell merge, loader).
- Commit: `feat(weather): lufttemperatur per park (Bazefield-punkt eller Open-Meteo ERA5)`

## Våg 2 — trovärdig grund i rapportberäkningarna (kräver 1B+1C)

### Task 2A: Temperaturkorrigerad PR + uppdelad förlustkaskad (fable, high)
- Modify: `elpris/performance_report_data.py`:
  - Ersätt hårdkodad 10 °C: modultemp per 15-min = `T_amb(t) + 0.03 × POA(t)` med riktig temperatur (interp. tim→kvart).
  - `temperature_loss_mwh`: gamma-koefficient (−0.34 %/°C default, per-park om PVsyst-PDF ger den) × (T_mod − 25 °C) × energi, aggregerat.
  - `clipping_loss_mwh`: beräknad ur `PARK_EXPORT_LIMIT` (intervall där inverter-DC-potential > exportgräns).
  - Residualen döps om (`residual_loss_mwh`, rubrik "Övrigt (soiling, modellfel, curtailment)") — fältnamnet `curtailment_loss_mwh` får inte längre ljuga.
  - Degradering: budget skalas `(1 − 0.005)^(år − PVsyst-basår)` via konstant från 1B.
- Modify: `elpris/performance_report_html.py` (waterfall får nya staplar).
- Test: utöka `tests/test_performance_report_data.py` med syntetiska fall (känd temp → känd förlust; exportgräns → känd clipping; residual = totalgap − delkomponenter).
- Validering: generera om 2026-06/2026-07-rapporter för alla parker, jämför kaskadsummor före/efter (total förlust oförändrad, bara uppdelad), browser-check en rapport.
- Commit: `feat(reports): temperaturkorrigerad PR, clipping/temp-förlust separerade ur residualen, degradering i budget`

## Våg 3 — Insikt steg 1: Parköversikt (flaggskeppet)

### Task 3A: Datamodul + insiktsgenerator (fable, high)
- Create: `elpris/insikt/__init__.py`, `elpris/insikt/parkoversikt.py`
- Komponerar per park (senaste stängda månad + MTD + 13 mån historik) ur `unified_dashboard_data`-byggstenarna: energi vs budget, PR vs budget-PR, tillgänglighet, förlustkaskad, intäkt (spot+PPA), specifik yield.
- Insiktsgenerator per park (mallbaserad, ingen hårdkodning av park/zon): status (över/i linje/under budget), dominerande orsak (väder / tillgänglighet / temperatur / övrigt) härledd ur kaskaden, trendflagga (3 mån glidande vs budget). Portföljsammanfattning överst.
- Test: `tests/test_insikt_parkoversikt.py` — syntetisk park-månad med känd kaskad ger förväntad orsaksmening; tone-logik.
### Task 3B: Renderare (fable, high — frontend-design-skillen läses av agenten)
- Create: `elpris/insikt/render.py` + `generate_insikt.py`
- Layout: portfölj-hero (klartext + 3 nyckeltal) → league table (sorterbar: vs budget, PR-gap, yield) → parkkort-grid med insiktsmening + sparkline → drilldown per park (kaskad-waterfall, 13-mån stapel). Nordic Clarity-designspråk, IntersectionObserver-lazy-render, inline-JSON endast för det som ritas.
- Validering: `python3 generate_insikt.py`, http.server + Playwright: screenshots desktop+mobil, konsolfel = 0, siffror stickprovas mot `performance_report_data`-värden för 2 parker.
- Commit: `feat(insikt): parköversikt — league table + parkkort med klartextinsikter`

## Våg 4 — Insikt steg 2: Daglig puls

### Task 4A: Detektorer + digest (opus, high; detektionsregler specas av Fable i task-briefen)
- Create: `elpris/insikt/puls.py` + `generate_puls.py`
- Detektorer (per gårdagens data): (1) inverter ≥X % under parkmedian N dagar i rad (data: `inverters/{park}_daily_yield.csv`), (2) stuck/saknad mätarsignal, (3) park-PR > 2σ under 30-dagars väderkorrigerat medel, (4) nya alarmtyper/alarmstorm vs baseline, (5) datakvalitet (källor som inte uppdaterats). Trösklar i konstanter, testbara.
- Output: kort HTML-digest + terminalrad; tom dag ⇒ "inga avvikelser" (en rad, ingen rapport-spam).
- Inkoppling: eget steg sist i `update_all.py` (efter data-sync).
- Test: `tests/test_insikt_puls.py` — syntetiska serier triggar/inte triggar varje detektor.
- Commit: `feat(insikt): daglig puls — avvikelsedetektion + digest i update_all`

## Våg 5 — Insikt steg 3: Intäkt & marknad

### Task 5A: Realiserad obalanskostnad (fable, high)
- Create: `elpris/insikt/obalans.py`: prognosproxy per park (a: persistens D-1 samma kvart, b: budgetform-skalning), fel × (obalanspris − spot) per 15-min → EUR per park/månad, båda proxies redovisas (spann, inte falsk precision).
- Test: syntetiskt fall med känt fel och kända priser.
### Task 5B: Kannibaliseringskoefficient (opus, medium)
- Create: `elpris/insikt/kannibalisering.py`: OLS ratio ~ installerad GW per zon (år 2020+), koefficient "+1 GW → −X p.e. ratio", R², extrapolering 2 år med osäkerhetsband. Stdlib-OLS (ingen numpy-dependency om repot saknar den).
### Task 5C: Sektion i Insikt-dashboarden (fable, high)
- Modify: `elpris/insikt/render.py` + ny `elpris/insikt/marknad.py`: capture/PPA-bok (från befintliga byggstenar), obalanskostnad, kannibalisering, forward-läge (från Task 1A:s `forward_history`: konvergensgraf + lookback-tabell — designens kort A+B landar här i stället för i unified).
- Validering: browser + stickprov; insiktsmeningar per delfråga.
- Commit: `feat(insikt): intäkt & marknad — obalanskostnad, kannibaliseringskoefficient, forward-konvergens`

## Våg 6 — Insikt steg 4: BESS/capex-beslutsstöd

### Task 6A: Revenue stacking-DP (fable, xhigh)
- Create: `elpris/insikt/bess_stack.py`: timvis DP där batteriet per timme väljer (arbitrage-ladda/urladda/idle) ELLER reserverar kapacitet till bästa ancillary-produkt (FCR-D upp/ned, aFRR) med SoC-krav för reserven; cykelkostnad EUR/MWh throughput; jämförelse mot dagens separata tak. BTM-varianten körs mot faktiska parkprofiler (`effective_power_mw`), inte TMY.
- Antaganden dokumenteras i modulens docstring + i UI (perfect foresight kvarstår → "övre gräns", bid-acceptans = parameter).
- Test: syntetiska prisdagar med kända optimala val; stackad intäkt ≥ max(separata strömmar) − ε; cykelkostnad minskar antalet cykler.
### Task 6B: Capex-kalkyl + sektion (opus, high)
- IRR (Newton på kassaflöden) + NPV/payback, per zon × duration × storlek; sektion i render med insiktsmening ("bästa business case idag: X").
- Commit: `feat(insikt): BESS revenue stacking + capex-kalkyl med IRR`

## Våg 7 — Insikt steg 5: Investerarexport

### Task 7A (opus, high): `generate_investor_report.py` → kurerad månads-HTML (+ utskriftsvänlig CSS för PDF) ur insikt-datamodulerna: portfölj-KPI, vs budget, intäkt, PPA-läge, marknadskontext. Ingen ny analys — bara kurering.
- Commit: `feat(insikt): investerarrapport (kurerad månadsexport)`

## Löpande regler

- **Rör aldrig** de ocommittade data-CSV:erna i `Resultat/` (Pontus WIP) — committa bara kod/docs/tester.
- pytest hela sviten efter varje våg; browser-verifiering för allt användarsynligt.
- Fable granskar varje tasks diff innan commit (subagent-driven development).
- Rivning (gamla flikar/sektioner) görs FÖRST efter Pontus feedback på första utkastet — inget raderas i detta pass.

## Öppna frågor till Pontus (blockerar inte första utkastet)

1. Namnet "Insikt" — OK eller annat?
2. Rivningstakt: när steg 1 är godkänt — ta bort ASSETS-fliken + månadsrapportens överlapp?
3. Investerarrapportens exakta KPI-lista (första utkastet gissar utifrån spec-målen).
