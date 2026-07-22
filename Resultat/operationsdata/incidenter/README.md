# Incidenter & work orders (manuell data)

Sektion 17 i månadsrapporten ("Incidents & Work Orders") läser en JSON-fil
per park och månad från denna katalog. Filerna fylls i **manuellt** av
O&M/asset-teamet — det finns ingen automatisk källa (t.ex. QBO/ServiceNow)
kopplad ännu.

## Namnkonvention

```
{park_key}_{YYYY-MM}.json
```

Exempel: `horby_2026-06.json` för Hörby, juni 2026. `park_key` är samma
nyckel som i `elpris/config.py` (`PARK_ZONES`), t.ex. `horby`, `hova`,
`fjallskar`.

## Format

Se `_template.json` i denna katalog för ett komplett exempel. Toppnivå har
två valfria listor, `incidents` och `work_carried_out`. Alla fält utom
`date` är valfria — saknade fält renderas som "—" i rapporten.

Om filen för en park/månad saknas, eller är trasig JSON, visar rapporten
en platshållare istället för att krascha.

Filnamnet `_template.json` (understreck-prefix) matchar inte
`{park_key}_{YYYY-MM}`-mönstret och laddas därför aldrig som verklig data.
