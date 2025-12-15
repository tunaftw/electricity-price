# Elpris - Swedish Electricity Price Analysis

System för att ladda ner och analysera svenska elpriser, reglerpriser och installerad kapacitet.

## Projektstruktur

```
electricity-price/
├── elpris/                    # Huvudmodul
│   ├── api.py                 # API-klient för elprisetjustnu.se
│   ├── capture.py             # Capture price-beräkningar
│   ├── config.py              # Konfiguration och konstanter
│   ├── energimyndigheten.py   # PxWeb API för installerad kapacitet
│   ├── entsoe.py              # ENTSO-E Transparency Platform API
│   ├── esett.py               # eSett Nordic imbalance settlement API
│   ├── mimer.py               # Svenska kraftnät Mimer API
│   ├── processing.py          # Konvertering tim → quarterly (15-min)
│   ├── solar_profile.py       # Solprofiler för capture-beräkning
│   └── storage.py             # Filhantering för CSV-data
├── Resultat/                  # All nedladdad data och analyser (se nedan)
├── data/                      # Symlinks till Resultat/ för bakåtkompatibilitet
├── docs/                      # Dokumentation
├── update_all.py              # Master update (kör hela kedjan)
├── download.py                # Ladda ner spotpriser (full historik)
├── update.py                  # Uppdatera befintlig data
├── process.py                 # Konvertera till quarterly-format
├── capture.py                 # Beräkna capture prices
├── status.py                  # Visa datastatus
├── entsoe_download.py         # Ladda ner ENTSO-E data (sol, vind, vatten, kärnkraft)
├── esett_download.py          # Ladda ner eSett obalanspriser
├── mimer_download.py          # Ladda ner reglerpriser
└── installed_download.py      # Ladda ner installerad kapacitet
```

## Datakatalog

All data och analysresultat sparas i `Resultat/`-katalogen:

```
Resultat/
├── marknadsdata/                    # Nedladdad extern marknadsdata
│   ├── spotpriser/                  # Spotpriser per elområde
│   │   ├── SE1/                     # 2021.csv, 2022.csv, ...
│   │   ├── SE2/
│   │   ├── SE3/
│   │   └── SE4/
│   │
│   ├── entsoe-produktion/           # ENTSO-E faktisk produktion
│   │   └── entsoe/generation/
│   │       ├── SE1/                 # solar_*.csv, wind_onshore_*.csv
│   │       ├── SE2/
│   │       ├── SE3/                 # + nuclear_*.csv
│   │       └── SE4/
│   │
│   ├── reglering-mimer/             # Svenska kraftnät reglerpriser
│   │   └── mimer/
│   │       ├── fcr/                 # FCR-N, FCR-D priser
│   │       ├── afrr/                # aFRR upp/ned per zon
│   │       ├── mfrr_cm/             # mFRR kapacitetsmarknad
│   │       └── mfrr/                # mFRR energiaktivering
│   │
│   ├── obalans-esett/               # eSett Nordic obalanspriser
│   │   └── esett/imbalance/
│   │       ├── SE1/
│   │       ├── SE2/
│   │       ├── SE3/
│   │       └── SE4/
│   │
│   └── installerad-kapacitet/       # Energimyndigheten statistik
│       └── installed/
│           ├── wind_by_elarea.csv
│           └── solar_installations.csv
│
├── profiler/                        # Beräknade produktionsprofiler
│   ├── beraknade/                   # PVsyst-processade (ew_boda.csv, etc.)
│   └── normaliserade/               # ENTSO-E normaliserade (solar_SE*.csv)
│
├── sol-kalldata/                    # Råa PVsyst-dokument
├── rapporter/                       # Analysrapporter och Excel-filer
├── BESS-PV-Vind-Baseload-PPA/       # Komplett analysproject
├── historik-nordpool/               # Duplicerad historisk data
└── presentationer/                  # PowerPoint-generering
```

**Bakåtkompatibilitet:** `data/`-katalogen innehåller symlinks till `Resultat/` så att befintliga scripts fungerar utan ändringar.

## Datakällor

