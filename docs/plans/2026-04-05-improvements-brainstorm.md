# Förbättringar och ny funktionalitet — Brainstorm

**Datum:** 2026-04-05
**Status:** Brainstorm-underlag, ej beslutat
**Syfte:** Identifiera högvärdes-förbättringar för Elpris-projektet

---

## TL;DR

Projektet är redan starkt på capture price-analys, BESS-arbitrage och forward-kurvor.
Den största outnyttjade potentialen ligger i **data som samlas in men aldrig
visualiseras** (Mimer reglerpriser, eSett obalanspriser, installerad kapacitet),
**integrerade beslutstöd** (revenue stack, PPA-kalkylator, scenarioanalys) och
**produktionshygien** (validering, loggning, tester, automation).

Den här planen listar 18 konkreta förslag grupperade i fem teman, rankar dem
efter värde/ansträngning och pekar ut **fem topp-initiativ** med designnotiser.

---

## Metod

Analysen bygger på:

1. Kodkartläggning av `elpris/`, rot-CLIs, `generate_dashboard_v2.py` och
   `dashboard_v2_data.py`
2. Granskning av alla plan-dokument i `docs/plans/`
3. Genomgång av `Resultat/`-katalogen, rapportformat och datatillgänglighet
4. Analys av `update_all.py`, nedladdningsskript och datapipeline
5. Tittar ur fyra perspektiv: **användare**, **affär**, **data/teknik** och
   **operation**

Alla observationer är verifierade mot koden där möjligt.

---

## Nuläge — vad som redan fungerar bra

- **Capture price-analys** med flera profiler (PVsyst, ENTSO-E, park-autodiscovery)
- **BESS-arbitrage** med DP-optimering (1h, 2h, 3h, 4h konfigurationer)
- **Solar + BESS (BTM)** med realistisk constraint att batteriet bara laddas från sol
- **Forward-kurva** integrerad med Nasdaq futures och EPAD per zon
- **Drill-down UI** (år → månad → dag → timme) i Bloomberg-mörk stil
- **Datadriven Excel-export V2** (22 MB, auto-upptäcker profiler)
- **Per-produkt färgsystem** och BESS-tabb i dashboard v2
- **Inkrementell nedladdning** via `get_latest_timestamp` som gör `update_all.py`
  idempotent

## Viktiga luckor (kort)

- **Reglermarknad och obalans är osynliga i dashboard** (data finns sedan länge)
- **Ingen integrerad ekonomisk modell** (IRR, payback, CAPEX/OPEX)
- **Ingen scenarioanalys** mot historisk väder-volatilitet
- **Noll test-täckning, ingen loggning, ingen datavalidering**
- **Manuell körning** — inga cron/launchd-jobb konfigurerade
- **`capture_prices_*.xlsx` är 113-128 MB** — ska troligen avvecklas till förmån
  för dashboard\_v2

---

## Förbättringsområden — alla förslag

Varje förslag har: **problem · lösning · värde · ansträngning (S/M/L) · förutsättning**.

### TEMA A: Synliggör data som redan samlas in

**A1. Reglermarknads-dashboard (Mimer)** — **DELVIS BYGGD**
- *Status:* `elpris/ancillary_dashboard_data.py` finns och integreras i dashboard
  v2 via `calculate_ancillary_data()` (7 profiler: FCR-N, FCR-D upp/ned,
  aFRR upp/ned, mFRR-CM upp/ned). Syns i sidebaren.
- *Återstår:* Validera att visualiseringen är komplett — har den egen tabb
  eller delas BESS-tabben? Trend/jämförelse-vyer? Kombinerat stöd-
  tjänste-totalvy?
- *Värde:* Data används redan men ofta förbisett i genomgångar.

**A2. Obalanspris-dashboard (eSett)** — `M`
- *Problem:* eSett imbalance-priser används bara av `battery_sizing_cli`. Ingen
  överblick över obalans-volatilitet per zon.
