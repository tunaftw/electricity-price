# Automatisk datasync och publicering – implementationsplan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Electricity Price hämtas, byggs, granskas, committas och publiceras utan handpåläggning
(design: `2026-10-02-automatisk-datasync-design.md`).

**Architecture:** Windows Schemaläggaren kör `scripts/windows/elpris_sync.ps1` morgon och kväll.
Skriptet använder `scripts/datastatus_klar.py` för att avgöra om gårdagen är komplett, granskar
sidan med `scripts/granska_sidan.mjs` och lämnar över via `Resultat/publicera/klar.json`.
En schemalagd uppgift i Claude-appen publicerar artefakten när kontrollsumman är ny.

**Tech Stack:** Python 3.13 (pytest), PowerShell 5.1, Windows Task Scheduler (ScheduledTasks-modulen),
Node 22 + Chrome (granskning), Claude-appens scheduled tasks.

---

### Task 1: Energinet-cachen växer inte längre

Energinet-steget sparar en ny fil (cirka 29 MB) per körningsdag: `DayAheadPrices_2025-10-01_<idag>.json`
och `ProductionConsumptionSettlement_2024-01-01_<idag>.json`. Laddarna globbar alla filer och
expanderar dem i ordning, så den nyaste filen räcker.

**Files:** Modify `elpris/nordic_market_data.py` (`fetch_energinet`), `.gitignore`.
Test `tests/test_nordic_market_data.py`.

1. Test: `fetch_energinet` med monkeypatchad `requests.get` och en `tmp_path` som innehåller en äldre
   `DayAheadPrices_2025-10-01_2026-09-30.json`. Efter anropet med `end='2026-10-02'` finns bara
   den nya filen kvar. En fil med annat start (`Elspotprices_…`) rörs inte.
2. Kör testet och se att det fallerar.
3. Implementera: efter `_save(path, …)` tas `cache.glob(f'{dataset}_{start}_*.json')` bort utom `path`.
4. Kör testet och se att det passerar. Kör sedan hela `tests/test_nordic_market_data.py`.
5. Lägg till `DayAheadPrices_*.json` och `ProductionConsumptionSettlement*.json` under
   `Resultat/marknadsdata/nordic_market/` i `.gitignore` och kör `git rm --cached` på de spårade
   filerna. Filerna hämtas om vid varje körning.
6. Commit.

### Task 2: Klar-kontroll `scripts/datastatus_klar.py`

**Files:** Create `scripts/datastatus_klar.py`. Test `tests/test_datastatus_klar.py`.

Regel `tacker_dagen(senaste, dag)`: en tidsstämpel med tidszon konverteras till Stockholm, en naiv
tas som den är. Dagen räknas som täckt om datumet är senare än `dag`, eller om datumet är `dag`
och klockan är 23 eller senare.

Källor och hur senaste värde hämtas:

| Källa | Funktion |
|---|---|
| Spot SE1–SE4 | `storage.get_latest_timestamp` |
| ENTSO-E sol och vind SE1–SE4 | `entsoe.get_latest_timestamp` |
| eSett SE1–SE4 | `esett.get_latest_timestamp` |
| Mimer fcr och mfrr_cm | `mimer.get_latest_timestamp` |
| Bazefield, alla parker | `bazefield.get_latest_synced_date` ≥ igår |
| Temperatur, alla parker | `temperature.get_latest_stored_date` ≥ idag − 7 |

Utdata: JSON på stdout `{"dag": …, "komplett": bool, "saknas": ["eSett SE3 (senast 2026-10-01 01:30)", …]}`.
Exitkod 0 om allt är komplett, annars 1. `--idag` används i tester.

1. Tester för `tacker_dagen`: aware UTC 21:45 på en sommardag ger komplett, UTC 23:45 dagen före
   ger inte komplett, naiv 23:00 ger komplett och `None` ger inte komplett. Testa också
   `kontrollera(idag, hamtare)` med injicerade hämtare.
2. Fail, implementera, pass.
3. Kör skarpt: `python scripts/datastatus_klar.py`. Före dagens synk ska den rapportera saknade källor.
4. Commit.

### Task 3: Synkskriptet `scripts/windows/elpris_sync.ps1`

Parametrar: `-Lage Morgon|Kvall`, `-Torrkorning`, `-Sista` (klockslag för sista omförsöket, standard 11:00).

- Låsfil `Resultat/publicera/sync.lock`. Ett lås som är äldre än 3 timmar räknas som dött.
- Logg `Resultat/logs/sync_<lage>_YYYYMMDD.log`.
- **Morgon:** kör `update_all.py --quiet --auto-reports` och sedan `datastatus_klar.py`. Är något
  ofullständigt väntar skriptet 30 minuter och kör om, till `-Sista`. Därefter används sidan som
  steg 11 byggde, men den byggs om efter sista omförsöket om det kom ny data.
- **Kväll:** kör `futures_daily.py` (exitkod ≠ 0 blir en varning) och sedan
  `generate_oversikt.py --also-artifact`.
- **Granskning:** `node scripts/granska_sidan.mjs file:///<sida> <tmp> 1440 light`. Fel blir stopp
  utan `klar.json`.
- **`klar.json`** innehåller `fil`, `sha256`, `storlek`, `data_tom` (från `datastatus_klar`),
  `lage`, `varningar` och `skapad`.
- **Git (bara morgon, och bara om grenen är `main`):** `git add Resultat/marknadsdata Resultat/profiler`,
  commit om något är stagat, sedan `git push origin main`. Pushfel blir en varning.
- **`-Torrkorning`:** skriver ut stegen utan att köra dem.

Verifiera med `-Torrkorning` och därefter en skarp morgonkörning. Commit.

### Task 4: Registrering i Schemaläggaren

**Files:** Create `scripts/windows/registrera.ps1`, `scripts/windows/README.md`.

- **Elpris morgon:** dagligen 06:30.
- **Elpris kväll:** mån–fre 19:15.
- **Inställningar:** `StartWhenAvailable`, `WakeToRun`, `ExecutionTimeLimit` 6 h,
  `MultipleInstances IgnoreNew`. Körs som inloggad användare.
- `-Avregistrera` tar bort båda.

Verifiera med `Get-ScheduledTask -TaskPath \Elpris\`. Commit.

### Task 5: Claude-uppgiften `elpris-publicera`

Schemalagd uppgift, cron `30 7,11 * * *` och `45 19 * * 1-5` (två uppgifter eller en med listan
`30 7,11 * * *` plus kvällen). Prompten är självbärande: läs `klar.json`, jämför mot
`senast_publicerad.json`, publicera med `url` och utan `capabilities`, läs tillbaka, skriv
`senast_publicerad.json`, notis bara vid fel eller varning. Testkör med "Kör nu".

### Task 6: Dokumentation

- `CLAUDE.md`: avsnittet Daglig automation.
- Vaulten: `Projects/electricity-prices/02-automatisk-sync.md` och en länk i indexnoten.
- Kortet på Primora Verktyg: "Uppdateras dagligen".
- Minnet `electricity-price.md`.
