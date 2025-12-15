# Batteridimensionering för AC-toppkapning

Hur stort batteri behövs för att kapa effekttoppar i en solcellspark vid reducerad AC-kapacitet?

## Sammanfattning

| Scenario | AC-kapacitet | Batteri | Klippt energi | Räddad energi |
|----------|--------------|---------|---------------|---------------|
| 100% → 50% | 0.75 → 0.375 MW | **0.38 MW / 2.5 MWh** | 251 MWh/år | 224 MWh (89%) |

**Tumregel för 1 MWp PV (Lundby-profil):**
- Effekt ≈ Max produktion minus ny AC-gräns
- Energi ≈ Max daglig klippning (7-8 timmars duration)
- C-rate: ~0.15C (låg - passar alla batterityper)

---

## Bakgrund

### Varför reducera AC-kapacitet?

1. **Lägre nätanslutningskostnad** - billigare växelriktare och nätavgifter
2. **Begränsad nätkapacitet** - nätet kan inte ta emot full effekt
3. **Effektbegränsning i avtal** - max inmatning begränsad av nätägare
4. **Överdimensionerad DC** - medvetet val för högre kapacitetsfaktor

### DC/AC-ratio

```
DC/AC-ratio = DC-kapacitet (MWp) / AC-kapacitet (MW)

Exempel:
  1 MWp DC / 1.0 MW AC = 1.0  (standard)
  1 MWp DC / 0.75 MW AC = 1.33 (vanlig överdimensionering)
  1 MWp DC / 0.50 MW AC = 2.0  (hög överdimensionering)
  1 MWp DC / 0.375 MW AC = 2.67 (extremt - kräver batteri)
```

---

## Case: 1 MWp Lundby → 50% AC-kapacitet

### Förutsättningar

| Parameter | Värde |
|-----------|-------|
| Plats | Lundby, södra Sverige |
| DC-kapacitet | 1.0 MWp |
| Solprofil | `south_lundby` (PVsyst-simulerad) |
| Nuvarande AC | 0.75 MW (DC/AC = 1.33) |
| Ny AC | 0.375 MW (DC/AC = 2.67) |
| Mål | Aldrig överskrida 0.375 MW till nätet |

### Profildata

| Parameter | Värde |
|-----------|-------|
| Max produktion | 0.754 MW (75.4% av DC) |
| Årsproduktion | 1012 MWh |
| Full load hours | 1012 h |
| Specifik yield | 1012 kWh/kWp |

---

## Klippningsanalys

### Utan batteri

Vid 0.375 MW AC-gräns utan batteri:

| Mått | Värde |
|------|-------|
| Total produktion | 1012 MWh/år |
| Export till nät | 761 MWh/år |
| **Klippt energi** | **251 MWh/år (24.8%)** |
| Timmar med klippning | 1109 h/år |

### Klippningens karaktär

| Parameter | Värde |
|-----------|-------|
| Max klipphastighet | 0.379 MW |
| Max daglig klippning | 2.85 MWh |
| Genomsnittlig klippning (dagar med klipp) | 1.0 MWh |

### Månadsfördelning

```
Jan:    0.0 MWh
Feb:    0.8 MWh
Mar:   16.4 MWh  ██
Apr:   43.4 MWh  █████
Maj:   47.2 MWh  █████
Jun:   47.6 MWh  █████
Jul:   41.8 MWh  █████
Aug:   34.9 MWh  ████
Sep:   15.2 MWh  █
Okt:    4.1 MWh
Nov:    0.0 MWh
Dec:    0.0 MWh
```

Klippning sker nästan uteslutande mars-september, med topp i april-juli.

---

## Batteridimensionering

### Hur batteriet fungerar för toppkapning

```
Scenario: AC-gräns 0.375 MW, aktuell produktion 0.6 MW

1. Sol producerar 0.6 MW
2. 0.375 MW exporteras direkt till nät
3. Överskott 0.225 MW laddas in i batteriet
4. På kvällen urladdas batteriet till nätet

Resultat: All energi tas tillvara, AC-gränsen överskrids aldrig
```