- *Lösning:* Ny vy med percentiler (P10/P50/P90) för upp- och
  nedregleringspriser per månad och zon.
- *Värde:* Grund för att kvantifiera risken med att inte hedga / ha batteri.
- *Förutsättning:* Data i `Resultat/marknadsdata/esett/imbalance/`.

**A3. Installerad kapacitet & kapacitetsfaktorer** — `S`
- *Problem:* Energimyndighetsdata (vind MW, sol MW per zon och år) används
  ingenstans. Vi kan inte svara "hur mycket mer sol installerades 2024?".
- *Lösning:* Enkel vy med stacked area per zon över tid, plus beräknad
  kapacitetsfaktor (GWh / (MW × 8760)).
- *Värde:* Kontext för kannibaliseringseffekter och trend-analys.
- *Förutsättning:* Data i `Resultat/marknadsdata/installerad/`.

**A4. PVsyst-profil vs ENTSO-E faktisk sol** — `S`
- *Problem:* Dashboard visar PVsyst-profiler (simulerade) och ENTSO-E
  sol-capture separat. Ingen jämförelse.
- *Lösning:* Overlay-vy "Simulerad vs faktisk capture" per zon och år. Visar
  hur bra PVsyst-profilen stämmer mot nationell faktisk produktion.
- *Värde:* Validerar PVsyst-profilen. Avviker den mycket finns risk att
  capture-siffror för nya projekt är fel.
- *Förutsättning:* ENTSO-E solar ligger redan i `entsoe/generation/SE*/`.

---

### TEMA B: Affärsanalys och beslutsstöd

**B1. BESS Revenue Stack-kalkylator** — `L`
- *Problem:* Arbitrage, FCR, aFRR och baseload-PPA analyseras separat. Ingen
  ser "vad tjänar jag totalt om jag stackar dessa?".
- *Lösning:* En modell som för en given BESS-konfiguration (MW, MWh, zon,
  strategi) beräknar:
  - Arbitrage-intäkt (befintligt)
  - FCR-reservintäkt (från Mimer)
  - aFRR-intäkt (från Mimer, enklare)
  - Prioritetskonflikter mellan arbitrage och reglertjänster
- *Värde:* Realistiskt revenue-case för investeringsbeslut. Arbitrage ensam
  räcker sällan för payback.
- *Förutsättning:* A1 bör göras först för datastruktur. Vissa prioriterings-
  antaganden behöver beslutas.

**B2. BESS payback/IRR-kalkylator** — `M`
- *Problem:* Vi räknar revenue men inte NPV/payback. CFO-fråga: "När tjänar
  vi in investeringen?"
- *Lösning:* Ny vy i BESS-tabben där man fyller i CAPEX (EUR/kWh), OPEX,
  WACC, degradation och livslängd. Visar:
  - Kumulativ cashflow
  - Simpel payback + IRR + NPV
  - Känslighetstabell (CAPEX × revenue-multiplier)
- *Värde:* Direkt användbar i investeringskommitté. Konkret go/no-go-underlag.
- *Förutsättning:* Arbitrage-revenue i EUR/MW (finns redan). CAPEX/OPEX är
  input från användaren — inte hårdkodat.

**B3. Weather stress-test (scenarioanalys)** — `M`
- *Problem:* Baseload-analysen visar 2024. Är 2024 representativt?
- *Lösning:* Kör alla analyser (capture, baseload, BESS) mot varje enskilt år
  2021-2025 och visa distribution. "Batteribehovet varierar mellan X och Y MWh
  beroende på år."
- *Värde:* Robusta dimensioneringsbeslut, inte best-case-dimensionering.
- *Förutsättning:* All historisk data finns. Mest "loop och aggregera".

**B4. Interaktiv PPA-kalkylator** — `L`
- *Problem:* Baseload-PPA-analysen är statisk (200 kW, 80/20 ratio). Ingen
  kan snabbt svara "vad händer om vi ger 10 % pass och sänker baseload till 70 %?".
