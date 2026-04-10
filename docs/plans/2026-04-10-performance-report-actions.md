# Performance Report — Detaljerade åtgärder per steg

**Skapad:** 2026-04-10
**Komplement till:** `docs/plans/2026-04-10-performance-report-roadmap.md`

Detta dokument bryter ner roadmappen till konkreta åtgärder som kan tickas av en i taget. Varje steg har:
- Förkrav (vad som måste vara klart innan)
- Numrerade åtgärder (klistra-och-kör eller skriv-i-fil)
- Verifiering (hur vet du att det fungerade)
- "Done when"-kriterier

I slutet finns en **färdig SharePoint-prompt** för Claude Cowork som extraherar all produktdata på en gång.

---

## STEG 1 — Bazefield re-synk med utökat format

**Förkrav:** `BAZEFIELD_API_KEY` finns i `.env`

### Åtgärder

1. **Verifiera API-nyckel**
   ```bash
   cd "/c/Users/PontusSkog/Developer/electricity prices"
   grep BAZEFIELD_API_KEY .env
   ```
   Om saknas: kontakta IT/Operations för intern Bazefield API-nyckel.

2. **Backup nuvarande data**
   ```bash
   cp -r Resultat/profiler/parker/ Resultat/profiler/parker_backup_20260410/
   ```

3. **Verifiera att backfill-koden stödjer utökat format**
   ```bash
   grep -n "irradiance_poa\|active_power_mw\|availability" elpris/bazefield.py
   ```
   Förväntat: rader 176-200, 288 (PARK_CSV_FIELDS).

4. **Testa med en park först (Stenstorp — minsta dataset)**
   ```bash
   python bazefield_download.py --backfill --parks stenstorp
   ```
   Om det går fel: kolla felmeddelande, justera retry-tider i `bazefield.py:RETRY_*` om timeout.

5. **Verifiera utökat format i CSV**
   ```bash
   head -2 Resultat/profiler/parker/stenstorp_SE3.csv
   ```
   Förväntat: `timestamp,power_mw,active_power_mw,irradiance_poa,availability`

6. **Kör backfill för alla parker**
   ```bash
   python bazefield_download.py --backfill
   ```
   Tidsåtgång: 1-2 timmar.

7. **Synka väderdata också**
   ```bash
   python bazefield_download.py --backfill --weather
   ```
   Om `--weather`-flaggan inte finns: lägg till stöd i `bazefield_download.py` eller kör programmatiskt:
   ```python
   from elpris.bazefield import sync_weather_data, BAZEFIELD_PARKS
   for park in BAZEFIELD_PARKS:
       sync_weather_data(park["key"], full_history=True)
   ```

8. **Generera testrapport och verifiera nya sektioner**
   ```bash
   python generate_performance_report.py --park horby --month 2026-03
   start "" "Resultat/rapporter/performance_horby_SE4_2026-03.html"
   ```
   Verifiera visuellt att följande inte längre visar "—":
   - Sektion 1: Performance Ratio %, Verkningsgrad %, Instrålnings-gauge
   - Sektion 4: PR vs Temp-diagram med data
   - Sektion 6: Performance Index med staplar
   - Sektion 9: Loss waterfall med irradiance shortfall

### Done when
- [ ] Alla 8 parker har 5-kolumners CSV-format
- [ ] Väderfilerna `*_weather.csv` finns för alla 8 parker
- [ ] Hörby-rapport för mars 2026 visar PR-värde mellan 60-90%
- [ ] Backup-mappen kan tas bort

---

## STEG 2 — Fyll i parkmetadata

**Förkrav:** SharePoint-prompt nedan körts → JSON med produktdata

### Åtgärder

1. **Öppna `elpris/park_config.py` i editor**

2. **Klistra in värden från SharePoint-extraktet**
   För varje park, ersätt placeholders:
   - `module_type: "TBD"` → faktisk modell
   - `module_wp: None` → effekt i Watt-peak (typiskt 400-600)
   - `num_modules: None` → antal moduler
   - `inverter_model: "TBD"` → invertermodell
   - `num_inverters: None` → antal invertrar
   - `tilt_angle: None` → grader (för fixed-tilt parker)
   - `standard_pr: 0.80` → justera per park om dokumentation har annat värde

3. **Lägg till nya fält som dyker upp i SharePoint-data**
   Eventuellt:
   - `commissioning_date: "2024-08-15"` (när parken togs i drift)
   - `transformer_capacity_kva: 3200` (transformatorkapacitet)
   - `module_efficiency_pct: 21.0` (modulverkningsgrad)

   Om nya fält tillkommer, uppdatera även:
   - `performance_report_html.py` `_render_project_parameters()` (radera "TBD"/"None"-villkor)
   - Eventuellt rapportens KPI-tabell

