# Batteridimensionering för prognosfelkompensation

Hur stort batteri behövs för att kompensera prognosfel i solproduktion och minimera obalanskostnader?

## Sammanfattning

| Prognosaccuracy | MAPE | Batteri | CAPEX | Coverage |
|-----------------|------|---------|-------|----------|
| 95% | 5% | **100 kW / 100 kWh** | ~52 500 EUR | 99% |
| 90% | 10% | **200 kW / 175 kWh** | ~117 500 EUR | 99% |

**Tumregel för 1 MWp PV:**
- Effekt ≈ 10-20% av peak-produktion
- Energi ≈ 1 timmes maxavvikelse
- Dubbel MAPE → Dubbelt batteri

---

## Definitioner

### MAPE (Mean Absolute Percentage Error)
Genomsnittligt procentuellt prognosfel.

```
Exempel:
  Prognos: 500 kW
  Verklighet: 475 kW
  Fel: |500 - 475| / 500 = 5%

5% MAPE = 95% prognosaccuracy (samma sak, olika uttryck)
```

### Coverage
Andel av prognosfel som batteriet kan kompensera.

- **P95 coverage** = täcker 95 av 100 simulerade avvikelser
- **P99 coverage** = täcker 99 av 100 simulerade avvikelser
- **P100 coverage** = täcker worst-case i simulering

### Obalans
Skillnaden mellan prognostiserad och faktisk produktion leder till obalans på elmarknaden, vilket medför kostnader.

---

## Hur batteriet kompenserar prognosfel

```
Scenario: Du lovade marknaden 600 kW kl 12:00

Verklighet A: Du producerar 550 kW (50 kW underskott)
→ Batteriet laddar ur 50 kW för att fylla gapet
→ Du levererar 600 kW som lovat

Verklighet B: Du producerar 650 kW (50 kW överskott)
→ Batteriet laddar in 50 kW
→ Du levererar 600 kW som lovat
```

---

## Analysresultat (1 MWp PV)

Baserat på Monte Carlo-simulering med 10 000 körningar, solprofil `south_lundby` (1012 kWh/kWp/år).

### Scenario 1: 95% prognosaccuracy (5% MAPE)

| Percentil | Effekt (kW) | Energi (kWh) | CAPEX (EUR) |
|-----------|-------------|--------------|-------------|
| P95 | 100 | 75 | 52 500 |
| P99 | 100 | 100 | 65 000 |
| P99.9 | 125 | 100 | 68 750 |
| P100 (max) | 125 | 100 | 68 750 |

**Rekommendation:** 100 kW / 100 kWh (~65 000 EUR)

### Scenario 2: 90% prognosaccuracy (10% MAPE)

| Percentil | Effekt (kW) | Energi (kWh) | CAPEX (EUR) |
|-----------|-------------|--------------|-------------|
| P95 | 175 | 150 | 101 250 |
| P99 | 200 | 150 | 105 000 |
| P99.9 | 225 | 175 | 121 250 |
| P100 (max) | 250 | 200 | 137 500 |

**Rekommendation:** 200 kW / 175 kWh (~117 500 EUR)

### Jämförelse

| Parameter | 5% MAPE | 10% MAPE | Skillnad |
|-----------|---------|----------|----------|
| Effekt | 100 kW | 200 kW | +100% |
| Energi | 100 kWh | 175 kWh | +75% |
| CAPEX | 65 000 EUR | 117 500 EUR | +81% |

**Slutsats:** Sämre prognos (90% vs 95%) kräver nästan dubbelt så stort batteri.

---

## Ekonomisk analys

### Obalanskostnader (utan batteri)

| MAPE | Årlig obalans | Kostnad/år |
|------|---------------|------------|
| 5% | ~51 MWh | ~1 000 EUR |
| 10% | ~101 MWh | ~2 000 EUR |

*Baserat på genomsnittliga obalanspriser: 25 EUR/MWh (upp), 15 EUR/MWh (ned)*

### Batterikostnad

