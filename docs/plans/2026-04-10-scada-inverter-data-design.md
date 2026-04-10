# SCADA Fas 6: Inverter-data via Bazefield

**Datum:** 2026-04-10
**Status:** Design godkänd, redo för implementation
**Relaterade dokument:**
- `2026-04-10-performance-report-roadmap.md` (Steg 5)
- `2026-04-10-performance-report-actions.md` (Steg 5)

## Kontext

Referens-rapporten (K-energy/Anayia) har **3 inverter-sektioner** som idag är platshållare i Svea Solars rapport:

- **Sektion 14:** Inverter Yield — daglig tabell + ranking per inverter
- **Sektion 15:** Inverter Efficiency — multi-line trend + heatmap
- **Sektion 18:** Alarm & Fault Summary — KPI-kort, timeline, treemap, statistik

Tidigare antagande var att vi behövde bygga 3 separata SCADA-klienter för portföljens 3 invertertillverkare (Sineng, Huawei, Sungrow). **Den antagan var fel.**

## Nyckelinsikt

Bazefield fungerar **redan** som aggregator för alla 3 leverantörer. Verifierat via direktanrop:

1. **Inverter-objekten finns** — Hörby har 5 TS-grupper med 51 INV-objekt, Hova har 2 TS + 17 INV-objekt, etc.
2. **257 data points per inverter** via `ObjectPointDetailsGetRequest` — `ActivePower`, `TotalEnergyProduced.1h`, `TempPanel`, `Available`, `OperationState`, m.fl.
3. **Alarm-history via `ObjectEventsHistoryGetRequest`** — returnerar alarm-events med eventCode, eventType, timeStart, timeEnd, eventDescription
4. **Funkar för alla 3 leverantörer** — testat Sineng (Hörby), Huawei (Hova, Tången, Stenstorp), Sungrow (Skäkelbacken)

Detta betyder att **vi slipper bygga 3 SCADA-klienter**. Istället utökar vi befintliga `bazefield.py` med inverter-nivå funktioner.

## Designbeslut (från brainstorming)

| Fråga | Beslut |
|-------|--------|
| Approach | Endast Bazefield. Inga direkta SCADA-integrationer. |
| Datalagring | Daglig aggregering per park (inte 15-min). En CSV per park per typ. |
| Scope | Full scope: sektion 14 + 15 + 18 |
| Alarm-filter | Endast `eventType == "Alarm"` (exkluderar EVENT-NightHours, Status etc.) |

## Arkitektur

### Nya/modifierade moduler

```
elpris/
├── inverter_registry.py       # NY: Statisk lista av alla invertrar per park
├── bazefield.py               # UTÖKAS: Nya fetch-funktioner för inverter-data
├── inverter_data.py           # NY: Aggregation + event-parsing för rapporter
└── performance_report_data.py # UTÖKAS: Integrera inverter-data i MonthlyReport
elpris/performance_report_html.py  # UTÖKAS: Ersätt 14, 15, 18 platshållare
discover_inverters.py          # NY: Engångs-script för att bygga registry
bazefield_download.py          # UTÖKAS: --inverters flagga
```

### Datalagring

```
Resultat/profiler/parker/inverters/
├── horby_daily_yield.csv      # 51 inverters × 31 days = ~1581 rows/month
├── horby_events.csv           # Park-level alarm log
├── fjallskar_daily_yield.csv  # 56 × 31 = 1736 rows/month
├── fjallskar_events.csv
├── bjorke_daily_yield.csv     # 17 × 31 = 527 rows/month
├── bjorke_events.csv
├── agerum_daily_yield.csv     # 24 × 31 = 744
├── agerum_events.csv
├── hova_daily_yield.csv       # 17 × 31 = 527
├── hova_events.csv
├── skakelbacken_daily_yield.csv  # 16 × 31 = 496
├── skakelbacken_events.csv
├── stenstorp_daily_yield.csv  # 3 × 31 = 93 (liten park)
├── stenstorp_events.csv
├── tangen_daily_yield.csv     # 16 × 31 = 496
└── tangen_events.csv
```

**Total**: 16 filer, ~6k rader / månad över hela portföljen. Kompakt.

### CSV-schema

**`{park}_daily_yield.csv`:**
```csv
date,inverter_name,energy_kwh,max_power_kw,rated_kw,capacity_factor_pct
2026-03-01,HRB-TS1-INV01,1250.5,198.3,275,18.95
2026-03-01,HRB-TS1-INV02,1248.7,197.5,275,18.92
...
```

