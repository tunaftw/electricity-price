# Obalanspriser och Obalansavräkning

Obalanspriset är det pris som balansansvariga parter (BRP) betalar eller får för sina obalanser. Det bestäms av kostnaderna för den balansering som Svenska kraftnät behöver utföra.

## Grundläggande koncept

### Vad är en obalans?

```
Obalans = Faktisk produktion/förbrukning - Planerad produktion/förbrukning

Positiv obalans (överskott): BRP levererade mer än planerat
Negativ obalans (underskott): BRP levererade mindre än planerat
```

### Systembalans vs individuell balans

```
┌─────────────────────────────────────────────────────────────────┐
│  SYSTEMBALANS (hela elområdet)                                  │
├─────────────────────────────────────────────────────────────────┤
│  Summan av alla BRP:ers obalanser + överföringsavvikelser       │
│                                                                  │
│  Systemöverskott → Svenska kraftnät nedreglerar                 │
│  Systemunderskott → Svenska kraftnät uppreglerar                │
└─────────────────────────────────────────────────────────────────┘
```

## Single Price Model

Sedan 1 november 2021 använder de nordiska länderna en **single price model** för obalanspriser.

### Hur fungerar det?

Alla BRP:er i ett elområde möter **samma obalanspris** oavsett deras obalansriktning:

```
┌─────────────────────────────────────────────────────────────────┐
│  SINGLE PRICE                                                    │
├─────────────────────────────────────────────────────────────────┤
│  Systemet har underskott (behöver uppreglering)                  │
│  → Obalanspris = Uppregleringspris (högt)                       │
│  → BRP med överskott får HÖGT pris (belönas)                    │
│  → BRP med underskott betalar HÖGT pris (bestraffas)            │
├─────────────────────────────────────────────────────────────────┤
│  Systemet har överskott (behöver nedreglering)                   │
│  → Obalanspris = Nedregleringspris (lågt, kan vara negativt)    │
│  → BRP med underskott betalar LÅGT pris (belönas)               │
│  → BRP med överskott får LÅGT pris (bestraffas)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Varför single price?

**Fördelar:**
- Enklare att förstå och prognosticera
- Incitament att hjälpa systembalansen
- Harmoniserat i Europa

**Nackdelar:**
- Risk för spekulativ trading mot obalanspriset
- Motverkas med obalansavgift (imbalance fee)

## Obalansprisberäkning

### Komponenter

Obalanspriset baseras på kostnaderna för aktiverad balansenergi:

```
Obalanspris = f(aktiverad aFRR, aktiverad mFRR, systemriktning)
```

### Beräkningsmetod (förenklad)

**Vid uppreglering:**
```
Obalanspris = MAX(mFRR uppris, aFRR uppris, spotpris)
```

**Vid nedreglering:**
```
Obalanspris = MIN(mFRR nedpris, aFRR nedpris, spotpris)
```

### 15-minutersupplösning

Sedan 22 maj 2023 beräknas obalanspriser per 15-minutersperiod (ISP - Imbalance Settlement Period) istället för per timme.

## Obalansavräkning via eSett

### eSetts roll

eSett är det gemensamma nordiska bolaget som hanterar obalansavräkning för:
- Sverige
- Finland
- Norge
- Danmark

### Avräkningsprocess

```
Tid →

Driftdygn (D)   D+1          D+7         D+14
     │           │            │            │
     ▼           ▼            ▼            ▼
  Drift    Preliminär    Uppdaterad    Slutlig
          avräkning     avräkning    avräkning
```

### Beräkning av obalansavgift

```
Obalansavgift = |Obalans| × Obalansavgiftssats

