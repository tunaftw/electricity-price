# FCR - Frekvenshållningsreserver

FCR (Frequency Containment Reserve) är den snabbaste reservtypen och aktiveras automatiskt vid frekvensavvikelser. FCR:s uppgift är att *stoppa* frekvensavvikelsen - inte återställa den till 50 Hz.

## Översikt av FCR-produkter

| Produkt | Frekvensområde | Aktivering | Uthållighet | Symmetri |
|---------|----------------|------------|-------------|----------|
| **FCR-N** | 49,9 - 50,1 Hz | Proportionell | 60 min | Symmetrisk (upp + ned) |
| **FCR-D upp** | 49,5 - 49,9 Hz | Full vid 49,5 Hz | 20 min | Endast upp |
| **FCR-D ned** | 50,1 - 50,5 Hz | Full vid 50,5 Hz | 20 min | Endast ned |

## FCR-N (Normaldrift)

FCR-N är aktiv kontinuerligt och justerar produktionen proportionellt mot frekvensavvikelsen.

### Tekniska krav

```
Frekvensintervall: 49,9 - 50,1 Hz
Aktivering:        Proportionell mot frekvensavvikelse
                   100% aktivering vid ±0,1 Hz
Responstid:        63% inom 60 sekunder
Full aktivering:   100% inom 3 minuter
Uthållighet:       Minst 60 minuter vid 100% aktivering
```

### Aktiveringsmönster

```
        Effekt
          ▲
    100%  │         ╱
          │       ╱
          │     ╱
      0%  ├───•───────────────► Frekvens
          │     ╲
          │       ╲
   -100%  │         ╲
          └──────────────────
              49.9  50.0  50.1 Hz
```

### Volymkrav 2024
- **235 MW** totalt i det nordiska synkronområdet
- Minst 2/3 av Sveriges andel måste upphandlas inom Sverige

## FCR-D upp (Störning uppreglering)

FCR-D upp aktiveras vid större underfrekvens och är dimensionerad för att hantera det största enskilda felet i systemet.

### Tekniska krav

```
Frekvensintervall: 49,5 - 49,9 Hz
Aktivering:        Börjar vid 49,9 Hz
                   100% aktivering vid 49,5 Hz
Responstid:        50% inom 5 sekunder
                   100% inom 30 sekunder
Uthållighet:       Minst 20 minuter vid 100% aktivering
```

### Aktiveringsmönster

```
        Effekt
          ▲
    100%  │  ████████████
          │      ▲
     50%  │      │ Ramp
          │      │
      0%  ├──────┴───────────► Frekvens
          │
          └──────────────────
              49.5  49.7  49.9 50.0 Hz
```

### Volymkrav 2024
- **Max 567 MW** (baserat på Oskarshamn 3 - 1450 MW dimensionerande fel)
- Varierar beroende på det aktuella dimensionerande felet

## FCR-D ned (Störning nedreglering)

FCR-D ned aktiveras vid överfrekvens och är dimensionerad för att hantera bortfall av stora utlandskablar.

### Tekniska krav

```
Frekvensintervall: 50,1 - 50,5 Hz
Aktivering:        Börjar vid 50,1 Hz
                   100% aktivering vid 50,5 Hz
Responstid:        50% inom 5 sekunder
                   100% inom 30 sekunder
Uthållighet:       Minst 20 minuter vid 100% aktivering
```

### Volymkrav 2024
- **Max 547 MW** (baserat på NSL/NordLink - 1400 MW dimensionerande fel)
- Upptrappning under 2022-2024:
  - Q1 2024: 365 MW
  - Q4 2024: 470 MW
  - 2025: Fullt volymbehov 547 MW

## Marknadsstruktur

### Upphandling

FCR upphandlas på kapacitetsmarknad dagen före drift (D-1) via två kompletterande auktioner:

```
Auktion 1: Morgon D-1
Auktion 2: Eftermiddag D-1 (kompletterande)
```

### Prissättning

Från 1 februari 2024 används **marginalpris** för FCR-kapacitet. Tidigare användes pay-as-bid.

**Marginalpris**: Alla antagna bud får betalt enligt det högsta antagna budets pris.

### Ersättning

```
Kapacitetsersättning = Marginalpris (EUR/MW) × Såld kapacitet (MW)
```

## Lämpliga resurser

### FCR-N
- Vattenkraft (traditionellt)
- Batterier (snabb respons)
- Förbrukningsflexibilitet

### FCR-D upp
- Vattenkraft
- Gasturbin
- Batterier
- Förbrukningsfrånkoppling

### FCR-D ned
- Förbrukning som kan öka
- Produktion som kan minska
- Batterier (laddning)
- Vindkraft (nedreglering)

## Förkvalificering

För att leverera FCR krävs:

1. **BSP-avtal** med Svenska kraftnät
2. **Förkvalificeringstest** av tekniska krav
3. **Kommunikationsinfrastruktur** för mätning och rapportering

### Minsta storlek
- **Förkvalificering**: 0,5 MW (hälften av minsta budstorlek)
- **Minsta bud**: 1 MW

## Prishistorik

FCR-priser publiceras via [Svenska kraftnät Mimer](https://mimer.svk.se/) och i månatliga rapporter.

Typiska prisnivåer (kan variera kraftigt):
- **FCR-N**: 10-50 EUR/MW,h
- **FCR-D upp**: 5-30 EUR/MW,h
- **FCR-D ned**: 2-20 EUR/MW,h

## Tekniska kravdokument

De fullständiga tekniska kraven finns i:
- "Tekniska villkor för förkvalificering och leverans av FCR"
- Tillgängligt på [svk.se](https://www.svk.se/aktorsportalen/bidra-med-reserver/)

## Källor

- [Svenska kraftnät - FCR-N](https://www.svk.se/aktorsportalen/bidra-med-reserver/om-olika-reserver/fcr-n/)
- [Svenska kraftnät - FCR-D upp](https://www.svk.se/aktorsportalen/bidra-med-reserver/om-olika-reserver/fcr-d-upp/)
- [Svenska kraftnät - FCR-D ned](https://www.svk.se/aktorsportalen/bidra-med-reserver/om-olika-reserver/fcr-d-ned/)
- [Svenska kraftnät - Nya tekniska krav för FCR](https://www.svk.se/press-och-nyheter/nyheter/elmarknad-allmant/2023/utgivelse-av-nya-tekniska-krav-for-frekvenshallningsreserver-fcr/)