4. **Verifiera ifyllning**
   ```bash
   python -c "
   from elpris.park_config import get_park_metadata, list_parks
   for park in list_parks():
       meta = get_park_metadata(park)
       missing = [k for k, v in meta.items() if v in (None, 'TBD')]
       if missing:
           print(f'{park}: saknar {missing}')
       else:
           print(f'{park}: OK')
   "
   ```

5. **Generera rapport och verifiera parametertabellen**
   ```bash
   python generate_performance_report.py --park horby --month 2026-03
   ```
   Sektion 1's "Key Project Parameters"-tabell ska nu visa alla rader utan "—".

6. **Commit:**
   ```bash
   git add elpris/park_config.py
   git commit -m "data: fill in park metadata from SharePoint datasheets"
   ```

### Done when
- [ ] Alla 8 parker har samtliga fält ifyllda (inga "TBD"/None kvar)
- [ ] Rapporten visar komplett parametertabell utan "—"
- [ ] Commit pushed

---

## STEG 3 — Manuella budgetöverstyrningar

**Förkrav:** Steg 1 klart (POA-data finns för PR-validering)

### Åtgärder

1. **Identifiera vilka parker som behöver overrides**
   Generera nuvarande rapporter:
   ```bash
   python generate_performance_report.py --all --month 2026-03
   ```
   För varje park, jämför `Faktisk MWh` vs `Budget MWh`. Stora avvikelser (>20%) tyder på att PVsyst-defaulten är fel för parken.

2. **Hämta korrekt PVsyst-output per park** (om tillgängligt)
   - Kolla `Resultat/sol-kalldata/` för parkspecifika PVsyst-PDF/CSV
   - Eller begär från projektledningen per park
   - Extrahera månadsproduktion (12 värden) och månadsinstrålning (12 värden)

3. **Lägg till overrides i `park_config.py`**
   ```python
   PARK_BUDGET_OVERRIDES = {
       "horby": {
           "2026-01": {"energy_mwh": 195.0, "irradiation_kwh_m2": 14.0, "pr_pct": 79.0},
           "2026-02": {"energy_mwh": 530.0, "irradiation_kwh_m2": 36.5, "pr_pct": 81.0},
           "2026-03": {"energy_mwh": 1520.0, "irradiation_kwh_m2": 105.0, "pr_pct": 82.0},
           "2026-04": {"energy_mwh": 2100.0, "irradiation_kwh_m2": 145.0, "pr_pct": 82.0},
           "2026-05": {"energy_mwh": 2650.0, "irradiation_kwh_m2": 180.0, "pr_pct": 82.0},
           "2026-06": {"energy_mwh": 2850.0, "irradiation_kwh_m2": 195.0, "pr_pct": 81.0},
           "2026-07": {"energy_mwh": 2780.0, "irradiation_kwh_m2": 190.0, "pr_pct": 80.0},
           "2026-08": {"energy_mwh": 2400.0, "irradiation_kwh_m2": 165.0, "pr_pct": 80.0},
           "2026-09": {"energy_mwh": 1750.0, "irradiation_kwh_m2": 120.0, "pr_pct": 81.0},
           "2026-10": {"energy_mwh": 1050.0, "irradiation_kwh_m2": 70.0, "pr_pct": 80.0},
           "2026-11": {"energy_mwh": 380.0, "irradiation_kwh_m2": 26.0, "pr_pct": 78.0},
           "2026-12": {"energy_mwh": 130.0, "irradiation_kwh_m2": 9.0, "pr_pct": 76.0},
       },
       # Repetera för andra parker som behöver det
   }
   ```

4. **Alternativt: Flytta till YAML-fil för enklare redigering**
   Om listan blir lång, flytta budgets till `Resultat/budgets/park_budgets.yaml`:
   ```yaml
   horby:
     2026-01: { energy_mwh: 195.0, irradiation_kwh_m2: 14.0, pr_pct: 79.0 }
     2026-02: { energy_mwh: 530.0, irradiation_kwh_m2: 36.5, pr_pct: 81.0 }
     # ...
   ```
   Och uppdatera `park_config.py:get_budget()` att läsa från fil.

5. **Verifiera att overrides används**
   ```python
   from elpris.park_config import get_budget
   b = get_budget("horby", 2026, 3)
   assert b["energy_mwh"] == 1520.0  # Should match override
   ```

6. **Regenerera rapporter och verifiera nya budget-värden**

