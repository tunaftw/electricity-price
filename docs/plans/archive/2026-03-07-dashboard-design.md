# Elpris Dashboard v1 — Design

**Datum:** 2026-03-07
**Status:** Godkänd

## Översikt

Självständig HTML-fil som visualiserar svenska elpriser (SE1–SE4) med fokus på
baseload-pris och capture price för solenergi. Genereras av ett Python-skript
som läser befintlig data och bäddar in allt i en enda HTML-fil.

## Beslut

| Parameter | Val |
|-----------|-----|
| Plattform | Självständig HTML-fil (framtida Vercel-hosting möjlig) |
| Grafbibliotek | Plotly.js |
| Valuta | EUR/MWh |
| Default-zon | Alla zoner likvärdigt (SE1–SE4) |
| Default-tidsperiod | All historik (från 2021-11-01) |
| Solprofiler | PVsyst (syd, öst-väst, tracker) + ENTSO-E normaliserade per zon |

## Solprofiler

### PVsyst-profiler (tre stycken)
- **Syd** — `south_lundby.csv` (Lundby, sydvänd)
- **Öst-Väst** — `ew_boda.csv` (Böda, öst-väst)
- **Tracker** — `tracker_sweden.csv` (Hova, single-axis tracker)

### ENTSO-E normaliserade (per zon)
- `solar_SE1.csv`, `solar_SE2.csv`, `solar_SE3.csv`, `solar_SE4.csv`

## Layout — tre huvudsektioner

### 1. Årsöversikt (landningssida)

**Tabell:**
- Rader: Alla hela år (2022, 2023, 2024, 2025, 2026 YTD)
- Kolumner per zon: baseload-pris, capture price (syd/öv/tracker), capture ratio
- Färgkodning för snabb överblick

**Graf:**
- Plotly-graf: baseload vs capture price per år, alla zoner
- Grupperat stapeldiagram eller linjediagram

### 2. Månadsvy

**Interaktivitet:**
- Välj ett eller flera år att jämföra
- Filtrera per zon

**Tabell + graf:**
- Baseload och capture price per månad
- Jämför syd vs öst-väst vs tracker i samma graf
- ENTSO-E-baserad capture som extra lager/toggle

### 3. Trendanalys

**Graf:**
- Linjediagram: capture price och capture ratio över hela historiken
- Filtrera per zon och profiltyp
- Baseload som referenslinje
- Plotly zoom/pan för detaljanalys

## Teknisk arkitektur

### Generering
```
Python-skript (generate_dashboard.py)
    ├── Läser spotpriser från Resultat/marknadsdata/spotpriser/
    ├── Läser solprofiler från Resultat/profiler/
    ├── Beräknar baseload + capture prices (återanvänder elpris/capture.py)
    ├── Serialiserar data till JSON
    └── Genererar self-contained HTML med inbäddad data + Plotly.js
```

### Befintliga moduler att återanvända
- `elpris/capture.py` — capture price-beräkning
- `elpris/solar_profile.py` — PVsyst-profilladdning + viktberäkning
- `elpris/config.py` — zoner, sökvägar, konstanter
- `elpris/storage.py` — dataladdning och statistik

### Uppdatering
1. Kör `update_all.py` (laddar ner ny data)
2. Kör `generate_dashboard.py` (genererar ny HTML)
3. Dela filen med kollegor

## Designprinciper

- **Pedagogiskt** — Tydliga rubriker, förklarande tooltips, logisk struktur
- **Grafiskt tilltalande** — Konsekvent färgpalett, professionell typografi
- **Interaktivt lagom** — Filtrering per datum/år/zon, inte överlastat
- **Skalbart** — Enkel att migrera till Vercel när det är dags

## Framtida utbyggnad (v2+)

- BESS och stödtjänstmarknadspriser
- Volatilitetsanalys (spread-visualisering, tröskelanalys)
- Capture prices för vind, vatten, kärnkraft
- Automatisk uppdatering (schemalagd)
- Hosting på Vercel med JSON-datafiler
