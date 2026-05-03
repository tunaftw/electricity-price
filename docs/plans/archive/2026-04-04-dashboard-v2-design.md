# Elpris Dashboard v2 — Design

**Datum:** 2026-04-04
**Status:** Godkänd
**Ersätter:** 2026-03-07-dashboard-design.md (v1)

## Översikt

Interaktiv HTML-dashboard för att följa svenska elpriser på detaljerad nivå,
med fokus på solcellsparker. Drill-down-navigation (år → månad → dag),
capture prices för alla kraftslag, och stöd för både standardprofiler och
faktiska parkprofiler. Mörkt tema (Bloomberg-inspirerat). Förberedd för
framtida migration till hosted webbapp.

## Beslut

| Parameter | Val |
|-----------|-----|
| Leveransformat | Statisk HTML-fil (migrationsbar till webbapp) |
| Grafbibliotek | Plotly.js (CDN) |
| Valuta | EUR/MWh |
| Zoner | SE1–SE4 (alla) |
| Navigation | Drill-down: år → månad → dag |
| Tema | Mörkt (Bloomberg-inspirerat) |
| Datanedladdning | Manuell (automatiseras senare) |
| Excel-export | Genereras parallellt med HTML |

## Capture prices — kraftslag och profiler

| Pristyp | Profil/källa | Zoner |
|---------|-------------|-------|
| Baseload | Aritmetiskt medel av spotpris | SE1–SE4 |
| Sol — Syd | `south_lundby.csv` | SE1–SE4 |
| Sol — Öst-väst | `ew_boda.csv` | SE1–SE4 |
| Sol — Tracker | `tracker_sweden.csv` | SE1–SE4 |
| Sol — Parker | `Resultat/profiler/parker/*.csv` | Per parks zon |
| Vind | ENTSO-E `wind_onshore` per zon | SE1–SE4 |
| Vattenkraft | ENTSO-E `hydro_water_reservoir` per zon | SE1–SE4 |
| Kärnkraft | ENTSO-E `nuclear` per zon | SE3, SE4 |

### Beräkningslogik

```
Capture price = Σ(spotpris_h × produktion_h) / Σ(produktion_h)
Capture ratio = capture price / baseload price
```

Timmar utan produktion exkluderas. Aggregering till dag/månad/år görs efter viktning.

### Parkprofiler — auto-discovery

```
Resultat/profiler/parker/
├── parknamn_SE3.csv      # Zon härleds från filnamnet (_SE1/_SE2/_SE3/_SE4)
├── annanpark_SE4.csv
└── ...
```

Format: timvärden med normaliserad produktion (0–1), samma som befintliga profiler.
Stöd för både PVsyst-simuleringar och faktisk produktionsdata.

## Layout

```
┌─────────────────────────────────────────────────┐
│  ELPRIS DASHBOARD          SE1 SE2 [SE3] SE4    │  ← Topbar med zonväljare
├──────────┬──────────────────────────────────────┤
│ FILTER   │                                      │
│          │   HUVUDGRAF                           │
│ ☑ Base   │   (Staplar/linjer beroende på vy)    │
│ ☑ Sol-S  │                                      │
│ ☑ Sol-ÖV │                                      │
│ ☑ Sol-T  │   Klickbar drill-down:               │
│ ☑ Vind   │   År → Månad → Dag                   │
│ ☑ Vatten │                                      │
│ ☑ Kärn   │                                      │
│          │                                      │
│ PARKER   ├──────────────────────────────────────┤
│ ☐ Boda   │   CAPTURE RATIO                      │
│ ☐ Lundby │   (Linjediagram, samma tidsperiod)   │
│          │                                      │
├──────────┴──────────────────────────────────────┤
│  Breadcrumb: 2024 > Mars                        │
│  (klicka för att navigera tillbaka)  [Excel]    │
└─────────────────────────────────────────────────┘
```