| Batteri | CAPEX | Årlig kostnad* |
|---------|-------|----------------|
| 100 kW / 100 kWh | 65 000 EUR | 8 420 EUR |
| 200 kW / 175 kWh | 117 500 EUR | 15 217 EUR |

*10 års livslängd, 5% diskonteringsränta*

### Lönsamhet för enbart prognosfelkompensation

| Scenario | Besparing/år | Batterikostnad/år | Netto |
|----------|--------------|-------------------|-------|
| 5% MAPE | ~1 000 EUR | ~8 400 EUR | **-7 400 EUR** |
| 10% MAPE | ~2 000 EUR | ~15 200 EUR | **-13 200 EUR** |

**Slutsats:** Batteriet är INTE lönsamt enbart för prognosfelkompensation.

### Värdet av batteriet

Prognosfelkompensation är en **sekundär** intäktsström. Batteriet måste kombineras med:

1. **FCR (Frequency Containment Reserve)** - högre intäkter
2. **Arbitrage** - köp billigt, sälj dyrt
3. **Peak shaving** - minska effekttoppar
4. **Backup/reservkraft** - värde vid nätfel

---

## Praktiska tumregler

### Dimensionering

```
För 1 MWp PV med 95% prognosaccuracy:
  Effekt:  100 kW (13% av peak 754 kW)
  Energi:  100 kWh (1 timmes buffert)
  C-rate:  1.0 (standard för BESS)
```

### Skalning

| Site-storlek | 5% MAPE | 10% MAPE |
|--------------|---------|----------|
| 1 MWp | 100 kW / 100 kWh | 200 kW / 175 kWh |
| 5 MWp | 500 kW / 500 kWh | 1 000 kW / 875 kWh |
| 10 MWp | 1 000 kW / 1 000 kWh | 2 000 kW / 1 750 kWh |

*Linjär skalning - approximation*

---

## Begränsningar

### Vad batteriet INTE täcker

1. **Extrema väderförändringar**
   - Plötsligt molntäcke (754 kW → 100 kW)
   - Snö på paneler
   - Hagel/storm

2. **Långvariga avvikelser**
   - 50 kW fel i 3 timmar = 150 kWh (överstiger 100 kWh kapacitet)

3. **Prognosfel > design-percentil**
   - P99-batteri täcker inte P100-händelser

### Åtgärder för "nära 100%" coverage

1. **Bättre prognoser** - investera i väderdata/ML
2. **Större batteri** - men dyrare
3. **Intraday-handel** - justera positioner närmare leverans
4. **Acceptera viss obalans** - kan vara billigare än batteriet

---

## Antaganden i modellen

| Parameter | Värde | Kommentar |
|-----------|-------|-----------|
| Solprofil | south_lundby | 1012 kWh/kWp/år, peak 0.754 MW/MWp |
| Korrelerade perioder | 4 st | 1 timmes maxavvikelse åt samma håll |
| Energikostnad | 500 EUR/kWh | BESS-kapacitet |
| Effektkostnad | 150 EUR/kW | Inverter/anslutning |
| Livslängd | 10 år | Kalendarisk |
| Diskonteringsränta | 5% | För annuitetsberäkning |
| Roundtrip-effektivitet | 88% | Laddning + urladdning |

---

## Relaterade verktyg

```bash
# Kör batteridimensionering
python3 battery_sizing_cli.py --profile south_lundby --capacity 1.0 --mape 0.05 --simulate --imbalance

# Visa alla profiler
python3 battery_sizing_cli.py --list-profiles

# Visa produktionsstatistik
python3 battery_sizing_cli.py --profile south_lundby --stats
```

## Källkod

- `elpris/battery_sizing.py` - `size_for_forecast_error()`, `calculate_coverage()`
- `elpris/forecast_error.py` - `ForecastErrorModel`, `simulate_forecast_errors()`
- `elpris/imbalance_cost.py` - `calculate_imbalance_cost()`, `calculate_battery_savings()`
