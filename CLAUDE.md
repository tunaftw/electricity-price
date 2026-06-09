# Elpris - Swedish Electricity Price Analysis

System för att ladda ner och analysera svenska elpriser, reglerpriser, futures
och solparksproduktion. Genererar dashboards och per-park månadsrapporter.

## Projektstruktur

```
electricity-price/
├── elpris/                              # Pythonpaket
│   ├── api.py                           # elprisetjustnu.se-klient (spotpriser)
│   ├── bazefield.py                     # Bazefield-klient (solparker)
│   ├── battery.py                       # Batteri-DP (arbitrage)
│   ├── battery_excel.py                 # Excel-export för battery_arbitrage
│   ├── bess_dashboard_data.py           # BESS-flikens data (arbitrage + BTM)
│   ├── capture.py                       # Capture price-beräkningar
│   ├── capture_report.py                # REPORTS_DIR-konstant + capture-rapporter
│   ├── config.py                        # Sökvägar, zoner, parkkonstanter
│   ├── dashboard_v2_data.py             # Park/profil-laddare för dashboards
│   ├── ancillary_dashboard_data.py      # Mimer/eSett-aggregering till dashboard
│   ├── energimyndigheten.py             # PxWeb (installerad kapacitet)
│   ├── entsoe.py                        # ENTSO-E Transparency Platform
│   ├── entsoe_profile.py                # Normaliserade ENTSO-E-profiler
│   ├── esett.py                         # eSett Nordic obalanspriser
│   ├── excel_export.py                  # Excel-export för capture_prices
│   ├── inverter_data.py                 # SCADA inverter-CSV (lazy-laddad)
│   ├── inverter_registry.py             # Auto-genererad av discover_inverters.py
│   ├── mimer.py                         # Svenska kraftnät reglerpriser
│   ├── nasdaq.py                        # Nasdaq Nordic futures (SYS + EPADs)
│   ├── operations_dashboard_data.py     # Specific yield, neg-pris, tracker, meterförlust
│   ├── park_config.py                   # Park-metadata + budget (PVsyst TMY)
│   ├── park_product_data.py             # Cowork SharePoint-extrakt (källa)
│   ├── performance_report_data.py       # KPI-beräkningar månadsrapport
│   ├── performance_report_html.py       # HTML-rendering månadsrapport
│   ├── ppm_schedule.py                  # Underhållsschema (lazy-laddad)
│   ├── processing.py                    # Tim → quarterly (15-min)
│   ├── rework_capture_analysis.py       # Rework: cannibalisering + orientering
│   ├── rework_dashboard_data.py         # Rework: komponerar + beskär payload
│   ├── rework_dashboard_html.py         # Rework-renderaren (Nordic Clarity)
│   ├── rework_imbalance.py              # Rework: eSett-obalansstatistik
│   ├── rework_market_analysis.py        # Rework: duck curve, neg-timmar, spreadar
│   ├── rework_portfolio.py              # Rework: portföljaggregat + klartext-insikter
│   ├── solar_profile.py                 # PVsyst + ENTSO-E solprofiler
│   ├── storage.py                       # CSV-läs/skriv för spotpriser
│   ├── unified_dashboard_data.py        # Aggregerar all data till JSON
│   └── unified_dashboard_v3_html.py     # Track C — Nordic Editorial-renderaren
├── tests/                               # Pytest-tester (begränsad täckning)
├── Resultat/                            # All nedladdad data + analyser (se nedan)
├── data/                                # Symlinks till Resultat/ (delvis — se nedan)
├── docs/                                # Insikter + planer (active vs archive)
├── update_all.py                        # Master pipeline (12 steg)
├── download.py                          # Spotpriser, full historik
├── update.py                            # Spotpriser, inkrementellt
├── process.py                           # Konvertera tim → quarterly
├── capture.py                           # Beräkna capture prices
├── status.py                            # Visa datastatus
├── entsoe_download.py                   # Hämta ENTSO-E-produktion
├── esett_download.py                    # Hämta eSett-obalanspriser
├── mimer_download.py                    # Hämta SVK-reglerpriser
├── nasdaq_download.py                   # Hämta Nasdaq-futures
├── installed_download.py                # Hämta installerad kapacitet
├── bazefield_download.py                # Synka Bazefield-solparker
├── generate_unified_dashboard.py        # Bygg unified dashboard (Track C)
├── generate_rework_dashboard.py         # Bygg rework-dashboard (Nordic Clarity)
├── generate_performance_report.py       # Bygg per-park månadsrapport
└── discover_inverters.py                # Maintenance: regenerera inverter_registry.py
```

