# Ladda ner reglerpriser från Mimer

Ladda ner FCR, aFRR och mFRR-priser från Svenska kraftnät Mimer.

## Instruktioner

$ARGUMENTS

### Tillgängliga produkter:
- **fcr** - FCR-N, FCR-D upp/ned (frekvensreglering)
- **afrr** - aFRR upp/ned per zon (automatisk frekvensåterställning)
- **mfrr_cm** - mFRR kapacitetsmarknad per zon

### Kommandon:

```bash
# Ladda ner alla produkter (full historik)
python3 mimer_download.py

# Ladda ner specifik produkt
python3 mimer_download.py --product fcr

# Ladda ner för specifikt datumintervall
python3 mimer_download.py --product afrr --start 2024-01-01 --end 2024-12-31
```

### Datatillgänglighet:
- FCR: från 2021-01-01
- aFRR: från 2022-11-01
- mFRR-CM: från 2024-06-01

### Output:
Data sparas till `data/raw/mimer/{produkt}/{år}.csv`
