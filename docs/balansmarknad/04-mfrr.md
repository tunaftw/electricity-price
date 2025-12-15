# mFRR - Manuell Frekvensåterställningsreserv

mFRR (manual Frequency Restoration Reserve) är den tertiära reserven i balanseringshierarkin. Den används för att hantera större obalanser och avlasta aFRR så att den återigen blir tillgänglig för nya störningar.

## Grundläggande funktion

mFRR är den "arbetshäst" som hanterar längre obalanser:

```
Störning → FCR stoppar → aFRR återställer → mFRR tar över långsiktigt
                                                    │
                                                    ▼
                                            aFRR frigörs för
                                            nästa störning
```

## Tekniska krav

```
Aktiveringstid:    100% inom 15 minuter från signal
Uthållighet:       15 minuter (schemalagd aktivering)
                   30 minuter (direktaktivering)
Minsta budstorlek: 1 MW
Budområde:         Per elområde (SE1, SE2, SE3, SE4)
```

## Två marknader - Kapacitet och Energi

mFRR handlas på **två separata marknader**:

### 1. Kapacitetsmarknaden (D-1)

Syftet är att säkerställa att tillräckliga resurser finns tillgängliga.

```
┌─────────────────────────────────────────────────────────┐
│  KAPACITETSMARKNADEN                                    │
├─────────────────────────────────────────────────────────┤
│  Vad säljs:    Tillgänglighet (beredskap)               │
│  När:          D-7 → D-1 kl 07:30                       │
│  Ersättning:   EUR/MW (kapacitetsbetalning)             │
│  Skyldighet:   Lämna energibud på energimarknaden       │
│  Prissättning: Marginalpris per elområde                │
└─────────────────────────────────────────────────────────┘
```

**Skyldighetsleverans**: Den som säljer kapacitet *måste* sedan lägga motsvarande energibud på energimarknaden.

### 2. Energiaktiveringsmarknaden (mFRR EAM)

Syftet är att aktivera den billigaste energin vid behov.

```
┌─────────────────────────────────────────────────────────┐
│  ENERGIAKTIVERINGSMARKNADEN (mFRR EAM)                  │
├─────────────────────────────────────────────────────────┤
│  Vad säljs:    Faktisk energi vid aktivering            │
│  När:          D-1 kl 13:00 → 45 min före driftkvart    │
│  Ersättning:   EUR/MWh (energibetalning)                │
│  Aktivering:   Automatiserad (sedan mars 2025)          │
│  Prissättning: Marginalpris per elområde                │
└─────────────────────────────────────────────────────────┘
```

## Budprocessen steg för steg

### Steg 1: Kapacitetsbud (D-7 till D-1)

```
Aktör lämnar kapacitetsbud:
┌────────────────────────────────────┐
│ Elområde:     SE3                  │
│ Timmar:       08:00-18:00          │
│ Volym:        50 MW upp            │
│ Pris:         15 EUR/MW,h          │
└────────────────────────────────────┘
```

### Steg 2: Kapacitetsauktion (D-1 morgon)

```
Svenska kraftnät genomför auktion:

  Bud sorteras efter pris (merit order)
           │
           ▼
  Volymbehov täcks
           │
           ▼
  Marginalpris sätts av dyraste antagna bud
           │
           ▼
  Alla antagna bud får marginalpriset
```

### Steg 3: Energibud (D-1 eftermiddag)

Aktörer som sålde kapacitet måste lägga energibud:

```
Aktör lämnar energibud:
┌────────────────────────────────────┐
│ Reglerande enhet: Kraftverk X     │
│ Driftkvart:       08:00-08:15      │
│ Volym:            50 MW upp        │
│ Pris:             45 EUR/MWh       │
└────────────────────────────────────┘
```

### Steg 4: Energiaktivering (driftdygnet)

Före mars 2025: Manuell aktivering av operatör
Efter mars 2025: Automatiserad via AOF-algoritm

```
AOF-algoritm väljer:
1. Samlar in alla energibud
2. Beräknar reglerlingsbehov per område
3. Tar hänsyn till överföringskapacitet
4. Aktiverar billigaste bud som täcker behovet
5. Sätter marginalpris per område
```

## mFRR EAM - Nordisk automatisering (från mars 2025)

Den 4 mars 2025 infördes den automatiserade nordiska mFRR-energiaktiveringsmarknaden.

### Före mFRR EAM
- Operatörer ringde manuellt upp kraftverk
- 60-minutersupplösning
- Nationell optimering

### Efter mFRR EAM
- Algoritm (AOF) väljer automatiskt
- 15-minutersupplösning
- Nordisk optimering över gränser
- Snabbare aktivering

### Effekter av mFRR EAM

**Positiva effekter:**
- Effektivare resursanvändning
- Lägre balanseringskostnader (i genomsnitt)
- Snabbare respons på obalanser

**Utmaningar:**
- Högre prisvolatilitet
- Större spread mellan spot och obalanspris
- Extrempriser har observerats (t.ex. 5000 EUR/MWh)

## Prissättning

### Kapacitetsmarknad - Marginalpris

```
Pris
 ▲
 │         ┌─────────────────  Marginalpris
 │    ┌────┘                   (alla får detta pris)
 │ ┌──┘
 │─┘
 └────────────────────────────► Volym
   ████████████████
   Antagna bud
```

### Energimarknad - Marginalpris per område

