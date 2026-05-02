# Generera Unified Dashboard

Genererar både Track A (Bloomberg-dark) och Track C (Nordic Editorial)
dashboards till `Resultat/rapporter/`.

## Instruktioner

Kör `python3 generate_unified_dashboard.py`

### Flaggor

- `--track A` — bara Track A (Bloomberg-dark, vidareutveckling av v2)
- `--track C` — bara Track C (Nordic Editorial, modern design)
- `--track both` — båda spåren (default)

## Output

`Resultat/rapporter/`
- `dashboard_unified_YYYYMMDD.html` (Track A, ~17 MB)
- `dashboard_unified_v3_YYYYMMDD.html` (Track C, ~17 MB)

Båda dashboards är fristående HTML-filer med inbäddad data och Plotly.js
via CDN. De delar samma backend (`elpris.unified_dashboard_data.build_unified_data`)
så CAPTURE/BESS/FUTURES/ASSETS-flikar visar identisk data, men i två
parallella visuella spår.
