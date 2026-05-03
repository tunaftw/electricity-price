# Ladda ner reglerpriser från Mimer

Ladda ner FCR, aFRR, mFRR-CM och mFRR (energiaktivering) från Svenska kraftnät Mimer.

## Instruktioner

$ARGUMENTS

### Tillgängliga produkter
- **fcr** — FCR-N, FCR-D upp/ned (frekvensreglering, från 2021-01-01)
- **afrr** — aFRR upp/ned per zon (automatisk frekvensåterställning, från 2022-11-01)
- **mfrr_cm** — mFRR kapacitetsmarknad per zon (från 2024-06-01)
- **mfrr** — mFRR energiaktivering per zon (från 2022-01-01, tomt efter mars 2025 pga eSett EAM)

### Kommandon

```bash
# Alla produkter (full historik)
python3 mimer_download.py

# Specifik produkt
python3 mimer_download.py --product fcr
python3 mimer_download.py --product mfrr --start 2024-01-01 --end 2024-12-31

# Inkrementell uppdatering (sedan senast)
python3 mimer_download.py --product afrr
```

### Output

Data sparas till `Resultat/marknadsdata/mimer/{produkt}/{år}.csv`.

Scripten returnerar exit-kod 1 om någon månads-chunk misslyckas, så cron
och `update_all.py` kan upptäcka tysta API-fel.
