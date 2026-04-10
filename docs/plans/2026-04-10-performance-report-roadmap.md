# Performance Report — Roadmap & Återstående arbete

**Skapad:** 2026-04-10
**Status:** MVP komplett, fas 2 förbereds
**Relaterad plan:** `~/.claude/plans/synthetic-mixing-bee.md`

## Bakgrund

Månadsrapport per solpark är implementerad som MVP (commits 6588c22..b863fdb). Rapporten genereras med:

```bash
python generate_performance_report.py --park horby --month 2026-03
python generate_performance_report.py --all --month 2026-03
```

Output: `Resultat/rapporter/performance_{park}_{zone}_{YYYY-MM}.html`

19 sektioner är implementerade (13 med data, 5 platshållare för SCADA-data, 1 executive summary). De flesta sektioner producerar korrekt utdata för parker med befintlig Bazefield-data. Vissa sektioner (PR, PI, instrålning, förlustanalys) visar "—" eller tomma diagram tills data är utökad — se steg 1 nedan.

---

## Steg 1: Bazefield re-synk med utökat format

**Prioritet:** HÖG — låser upp ~5 sektioner som idag är delvis tomma

**Status (uppdaterat 2026-04-10):** POA-datakvalitetsproblem upptäckt under pilot. Asset Management bekräftade två issues:
1. `IrradiancePOA` på park-objektet är average av flera sensorer där några rapporterar 0 → ger ~50% av verkliga värden. Zaira jobbar på fix.
2. `ActivePower` är opålitlig pga icke-kommunicerande invertrar → använd alltid `ActivePowerMeter`.

**Workaround:** `elpris/bazefield.py:PARK_IRRADIANCE_OVERRIDES` mappar varje park till en bättre POA-källa (TS/WS/SATWST child-object). Auto-discovered via `ObjectStructureGetRequest` API. Hörby verifierad: PR gick från 204% (broken) till 89% (korrekt) — i linje med PVsyst budget 85%.

**Bakgrund:** Nuvarande CSV-filer i `Resultat/profiler/parker/` har bara `timestamp,power_mw`. `bazefield.py` stödjer redan utökat format med 5 kolumner, men backfill har inte körts. När detta körs aktiveras automatiskt:

| Sektion | Vad som aktiveras |
|---------|-------------------|
| Sektion 1 (Summary) | Performance Ratio %, Verkningsgrad %, Instrålningsgauge |
| Sektion 4 (PR vs Temp) | Daglig PR-graf och tabell |
| Sektion 5 (Expected vs Actual) | Förväntad produktion baserad på faktisk instrålning (inte bara budget) |
| Sektion 6 (Performance Index) | PI-staplar med korrekta värden |
| Sektion 7 (Efficiency) | Båda area-charts |
| Sektion 8 (Power vs Irradiation) | Bästa/sämsta dag med instrålningskurva |
| Sektion 9-11 (Förlustanalys) | Korrekt waterfall med irradiance shortfall, availability loss |

### Förkrav
1. `BAZEFIELD_API_KEY` måste vara satt i `.env`-filen
2. Verifiera koden i `elpris/bazefield.py:176-200` (funktionen `fetch_extended_park_data`)
3. CSV-fältnamn: `timestamp, power_mw, active_power_mw, irradiance_poa, availability` (definierad på rad 288)

### Körinstruktion
```bash
# Steg 1: Verifiera att API-nyckeln finns
grep BAZEFIELD_API_KEY .env

# Steg 2: Backup nuvarande CSV (säkerhet — kan ta bort efter verifiering)
cp -r Resultat/profiler/parker/ Resultat/profiler/parker_backup_$(date +%Y%m%d)/

# Steg 3: Kör backfill med utökat format för alla parker
python bazefield_download.py --backfill

# Steg 4: Verifiera att utökat format finns i CSV
head -2 Resultat/profiler/parker/horby_SE4.csv
# Förväntat: timestamp,power_mw,active_power_mw,irradiance_poa,availability
```

### Verifiera resultat
```bash
# Kör rapport och kontrollera att PR/PI inte längre är tomma
python generate_performance_report.py --park horby --month 2026-03
# Öppna HTML och verifiera sektion 1, 4, 5, 6, 7, 8, 9, 10
```

