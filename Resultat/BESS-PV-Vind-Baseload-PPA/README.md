# BESS + PV + Vind: Baseload PPA Analys

**Senast uppdaterad:** 2024-12-09
**Zon:** SE3 | **År:** 2024 | **Batterieffektivitet:** 90%

---

## Sammanfattning

Denna analys undersöker hur man kan leverera **baseload PPA** (konstant effekt 24/7/365) genom att kombinera:
- Solkraft (PV)
- Vindkraft
- Batterilagring (BESS)

### Huvudresultat

| Parameter | Värde |
|-----------|-------|
| **Optimal ratio** | 20% Sol / 80% Vind |
| **Max Baseload** | 44% av medelproduktion |
| **Batteri (1-2h duration)** | 0.46 MWh |
| **Batterieffektivitet** | 90% round-trip |

---

## Innehåll

### Presentation
- `baseload_ppa_presentation.pptx` - 9 slides med analys och resultat

### Resultat (`/resultat`)
| Fil | Beskrivning |
|-----|-------------|
| `baseload_ppa_analysis.xlsx` | Timvis analys med BESS state-of-charge |
| `ratio_optimization_SE3_2024.xlsx` | Grid-sökning för optimal sol/vind ratio |
| `ratio_optimization_SE3_2024.png` | Visualisering av ratio-optimering |
| `baseload_validation_SE3_2024.xlsx` | **Valideringsverktyg med formler** (se nedan) |

### Dokumentation (`/dokumentation`)
| Fil | Beskrivning |
|-----|-------------|
| `baseload_ppa_key_insights.md` | 7 nyckelinsikter från analysen |
| `2024-12-06_baseload_ppa_analys.md` | Detaljerad analysrapport |
| `ekonomisk_riskanalys_200kW.md` | Ekonomisk- och riskanalys för 200 kW baseload |

### Kod (`/kod`)
| Fil | Beskrivning |
|-----|-------------|
| `baseload_analysis.py` | Huvudmodul för baseload-beräkningar |
| `baseload_ratio_cli.py` | CLI för ratio-optimering |

---

## Hur man kör analysen

```bash
# Från electricity-price root:
python baseload_ratio_cli.py --battery-min 1.0 --battery-max 2.0 --efficiency 0.90 --excel --heatmap
```

### CLI-flaggor

| Flagga | Default | Beskrivning |
|--------|---------|-------------|
| `--total-capacity` | 2.0 | Total installerad kapacitet (MW) |
| `--zone` | SE3 | Elområde (SE1-SE4) |
| `--battery-min` | 1.0 | Min batteri-duration (h) |
| `--battery-max` | 3.0 | Max batteri-duration (h) |
| `--efficiency` | 0.90 | Round-trip batterieffektivitet |
| `--excel` | - | Exportera till Excel |
| `--heatmap` | - | Skapa visualisering |

---

## Nyckelinsikter

1. **80% baseload är sweet spot** - Kräver endast 8 MWh batteri vs 109 MWh för 100%
2. **Sommarnätter är flaskhalsen** - Inte vintern som förväntat
3. **10% pass minskar batteri 50-100%** - Förhandla pass-timmar i PPA
4. **Mer vind med striktare batteri-constraint** - Vind täcker nätter utan buffring
5. **90% efficiency ökar batteribehov ~10%** - Viktigt att inkludera i beräkningar

---

## Ekonomisk Analys (200 kW Baseload)

| Parameter | Värde |
|-----------|-------|
| **Baseload** | 200 kW (38% av medelproduktion) |
| **Batteri** | 200 kWh / 1h duration |
| **Missade timmar (2024)** | 0 |
| **Pay-as-produced revenue** | 1.94 MSEK/år |
| **Break-even premium** | ~6% (25 SEK/MWh) |

Se `dokumentation/ekonomisk_riskanalys_200kW.md` för fullständig analys.

---

## Valideringsverktyg

Excel-filen `resultat/baseload_validation_SE3_2024.xlsx` innehåller 7 flikar för att validera beräkningarna:

| Flik | Beskrivning |
|------|-------------|
| **Parametrar** | Redigerbara inputs - ändra baseload, efficiency, sol/vind MW |
| **Sol Profil** | 8760 timmar med normaliserad solproduktion |
| **Vind Profil** | 8760 timmar med kapacitetsfaktor för vind |
| **Timberäkning** | Formler: deficit, surplus, net flow, cum sum, SOC |
| **Daglig Summering** | 366 rader aggregerat per dag |
| **Kritiska Timmar** | Top 100 värsta underskottstimmar |
| **Sammanfattning** | Nyckeltal med automatiska formler |

### Så här validerar du analysen

1. Öppna `baseload_validation_SE3_2024.xlsx`
2. Gå till fliken **Parametrar** och ändra t.ex. baseload från 0.231 till 0.300 MW
3. Observera hur **Sammanfattning** uppdateras automatiskt:
   - Deficit-timmar ökar
   - Max batteribehov ökar
   - Batteriduration ökar
4. Granska **Timberäkning** för att se timvisa beräkningar
5. Se **Kritiska Timmar** för att identifiera värsta stunderna

### Generera ny valideringsfil

```bash
python baseload_ratio_cli.py --battery-min 1.0 --battery-max 2.0 --efficiency 0.90 --detailed-validation
```

---

## Datakällor

- **Solprofil:** PVsyst simulation (south_lundby)
- **Vindprofil:** ENTSO-E Transparency Platform, SE3 2024
- **Period:** 8,784 timmar (skottår 2024)

---

*Genererad med `elpris` analysverktyg*