### 1. Spotpriser (elprisetjustnu.se)
- **Zoner:** SE1, SE2, SE3, SE4
- **Period:** 2021-11-01 → idag
- **Format:** Timdata (fram till okt 2025), sedan 15-min
- **API:** `https://www.elprisetjustnu.se/api/v1/prices/{year}/{month}-{day}_{zone}.json`

### 2. Reglerpriser (Svenska kraftnät Mimer)
- **FCR:** FCR-N, FCR-D upp/ned (från 2021-01-01)
- **aFRR:** aFRR upp/ned per zon (från 2022-11-01)
- **mFRR-CM:** Kapacitetsmarknad per zon (från 2024-06-01)
- **mFRR:** Energiaktivering per zon (från 2022-01-01, tomt efter mars 2025)
- **API:** `https://mimer.svk.se/PrimaryRegulation/DownloadText`

### 3. Installerad kapacitet (Energimyndigheten)
- **Vindkraft:** Antal verk, MW, GWh per elområde (2003-2024)
- **Sol:** Antal anläggningar, MW per region (2016-2024)
- **API:** PxWeb REST API

### 4. Faktisk produktion (ENTSO-E Transparency Platform)
- **API:** `https://web-api.tp.entsoe.eu/api`
- **Token:** Kräver API-token, sätt miljövariabel `ENTSOE_TOKEN` eller `.env`-fil
- **Dokumentation:** https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html

#### Tillgängliga produktionstyper per zon

| Typ | Kod | SE1 | SE2 | SE3 | SE4 | Från |
|-----|-----|-----|-----|-----|-----|------|
| solar | B16 | ~2022 | ~2022 | ~2015 | ~2015 | Solproduktion |
| wind_onshore | B19 | 2015 | 2015 | 2015 | 2015 | Landbaserad vind |
| wind_offshore | B18 | - | - | - | - | Ej i Sverige ännu |
| hydro_water_reservoir | B12 | 2015 | 2015 | 2015 | 2015 | Vattenkraft (magasin) |
| hydro_run_of_river | B11 | - | - | - | - | Strömkraft (begränsad data) |
| nuclear | B14 | - | - | 2015 | 2015 | Kärnkraft (Forsmark/Ringhals) |
| fossil_gas | B04 | - | - | 2015 | - | Gaskraft (minimal) |
| biomass | B01 | - | - | - | - | Begränsad data |

**Upplösning:** 60 min (timdata), vissa perioder 15 min

### 5. Obalanspriser (eSett Nordic Imbalance Settlement)
- **Obalanspriser:** Köp/sälj-priser vid obalans (från 2023-05-22)
- **Regleringspriser:** Upp/ned-reglering (mFRR EAM aktivering)
- **Format:** 15-min upplösning
- **API:** `https://api.opendata.esett.com`
- **Gratis:** Ingen API-nyckel krävs

## Kommandon

### Ladda ner spotpriser
```bash
# Full historik alla zoner
python3 download.py

# Specifik zon
python3 download.py --zones SE3

# Specifik period
python3 download.py --start 2024-01-01 --end 2024-12-31
```

### Uppdatera data
```bash
# Uppdatera alla zoner med ny data
python3 update.py

# Specifik zon
python3 update.py --zones SE3
```

### Visa status
```bash
python3 status.py
```

### Processera till quarterly
```bash
python3 process.py
```

### Beräkna capture prices
```bash
# Standard solprofil
python3 capture.py SE3

# Per månad
python3 capture.py SE3 --period month

# Per år
python3 capture.py SE3 --period year
```

### Ladda ner reglerpriser (Mimer)
```bash
# Alla produkter (fcr, afrr, mfrr_cm, mfrr)
python3 mimer_download.py

# Specifik produkt
python3 mimer_download.py --product fcr

# mFRR energiaktivering (historik före EAM mars 2025)
python3 mimer_download.py --product mfrr --start 2024-01-01 --end 2024-12-31
```

### Ladda ner obalanspriser (eSett)
```bash
# Alla zoner
python3 esett_download.py

# Specifik zon
python3 esett_download.py --zones SE3 SE4

# Specifikt intervall
python3 esett_download.py --zones SE3 --start 2024-01-01 --end 2024-12-31
```