### Tidsåtgång
- Inkrementell backfill (en månad): ~5-15 minuter
- Full historik (sedan augusti 2024): ~1-2 timmar pga API rate limiting

### Risker
- API rate limiting kan ge timeout — koden i `bazefield.py` har retry-logik (3 försök, exponential backoff)
- Eventuellt ändra `--start` för att begränsa tidsspann om något går snett
- Behåll backup tills full verifiering genomförd

---

## Steg 2: Fyll i parkmetadata

**Prioritet:** MEDEL — kosmetiskt men viktigt för rapportens "Key Project Parameters"-tabell

**Bakgrund:** I `elpris/park_config.py` är de flesta `PARK_METADATA`-fält "TBD" eller `None`. Detta gör att rapportens parametertabell visar "—" för dessa rader. Information finns troligen i SveaSolar-vaulten eller i parkens dokumentation.

### Fält som behöver fyllas i per park

```python
# Exempel för Hörby - se elpris/park_config.py
"horby": {
    "display_name": "Hörby",                    # ✓ klart
    "location": "Hörby, Skåne",                 # ✓ klart  
    "module_type": "TBD",                        # ❌ FYLL I (t.ex. "Longi LR5-72HBD")
    "module_wp": None,                           # ❌ FYLL I (t.ex. 540)
    "num_modules": None,                         # ❌ FYLL I (t.ex. 33548)
    "inverter_model": "TBD",                     # ❌ FYLL I (t.ex. "Sungrow SG250HX")
    "num_inverters": None,                       # ❌ FYLL I (t.ex. 72)
    "tilt_angle": None,                          # ❌ FYLL I (grader, t.ex. 20)
    "tracking": False,                           # ✓ klart för alla
    "standard_pr": 0.80,                         # ✓ kan justeras per park (0.78-0.83 normalt)
    "profile_type": "south",                     # ✓ klart (hova: tracker)
}
```

### Var man hittar uppgifterna
1. **SveaSolarObsidianv2-vaulten:** `Projects/Elpris/` eller park-specifika noter
2. **Bazefield UI:** Parkens "Asset Information"-flik
3. **PVsyst-källdata:** `Resultat/sol-kalldata/` för Lundby, Hova, Böda
4. **Avtal/EPC-dokumentation:** Kontakta projektledningen

### Verifiering
Efter ifyllning, generera en rapport och kontrollera sektion 1's "Key Project Parameters"-tabell:
```bash
python generate_performance_report.py --park horby --month 2026-03
# Öppna HTML, scrolla till parametertabell, verifiera att alla rader visar värden
```

### Optional: Justera standard_pr per park
Olika parker har olika baseline-PR beroende på systemdesign:
- Tracker (Hova): typiskt 0.83-0.85
- Sydmonterade fixed-tilt: 0.78-0.82
- Öst-väst: 0.76-0.80

Justera `standard_pr` baserat på första 3-6 månaders data när Performance Ratio finns tillgänglig.

---

## Steg 3: Manuella budgetöverstyrningar

**Prioritet:** MEDEL — när PVsyst-default inte räcker

**Bakgrund:** PVsyst TMY-budget är generisk per profiltyp (south/ew/tracker). För finmaskig styrning kan parkspecifika budgets sättas i `PARK_BUDGET_OVERRIDES` i `elpris/park_config.py`.

### Användningsfall
- När en park har specifik förväntad produktion från senaste PVsyst-simulering
- För avtalad produktionsgaranti vs PPA
- Vid degraderingsjustering år 2+ (-0.5% per år typiskt)

### Format
```python
PARK_BUDGET_OVERRIDES = {
    "horby": {
        "2026-01": {"energy_mwh": 195.0, "irradiation_kwh_m2": 14.0, "pr_pct": 79.0},
        "2026-02": {"energy_mwh": 530.0, "irradiation_kwh_m2": 36.5, "pr_pct": 81.0},
        "2026-03": {"energy_mwh": 1520.0, "irradiation_kwh_m2": 105.0, "pr_pct": 82.0},
        # ... resten av året
    },
    "hova": {
        "2026-03": {"energy_mwh": 580.0, "irradiation_kwh_m2": 110.0, "pr_pct": 84.0},
    },
}
```