### Done when
- [ ] Minst 4 parker har 12-månadersbudget i overrides
- [ ] Rapporterna visar de nya budgetvärdena
- [ ] Avvikelser mellan budget och faktisk är under 15% för 2026-03

---

## STEG 4 — Modultemperatur via väderdata

**Förkrav:** Steg 1 klart (POA-data behövs för Sandia-formeln)

### Åtgärder

1. **Verifiera om Bazefield har omgivningstemperatur**
   - Logga in på Bazefield UI
   - Navigera till valfri parks väderstation (t.ex. "HRB-WS1" för Hörby)
   - Lista alla domain points
   - Sök efter "AmbientTemperature", "AirTemperature", "T_Amb" eller liknande

2. **Alternativ A — Bazefield har temperatur:**
   - Lägg till i `elpris/bazefield.py:WEATHER_POINTS_MAP`:
     ```python
     WEATHER_POINTS_MAP = {
         "IrradianceGHI": "ghi",
         "WindSpeed": "wind_speed",
         "Humidity": "humidity",
         "AmbientTemperature": "ambient_temp_c",  # NY
     }
     ```
   - Uppdatera `WEATHER_CSV_FIELDS` med `ambient_temp_c`
   - Uppdatera `save_weather_data()` att skriva nya kolumnen
   - Kör `bazefield_download.py --backfill --weather` för att resynka

3. **Alternativ B — Bazefield har INTE temperatur (SMHI-fallback):**
   - Skapa `elpris/smhi.py`:
     ```python
     """SMHI Open Data klient för temperaturhistorik."""
     import requests
     from datetime import datetime, date
     
     SMHI_BASE = "https://opendata-download-metobs.smhi.se/api"
     
     # Närmaste SMHI-station per park (slå upp på smhi.se/data → Meteorologi → Lufttemperatur)
     PARK_SMHI_STATION = {
         "horby": "53430",      # Hörby (närmsta)
         "fjallskar": "127390", # TBD
         # ... fyll i resten
     }
     
     def fetch_temperature_history(station_id: str, start: date, end: date) -> list[dict]:
         """Hämta timvis lufttemperatur från SMHI."""
         # Parameter 1 = lufttemperatur, period "corrected-archive"
         url = f"{SMHI_BASE}/version/1.0/parameter/1/station/{station_id}/period/corrected-archive/data.csv"
         r = requests.get(url, timeout=30)
         r.raise_for_status()
         # Parse CSV och filtrera till start..end
         ...
     ```
   - Lagra resultat i `Resultat/marknadsdata/smhi/temperature_{park}.csv`
   - Skapa `smhi_download.py` CLI-skript

4. **Uppdatera `performance_report_data.py`**
   I `_compute_module_temp()`-funktionen, ladda ambient temp från CSV om tillgänglig:
   ```python
   def _load_ambient_temp(park_key: str, zone: str) -> dict[str, float]:
       """Returnera dict {timestamp_iso: ambient_temp_c}."""
       weather_path = PARKS_PROFILE_DIR / f"{park_key}_{zone}_weather.csv"
       if not weather_path.exists():
           return {}
       result = {}
       with open(weather_path, encoding="utf-8") as f:
           reader = csv.DictReader(f)
           for row in reader:
               if "ambient_temp_c" in row and row["ambient_temp_c"]:
                   result[row["timestamp"]] = float(row["ambient_temp_c"])
       return result
   ```

5. **Verifiera att modultemperatur nu är beräknad**
   ```bash
   python -c "
   from elpris.performance_report_data import generate_report
   r = generate_report('horby', 2026, 3)
   print(f'Avg module temp: {r.avg_module_temp_c}')  # Should NOT be None
   "
   ```

### Done when
- [ ] Antingen Bazefield eller SMHI ger ambient temperatur
- [ ] `MonthlyReport.avg_module_temp_c` är inte None för parker med data
- [ ] Sektion 4 (PR vs Temp) visar verklig modultemperatur, inte 0

---

## STEG 5 — SCADA-integration (Sungrow iSolarCloud)

**Förkrav:** Inverter-fabrikat verifierat per park (se SharePoint-prompt)

### Åtgärder

1. **Skaffa API-credentials**
   - Begär API-key + secret från Sungrow Support (eller via Operations om Svea har avtal)
   - Vissa kunder måste begära API-aktivering manuellt
   - Lägg i `.env`:
     ```
     SUNGROW_API_KEY=...
     SUNGROW_API_SECRET=...
     SUNGROW_BASE_URL=https://gateway.isolarcloud.com.hk/openapi
     ```

2. **Verifiera tillgång**
   ```bash
   curl -X POST "$SUNGROW_BASE_URL/getPlantList" \
     -H "x-access-key: $SUNGROW_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"sys_code": "901", "appkey": "..."}'
   ```

