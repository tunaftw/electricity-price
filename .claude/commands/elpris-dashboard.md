# Generera Unified Dashboard

Genererar Track C (Nordic Editorial) — den valda primära dashboarden — till
`Resultat/rapporter/`.

## Instruktioner

Kör `python3 generate_unified_dashboard.py`

### Flaggor

- `--track C` — Track C (Nordic Editorial, **default**)
- `--track A` — Track A (Bloomberg-dark, **deprecated** sedan 2026-05)
- `--track both` — båda spåren (för jämförelse)

## Output

`Resultat/rapporter/`
- `dashboard_unified_v3_YYYYMMDD.html` (Track C, ~17 MB) — primär
- `dashboard_unified_YYYYMMDD.html` (Track A, ~17 MB) — bara om `--track A` eller `both`

Dashboards är fristående HTML-filer med inbäddad data och Plotly.js via CDN.
Båda spår delar samma backend (`elpris.unified_dashboard_data.build_unified_data`).

## Status

**Track C valt som primär** efter A/B-jämförelse 2026-05. Track A behålls
i kodbasen för bakåtkompatibilitet och kan tas bort efter ytterligare
iteration på Track C.
