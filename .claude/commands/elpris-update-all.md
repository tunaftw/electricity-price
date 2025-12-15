# Master Update - Uppdatera allt

Kör hela uppdateringskedjan: ladda ner ny data, processera och generera Excel-rapporter.

## Vad som körs

1. **Spotpriser** - Inkrementell uppdatering från elprisetjustnu.se
2. **ENTSO-E** - Sol/vind-produktion (körs automatiskt om ENTSOE_TOKEN finns)
3. **Mimer** - Reglerpriser från Svenska kraftnät
4. **eSett** - Obalanspriser
5. **Process** - Konvertera raw till quarterly (15-min)
6. **Capture** - Beräkna capture prices
7. **Excel** - Generera capture_prices + battery_arbitrage rapporter
8. **Status** - Visa datastatus

## Instruktioner

Kör `python3 update_all.py`

### Flaggor

- `--zones SE3 SE4` - Endast specifika zoner
- `--skip-entsoe` - Hoppa över ENTSO-E (även om token finns)
- `--skip-mimer` - Hoppa över Mimer reglerpriser
- `--skip-esett` - Hoppa över eSett obalanspriser
- `--skip-excel` - Hoppa över Excel-generering
- `--quiet` - Tyst läge

## ENTSO-E token

Om ENTSOE_TOKEN är satt i miljön eller `.env`-filen körs ENTSO-E automatiskt.
Annars hoppas det steget över utan fel.

## Output

Excel-rapporter sparas till: `Resultat/rapporter/`
- `capture_prices_YYYYMMDD.xlsx`
- `battery_arbitrage_YYYYMMDD.xlsx`