Obalansavgiftssats = 1,15 EUR/MWh (harmoniserad i Norden)
```

## Prissättning sedan mFRR EAM (mars 2025)

### Förändrad marknadsdynamik

Efter införandet av mFRR EAM har obalanspriserna blivit mer volatila:

```
┌─────────────────────────────────────────────────────────────────┐
│  OBSERVERADE EFFEKTER                                           │
├─────────────────────────────────────────────────────────────────┤
│  • Större spread mellan spot och obalanspris                    │
│  • Extrempriser: Upp till 5000 EUR/MWh har observerats          │
│  • Ökad frekvens av prispikar                                   │
│  • Olika priser i olika elområden (tidigare mer lika)           │
└─────────────────────────────────────────────────────────────────┘
```

### Extremprisexempel

**6 mars 2025 (DK1):** Obalanspriset nådde ~5000 EUR/MWh under en timme

**7 april 2024:** Obalanspriset var -1005 EUR/MWh (negativt!) i flera nordiska zoner

### Toleransband och prisjusteringar

Svenska kraftnät har infört åtgärder för att hantera extrema priser:
- Manuell granskning av priser i efterhand
- Justeringar vid systemfel
- Planerat toleransband i budvalssystemet

## Obalanspriser och mFRR-priser

### Samband

```
┌─────────────────────────────────────────────────────────────────┐
│  mFRR ENERGIPRIS → PÅVERKAR → OBALANSPRIS                       │
├─────────────────────────────────────────────────────────────────┤
│  Vid uppreglering:                                               │
│  mFRR uppris (marginalpris för aktiverade bud) styr obalans     │
│                                                                  │
│  Vid nedreglering:                                               │
│  mFRR nedpris (marginalpris för aktiverade bud) styr obalans    │
└─────────────────────────────────────────────────────────────────┘
```

### Skillnad mot specialreglering

Specialreglering (för nätavlastning, inte frekvens) påverkar INTE obalanspriset:
- Aktiverade resurser får pay-as-bid
- Exkluderas från obalansprisberäkningen

## Dataåtkomst

### eSett Open Data API

```
API: https://api.opendata.esett.com
Ingen API-nyckel krävs

Tillgänglig data:
- Obalanspriser (köp/sälj) per 15 min
- Regleringspriser (upp/ned)
- Obalansvolymer
```

### I detta projekt

```bash
# Ladda ner obalanspriser
python3 esett_download.py

# Specifik zon och period
python3 esett_download.py --zones SE3 --start 2024-01-01 --end 2024-12-31
```

### Dataformat

```csv
time_start,zone,imbl_sales_price_eur_mwh,imbl_purchase_price_eur_mwh,up_reg_price_eur_mwh,down_reg_price_eur_mwh
2024-12-01T00:00:00Z,SE3,0.5,0.5,18.95,0.5
```

| Kolumn | Beskrivning |
|--------|-------------|
| imbl_sales_price | Pris BRP får vid överskott |
| imbl_purchase_price | Pris BRP betalar vid underskott |
| up_reg_price | Uppregleringspris |
| down_reg_price | Nedregleringspris |

## Strategier för BRP:er

### Minimera obalansrisk

1. **Förbättra prognoser** - Bättre produktion/förbrukningsprognoser
2. **Intraday-handel** - Justera positioner närmare realtid
3. **Portföljstorlek** - Större portföljer ger utjämning
4. **Flexibla resurser** - Möjlighet att justera produktion/förbrukning

### Obalanspriskänslighet

```
Obalansrisk = Exponering (MWh) × Förväntad prisvolatilitet

Högre risk:
- Variabel förnybar produktion (sol, vind)
- Temperaturkänslig förbrukning
- Små portföljer
```

## Framtida förändringar

### 15-minuters day-ahead (30 sep 2025)

Från 30 september 2025 handlas spotmarknaden i 15-minutersintervall, vilket:
- Förbättrar matchningen mot obalansavräkningen
- Ger bättre prissignaler
- Minskar strukturella obalanser

### Ökad transparens

- Fler realtidsdata publiceras
- Bättre prognosverktyg
- Detaljerad efterhandsanalys

## Källor

- [eSett - Nordic Imbalance Settlement](https://www.esett.com/)
- [eSett Handbook](https://www.esett.com/handbook/)
- [Nordic Balancing Model - Single Price](https://nordicbalancingmodel.net/roadmap-and-projects/single-price-model/)
- [Svenska kraftnät - Balansavräkning](https://www.svk.se/aktorsportalen/balansansvarig-part/balansavrakning/)
- [Svenska kraftnät - Utredning mFRR-priser](https://www.svk.se/press-och-nyheter/nyheter/balansansvar/2025/utredning-och-justering-av-priser-avseende-mfrr/)