## Datakatalog

All data och analysresultat ligger i `Resultat/`:

```
Resultat/
├── marknadsdata/                # Nedladdad marknadsdata
│   ├── spotpriser/              # SE1-SE4: raw + quarterly per år
│   ├── entsoe/generation/       # SE1-SE4: solar/wind_onshore/nuclear/hydro per år
│   ├── mimer/                   # fcr/, afrr/, mfrr_cm/, mfrr/ per år
│   ├── esett/imbalance/         # SE1-SE4 obalanspriser per år
│   ├── installerad/             # Energimyndigheten (sol + vind)
│   └── nasdaq/futures/          # SYS + EPAD per zon
├── profiler/
│   ├── beraknade/               # PVsyst-processade (.csv per park-profil)
│   ├── normaliserade/           # ENTSO-E normaliserade (solar_SE*.csv)
│   └── parker/                  # Bazefield 15-min per park (utökat format)
├── sol-kalldata/                # Råa PVsyst-dokument (PDF/XLSX)
├── rapporter/                   # Genererade dashboards + Excel + per-park HTML
├── logs/                        # Körningsloggar
├── BESS-PV-Vind-Baseload-PPA/   # Avslutat analysprojekt (arkiv-likt)
├── historik-nordpool/           # Lokal kopia (gitignorerad — duplicerad data)
└── presentationer/              # PowerPoint-utkast
```

**`data/`-katalogen** innehåller delvis bakåtkompatibilitet:
- `data/profiles`, `data/solar_profiles`, `data/raw/{SE1..SE4,entsoe,esett,installed,mimer}` är symlinks till `Resultat/...`
- `data/quarterly/`, `data/raw/`, `data/reports/` är riktiga kataloger som gradvis ska migreras till `Resultat/`. Tills vidare läser/skriver vissa scripts via dessa.

## Datakällor

### 1. Spotpriser — elprisetjustnu.se
- **Zoner:** SE1, SE2, SE3, SE4
- **Period:** 2021-11-01 → idag (15-min upplösning från 2025-10-01)
- **API:** `https://www.elprisetjustnu.se/api/v1/prices/{year}/{month}-{day}_{zone}.json`

### 2. Reglerpriser — Svenska kraftnät Mimer
- **FCR:** FCR-N, FCR-D upp/ned (från 2021-01-01)
- **aFRR:** aFRR upp/ned per zon (från 2022-11-01)
- **mFRR-CM:** Kapacitetsmarknad per zon (från 2024-06-01)
- **mFRR:** Energiaktivering per zon (från 2022-01-01, tomt efter mars 2025 pga eSett EAM)
- **API:** `https://mimer.svk.se/PrimaryRegulation/DownloadText`

### 3. Installerad kapacitet — Energimyndigheten (PxWeb)
- **Vindkraft:** Antal verk, MW, GWh per elområde
- **Sol:** Antal anläggningar, MW per region
- **API:** PxWeb REST

### 4. Faktisk produktion — ENTSO-E Transparency Platform
- **API:** `https://web-api.tp.entsoe.eu/api`
- **Token:** `ENTSOE_TOKEN` (miljövariabel eller `.env`)
- **Upplösning:** 60 min (vissa 15 min)

| Typ | Kod | SE1 | SE2 | SE3 | SE4 |
|-----|-----|-----|-----|-----|-----|
| solar | B16 | ~2022 | ~2022 | ~2015 | ~2015 |
| wind_onshore | B19 | 2015 | 2015 | 2015 | 2015 |
| hydro_water_reservoir | B12 | 2015 | 2015 | 2015 | 2015 |
| nuclear | B14 | – | – | 2015 | 2015 |
| fossil_gas | B04 | – | – | 2015 | – |

### 5. Obalanspriser — eSett Nordic Imbalance Settlement
- **Period:** Från 2023-05-22, 15-min upplösning
- **API:** `https://api.opendata.esett.com` (ingen nyckel)

### 6. Elfutures — Nasdaq Nordic Commodities
- **SYS Baseload:** Nordic system price futures (kvartal, år)
- **EPAD:** Per zon (Luleå, Sundsvall, Stockholm, Malmö)
- **Upplösning:** Daglig settlement (`dailyFix`) i EUR/MWh
- **API:** `https://api.nasdaq.com/api/nordic/` (odokumenterat)
- **OBS:** Handeln flyttad till Euronext mars 2026, men Nasdaq publicerar fortfarande dailyFix

