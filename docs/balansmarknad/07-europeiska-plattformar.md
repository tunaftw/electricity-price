# Europeiska Balanseringsplattformar

EU:s Electricity Balancing Guideline (EB GL) kräver att europeiska TSO:er samarbetar kring balansering via gemensamma plattformar. De tre huvudsakliga plattformarna är PICASSO (aFRR), MARI (mFRR) och TERRE (RR).

## Översikt

```
┌─────────────────────────────────────────────────────────────────┐
│  EUROPEISKA BALANSERINGSPLATTFORMAR                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PICASSO (aFRR)     MARI (mFRR)        TERRE (RR)               │
│  ──────────────     ───────────        ──────────               │
│  Driftstart:        Driftstart:        Driftstart:              │
│  Juni 2022          Oktober 2022       Januari 2020             │
│                                                                  │
│  Responstid:        Responstid:        Responstid:              │
│  < 7,5 min          < 12,5 min         < 30 min                 │
│                                                                  │
│  Sverige:           Sverige:           Sverige:                 │
│  Planerad           Planerad           Deltar ej                │
│  anslutning         2027-2028          (använder mFRR)          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## PICASSO - aFRR-plattformen

PICASSO (Platform for the International Coordination of Automated Frequency Restoration and Stable System Operation) är den europeiska plattformen för utbyte av aFRR-energi.

### Grundläggande information

| Egenskap | Värde |
|----------|-------|
| Driftstart | 24 juni 2022 |
| Reservtyp | aFRR (automatisk frekvensåterställning) |
| Responstid | ≤ 7,5 minuter |
| Cykel | Kontinuerlig (var 4:e sekund) |
| Ansvarig | ENTSO-E |

### Hur PICASSO fungerar

```
1. TSO:er rapporterar sitt aFRR-behov
              │
              ▼
2. Algoritm samlar in alla aFRR-bud
              │
              ▼
3. Optimering över landsgränser
              │
              ▼
4. Aktivering av billigaste bud
              │
              ▼
5. Avräkning och settlement
```

### Deltagande länder (2024)

PICASSO har gradvis utökats med fler länder:
- Tyskland, Österrike, Belgien, Frankrike, Nederländerna (tidiga deltagare)
- Italien (pausat temporärt 2024)
- Fler länder ansluter successivt

### Sveriges status

Sverige deltar **ännu inte** i PICASSO men planerar anslutning:
- Nuvarande aFRR: Nationell/nordisk upphandling
- Framtid: Övergång till ACE-baserad aFRR vid PICASSO-anslutning
- Förväntat ökat volymbehov: 160-400 MW

## MARI - mFRR-plattformen

MARI (Manually Activated Reserves Initiative) är den europeiska plattformen för utbyte av mFRR-energi.

### Grundläggande information

| Egenskap | Värde |
|----------|-------|
| Driftstart | 2 december 2022 |
| Reservtyp | mFRR (manuell frekvensåterställning) |
| Responstid | ≤ 12,5 minuter |
| Cykel | Diskret (per 15-minutersperiod) |
| Ansvarig | ENTSO-E |

### Hur MARI fungerar

```
┌─────────────────────────────────────────────────────────────────┐
│  MARI OPTIMIZATION FUNCTION (MOF)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input:                         Output:                          │
│  • mFRR-bud från TSO:er         • Aktiverade bud per område     │
│  • Behov per budområde          • Marginalpris per område       │
│  • Överföringskapacitet         • Gränsöverskridande flöden     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Sveriges status

Sverige förväntas ansluta till MARI **2027-2028**:
- Nuvarande: Nordisk mFRR EAM (mars 2025)
- Framtida: Full integration med MARI
- Effekt: Större optimeringsområde, potentiellt lägre kostnader

### Nordisk mFRR EAM vs MARI

```
┌─────────────────────────┐     ┌─────────────────────────┐
│  NORDISK mFRR EAM       │     │  MARI                   │
│  (nuvarande)            │     │  (framtida)             │
├─────────────────────────┤     ├─────────────────────────┤
│  Länder: NO, SE, FI, DK │     │  Länder: Hela EU        │
│  Algoritm: AOF          │     │  Algoritm: MOF          │
│  Start: Mars 2025       │     │  Start: Dec 2022        │
│  Sverige: Deltar        │     │  Sverige: Planerad      │
└─────────────────────────┘     └─────────────────────────┘
```

## TERRE - RR-plattformen

