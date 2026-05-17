# Visa Unified Dashboard i Claude Code preview-rutan

Kopierar senaste genererade unified dashboard till `/private/tmp/dashboard.html`
och startar `rapporter-server` (definierad i `.claude/launch.json`) så den
visas direkt i Claude Code:s preview-ruta — inget tabbande mellan webbläsare.

## Instruktioner

1. Hitta senaste `dashboard_unified_v3_*.html` i `Resultat/rapporter/`:
   ```bash
   ls -t Resultat/rapporter/dashboard_unified_v3_*.html | head -1
   ```
2. Kopiera den till `/private/tmp/dashboard.html`:
   ```bash
   cp "$(ls -t Resultat/rapporter/dashboard_unified_v3_*.html | head -1)" /private/tmp/dashboard.html
   ```
3. Starta servern via `mcp__Claude_Preview__preview_start` med name `rapporter-server`.
4. Navigera preview till `/dashboard.html` via `mcp__Claude_Preview__preview_eval`
   med expression `window.location.href = '/dashboard.html'`.
5. Ta en screenshot för att bekräfta att det funkar.

## Bakgrund

Claude.app:s macOS-sandbox blockerar python-processer från att läsa
projektkatalogen, men `/private/tmp/` är tillåtet. Workflowet ovan kringgår
det genom att kopiera den fristående HTML-filen dit servern kan läsa den.

Om dashboarden inte finns ännu, generera den först med `/elpris-dashboard`
(eller `python3 generate_unified_dashboard.py`).