### Hierarki
1. Kollar `PARK_BUDGET_OVERRIDES[park_key]["YYYY-MM"]` först
2. Faller tillbaka på `_load_pvsyst_budget(profile_type, capacity_kwp, month)` om ingen override

### Förslag
Skapa en separat YAML/JSON-fil för budgets om listan blir lång. Konvertera `park_config.py:get_budget()` att läsa från fil istället för dict.

---

## Steg 4: Modultemperatur via väderdata

**Prioritet:** LÅG — kosmetiskt, ger mer exakt PR-temperaturkorrigering

**Bakgrund:** `performance_report_data.py` använder en förenklad Sandia-modell med antagen omgivningstemperatur (10 °C för Sverige):
```python
T_module = T_ambient + 0.03 * POA_irradiance
```

För korrekt modultemperatur behövs faktisk omgivningstemperatur från Bazefields väderstationer.

### Vad som behövs
1. **Bazefield weather-CSV:** Filer som `Resultat/profiler/parker/{park}_{zone}_weather.csv` med kolumner `timestamp,ghi,wind_speed,humidity`
2. **Problem:** Ambient temperature finns inte i nuvarande Bazefield-vyn — endast GHI, vind, fukt
3. **Lösning A:** Lägg till "AmbientTemperature" eller liknande domain point i `bazefield.py:WEATHER_POINTS_MAP`
4. **Lösning B:** Använd extern väderdata (SMHI Open Data API) per parkens GPS-koordinat

### Implementation A (lätt)
```python
# elpris/bazefield.py
WEATHER_POINTS_MAP = {
    "IrradianceGHI": "ghi",
    "WindSpeed": "wind_speed",
    "Humidity": "humidity",
    "AmbientTemperature": "ambient_temp_c",  # NY — verifiera namn i Bazefield UI
}
```

Verifiera först i Bazefields web-UI vilka domain points som finns för en parks väderstation.

### Implementation B (SMHI-fallback)
Lägg till `elpris/smhi.py`:
```python
def fetch_temperature(lat: float, lon: float, start: datetime, end: datetime) -> list[dict]:
    """Hämta timvis temperatur från närmaste SMHI-station."""
    # SMHI Open Data: https://opendata.smhi.se/apidocs/metobs/
```

Sedan i `performance_report_data.py:_compute_module_temp()`, ladda väderdata om tillgänglig, annars använd default.

### Förväntad effekt på rapporten
- Sektion 1: Medelmodultemp får korrekt värde (idag visar None när väderdata saknas)
- Sektion 4: PR vs Temp-grafens temperaturlinje blir korrekt
- Sektion 9-10: Temperaturförlust i waterfall blir baserad på faktisk temp (idag använder vi POA + 10°C antagande)

---

## Steg 5: SCADA-integration för inverter-data

**Prioritet:** HÖG (på sikt) — låser upp 5 platshållarsektioner

**Bakgrund:** Sektionerna 14, 15, 16, 17, 18 (Inverter Yield, Inverter Efficiency, PPM Schedule, Incidents, Alarm/Fault) är platshållare. För att aktivera dessa krävs direkt integration med invertertillverkarnas SCADA-system. Bazefield aggregerar bara på parknivå.

**OBS (uppdaterat 2026-04-10 efter Cowork-extraktion):** Portföljen har **3 olika invertertillverkare**, inte bara Sungrow som tidigare antaget. Detta betyder 3 separata API-integrationer. Se `elpris/park_product_data.py:SCADA_INTEGRATION_GROUPS`.

### Inventarium per park (verifierat från PVsyst SRC Forecast Oct 2025)

| Park | Antal invertrar | Fabrikat | Modell | API |
|------|-----------------|----------|--------|-----|
| Hörby | 51 | **Sineng** | SP-275K-H1 | Sineng iSolarCloud / Modbus TCP |
| Fjällskär | 56 | **Sineng** | SP-275K-H1 | Sineng iSolarCloud / Modbus TCP |
| Björke | 17 | **Sineng** | SP-275K-H1 | Sineng iSolarCloud / Modbus TCP |
| Agerum | 24 | **Sineng** | SP-275K-H1 | Sineng iSolarCloud / Modbus TCP |
| Hova ⭐ tracker | 17 | **Huawei** | SUN2000-330KTL-H1 | Huawei FusionSolar (REST + Modbus) |
| Stenstorp | 3 | **Huawei** | SUN2000-330KTL-H1 | Huawei FusionSolar |
| Tången | 16 | **Huawei** | SUN2000-330KTL-H1 | Huawei FusionSolar |
| Skäkelbacken | 16 | **Sungrow** | SG350HX-15A | Sungrow iSolarCloud |

