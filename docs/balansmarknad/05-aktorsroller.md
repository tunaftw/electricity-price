# Aktörsroller - BRP och BSP

Sedan 1 maj 2024 finns två separata aktörsroller på den svenska balansmarknaden: **BRP** (Balance Responsible Party / Balansansvarig part) och **BSP** (Balancing Service Provider / Leverantör av balanstjänster).

## Översikt

```
┌──────────────────────────────────────────────────────────────────┐
│                        ELMARKNADEN                               │
├────────────────────────────┬─────────────────────────────────────┤
│          BRP               │              BSP                    │
│  (Balansansvarig part)     │  (Leverantör av balanstjänster)     │
├────────────────────────────┼─────────────────────────────────────┤
│  Planerar balans           │  Levererar reserver                 │
│  Handlar på spotmarknad    │  Säljer FCR, aFRR, mFRR             │
│  Betalar för obalanser     │  Får ersättning för aktivering      │
│  Avtal med eSett           │  Avtal med Svenska kraftnät         │
└────────────────────────────┴─────────────────────────────────────┘
```

## BRP - Balansansvarig Part

### Definition

En BRP har det affärsmässiga och planeringsmässiga ansvaret för att det är balans mellan tillförsel och uttag av el inom sitt ansvarsområde.

### Ansvar och skyldigheter

1. **Planera balans** per timme/kvart för sin portfölj
2. **Handla på spotmarknaden** (Nord Pool)
3. **Rapportera** handelsscheman till Svenska kraftnät
4. **Betala obalansavgifter** om planering avviker från utfall
5. **Ställa ekonomisk säkerhet** hos eSett

### Exempel på BRP:er
- Elproducenter
- Elhandelsbolag
- Stora industriföretag
- Aggregatorer

### Obalansavräkning

När en BRP misslyckas med att balansera uppstår en obalans som avräknas:

```
Obalans = Faktiskt utfall - Planerad balans

Om obalans > 0: BRP har överskott → säljer till obalanspris
Om obalans < 0: BRP har underskott → köper till obalanspris
```

### Bli BRP - Process

1. **Registrera intresse** hos eSett (settlement@esett.com)
2. **Anmäl till Svenska kraftnät** för Ediel-konto
3. **Teckna Ediel-avtal** med Svenska kraftnät
4. **Klara systemtest** i Ediel-portalen
5. **Ställ säkerhet** hos eSett
6. **BRP-avtal** aktiveras

## BSP - Leverantör av Balanstjänster

### Definition

En BSP är en aktör med godkända förkvalificerade enheter som kan erbjuda stödtjänster (FCR, aFRR, mFRR) till Svenska kraftnät.

### Ansvar och skyldigheter

1. **Leverera reserver** enligt avtal och bud
2. **Uppfylla tekniska krav** för respektive stödtjänst
3. **Rapportera mätdata** i realtid (för aFRR)
4. **Följa aktiveringssignaler** vid avrop

### BSP-avtalet

BSP-avtalet med bilagor reglerar:
- Vilka stödtjänster som får levereras
- Tekniska krav per stödtjänst
- Sanktioner vid underleverans
- Ersättningsmodeller

### Bli BSP - Process

1. **Förkvalificera resurser** (test av tekniska krav)
2. **Teckna BSP-avtal** via eSett
3. **Registrera resurser** i Svenska kraftnäts system
4. **Börja handla** på kapacitets- och energimarknader

**Nuvarande krav (2024):** För att bli BSP måste man också vara BRP eller ha avtal med en BRP.

### Underleverantörer

En BSP kan använda underleverantörer:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   BSP       │────▶│ Underlev.   │────▶│ Slutkund    │
│ (avtalspart)│     │ (aggregator)│     │ (batteri)   │
└─────────────┘     └─────────────┘     └─────────────┘
        │
        ▼
   Ansvarar mot
   Svenska kraftnät
