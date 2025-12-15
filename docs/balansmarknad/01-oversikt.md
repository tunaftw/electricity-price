# Översikt - Svenska Balansmarknaden

## Vad är balansmarknaden?

Balansmarknaden är en marknad där Svenska kraftnät (systemansvarig TSO) köper och säljer el för att i realtid upprätthålla balansen mellan produktion och förbrukning i det svenska elnätet. Frekvensen i elnätet ska hela tiden ligga nära 50 Hz - avvikelser indikerar obalans.

```
Överproduktion → Frekvens > 50 Hz → Behov av nedreglering
Underskott     → Frekvens < 50 Hz → Behov av uppreglering
```

## Varför behövs balansering?

1. **Fysisk begränsning**: El kan inte lagras i stor skala - produktion måste matcha förbrukning varje sekund
2. **Prognosfel**: Förbrukning och produktion (särskilt sol/vind) avviker alltid från prognoser
3. **Störningar**: Kraftverk och kablar kan trilla ur drift oväntat
4. **Frekvenskvalitet**: Avvikelser från 50 Hz kan skada utrustning och i värsta fall leda till nedsläckning

## Reserver och deras roller

Svenska kraftnät använder olika typer av reserver som aktiveras i sekvens beroende på behov:

```
Tid efter störning →

[0-30 sek]     [30 sek - 15 min]     [15 min - 60 min]     [> 60 min]
    │                  │                     │                  │
    ▼                  ▼                     ▼                  ▼
   FCR              aFRR                  mFRR              Ersättning

Frekvens-       Frekvens-            Frekvens-            Återställ
hållning        återställning        återställning        reserver
(automatisk)    (automatisk)         (manuell/auto)
```

### Reservernas funktion

| Reserv | Funktion | Aktivering |
|--------|----------|------------|
| **FCR** (Frequency Containment Reserve) | Stoppar frekvensavvikelsen | Automatiskt vid frekvensavvikelse |
| **aFRR** (automatic Frequency Restoration Reserve) | Återställer frekvensen till 50 Hz | Automatiskt via signal från TSO |
| **mFRR** (manual Frequency Restoration Reserve) | Återställer frekvensen, avlastar aFRR | Tidigare manuellt, nu automatiserat (EAM) |

## Marknadsstruktur

### Kapacitetsmarknad vs Energimarknad

**Kapacitetsmarknad (D-1)**
- Handlas dagen före drift
- Aktörer säljer *tillgänglighet* (beredskap att leverera)
- Ersättning: SEK/MW eller EUR/MW
- Syfte: Säkerställa att resurser finns tillgängliga

**Energimarknad (intraday)**
- Aktivering sker vid behov under driftdygnet
- Aktörer levererar faktisk energi
- Ersättning: SEK/MWh eller EUR/MWh
- Syfte: Faktisk balansering

### Tidslinje för en typisk dag

```
D-7 till D-1 07:30    │  Kapacitetsbud för mFRR
                      │
D-1 morgon            │  Kapacitetsauktion FCR, aFRR, mFRR
                      │
D-1 13:00             │  Energibud för mFRR öppnar
                      │
D-1 → 45 min före     │  Energibud kan uppdateras
                      │
Driftkvarten          │  Aktivering vid behov
                      │
D+1                   │  Balansavräkning (preliminär)
                      │
D+14                  │  Balansavräkning (slutlig)
```

## Svenska elområden (budområden)

Sverige är uppdelat i fyra elområden sedan 2011:

```
┌─────────────────────┐
│        SE1          │  Norra Norrland (Luleå)
│      Luleå          │  - Stor vattenkraft
├─────────────────────┤
│        SE2          │  Södra Norrland (Sundsvall)
│     Sundsvall       │  - Stor vattenkraft
├─────────────────────┤
│        SE3          │  Mellansverige (Stockholm)
│     Stockholm       │  - Kärnkraft, förbrukning
├─────────────────────┤
│        SE4          │  Södra Sverige (Malmö)
│      Malmö          │  - Vindkraft, import
└─────────────────────┘
```

Varje elområde kan ha olika:
- Spotpriser
- mFRR-priser
- Obalanspriser
- Kapacitetsupphandling

## Nordiskt samarbete

De nordiska länderna (Sverige, Norge, Finland, Danmark) samarbetar kring balansering:

- **Gemensamt synkronområde**: Samma frekvens i hela Norden
- **FCR**: Gemensam nordisk upphandling
- **mFRR kapacitet**: Trilateral marknad (SE/FI/DK) från nov 2024
- **mFRR energi**: Nordisk EAM från mars 2025
- **eSett**: Gemensam obalansavräkning

## Framtida utveckling

### Pågående förändringar
- **15-minutersmarknad**: Kortare handelsperioder för bättre prissignaler
- **Automatisering**: mFRR EAM ersätter manuell aktivering
- **Europeisk integration**: Anslutning till MARI, PICASSO

### Förväntade effekter
- Mer volatila priser
- Större spread mellan spotpris och obalanspris
- Ökade krav på flexibilitet
- Nya möjligheter för batterier och flexibel förbrukning

## Källor

- [Svenska kraftnät - Om reserver](https://www.svk.se/aktorsportalen/bidra-med-reserver/)
- [Svenska kraftnät - Behov av reserver](https://www.svk.se/aktorsportalen/bidra-med-reserver/behov-av-reserver-nu-och-i-framtiden/)
- [Nordic Balancing Model](https://nordicbalancingmodel.net/)