3. **Mappa Bazefield park-IDs till Sungrow plant-IDs**
   - Sungrows "plantId" är annat än Bazefields ID
   - Skapa mapping i `elpris/config.py`:
     ```python
     SUNGROW_PLANT_IDS = {
         "horby": "1234567",
         "fjallskar": "2345678",
         # ...
     }
     ```

4. **Skapa `elpris/sungrow.py`**
   ```python
   """Sungrow iSolarCloud API-klient."""
   import requests
   from datetime import date
   
   class SungrowClient:
       def __init__(self, api_key: str, api_secret: str, base_url: str):
           self.api_key = api_key
           self.api_secret = api_secret
           self.base_url = base_url
           self.token = None
       
       def login(self): ...
       def list_devices(self, plant_id: str) -> list[dict]: ...
       def fetch_device_yield(self, device_id: str, start: date, end: date) -> list[dict]: ...
       def fetch_alarms(self, plant_id: str, start: date, end: date) -> list[dict]: ...
   ```

5. **Skapa `sungrow_download.py` CLI**
   ```bash
   python sungrow_download.py --park horby --start 2026-03-01 --end 2026-03-31
   ```
   Sparar:
   - `Resultat/marknadsdata/sungrow/inverters/horby/inv_*_yield.csv`
   - `Resultat/marknadsdata/sungrow/alarms/horby_2026-03.csv`

6. **Utöka `MonthlyReport` med inverter-data**
   ```python
   @dataclass
   class InverterDailyData:
       inverter_id: str
       date: str
       yield_kwh: float
       efficiency_pct: float
   
   @dataclass
   class AlarmRecord:
       inverter_id: str
       timestamp: datetime
       code: int
       description: str
       duration_min: int
       severity: str
   
   # I MonthlyReport:
   inverters: list[InverterDailyData] = field(default_factory=list)
   alarms: list[AlarmRecord] = field(default_factory=list)
   faults: list[FaultRecord] = field(default_factory=list)
   ```

7. **Aktivera platshållarsektioner i `performance_report_html.py`**
   - Sektion 14: ersätt platshållare med tabell + ranking-card
   - Sektion 15: ersätt platshållare med multi-line trend + heatmap
   - Sektion 18: ersätt platshållare med KPI-kort + treemap + timeline
   - Sektion 19: ersätt platshållare med statistiktabell + cirkeldiagram

8. **Testa end-to-end**
   ```bash
   python sungrow_download.py --all --start 2026-03-01 --end 2026-03-31
   python generate_performance_report.py --park horby --month 2026-03
   ```
   Verifiera att sektion 14-15, 18-19 nu har data.

### Done when
- [ ] Sungrow API svarar för minst en park
- [ ] Inverter-data lagras i CSV per park
- [ ] Sektion 14, 15, 18, 19 i rapporten visar data istället för platshållare
- [ ] Alarm/fault-statistik i rapport matchar Sungrow UI

---

## STEG 6 — PPM Schedule (statisk konfiguration)

**Förkrav:** PPM-avtal/serviceavtal från Operations

### Åtgärder

1. **Skaffa PPM-listan från Operations**
   - Begär kopia av PPM-avtalet per park
   - Eller fråga vem som hanterar förebyggande underhåll
   - Notera frekvenser: monthly, quarterly, biannual, annual

2. **Skapa `elpris/ppm_schedule.py`**
   ```python
   """Statisk PPM-konfiguration per park."""
   from typing import Literal
   
   Frequency = Literal["monthly", "quarterly", "biannual", "annual"]
   
   PPM_TASKS_DEFAULT = [
       {
           "task": "Visuell inspektion paneler",
           "frequency": "biannual",
           "scheduled_months": [3, 9],
       },
       {
           "task": "Termografi MV/HV-anläggning",
           "frequency": "annual",
           "scheduled_months": [6],
       },
       {
           "task": "Vegetationskontroll",
           "frequency": "biannual", 
           "scheduled_months": [5, 9],
       },
       {
           "task": "Inverter-underhåll",
           "frequency": "annual",
           "scheduled_months": [10],
       },
       {
           "task": "Brandskyddskontroll",
           "frequency": "annual",
           "scheduled_months": [6],
       },
       # ... lägg till från PPM-avtal
   ]
   
   # Per-park-overrides om nödvändigt
   PARK_PPM_OVERRIDES: dict[str, list[dict]] = {}
   
   def get_ppm_schedule(park_key: str) -> list[dict]:
       """Returnera PPM-listan för en park."""
       return PARK_PPM_OVERRIDES.get(park_key, PPM_TASKS_DEFAULT)
   ```

