# Ekonomisk Riskanalys: 200 kW Baseload PPA

**Datum:** 2024-12-09
**Scenario:** 200 kW baseload med 1h batteri (200 kWh)
**Zon:** SE3 | **År:** 2024 | **Batterieffektivitet:** 90%

---

## Sammanfattning

| Parameter | Värde |
|-----------|-------|
| **Baseload** | 200 kW (38% av medelproduktion) |
| **Batteri** | 200 kWh / 1h duration |
| **Missade leveranstimmar** | 0 av 8784 |
| **Pay-as-produced revenue** | 1.94 MSEK/år |
| **Break-even premium** | ~4% (17 SEK/MWh) |

---

## 1. Leveransriskanalys

### Simuleringsresultat (SE3 2024)

Med 20% sol / 80% vind mix och 90% batterieffektivitet:

| Baseload (kW) | % av medel | Missade timmar | Risk |
|---------------|------------|----------------|------|
| 200 | 38% | 0 | Ingen |
| 220 | 42% | 0 | Ingen |
| 230 | 44% | 7 | Låg |
| 250 | 48% | 34 | Medium |
| 300 | 57% | 128 | Hög |

**Slutsats:** 200 kW med 1h batteri klarar 100% leverans för 2024 års data.

---

## 2. Ekonomisk Jämförelse

### Pay-as-produced (referensscenario)

| Parameter | Värde |
|-----------|-------|
| Årlig produktion | 4,621 MWh |
| Capture price | 419 SEK/MWh |
| **Årlig revenue** | **1.94 MSEK** |

### Baseload PPA (med batteri)

| Parameter | Värde |
|-----------|-------|
| Årlig baseload-leverans | 1,753 MWh (200 kW × 8760h) |
| Överskott till spot | 2,868 MWh |

### Batterikostnad

| Post | Värde |
|------|-------|
| CAPEX | 500 kSEK (200 kWh × 2,500 SEK/kWh) |
| Avskrivning (15 år) | 33 kSEK/år |
| O&M (~2%/år) | 10 kSEK/år |
| **Total årskostnad** | **43 kSEK/år** |

---

## 3. Break-even Premium

För att täcka batterikostnaden krävs ett premium på baseload-volymen:

```
Break-even premium = Batterikostnad / Baseload-volym
                   = 43,000 SEK / 1,753 MWh
                   = 24.5 SEK/MWh ≈ 2.5 öre/kWh
```

**Uttryckt som procentuellt premium:**
```
Premium % = 24.5 / 419 = 5.8%
```

### Praktisk tolkning

Om spotpris (capture) = 419 SEK/MWh:
- **Baseload PPA-pris** behöver vara ≥ **444 SEK/MWh** för break-even
- Premium: ~25 SEK/MWh eller 2.5 öre/kWh

---

## 4. Icke-kvantifierade Risker

### Hög påverkan

| Risk | Beskrivning | Mitigation |
|------|-------------|------------|
| **Vädervariation** | 2024 kan vara atypiskt; andra år kan ha längre vindstilla perioder | Analysera 5-10 års historik |
| **Prisrisk vid icke-leverans** | Måste köpa el på spot vid deficit, kan vara dyrt vid höga priser | Tak på straffavgift i kontraktet |

### Medium påverkan

| Risk | Beskrivning | Mitigation |
|------|-------------|------------|
| **Batteridegradation** | 80% kapacitet efter 10-15 år | Överdimensionera initialt |
| **Tekniskt driftsstopp** | Batteri/omriktare kan gå sönder | Serviceavtal med SLA |
| **Ränterisk** | Finansieringskostnad kan öka | Fast ränta på lån |

### Låg påverkan

| Risk | Beskrivning |
|------|-------------|
| **Motpartsrisk** | PPA-köparens betalningsförmåga |
| **Regulatorisk risk** | Förändrade skatter/avgifter |

---

## 5. Rekommendation

### För 200 kW baseload:

**Go ahead** om:
- PPA-premium ≥ 25 SEK/MWh (6% över spot)
- Kontraktet har rimlig straffklausul för icke-leverans
- Producenten accepterar vädervariation som kvarstående risk

**Alternativ att överväga:**
- 180 kW baseload (större säkerhetsmarginal)
- 10% pass-klausul (minskar batteri/risk markant)
- Längre batterigaranti från leverantör

---

## 6. Känslighetsanalys

### Vid olika spotprisnivåer

| Spot (SEK/MWh) | Break-even premium (%) |
|----------------|------------------------|
| 300 | 8.2% |
| 400 | 6.1% |
| 500 | 4.9% |
| 600 | 4.1% |

### Vid olika batterikostnader

| CAPEX (SEK/kWh) | Årskostnad | Break-even premium |
|-----------------|------------|-------------------|
| 2,000 | 35 kSEK | 20 SEK/MWh (4.8%) |
| 2,500 | 43 kSEK | 25 SEK/MWh (5.8%) |
| 3,000 | 52 kSEK | 30 SEK/MWh (7.1%) |

---

## Datakällor

- Spotpriser: elprisetjustnu.se SE3 2024
- Sol/vindprofiler: PVsyst + ENTSO-E
- Batterikostnader: Marknadsestimat 2024
- Analys: `elpris/baseload_analysis.py`

---

*Genererad 2024-12-09*