### Storleksalternativ

| Batteri | Export | Förlorat | Räddat | Cykler/år | Utnyttjande |
|---------|--------|----------|--------|-----------|-------------|
| 0.20 MW / 1.0 MWh | 885 MWh | 113 MWh | 125 MWh | ~130 | 50% |
| 0.30 MW / 1.5 MWh | 930 MWh | 63 MWh | 170 MWh | ~120 | 68% |
| **0.38 MW / 2.0 MWh** | **964 MWh** | **26 MWh** | **203 MWh** | **~105** | **81%** |
| **0.38 MW / 2.5 MWh** | **984 MWh** | **4 MWh** | **224 MWh** | **~95** | **89%** |
| 0.38 MW / 3.0 MWh | 987 MWh | 1 MWh | 226 MWh | ~80 | 90% |

*Max utnyttjande 90% pga batteriförluster (RT-effektivitet 90%)*

### Rekommenderad storlek

```
┌─────────────────────────────────────────────────────────┐
│  BATTERI: 0.38 MW / 2.5 MWh                             │
│                                                         │
│  Effekt:     380 kW                                     │
│  Energi:     2500 kWh                                   │
│  Duration:   6.6 timmar                                 │
│  C-rate:     0.15C (laddning/urladdning)                │
│  Cykler:     ~95/år                                     │
│                                                         │
│  Resultat:   89% av klippt energi räddas                │
│              Endast 4 MWh/år går förlorat (spillover)   │
└─────────────────────────────────────────────────────────┘
```

---

## Förlustanalys

### Energiflöde med 0.38 MW / 2.5 MWh batteri

```
Solproduktion:     1012 MWh/år
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
   Direkt export              Överskott (klipps)
     761 MWh                     251 MWh
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              Till batteri     Spillover      (aldrig)
                247 MWh          4 MWh
                    │
                    ▼
           Batteriförlust (10%)
                 25 MWh
                    │
                    ▼
           Urladdning till nät
                222 MWh

TOTAL EXPORT: 761 + 222 = 983 MWh/år (97% av produktion)
FÖRLUSTER: 4 (spillover) + 25 (batteri) = 29 MWh/år (3%)
```

### Jämförelse

| Scenario | Export | Förlust | Kommentar |
|----------|--------|---------|-----------|
| 0.75 MW AC (ingen gräns) | 1011 MWh | 1 MWh | Referens |
| 0.375 MW AC utan batteri | 761 MWh | 251 MWh | 25% förlust |
| 0.375 MW AC + 2.5 MWh batteri | 984 MWh | 28 MWh | 3% förlust |

**Batteriet räddar ~224 MWh/år** som annars skulle klippas bort.

---

## Ekonomisk analys

### Kostnadsantaganden

| Parameter | Värde | Kommentar |
|-----------|-------|-----------|
| Batterikostnad (energi) | 500 EUR/kWh | Utility-scale Li-ion |
| Batterikostnad (effekt) | 150 EUR/kW | Inverter/BMS |
| Livslängd | 15 år | Kalendarisk |
| Cykler | 5000+ | Lågt slitage vid 95 cykler/år |
| Elpris (medel) | 50 EUR/MWh | SE4 snitt |
| Diskonteringsränta | 5% | |

### Investeringskalkyl

| Post | Beräkning | Värde |
|------|-----------|-------|
| Batterienergi | 2500 kWh × 500 EUR | 1 250 000 EUR |
| Batterieffekt | 380 kW × 150 EUR | 57 000 EUR |
| **Total CAPEX** | | **1 307 000 EUR** |
| Årlig kostnad (annuitet) | CAPEX × 0.096 | 125 500 EUR/år |

### Intäkter

| Post | Beräkning | Värde |
|------|-----------|-------|
| Räddad energi | 224 MWh/år | |
| Energivärde | 224 MWh × 50 EUR | 11 200 EUR/år |
| **Besparing AC-anslutning** | (0.75 - 0.375) MW × X EUR | **Beror på nätavgift** |