- *Lösning:* Ny "PPA Designer"-sida med slidrar för:
  - Baseload % (0-100)
  - Pass % (0-20)
  - Sol/vind-ratio
  - Batteri (MWh, effektivitet)
  - PPA-pris (EUR/MWh)
  Realtidsuppdatering av batteribehov, missade timmar och NPV.
- *Värde:* Möjliggör snabba what-if i förhandling och internt.
- *Förutsättning:* Logik finns i `baseload_analysis.py`, behöver exponeras
  som beräkning i dashboard eller via lätt webbserver.

**B5. Pass-klausul heatmap** — `S`
- *Problem:* Relaterat till B4 men ger snabböverblick. Vilken baseload %
  kan vi rimligt garantera vid olika pass %?
- *Lösning:* Matris med baseload-% på y-axel, pass-% på x-axel, celler visar
  batteribehov (MWh) eller break-even-premium (EUR/MWh).
- *Värde:* Visar bäst PPA-struktur på en skärm.
- *Förutsättning:* En loopning av `baseload_analysis.py` över grid.

**B6. Capture-price trend & volatilitet** — `S`
- *Problem:* Vi visar capture-priser som tal men inte trender. Faller
  SE3-solens capture price 5 %/år eller 0 %/år?
- *Lösning:* Tidsserie av årlig capture + glidande medelvärden + procentuell
  förändring år-över-år. Per profil och zon.
- *Värde:* Kvantifierar kannibalisering historiskt. Input till prognoser.
- *Förutsättning:* Data finns, enkelt aggregat.

---

### TEMA C: Datakvalitet, tester och automation

**C1. Datakvalitets-validering** — `M`
- *Problem:* Ingen validering av att nedladdad data är komplett/korrekt.
  Gaps, negativa priser, outliers flaggas aldrig.
- *Lösning:* Ny modul `elpris/quality.py` som kontrollerar:
  - Gaps i tidsserier (saknas timmar/dagar?)
  - Duplikater i CSV-filer
  - Prisextremer (< -500 eller > 3000 EUR/MWh flaggas)
  - Tidszon-konsistens
  Körs från `update_all.py` efter varje nedladdning och rapporterar i status.
- *Värde:* Upptäcker trasig data innan den sipprar in i dashboarden.
- *Förutsättning:* Ingen.

**C2. Strukturerad loggning** — `S`
- *Problem:* All output går till stdout. Ingen kan gå tillbaka och se
  "vilken dag misslyckades ENTSO-E-nedladdningen?".
- *Lösning:* Använd Pythons `logging` med daglig roterad loggfil i
  `Resultat/logs/YYYY-MM-DD.log`. En loggrad per API-anrop, fel och steg i
  `update_all.py`.
- *Värde:* Felsökning, övervakning, granskningsbarhet.
- *Förutsättning:* Ingen.

**C3. Automatisk daglig körning** — `S`
- *Problem:* `update_all.py` körs manuellt. Data blir lätt gammal.
- *Lösning:* launchd-plist (macOS) som kör `update_all.py` kl 09:00 varje dag,
  skriver till loggen från C2. Dokumenterat i README.
- *Värde:* Alltid färsk data. Slipper glömma att uppdatera.
- *Förutsättning:* C2 (loggning) för felsökning utan att sitta vid datorn.

**C4. Grundläggande test-täckning** — `M`
- *Problem:* Noll tester. Refaktorering är farlig — ingen vet om dashboarden
  går sönder när `dashboard_v2_data.py` ändras.
- *Lösning:* pytest för kritiska moduler:
  - `processing.py` (tim → 15-min expansion)
  - `capture.py` (capture-beräkningar med kända exempel)
  - `battery.py` (DP-algoritm med liten känd dataset)
  - `dashboard_v2_data.py` (aggregeringar på liten syntetisk data)
- *Värde:* Trygghet vid ändringar. Dokumenterar förväntade beteenden.
- *Förutsättning:* Ingen.

