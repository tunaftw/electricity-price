# Baseload PPA-analys: Sol + Vind + Batteri

**Datum:** 2024-12-06
**Analysperiod:** 2024 (8784 timmar)
**Installation:** 1 MW sol (south_lundby PVsyst) + 1 MW vind (ENTSO-E SE3)

---

## Sammanfattning

Denna analys undersöker hur man kan leverera **konstant baseload** (24/7/365) genom att kombinera solkraft, vindkraft och batterilager. Huvudfrågan: *Hur stort batteri krävs för att garantera leverans?*

### Huvudslutsatser

1. **100% baseload (0.415 MW) kräver massiv säsonglagring** - 109 MWh batteri med 15+ dagars duration för att täcka "Dunkelflaute" (vindstilla + mörker).

2. **1:1 sol/vind-ratio är optimal** - Sol och vind kompletterar varandra väl (sol=sommar/dag, vind=vinter/natt).

3. **Lägre baseload minskar batteribehov drastiskt:**
   - 100% av snitt → 109 MWh batteri
   - 80% av snitt → 8 MWh batteri
   - 50% av snitt → 1 MWh batteri

4. **10% "pass" (ursäktade timmar) minskar batteribehov med 50-100%** - de sämsta timmarna står för oproportionerligt mycket av kravet.

5. **Sommarnätter är kritiska** - inte vintern! Vindstilla sommarnätter (juli-augusti) är de svåraste perioderna.

---

## Metodik

### Datakällor

| Data | Källa | Format |
|------|-------|--------|
| Solprofil | PVsyst (south_lundby) | MW per timme, normaliserat till 1 MW |
| Vindprofil | ENTSO-E SE3 faktisk produktion | Normaliserad kapacitetsfaktor ~30% |
| Prisdata | elprisetjustnu.se | SEK/kWh per timme |

### Beräkningsmetod

1. **Kombinerad produktion per timme:**
   ```
   produktion[t] = sol_profil[t] × sol_mw + vind_profil[t] × vind_mw
   ```

2. **Underskott/överskott:**
   ```
   diff[t] = produktion[t] - baseload
   underskott[t] = max(0, -diff[t])
   överskott[t] = max(0, diff[t])
   ```

3. **Batteridimensionering (max drawdown-metoden):**
   - Simulera kumulativ energibalans över året
   - Batteristorlek = maximala "dalen" innan återhämtning
   - Hanterar årscykel (dec→jan kan vara sammanhängande period)

### Implementerade moduler

- `elpris/entsoe_profile.py` - Laddar ENTSO-E produktionsdata och skapar normaliserade profiler
- `elpris/baseload_analysis.py` - Kärnlogik för baseload-simulering och batteridimensionering

---

## Resultat

### Kapacitetsfaktorer (2024)

| Källa | Kapacitetsfaktor |
|-------|------------------|
| Sol (south_lundby) | 11.5% |
| Vind (ENTSO-E SE3) | 30.0% |
| Kombinerat (1+1 MW) | 20.8% |

**Medelproduktion:** 0.415 MW (3647 MWh/år)

### Batteribehov vid olika baseload-nivåer

| Baseload | % av snitt | Deficit-timmar | Batteri | Duration |
|----------|------------|----------------|---------|----------|
| 0.415 MW | 100% | 5671 (65%) | 109 MWh | 15.5 dagar |
| 0.374 MW | 90% | 4560 (52%) | 17 MWh | 2.8 dagar |
| 0.332 MW | 80% | 3319 (38%) | 8 MWh | 1.6 dagar |
| 0.249 MW | 60% | 1153 (13%) | 3 MWh | 22 timmar |
| 0.208 MW | 50% | 447 (5%) | 1 MWh | 14 timmar |

### Kritiska perioder (varför batteri behövs)

