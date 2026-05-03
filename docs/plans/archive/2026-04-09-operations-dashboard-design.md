# Operations Dashboard — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Datum:** 2026-04-09
**Syfte:** Ny "Operations"-sektion i dashboard v2 med 15 visualiseringar for solparksportfoljens operationella prestanda, vader, finans och utrustningsstatus.

---

## 1. Bakgrund och kontext

### Vad finns idag
- Bazefield-integration klar: `elpris/bazefield.py` synkar `ActivePowerMeter` (15-min) for 8 parker
- Dashboard v2 (`generate_dashboard_v2.py`) har tre sektioner: Capture, BESS, Futures
- Parkdata lagras i `Resultat/profiler/parker/<park>_<zone>.csv` (kolumner: `timestamp,power_mw`)
- Dashboard auto-upptacker parkprofiler och beraknar capture price via `_calculate_entsoe_capture()`

### Vad vi bygger
En fjarde dashboard-sektion "Operations" med 15 visualiseringar i 4 faser, plus utokad Bazefield-synk.

### Portfolj
| Park | Key | Zon | kWp | DC/AC | Export limit | Tracker | Data fran |
|------|-----|-----|-----|-------|-------------|---------|-----------|
| Horby | horby | SE4 | 18116 | 0.525 | 70% | Nej | 2024-07 |
| Fjallskar | fjallskar | SE3 | 20745 | 0.465 | 70% | Nej | 2024-09 |
| Bjorke | bjorke | SE3 | 6943 | 0.614 | 70% | Nej | 2024-09 |
| Agerum | agerum | SE4 | 8846 | 0.819 | 70% | Nej | 2024-09 |
| Hova | hova | SE3 | 5917 | 0.645 | 70% | Ja (96st) | 2025-01 |
| Skakelbacken | skakelbacken | SE3 | 6500 | 0.619 | 100% | Nej | 2025-07 |
| Stenstorp | stenstorp | SE3 | 1133 | - | - | Nej | 2025-08 |
| Tangen | tangen | SE4 | 6727 | 0.582 | 70% | Nej | 2025-12 |

---

## 2. Arkitektur

### Dashboard-sektion
Dashboard v2 har en tabstruktur: varje tab satter `state.dashboard`, byter `body.className` for CSS-fargvariabler, visar ratt sidebar och anropar ratt render-funktion.

Ny tab: **Operations** med fargpalett gron (`#4ADE80`):
```css
body.product-operations {
    --product: #4ADE80;
    --product-dim: rgba(74, 222, 128, 0.15);
    --product-glow: rgba(74, 222, 128, 0.35);
}
```

Monster att folja (existerande kod):
- `switchDashboard('operations')` — byter state + body class
- `buildOperationsSidebar()` — checkboxar for feature-grupper
- `renderOperations()` — dispatcher for vyer
- Data fran `calculate_operations_data()` i ny modul

### Nya filer
| Fil | Beskrivning |
|-----|-------------|
| `elpris/operations_dashboard_data.py` | Berakningar for alla 15 features |
| `.claude/commands/elpris-bazefield.md` | Uppdatera med nya datapunkter |

### Modifierade filer
| Fil | Andring |
|-----|---------|
| `elpris/bazefield.py` | Utokad synk: fler datapunkter, vaderstation-synk |
| `elpris/config.py` | Park-konstanter (kWp, DC/AC, export limit) |
| `generate_dashboard_v2.py` | Ny tab, sidebar, render-funktioner |
| `elpris/dashboard_v2_data.py` | `load_park_actual_data()` hanterar nya kolumner |

---

## 3. Datalager — Utokad Bazefield-synk

### Kritiskt designbeslut: Lagringsformat

**Problem:** Vaderdata (GHI, WindSpeed, Humidity) kommer fran ett ANNAT Bazefield-objekt (vaderstation) an parkdata (ActivePower, IrradiancePOA, Availability). De kan inte hamtas i samma API-anrop.

**Losning: Hybrid**
- **Utoka park-CSV** med data fran park-objektet (samma API-anrop):
  `timestamp,power_mw,active_power_mw,irradiance_poa,availability`
- **Separat vader-CSV** per park (fran vaderstation-objektet):
  `Resultat/profiler/parker/<park>_<zone>_weather.csv`
  `timestamp,ghi,wind_speed,humidity`

### Bakatkompabilitet
`load_park_actual_data()` anvander `csv.DictReader` och laseer bara `timestamp` + `power_mw` — nya kolumner ignoreras automatiskt. Men `save_park_data()` maste uppdateras for att hantera fler kolumner.

### Ny synk-logik i bazefield.py