**Inverter-grupper för planering:**
- **Sineng** (4 parker, 148 enheter): Hörby, Fjällskär, Björke, Agerum — högsta prioritet (största gruppen)
- **Huawei** (3 parker, 36 enheter): Hova, Stenstorp, Tången — andra prioritet
- **Sungrow** (1 park, 16 enheter): Skäkelbacken — lägsta prioritet

**Action:** Begär API-credentials från respektive leverantör (eller via Operations om Svea redan har avtal).

### Implementations-prioritet

Implementera i tre faser, en per fabrikat:

**Fas 5A: Sineng (148 enheter, 4 parker — högsta värde)**
- Sineng iSolarCloud kräver oftast Modbus TCP-uppkoppling till parkens lokala datalogger (inte cloud-API som Sungrow/Huawei)
- Verifiera om Bazefield redan läser Modbus-data från Sineng — i så fall kan vi exponera det via befintligt CSV
- Kontaktperson: Sineng EU support eller Operations-teamet

**Fas 5B: Huawei (36 enheter, 3 parker)**
- Huawei FusionSolar har modernt REST-API: `https://eu5.fusionsolar.huawei.com/thirdData/`
- Auth: northbound API user + system code (måste skapas i FusionSolar UI)
- Endpoints:
  - `/getStationList` — lista parker
  - `/getDevList` — lista invertrar per park
  - `/getDevHistoryKpi` — historisk daglig produktion per inverter
  - `/getDevRealKpi` — realtid (för varningar)
  - `/getAlarmList` — larmhistorik

**Fas 5C: Sungrow (16 enheter, 1 park)**
- Sungrow iSolarCloud: https://gateway.isolarcloud.com.hk/openapi
- Endpoints:
  - `/getDeviceListByPlant` — lista invertrar
  - `/getDevicePointMinuteDataList` — 5-min eller 15-min data per inverter
  - `/getPlantAlarmInfoListNew` — larm och fel
- Datapunkter: `total_yield_kwh`, `daily_yield_kwh`, `efficiency_pct`, `dc_input_power`, `ac_output_power`, `temperature`

### Modul-struktur

Skapa en gemensam abstraktion + per-leverantör-implementation:

```
elpris/
├── scada/
│   ├── __init__.py           # Re-exports
│   ├── base.py               # Abstract SCADAClient
│   ├── sineng.py             # Sineng-specific
│   ├── huawei.py             # Huawei FusionSolar-specific
│   └── sungrow.py            # Sungrow iSolarCloud-specific
```

Gemensamt interface:
```python
class SCADAClient(ABC):
    @abstractmethod
    def list_inverters(self, park_key: str) -> list[InverterInfo]: ...
    @abstractmethod
    def fetch_daily_yield(self, park_key: str, start: date, end: date) -> list[InverterDailyData]: ...
    @abstractmethod
    def fetch_alarms(self, park_key: str, start: date, end: date) -> list[AlarmRecord]: ...
```

### Routing per park
Använd `SCADA_INTEGRATION_GROUPS` från `park_product_data.py`:
```python
from elpris.park_product_data import SCADA_INTEGRATION_GROUPS

def get_scada_client_for_park(park_key: str) -> SCADAClient:
    for manufacturer, parks in SCADA_INTEGRATION_GROUPS.items():
        if park_key in parks:
            if manufacturer == "sineng": return SinengClient()
            if manufacturer == "huawei": return HuaweiClient()
            if manufacturer == "sungrow": return SungrowClient()
    raise ValueError(f"Ingen SCADA-mappning för park: {park_key}")
```

### Datalagring
```
Resultat/marknadsdata/sungrow/
├── inverters/
│   ├── horby/
│   │   ├── inv_001_yield.csv
│   │   ├── inv_002_yield.csv
│   │   └── ...
│   └── ...
└── alarms/
    ├── horby_2026-03.csv
    └── ...
```

