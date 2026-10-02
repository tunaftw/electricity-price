# Automatisk datasync och publicering av Electricity Price – design

Datum: 2026-10-02 · Status: godkänd av Pontus

## Mål

Electricity Price ska uppdateras när datan finns, utan handpåläggning: gårdagens
marknads- och parkdata på morgonen och terminernas avräkningar på vardagskvällen.
Sidan visar som i dag data t.o.m. igår (ingen morgondagsvy). Inga beräkningar ändras.

## Arkitektur: två lager och en överlämningsfil

### Lager 1 – Windows Schemaläggaren (hämtar, bygger, granskar, committar)

`scripts/windows/elpris_sync.ps1 -Lage Morgon|Kvall` registreras som två uppgifter:

| Uppgift | Tid | Gör |
|---|---|---|
| Elpris morgon | dagligen 06:30 | `update_all.py --quiet --auto-reports`, klar-kontroll, omförsök var 30:e min till 11:00, granskning, commit + push |
| Elpris kväll | mån–fre 19:15 | `futures_daily.py`, `generate_oversikt.py --also-artifact`, granskning |

Uppgifterna körs i efterhand om datorn var avstängd (StartWhenAvailable) och får väcka datorn.
En låsfil (`Resultat/publicera/sync.lock`) hindrar att två körningar överlappar.

**Klar-kontroll** – `scripts/datastatus_klar.py` skriver JSON och sätter exitkod 0/1:

| Källa | Komplett när |
|---|---|
| Spotpriser SE1–SE4 | igår finns |
| ENTSO-E (sol, vind), eSett, Mimer mFRR | igår har alla kvartar |
| Bazefield | igår finns för alla parker |
| Temperatur | högst 7 dagar gammal (ERA5 släpar) |
| Terminer (`--terminer`, kvällen) | senaste SYS-avräkningen är den förväntade |

Är något ofullständigt kl 11:00 byggs sidan ändå med det som finns och `klar.json` får en
varning, så att en sen källa inte håller hela sidan kvar på förrgår.

**Granskning** – `node scripts/granska_sidan.mjs` på den byggda sidan (huvudlös Chrome).
Konsolfel eller saknat datum stoppar överlämningen.

**Överlämningsfil** – `Resultat/publicera/klar.json` skrivs bara efter lyckat bygge och
lyckad granskning: sökväg till `_artifact.html`, `data_tom` (datum), SHA-256, storlek,
`lage`, `varningar[]`, `skapad`. Misslyckas något skrivs ingen fil och föregående sida
ligger kvar publicerad. Logg: `Resultat/logs/sync_<lage>_YYYYMMDD.log`.

**Git** – efter morgonkörningen: commit `data: sync electricity markets and solar parks
through <datum>` med bara `Resultat/marknadsdata` och `Resultat/profiler`, sedan push till
`origin main`. Har användaren egna oincheckade ändringar utanför de sökvägarna stagas de
inte; står repot inte på `main` hoppas commiten över och det loggas.

### Lager 2 – Claude-appens schemalagda uppgift `elpris-publicera`

Körs 07:30, 11:30 och 19:45. Läser `klar.json`; är SHA-256 samma som i
`Resultat/publicera/senast_publicerad.json` avslutas den direkt. Annars publiceras
`_artifact.html` till https://claude.ai/artifact/WNYnDJsiK6D75AhUPdfWUT med `url` och utan
`capabilities` (db, user och downloads behålls). Den publicerade sidan läses tillbaka och
datum och storlek kontrolleras innan `senast_publicerad.json` skrivs. Notis bara vid fel
eller varning. Om appen är stängd körs uppgiften vid nästa start; datan hämtas ändå.

## Följdändringar

- Energinet-steget (`elpris/nordic_market_data.py`) skriver över en fil i stället för en
  ny fil per körningsdag, så att git inte växer med en fil per dag.
- Kortet på Primora Verktyg ändras en gång till "Uppdateras dagligen".
- `CLAUDE.md` (Daglig automation), `scripts/windows/README.md` och vaulten uppdateras.

## Provkörning

1. `elpris_sync.ps1 -Lage Morgon -Torrkorning` – visar vad som skulle göras.
2. Skarp morgonkörning, kontrollera logg, `klar.json` och commit.
3. "Kör nu" på Claude-uppgiften (godkänn publiceringen första gången).
4. Läs tillbaka den publicerade sidan: data t.o.m. igår.

## Utanför omfånget

Morgondagens day-ahead, molnkörning, publicering av Sites-versionen, månadsrapporterna
utöver det `--auto-reports` redan gör.
