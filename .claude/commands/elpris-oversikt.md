# Generera Översikt (portföljen och elmarknaden på en sida)

Genererar Översikt till `Resultat/rapporter/`: portföljens produktion mot
budget, elmarknaden (spotpris och solens capture rate, SE1–SE4 + DK1/DK2),
terminer (SYS + EPAD för SE3/SE4) och batteri-arbitrage.

## Instruktioner

Kör `python3 generate_oversikt.py` (cirka 10–15 s).

Vid iteration på renderaren: spara datat en gång och rendera om på sekunder:

```bash
python3 generate_oversikt.py --save-data /tmp/oversikt.json
python3 generate_oversikt.py --from-data /tmp/oversikt.json
```

Verifiera i webbläsare (http.server + Playwright/Browser, inte file://).

## Output

`Resultat/rapporter/oversikt_YYYYMMDD.html` (~5,4 MB, Plotly inbäddat — inga externa
skript, fungerar offline och i förhandsvisningar).
Fem delar: **Portföljen** (månadsväljare, parktabell med dagremsor för
datatäckning, parkdetalj vid klick), **Elmarknaden**, **Terminer**,
**Batteri**, **Datastatus** (kända problem + definitioner).

Backend: `elpris/oversikt/` — `build.build_oversikt_data()` sätter ihop
`portfolj`, `marknad`, `terminer`, `batteri` och `datastatus`.
Renderare: `elpris.oversikt.render.render_oversikt`.

## Design

`docs/plans/2026-09-22-oversikt-design.md` — principer, definitioner och
vad som medvetet utelämnats.