```
SE3 Marginalpris = Dyraste aktiverade budet i SE3

Om överföringskapacitet begränsar:
- Olika priser i olika elområden
- Resurs i SE2 kan få SE2-pris även om den avhjälper SE3-obalans
```

### Specialreglering - Pay-as-bid

Specialreglering sker av andra skäl än frekvens (t.ex. nätbegränsningar):
- Påverkar inte obalanspriset
- Aktiverade resurser får sitt budpris (pay-as-bid)

## Pristak och budgränser

Energibud på mFRR-marknaden har harmoniserade pristak enligt EU-regler:

```
┌─────────────────────────────────────────────────────────────────┐
│  PRISTAK FÖR mFRR ENERGIBUD                                     │
├─────────────────────────────────────────────────────────────────┤
│  Högsta tillåtna pris:    +10 000 EUR/MWh                       │
│  Lägsta tillåtna pris:    -10 000 EUR/MWh                       │
│  (Harmoniserat i EU via Electricity Balancing Guideline)        │
└─────────────────────────────────────────────────────────────────┘
```

## Budstrategier och incitament

### Strategi: Lågt kapacitetsbud + högt energibud

En aktör kan teoretiskt:
1. Lägga lågt kapacitetsbud för att bli antagen
2. Lägga högt energibud för att undvika aktivering
3. Få kapacitetsersättning utan att behöva leverera energi

**Begränsningar:**

| Faktor | Effekt |
|--------|--------|
| Marginalpris | Du får marknadens pris, inte ditt budpris |
| Konkurrens | Billigare bud aktiveras först |
| Extremsituationer | Vid kapacitetsbrist kan även dyra bud aktiveras |
| Skyldighetskontroll | Svenska kraftnät kontrollerar att energibud matchar såld kapacitet |

**Utfall beroende på marknadssituation:**

```
Ditt energibud: 5000 EUR/MWh

Scenario A: Marginalpris 120 EUR/MWh
→ Du aktiveras INTE (för dyr)
→ Resultat: Bara kapacitetsersättning

Scenario B: Marginalpris 5500 EUR/MWh (extremsituation)
→ Du AKTIVERAS (ditt bud behövs)
→ Resultat: Du får 5500 EUR/MWh, men MÅSTE leverera

Scenario C: Marginalpris 4800 EUR/MWh
→ Du aktiveras INTE (ditt bud för dyrt)
→ Resultat: Bara kapacitetsersättning
```

**Slutsats:** Strategin innebär en trade-off mellan "säker" kapacitetsersättning och missade energiintäkter vid höga marknadspriser.

## Ersättningsberäkning

### Kapacitetsersättning

```
Kapacitetsersättning = Marginalpris (EUR/MW) × Kontrakterad volym (MW)

Exempel:
50 MW × 15 EUR/MW = 750 EUR för en timme
```

### Energiersättning

```
Energiersättning = Aktiverad energi (MWh) × mFRR-pris (EUR/MWh)

Exempel vid aktivering 15 minuter:
50 MW × 0,25 h × 120 EUR/MWh = 1500 EUR
```

## Trilateral kapacitetsmarknad (nov 2024)

Sedan 19 november 2024 finns en gemensam kapacitetsmarknad för Sverige, Finland och Danmark.

```
┌─────────────────────────────────────────────────────────┐
│  TRILATERAL mFRR KAPACITETSMARKNAD                      │
├─────────────────────────────────────────────────────────┤
│  Länder:    Sverige, Finland, Danmark                   │
│  Start:     19 november 2024                            │
│  Syfte:     Dela kapacitet över gränser                │
│  Effekt:    Lägre kapacitetskostnader                   │
│             Bättre utnyttjande av resurser              │
└─────────────────────────────────────────────────────────┘
```

## Volymkrav och upphandling

### 2024 Q2-Q4
- **mFRR upp**: 400 MW per timme
- **mFRR ned**: 600 MW per timme

Upphandling sker per elområde för att säkerställa lokal tillgång.

## Framtida utveckling - MARI

Sverige förväntas ansluta till den europeiska mFRR-plattformen MARI (Manually Activated Reserves Initiative) under 2027-2028.

### Vad innebär MARI?
- Gemensam europeisk energiaktiveringsmarknad
- Ännu större optimeringsområde
- Harmoniserade produkter och regler

## Dataåtkomst

mFRR-data tillgänglig via:
- **Mimer** (mimer.svk.se) - Kapacitets- och energipriser
- **eSett** (opendata.esett.com) - Obalanspriser
- I detta projekt: `mimer_download.py --product mfrr`

## Källor

- [Svenska kraftnät - mFRR](https://www.svk.se/aktorsportalen/bidra-med-reserver/om-olika-reserver/mfrr/)
- [Svenska kraftnät - mFRR EAM](https://www.svk.se/utveckling-av-kraftsystemet/systemansvar--elmarknad/ny-nordisk-balanseringsmodell-nbm/automatiserad-nordisk-energiaktiveringsmarknad-for-mfrr/)
- [Svenska kraftnät - Trilateral kapacitetsmarknad](https://www.svk.se/utveckling-av-kraftsystemet/systemansvar--elmarknad/ny-nordisk-balanseringsmodell-nbm/nordisk-kapacitetsmarknad-for-mfrr/)
- [Nordic Balancing Model](https://nordicbalancingmodel.net/)
- [stodtjanster.se - mFRR-marknaden](https://stodtjanster.se/mfrr-hos-svk/)