**`{park}_events.csv`:**
```csv
inverter_name,event_name,event_code,event_type,time_start_utc,time_end_utc,duration_min,description
HRB-TS1-INV04,Alarm0005,5,Alarm,2025-10-21T07:57:11Z,2025-10-21T08:00:09Z,3,Grid abnormal
HRB-TS1-INV04,Alarm0012,12,Alarm,2025-11-05T14:23:00Z,2025-11-05T14:25:30Z,3,AC voltage abnormal
...
```

## Inverter Registry

**`elpris/inverter_registry.py`** — Statisk lista som skapas via engångs-discovery.

```python
PARK_INVERTERS: dict[str, list[dict]] = {
    "horby": [
        {"name": "HRB-TS1-INV01", "id": "1169E154FC49D000", "transformer": "TS1", "rated_kw": 275},
        {"name": "HRB-TS1-INV02", "id": "...", "transformer": "TS1", "rated_kw": 275},
        # ... 51 invertrar totalt
    ],
    "fjallskar": [...],  # 56 invertrar
    "bjorke": [...],     # 17
    "agerum": [...],     # 24
    "hova": [...],       # 17 (Huawei, tracker)
    "skakelbacken": [...], # 16 (Sungrow)
    "stenstorp": [...],  # 3 (Huawei, pilot)
    "tangen": [...],     # 16 (Huawei)
}
```

**Rated kW per leverantör:**
- Sineng SP-275K-H1 → 275 kW
- Huawei SUN2000-330KTL-H1 → 330 kW
- Sungrow SG350HX-15A → 350 kW

**Discovery-script** (`discover_inverters.py`):
1. Kör `ObjectStructureGetRequest` för Hörby (returnerar alla objekt i systemet)
2. Filtrera objekt med `objectKey` matchande regex `^[A-Z]+-TS\d+-INV\d+$`
3. Gruppera per park via parent → TS → park-ID
4. Slå upp rated_kw via `park_product_data.inverter_model`
5. Skriv ut formatterad Python-dict till `inverter_registry.py`

Körs **en gång** initialt och vid inverter-ändringar (nya parker, nya TS).

## Dataflöde

### Sync-funktioner (i `bazefield.py`)

```python
def fetch_inverter_daily_yield(
    park_key: str,
    from_date: date,
    to_date: date,
) -> list[dict]:
    """Hämta daglig yield per inverter för en park.
    
    Returns: [{date, inverter_name, energy_kwh, max_power_kw, rated_kw, capacity_factor_pct}, ...]
    """
    # 1. Slå upp invertrarna från inverter_registry.PARK_INVERTERS[park_key]
    # 2. För varje inverter:
    #    - fetch_timeseries(inv_id, ["TotalEnergyProduced.1h", "ActivePower"], ...)
    #    - Aggregera timmarna till daglig total
    #    - Plocka ut daily max ActivePower
    # 3. Beräkna capacity_factor = energy_kwh / (rated_kw × 24) × 100
    # 4. Returnera list-of-dicts


def fetch_inverter_events(
    park_key: str,
    from_date: date,
    to_date: date,
) -> list[dict]:
    """Hämta alarm-events per inverter för en park.
    
    Filter: eventType == "Alarm" (exkluderar Status, NightHours etc.)
    Returns: [{inverter_name, event_name, event_code, time_start, time_end, duration_min, description}, ...]
    """
    # 1. Slå upp invertrarna
    # 2. Batcha ObjectEventsHistoryGetRequest för alla invertrar (ev. i chunks)
    # 3. Filtrera till eventType=="Alarm"
    # 4. Beräkna duration_min = (time_end - time_start) / 60
    # 5. Returnera sorterad lista


def save_inverter_yield_csv(park_key: str, records: list[dict]) -> int:
    """Spara daglig yield till CSV (upsert, undvik dubbletter)."""

def save_inverter_events_csv(park_key: str, records: list[dict]) -> int:
    """Spara events till CSV (upsert baserat på time_start + inverter_name)."""
```

### CLI-integration

```bash
# Default: bara park-level sync (som idag)
python bazefield_download.py --backfill

# Inklusive inverter-nivå
python bazefield_download.py --backfill --inverters

# Bara inverter-data för en park
python bazefield_download.py --inverters --parks horby
```

Flaggan `--inverters` triggar både `fetch_inverter_daily_yield()` och `fetch_inverter_events()`.

**Uppskattad körtid:** ~5-10 min per park för backfill (200 invertrar × 30 API-anrop × 0.5s delay = 30 min totalt för hela portföljen).

## Rapport-integration

### Utökad `MonthlyReport`-dataclass

