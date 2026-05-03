# Datadriven Excel-export for Dashboard V2

**Datum:** 2026-04-04
**Status:** Design klar

## Problem

Excel-exporten (`excel_export_v2.py`) har hårdkodad kunskap om vilka profiler och datakällor som finns. När en ny profil (t.ex. en park, ett kraftslag) läggs till i dashboarden måste Excel-koden uppdateras manuellt. Det är felbenäget och skalas inte.

## Lösning

En datadriven Excel-export som läser samma datastruktur som dashboarden och anpassar sig automatiskt till nya profiler. Exporten blir en tunn serialiseringslayer — den beskriver *format*, inte *logik*.

## Arkitekturprincip

```
dashboard_v2_data.py → calculate_dashboard_v2_data(granularities=...)
       ↓                              ↓
  dashboard HTML                 excel_export_v2.py
  (yearly/monthly/daily)         (yearly/monthly/daily/hourly)
```

Samma funktion, samma beräkningar, samma profiler. Enda skillnaden: vilka granularitetsnivåer som begärs. Dashboard-HTML:en begär `["yearly", "monthly", "daily"]` (som idag). Excel-exporten begär `["yearly", "monthly", "daily", "hourly"]`.

## Datastruktur (kontrakt)

Funktionen `calculate_dashboard_v2_data()` returnerar:

```python
{
  "zones": ["SE1", "SE2", "SE3", "SE4"],
  "profiles": {"baseload": "Baseload", "sol_syd": "Sol Syd", ...},
  "data": {
    "SE1": {
      "baseload": {
        "yearly":  [{"year": 2024, "baseload": 45.3, "capture": None, ...}],
        "monthly": [{"year": 2024, "month": 1, "baseload": 52.1, ...}],
        "daily":   [{"date": "2024-01-01", ...}],
        "hourly":  [{"date": "2024-01-01", "hour": 0, "baseload": 48.2, 
                     "capture": 0.0, "weight": 0.0}, ...]
      },
      "sol_syd": { ... same structure ... }
    }
  }
}
```

Hourly genereras bara när det begärs via `granularities`-parametern.

## Excel-flikstruktur

**Zon x granularitet:** 4 zoner x 4 nivåer = 16 flikar + 1 sammanfattning.

| Flik | Rader (uppskattning) | Innehåll |
|------|----------------------|----------|
| SE1 Yearly | ~5 | Year, Baseload, [profil capture+ratio]... |
| SE1 Monthly | ~60 | Year, Month, Baseload, [profil capture+ratio]... |
| SE1 Daily | ~1 800 | Date, Baseload, [profil capture+ratio]... |
| SE1 Hourly | ~44 000 | Date, Hour, Baseload, [profil capture+weight]... |
| SE2 Yearly | ... | ... |
| ... | | |
| Sammanfattning | 1 flik | Yearly per zon, senaste året |

Kolumner genereras dynamiskt från `data["profiles"]` — nya profiler dyker upp automatiskt.

## Formatering

- Priser: `#,##0.00` (EUR/MWh)
- Ratios: `0.000` med villkorlig färg (grön >= 0.9, gul >= 0.7, röd < 0.7)
- Frozen header-rad och auto-filter på varje flik
- Flikfärger per zon (matchande dashboardens färger)
- Hourly inkluderar `weight` per profil för verifierbarhet

## Hourly-beräkning

Ingen ny datakälla — samma spotpriser och profilvikter som redan används. Spotpriserna är timdata (eller medelvärde av 15-min till timme). Varje rad kopplas till profilvikten:

```python
if "hourly" in granularities:
    hourly.append({
        "date": date_str,
        "hour": hour,
        "baseload": price_eur_mwh,
        "capture": price_eur_mwh * weight,
        "weight": weight
    })
```

Gated bakom `if "hourly" in granularities` — dashboard-HTML påverkas inte.

## Filstorlek

Med hourly-data, ~10 profiler, 4 zoner, ~4 år: uppskattningsvis 15-25 MB xlsx. openpyxl `write_only`-läge hanterar detta utan minnesproblem.

## Kodändringar

| Fil | Ändring |
|-----|---------|
| `elpris/dashboard_v2_data.py` | Lägg till `granularities`-parameter + hourly-samling i loopen |
| `elpris/excel_export_v2.py` | Skriv om till datadriven serialisering |
| `generate_dashboard_v2.py` | Anropa Excel-export efter HTML-generering |

**Inget som ändras:**
- Dashboard HTML — samma anrop, samma default-granulariteter
- Alla andra datakällor och scripts
- V1-dashboarden och dess Excel-export
- `update_all.py` — anropar redan `generate_dashboard_v2.py`

## Riskbedömning

- **Låg risk:** Befintlig dashboard-kod får en ny parameter med default som bevarar nuvarande beteende.
- **Ingen ny datakälla:** Allt bygger på samma pipeline.
- **Isolerat:** Excel-exporten är en ny implementation som inte påverkar HTML-generering.
