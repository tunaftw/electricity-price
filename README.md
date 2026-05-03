# Elpris

Svensk elpris-, regleringspris- och solparksanalys. Hämtar data från flera
APIer (elprisetjustnu, ENTSO-E, eSett, Mimer, Nasdaq, Bazefield,
Energimyndigheten), bearbetar till 15-min upplösning, beräknar capture prices
och bygger Track C unified dashboard + per-park månadsrapporter.

## Snabbstart

```bash
# Engångsuppsättning: skapa .env med API-nycklar
cat > .env <<'EOF'
ENTSOE_TOKEN=...
BAZEFIELD_API_KEY=...
EOF

# Installera beroenden
pip install requests tenacity openpyxl

# Kör hela pipelinen
python3 update_all.py
```

Resultatet sparas i `Resultat/rapporter/`:
- `dashboard_unified_v3_YYYYMMDD.html` — unified dashboard (Track C)
- `capture_prices_YYYYMMDD.xlsx` — capture price-rapport
- `battery_arbitrage_YYYYMMDD.xlsx` — BESS arbitrage-analys
- `performance_<park>_<zone>_YYYY-MM.html` — per-park månadsrapport (med `--reports`)

## Dokumentation

Se [`CLAUDE.md`](CLAUDE.md) för full systemöversikt: arkitektur, datakällor,
slash commands, dataformat och konventioner.

## Slash commands

I Claude Code finns 14 projekt-specifika slash commands i `.claude/commands/`.
`/elpris-update-all` är master-pipelinen och rekommenderas för rutinkörningar.
Se CLAUDE.md för full lista.
