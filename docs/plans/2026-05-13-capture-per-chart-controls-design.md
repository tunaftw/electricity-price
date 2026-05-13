# Capture-fliken: per-graf kontroller

**Datum:** 2026-05-13
**Status:** Design godkänd, ej påbörjad
**Berör:** Capture-fliken på unified dashboard, `elpris/unified_dashboard_v3_html.py`

## Bakgrund

Capture-fliken har idag tre globala kontrollgrupper:

- **Zone** (SE1/SE2/SE3/SE4) — i sidhuvudet
- **Period** (yearly/monthly/daily) — i sidhuvudet
- **Range** (All/5Y/2Y/1Y/6M + prev/next/Latest) — i en `range-bar` mellan
  Profiles-kortet och graferna

Plus ett separat **Profiles-kort** med teknik-toggles (Sol Syd, Sol Öst-Väst,
Sol Track, Vind, Baseload). De globala kontrollerna styr alla tre graferna
samtidigt: Price evolution, Capture spread, Hour × month heatmap.

Problem: när användaren scrollar genom sidan tappar man kontexten — det är
lätt att glömma vilken zon, period och range som är aktiv när man bara ser
graferna. Kontrollerna sitter "utanför" graferna istället för i samma
visuella block.

## Designval

### State-modell — oberoende per graf

Varje graf har eget state. Att klicka på SE4 i Price evolution-kortet ändrar
*bara* Price evolution-grafen. Spread-kortet och heatmapen behåller sina
egna val. Detta är ett medvetet val över alternativen "synkade (delat
state)" och "synkade + sticky global bar" — det ger maximal flexibilitet
för sida-vid-sida-jämförelse (t.ex. SE3 monthly bredvid SE4 yearly).

Initial state är identisk med dagens default på alla tre graferna:

```js
captureState = {
  main:    { zone:'SE3', period:'monthly', range:'6m', windowIdx:0,
             profiles:['solar_south','wind'] },
  spread:  { zone:'SE3', period:'monthly', range:'6m', windowIdx:0,
             profiles:['solar_south','wind'] },
  heatmap: { zone:'SE3' }
};
```

Det första intrycket av sidan är därmed identiskt med dagens — bara
kontrollerna har flyttat plats.

### Kontroller per graf — vilka och var

| Graf            | Zone | Period | Range | Profiles |
|-----------------|------|--------|-------|----------|
| Price evolution | ✓    | ✓      | ✓     | ✓        |
| Capture spread  | ✓    | ✓      | ✓     | ✓        |
| Hour × month    | ✓    | –      | –     | –        |

Heatmapen behåller sin nuvarande "all-time, hour × month"-karaktär. Period
och Range gäller inte (cellerna är redan timme × månad-aggregat). Profiles
finns inte i heatmapen idag och läggs inte till.

### Visuell layout

Page-head skalas ner till bara `eyebrow + title + subtitle`. Globala
`page-controls`, fristående Profiles-kort och `range-bar` tas bort helt.

Korten ligger fortfarande i `grid-2` (Price evolution till vänster, Capture
spread till höger). Heatmapen ligger som idag i egen rad under.

Inuti varje main/spread-kort:

```
┌─ CARD ─────────────────────────────────────────┐
│ Price evolution                  [Profiles ▾] │  card-head
│ Baseload & capture, EUR/MWh                    │
│ ───────────────────────────────────────────── │
│ ZONE    SE1 SE2 [SE3] SE4                      │  ny chart-controls
│ PERIOD  yearly [monthly] daily        ‹ › ⟳   │  3 rader segmented chips
│ RANGE   All 5Y 2Y 1Y [6M]                     │  + range-nav höger
│ ───────────────────────────────────────────── │
│ [Plotly chart]                                 │
└────────────────────────────────────────────────┘
```

Heatmap-kortet får bara en `ZONE`-rad under card-head.

**Profiles-popover.** En knapp uppe till höger i card-head visar valda
profiler komprimerat (t.ex. `Sol Syd, Vind +1 ▾`). Klick öppnar en
absolutpositionerad panel med samma teknik-toggles som dagens
Profiles-kort, inklusive färgprickar. Popovern stängs på klick utanför
eller `Escape`. För spread-kortet (det högra i grid-2) öppnas popovern
mot vänster för att inte klippas av sidkanten.

### Plotly-rendering