**C5. Avveckla `capture_prices_*.xlsx` (113-128 MB)** — `S`
- *Problem:* Dessa filer är 5× större än dashboard\_v2-exporten och verkar
  vara legacy. De fyller `Resultat/rapporter/` och backas upp med resten.
- *Lösning:* Bekräfta med dig om de används. Om inte — flagga för arkivering,
  ta bort ur master-pipeline.
- *Värde:* Diskspace + pipeline-hastighet. Mindre förvirring.
- *Förutsättning:* Användarbeslut.

---

### TEMA D: Dashboard- och UX-förbättringar

**D1. Forward vs realiserat spot-overlay (förbättring)** — `S`
- *Problem:* Forward-kurvan visar futures men jämförs inte tydligt med
  verklig realiserad spot. Hur bra prissätter marknaden?
- *Lösning:* I "Forward vs Realiserat Spot"-vyn, lägg till ett glidande
  "forward-bias"-spår (historisk forward minus realiserad per kvartal).
- *Värde:* Visar systematisk över-/underprissättning, nyttigt för hedging.
- *Förutsättning:* Forward-data finns, spot-data finns.

**D2. Capture-ratio över tid (trend-vy)** — `S`
- *Problem:* Capture-ratio (capture/baseload) visas per period men inte som
  trend. Sjunker den?
- *Lösning:* Ny tidsserie "Capture-ratio över tid" per profil och zon med
  årsmedel och trendlinje.
- *Värde:* Direkt visualisering av kannibaliseringseffekt.
- *Förutsättning:* Data finns, aggregation är enkel.

**D3. Sommarnatts-/vinternatts-analys** — `S`
- *Problem:* Baseload-analysen visar att sommarnätter är flaskhalsen men
  det är inte visualiserat i dashboard.
- *Lösning:* Heatmap (timme × månad) med priser, capture eller batteri-
  utnyttjandegrad per zon.
- *Värde:* Intuitiv förståelse av när marknaden är tight.
- *Förutsättning:* Data finns timvis för baseload.

---

### TEMA E: Prognoser och framtidsblick

**E1. Hedging-rekommendatör** — `M`
- *Problem:* Vi har både realiserad capture och forward futures men ingen
  rekommendation: "Bör jag hedga 50 %, 100 %?"
- *Lösning:* Jämförelse per kvartal: historisk capture (5 år) vs aktuellt
  forward-pris. Rekommendation baserad på hur långt forward ligger från
  historisk median och volatilitet.
- *Värde:* Beslutsstöd för treasuryfunktion eller projektfinansiering.
- *Förutsättning:* B6 (capture-trend) + Nasdaq-data (finns).

**E2. Kannibaliseringsindex (enkel version)** — `L`
- *Problem:* Vi vill kunna svara "hur mycket sjunker capture om ytterligare
  2 GW sol byggs i SE3?"
- *Lösning:* Empirisk regression: capture-ratio per zon mot installerad
  sol-kapacitet per zon (båda från befintlig data). Ger en enkel lutning
  "per GW ny sol i SE3 sjunker capture-ratio med X%".
- *Värde:* Input till långsiktiga investeringsbeslut.
- *Förutsättning:* Data finns. Metod är enkel lineär regression men måste
  dokumenteras tydligt som empirisk indikator, inte prognos.

---

## Prioritetsmatris

Värde × ansträngning. Högre värde + lägre ansträngning = starkare rekommendation.