| Baseload | Kritisk period | Orsak |
|----------|----------------|-------|
| 50% | Juli 23-24 (16h) | Sommarnatt, vindstilla |
| 80% | Nov 6-9 (69h, 2.9d) | Höstmörker + låg vind |
| 90% | Juli 22-25 (64h, 2.7d) | Sommarvindstilla (anticyklon) |
| 100% | Flera veckor | Dunkelflaute vintertid |

### Effekt av "pass" (tillåtna icke-leveranstimmar)

**Med 10% pass (skippa de 878 sämsta timmarna):**

| Baseload | 100% leverans | 90% leverans | Besparing |
|----------|---------------|--------------|-----------|
| 0.208 MW | 1.2 MWh | 0 MWh | −100% |
| 0.332 MW | 8.2 MWh | 3.3 MWh | −60% |
| 0.415 MW | 109 MWh | 57 MWh | −48% |

**Fördelning av pass-timmar (10% pass vid full baseload):**
- Juli: 237 timmar (27%)
- Augusti: 179 timmar (20%)
- Juni: 145 timmar (17%)
- Januari: 1 timme (0.1%)

→ **Sommarnätter dominerar** - inte vinterperioder!

---

## Capture Price-analys (bonus)

Under sessionen skapades även ENTSO-E-baserade sol- och vindprofiler för capture price-beräkning.

### Solar Capture 2022-2024 (SE3)

| År | Capture | Average | Ratio |
|----|---------|---------|-------|
| 2022 | 1.65 SEK | 1.38 SEK | 120% |
| 2023 | 0.48 SEK | 0.59 SEK | 81% |
| 2024 | 0.27 SEK | 0.41 SEK | 66% |

### Wind Capture 2022-2024 (SE3)

| År | Capture | Average | Ratio |
|----|---------|---------|-------|
| 2022 | 1.34 SEK | 1.38 SEK | 97% |
| 2023 | 0.60 SEK | 0.59 SEK | 102% |
| 2024 | 0.43 SEK | 0.41 SEK | 105% |

**Insikt:** Sol har sjunkande capture ratio (kannibalisering), vind ligger stabilt ~100%.

---

## Saknade analyser / Framtida arbete

### 1. Ekonomisk optimering
- Kostnad för batteri (€/kWh) vs. värdet av leveranssäkerhet
- Break-even: När lönar sig batteri vs. spot-inköp vid underskott?
- Intäkt från överskottsförsäljning på spot

### 2. Multi-års robusthet
- Analysera 2022-2024 för att se variation mellan år
- Worst-case år vs. genomsnitt
- Klimatförändringens påverkan på vindmönster

### 3. Geografisk diversifiering
- Kombinera vind från SE1/SE2 med sol från SE3/SE4
- Korrelation mellan zoner - minskar det batteribehov?

### 4. Intradag-optimering
- Använd batteriet för arbitrage under överskottstimmar
- Stackade intäkter: baseload + FCR + arbitrage

### 5. Prognosfel och obalans
- Vad händer om prognosen är fel?
- Kostnad för obalans (eSett-data) vs. batteribuffert

### 6. Alternativa PPA-strukturer
- Pay-as-produced vs. baseload
- Shaped PPA (dag/natt-profil)
- Floor/cap-strukturer

---

## Appendix A: Analysflöde (transcript-sammanfattning)

### Steg 1: ENTSO-E profiler skapades
```
Användare: Skapa solprofil baserat på ENTSO-E faktisk produktion per zon,
           plus vindprofil från vinddata.

Claude: Skapade elpris/entsoe_profile.py med:
        - load_entsoe_generation()
        - create_typical_profile()
        - get_entsoe_weight()

        Sparade profiler i data/profiles/:
        - solar_SE1.csv ... solar_SE4.csv
        - wind_onshore_SE1.csv ... wind_onshore_SE4.csv
```

### Steg 2: Capture price-analys kördes
```
Användare: Visa capture price 2022-2024 för varje zon.

Claude: Körde analys för sol och vind capture per år/zon.
        Insikt: Sol-capture sjunker (66% 2024), vind stabil (~100%).
```

