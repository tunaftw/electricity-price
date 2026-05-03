# Ladda ner Nasdaq Nordic futures

Ladda ner SYS baseload + EPADs (svenska zoner) från Nasdaq Nordic Commodities.

## Instruktioner

$ARGUMENTS

### Tillgängliga produkter
- **sys** — Nordic SYS baseload futures (kvartal, år)
- **epad_se** — Alla svenska EPAD-zoner
- **epad_se1 / epad_se2 / epad_se3 / epad_se4** — Specifik zon

### Kommandon

```bash
# Alla produkter, inkrementell uppdatering
python3 nasdaq_download.py

# Specifik produkt
python3 nasdaq_download.py --products sys
python3 nasdaq_download.py --products epad_se3

# Specifik period
python3 nasdaq_download.py --start 2025-01-01 --end 2026-04-03
```

### Datakälla

`https://api.nasdaq.com/api/nordic/` — odokumenterat JSON-API, ingen nyckel krävs.

**OBS:** Handeln flyttades till Euronext mars 2026, men Nasdaq publicerar
fortfarande dailyFix-priser för rapporterings­ändamål.

### Output

Data sparas till `Resultat/marknadsdata/nasdaq/futures/`:
- `sys_baseload.csv`
- `epad_se{1..4}_{lul,sun,sto,mal}.csv`

CSV-skrivningen är atomisk (tmp + rename) så filen aldrig blir trunkerad
om scriptet avbryts mitt i en skrivning.