Idag finns en `renderCapture()` som drar global state och ritar alla tre
graferna. Den splittras i tre rena render-funktioner:

```js
renderCaptureMain(state)
renderCaptureSpread(state)
renderCaptureHeatmap(state)
```

`Plotly.react()` används istället för `Plotly.newPlot()` så att zoom och
tooltip-positioner inte återställs vid varje liten kontrolländring. Detta
verifieras mot dagens implementation och uppgraderas vid behov.

En `wireCaptureCard(chartId, stateRef, renderFn)` binder klick på chips,
range-nav och profiles-popover och kallar respektive render-funktion.

### Implementation — fil och struktur

All ändring sker i `elpris/unified_dashboard_v3_html.py`:

- HTML-mallen för Capture-sektionen byggs om. En återanvändbar Python-funktion
  `_capture_chart_card(chart_id, title, sub, controls={'zone','period','range','profiles'})`
  genererar kort-strukturen tre gånger med rätt IDs:

  ```
  capture-{chart}-zones
  capture-{chart}-period
  capture-{chart}-range
  capture-{chart}-range-nav
  capture-{chart}-profiles-btn
  capture-{chart}-profiles-pop
  capture-{chart}-chart
  ```

  För heatmapen utelämnas alla utom `zones` och `chart`.

- Gamla IDs `capture-zones`, `capture-period`, `capture-range`,
  `capture-range-bar`, `capture-profiles` tas bort. Sökning på de IDs:erna
  i `unified_dashboard_v3_html.py` ska efter ändringen ge noll träffar.

- CSS: ny `.chart-controls`-blockklass för kontrollraderna. Existerande
  `.seg`-klass (segmented buttons) återanvänds. Ny `.profiles-popover`-klass
  för popoverns container.

- JS: state-objekt + render-funktioner + wire-funktion enligt ovan. Inget
  beroende mellan korten.

`elpris/unified_dashboard_data.py` rörs inte — den serverar redan data per
zon/period, vi konsumerar bara på fler ställen.

### URL-hash sync — skippas i v1

Att kunna dela en länk med specifik per-graf-state via URL-hash är "nice
to have" men inte nödvändigt för v1. Behovet är mest för rapporter och
delning, vilket inte är primärt på Capture-fliken. Kan läggas till i v2 med
schema `#capture?main=SE4.yearly.2y.0.solar_south,solar_track&spread=...`
om det visar sig efterfrågat.

## Risker

- **Plotly-prestanda.** Snabba klick triggar `Plotly.react()` per kort. Mitigering:
  bara ett kort ritas om per klick (oberoende state); det är bättre än dagens
  beteende där en zone-ändring renderar alla tre.

- **Popover-klippning.** Spread-kortets popover öppnas mot vänster för att
  inte klippas av sidkanten.

- **State-divergens upplevs som inkonsekvent.** En eyeball-skanning visar
  potentiellt olika zoner i olika kort. Det är avsiktligt — kortets state
  visas tydligt i kontrollraden under card-head, så användaren ser alltid
  vad respektive graf representerar.

- **CSS-spillover.** `.seg`-klassen används även i BESS/FUTURES/ASSETS. Den
  rörs inte; nya klasser är prefixade och lokala till Capture.

## Acceptanskriterier

1. Page-head på Capture-fliken har bara title + subtitle, inga kontroller.
2. Fristående Profiles-kort och fristående range-bar är borta.
3. Main + spread-kort har var sin Zone + Period + Range + range-nav +
   profiles-popover. Heatmap-kortet har bara Zone.
4. Klick på SE4 i main-kortet ändrar bara main-grafen. Spread + heatmap
   behåller sitt state.
5. Profiles-popover öppnas/stängs på klick + Escape och uppdaterar bara
   sitt kort.
6. Defaults vid första rendering är identiska med dagens dashboard
   (SE3, monthly, 6M, profiles=Sol Syd+Vind).
7. `python3 generate_unified_dashboard.py` kör utan Python-fel.
8. Ingen JS-konsolfel i preview-servern. Alla kombinationer av Zone × Period
   × Range × profiles kan klickas igenom på alla tre korten utan att grafer
   "fryser" eller går sönder.

## Out of scope

- URL-hash sync (v2).
- Heatmap-Period/Range.
- BESS-, FUTURES-, ASSETS-flikarna — bara Capture berörs.
- "Synka alla grafer"-knapp / pin-mellan-kort.