**Park-data (utokat):**
```python
# Nuvarande: Points=["ActivePowerMeter"]
# Nytt:
PARK_POINTS = ["ActivePowerMeter", "ActivePower", "IrradiancePOA", "Availability"]
```
Alla returneras i samma API-anrop for samma ObjectId.

**Vaderstation-data (nytt):**
```python
# Kraver separat ObjectId per park (vaderstation != park)
WEATHER_POINTS = ["IrradianceGHI", "WindSpeed", "Humidity"]
```
Kraver mapping: park_key -> weather_station_object_id.

**Weather Station Object IDs** (fran API-utforskning):
```python
PARK_WEATHER_STATIONS = {
    "horby": "1164CB70FB89D000",      # HRB-WS1
    "fjallskar": "<FJL-WS1-id>",       # behover sloas upp
    "bjorke": "<BJK-WS1-id>",
    "agerum": "<AGR-WS1-id>",
    "hova": "<HOV-WS1-id>",            # har 4 WS, valj primara
    "skakelbacken": "<SKB-WS1-id>",
    "stenstorp": "<STT-WS1-id>",
    "tangen": "<TNG-WS1-id>",
}
```
OBS: Dessa ID:n maste slas upp via ObjectStructureGetRequest vid implementation.

### Satellit-vaderstation (fas 3, feature 5)
5 parker har satellitvarderdata. Separata objekt-ID:n, synkas till:
`Resultat/profiler/parker/<park>_<zone>_satellite.csv`

---

## 4. Feature-specifikationer

### Fas 1 — Quick wins (ingen ny synk for features 2/10/11; feature 14 kraver ActivePower)

#### F2: Specific Yield-rankning
- **In:** `power_mw` per park + `PARK_CAPACITY_KWP`
- **Berakning:** `SY = sum(power_mw * 0.25) / (capacity_kWp / 1000)` per manad (MWh/MWp = kWh/kWp)
- **Ut:** Grupperat stapeldiagram, en serie per park, manad pa x-axel
- **Navigation:** Drilldown: ar -> manad
- **Kommentar:** power_mw ar ActivePowerMeter (det vi redan synkar). 0.25 for 15-min -> h.

#### F10: Negativ pris-exponering
- **In:** `power_mw` per park + spotpriser per zon (quarterly-data)
- **Berakning:** For varje 15-min: om `spot_price_eur < 0 AND power_mw > 0`: rakna timmar, volym (MWh), intakt (EUR)
- **Ut:** Dual y-axis: staplar=timmar, linje=negativ intakt. Per park inom samma zon.
- **Matchning:** Park-timestamps (lokal tid) maste konverteras till UTC for att matcha spotpriser (som lagras i UTC).
- **Navigation:** Drilldown: ar -> manad

#### F11: Tracker-vinst (Hova vs fasta)
- **In:** Specific yield for HOV, BJK, SKB (alla SE3)
- **Berakning:** `gain_pct = (sy_hova / mean(sy_bjorke, sy_skakelbacken) - 1) * 100`
- **Ut:** Stapeldiagram per manad, gront=positiv gain, rott=negativ
- **Kommentar:** Bara relevant nar alla tre parker har data for perioden. Hova fran jan 2025, SKB fran jul 2025, sa overlap borjar jul 2025.

#### F14: Meterforlustanalys
- **In:** `active_power_mw` (invertersumma) + `power_mw` (matare) per park
- **Berakning:** `loss_pct = (1 - power_mw / active_power_mw) * 100` under dagljustimmar (power_mw > 0.1)
- **Ut:** Linjediagram per park, farggradient: gron <2%, gul 2-4%, rod >4%
- **Kraver:** Utokad synk (ActivePower-kolumn)

### Fas 2 — Utokad synk (IrradiancePOA + Availability + vader)

#### F1: Performance Ratio (PR)
- **In:** `power_mw` + `irradiance_poa` + `PARK_CAPACITY_KWP`
- **Berakning:** `PR = actual_energy_kWh / (irradiance_kWh_m2 * capacity_kWp * temperature_correction)`
  - Forenklat (utan temp-korrektion): `PR = (sum(power_mw) * 250) / (sum(irradiance_poa) * 0.25 * capacity_kWp)`
  - power_mw i MW, irradiance_poa i W/m2, capacity i kWp
  - Faktor 250: 0.25h * 1000 (MW->kW)
- **Ut:** Linjediagram per park, y-axel PR (0.60-1.00), troskellinjer
- **Navigation:** Drilldown: ar -> manad

#### F7: Instralningskarta (GHI)
- **In:** `ghi` fran vader-CSV per park
- **Berakning:** `monthly_ghi_kWh_m2 = sum(ghi * 0.25) / 1000` (W/m2 -> kWh/m2 via 15-min)
- **Ut:** Heatmap (park x manad) med fargskala for instrralning
- **Kraver:** Vader-synk