```python
@dataclass
class InverterMonthly:
    name: str                   # "HRB-TS1-INV01"
    transformer: str            # "TS1"
    rated_kw: float             # 275.0
    total_energy_kwh: float     # Månadens totalsumma
    max_power_kw: float         # Högsta peak under månaden
    avg_capacity_factor_pct: float  # Månatligt snitt av CF
    days_active: int            # Antal dagar med >1 kWh
    rank: int                   # Månadens ranking (1=bäst)

@dataclass
class AlarmEvent:
    inverter_name: str
    event_name: str             # "Alarm0005"
    event_code: int             # 5
    description: str            # "Grid abnormal"
    time_start: datetime
    time_end: datetime | None
    duration_min: float

@dataclass
class MonthlyReport:
    # ... befintliga fält ...
    inverters: list[InverterMonthly] = field(default_factory=list)
    alarms: list[AlarmEvent] = field(default_factory=list)
    # Calculated aggregates
    has_inverter_data: bool = False
    has_alarm_data: bool = False
```

### HTML-sektioner

**Sektion 14: Inverter Yield**
- Vänster: tabell 31 rader × N+2 kolumner (dag, inv_01..inv_N, total) — visar daglig kWh
- Höger: "Inverter Ranking"-card med lista sorterad efter månadstotal, färgkodad (top 5 grön, bottom 5 röd)
- Note: standardavvikelse mellan invertrar (indikator på trasig sträng)

**Sektion 15: Inverter Efficiency**
- Övre: multi-line chart, en linje per inverter, Y=CF%, X=dag
- Undre: heatmap 31 rader × N kolumner, färgkodad grön→röd baserat på CF%
- Höger: ranking-tabell med snitt CF% per inverter, färgkodad (≥98% grön, 97-98% gul, <97% röd)

**Sektion 18: Alarm & Fault Summary**
- Topp: 4 KPI-kort (Total alarms, Unique types, Avg MTBA hrs, Active alarms)
- Timeline-chart: stacked bar, en bar per dag, färgkodad per alarm-typ
- Treemap: per-inverter alarm-frekvens
- Alarm-frekvens-tabell: topp alarm-typer med antal + total duration
- Detaljtabell: alla alarm-events (scrollbar om >30)

**Graceful degradation:** Om en sektion saknar data (t.ex. Stenstorps ActivePower), visas en stilfull "Data otillgänglig för denna park"-notis istället för tom sektion.

## Filer som modifieras

| Fil | Operation | Rader |
|-----|-----------|-------|
| `discover_inverters.py` | NY (CLI) | ~80 |
| `elpris/inverter_registry.py` | NY (genererad) | ~220 |
| `elpris/bazefield.py` | Modifiera (4 nya funktioner) | +200 |
| `elpris/inverter_data.py` | NY (aggregation) | ~250 |
| `elpris/performance_report_data.py` | Modifiera (ladda inverter-data) | +80 |
| `elpris/performance_report_html.py` | Modifiera (3 nya sektioner) | +400 |
| `bazefield_download.py` | Modifiera (--inverters flagga) | +20 |
| `Resultat/profiler/parker/inverters/*.csv` | NYA (16 filer, ~6k rows) | - |
| `docs/plans/2026-04-10-scada-inverter-data-design.md` | NY (detta dokument) | ~300 |

## Implementationsordning

### Steg 1: Discovery (~30 min)
1. Skriv `discover_inverters.py`
2. Kör → generera `elpris/inverter_registry.py`
3. Verifiera antal invertrar per park matchar `park_product_data.num_inverters`

### Steg 2: Bazefield fetch-funktioner (~1 h)
1. Implementera `fetch_inverter_daily_yield()` — använd befintlig `fetch_timeseries()`
2. Implementera `fetch_inverter_events()` — ny wrapper för `ObjectEventsHistoryGetRequest`
3. Implementera `save_inverter_yield_csv()` och `save_inverter_events_csv()`
4. Spot-test för Hörby mars 2026

### Steg 3: CLI-integration (~15 min)
1. Lägg till `--inverters` flagga i `bazefield_download.py`
2. Testa: `python bazefield_download.py --inverters --parks horby`

### Steg 4: Initial sync (~30-60 min körtid)
1. Kör `python bazefield_download.py --inverters --backfill`
2. Verifiera 16 CSV-filer skapade
3. Kontrollera datakvalitet: inga nulls, rimliga värden

### Steg 5: Aggregation & dataclass (~1 h)
1. Skapa `elpris/inverter_data.py` med `load_inverter_monthly()` och `load_alarm_events()`
2. Utöka `MonthlyReport` med inverter-fält
3. Integrera i `performance_report_data.generate_report()`
4. Test: `generate_report('horby', 2026, 3)` → verifiera `.inverters` och `.alarms` fyllda