### Steg 3: Baseload-analys initierades
```
Användare: Hur stort batteri för 100% baseload med 1 MW sol + X MW vind?

Claude: Skapade elpris/baseload_analysis.py
        Parametrar: SE3, south_lundby, 2024

        Resultat: 1:1 ratio optimal, men 109 MWh batteri för 100% baseload.
```

### Steg 4: Olika baseload-nivåer testades
```
Användare: Vad händer med lägre baseload?

Claude: Analyserade 50%, 60%, 70%, 80%, 90%, 100% av medelproduktion.

        Nyckelinsikt: 80% baseload = 8 MWh batteri (vs 109 MWh för 100%)
```

### Steg 5: Pass-timmar analyserades
```
Användare: Om vi tillåter 10% eller 20% "pass" (ej leverera vissa timmar)?

Claude: Analyserade batteribehov med olika pass-procent.

        Nyckelinsikt:
        - 10% pass minskar batteri med 48-100%
        - De sämsta timmarna är sommarnätter (juli-aug), inte vinter!
```

### Steg 6: Detaljerad förklaring
```
Användare: Förklara beräkningen i detalj för 50% baseload.

Claude: Visade timme-för-timme simulering:
        - Longest deficit run: 16 timmar (juli 23-24)
        - Batteri måste täcka ~1 MWh under denna period
        - Med 10% pass: inget batteri behövs alls!
```

---

## Appendix B: Kod-exempel

### Köra baseload-analys
```python
from elpris.baseload_analysis import run_baseload_analysis, analyze_wind_ratios

# Analysera olika vindkapaciteter
results = analyze_wind_ratios(
    sol_mw=1.0,
    zone="SE3",
    sol_profile_name="south_lundby",
    year=2024,
    wind_ratios=[0.5, 1.0, 1.5, 2.0]
)

# Specifik analys
r = run_baseload_analysis(
    sol_mw=1.0,
    vind_mw=1.0,
    zone="SE3",
    sol_profile_name="south_lundby",
    year=2024,
    baseload_mw=0.332  # 80% av snitt
)

print(f"Batteribehov: {r.battery_mwh_required:.1f} MWh")
```

### Köra capture price med ENTSO-E profiler
```bash
# Sol capture SE3
python3 capture.py SE3 --profile entsoe_solar_SE3 --period year

# Vind capture SE3
python3 capture.py SE3 --profile entsoe_wind_onshore_SE3 --period year
```

---

## Appendix C: Dataflöde

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATAKÄLLOR                                   │
├─────────────────────────────────────────────────────────────────────┤
│  PVsyst CSV          ENTSO-E API           elprisetjustnu.se        │
│  (south_lundby)      (generation)          (spotpriser)             │
└────────┬─────────────────┬─────────────────────┬────────────────────┘
         │                 │                     │
         ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PROFILER (normaliserade)                        │
├─────────────────────────────────────────────────────────────────────┤
│  data/solar_profiles/     data/profiles/                            │
│  south_lundby.csv         solar_SE3.csv                             │
│                           wind_onshore_SE3.csv                       │
└────────┬─────────────────────┬──────────────────────────────────────┘
         │                     │
         ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ANALYS-MODULER                                    │
├─────────────────────────────────────────────────────────────────────┤
│  elpris/baseload_analysis.py    elpris/capture.py                   │
│  - run_baseload_analysis()      - calculate_capture_price()         │
│  - analyze_wind_ratios()        - calculate_capture_by_period()     │
└────────┬─────────────────────────────┬──────────────────────────────┘
         │                             │
         ▼                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         RESULTAT                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Batteridimensionering           Capture prices                      │
│  - MWh kapacitet                 - SEK/kWh per period               │
│  - MW effekt                     - Capture ratio                     │
│  - Kritiska perioder             - Zonspread                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

*Genererad av Claude Code, 2024-12-06*
