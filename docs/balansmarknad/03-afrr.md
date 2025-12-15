# aFRR - Automatisk Frekvensåterställningsreserv

aFRR (automatic Frequency Restoration Reserve) är en sekundärreserv som aktiveras automatiskt via styrsignal från Svenska kraftnät. Till skillnad från FCR som stabiliserar frekvensen, har aFRR till uppgift att *återställa* frekvensen till 50 Hz.

## Grundläggande funktion

```
FCR aktiverad    →    aFRR tar över    →    FCR frigörs
(frekvens stabil      (frekvens återställs    (redo för nästa
 men inte 50 Hz)       till 50 Hz)             störning)
```

### Aktiveringskedja

```
Tid →
     0        30 sek     2 min       5 min      15 min
     │           │         │           │           │
     ▼           ▼         ▼           ▼           ▼
  Störning    FCR        FCR        aFRR        mFRR
  inträffar   full      stabil     tar över    avlastar
              aktiv
```

## Tekniska krav

```
Aktivering:        Automatisk via styrsignal (setpoint)
Kommunikation:     Realtid - signal var 4:e sekund
Rampning:          Minst 7% av kapaciteten per minut
Full aktivering:   100% inom 5 minuter
Uthållighet:       Minst 15 minuter vid 100% aktivering
Minsta budstorlek: 1 MW
```

### Styrning

aFRR styrs via en kontinuerlig signal (setpoint) från Svenska kraftnät:
- Setpoint anger önskad effektnivå i MW
- Resursen ska följa setpoint inom definierade toleranser
- Signalen uppdateras var 4:e sekund

```
    Setpoint (MW)
         ▲
    +100 │    ╭──╮
         │   ╱    ╲      ╭──
      0  ├──╯      ╲    ╱
         │          ╲──╯
   -100  │
         └────────────────────► Tid
```

## Marknadsstruktur

### Kapacitetsmarknad

aFRR upphandlas på kapacitetsmarknad dagen före drift (D-1).

**Från 3 mars 2025:**
- Upphandling alla timmar, alla dagar
- 500 MW upp + 500 MW ned

### Budgivning

```
Budperiod:    D-1 (dagen före drift)
Budstorlek:   Min 1 MW
Budformat:    Per elområde
Prissättning: Marginalpris
```

### Ersättning

```
Kapacitetsersättning = Marginalpris (EUR/MW) × Kontrakterad kapacitet (MW)
Energiersättning     = Aktiverad energi (MWh) × Energipris (EUR/MWh)
```

## Skillnad mot FCR och mFRR

| Egenskap | FCR | aFRR | mFRR |
|----------|-----|------|------|
| Aktivering | Frekvens (lokal) | Signal (central) | Signal (central) |
| Responstid | Sekunder | Minuter | 15 minuter |
| Styrning | Automatisk | Automatisk | Manuell/Auto |
| Syfte | Stoppa avvikelse | Återställa frekvens | Återställa frekvens |

## Kommunikationskrav

Till skillnad från FCR kräver aFRR **realtidskommunikation** med Svenska kraftnät:

```
Svenska kraftnät  ←→  Resursägare
      │                    │
   Setpoint           Mätdata
   (4 sek)            (4 sek)
```

### Krav på kommunikation
- Latens: < 2 sekunder
- Tillgänglighet: > 98%
- Protokoll: Specificeras i tekniska villkor
- Redundans: Rekommenderas

**Viktigt**: Ingen dispens ges för realtidskommunikation vid aFRR - detta är ett absolut krav.

## Lämpliga resurser

### Etablerade tekniker
- **Vattenkraft** - Traditionell leverantör, snabb respons
- **Gasturbiner** - Snabb uppstart, hög tillgänglighet
- **Pumpkraft** - Kan både producera och konsumera

### Nya möjligheter
- **Batterier** - Mycket snabb respons, begränsad uthållighet
- **Aggregerade resurser** - Många små resurser sammantaget
- **Industriell förbrukning** - Processer med flexibilitet

## Förkvalificering

### Process

1. **Ansökan** till Svenska kraftnät
2. **Teknisk dokumentation** av resursens egenskaper
3. **Förkvalificeringstest** med godkänt resultat
4. **BSP-avtal** signeras

### Testkrav
- Resursens förmåga att följa setpoint
- Kommunikationens tillförlitlighet
- Mätningens noggrannhet
- Rampningshastighet

## Framtida utveckling - PICASSO

Sverige planerar att ansluta till den europeiska aFRR-plattformen PICASSO (Platform for the International Coordination of Automated Frequency Restoration and Stable System Operation).

### Nuvarande status
- PICASSO driftsattes juni 2022
- Sverige deltar ännu inte
- Planerad anslutning: Framtida (ej fastställt datum)

### Vad innebär PICASSO?
- Gemensam europeisk marknad för aFRR-energi
- Automatisk optimering över landsgränser
- Ändrad dimensionering baserat på ACE (Area Control Error)
- Förväntat ökat behov: 160-400 MW

### ACE-baserad aFRR

Vid övergång till PICASSO ändras dimensionering:

**Nuvarande**: Baserat på frekvenskvalitet (hela Norden)
**Framtida**: Baserat på ACE per budområde

```
ACE = Planerad export - Faktisk export + Bias × Frekvensavvikelse
```

Detta innebär att varje budområde ansvarar för sina egna obalanser, vilket ökar behovet av lokal aFRR-kapacitet.

## Prisdata

aFRR-priser publiceras via:
- [Svenska kraftnät Mimer](https://mimer.svk.se/)
- Månadsrapporter från Svenska kraftnät

### Typiska prisnivåer
Priserna varierar kraftigt beroende på:
- Tid på dygnet
- Tillgång på resurser
- Väderförhållanden
- Systemsituation

## Källor

- [Svenska kraftnät - aFRR](https://www.svk.se/aktorsportalen/bidra-med-reserver/om-olika-reserver/afrr/)
- [Svenska kraftnät - Tekniska villkor aFRR](https://www.svk.se/press-och-nyheter/nyheter/elmarknad-allmant/2023/inforande-av-tekniska-villkor-for-forkvalificering-och-leverans-av-afrr-fcr-och-mfrr/)
- [ENTSO-E - PICASSO](https://www.entsoe.eu/network_codes/eb/picasso/)
- [Svenska kraftnät - Upphandling av aFRR](https://www.svk.se/press-och-nyheter/nyheter/balansansvar/2025/upphandling-av-automatisk-frekvensaterstallningsreserv-afrr-fran-starten-av-mfrr-eam/)