### 7. Solparksproduktion — Bazefield
- **8 parker:** Horby/Agerum/Tangen (SE4), Fjallskar/Hova/Bjorke/Skakelbacken/Stenstorp (SE3)
- **Upplösning:** 15 min
- **Datapunkter per park:** ActivePowerMeter (grid), ActivePower (inverter), IrradiancePOA, Availability
- **Datapunkter per väderstation:** IrradianceGHI, WindSpeed, Humidity
- **Nyckel:** `BAZEFIELD_API_KEY` i `.env`
- **API:** `https://sveasolar.bazefield.com/BazeField.Services/api/`

## Slash Commands

Slash commands i `.claude/commands/`. Master-kommandot rekommenderas för rutinkörningar.

### Master Update (rekommenderad)
- `/elpris-update-all` — Hela pipelinen (12 steg: spotpriser → Bazefield → ENTSO-E → Mimer → Nasdaq → eSett → process → capture → Excel → unified dashboard → status). Lägg till `--reports` för per-park månadsrapport.

### Datakällor
- `/elpris-download` — Spotpriser, full historik
- `/elpris-update` — Spotpriser, inkrementellt
- `/elpris-entsoe` — ENTSO-E generation
- `/elpris-esett` — eSett obalanspriser
- `/elpris-mimer` — SVK reglerpriser (fcr/afrr/mfrr_cm/mfrr)
- `/elpris-nasdaq` — Nasdaq Nordic futures (SYS + EPADs)
- `/elpris-installed` — Energimyndigheten installerad kapacitet
- `/elpris-bazefield` — Bazefield solparker

### Analys och rapporter
- `/elpris-status` — Datastatus
- `/elpris-capture` — Capture prices
- `/elpris-excel` — Excel-rapporter (capture + battery arbitrage)
- `/elpris-dashboard` — Unified dashboard (Track C — Nordic Editorial)
- `/elpris-rework` — Rework-dashboard (Nordic Clarity — portfölj & marknad)
- `/elpris-reports` — Per-park månadsrapport (alla 8 parker)

## Kommandon (CLI)

### Spotpriser
```bash
python3 download.py                              # Full historik alla zoner
python3 download.py --zones SE3                  # Specifik zon
python3 download.py --start 2024-01-01 --end 2024-12-31
python3 update.py                                # Inkrementell uppdatering
```

### ENTSO-E
```bash
python3 entsoe_download.py                       # solar + wind_onshore alla zoner
python3 entsoe_download.py --zones SE3 --types solar
python3 entsoe_download.py --types hydro_water_reservoir
python3 entsoe_download.py --zones SE3 SE4 --types nuclear
python3 entsoe_download.py --zones SE3 SE4 --start 2024-01-01 --end 2024-12-31
```
**Tillgängliga typer:** solar, wind_onshore, wind_offshore, hydro_run_of_river, hydro_water_reservoir, nuclear, fossil_gas, fossil_hard_coal, biomass, other.
Full historik 2015→idag tar ~30-60 min pga API rate limit.

### eSett, Mimer, Nasdaq, Installerad
```bash
python3 esett_download.py                        # Alla zoner
python3 esett_download.py --zones SE3 SE4 --start 2024-01-01

python3 mimer_download.py                        # Alla produkter
python3 mimer_download.py --product fcr
python3 mimer_download.py --product mfrr --start 2024-01-01 --end 2024-12-31

python3 nasdaq_download.py                       # Alla produkter (SYS + EPAD)
python3 nasdaq_download.py --products sys
python3 nasdaq_download.py --products epad_se3

python3 installed_download.py
```
Alla download-script returnerar exit-kod 1 om någon månads-chunk misslyckas, så `update_all.py` och cron märker tysta API-fel.

### Bazefield
```bash
python3 bazefield_download.py                    # Inkrementell synk
python3 bazefield_download.py --backfill         # Full historik
python3 bazefield_download.py --parks horby fjallskar
python3 bazefield_download.py --status
```

### Bearbetning + analys
```bash
python3 process.py                               # Tim → quarterly
python3 capture.py SE3                           # Standard solprofil
python3 capture.py SE3 --period month
python3 capture.py SE3 --period year
python3 status.py                                # Datastatus
```

### Unified Dashboard (Track C — Nordic Editorial)
```bash
python3 generate_unified_dashboard.py
```
Skapar `Resultat/rapporter/dashboard_unified_v3_YYYYMMDD.html` (~17 MB, fristående HTML med inbäddad data + Plotly.js via CDN). 4 flikar: **CAPTURE**, **BESS**, **FUTURES**, **ASSETS**.

Backend: `elpris.unified_dashboard_data.build_unified_data` aggregerar all data till JSON. Renderaren `elpris.unified_dashboard_v3_html.render_track_c` bygger HTML.

