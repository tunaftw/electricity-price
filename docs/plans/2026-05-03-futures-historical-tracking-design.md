# Futures historical tracking + Forward-vs-realised split

**Datum:** 2026-05-03
**Status:** Design godkänd, ej påbörjad
**Berör:** FUTURES-fliken på unified dashboard, `dashboard_v2_data.py`, `nasdaq_download.py`, `status.py`

## Bakgrund

FUTURES-fliken har idag ett toppkort "Forward vs realised" som blandar tre serier
i samma graf: SYS baseload, zone-implied (SYS+EPAD), och realised YTD-spot för
levererade kontrakt. Lägre på sidan ligger SYS och EPAD redan separerade i
"EPAD differentials" + "Quarterly forwards" / "Yearly forwards".

Två behov uppstod:

1. **Spegla samma uppdelning i toppkortet** — separera SYS från EPAD så att
   avvikelser mellan implied och realised kan tillskrivas rätt komponent.
2. **Bevara och visualisera historik** för futures vs faktiskt utfall, så att
   man i efterhand kan svara på "vad sa marknaden om Q2-26 SE3 12 månader
   innan leverans, och vad blev utfallet?"

## Befintlig datalagring

`Resultat/marknadsdata/nasdaq/futures/sys_baseload.csv` och
`epad_se{1..4}_*.csv` lagrar redan en daglig tidsserie per kontrakt. `save_to_csv`
i [`elpris/nasdaq.py`](../elpris/nasdaq.py) mergar nya rader på `(date, contract)`,
så historiken bevaras automatiskt så länge `nasdaq_download.py` körs.

Risken är inte radering utan **körningsluckor**. När ett kontrakt går till
leverans tas det bort från Nasdaqs sök-API; befintliga rader ligger kvar men
nya kommer aldrig. Konkret exempel som upptäcktes vid design: Q1-26 har
sista `daily_fix` 2025-03-28, trots att kontraktet borde ha handlats fram till
2025-12-31.

## Designval

### Datamodell — option A (full daglig historik)

Inga nya CSV-filer. Befintliga `daily_fix`-rader är källan. Beräknade fält
läggs till i dashboard-JSON vid bygget:

- `delivery_start` / `delivery_end` parsas ur kontraktssymbol via befintlig
  `_parse_contract_period` i `dashboard_v2_data.py`.
- `final_settlement_date` = senaste `date` i CSV:n för det kontraktet.
- `is_clean_final` = `final_settlement_date >= delivery_start - 7 dagar`.

**Ny output-nyckel `forward_history`** i `load_forward_curve_data` returvärde:

```json
"forward_history": {
  "Q2-26": {
    "delivery_start": "2026-04-01",
    "delivery_end": "2026-06-30",
    "final_settlement_date": "2026-03-31",
    "is_clean_final": true,
    "sys_series": [{"date": "2024-01-02", "price": 34.0}, ...],
    "epad_series": {
      "SE1": [...], "SE2": [...], "SE3": [...], "SE4": [...]
    },
    "realised_spot": {"SE1": 78.5, "SE2": 80.1, "SE3": 86.2, "SE4": 92.3}
  },
  "YR-26": { ... }
}
```

Endast levererade eller pågående kontrakt (de aktiva ligger redan i `contracts`).
Storleksuppskattning: ~600 dagar × 4 EPAD-zoner × 5–10 kontrakt ≈ < 200 KB
tillagt i JSON.

**Ny output-nyckel `forward_health`** med arrayer av kontrakt som har
"stale final" eller är "approaching expiry" — samma data som `status.py`
använder för varningar.

### Visualisering — layout iv (graf + tabell)

#### Topp-kortet splittas (B + a)

`renderForwardChart` ersätts av två renderingar:

1. **"SYS baseload — forward curve"** (nytt övre kort): en serie, ingen
   zone-selector, ingen realised-romb (vi har inget Nord Pool SYS-spotpris).
2. **"Zone forward vs realised"** (gamla kortet, krymper): zone-implied
   (SYS+EPAD) + realised-romb för vald zon. Zone-segmentet kvar.

Befintlig EPAD-bar-chart, "Quarterly forwards" och "Yearly forwards" lämnas
orörda.

#### Två nya kort längst ner på FUTURES-fliken

**Kort A — "Forward convergence"** (Plotly):

