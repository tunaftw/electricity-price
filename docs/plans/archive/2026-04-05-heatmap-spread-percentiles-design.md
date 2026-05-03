# Heatmap + Spread Percentiler — Design

## Context

Dashboarden visar idag spotpriser som tidsserier (drill-down år→månad→dag) och spread som ett enda genomsnitt per period. Detta döljer två typer av mönster som investerare behöver:

1. **Intradag-mönster**: När på dygnet (och året) är priserna högst? Detta styr BESS-dispatch-strategi och värderar solens produktionsprofil.
2. **Volatilitetsdistribution**: Hur ofta är spreads stora nog att motivera arbitrage? En medeldagsvärde döljer tail-risk — var 10:e dag kan vara nära olönsam.

Designen tillför två kompletterande visualiseringar — en på CAPTURE-tabben (prismönster) och en på BESS-tabben (arbitrage-case).

---

## Feature 1: Spotpris-heatmap (CAPTURE-tabben)

### Placering

Nytt kort längst ner på CAPTURE-vyn, efter zonjämförelse-matrisen.

### Innehåll

12×24 heatmap: **månader som rader, timmar som kolumner**, celler färgade efter medelspotpris i EUR/MWh. Följer aktiv zon (`state.zone`).

**Mode-toggle via dropdown:**
- "Alla år" (default) — aggregerat medelvärde över all tillgänglig data, visar typisk säsongs-/dygnsrytm
- Per-år (2021, 2022, ..., 2026) — visar hur mönstret förändrats

**Färgskala:** `RdYlBu` inverterad (blå = lågt pris, röd = högt). Branschstandard.

**Hover:** "Jan 18:00 → 85.3 EUR/MWh"

### Datalayer

Ny funktion `_calculate_hour_month_heatmap(spot_prices, year=None)` i `elpris/dashboard_v2_data.py`. Returnerar 12×24 matris med medelpriser. Celler utan data = `None`.

I `calculate_dashboard_v2_data()` byggs `heatmap[zone] = {"all": matrix, "by_year": {year: matrix}, "years": [...]}`. Storlek: ~7k floats totalt (trivialt).

### Frontend

- HTML: nytt `.card` med titel, infotext, year-dropdown, `<div id="heatmap-chart">`
- JS: `renderHeatmap()` byggs från `DATA.heatmap[state.zone]`, Plotly `type: 'heatmap'`
- Anropas från `renderYearly/Monthly/Daily` så den följer zonbyte
- `buildHeatmapYearDropdown()` fyller dropdown vid init

---

## Feature 2: Spread-percentiler (BESS-tabben)

### Placering

Nytt kort efter existerande Spread-graf på BESS-vyn.

### Innehåll

Tabell med rader = percentiler (P90, P75, P50, P25, P10) och kolumner = år + "Totalt". P50-raden fetstilas som median.

**Exempel (SE3):**

| Percentil | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | Totalt |
|-----------|------|------|------|------|------|------|--------|
| P90 (bra dag) | 310 | 350 | 130 | 95 | 140 | 150 | 230 |
| P75 | 210 | 235 | 85 | 65 | 95 | 105 | 150 |
| **P50 (median)** | **140** | **155** | **55** | **45** | **65** | **75** | **95** |
| P25 | 85 | 105 | 35 | 30 | 40 | 50 | 55 |
| P10 (dålig dag) | 40 | 60 | 15 | 15 | 20 | 25 | 25 |

Visar volatilitet över tid: krisår 2022 = bred fördelning, normalår = smal.

### Datalayer

Ny funktion `_calculate_spread_percentiles(spread_daily)` i `elpris/bess_dashboard_data.py`. Använder `statistics.quantiles` med n=100 för att få exakta percentiler.

Krav ≥10 värden för att beräkna percentil (annars None). Lagras som `zone_data["spread_percentiles"]` = `{years: [...], percentiles: {p10: [...], p25: [...], ...}}`.

### Frontend

- HTML: nytt `.card` efter Spread-grafen med `<table id="spread-percentile-table">`
- JS: `renderSpreadPercentiles()` bygger HTML-tabellen
- Anropas från `renderBess()` så den följer zon- och unit-förändringar
- Varje rad har unik färg/opacitet så ögat hittar P50 snabbt

---

## Filer att modifiera

| Fil | Ändring |
|-----|---------|
| `elpris/dashboard_v2_data.py` | Ny funktion `_calculate_hour_month_heatmap()`, bygg heatmap-data per zon |
| `elpris/bess_dashboard_data.py` | Ny funktion `_calculate_spread_percentiles()`, bygg percentiler per zon |
| `generate_dashboard_v2.py` | Två nya kort + JS-rendering + year dropdown för heatmap |

---

## Återanvändbara byggstenar

- `load_spot_prices(zone)` — redan existerande, levererar hourly spotpriser per zon
- `spread_daily` — redan beräknat i `calculate_bess_data()` för BESS-spread-profilen
- `statistics.quantiles()` — Python standard library, ingen extra dependency
- `PLOTLY_DARK` theme — återanvänds för heatmap layout
- `.card` + `.card-title` CSS-stil — återanvänds för båda nya korten

---

## Verifiering

1. Kör `python3 generate_dashboard_v2.py` — ska slutföras utan fel
2. Öppna HTML, CAPTURE-tabben:
   - Nytt "Spotpris-heatmap"-kort syns längst ner
   - Heatmap visar 12×24 matris för aktiv zon
   - Dropdown visar "Alla år" + 2021-2026
   - Byte av zon uppdaterar heatmappen
   - Byte av år i dropdown uppdaterar matrisen
3. Öppna BESS-tabben:
   - Nytt "Spread-percentiler"-kort syns efter Spread-grafen
   - Tabell har 5 rader × (år + Totalt) kolumner
   - P50-raden är fetstilad
   - Byte av zon uppdaterar tabellen
4. Visuell sanity check:
   - SE3 heatmap sommar 11-14: blåaktig (låga priser, solkannibaliseringseffekt)
   - SE3 heatmap vinter 17-20: röd (höga peaks)
   - SE3 2022 percentiler högre än 2024 (krisår vs normalår)

---

## Out of scope

- Click-to-drill-down på heatmap-celler (tooltip räcker för V1)
- Profile-specific heatmaps (sol_syd capture by hour×month) — kan lätt läggas till senare som dropdown
- Histogram-visning av spread-distribution — percentiltabellen ger liknande insikt
- Percentiler per månad (bara per år) — håller scope nere