### Lönsamhet enbart från energiräddning

| Post | Värde |
|------|-------|
| Årlig intäkt (energi) | 11 200 EUR |
| Årlig kostnad (batteri) | 125 500 EUR |
| **Netto** | **-114 300 EUR/år** |

**Slutsats:** Batteriet är INTE lönsamt enbart för att rädda klippt energi.

### Break-even för nätanslutningsbesparing

För lönsamhet krävs att kostnaden för 0.375 MW extra AC-kapacitet överstiger:

```
Break-even: 125 500 - 11 200 = 114 300 EUR/år

Om nätanslutning har 15 års avskrivning:
  Besparing krävs: 114 300 × 10.38 (annuitetsfaktor) = 1 186 000 EUR

Alternativt uttryckt:
  Nätanslutningskostnad > 3 160 EUR/kW för att motivera batteriet
```

---

## Kombinerade intäktsströmmar

Batteriet blir lönsamt om det kombineras med andra tjänster:

### 1. FCR-D (Frequency Containment Reserve - Disturbance)

| Parameter | Värde |
|-----------|-------|
| Tillgänglig kapacitet | ~300 kW (efter SOC-marginal) |
| FCR-D pris | 10-30 EUR/MW/h |
| Timmar/dag tillgänglig | ~16 h (natt + morgon/kväll) |
| Potential | 15 000 - 50 000 EUR/år |

### 2. Arbitrage (day-ahead)

| Parameter | Värde |
|-----------|-------|
| Daglig cykel | 1 (utöver solkapning) |
| Spread SE4 | ~20 EUR/MWh (snitt) |
| Potential | 2.5 MWh × 20 EUR × 300 dagar = 15 000 EUR/år |

### 3. Intraday/balansmarknad

| Parameter | Värde |
|-----------|-------|
| mFRR EAM aktivering | Sporadisk |
| Potential | 5 000 - 15 000 EUR/år |

### Total intäktspotential

| Intäktsström | Konservativ | Optimistisk |
|--------------|-------------|-------------|
| Räddad energi | 11 200 EUR | 11 200 EUR |
| FCR-D | 15 000 EUR | 50 000 EUR |
| Arbitrage | 10 000 EUR | 20 000 EUR |
| Intraday/mFRR | 5 000 EUR | 15 000 EUR |
| **Total** | **41 200 EUR** | **96 200 EUR** |

Med dessa intäkter kan business case se annorlunda ut, men kräver aktiv marknadshantering.

---

## Praktiska aspekter

### Val av batteriteknologi

| Krav | Implikation |
|------|-------------|
| Låg C-rate (0.15C) | Alla batterityper fungerar |
| Få cykler (~95/år) | Lång livslängd möjlig |
| Lång duration (6-7h) | LFP eller Na-ion lämpligt |
| Utomhusplacering | Container-lösning |

**Rekommendation:** LFP (Lithium Iron Phosphate) - bäst balans kostnad/livslängd vid låg cykling.

### Driftstrategi

```
Dagtid (solproduktion):
  IF produktion > 0.375 MW:
    Ladda batteri med (produktion - 0.375)
  ELSE:
    Exportera all produktion

Natt/kväll:
  Ladda ur batteri till nät
  ELLER deltag på FCR-D marknaden
```

### SOC-hantering

| Period | SOC-mål | Kommentar |
|--------|---------|-----------|
| Morgon (före sol) | 0-20% | Utrymme för laddning |
| Dag (solproduktion) | 0→100% | Tar emot klippt energi |
| Kväll | 100→0% | Urladdning till nät |

---

## Känslighetsanalys

### AC-gräns påverkan

| AC-gräns | Klippt | Batteri | Duration |
|----------|--------|---------|----------|
| 50% (0.375 MW) | 251 MWh | 0.38 MW / 2.5 MWh | 6.6 h |
| 60% (0.45 MW) | 178 MWh | 0.30 MW / 2.0 MWh | 6.7 h |
| 70% (0.525 MW) | 114 MWh | 0.23 MW / 1.5 MWh | 6.5 h |
| 80% (0.6 MW) | 62 MWh | 0.15 MW / 1.0 MWh | 6.7 h |

