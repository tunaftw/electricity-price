# Generera Rework-dashboarden (Nordic Clarity)

Genererar portfölj- & marknadsrapporten (Fable-reworken) till
`Resultat/rapporter/`. Byggd parallellt med Track C — ersätter den inte.

## Instruktioner

Kör `python3 generate_rework_dashboard.py`

Vid iteration på renderaren: spara datat en gång och rendera om på sekunder:

```bash
python3 generate_rework_dashboard.py --save-data /tmp/rework_data.json
python3 generate_rework_dashboard.py --from-data /tmp/rework_data.json
```

## Output

`Resultat/rapporter/dashboard_rework_YYYYMMDD.html` (~0,5 MB).

Self-contained HTML (Plotly via CDN, inbäddad JSON). Sex sektioner i
rapport-läsordning med klartext-insikter: **Översikt**, **Marknaden**,
**Capture & cannibalisering**, **Parkerna**, **Risk & intäkt**,
**Datakvalitet**.

Backend: `elpris.rework_dashboard_data.build_rework_data` (komponerar
`build_unified_data()` + rework-analyserna och beskär payloaden).
Renderare: `elpris.rework_dashboard_html.render_rework`.

## Design

Se `docs/plans/2026-06-09-fable-rework-design.md` för vald struktur,
insikter och avgränsningar.
