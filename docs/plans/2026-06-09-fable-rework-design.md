# Fable Rework — Portfölj- & marknadsrapport (blankt blad)

**Datum:** 2026-06-09
**Branch:** `fable-rework-dashboard`
**Status:** Design → implementation i samma branch

## Uppdrag

Blankt-blad-omtag av analys- och presentationslagret, byggt parallellt med
(inte i stället för) Track C-dashboarden och månadsrapporterna. Två publiker
ska betjänas i samma dokument:

1. **Investerare/ledning** — polerad portföljöversikt, trender, slutsatser i
   klartext. Förtroendeingivande, läsbar uppifrån och ner som en rapport.
2. **Asset management/ops** — djup per park: yield, PR, budgetavvikelse,
   capture, negativpris-exponering, datakvalitet. Åtgärdbara siffror.

Designprincip: **översikt först, djup på begäran**. Dokumentet läses linjärt
som en berättelse (marknad → capture → portfölj → risk), med drill-down via
parkväljare i stället för att allt renderas samtidigt.

## Vad datainventeringen visade (urval)

| Källa | Täckning | Notering |
|-------|----------|----------|
| Spot quarterly | 2021-11 → 2026-05-22 | 15-min äkta från 2025-10 |
| Bazefield parker | ~2024-08 → 2026-06-02 | 15-min, POA, availability |
| ENTSO-E generation | 2015/2021 → 2026 | solar/vind/hydro/kärnkraft per zon |
| Energimyndigheten sol | 2016–2024, per län | län→zon-mappning krävs |
| Energimyndigheten vind | 2004–2024, per elområde | direkt användbar |
| Nasdaq futures | → 2026-04-29 | SYS + EPAD per zon |
| eSett obalans | 2023-05 → 2026-06-02 | **används inte i någon befintlig vy** |
| PVsyst-profiler | TMY | south_lundby, ew_boda, tracker_sweden |

Berättelsen som datat bär på (validerad med prober):

- **Spotpris SE3 per år:** 130 € (2021) → 36 € (2024) → 78 € (2026 YTD).
  Energikris → normalisering → återhämtning.
- **Negativa timmar SE3:** 0 (2021) → 652 h (2024) → 344 h (2025) → 34 h
  (2026 t.o.m. maj). Solens egen prispress, nu delvis absorberad.
- **Capture ratio sol syd SE3:** 1.07 (2021) → 0.66 (2025) medan installerad
  sol i SE3 gick 0.2 → 6.3 GW (2016–2024). Cannibaliseringskurvan i ett blad.
- **Intradagsspread** (duck curve): kollapsade efter 2022 (144→30 €), växer
  igen (44 € 2026) — flexvärde på väg tillbaka.

## Vald struktur — sex sektioner i en självbärande HTML

`Resultat/rapporter/dashboard_rework_YYYYMMDD.html` — Python genererar,
Plotly via CDN, all data inbäddad som JSON. Ingen ny stack.

### 1. ÖVERSIKT (investerare)
- Hero-KPI:er: kapacitet, YTD-produktion vs budget, YTD-intäkt (spot & PPA),
  flottans capture senaste stängda månad + premium vs baseload.
- **Klartext-slutsatser**: automatgenererade meningar med riktiga tal
  (beräknas i Python, trösklar avgör formulering). Detta är sektionens
  kärna — investerare ska kunna läsa fem meningar och förstå läget.
- 13 månaders portföljproduktion vs budget (staplar + budgetlinje).
- Park-YTD-tabell (produktion, vs budget, yield) som snabb lägesbild.

### 2. MARKNADEN (smart elprisanalys)
- Månadssnittpris per zon 2021→ (strukturell trend, kris-annotering).
- Volatilitet: daglig intradagsspread (snitt max−min per dag, månadsvis).
- **Duck curve-utveckling**: timprofil av snittpris per år (lokal tid),
  zonväljare — visar middagsgropen fördjupas år för år.
- Negativa pristimmar per månad och år, per zon.
- Zonspreadar SE4−SE3, SE3−SE1 (månadsvis) — flaskhalsvärde.
- Pris-heatmap månad × timme (återanvänd från dashboard_v2).

### 3. CAPTURE & CANNIBALISERING (kärnanalys sol)
- Capture-pris + capture ratio per zon över tid (sol syd som referens).
- **Cannibalisering**: dual-axis installerad sol-MW per zon (län→zon-mappad
  Energimyndigheten-data) mot årlig capture ratio. Korrelationen är poängen.
- **Orienteringsanalys** (PVsyst-profilerna):
  - Capture-premie öst-väst vs syd vs tracker per år och zon.
  - **EUR/kWp-perspektivet**: capture × specifik produktion
    (911/1012/1202 kWh/kWp för ew/syd/tracker) — EW har högre capture-pris
    men lägre yield; vad vinner i kr per installerad kWp? Det är frågan
    en investerare faktiskt ställer.
  - Profilform vs prisform: normaliserad juni-produktionsprofil per
    orientering överlagrad på juni-prisprofil — *varför* EW vinner på
    marginalen syns direkt.
- PVsyst vs ENTSO-E-validering (återanvänd `validation` från dashboard_v2)
  som trovärdighetsnot.

### 4. PARKERNA (asset management)
- League table senaste stängda månad: energi, vs budget, yield, PR,
  availability, capture, negativpris-MWh per park. Sorterbar.
- Specific yield-jämförelse alla parker (månadsvis linjer).
- Tracker-analys: Hova vs Björke/Skäkelbacken med explicit caveat att
  Hova är portföljens enda tracker (väntat hög, inte anomalt).