3. **Aktivera sektion 16 i `performance_report_html.py`**
   I `_render_ppm_schedule()`, rita en kalendermatris:
   - Rader = PPM-tasks
   - Kolumner = Jan-Dec
   - Celler = "📅 Schd" om uppgiften är schemalagd den månaden
   - Highlighta nuvarande månad

4. **Verifiera**
   ```bash
   python generate_performance_report.py --park horby --month 2026-03
   ```
   Sektion 16 ska visa kalendermatris med PPM-tasks.

### Done when
- [ ] Minst 6 PPM-tasks definierade i `ppm_schedule.py`
- [ ] Sektion 16 visar matris med korrekta scheman
- [ ] Inga "Data ej tillgänglig"-platshållare kvar

---

## STEG 7 — Incidentlogg

**Förkrav:** Beslut om inmatningsmetod (manuell JSON eller ticketsystem)

### Åtgärder

1. **Bestäm inmatningsmetod**
   - Alternativ A: Manuell JSON-fil per månad (enklast)
   - Alternativ B: Excel-mall som konverteras till JSON
   - Alternativ C: Jira/ServiceNow API-integration (mest robust)

2. **Skapa schemat (Alternativ A)**
   Filplats: `Resultat/operationsdata/incidenter/{park}_{YYYY-MM}.json`
   ```json
   {
     "incidents": [
       {
         "date": "2026-03-14",
         "issue_id": 574,
         "fault_type": "Inverter Failure",
         "equipment": "INV 1-4",
         "description": "Inverter offline",
         "start": "2026-03-14T17:36:00",
         "end": "2026-03-14T17:44:00",
         "priority": "Med",
         "status": "Resolved",
         "gen_loss_kwh": 0
       }
     ],
     "work_carried_out": [
       {
         "date": "2026-03-22",
         "activity": "Visuell inspektion paneler",
         "status": "Completed",
         "remarks": "Inga avvikelser"
       }
     ]
   }
   ```

3. **Skapa `elpris/incidents.py`**
   ```python
   """Inläsning av incidentdata."""
   import json
   from pathlib import Path
   from .config import RESULTAT_DIR
   
   INCIDENTS_DIR = RESULTAT_DIR / "operationsdata" / "incidenter"
   
   def load_incidents(park_key: str, year: int, month: int) -> dict:
       """Returnera {incidents: [...], work_carried_out: [...]}."""
       path = INCIDENTS_DIR / f"{park_key}_{year:04d}-{month:02d}.json"
       if not path.exists():
           return {"incidents": [], "work_carried_out": []}
       return json.loads(path.read_text(encoding="utf-8"))
   ```

4. **Utöka `MonthlyReport`**
   ```python
   incidents: list[dict] = field(default_factory=list)
   work_carried_out: list[dict] = field(default_factory=list)
   ```

5. **Aktivera sektion 17 i HTML**
   Rita två tabeller:
   - "Incidenter under månaden" (med priority-färgkoder)
   - "Arbete utfört på siten"

6. **Skapa Excel-mall för enkel inmatning** (optional)
   Filplats: `Resultat/operationsdata/incidenter/_template.xlsx`
   Skapa script `incidents_excel_to_json.py` som konverterar Excel → JSON.

### Done when
- [ ] Schema definierat
- [ ] Minst en JSON-fil skapad för testparker
- [ ] Sektion 17 i rapport visar tabeller med data

---

## STEG 8 — LLM-genererad Executive Summary

**Förkrav:** Anthropic API-nyckel i `.env`

### Åtgärder

1. **Verifiera/skapa `ANTHROPIC_API_KEY` i `.env`**

2. **Installera anthropic SDK**
   ```bash
   pip install anthropic
   ```
   Lägg till i `requirements.txt`.