### Ladda ner installerad kapacitet
```bash
python3 installed_download.py
```

### Ladda ner ENTSO-E data (faktisk produktion)
```bash
# Sätt API-token (alternativ 1: miljövariabel)
export ENTSOE_TOKEN=din-token-här

# Sätt API-token (alternativ 2: .env-fil)
echo "ENTSOE_TOKEN=din-token-här" >> .env

# Sol och vind för alla zoner (standard)
python3 entsoe_download.py

# Specifik zon och typ
python3 entsoe_download.py --zones SE3 --types solar

# Vattenkraft för alla zoner
python3 entsoe_download.py --types hydro_water_reservoir

# Kärnkraft (endast SE3 och SE4)
python3 entsoe_download.py --zones SE3 SE4 --types nuclear

# Alla relevanta typer för full dataöversikt
python3 entsoe_download.py --types solar wind_onshore hydro_water_reservoir nuclear

# Specifikt intervall
python3 entsoe_download.py --zones SE3 SE4 --start 2024-01-01 --end 2024-12-31
```

**Tillgängliga typer:** solar, wind_onshore, wind_offshore, hydro_run_of_river,
hydro_water_reservoir, nuclear, fossil_gas, fossil_hard_coal, biomass, other

**OBS:** Nedladdning av full historik (2015-idag) tar ca 30-60 minuter pga API rate limiting.

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
Från 1 oktober 2025 övergår den svenska elmarknaden till 15-minutersupplösning (quarterly). Data före detta datum expanderas från timdata (varje timpris upprepas 4 gånger).

## Slash Commands

Projektet har slash commands i `.claude/commands/`:

### Master Update (rekommenderad)
- `/elpris-update-all` - **Kör hela uppdateringskedjan** (data + beräkningar + Excel)

### Datakällor
- `/elpris-download` - Ladda ner spotpriser (full historik)
- `/elpris-update` - Uppdatera spotpriser (inkrementellt)
- `/elpris-entsoe` - Ladda ner ENTSO-E data (sol/vind/kärnkraft)
- `/elpris-esett` - Ladda ner eSett obalanspriser
- `/elpris-mimer` - Ladda ner reglerpriser (SVK)
- `/elpris-installed` - Ladda ner installerad kapacitet

### Analys och rapporter
- `/elpris-status` - Visa datastatus
- `/elpris-capture` - Beräkna capture prices
- `/elpris-excel` - Generera Excel-rapporter

## Beroenden

```
requests>=2.31.0
tenacity>=8.2.0
openpyxl>=3.1.0
```

## API-nycklar och konfiguration

Projektet använder en `.env`-fil för att lagra API-nycklar. Skapa filen i projektets rot:

```bash
# .env
ENTSOE_TOKEN=din-entso-e-token-här
```

### Skaffa API-nycklar

| API | Registrering | Kostnad |
|-----|--------------|---------|
| **ENTSO-E** | https://webportal.tp.entsoe.eu/ → "My Account Settings" | Gratis |
| **eSett** | Ingen nyckel krävs | Gratis |
| **Mimer (SVK)** | Ingen nyckel krävs | Gratis |
| **elprisetjustnu.se** | Ingen nyckel krävs | Gratis |
| **Energimyndigheten** | Ingen nyckel krävs | Gratis |

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
2024-01-01T01:00:00+00:00,SE3,solar,0.0,60
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

## Dokumentation

Fördjupad dokumentation finns i `docs/`:

| Mapp | Beskrivning |
|------|-------------|
| `docs/balansmarknad/` | Svenska balansmarknaden (FCR, aFRR, mFRR) |
| `docs/bess-dimensionering/` | Batteridimensionering för PV-prognosfel |

## Framtida utveckling

- [x] ENTSO-E integration
- [x] eSett obalanspriser
- [x] mFRR energiaktivering (Mimer)
- [ ] Automatisk daglig uppdatering
- [ ] Batterioptimering / arbitrage-analys
- [ ] Historiska solprofiler per region
- [ ] Använd ENTSO-E solproduktion för capture price-beräkning
- [ ] Nord Pool intraday (kräver kundavtal)
