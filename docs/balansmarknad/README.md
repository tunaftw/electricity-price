# Svenska Balansmarknaden - Kunskapsbank

Denna kunskapsbank innehåller detaljerad information om den svenska och nordiska balansmarknaden, dess olika produkter, aktörsroller och prissättningsmekanismer.

## Innehåll

| Dokument | Beskrivning |
|----------|-------------|
| [01 Översikt](01-oversikt.md) | Grundläggande om balansmarknaden och kraftsystemets balansering |
| [02 FCR](02-fcr.md) | Frekvenshållningsreserver (FCR-N, FCR-D upp, FCR-D ned) |
| [03 aFRR](03-afrr.md) | Automatisk frekvensåterställningsreserv |
| [04 mFRR](04-mfrr.md) | Manuell frekvensåterställningsreserv (kapacitet och energi) |
| [05 Aktörsroller](05-aktorsroller.md) | BRP (balansansvarig) och BSP (balanstjänstleverantör) |
| [06 Obalanspriser](06-obalanspriser.md) | Obalansavräkning och prissättning |
| [07 Europeiska plattformar](07-europeiska-plattformar.md) | MARI, PICASSO, TERRE |

## Snabböversikt - Reservprodukter

| Produkt | Aktivering | Responstid | Uthållighet | Marknad |
|---------|------------|------------|-------------|---------|
| **FCR-N** | Automatisk (frekvens) | Kontinuerlig | 60 min | D-1 kapacitet |
| **FCR-D upp** | Automatisk (frekvens) | 5-30 sek | 20 min | D-1 kapacitet |
| **FCR-D ned** | Automatisk (frekvens) | 5-30 sek | 20 min | D-1 kapacitet |
| **aFRR** | Automatisk (signal) | < 5 min | 15 min | D-1 kapacitet |
| **mFRR** | Manuell/Automatisk | 15 min | 15-30 min | D-1 kapacitet + energi |

## Viktiga datum och milstolpar

| Datum | Händelse |
|-------|----------|
| 2021-11-01 | Single Price Model införs i Norden |
| 2022-06-24 | PICASSO (europeisk aFRR-plattform) driftsatt |
| 2022-10-01 | MARI (europeisk mFRR-plattform) driftsatt |
| 2023-05-22 | 15-minuters obalansavräkning införs |
| 2023-09-01 | Nya tekniska krav för FCR träder i kraft |
| 2023-09-01 | Nationell kapacitetsmarknad för mFRR startar |
| 2024-05-01 | BSP- och BRP-rollerna införs officiellt |
| 2024-11-19 | Trilateral mFRR-kapacitetsmarknad (SE/FI/DK) |
| 2025-03-04 | mFRR EAM (automatiserad energiaktivering) startar |
| 2025-09-30 | 15-minuters day-ahead handel införs |
| ~2027-2028 | Sverige ansluter till MARI |

## Officiella källor

- [Svenska kraftnät - Aktörsportalen](https://www.svk.se/aktorsportalen/)
- [eSett - Nordic Imbalance Settlement](https://www.esett.com/)
- [Nordic Balancing Model](https://nordicbalancingmodel.net/)
- [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/)
- [Energimarknadsinspektionen](https://ei.se/)

## Dataåtkomst

I detta projekt finns skript för att ladda ner data från:
- `mimer_download.py` - FCR, aFRR, mFRR priser från Svenska kraftnät Mimer
- `esett_download.py` - Obalanspriser från eSett
- Se [CLAUDE.md](../../CLAUDE.md) för fullständig dokumentation