| Förslag | Värde | Ansträngning | Rekommendation |
|---|---|---|---|
| C5. Avveckla `capture_prices_*.xlsx` | M | S | **Gör direkt** |
| A3. Installerad kapacitet-vy | M | S | **Snabbvinst** |
| A4. PVsyst vs ENTSO-E overlay | H | S | **Snabbvinst** |
| B6. Capture-trend/volatilitet | H | S | **Snabbvinst** |
| D1. Forward-bias-overlay | M | S | Snabbvinst |
| D2. Capture-ratio trend | M | S | Snabbvinst |
| D3. Sommarnatts-heatmap | M | S | Snabbvinst |
| B5. Pass-klausul heatmap | H | S | **Snabbvinst** |
| C2. Strukturerad loggning | M | S | Gör snart |
| C3. Automatisk daglig körning | M | S | Efter C2 |
| A1. Reglermarknads-dashboard | H | M | **Strategiskt** |
| A2. Obalanspris-dashboard | M | M | Strategiskt |
| B3. Weather stress-test | H | M | **Strategiskt** |
| B2. BESS payback/IRR | H | M | **Strategiskt** |
| C1. Datakvalitets-validering | H | M | **Strategiskt** |
| C4. Test-täckning | M | M | Strategiskt |
| E1. Hedging-rekommendatör | M | M | Strategiskt |
| B1. BESS Revenue Stack | H | L | **Stor investering** |
| B4. Interaktiv PPA-kalkylator | H | L | Stor investering |
| E2. Kannibaliseringsindex | M | L | Stor investering |

---

## Topp 5 — detaljerade rekommendationer

### 1. A4. PVsyst vs ENTSO-E overlay — validera simulerade profiler
**Varför först:** Låg ansträngning, hög insikt. Om PVsyst-profilen avviker
> 5-10 % från faktisk ENTSO-E-sol finns risk att alla capture-siffror i
dashboarden är systematiskt fel.

**Design:**
- Ny vy i sol-kategorin: "Simulerad vs faktisk capture".
- X-axel: månad (2021-2025). Y-axel: EUR/MWh capture.
- Två linjer per zon: PVsyst-profil-capture (snitt av alla tre profiler) och
  ENTSO-E-faktisk-solcapture. Skillnaden i % som bandyta.
- Tooltip visar båda värdena och avvikelsen.

**Filer:**
- `elpris/dashboard_v2_data.py` (ny beräkning, lägg till under `calculate_dashboard_v2_data`)
- `generate_dashboard_v2.py` (ny vy-funktion)

**Första steget:** Skriv ett 30-raders script som beräknar och skriver ut
avvikelsen per zon och år. Om avvikelsen är trivial är kostnaden för en full
vy lägre eftersom slutsatsen är "de stämmer". Om den är stor — högprioritet.

---

### 2. B6 + D2. Capture-trend och ratio-trend — kvantifiera kannibalisering
**Varför först:** En av de viktigaste affärsfrågorna — "faller capture-priset
år för år?" — är inte visualiserad idag. Mycket enkelt att göra.

**Design:**
- Ny vy: "Capture-trend" med årsmedel per profil och zon, plus capture/baseload-
  ratio som sekundär axel.
- Visa procentuell förändring år-över-år som bar-chart under.

**Filer:**
- `elpris/dashboard_v2_data.py` (har redan yearly-aggregat)
- `generate_dashboard_v2.py` (ny renderfunktion)

**Första steget:** Utöka befintliga yearly-data med YoY %-förändringskolumn,
rendera i ny Plotly-vy.

---

### 3. B3. Weather stress-test — robust dimensionering
**Varför först:** Nuvarande baseload-analys bygger på ett år (2024). För stora
investeringsbeslut behöver vi distribution över 4-5 historiska år.

**Design:**
- CLI-kommando: `python3 stress_test.py --zone SE3 --baseload 200 --years 2021-2025`
- Kör `baseload_analysis` per år, samlar batteribehov + missade timmar.
- Output: tabell + boxplot per metrik, rekommenderat dimensioneringsvärde
  (t.ex. P90 av batteribehovet).

**Filer:**
- Nytt: `stress_test.py` (rot-CLI).
- Potentiellt: `elpris/baseload_analysis.py` (exponera en ren beräkningsfunktion
  om den inte redan gör det).

**Första steget:** Hitta dokumentationens baseload-analys och kolla vilken
funktion som beräknar batteribehov givet en zon + år. Gör en liten loop.

