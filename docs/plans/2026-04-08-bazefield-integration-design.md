# Bazefield-integration — Synk av solparksproduktion

**Datum:** 2026-04-08
**Syfte:** Ladda ner verklig produktionsdata (15-min) från Svea Solars solparker via Bazefield API, för att beräkna "verkligt" capture price som jämförelse med PVSyst-profiler i dashboarden.

## Arkitektur

```
Bazefield API → bazefield_download.py → Resultat/profiler/parker/<park>_SE<zon>.csv
                                                    ↓
                              Dashboard v2 auto-upptäcker parkprofiler
                                                    ↓
                              Capture price beräknas per park vs spotpris
```

### Nya filer

| Fil | Beskrivning |
|-----|-------------|
| `elpris/bazefield.py` | API-klient för Bazefield |
| `bazefield_download.py` | CLI-script för nedladdning/synk |
| `.claude/commands/elpris-bazefield.md` | Slash command för standardiserad synk |

### Befintliga filer som ändras

| Fil | Ändring |
|-----|---------|
| `update_all.py` | Nytt steg: Bazefield-synk |
| `CLAUDE.md` | Dokumentation av ny datakälla |

## API-detaljer

- **Bas-URL:** `https://sveasolar.bazefield.com/BazeField.Services/api/`
- **Autentisering:** Bearer-token via `BAZEFIELD_API_KEY` i `.env`
- **Endpoint:** `POST /json/reply/GetDomainPointTimeSeriesAggregated`
- **Datapunkt:** `ActivePowerMeter` (MW vid nätanslutning)
- **Upplösning:** 15 minuter, AVERAGE-aggregat
- **Rate limits:** Ej dokumenterade, chunka i 30-dagarsintervall

## Solparker

| Park | Key | Bazefield ID | Elområde | Status |
|------|-----|-------------|----------|--------|
| Hörby | horby | 1164AFE219C9D000 | SE4 | Aktiv |
| Fjällskär | fjallskar | 117FEB196CC9D000 | SE3 | Aktiv |
| Agerum | agerum | 11BD1C992309D000 | SE4 | Aktiv |
| Hova | hova | 1226CE0630C9D000 | SE3 | Aktiv |
| Björke | bjorke | 11BC114AFFC9D000 | SE3 | Ej verifierad |
| Skakelbacken | skakelbacken | 12BC5B932DC9D000 | SE3 | Ej verifierad |
| Stenstorp | stenstorp | 12C0707193C9D000 | SE3 | Ej verifierad |
| Tången | tangen | 13F29EF630C9D000 | SE4 | Ej verifierad |

Parker markerade "Ej verifierad" hade 0 MW i testperioden (jun 2025). Backfill-processen probar automatiskt och hoppar över parker utan data.

## Dataformat

Filnamn: `Resultat/profiler/parker/<park_key>_SE<zon>.csv`

```csv
timestamp,power_mw
2025-06-15T10:00:00+02:00,11.466
2025-06-15T10:15:00+02:00,11.562
```

## API-klient (`elpris/bazefield.py`)

### Konfiguration

```python
PARKS = {
    "horby":        {"id": "1164AFE219C9D000", "zone": "SE4", "name": "Hörby"},
    "fjallskar":    {"id": "117FEB196CC9D000", "zone": "SE3", "name": "Fjällskär"},
    "bjorke":       {"id": "11BC114AFFC9D000", "zone": "SE3", "name": "Björke"},
    "agerum":       {"id": "11BD1C992309D000", "zone": "SE4", "name": "Agerum"},
    "hova":         {"id": "1226CE0630C9D000", "zone": "SE3", "name": "Hova"},
    "skakelbacken": {"id": "12BC5B932DC9D000", "zone": "SE3", "name": "Skakelbacken"},
    "stenstorp":    {"id": "12C0707193C9D000", "zone": "SE3", "name": "Stenstorp"},
    "tangen":       {"id": "13F29EF630C9D000", "zone": "SE4", "name": "Tången"},
}
```

### Huvudfunktioner

- `fetch_timeseries(park_key, from_date, to_date)` — hämtar ActivePowerMeter i 15-min AVERAGE
- `find_first_data_date(park_key)` — binärsökning bakåt för att hitta första dag med data
- `get_latest_synced_date(park_key)` — läser befintlig CSV för att hitta var vi slutade

### Inkrementell synk

1. Läs sista timestamp i befintlig CSV
2. Hämta data från dagen efter till idag
3. Chunka i 30-dagarsintervall
4. Appenda till befintlig CSV (undvik dubbletter via timestamp-jämförelse)

## CLI (`bazefield_download.py`)

```bash
# Synka alla parker (inkrementellt)
python3 bazefield_download.py

# Specifik park
python3 bazefield_download.py --parks horby fjallskar

# Full historik (initial backfill)
python3 bazefield_download.py --backfill

# Visa synkstatus
python3 bazefield_download.py --status
```

## Integration med update-kedjan

Ordning i `update_all.py`:
1. Spotpriser
2. **Bazefield (ny)**
3. ENTSO-E
4. Mimer
5. eSett
6. Capture price
7. Excel
8. Dashboard

## Capture price

Ingen kodändring behövs. Dashboard v2 auto-upptäcker profiler i `Resultat/profiler/parker/` via filnamn `<park>_SE<zon>.csv` och beräknar capture price per park.

## Framtida steg

- Schemalagd automatisk synk (cron/trigger)
- Irradiance-data (IrradiancePOA) för PR-beräkning
- Jämförelsevy: PVSyst vs verklig produktion per park