- Selectorer: kontrakt-dropdown (levererade + pågående) + zone-segment.
- X = settlement-datum, Y = €/MWh.
- Tre serier:
  - `SYS forward` (mörkgrön linje, full handelshistorik)
  - `<zone> implied` (orange linje, SYS+EPAD per dag — NaN där någon saknas)
  - `Realised <zone>` (lila streckad horisontell linje över delivery-perioden,
    romb-marker vid `delivery_end`)
- Vertikal grå linje vid `delivery_start` med "Delivery starts"-annotation.
- Om `is_clean_final == false`: varningstext i kortets sub-titel.

**Kort B — "Lookback table"** (editorial-tabell):

- En rad per (kontrakt, zone). Default visar levererade kontrakt; "Show pending"
  toggle expanderar.
- Kolumner: `Contract` · `Zone` · `T-12mo` · `T-6mo` · `T-3mo` · `T-1mo` ·
  `Final` · `Realised` · `Error (€/MWh)` · `Error (%)`.
- T-Xmo-värde = zone-implied (SYS+EPAD) på den dag som ligger närmast
  `delivery_start − Xmo` ±7 dagar. "—" om ingen daily_fix inom fönstret.
- Felfärgning: grön (|err| < 5), gul (5–15), röd (>15).
- Sorterbar; default sort = senaste delivery-start först.

### Operationella garantier — minimalism

Två tillägg i [`status.py`](../status.py):

1. **Pre-expiry varning.** För varje aktivt kontrakt där
   `delivery_start − today() ≤ 14 dagar` OCH senaste fix > 7 dagar gammal:
   skriv ut röd ANSI-varning med körningsförslag.
2. **Post-expiry retroaktiv granskning.** För varje kontrakt där
   `final_settlement_date < delivery_start − 7 dagar`: skriv ut diagnostisk
   varning. Kan inte återskapa data men flaggar för analyser.

**Ingen ny cron / push-notis.** `update_all.py` kör redan `nasdaq_download`;
chronic missade körningar är ett operativt problem som inte löses robust i kod.

### Q1-26-luckan

Innan shipping testas om Nasdaqs `instruments/{orderbookId}/price-history`
returnerar data för delistade kontrakt via gammalt orderbook-ID. Om ja: ny
flagga `nasdaq_download.py --backfill-expired` som re-söker via cachade ID:n.
Om nej: luckan accepteras och flaggas som "data missing" i lookback-tabellen.

## Filer som påverkas

- `elpris/dashboard_v2_data.py` — utökar `load_forward_curve_data` med
  `_load_full_history`-hjälpare, `forward_history`- och `forward_health`-utdata.
- `elpris/unified_dashboard_v3_html.py` — splittar `renderForwardChart`,
  lägger till `renderSysForwardChart`, `renderZoneForwardVsRealisedChart`,
  `renderConvergenceChart`, `renderLookbackTable`. State-utökning:
  `FUTURES_STATE.convergenceContract`.
- `status.py` — två nya checkar.
- `elpris/nasdaq.py` — `discover_and_download` accepterar
  `include_delisted=False` parameter (default oförändrat beteende).
- `nasdaq_download.py` — ny `--backfill-expired` flagga (experimentell).

## Leveransordning (separata commits)

1. **Topp-graf-split (B + a).** Ren refactor, ingen ny data. Verifiera
   identisk rendering för aktiva kontrakt.
2. **Datalager.** `forward_history` + `forward_health` i JSON. Renderar inget;
   verifiera JSON-storleksökning < 200 KB.
3. **Konvergens-graf + lookback-tabell.** Den nya användarsynliga delen.
4. **status.py-varningar.**
5. **Q1-26 backfill-experiment.** Oberoende; om det ger data → backfill kör
   en gång, annars rivs flaggan.

## Test-strategi

Pytest-täckningen är begränsad. Verifieras manuellt genom att köra
`python3 generate_unified_dashboard.py` efter varje steg och inspektera
HTML-output. Inga nya pytest-tester om vi inte hittar regression-prone
hjälpfunktioner värda att skydda.

## Avgränsning

- Ingen Nord Pool SYS-spotnedladdning (skippad pga ingen befintlig källa
  utan kundavtal).
- Ingen forward-error spaghetti-graf (option iii i diskussionen) — för få
  levererade kontrakt idag för att den ska bli meningsfull. Kan adderas
  senare när 8+ kontrakt finns.
- Ingen push-notis-infrastruktur.
