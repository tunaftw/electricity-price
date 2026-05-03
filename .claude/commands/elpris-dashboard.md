# Generera Unified Dashboard

Genererar Track C (Nordic Editorial) — den primära unified dashboarden — till
`Resultat/rapporter/`.

## Instruktioner

Kör `python3 generate_unified_dashboard.py`

## Output

`Resultat/rapporter/dashboard_unified_v3_YYYYMMDD.html` (~17 MB).

Fristående HTML-fil med inbäddad data och Plotly.js via CDN. 4 flikar:
**CAPTURE**, **BESS**, **FUTURES**, **ASSETS**.

Backend: `elpris.unified_dashboard_data.build_unified_data` aggregerar all data
till JSON. Renderaren `elpris.unified_dashboard_v3_html.render_track_c` bygger
HTML.

## Bakgrund

Track C valdes som primär efter A/B-jämförelse 2026-05. Track A
(Bloomberg-dark) togs bort 2026-05.