- Negativpris-exponering per park över tid.
- **Park-drilldown via väljare** (en panel, re-render vid val): 13 mån
  KPI-tabell, produktion vs budget, PR/availability, realiserad capture
  vs zonens baseload, förlust-waterfall senaste stängda månad, daglig
  produktion senaste 3 mån, parkfakta + PPA-villkor.

### 5. RISK & INTÄKT (futures, PPA, obalans)
- Forward curve per zon (SYS+EPAD, senaste settlement) + realiserad spot
  för levererade kontrakt (träffsäkerhet).
- **PPA vs marknad**: per park med PPA — kontrakterat pris (SEK/MWh,
  EUR-konverterat tidsviktat) vs realiserad spot-capture vs forward.
  YTD-uplift i EUR av PPA-hedgen (= revenue_ppa − revenue_spot).
  Svarar på "är våra hedgar in eller out of the money?"
- **Obalanskostnad (eSett — ny analys, datat var helt outnyttjat)**:
  månadsvis snitt|obalanspris − spot| per zon + andel kvarter
  uppreglerade/nedreglerade. Proxyn för vad prognosfel kostar en
  solproducent per MWh fel.

### 6. DATAKVALITET (ops-hygien)
- Per park: senaste datapunkt, mätartäckning % (andel energi från
  grid-mätare vs inverter-fallback), stuck-value-dagar (Stenstorp-felet),
  availability-täckning. Gör tyst sensorröta synlig.

Footer: genereringstid, datakällor med täckningsdatum, ordlista
(capture, ratio, PR, specific yield, EPAD, TB2).

## Återanvändning (läses, ändras inte)

| Behov | Befintlig modul |
|-------|-----------------|
| Park-KPI per månad (budget, PR, förluster, dagligt) | `unified_dashboard_data.build_unified_data` → assets |
| Realiserad capture/revenue/PPA per park | `park_revenue.calculate_park_revenue_capture` (via assets) |
| Zon-capture per profil (syd/ew/tracker), heatmap, validering, forward | `dashboard_v2_data.calculate_dashboard_v2_data` (via market) |
| Specific yield, neg-pris, tracker-gain, meterförlust | `operations_dashboard_data` (via market.operations) |
| effective_power_mw + stuck-detection | `operations_dashboard_data.load_park_15min` |
| Parkmetadata, budget, PPA | `park_config` |
| PVsyst TMY-profiler | `Resultat/profiler/beraknade/*.csv` |

`build_unified_data()` anropas EN gång; rework-bygget komponerar dess
market+assets och **beskär** payloaden (släng dagliga serier per
zon×profil, BESS/ancillary-profiler, park_*-profiler) innan inbäddning,
så HTML-filen blir väsentligt mindre än dagens 17 MB.

## Nya moduler

```
elpris/rework_market_analysis.py   # quarterly-CSV → årsstatistik, duck curve,
                                   # neg-timmar, zonspreadar, volatilitet
elpris/rework_capture_analysis.py  # län→zon-mappning av Energimyndigheten-sol,
                                   # cannibalisering, orienterings-premie,
                                   # EUR/kWp, TMY-profilformer
elpris/rework_imbalance.py         # eSett-CSV → månadsvis obalansstatistik
elpris/rework_portfolio.py         # portfölj-aggregat, PPA-vy, datakvalitet,
                                   # klartext-insikter (svenska meningar)
elpris/rework_dashboard_data.py    # komponerar allt → en JSON-dict + pruning
elpris/rework_dashboard_html.py    # renderare (egen visuell identitet)
generate_rework_dashboard.py       # CLI: bygg data + skriv HTML
tests/test_rework_analysis.py      # enhetstester för rena funktioner
                                   # (syntetisk data, inga fil-beroenden)
```

Python 3.9-kompatibelt (`from __future__ import annotations`).

## Visuell identitet — "Nordic Clarity"

Avsiktligt skild från Track C (varmt papper/chartreuse/mörk sidorail):

- Ljus, sval bas (vitt + kyligt grå), djup petrol/teal som primäraccent,
  bärnsten för sol-serier, korall för negativa värden.
- Toppnav med sticky sektionslänkar (rapportkänsla, inte verktygskänsla).
- Varje sektion inleds med en "takeaway"-rad i stor stil — klartext först,
  graf sen.
- Tal i tabellform med tabular-nums; svenska tusentalsavgränsare.
- Lazy chart-rendering via IntersectionObserver (initial load snabb trots
  ~30 grafer).

## Verifiering

1. `python3 generate_rework_dashboard.py` → fil skapas, rimlig storlek.
2. Sanity-grep på HTML: Plotly-divs, inbäddad JSON ej tom, sektions-id:n.
3. `python3 -m pytest tests/` — befintliga 57 + nya tester gröna.
4. `python3 generate_unified_dashboard.py` körs en gång — beviset att
   gamla dashboarden är orörd och fungerar.

## Kända avgränsningar (medvetna val)

- Energimyndighetens soldata slutar 2024 → cannibaliseringskorrelationen
  får 2025/2026 endast på ratio-axeln, markeras i grafen.
- Nasdaq-data t.o.m. 2026-04-29 (Euronext-flytten) → forward märks med
  as-of-datum.
- Quarterly spot slutar 2026-05-22 i nuvarande synk → capture/revenue
  för juni blir partiell; pro-rata hanteras redan av unified-bygget.
- Län→zon-mappningen är dominant-zon-approximation (län kan korsa
  zongränser); duger för trendkorrelation, dokumenteras i grafen.
- BESS-djupanalys lämnas i Track C (ingen duplicering); rework visar
  flexvärdes-signalen via intradagsspread i stället.
