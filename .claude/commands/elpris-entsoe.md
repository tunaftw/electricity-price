# Ladda ner ENTSO-E produktionsdata

Ladda ner faktisk produktionsdata (sol, vind, kärnkraft) från ENTSO-E Transparency Platform
för SE1–SE4 och DK1/DK2, samt day-ahead-priser för DK1/DK2.

## Krav

**API-token krävs!** Sätt miljövariabeln `ENTSOE_TOKEN` eller skapa en `.env`-fil:
```bash
export ENTSOE_TOKEN=din-token-här
# eller
echo "ENTSOE_TOKEN=din-token-här" >> .env
```

Skaffa token på: https://webportal.tp.entsoe.eu/ (My Account Settings)

## Instruktioner

1. Kontrollera att ENTSOE_TOKEN är satt
2. Kör `python3 entsoe_download.py` — sol och vind för SE1–SE4, plus DK1/DK2 sol
   och DK1/DK2 day-ahead-priser (allt inkrementellt)

### Flaggor

- `--zones SE3 SE4` - Specifika zoner (SE1–SE4, DK1, DK2). Anger du zoner körs bara de.
- `--types solar wind_onshore nuclear` - Specifika produktionstyper
- `--start 2024-01-01 --end 2024-12-31` - Specifikt datumintervall (`--end` inklusive; default igår)
- `--prices` - Day-ahead-priser (A44) i stället för produktion (default-zoner DK1 DK2)
- `--with-dk` - Lägg till DK1/DK2 sol + DK1/DK2 priser när `--zones` anges (för `update_all.py`)
- `--no-dk` - Hoppa över DK-delen i en körning utan argument

### Exempel

```bash
python3 entsoe_download.py --zones DK1 DK2 --types solar           # DK-sol
python3 entsoe_download.py --prices --zones DK1 DK2                # DK-priser, inkrementellt
python3 entsoe_download.py --prices --start 2022-01-01 --end 2026-09-22
python3 entsoe_download.py --zones SE1 SE2 SE3 SE4 --types solar wind_onshore --with-dk
```

### DK-priser — lagring

- `Resultat/marknadsdata/spotpriser/DK1/YYYY.csv` — samma format som de svenska filerna
  (`time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR`, svensk lokaltid, lokal-år-filer).
- `EXR` (SEK/EUR) tas per dygn från SE3-filen; saknas den blir SEK/EXR tomma och fylls
  i vid nästa körning.
- Upplösning: 60 min fram till 2025-10-01, därefter 15 min. `data/quarterly/DK1/` genereras
  om automatiskt (och av `python3 process.py`).
- `--prices` för SE-zoner skriver till `Resultat/marknadsdata/entsoe/prices/<zon>/` — de
  svenska elprisetjustnu-filerna skrivs aldrig över.

### Tillgängliga typer

- `solar` - Solproduktion
- `wind_onshore` - Landbaserad vindkraft
- `wind_offshore` - Havsbaserad vindkraft (ej i Sverige ännu; finns i DK)
- `hydro_water_reservoir` - Vattenkraft (magasin)
- `nuclear` - Kärnkraft (endast SE3, SE4)

## Varning

Nedladdning av full historik (2015-idag) tar ca 30-60 minuter pga API rate limiting.
ENTSO-E utelämnar upprepade värden (curveType A03); parsern fyller dem framåt.
