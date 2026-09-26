# Generera Electricity Price (huvudversionen, byggd på Översikt)

Genererar Electricity Price till `Resultat/rapporter/`: portföljens produktion mot
budget med en vy per park, elmarknaden (spotpris, solens capture rate, heatmap timme ×
månad och capture per panelutformning), terminer (SE3/SE4 och alla sex nordiska zoner),
batteri (arbitrage-tak och stödtjänster) och datastatus. Gränssnittet är på engelska
i Primoras profil.

## Instruktioner

Kör `python3 generate_oversikt.py` (cirka 80 s; tilläggen från Track C tar 30–60 s).
Lägg till `--also-artifact` för att samtidigt skriva artefaktversionen.

Vid iteration på renderaren: spara datan en gång och rendera om på under en sekund:

```bash
python3 generate_oversikt.py --save-data /tmp/ep.json
python3 generate_oversikt.py --from-data /tmp/ep.json
```

Kontrollera att talen är oförändrade: `python3 scripts/jamfor_facit.py facit.json ny.json`.
Granska i huvudlös Chrome (bredder, teman, konsolfel och sidledsrullning):
`node scripts/granska_sidan.mjs http://localhost:PORT/electricity_price_YYYYMMDD.html utkatalog`.

## Output

`Resultat/rapporter/electricity_price_YYYYMMDD.html` (cirka 2,6 MB: Plotly-delpaketet,
typsnitt och ikoner är inbäddade, så sidan fungerar offline och som mejlbilaga) och
med `--also-artifact` även `electricity_price_YYYYMMDD_artifact.html`.

Backend: `elpris/oversikt/`. Renderare: `elpris.oversikt.render`.

## Design

`docs/plans/2026-09-22-oversikt-design.md` och vaultens
`Projects/electricity-prices/01-produktversion.md`.