3. **Skapa `elpris/llm_summary.py`**
   ```python
   """LLM-genererad executive summary för månadsrapporter."""
   import os
   from anthropic import Anthropic
   from .performance_report_data import MonthlyReport
   
   def generate_executive_summary(report: MonthlyReport) -> str:
       """Generera prosaisk månadssammanfattning på svenska via Claude."""
       client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
       
       prompt = f"""Skriv en professionell månadssammanfattning på svenska för 
   solparken {report.park_display_name} ({report.zone}, {report.capacity_mwp:.1f} MWp).
   
   PERIOD: {report.month_name} {report.year}
   
   NYCKELTAL:
   - Faktisk produktion: {report.actual_energy_mwh:.0f} MWh
   - Budget: {report.budget_energy_mwh:.0f} MWh
   - Avvikelse: {(report.actual_energy_mwh / report.budget_energy_mwh - 1) * 100:+.1f}%
   - Specific Yield: {report.yield_kwh_kwp:.1f} kWh/kWp
   - PR: {report.performance_ratio_pct or 'N/A'}%
   - Verkningsgrad: {report.efficiency_pct or 'N/A'}%
   
   FÖRLUSTER (MWh):
   - Curtailment: {report.losses.curtailment_loss_mwh:.1f}
   - Instrålningsunderskott: {report.losses.irradiance_shortfall_loss_mwh:.1f}
   - Tillgänglighetsförlust: {report.losses.availability_loss_mwh:.1f}
   - Temperaturförlust: {report.losses.temperature_loss_mwh:.1f}
   - Övriga förluster: {report.losses.other_losses_mwh:.1f}
   
   STRUKTUR (3 stycken):
   1. **Översikt** — Vad hände denna månad? Vad var huvuddrivare?
   2. **Viktiga observationer** — Punktlista med 3-5 insikter (kursivera siffror)
   3. **Sammanfattande bedömning** — Är parken på rätt kurs? YTD-perspektiv?
   
   TON: Saklig, koncis, professionell. Använd "parken" eller parknamnet, inte "vi".
   FORMAT: Markdown med rubriker (**fet**) och punktlistor.
   LÄNGD: Max 250 ord.
   """
       
       response = client.messages.create(
           model="claude-sonnet-4-6",
           max_tokens=600,
           messages=[{"role": "user", "content": prompt}]
       )
       return response.content[0].text
   ```

4. **Cacha resultat så samma rapport inte regenereras**
   ```python
   # Spara cache i Resultat/cache/llm_summary/{park}_{year}-{month}.txt
   # Kolla om filen finns innan API-anrop
   ```

5. **Integrera i `performance_report_html.py:_render_executive_summary()`**
   Anropa `generate_executive_summary(report)` istället för mall-text.

6. **Verifiera kostnaden**
   - Sonnet 4.6: ~$3 per million input tokens
   - Per rapport: ~500 input tokens, 600 output → ~$0.01
   - 8 parker × 12 månader = $0.96/år — försumbart

### Done when
- [ ] LLM-genererad text visas i sektion 19
- [ ] Cache fungerar (andra körning är instant)
- [ ] Texten är på korrekt svenska och täcker alla 3 stycken

---

## STEG 9 — Automatisk månadsvis generering

**Förkrav:** Steg 1 körts åtminstone en gång (data finns)

### Åtgärder

1. **Skapa wrapper-skript `monthly_reports.bat`**
   ```batch
   @echo off
   cd /d "C:\Users\PontusSkog\Developer\electricity prices"
   call .venv\Scripts\activate.bat
   
   REM Synka senaste data
   python bazefield_download.py
   python update_all.py
   
   REM Generera rapporter (default = senaste fullständiga månad)
   python generate_performance_report.py --all
   
   REM Logga resultat
   echo %DATE% %TIME% - Reports generated >> reports.log
   ```

2. **Schemalägg via Windows Task Scheduler**
   ```powershell
   schtasks /create ^
     /sc monthly /d 1 /st 06:00 ^
     /tn "Solpark Performance Reports" ^
     /tr "C:\Users\PontusSkog\Developer\electricity prices\monthly_reports.bat" ^
     /rl HIGHEST
   ```

3. **Eller använd Claude Code's CronCreate**
   ```python
   # I Claude Code-sessionen
   CronCreate(
       name="monthly_performance_reports",
       schedule="0 6 1 * *",  # 1:a varje månad kl 06:00
       command="python generate_performance_report.py --all"
   )
   ```

4. **Email-distribution** (optional)
   - Använd MS Graph/Outlook MCP för att skicka rapport-länkar
   - Eller publicera till SharePoint-mapp och dela länk
   ```python
   # email_reports.py
   from elpris.park_config import list_parks
   from datetime import date
   
   def send_monthly_reports(year: int, month: int):
       for park in list_parks():
           filepath = f"Resultat/rapporter/performance_{park}_{zone}_{year}-{month:02d}.html"
           # Bifoga eller länka till SharePoint
           # Skicka via Outlook MCP
   ```

### Done when
- [ ] Schemalagd uppgift körs automatiskt
- [ ] Loggfil visar lyckade körningar
- [ ] Asset managers får länk/notis när nya rapporter genererats

---

## STEG 10 — PDF-export

**Förkrav:** Steg 1-3 klara (rapporten är fullständig)

### Åtgärder

