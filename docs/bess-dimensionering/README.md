# BESS-dimensionering

Dokumentation för batteridimensionering (Battery Energy Storage System) i kombination med solkraft.

## Innehåll

| Dokument | Beskrivning |
|----------|-------------|
| [01-prognosfelkompensation.md](01-prognosfelkompensation.md) | Dimensionering av batteri för att kompensera prognosfel i PV-produktion |
| [02-ac-toppkapning.md](02-ac-toppkapning.md) | Dimensionering av batteri för AC-toppkapning vid reducerad växelriktarkapacitet |

## Relaterade moduler

- `elpris/battery_sizing.py` - Dimensioneringsberäkningar
- `elpris/forecast_error.py` - Prognosfelmodellering
- `elpris/imbalance_cost.py` - Obalansanalys

## CLI-verktyg

```bash
# Dimensionera batteri för prognosfelkompensation
python3 battery_sizing_cli.py --profile south_lundby --capacity 1.0 --mape 0.05 --simulate

# Lista tillgängliga solprofiler
python3 battery_sizing_cli.py --list-profiles
```