---

### 4. A1. Reglermarknads-dashboard (Mimer)
**Varför:** Öppnar upp en hel marknad som systemet redan har data på. Är
grund för B1 (Revenue Stack). Ger nya vyer utan att behöva nya datakällor.

**Design:**
- Ny tabb/produkt "Reglermarknad" i dashboard v2.
- Underproduktval: FCR-N, FCR-D-up, FCR-D-down, aFRR-up, aFRR-down, mFRR-CM.
- Tidsserie (månad/vecka/dag) per produkt och zon. Jämförelse mot spot-pris.
- KPI-kort: årsmedelpris, volatilitet (standardavvikelse), antal timmar
  > 50 EUR/MW/h.

**Filer:**
- `elpris/dashboard_v2_data.py` (ny datafunktion `load_regulation_data`)
- `generate_dashboard_v2.py` (ny vy + produkt-färgmappning)

**Första steget:** Skriv en pandas-ad-hoc som läser `mimer/fcr/*.csv`, plotar
årsmedel per zon. Validera att data är rimlig. Bygg sedan in i dashboard.

---

### 5. C1 + C2. Datakvalitets-validering + loggning
**Varför:** Produktion utan kvalitetssäkring är farlig. Om en zon får korrupt
data sprider det sig in i dashboard och rapporter. Bygg basen nu innan fler
konsumenter (B1, B4) läggs på.

**Design:**
- Ny modul `elpris/quality.py` med:
  - `check_continuity(path)` — verifierar inga gaps i timestamp-sekvenser.
  - `check_duplicates(path)` — hittar dubletter efter timestamp.
  - `check_extremes(path)` — flaggar priser utanför `[-500, 3000]` EUR/MWh.
  - `check_timezone(path)` — säkerställer konsekvent tz i hela filen.
- `update_all.py` kör `quality.check_all()` efter varje steg och skriver
  sammanfattning till loggen.
- `logging`-konfigurering centralt i `elpris/config.py`, roterad loggfil i
  `Resultat/logs/`.

**Filer:**
- Ny: `elpris/quality.py`, `elpris/logging_config.py`.
- Modifiera: `update_all.py`, `elpris/config.py`.

**Första steget:** `quality.py` med en enda funktion — `check_continuity` för
spotpris-CSV — plus ett CLI `python3 quality_check.py`. Utöka gradvis.

---

## Om du bara har tid för tre saker i nästa sprint

1. **B6 + D2 (Capture-trend)** — 1 dag, direkt affärsvärde.
2. **A4 (PVsyst vs ENTSO-E)** — 1 dag, validerar grundantagandet för allt annat.
3. **C1 + C2 (Kvalitet + loggning)** — 2-3 dagar, säkrar produktionshygien
   innan nya funktioner läggs på.

## Om du har en hel sprint (2 veckor)

Lägg till **B3 (Weather stress-test)** och **A1 (Reglermarknads-dashboard)**.
Då täcker du in både affärsvärde, validering, produktionshygien och ny
synliggörande av stor datamängd.

## Om du bygger en kvartalsroadmap

Bygg **B1 (BESS Revenue Stack)** som kvartalets stora initiativ. Den är
beroende av A1 och C1 som grundläggs tidigare i kvartalet och levererar en
genuint ny affärsförmåga: ett samlat revenue-case för batteriinvesteringar.

---

## Saker jag medvetet lämnar utanför

- **Realtids-dashboard**: Systemet är retrospektivt. Att bygga realtid kräver
  nya API:er, ny frontend-arkitektur och ändrar produktens karaktär.
- **Multi-site portfolio-optimering**: För tidigt — `parker/`-mappen är tom.
  När 2-3 riktiga parker finns blir detta relevant.
- **Avancerade prognos-modeller (ML)**: Börja med enkel regression (E2) och
  statistisk analys (B3) innan ML. ML kräver fel-modellering, validering och
  disciplin som inte finns idag.
