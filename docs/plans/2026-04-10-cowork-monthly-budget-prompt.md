# Cowork-prompt: Månatlig PVsyst-budget per park

**Datum:** 2026-04-10
**Syfte:** Extrahera månadsvisa expected energy + irradiation + PR från PVsyst SRC Forecast-rapporter per park, för att kunna fylla i `PARK_BUDGET_OVERRIDES` i `elpris/park_config.py`.

## Bakgrund

Idag använder `get_budget()` i `park_config.py` en **approximation**:
- Parkens årliga yield från Cowork-extraktet (t.ex. Hörby: 1036 kWh/kWp/år)
- Månadsfördelning från PVsyst-profilen (south_lundby/ew_boda/tracker_sweden)
- Detta ger en **rimlig** budget men är inte 100% parkspecifik

För att förbättra precisionen behöver vi **månadsvärden direkt från PVsyst SRC Forecast-rapporten per park**. Dessa PDFs finns i SharePoint under varje parks Technical Documentation / Yield Assessment-mapp.

## Prompt för Claude Cowork

Klistra in följande i Claude Cowork som har SharePoint-access:

```
Jag behöver extrahera månadsvisa värden från PVsyst SRC Forecast-rapporterna
för Svea Solars 8 operativa solparker. Datat ska användas för att kalibrera
budgetvärden i ett månadsrapport-system.

PARKER och RAPPORTER (samtliga SRC Forecast från Oct 2025):

1. Hörby (Mjällby, SE4, 12 MWac) — "14102025_Hörby PVsyst_SRC Forecast 12 MW [SLC_weighted].pdf"
2. Fjällskär 1 (Enstaberga, SE3, 14 MWac) — "15102025_PVsyst Fjällskär SRC Forecast [SLC].pdf"
3. Björke (Trödje, SE3, 4 MWac) — "15102025_PVsyst Björke Bifacial SRC Forecast 4MW [SLC].pdf"
4. Agerum (Örelycke, SE4, 6 MWac) — "15102025_PVsyst Agerum SRC Forecast [SLC].pdf"
5. Hova (Källtorp, SE3, 5 MWac, TRACKER) — "15102025_Hova_PVsyst SRC Forecast 5MW [SLC].pdf"
6. Skäkelbacken (Dalarna, SE3, 5 MWac) — "15102025_PVsyst Skakelbacken SRC Forecast [SLC].pdf"
7. Stenstorp (Västra Götaland, SE3, 0.9 MWac) — "05052025_Stenstorp_Bifacial PVsyst RH SRC [MTNM]_Corrected.pdf"
8. Tången 1 (Gungvala, SE4, 4.5 MWac) — "15102025_PVsyst Tången SRC Forecast [SLC].pdf"

SHAREPOINT-SÖKVÄG (sannolikt):
https://sveasolarcom.sharepoint.com/sites/Utilityhub/Asset Management Library/
Projects in operation/{PARK_FOLDER}/03 - Technical Documentation/01 - Yield Assessment/01 - PVsyst/

Där PARK_FOLDER är:
- 01 - Fjällskär, 02 - Hörby, 03 - Björke, 04 - Agerum,
- 06 - Hova, 08 - Stenstorp, 09 - Skakelbacken, 10 - Tången

VAD SOM SKA EXTRAHERAS PER PARK OCH MÅNAD (12 månader):

Från PVsyst-rapportens "Main results" eller "Balances and main results"-tabell,
hitta den månadsvisa tabellen och extrahera:

- month: 1-12 (Jan-Dec)
- energy_mwh: E_Grid (Energy injected into grid) i MWh
- irradiation_kwh_m2: GlobInc eller "POA irradiation" i kWh/m² för månaden
- pr_pct: Performance Ratio % för månaden (varierar typiskt per månad,
          högre i vinter pga kallare moduler)

OBS: Kolla kolumnrubriker noga! PVsyst använder ibland:
- E_Grid (MWh) eller E_Grid (kWh) — om kWh, dividera med 1000
- GlobInc (kWh/m²) eller GlobInc (MWh/m²) — standard är kWh/m²
- PR som decimal (0.82) eller procent (82.0) — vi vill ha procent

OUTPUTFORMAT:

Returnera en Python-dict som denna (klistra-och-kör-format):

```python
PARK_BUDGET_OVERRIDES = {
    "horby": {
        "2026-01": {"energy_mwh": 195.0, "irradiation_kwh_m2": 14.0, "pr_pct": 79.5},
        "2026-02": {"energy_mwh": 530.0, "irradiation_kwh_m2": 36.5, "pr_pct": 81.2},
        "2026-03": {"energy_mwh": 1520.0, "irradiation_kwh_m2": 105.0, "pr_pct": 83.5},
        "2026-04": {"energy_mwh": 2100.0, "irradiation_kwh_m2": 145.0, "pr_pct": 84.2},
        "2026-05": {"energy_mwh": 2650.0, "irradiation_kwh_m2": 180.0, "pr_pct": 84.5},
        "2026-06": {"energy_mwh": 2850.0, "irradiation_kwh_m2": 195.0, "pr_pct": 83.8},
        "2026-07": {"energy_mwh": 2780.0, "irradiation_kwh_m2": 190.0, "pr_pct": 83.1},
        "2026-08": {"energy_mwh": 2400.0, "irradiation_kwh_m2": 165.0, "pr_pct": 83.5},
        "2026-09": {"energy_mwh": 1750.0, "irradiation_kwh_m2": 120.0, "pr_pct": 84.0},
        "2026-10": {"energy_mwh": 1050.0, "irradiation_kwh_m2": 70.0, "pr_pct": 82.8},
        "2026-11": {"energy_mwh": 380.0, "irradiation_kwh_m2": 26.0, "pr_pct": 78.5},
        "2026-12": {"energy_mwh": 130.0, "irradiation_kwh_m2": 9.0, "pr_pct": 76.0},
    },
    "fjallskar": {
        # ... samma struktur för alla 12 månader
    },
    # ... alla 8 parker
}
```

VIKTIGT:
1. Använd år 2026 för nyckeln (året vi genererar rapporter för)
2. Om rapporten använder annan basera-år, notera det
3. Om något värde är osäkert eller inte finns, lämna en kommentar
4. Ange i toppen av dictt vilket år PVsyst-simuleringen baseras på
5. Om tabellen har annorlunda kolumnrubriker, berätta vad du hittade
6. För Hova (tracker), PR kan vara högre (85-90%) än för fixed-tilt parker

SÄRSKILT OM STENSTORP:
Stenstorp-rapporten är från maj 2025 (Corrected version med MTNM-väder),
inte oktober-batchen. Nämn om det är märkbar skillnad i metodologi.

Efter extraktionen, gör en sanity-check:
- Sum av månaderna ≈ årliga yield × kapacitet (inom ±2%)
- Irradiation-total ska matcha årsvärdet i rapporten
- PR-medel (viktat på energi) ska matcha parkens årliga PR

Om något inte stämmer, flagga det så vi kan utreda.
```

