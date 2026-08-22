# Produktspec: "Insikt" — en produkt, slutsats först

**Datum:** 2026-08-22
**Status:** Styrande spec för ombyggnaden (godkänd riktning av Pontus 2026-08-22)

## Varför

Repot har idag tre halvfärdiga presentationsprodukter (unified dashboard, rework-dashboard,
per-park månadsrapport) som överlappar. Ingen är "grym". Beslut: **en ny produkt byggs
funktion för funktion ovanpå befintlig datapipeline**, och gamla ytor rivs i takt med att
de ersätts. Datapipelinen (nedladdare, CSV-lager, `update_all.py`) behålls orörd.

## Designprincip (domaren vid scope-frågor)

> **Varje vy leder med en slutsats i klartext. Grafen under är beviset.**

Användaren ska aldrig behöva dra analysen själv. Om en sektion inte kan formulera sin
slutsats i en mening är den inte klar. Insikter genereras per park och per fråga, inte
bara på portföljnivå. Hårdkodade zoner/parker i insiktslogik är förbjudet.

## Målgrupper

1. **Teamet** (veckovis + daglig puls) — driftbeslut, marknadsförståelse, kunskapshöjning.
2. **Investerare** (månads-/kvartalsvis) — kurerad delmängd, exporterbar.

## De fem frågorna produkten svarar på (= byggordning)

| # | Fråga | Feature |
|---|-------|---------|
| 0 | (förutsättning) Går siffrorna att lita på? | PVsyst-månadsbudget, temperaturdata, uppdelad förlustkaskad |
| 1 | Hur går parkerna? | Parköversikt: league table + parkkort med klartextinsikt |
| 2 | Hände något igår? | Daglig puls: avvikelsedetektion + digest |
| 3 | Vad tjänar vi, och varför? | Intäkt & marknad: capture, PPA vs spot, obalanskostnad, kannibaliseringskoefficient |
| 4 | Ska vi investera? | BESS/capex: revenue stacking, verkliga parkprofiler, cykelkostnad, IRR |
| 5 | Vad visar vi investerare? | Kurerad export av 1+3 (+4 vid behov) |

Futures-historikräddningen (design 2026-05-03) körs direkt oavsett ordning — data
försvinner oåterkalleligt ur Nasdaqs API vid leverans.

## Definition av "grym" (gate innan nästa feature påbörjas)

1. Siffrorna är validerade mot källdata (dokumenterad kontroll, inte "ser rimligt ut").
2. Slutsatsen genereras i klartext utan att användaren räknar själv.
3. Verifierad i browser (http.server + Playwright — inte grep).
4. Teamet har använt den ≥2 veckor och feedback är inarbetad.

Punkt 1–3 kan Claude verifiera; punkt 4 är Pontus/teamets gate.

## Teknisk placering

- Nytt namespace: `elpris/insikt/` (dataloaders + insiktsgeneratorer + renderare).
- Generator: `generate_insikt.py` → `Resultat/rapporter/insikt_YYYYMMDD.html`.
- Daglig puls: `Resultat/rapporter/puls/puls_YYYY-MM-DD.html` (+ terminal-sammanfattning).
- Återanvänd loaders från `elpris/` fritt; kopiera inte data-logik, importera den.
- Designspråk: bygger vidare på Nordic Clarity (rework), inte en tredje identitet.

## Rivningsprincip

När en insikt-sektion når "grym": ta bort det den ersätter (flik, rapportsektion,
Excel-export). Rivning är en del av featuren, inte ett senare städprojekt.

## Utanför scope (tills vidare)

- ML-prognoser, realtidsdata, Nord Pool intraday, hosted auth-version
  (hosted är fortsatt mål men blockeras inte av denna ombyggnad).
