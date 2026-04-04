# Ladda ner eSett obalanspriser

Ladda ner obalanspriser från eSett Nordic Imbalance Settlement.

## Om eSett

eSett hanterar obalansavräkning för de nordiska länderna. API:t är helt öppet - ingen nyckel krävs.

**Data tillgänglig från:** 2023-05-22
**Upplösning:** 15 minuter

## Instruktioner

1. Kör `python3 esett_download.py` för att ladda ner obalanspriser för alla zoner

### Flaggor

- `--zones SE3 SE4` - Specifika zoner
- `--start 2024-01-01 --end 2024-12-31` - Specifikt datumintervall

## Dataformat

Kolumner i nedladdad data:
- `imbl_sales_price_eur_mwh` - Försäljningspris vid obalans (EUR/MWh)
- `imbl_purchase_price_eur_mwh` - Köppris vid obalans (EUR/MWh)
- `up_reg_price_eur_mwh` - Uppregleringsintervall (EUR/MWh)
- `down_reg_price_eur_mwh` - Nedregleringsintervall (EUR/MWh)

Data sparas till: `Resultat/marknadsdata/esett/imbalance/`