1. **Installera Playwright** (om inte redan installerat)
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **Skapa `elpris/pdf_export.py`**
   ```python
   """Export av HTML-rapport till PDF via headless Chromium."""
   import asyncio
   from pathlib import Path
   from playwright.async_api import async_playwright
   
   async def html_to_pdf(html_path: Path, pdf_path: Path):
       """Konvertera HTML-fil till PDF."""
       async with async_playwright() as p:
           browser = await p.chromium.launch()
           page = await browser.new_page()
           await page.goto(f"file://{html_path.absolute()}")
           await page.wait_for_load_state("networkidle")
           # Vänta extra på Plotly-rendering
           await page.wait_for_timeout(2000)
           await page.pdf(
               path=str(pdf_path),
               format="A4",
               landscape=True,
               print_background=True,
               margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"},
           )
           await browser.close()
   
   def export_to_pdf(html_path: Path) -> Path:
       """Synkron wrapper, returnerar PDF-sökväg."""
       pdf_path = html_path.with_suffix(".pdf")
       asyncio.run(html_to_pdf(html_path, pdf_path))
       return pdf_path
   ```

3. **Lägg till `--pdf`-flagga i `generate_performance_report.py`**
   ```python
   parser.add_argument("--pdf", action="store_true", help="Exportera även till PDF")
   
   # Efter HTML-generering:
   if args.pdf:
       from elpris.pdf_export import export_to_pdf
       pdf_path = export_to_pdf(filepath)
       print(f"  ✓ {pdf_path}")
   ```

4. **Verifiera Plotly-rendering i PDF**
   - Kör: `python generate_performance_report.py --park horby --month 2026-03 --pdf`
   - Öppna PDF:n
   - Verifiera att alla diagram syns (Plotly är JS, kan vara tomt om timing är fel)
   - Justera `wait_for_timeout()` om diagram inte renderas

5. **Optimera filstorlek**
   - PDF kan bli stor (5-15 MB) pga embedded fonts
   - Optional: kör `pdftk` eller `qpdf` för komprimering

### Done when
- [ ] PDF genereras tillsammans med HTML när `--pdf` flagga används
- [ ] Alla 19 sektioner visas korrekt i PDF
- [ ] Filstorlek under 15 MB
- [ ] PDF kan delas med externa intressenter

---

# SHAREPOINT-PROMPT FÖR CLAUDE COWORK

Klistra in detta i Claude Cowork (eller annan agent med SharePoint-åtkomst) för att extrahera all produktdata för parkmetadata-ifyllningen i Steg 2 och inverter-fabrikat för Steg 5.