Durationen är relativt konstant (~6-7 timmar) oavsett AC-gräns.

### Profil påverkan

| Profil | Max | Årsproduktion | Klippning vid 50% AC |
|--------|-----|---------------|---------------------|
| south_lundby | 0.754 MW | 1012 MWh | 251 MWh (25%) |
| tracker_sweden | ~0.85 MW | ~1150 MWh | ~350 MWh (30%) |
| ew_boda | ~0.65 MW | ~900 MWh | ~150 MWh (17%) |

Tracker-system klipper mer pga högre peak, öst-väst mindre pga flackare profil.

---

## Begränsningar i analysen

### Vad modellen inkluderar

- Timupplöst solprofil (8760 timmar)
- Daglig battericykling (ladda dag, ladda ur natt)
- Batteriförluster (90% RT-effektivitet)
- Spillover vid fullt batteri

### Vad modellen EJ inkluderar

1. **Intraday-variation** - verklig produktion varierar inom timmen
2. **Molnpassager** - snabba förändringar kan ge kortvariga toppar
3. **Batteridegradation** - kapacitetsförlust över tid
4. **Temperatureffekter** - påverkar både PV och batteri
5. **Nätbegränsningar** - kan begränsa urladdning kvällstid

### Konsekvens av förenklingar

Verklig batteristorlek kan behöva vara **10-20% större** för att hantera:
- Intraday-toppar
- Säkerhetsmarginaler
- Kapacitetsförlust år 1-15

---

## Slutsatser

### Dimensionering

1. **Effekt:** 0.38 MW - bestäms av max klipphastighet (0.754 - 0.375 = 0.379 MW)
2. **Energi:** 2.5 MWh - bestäms av max daglig klippning plus marginal
3. **Duration:** 6-7 timmar - ovanligt långt för solpark + batteri

### Ekonomi

4. **Energivärde ensamt:** Otillräckligt för lönsamhet
5. **Nätbesparing:** Kan motivera om >3 000 EUR/kW
6. **Stacking:** FCR-D + arbitrage krävs för positiv ROI

### Rekommendation

> För 1 MWp Lundby med 50% AC-begränsning:
>
> **Batteri: 0.38 MW / 2.5 MWh** (alternativt 2.0-3.0 MWh beroende på risktolerans)
>
> Kombinera med FCR-D deltagande natt/kväll för att förbättra ekonomin.

---

## Appendix: Simuleringsdata

### Indata

| Parameter | Värde |
|-----------|-------|
| Profil | `data/solar_profiles/south_lundby.csv` |
| Format | month, day, hour, power_mw |
| Rader | 8760 (1 år timdata) |
| Normalisering | Per MWp installerat |

### Batterimodell

```python
# Förenklad modell
for hour in year:
    if solar > ac_limit:
        excess = solar - ac_limit
        charge = min(excess, battery_mw, (battery_mwh - soc) / eff_charge)
        soc += charge * eff_charge
        lost += excess - charge

    # Daglig urladdning
    if new_day:
        export += soc * eff_discharge
        soc = 0
```

### Resultat (fullständig tabell)

| MW | MWh | Export | Förlust | Räddat | Cykler | Utnytt. |
|----|-----|--------|---------|--------|--------|---------|
| 0.10 | 0.5 | 829 | 176 | 69 | 144 | 27% |
| 0.20 | 1.0 | 885 | 113 | 125 | 131 | 50% |
| 0.30 | 1.5 | 930 | 63 | 170 | 118 | 68% |
| 0.38 | 2.0 | 964 | 26 | 203 | 106 | 81% |
| 0.38 | 2.5 | 984 | 4 | 224 | 93 | 89% |
| 0.38 | 3.0 | 987 | 1 | 226 | 78 | 90% |
| 0.40 | 4.0 | 988 | 0 | 227 | 58 | 91% |