### Rapportintegration
Uppdatera `performance_report_data.py`:
- `MonthlyReport.inverters: list[InverterData]` — daglig yield + total per inverter
- `MonthlyReport.alarms: list[AlarmRecord]` — alla larm för månaden
- `MonthlyReport.faults: list[FaultRecord]` — alla fel för månaden

Uppdatera `performance_report_html.py`:
- Sektion 14: Inverter-yield-tabell + ranking-card
- Sektion 15: Inverter-efficiency-trend (multi-line) + heatmap
- Sektion 18: Alarm/fault summary med KPI-kort + treemap
- Sektion 19: Alarm/fault-statistiktabell + cirkeldiagram

### Tidsåtgång
- API-utforskning + auth: 1-2 dagar
- Sungrow-klient + datalagring: 2-3 dagar  
- Integration i rapport (2 sektioner): 1-2 dagar
- **Total:** ~1 vecka för Sungrow-baserade parker
- Andra fabrikat (om de finns): repetera per leverantör

### Beroenden
- API-credentials från Operations
- Lista över alla inverter-IDs per park
- Bekräftelse att Svea Solar har API-åtkomst (vissa kunder måste begära aktivering)

---

## Steg 6: PPM Schedule (statisk konfiguration)

**Prioritet:** LÅG — kosmetiskt, kan implementeras snabbt utan extern data

**Bakgrund:** Sektion 16 (PPM Schedule) i originalrapporten visar en kalender över planerat förebyggande underhåll (preventive maintenance) per månad. Detta kan implementeras som statisk konfiguration utan SCADA.

### Implementation
Skapa `elpris/ppm_schedule.py`:

```python
PPM_TASKS = [
    {
        "task": "Termografering MV/HV",
        "frequency": "annual",
        "scheduled_months": [6],  # Juni varje år
    },
    {
        "task": "Visuell inspektion paneler",
        "frequency": "biannual",
        "scheduled_months": [3, 9],  # Mars och September
    },
    {
        "task": "Vegetationskontroll", 
        "frequency": "biannual",
        "scheduled_months": [5, 9],
    },
    # ... lista från PPM-avtal
]

def get_ppm_schedule_for_year(year: int) -> list[dict]:
    """Returnera schemat för ett år som matris (task × månad)."""
```

Uppdatera `performance_report_html.py:_render_ppm()` att rita kalendermatrisen.

### Datakälla
Hämta listan från PPM-kontraktet med Operations-leverantören (t.ex. K-energy eller intern). Anpassa efter parkens specifika underhållsplan.

---

## Steg 7: Incidentlogg + Work Carried Out

**Prioritet:** LÅG-MEDEL — kräver manuell inmatning eller ticketsystem-integration

**Bakgrund:** Sektion 17 visar incidenter och arbete utfört på siten. Ingen automatisk källa finns idag.

### Alternativ A: Manuell JSON-fil per park
```
Resultat/operationsdata/incidenter/
├── horby_2026-03.json
├── hova_2026-03.json
└── ...
```

Format:
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

### Alternativ B: Jira/ServiceNow-integration
Om Svea Solar använder ett ticketsystem för operations-incidenter:
- API-integration mot Jira/ServiceNow
- Filtrera på park-tag och månad
- Mappa fält till rapportens kolumner

### Implementation
Uppdatera `performance_report_data.py`:
- `MonthlyReport.incidents: list[Incident]`
- `MonthlyReport.work_log: list[WorkLogEntry]`

Och `performance_report_html.py:_render_incidents()`.

---

## Steg 8: Förbättrad Executive Summary med LLM

**Prioritet:** LÅG — befintlig är funktionell men generisk

**Bakgrund:** Sektion 19 har idag mall-baserad text med variabler. Originalrapporten har mer naturlig prosa med kontextuell analys.

### Alternativ
1. **Mer mall-text:** Lägg till conditional branches baserat på avvikelse-storlek, säsong, etc.
2. **LLM-genererad:** Skicka KPI-data till Claude/GPT och generera 3-5 stycken på svenska
3. **Hybrid:** LLM genererar 1 stycke "highlights" + mallbaserad detalj

