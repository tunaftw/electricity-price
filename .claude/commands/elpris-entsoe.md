# Ladda ner ENTSO-E produktionsdata

Ladda ner faktisk produktionsdata (sol, vind, kärnkraft) från ENTSO-E Transparency Platform.

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
2. Kör `python3 entsoe_download.py` för att ladda ner sol och vind för alla zoner

### Flaggor

- `--zones SE3 SE4` - Specifika zoner
- `--types solar wind_onshore nuclear` - Specifika produktionstyper
- `--start 2024-01-01 --end 2024-12-31` - Specifikt datumintervall

### Tillgängliga typer

- `solar` - Solproduktion
- `wind_onshore` - Landbaserad vindkraft
- `wind_offshore` - Havsbaserad vindkraft (ej i Sverige ännu)
- `hydro_water_reservoir` - Vattenkraft (magasin)
- `nuclear` - Kärnkraft (endast SE3, SE4)

## Varning

Nedladdning av full historik (2015-idag) tar ca 30-60 minuter pga API rate limiting.