## Användning efter Cowork returnerar data

När Cowork levererar dict-datat:

1. **Verifiera sanity-checks** — sum av månader ska matcha årligt total
2. **Klistra in i `elpris/park_config.py`** — ersätt den tomma `PARK_BUDGET_OVERRIDES`
3. **Kör om rapporter för de månader vi har:**
   ```bash
   python generate_performance_report.py --all --month 2026-01
   python generate_performance_report.py --all --month 2026-02
   python generate_performance_report.py --all --month 2026-03
   ```
4. **Jämför före/efter** — budget-värdena ska ändras (sannolikt några procent) och PR-jämförelser ska vara mer exakta
5. **Commit:**
   ```bash
   git add elpris/park_config.py
   git commit -m "data: fill PARK_BUDGET_OVERRIDES with monthly PVsyst values"
   ```

## Effekt på rapporter

**Före:**
- Budget beräknas genom att skala PVsyst-profil med parkens årliga yield
- Alla månaders PR-budget är samma (parkens årsvärde)
- Approximation med ±5% fel mot verklig PVsyst-förväntan

**Efter:**
- Budget är direkt från parkens egen PVsyst-simulering
- Månadsvisa PR-skillnader reflekteras (vinter = högre PR pga kallare moduler)
- Exakt match mot PVsyst SRC Forecast — ingen approximation

## Alternativ om Cowork inte kan läsa PDFs

Om Cowork inte kan parsa PVsyst-tabellerna ur PDFs:

1. **Manuell metod:** Be Operations att exportera månadstabeller från PVsyst till Excel/CSV per park
2. **Gemensam approach:** Använd "Main results"-tabellens bild och transkribera manuellt (12 rader × 3 värden × 8 parker = 288 värden — 1-2h jobb)
3. **OCR:** Kör PDF genom OCR (pytesseract/unstructured) för att få tabelldata

## Stäng inte denna fil efter extraktion

Behåll detta dokument i repo:t som referens för FRAMTIDA UPPDATERINGAR när nya PVsyst-rapporter kommer (t.ex. efter tracker-ombyggnader, degraderingsuppdateringar, nya PPA-kontrakt).
