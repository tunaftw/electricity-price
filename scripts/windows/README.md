# Automatisk datasync på Windows

Electricity Price uppdateras av två lager
(design: `docs/plans/2026-10-02-automatisk-datasync-design.md`):

1. **Windows Schemaläggaren** kör `elpris_sync.ps1`:
   - **Morgon (dagligen 06:30):** `update_all.py` och klar-kontrollen
     (`scripts/datastatus_klar.py`). Om gårdagen inte är komplett hämtar den igen var 30:e minut
     till 11:00. Därefter committar den och pushar datan till `origin/main`.
   - **Kväll (mån–fre 19:15):** `futures_daily.py` och `generate_oversikt.py --also-artifact`.
   - **Båda:** sidan granskas i huvudlös Chrome. Ett godkänt bygge lämnas över i
     `Resultat/publicera/klar.json`.
2. **Claude-appens schemalagda uppgift `elpris-publicera`** (07:45, 11:45 och 19:45) publicerar
   `klar.json` till artefakten när kontrollsumman är ny. Uppgiften körs bara när appen är öppen.
   Om appen var stängd körs den vid nästa start.

## Kommandon

Registrera eller uppdatera de två uppgifterna (under `\Elpris\` i Schemaläggaren):

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/registrera.ps1
```

Ta bort dem:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/registrera.ps1 -Avregistrera
```

Kör nu. Lägg till `-Torrkorning` för att bara se stegen:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/elpris_sync.ps1 -Lage Morgon
```

## Felsökning

- **Loggar:** `Resultat/logs/sync_morgon_YYYYMMDD.log`, `sync_kvall_YYYYMMDD.log` och
  `futures_daily_YYYYMMDD.log`.
- **Ingen `klar.json`:** bygget eller granskningen misslyckades. Föregående sida ligger kvar
  publicerad. Felet står på raden `FEL:` i loggen.
- **`Resultat/publicera/sync.lock`:** en körning pågår. Ett lås som är äldre än 3 timmar ignoreras.
- **Annan Python än `python`:** sätt miljövariabeln `ELPRIS_PYTHON`.
- **Commit:** körningen committar bara ändrade spårade filer, nya `*.csv` och nya
  `nordic_market/futures_*.json` under `Resultat/marknadsdata` och `Resultat/profiler`, och bara
  när repot står på `main`. Andra ändringar rörs inte.