#### F13: Tillganglighetskalender
- **In:** `availability` per park
- **Berakning:** `daily_avail = mean(availability_15min)` per dag
- **Ut:** Heatmap (park x dag), farg: gron >98%, gul 90-98%, rod <90%
- **Interaktion:** Horisontell scroll, klickbar for detaljer

#### F15: Degraderingstrend
- **In:** `power_mw` + `irradiance_poa` per park
- **Berakning:** `norm_yield = specific_yield_month / irradiance_kWh_m2_month`
  Plotta samma manad over ar, linear regression for degraderingshastighet
- **Ut:** Linjediagram per park, x=manad (jan-dec), en linje per ar
- **Kommentar:** Behover 2+ ar data. Horby, Fjallskar, Bjorke, Agerum har ~18 man. Begransad men vaxande.

### Fas 3 — Avancerad finansiell analys

#### F8: Revenue Waterfall
- **In:** PVSyst-profiler + faktisk produktion + instralning + availability + spotpris
- **Berakning (decomposition):**
  1. `budget_rev = sum(pvsyst_weight * spot_price)` — vad PVSyst forutsade
  2. `irradiance_effect = (actual_irr / expected_irr - 1) * budget_rev` — mer/mindre sol
  3. `availability_effect = -lost_production * avg_spot_price` — driftstopp
  4. `residual = actual_rev - budget_rev - irradiance_effect - availability_effect` — ovrig avvikelse
- **Ut:** Waterfall-diagram: budget -> irradiance -> availability -> residual -> faktiskt
- **Kommentar:** Mest varde per ar. "Expected irradiance" kan tas fran PVSyst-profilen eller fran satellite-vaeder.

#### F9: Forlorade intakter fran driftstopp
- **In:** `availability` + `irradiance_poa` + spotpriser
- **Berakning:** Nar `availability < 50%`: `lost_rev = expected_power * (1-avail/100) * 0.25 * spot_price`
- **Ut:** Rangordnad tabell + manadsvis stapeldiagram
- **Kommentar:** expected_power beraknas fran instralning * kapacitet * typisk PR

#### F5: Fysisk vs satellit-instralning
- **In:** WS IrradiancePOA + Satellit IrradiancePOA (5 parker: HRB, FJL, BJK, AGR, HOV)
- **Berakning:** Scatter + linear regression, R2, bias, RMSE
- **Ut:** Scatter per park med 1:1 referenslinje
- **Kraver:** Synk av bade WS- och SAT-objekt

#### F4: Clipping/curtailment
- **In:** `power_mw` + `irradiance_poa` + export limit
- **Berakning:** `clip_threshold = PARK_CAPACITY_KWP * PARK_CURTAILMENT_PCT / 1000` (MW)
  Nar `power_mw >= clip_threshold * 0.98`: clipping detekterad
  `clipped_energy = (expected_from_irradiance - actual) * 0.25`
- **Ut:** Staplar=clipping-timmar, linje=forlorad energi. Per park.
- **Kommentar:** Med 70% export limit ar clipping mycket troligt under sommaren!

### Fas 4 — Invertenniva

#### F3: Vaxelriktar-heatmap
- **In:** Per-inverter ActivePower (kraver synk av 200+ objekt)
- **Berakning:** Daglig energi per inverter, normaliserad mot median
- **Ut:** Heatmap (inverter x dag), valj park
- **Komplexitet:** Hog — datavolym, API-anrop, lagringsformat
- **Forslag:** Borja med en park (Horby, 51 inv)

#### F6: Vindpaverkan pa effektivitet
- **In:** `power_mw` + `irradiance_poa` + `wind_speed`
- **Berakning:** `efficiency = power_mw / (irradiance_poa * capacity / 1000)` for dagljus
  Scatter vs wind_speed
- **Ut:** Scatter per park, farg = manad

#### F12: Reaktiv effekt
- **In:** ReactivePowerMeter + PowerFactor (parkniva, redan i API)
- **Berakning:** Manadsmedel under produktionstimmar
- **Ut:** Linjediagram, trooskel vid cos(phi)=0.95

---

## 5. Operations sidebar-layout

```
PRESTANDA
  [x] Specific Yield (F2)
  [x] Performance Ratio (F1)
  [ ] Degradering (F15)
  [ ] Meterforlust (F14)

VADER
  [ ] Instralning GHI (F7)
  [ ] Vind-paverkan (F6)
  [ ] WS vs Satellit (F5)

FINANS
  [x] Negativ pris (F10)
  [ ] Revenue Waterfall (F8)
  [ ] Driftstoppsforlust (F9)
  [ ] Clipping (F4)

PORTFOLJ
  [ ] Tillganglighet (F13)
  [ ] Tracker-vinst (F11)
  [ ] Elkvalitet (F12)
  [ ] Inverterheatmap (F3)
```