### Rework-dashboard (Nordic Clarity — portfölj & marknad)
```bash
python3 generate_rework_dashboard.py
python3 generate_rework_dashboard.py --save-data /tmp/rework_data.json   # cacha data
python3 generate_rework_dashboard.py --from-data /tmp/rework_data.json   # iterera på renderaren (sekunder)
```
Skapar `Resultat/rapporter/dashboard_rework_YYYYMMDD.html` (~0,5 MB, fristående HTML).
Sex sektioner i rapport-läsordning med automatgenererade klartext-insikter:
**Översikt**, **Marknaden** (duck curve, negativtimmar, zonspreadar),
**Capture & cannibalisering** (installerad sol vs ratio, orientering EUR/kWp),
**Parkerna** (league table + drilldown), **Risk & intäkt** (forward, PPA-bok,
eSett-obalans), **Datakvalitet**. Byggd parallellt med Track C — ersätter den inte.

Backend: `elpris.rework_dashboard_data.build_rework_data` (komponerar
`build_unified_data()` + rework-analysmodulerna, beskär payloaden).
Renderare: `elpris.rework_dashboard_html.render_rework`.
Design: `docs/plans/2026-06-09-fable-rework-design.md`.

### Per-park månadsrapport
```bash
python3 generate_performance_report.py --park horby --month 2026-03
python3 generate_performance_report.py --all --month 2026-03
python3 generate_performance_report.py --park horby                  # senaste fullständiga månad
```
Skapar `Resultat/rapporter/performance_<park>_<zone>_YYYY-MM.html` med 19 sektioner: KPI, YTD, daglig produktion, PR, PI, förlustanalys (waterfall), bästa/sämsta dagar + platshållare för inverter/alarm.

**Parkbudget:** PVsyst TMY som default. Manuella overrides i `PARK_BUDGET_OVERRIDES` i `elpris/park_config.py`.

### Inverter registry (maintenance)
```bash
python3 discover_inverters.py
```
Pingar Bazefield för att lista alla inverter-ID:n per park och regenererar `elpris/inverter_registry.py`. Körs vid behov när nya invertrar driftsätts; `inverter_registry` är Python-källkod som checkas in i git.

### SCADA inverter-data (per-park månadsrapport sektion 14/15/18)
```bash
# Engångs-backfill (alla 8 parker, ~50 min totalt)
python3 bazefield_download.py --inverters --backfill

# Inkrementell sync efter backfill
python3 bazefield_download.py --inverters

# Bara en park
python3 bazefield_download.py --inverters --parks horby
```
Hämtar daglig yield + alarm-events per inverter via Bazefield för alla 200 invertrar
i portföljen. Sparas till `Resultat/profiler/parker/inverters/{park}_daily_yield.csv`
och `{park}_events.csv`. När data finns visar `generate_performance_report.py`
sektion 14 (Inverter Yield), 15 (Inverter Efficiency) och 18 (Alarm & Fault Summary)
i månadsrapporten — annars graceful "Begränsad data"-notis.

### Daglig automation (macOS launchd / cron)
Färdig launchd-plist + installationsinstruktioner finns i [`scripts/README.md`](scripts/README.md).
Kör `python3 update_all.py --quiet` dagligen 06:00, loggar till `Resultat/logs/`.

## Viktiga koncept

### Elområden (SE1-SE4)
- **SE1:** Norra Norrland (Luleå)
- **SE2:** Södra Norrland (Sundsvall)
- **SE3:** Mellansverige (Stockholm)
- **SE4:** Södra Sverige (Malmö)

### Capture Price
Genomsnittligt pris viktat mot solproduktion:
```
Capture = Σ(pris × solproduktion) / Σ(solproduktion)
```

### 15-minutersmarknad
Från 2025-10-01 övergår den svenska elmarknaden till 15-min upplösning. Spotpriser före detta datum expanderas i `processing.py` (varje timpris upprepas 4 gånger).

### Effective power (Bazefield)
`elpris.operations_dashboard_data.load_park_15min` exponerar `effective_power_mw` per intervall: grid-mätare när tillgänglig, annars inverter-summa, annars 0. **All energi-aggregering** (specific yield, neg-pris-exponering) ska använda `effective_power_mw`, inte `power_mw` direkt — annars rapporteras 0 för parker med trasig mätarsignal (t.ex. Stenstorp).

## Operations Dashboard

Operations-vyn (i ASSETS-fliken på unified dashboard) beräknas i
`elpris/operations_dashboard_data.py`:

