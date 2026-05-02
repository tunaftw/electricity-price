# Master Update - Uppdatera allt

Kör hela uppdateringskedjan (12 steg): ladda ner ny data, processera och
generera rapporter inkl. Unified Dashboard.

## Vad som körs

 1. **Spotpriser** — Inkrementell uppdatering från elprisetjustnu.se
 2. **Bazefield** — Solparksdata (körs om `BAZEFIELD_API_KEY` finns)
 3. **ENTSO-E** — Sol/vind-produktion (körs om `ENTSOE_TOKEN` finns)
 4. **Mimer** — Reglerpriser från Svenska kraftnät
 5. **Nasdaq** — Nordic futures (SYS + EPADs)
 6. **eSett** — Obalanspriser
 7. **Process** — Konvertera raw till quarterly (15-min)
 8. **Capture** — Beräkna capture prices
 9. **Excel** — Generera capture_prices + battery_arbitrage rapporter
10. **Unified Dashboard** — Generera Track A + Track C HTML
11. **Park reports** — Per-park månadsrapport (endast med `--reports`)
12. **Status** — Visa datastatus

## Instruktioner

Kör `python3 update_all.py`

### Flaggor

- `--zones SE3 SE4` — Endast specifika zoner
- `--skip-bazefield` — Hoppa över Bazefield-synk
- `--skip-entsoe` — Hoppa över ENTSO-E (även om token finns)
- `--skip-mimer` — Hoppa över Mimer reglerpriser
- `--skip-nasdaq` — Hoppa över Nasdaq futures
- `--skip-esett` — Hoppa över eSett obalanspriser
- `--skip-excel` — Hoppa över Excel-generering
- `--reports` — Generera även per-park månadsrapporter
- `--month YYYY-MM` — Specifik månad för park-rapporter (med `--reports`)
- `--quiet` — Tyst läge

## API-nycklar

- `ENTSOE_TOKEN` (i `.env` eller miljö) — krävs för ENTSO-E-steget
- `BAZEFIELD_API_KEY` (i `.env`) — krävs för Bazefield-steget

Saknas en nyckel hoppas motsvarande steg över utan fel.

## Output

Rapporter sparas till `Resultat/rapporter/`:
- `capture_prices_YYYYMMDD.xlsx`
- `battery_arbitrage_YYYYMMDD.xlsx`
- `dashboard_unified_YYYYMMDD.html` (Track A)
- `dashboard_unified_v3_YYYYMMDD.html` (Track C)
- `performance_<park>_<zone>_YYYY-MM.html` (med `--reports`)