### LLM-implementation skiss
```python
def generate_executive_summary(report: MonthlyReport) -> str:
    """Generera prosaisk sammanfattning via Claude API."""
    prompt = f"""
    Skriv en kort prosaisk månadssammanfattning på svenska för {report.park_display_name} 
    baserat på följande KPI:er. Var saklig och koncis (3-5 meningar).
    
    Data:
    - Faktisk: {report.actual_energy_mwh} MWh
    - Budget: {report.budget_energy_mwh} MWh
    - Yield: {report.yield_kwh_kwp} kWh/kWp
    - PR: {report.performance_ratio_pct or 'N/A'}
    - Förluster: {report.losses}
    """
    # Anropa Anthropic API
```

**OBS:** LLM-generering bör cachas (samma rapport ska inte regenereras varje körning).

---

## Steg 9: Automatisk månadsvis generering

**Prioritet:** MEDEL — när rapporten är produktionsmogen

**Bakgrund:** Idag måste rapporten genereras manuellt. Ska köras automatiskt första vardagen i månaden.

### Implementation med Windows Task Scheduler
```powershell
# Skapa schemalagd uppgift
schtasks /create /sc monthly /d 1 /st 06:00 /tn "Solpark Performance Reports" /tr "python C:\Users\PontusSkog\Developer\electricity prices\generate_performance_report.py --all"
```

### Eller via Claude Code CronCreate
```python
# I projektets cron-config
{
  "name": "monthly_performance_reports",
  "schedule": "0 6 1 * *",  # 1:a varje månad kl 06:00
  "command": "python generate_performance_report.py --all"
}
```

### Email-distribution
Efter generering — skicka rapport-länk till asset managers via:
- Outlook/Microsoft 365 (via MCP-integration)
- Eller publicera till SharePoint/Teams

---

## Steg 10: PDF-export

**Prioritet:** LÅG — HTML är primärt format men PDF efterfrågas av externa intressenter

**Bakgrund:** Vissa intressenter (revisorer, ägare) vill ha PDF. HTML kan exporteras manuellt via Ctrl+P → "Save as PDF" i Chrome, men automatisering är möjlig.

### Alternativ
1. **Chromium headless:** `playwright` — använd befintlig Playwright MCP, navigera till HTML, exportera till PDF
2. **WeasyPrint:** Python-bibliotek, men sämre Plotly-stöd
3. **Puppeteer/wkhtmltopdf:** Externa verktyg

### Implementation med Playwright
```python
# elpris/pdf_export.py
async def html_to_pdf(html_path: Path, pdf_path: Path):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"file://{html_path}")
        await page.wait_for_load_state("networkidle")
        await page.pdf(
            path=pdf_path,
            format="A4",
            landscape=True,
            print_background=True,
        )
        await browser.close()
```

### CLI-flagga
```bash
python generate_performance_report.py --park horby --month 2026-03 --pdf
```

---

## Verifieringschecklista (efter alla steg)

När alla steg är genomförda, jämför rapporten med referensen i `Reporting example Asset management/SVEA Anagia 3MW Performance Reports March 2026.pdf`:

- [ ] Alla 25 sidor i originalet har en motsvarande sektion
- [ ] KPI-värden är korrekta (verifiera mot Bazefield UI)
- [ ] PR och PI är inom rimliga intervall (60-100% normalt)
- [ ] Loss cascade summerar till budget - actual
- [ ] Inverter-data finns och är konsistent med park-totalen
- [ ] Larm-/fellistor är kompletta
- [ ] PPM-schemat matchar serviceavtal
- [ ] Executive Summary är läsbar och saklig
- [ ] Print-CSS fungerar i Chrome (Ctrl+P → A4 landscape)
- [ ] Filstorlek under 10 MB per rapport
- [ ] Alla 8 parker genereras utan fel via `--all`

---

## Kvarvarande open questions

1. **Vilka invertertillverkare har vi per park?** — viktigt för steg 5 (SCADA)
2. **Har Svea Solar API-credentials hos Sungrow/SMA/Huawei iSolarCloud?** — kan ta veckor att få aktiverat
3. **Vem äger PPM-schemat per park?** — extern OEM eller intern operations?
4. **Var lagras incidentdata idag?** — Excel, mejl, ticketsystem?
5. **Vilken målgrupp får rapporten?** — bara internt eller även externa ägare/banker? Påverkar branding och språk
6. **Behöver vi engelsk version?** — för internationella ägare/finansiärer