TERRE (Trans European Replacement Reserve Exchange) är plattformen för ersättningsreserver (RR).

### Grundläggande information

| Egenskap | Värde |
|----------|-------|
| Driftstart | 6 januari 2020 |
| Reservtyp | RR (Replacement Reserve) |
| Responstid | ≤ 30 minuter |
| Syfte | Ersätta aktiverad aFRR/mFRR |
| Ansvarig | ENTSO-E |

### Sveriges status

Sverige deltar **inte** i TERRE:
- RR används främst i länder med lång aktiveringstid
- Sverige använder mFRR för motsvarande ändamål
- Ingen planerad anslutning

## IGCC - Imbalance Netting

Utöver de tre huvudplattformarna finns IGCC (International Grid Control Cooperation) som netto:ar obalanser mellan länder.

### Hur IGCC fungerar

```
Land A har underskott: -100 MW
Land B har överskott:  +80 MW
                       ─────────
Netto aktivering:       20 MW

Istället för att båda aktiverar reserver separat,
netto:as obalanserna och endast differensen hanteras.
```

### Fördelar
- Minskade balanseringskostnader
- Färre aktiveringar
- Effektivare resursanvändning

## Tidslinje för europeisk integration

```
Tid →

2020        2022         2024         2026         2028
  │           │            │            │            │
  ▼           ▼            ▼            ▼            ▼
TERRE      PICASSO      Trilateral   Sverige     Sverige
startar    MARI         mFRR CM      ansluter    ansluter
           startar      (SE/FI/DK)   PICASSO?    MARI?
```

## Påverkan på svenska aktörer

### Möjligheter

1. **Större marknad**: Fler köpare av flexibilitet
2. **Effektivare priser**: Bättre prisoptimering
3. **Konkurrens**: Stimulerar innovation
4. **Export av flexibilitet**: Svenska resurser kan sälja till Europa

### Utmaningar

1. **Komplexare regler**: Harmoniserade krav
2. **Systemanpassningar**: IT-system måste uppgraderas
3. **Prisvolatilitet**: Kan öka vid gränsöverskridande handel
4. **Lokala behov**: Risk att lokala resurser prioriteras bort

## Electricity Balancing Guideline (EB GL)

### Bakgrund

EB GL är EU-förordningen som reglerar balansmarknaden:
- **Förordning**: (EU) 2017/2195
- **Syfte**: Harmonisera balanseringsmarknader i EU
- **Mål**: Effektiv, konkurrensutsatt balansmarknad

### Huvudkrav

1. **Gemensamma plattformar** för utbyte av balansenergi
2. **Standardiserade produkter** för reserver
3. **Transparenta priser** och data
4. **Icke-diskriminerande tillgång** för alla aktörer

## Framtida utveckling

### Kortsiktigt (2025-2026)
- Stabilisering av nordisk mFRR EAM
- Fortsatt utbyggnad av PICASSO/MARI
- Sverige förbereder anslutning

### Medellångt (2027-2030)
- Sverige i MARI
- Potentiellt Sverige i PICASSO
- Ökad europeisk integration

### Långsiktigt
- Fullt integrerad europeisk balansmarknad
- Real-tidshandel över kontinenten
- Optimerad användning av alla flexibilitetsresurser

## Dataresurser

### ENTSO-E Transparency Platform
- URL: https://transparency.entsoe.eu/
- Innehåll: Balansdata för hela Europa
- Format: Webbgränssnitt och API

### ENTSO-E Rapporter
- Electricity Balancing Cost Report (årlig)
- Information om PICASSO/MARI/TERRE

## Källor

- [ENTSO-E - PICASSO](https://www.entsoe.eu/network_codes/eb/picasso/)
- [ENTSO-E - Electricity Balancing](https://www.entsoe.eu/network_codes/eb/)
- [ENTSO-E - Balancing Cost Report 2024](https://eepublicdownloads.entsoe.eu/clean-documents/nc-tasks/240628_ENTSO-E_Electricity_Balancing_Cost_Report_2024.pdf)
- [Nordic Balancing Model](https://nordicbalancingmodel.net/)
- [Svenska kraftnät - mFRR EAM](https://www.svk.se/utveckling-av-kraftsystemet/systemansvar--elmarknad/ny-nordisk-balanseringsmodell-nbm/automatiserad-nordisk-energiaktiveringsmarknad-for-mfrr/)
- [Nano Energies - MARI, PICASSO, TERRE](https://nanoenergies.eu/knowledge-base/mari-picasso-and-terre)