- **PPTX-generering**: Finns redan något (`Resultat/presentationer/`). Lägger
  inte till mer förrän efterfrågan är uttryckt.

---

## Tekniska skulder att ha i bakhuvudet

1. **Duplicerad logik** — `battery.py` och `bess_dashboard_data.py` delar DP-
   algoritm. `solar_battery.py` och `bess_dashboard_data.py` delar BTM-logik.
   Bör konsolideras, men inte akut.
2. **Legacy dashboard v1** — `generate_dashboard.py` och `elpris/dashboard_data.py`
   är ersatta av v2. Om de inte används längre — arkivera.
3. **`Resultat/BESS-PV-Vind-Baseload-PPA/kod/`** — duplicerad från projekt-
   roten, riskerar drifta isär. Bör importera från `elpris/` istället.
4. **Tidszon-ambiguitet** — ISO-timestamps utan explicit TZ i spotpris-CSV.
   Rekommendation: standardisera på UTC i hela pipelinen.
5. **Manuell sökväg-hantering** — många scripts har egen path-logik.
   `elpris/config.py` centraliserar en del men inte allt.

---

## Nästa steg

Läs planen, välj 1-3 förslag att gå vidare på. Säg till vilka — jag kan skriva
detaljerad implementationsplan (à la `docs/plans/2026-04-05-excel-export-v2-
implementation.md`) för de valda.

---

## Genomfört 2026-04-05

Efter brainstorm-plan skrevs, implementerades tre av förslagen direkt:

### A4 — PVsyst vs ENTSO-E-validering ✅

- Nytt CLI: `analyze_solar_profiles.py`
- Resultat sammanfattade i `docs/insights/2026-04-05-pvsyst-vs-entsoe-validation.md`
- **Fynd:** PVsyst-profiler överestimerar capture-pris med 7-12 % i SE2-SE4
  för fullständiga år 2022-2025. Trenden växer med tiden (kannibalisering).
  Bör tas med som justeringsfaktor vid nya projektvärderingar.

### B6 + D2 — Capture-trender i dashboard ✅

- Ny chart-card "Förändring år-över-år (capture)" i dashboard v2, synlig
  endast i yearly-vyn.
- Grupperad bar-chart visar YoY % per profil och år. Röd = negativ
  förändring (kannibalisering), zonfärg = positiv.
- Modifierade filer: `generate_dashboard_v2.py` (ny `renderYoYChart()`).

### C1 — Datakvalitets-validering ✅

- Ny modul: `elpris/quality.py` med gap-, duplikat-, prisextrem- och
  tz-kontroller. Hanterar DST-övergångar korrekt (ignorerar labeling-
  artefakter).
- Ny CLI: `quality_check.py` (exit 0 = OK, 1 = minst ett fel).
- 10 unit-tester i `tests/test_quality.py` (alla passerar).
- **Fynd vid första körning:** 4 riktiga dataluckor i SE2/2022 (timmen 23:00
  saknas 4 nätter i sept-okt) och 1 lucka i SE3/2021. Actionable — kan
  re-fetchas från elprisetjustnu.se.

### Rättelse i planen

A1 (Reglermarknads-dashboard) visade sig redan vara delvis implementerad via
`elpris/ancillary_dashboard_data.py` — den första utforskningen missade detta.
Listan uppdaterad.

### Kvar att göra

Se prioritetsmatrisen ovan för topp-förslagen. Rimliga nästa steg:

- **B3 (Weather stress-test)** — viktigast för robust dimensionering
- **B2 (BESS payback/IRR)** — ekonomimodellen finns redan delvis i dashboard
  v2 (`invest-card`), kan utökas
- **C2 + C3 (loggning + automatisk körning)** — produktionshygien
- **Fyll i real-gap-luckorna** som quality_check.py hittade via riktad
  `download.py --zones SE2 --start 2022-09-04 --end 2022-09-05` etc.

