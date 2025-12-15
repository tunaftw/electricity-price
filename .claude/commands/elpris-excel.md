# Generera Excel-rapporter

Generera Excel-rapporter med capture prices och batterianalys.

## Instruktioner

### Capture Price Excel

```bash
python3 -c "from elpris.excel_export import export_capture_excel; print(export_capture_excel())"
```

Genererar: `Resultat/rapporter/capture_prices_YYYYMMDD.xlsx`

**Innehåll:**
- Summary (årlig data för alla zoner)
- Per zon (SE1-SE4) med månadsdata
- Capture price (EUR/MWh) per profil
- Capture ratio (%)
- Baseload pris (EUR/MWh)

### Battery Arbitrage Excel

```bash
python3 -c "from elpris.battery_excel import export_battery_excel; print(export_battery_excel())"
```

Genererar: `Resultat/rapporter/battery_arbitrage_YYYYMMDD.xlsx`

**Innehåll:**
- Summary (årlig data - spread, intäkter, lönsamhet)
- Per zon (månadsdata + årssammanfattningar)
- Dagliga detaljer med månadssummor
- 24-timmarsprofil för alla zoner

### Alla rapporter via update_all

```bash
python3 update_all.py --skip-entsoe --skip-mimer --skip-esett
```

Detta genererar Excel-rapporter utan att uppdatera extern data.

## Krav

Kräver openpyxl: `pip install openpyxl`