```

BSP:n är alltid ytterst ansvarig även om en underleverantör levererar stödtjänsten.

## Relation mellan BRP och BSP

### Nuvarande modell (2024)

```
┌─────────────────────────────────────────┐
│  Samma aktör är både BRP och BSP        │
│  ELLER                                   │
│  BSP har avtal med en BRP               │
└─────────────────────────────────────────┘
```

### Framtida modell (~2028)

```
┌─────────────────────────────────────────┐
│  BSP kan vara helt oberoende av BRP     │
│  - Inga krav på BRP-koppling            │
│  - Förenklad marknadstillgång           │
│  - Möjliggör nya affärsmodeller         │
└─────────────────────────────────────────┘
```

## Obalanshantering och BRP

### Single Price Model (sedan 2021)

Alla BRP:er i ett elområde möter samma obalanspris oavsett riktning på sin obalans:

```
Systemet har underskott:
- BRP med underskott: Köper till högt pris (bestraffas)
- BRP med överskott: Säljer till högt pris (belönas)

Systemet har överskott:
- BRP med överskott: Säljer till lågt pris (bestraffas)
- BRP med underskott: Köper till lågt pris (belönas)
```

### Obalansavgift (Imbalance Fee)

Utöver obalanspriset betalar BRP:er en fast avgift:
- **1,15 EUR/MWh** (harmoniserat i Norden sedan 2021)

Syftet är att motverka spekulativ trading mot obalanspriset.

## Ekonomiska flöden

```
                    ┌─────────────────┐
                    │ Svenska kraftnät│
                    │     (TSO)       │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│     BSP       │   │     eSett     │   │    BRP        │
│ FCR/aFRR/mFRR │   │ Obalansavrä.  │   │ Handel/obal.  │
│  ersättning   │   │               │   │  kostnad      │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Sanktioner

### BSP - Underleverans

Om en BSP inte levererar kontrakterad stödtjänst:
- Utebliven kapacitetsersättning
- Eventuell sanktionsavgift
- Vid upprepade brister: Avstängning

### BRP - Stora obalanser

BRP:er med stora obalanser:
- Betalar obalanspris (kan vara extremt)
- Betalar obalansavgift
- Kan vid systematiska problem få förhöjda säkerhetskrav

## Privatpersoner och stödtjänster

Sedan 2023 kan även privatpersoner delta via aggregatorer:

```
Privatperson → Aggregator (BSP) → Svenska kraftnät
   │                │
   └── Batteri ─────┘
   └── Elbil ───────┘
   └── Värmepump ───┘
```

Privatpersonen behöver inte själv vara BSP utan levererar via en aggregator.

## Viktiga avtal

| Avtal | Parter | Syfte |
|-------|--------|-------|
| **BSP-avtal** | BSP ↔ Svenska kraftnät | Leverans av stödtjänster |
| **BRP-avtal** | BRP ↔ Svenska kraftnät | Balansansvar |
| **Ediel-avtal** | Aktör ↔ Svenska kraftnät | Elektronisk kommunikation |
| **eSett-avtal** | BRP ↔ eSett | Obalansavräkning |

## Källor

- [Svenska kraftnät - BRP](https://www.svk.se/aktorsportalen/balansansvarig-part/)
- [Svenska kraftnät - BSP](https://www.svk.se/aktorsportalen/leverantor-av-balanstjanster-bsp/)
- [Svenska kraftnät - BSP-avtalet](https://www.svk.se/aktorsportalen/leverantor-av-balanstjanster-bsp/bsp-avtalet/)
- [Svenska kraftnät - BSP/BRP införande](https://www.svk.se/utveckling-av-kraftsystemet/systemansvar--elmarknad/inforande-av-aktorsrollerna-bsp-och-brp/)
- [Energimarknadsinspektionen - BSP/BRP villkor](https://ei.se/om-oss/nyheter/2023/2023-05-25-ei-har-tagit-beslut-om-villkor-for-leverantorer-av-balanstjanster-och-balansansvariga-parter)