Navigation: parkvalj (dropdown eller checkboxar) istallet for zonval (operations ar park-centrerad, inte zon-centrerad som capture).

---

## 6. Implementationsordning (detaljerad)

### Steg 1: Park-konstanter och config (30 min)
- Lagg till `PARK_CAPACITY_KWP`, `PARK_DC_AC_RATIO`, `PARK_CURTAILMENT_PCT` i `elpris/config.py`
- Lagg till `PARK_WEATHER_STATIONS` mapping (sloe upp WS-objekt-ID:n via API)

### Steg 2: Utoka Bazefield-synk (2-3h)
- Andra `fetch_timeseries()` att hamta `PARK_POINTS = ["ActivePowerMeter", "ActivePower", "IrradiancePOA", "Availability"]`
- Utoka `save_park_data()` for nya kolumner (bakatkompabilitet: gamla CSV:er med bara 2 kolumner maste fortfarande funka)
- Ny funktion `fetch_weather_timeseries(park_key)` som anvander WS-objekt-ID
- Ny funktion `save_weather_data()` -> `<park>_<zone>_weather.csv`
- Uppdatera `download_park()` att hamta bade park + vader
- Kora full re-synk (--backfill) for att fylla pa nya kolumner

### Steg 3: Operations data-modul (3-4h)
- Skapa `elpris/operations_dashboard_data.py`
- Loader-funktioner: `load_park_extended_data()`, `load_weather_data()`
- Berakningsfunktioner for Fas 1 features (F2, F10, F11, F14)
- Returnerar dict i samma format som ovriga dashboard-moduler

### Steg 4: Dashboard Operations-sektion grund (2-3h)
- CSS: `body.product-operations` fargvariabler
- HTML: ny tab-knapp "Operations"
- JS: `switchDashboard('operations')`, `buildOperationsSidebar()`, `renderOperations()`
- Bas-rendering: yearly/monthly drilldown

### Steg 5: Fas 1 features rendering (2-3h)
- `renderSpecificYield()`, `renderNegativePrice()`, `renderTrackerGain()`, `renderMeterLoss()`

### Steg 6: Fas 2 berakningar + rendering (4-5h)
- F1, F7, F13, F15 berakningar i operations_dashboard_data.py
- Render-funktioner i generate_dashboard_v2.py

### Steg 7: Fas 3 berakningar + rendering (4-5h)
- F8, F9, F5, F4

### Steg 8: Fas 4 invertenniva (4-6h)
- Utoka bazefield.py for inverter-synk
- F3, F6, F12

---

## 7. Risker och oppna fragor

1. **Vaderstations-ID:n** — Maste slas upp for alla parker for implementation. Horby HRB-WS1 ar verifierad (`1164CB70FB89D000`), ovriga behover ObjectStructureGetRequest.

2. **Backfill-tid** — Re-synk med fler datapunkter tar langre. Uppskattning: 30-60 min for alla parker.

3. **HTML-filstorlek** — Dashboard v2 ar redan ~17 MB. 15 nya features med data okar den kraftigt. Overvag: lazy loading av operations-data, eller separat HTML-fil.

4. **Specific Yield-berakning** — `power_mw` fran Bazefield ar genomsnittseffekt per 15-min-intervall. For att fa korrekt energi: `energy_MWh = power_mw * 0.25`. Men: noll-poster saknas i CSV (natter). Maste detta hanteras? Troligen inte — nolltimmar bidrar inte till yield.

5. **PR-formel** — Formeln i planen ar en forenkling (utan temperaturkorrektion). Racker detta? For inledande analys ja, men IEC 61724-standard kraver temperaturkorrektion.

6. **Export limit vs clipping** — 70% export limit innebar att clipping sker vid `kWp * 0.70 / 1000` MW, INTE vid full kapacitet. Formeln i F4 maste anvanda export limit, inte nameplate.

---

## 8. Verifiering

### Per-feature verifiering
- F2: Specific yield bor vara 50-150 kWh/kWp/manad (sommar hog, vinter lag)
- F1: PR bor vara 0.70-0.90 for valskotta parker
- F10: Negativa priser forekom framst i SE3 vintern 2024/2025
- F11: Tracker-gain bor vara 10-25% under sommar, nara 0% vinter
- F4: Clipping bor detekteras under hoginstralningsdagar (juni-augusti)

### End-to-end
1. `python3 bazefield_download.py --backfill` (re-synk med nya datapunkter)
2. `python3 generate_dashboard_v2.py`
3. Oppna dashboard, klicka "Operations"-fliken
4. Verifiera att features renderas med rimlig data