### Steg 6: HTML-rendering (~2 h — största jobbet)
1. Ersätt sektion 14 platshållare med `_render_inverter_yield()`
2. Ersätt sektion 15 platshållare med `_render_inverter_efficiency()`
3. Ersätt sektion 18 platshållare med `_render_alarm_summary()`
4. Lägg till CSS för nya tabeller, heatmaps, treemaps
5. Testa rendering för Hörby mars 2026

### Steg 7: Verifiering (~30 min)
1. Generera alla 24 rapporter (8 parker × 3 månader jan-mar)
2. Spot-check Hörby mot Bazefield UI
3. Spot-check Stenstorp (graceful degradation)
4. Commit per steg

**Total uppskattad tid:** 5-7 timmar implementation + körtid.

## Verifiering

### Funktionella tester

```bash
# 1. Discovery
python discover_inverters.py
# → elpris/inverter_registry.py skapas med ~200 invertrar

# 2. Fetch test
python -c "
from elpris.bazefield import fetch_inverter_daily_yield
from datetime import date
data = fetch_inverter_daily_yield('horby', date(2026, 3, 1), date(2026, 3, 31))
print(f'{len(data)} records, first: {data[0]}')
"

# 3. Full backfill
python bazefield_download.py --inverters --backfill

# 4. Verifiera filer
ls -la Resultat/profiler/parker/inverters/
# → 16 filer, storlek OK

# 5. Generera rapport med inverter-data
python generate_performance_report.py --park horby --month 2026-03

# 6. Öppna HTML och verifiera
# - Sektion 14: tabell + ranking visar 51 invertrar
# - Sektion 15: heatmap och multi-line chart
# - Sektion 18: KPI-kort + alarm-tabell

# 7. Alla parker
python generate_performance_report.py --all --month 2026-03
```

### Jämför mot Bazefield UI

Öppna Hörby i Bazefield dashboard → kontrollera:
- Total yield för mars ≈ sum av alla invertrar i rapporten (±1%)
- Top 3 invertrar samma i båda verktygen
- Alarm-antal rimligt (ska matcha Bazefield alarms-vy)

## Kända begränsningar

1. **Stenstorp har begränsad data**
   - Inga `ActivePower` records
   - Inga `Available` flags
   - Endast `TotalEnergyProduced.1h` finns
   - **Effekt:** Sektion 14 fungerar (daglig energi). Sektion 15 visar "Begränsad data" (ingen CF). Sektion 18 visar "Ingen alarm-data".

2. **Långa fetch-tider vid backfill**
   - 200 invertrar × ~30 API-anrop = ~6000 requests
   - Med 0.5s delay: ~50 min totalt
   - **Mitigation:** Progress-logging per park, möjlighet att avbryta och återuppta

3. **Språk i alarm-beskrivningar**
   - Bazefield returnerar eventDescription på engelska
   - Vi behåller engelskt men lägger till svensk översättning för kända kritiska alarm (Grid abnormal → Nätstörning etc.)
   - Lookup-tabell i `inverter_data.py`

4. **Capacity factor > 100%**
   - Sineng 275kW kan kortvarigt peaka till ~300kW
   - Sanity check: cap vid 110% i beräkningen, flagga som warning om >110%

5. **Stora invertergrupper ger bred tabell**
   - Hörby 51 invertrar ger en TAH-bred tabell
   - **Mitigation:** I sektion 14 gruppera per transformer (TS1-TS5) för visuell klarhet. Visa totalsumma + top 5 + bottom 5.

## Risker & Mitigations

| Risk | Sannolikhet | Påverkan | Mitigation |
|------|-------------|----------|------------|
| Backfill tar >1h | Hög | Låg | Körs sällan, kan pausas/återupptas |
| Event-data saknas för vissa leverantörer | Medel | Medel | Graceful degradation med "Ingen alarm-data"-notis |
| HTML-tabeller blir för breda | Hög | Låg | Gruppera per transformer, visa top/bottom |
| Stenstorps begränsning påverkar UX | Låg | Låg | Tydlig "Begränsad data"-notis per sektion |
| Discovery-skriptet missar invertrar | Låg | Hög | Cross-check mot `park_product_data.num_inverters` |
| ObjectEventsHistoryGetRequest rate-limiterar | Medel | Medel | Batcha per park, inte per inverter |

## Vad som INTE ingår

- **Inverter-nivå efficiency per hour** (bara dagligt). Senare förbättring.
- **String-level data** (DC-Voltage1-16, DC-Current1-16). Överkill för rapporten.
- **Realtid-övervakning.** Dashboard v2 eller annat verktyg.
- **Alarm-notifications.** Out of scope för månadsrapporten.
- **Direkta SCADA-credentials** till Sineng/Huawei/Sungrow. Bazefield är tillräckligt.