```
Jag behöver extrahera teknisk produktdata för Svea Solars 8 svenska solparker
till en konfigurationsfil. Sök i SharePoint efter relevant dokumentation.

PARKER (med alternativa namn):
1. Hörby (Horby) - SE4, ~18.1 MWp DC, Skåne
2. Fjällskär (Fjallskar) - SE3, ~20.7 MWp DC, Ångermanland
3. Björke (Bjorke) - SE3, ~6.9 MWp DC, Västra Götaland
4. Agerum - SE4, ~8.8 MWp DC, Blekinge
5. Hova - SE3, ~5.9 MWp DC, Västra Götaland (TRACKER-park)
6. Skäkelbacken (Skakelbacken) - SE3, ~6.5 MWp DC, Västra Götaland
7. Stenstorp - SE3, ~1.1 MWp DC, Västra Götaland
8. Tången (Tangen) - SE4, ~6.7 MWp DC, Halland

VAD SOM SKA HITTAS PER PARK:

Tekniska specifikationer:
- module_type: Modulmärke och modell (t.ex. "Longi LR5-72HBD-540M")
- module_wp: Modulens nominella effekt i Watt-peak (t.ex. 540)
- num_modules: Totalt antal moduler i parken
- inverter_model: Invertermärke och modell (t.ex. "Sungrow SG250HX")
- inverter_manufacturer: Bara fabrikat (Sungrow/SMA/Huawei/Schneider/etc.)
- num_inverters: Totalt antal invertrar
- tilt_angle: Lutningsvinkel i grader (för fixed-tilt parker)
- azimuth: Riktning i grader (180 = söder)
- tracking_type: "fixed", "single-axis", "dual-axis", eller "none"
- transformer_capacity_kva: Transformatorkapacitet i kVA (t.ex. 3200)
- transformer_count: Antal transformatorer
- string_inverter_or_central: "string" eller "central"

Driftsdata:
- commissioning_date: Driftssättningsdatum (YYYY-MM-DD)
- ppa_start_date: PPA/avtalsstart om relevant
- expected_annual_yield_kwh_kwp: Förväntad årlig produktion (kWh/kWp/år) från PVsyst
- expected_pr_pct: Förväntad Performance Ratio från PVsyst (typiskt 78-85%)

GPS och plats:
- latitude: Decimalgrader (t.ex. 55.8456)
- longitude: Decimalgrader (t.ex. 13.6589)
- exact_location_name: Exakt ort (t.ex. "Hörby kommun")

Avtal:
- ppm_provider: Vem utför förebyggande underhåll (PPM)
- scada_system: Vilket övervakningssystem (Bazefield + ev. annat)
- inverter_api_access: Har Svea API-åtkomst till invertertillverkaren? (Ja/Nej/Okänt)

VAR ATT LETA I SHAREPOINT:
1. Sök på parknamn (både svenska och engelska varianter)
2. Letar efter dokumenttyper:
   - PVsyst-rapporter (PDF, oftast namngivna med datum + parknamn)
   - Datasheets för moduler/invertrar (typically en mapp "Data Sheets" per park)
   - EPC-kontrakt / Construction contracts
   - As-built-dokumentation
   - Commissioning reports
   - O&M Manuals
   - Asset Management dokument
3. Vanliga mappnamn att söka i:
   - "Solar Plants" / "Solparker" / "Assets"
   - "Project Documentation"
   - "Technical"
   - "Operations" / "O&M"

OUTPUTFORMAT:
Returnera en Python-dict (klistra-och-kör-format) som denna:

```python
PARK_PRODUCT_DATA = {
    "horby": {
        "module_type": "Longi LR5-72HBD-540M",
        "module_wp": 540,
        "num_modules": 33548,
        "inverter_model": "Sungrow SG250HX",
        "inverter_manufacturer": "Sungrow",
        "num_inverters": 72,
        "tilt_angle": 20,
        "azimuth": 180,
        "tracking_type": "fixed",
        "transformer_capacity_kva": 3200,
        "transformer_count": 2,
        "string_inverter_or_central": "string",
        "commissioning_date": "2024-08-15",
        "ppa_start_date": "2024-09-01",
        "expected_annual_yield_kwh_kwp": 1050,
        "expected_pr_pct": 81.5,
        "latitude": 55.8456,
        "longitude": 13.6589,
        "exact_location_name": "Hörby kommun",
        "ppm_provider": "K-energy AB",
        "scada_system": "Bazefield + Sungrow iSolarCloud",
        "inverter_api_access": "Ja",
        "source_documents": [
            "PVsyst Report - Horby - 2024-03-15.pdf",
            "EPC Contract - Horby - signed 2023-11.pdf",
            "Commissioning Report - Horby - 2024-08-15.pdf"
        ]
    },
    "fjallskar": {
        # ... samma fält
    },
    # ... alla 8 parker
}
```

VIKTIGT:
- Om ett fält inte hittas, sätt det till None (inte tom sträng)
- Lista källdokument under "source_documents" så jag kan verifiera
- Om olika dokument säger olika, gå med det senaste eller markera "FÖRSÖK MED: X eller Y"
- Returnera så mycket data du kan hitta — partial är bättre än inget
- Om en park inte hittas alls, returnera {"NOT_FOUND_IN_SHAREPOINT": true}
```

---

# Användning

När du fått tillbaka data från Claude Cowork:

1. **Spara JSON-resultatet** i `Resultat/parkdata/sharepoint_extract_2026-04-10.json`

2. **Mappa till `park_config.py`-format**:
   ```python
   # I en Python-prompt eller skript
   import json
   data = json.loads(open("Resultat/parkdata/sharepoint_extract_2026-04-10.json").read())
   for park_key, fields in data.items():
       print(f'"{park_key}": {{')
       print(f'    "display_name": "...",')
       print(f'    "module_type": "{fields.get("module_type", "TBD")}",')
       print(f'    "module_wp": {fields.get("module_wp")},')
       print(f'    "num_modules": {fields.get("num_modules")},')
       print(f'    "inverter_model": "{fields.get("inverter_model", "TBD")}",')
       print(f'    "num_inverters": {fields.get("num_inverters")},')
       print(f'    "tilt_angle": {fields.get("tilt_angle")},')
       print(f'    "tracking": {fields.get("tracking_type") != "fixed"},')
       print(f'    "standard_pr": {fields.get("expected_pr_pct", 80) / 100},')
       print(f'    # ...')
       print(f'}},')
   ```

3. **Granska och commit** uppdaterad `park_config.py`

4. **Kontaktlista för Steg 5** (SCADA):
   Använd `inverter_manufacturer` per park för att veta vilka API:er som behövs:
   - Sungrow → iSolarCloud API
   - SMA → Sunny Portal API / Modbus
   - Huawei → FusionSolar API
   - Schneider → EcoStruxure
   - Etc.