| Feature | Beskrivning |
|---------|-------------|
| **Specific Yield** | Månadsvis kWh/kWp per park (effective power) |
| **Negativa priser** | Intäktsförlust vid negativa spotpriser |
| **Tracker-gain** | Hova (tracker) vs Björke + Skäkelbacken (fast), % |
| **Meterförlust** | ActivePower (inverter) vs ActivePowerMeter (grid) |

Parkkonstanter (`elpris/config.py`):
- `PARK_CAPACITY_KWP` — installerad DC-kapacitet per park
- `PARK_EXPORT_LIMIT` — exportgräns som andel av DC
- `PARK_ZONES` — elområde per park

## Beroenden

```
requests>=2.31.0
tenacity>=8.2.0
openpyxl>=3.1.0
```

## API-nycklar och `.env`

Skapa `.env` i projektets rot:

```bash
# .env
ENTSOE_TOKEN=...
BAZEFIELD_API_KEY=...
```

| API | Registrering | Kostnad |
|-----|--------------|---------|
| **ENTSO-E** | https://webportal.tp.entsoe.eu/ → "My Account Settings" | Gratis |
| **Bazefield** | Intern API-nyckel | Internt |
| **eSett, Mimer, elprisetjustnu, Energimyndigheten, Nasdaq** | Ingen nyckel krävs | Gratis |

## Dataformat

### Spotpriser (raw)
```csv
timestamp,price_sek,price_eur
2024-01-01T00:00:00+01:00,0.8234,0.0756
```

### Quarterly
```csv
timestamp,price_sek,price_eur
2024-01-01T00:00:00+01:00,0.8234,0.0756
2024-01-01T00:15:00+01:00,0.8234,0.0756
```

### Vindkraft (installed)
```csv
year,zone,turbines,installed_mw,production_gwh
2024,SE1,823,3066.87,7537.24
```

### ENTSO-E generation
```csv
time_start,zone,psr_type,generation_mw,resolution_minutes
2024-01-01T00:00:00+00:00,SE3,solar,0.0,60
```

### eSett obalanspriser
```csv
time_start,zone,imbl_sales_price_eur_mwh,imbl_purchase_price_eur_mwh,up_reg_price_eur_mwh,down_reg_price_eur_mwh
2024-12-01T00:00:00Z,SE3,0.5,0.5,18.95,0.5
```

### mFRR energiaktivering (Mimer)
```csv
time_start,zone,mfrr_up_price_eur_mwh,mfrr_up_volume_mwh,mfrr_down_price_eur_mwh,mfrr_down_volume_mwh
2024-12-01T00:00:00,SE3,19.28,0,-0.5,58
```

### Nasdaq futures
```csv
date,contract,daily_fix_eur,bid_eur,ask_eur,high_eur,low_eur,open_interest
2026-03-31,ENOFUTBLYR-27,47.15,,,,,
2026-03-31,SYSTOFUTBLYR-27,-4.51,,,,,
```

## Dokumentation

- `docs/insights/` — analys- och valideringsnotat (PVsyst vs ENTSO-E mm).
- `docs/plans/` — aktiva designer/planer. Shippade designer ligger i `docs/plans/archive/`.
- Kringgående produktdokumentation finns i Obsidian-vaulten:
  `../SveaSolarObsidianv2/Projects/Elpris/`.

## Framtida utveckling

- [x] ENTSO-E integration
- [x] eSett obalanspriser
- [x] mFRR energiaktivering (Mimer)
- [x] Operations Dashboard Fas 1
- [x] Månadsrapport per park (HTML, 19 sektioner)
- [x] Unified dashboard (Track C — Nordic Editorial, 4 flikar)
- [x] Track C valt som primär (2026-05) och Track A borttagen (2026-05)
- [x] Batterioptimering / arbitrage-analys (BESS-flik + battery_arbitrage Excel)
- [x] Bazefield utökat format (POA, availability, active power)
- [x] Månadsrapport: SCADA-integration (inverter-nivå, alarm/fault) — implementation klar; `bazefield_download.py --inverters --backfill` hämtar data, sektion 14/15/18 renderas i månadsrapporten
- [x] Daglig automation (macOS launchd plist i `scripts/`, manuell installation per `scripts/README.md`)
- [ ] Vidareutveckla Track C (layout, datapunkter, interaktivitet baserat på team-feedback)
- [ ] Migrera till hosted version med autentisering (Vercel/Netlify privat)
- [ ] Historiska solprofiler per region
- [ ] Använd ENTSO-E solproduktion för capture price-beräkning
- [ ] Nord Pool intraday (kräver kundavtal)
