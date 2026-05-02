# Generera per-park månadsrapport

Genererar 19-sektioners HTML-rapport per solpark för senaste fullständiga
månad (eller specifik månad).

## Instruktioner

Kör `python3 generate_performance_report.py --all`

### Flaggor

- `--all` — Alla 8 parker (default beteende när inget annat anges)
- `--park <key>` — Bara en park (t.ex. `horby`, `fjallskar`, `agerum`,
  `hova`, `bjorke`, `skakelbacken`, `stenstorp`, `tangen`)
- `--month YYYY-MM` — Specifik månad (default: senaste fullständiga månad)

## Output

`Resultat/rapporter/performance_<park>_<zone>_YYYY-MM.html` — en fil per park.

Innehåller bl.a. KPI-sammanfattning, YTD, daglig produktion, PR, PI,
förlustanalys (waterfall), bästa/sämsta dagar, samt platshållare för
inverter/alarm-data (kräver SCADA-integration).

## Krav

PR, PI, instrålning och förlustanalys kräver utökat Bazefield-format
(POA-instrålning, availability, active power). Kör vid behov först:
`python3 bazefield_download.py --backfill`

## Via update_all.py

För att även generera dessa rapporter som en del av master-pipeline:
`python3 update_all.py --reports` (eller `--reports --month YYYY-MM`).
