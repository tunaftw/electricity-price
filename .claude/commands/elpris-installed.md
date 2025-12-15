# Ladda ner installerad kapacitet

Ladda ner statistik över installerad sol- och vindkraft från Energimyndigheten.

## Instruktioner

$ARGUMENTS

### Kommando:

```bash
python3 installed_download.py
```

### Tillgänglig data:

**Vindkraft per elområde (2003-2024):**
- Antal verk
- Installerad effekt (MW)
- Elproduktion (GWh)
- Per zon: SE1, SE2, SE3, SE4

**Solcellsanläggningar (2016-2024):**
- Antal anläggningar
- Installerad effekt (MW)
- Per region/län
- Per effektklass (< 20 kW, 20 kW-1 MW, > 1 MW)

### Datakälla:
Officiell svensk energistatistik från Energimyndigheten (PxWeb API).

### Output:
Data sparas till:
- `data/raw/installed/wind_by_elarea.csv`
- `data/raw/installed/solar_installations.csv`
