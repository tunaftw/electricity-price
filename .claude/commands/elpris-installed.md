# Ladda ner installerad kapacitet

Ladda ner statistik över installerad sol- och vindkraft från Energimyndigheten (PxWeb API).

## Instruktioner

$ARGUMENTS

### Kommando

```bash
python3 installed_download.py
```

### Tillgänglig data

**Vindkraft per elområde (2003-):**
- Antal verk
- Installerad effekt (MW)
- Elproduktion (GWh)
- Per zon: SE1, SE2, SE3, SE4

**Solcellsanläggningar (2016-):**
- Antal anläggningar
- Installerad effekt (MW)
- Per region/län
- Per effektklass (< 20 kW, 20 kW-1 MW, > 1 MW)

### Datakälla

Officiell svensk energistatistik från Energimyndigheten (PxWeb REST API). Ingen nyckel.

### Output

Data sparas till:
- `Resultat/marknadsdata/installerad/wind_by_elarea.csv`
- `Resultat/marknadsdata/installerad/solar_installations.csv`