### Årsvy (startsida)

- Grupperat stapeldiagram: capture price per kraftslag/profil
- Alla år visas (2022–idag)
- Klicka på en stapel → drill down till månadsvy

### Månadsvy

- Stapel- eller linjediagram: capture price per månad för valt år
- Jämför profiler i samma graf
- Klicka på en månad → drill down till dagsvy

### Dagsvy

- Linjediagram: timpriser (eller 15-min efter okt 2025) för vald månad
- Spotpris + produktionsprofiler överlagrade
- Hover visar exakta värden

### Interaktion

- Zonknappar i topbar (byter zon, behåller tidsperiod)
- Checkboxar i sidopanelen filtrerar vilka serier som visas
- Breadcrumb-navigation för att gå tillbaka uppåt
- Hover-tooltips med exakta värden
- Plotly zoom/pan i dagsvyn

## Visuell design

**Färgpalett (mörkt tema):**

| Element | Färg |
|---------|------|
| Bakgrund | `#1a1a2e` |
| Grafbakgrund | `#16213e` |
| Text | `#e0e0e0` |
| Baseload | `#ffffff` (vit) |
| Sol — Syd | `#ffd700` (gul) |
| Sol — Öst-väst | `#ff8c00` (orange) |
| Sol — Tracker | `#ff6347` (korallröd) |
| Vind | `#00d4aa` (turkos) |
| Vattenkraft | `#4169e1` (blå) |
| Kärnkraft | `#dc143c` (röd) |
| Parker | Unika dämpade färger per park |

## Teknisk arkitektur

### Python-sidan

```python
# Ny modul: elpris/dashboard_v2.py

# 1. Ladda data
spotpriser = load_spot_prices(zones=["SE1","SE2","SE3","SE4"])
entsoe = load_entsoe_generation(
    types=["solar","wind_onshore","hydro_water_reservoir","nuclear"]
)
profiler_standard = load_standard_profiles()   # syd, öv, tracker
profiler_parker = discover_park_profiles()      # auto-scan mappen

# 2. Beräkna capture prices
capture_data = calculate_all_captures(
    spotpriser, entsoe, profiler_standard, profiler_parker
)

# 3. Aggregera till dag/månad/år
aggregated = aggregate_periods(capture_data)

# 4. Generera HTML + Excel
generate_html(aggregated, output_path="Resultat/rapporter/dashboard.html")
generate_excel(aggregated, output_path="Resultat/rapporter/dashboard.xlsx")
```

### Befintliga moduler att återanvända
- `elpris/capture.py` — capture price-beräkning
- `elpris/solar_profile.py` — profilladdning + viktberäkning
- `elpris/config.py` — zoner, sökvägar, konstanter
- `elpris/storage.py` — dataladdning
- `elpris/entsoe.py` — ENTSO-E data

### HTML/JS-sidan
- Plotly.js via CDN
- All data inbäddad som `const DATA = {...}` i `<script>`
- ~300 rader JavaScript: drill-down, filtrering, grafuppdatering
- Ingen build-step

### Filstorlek
- HTML: ~2–5 MB (data + JS-logik)
- Plotly.js: ~3 MB (CDN, cachas av browser)

## Migration till webbapp (framtida)

```
Steg 1 (nu):   Python → JSON → Inbäddad i HTML
Steg 2 (sen):  Python (FastAPI) → JSON API → Samma frontend-JS
```

Migrationen innebär:
1. Flytta JSON från inbäddad `<script>` till API-endpoints
2. Byta `const DATA = {...}` mot `fetch('/api/...')`
3. Lägga till `Dockerfile` och deploya

Frontend-koden (grafer, drill-down, filtrering) behöver inte skrivas om.

## Excel-export

Genereras parallellt med HTML via `openpyxl`:
- Flik per zon (SE1–SE4)
- Årlig och månadsvis aggregering
- Alla capture prices och ratios
