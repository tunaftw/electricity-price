# Elpris · Analysrum

En första fungerande lokal dashboard för åtta solparker, svenska spotpriser och det befintliga terminsarkivet. Riktiga lokala data; ingen liveanslutning i webbläsaren.

## Starta

Från projektroten `electricity-price`:

```sh
python3 generate_intelligence_dashboard.py
npm --prefix energy_dashboard ci
npm --prefix energy_dashboard run dev -- --host 127.0.0.1
```

Öppna **http://localhost:3000/**. Kräver projektets Python-beroenden och Node 22.13 eller senare. Exporten tar normalt omkring tio sekunder på denna dator. Den ändrar inte källfiler eller tidigare rapporter.

För en lokal produktionsbyggd version:

```sh
npm --prefix energy_dashboard run build
npm --prefix energy_dashboard start -- --ip 127.0.0.1 --port 3000
```

Stoppa en tidigare server på samma port först. Servern är lokal och saknar teaminloggning. Den ska köras bunden till loopback tills en autentiserad driftmiljö är vald. Ingen extern publicering ingår i denna lokala leverans.

## Användning

- **Portföljen:** välj månad och elområde, sortera parkjämförelsen och öppna en park för dag/kvart samt export. Standardmånaden är den senaste med minst fyra kompletta parker och användbar preliminär PR, för närvarande juni 2026. Nyare men bristfälliga månader går alltid att välja.
- **Elmarknaden:** jämför exempelvis 2024 med 2023; växla till dagar eller kvartar för varaktighet och dygnsprofil. Kvartar som kommer från timdata har oförändrat timpris.
- **Terminer:** välj leveranskontrakt och handelsperiod eller två datum för historiska årskurvor. SYS+EPAD kräver båda benen samma datum. YR-23/24 saknas i arkivet; kalenderårens spotpriser finns.
- **Intäkt & PPA:** ett transparent scenario på känd export med dagens PPA-inställningar. Det är inte historiskt avtalsutfall eller avräknad intäkt.
- **Underlaget:** källornas senaste datum, beräkningsregler, fullständigt filmanifest och kontrollsummor.

**Kopiera vy** kopierar URL:ens arbetsyta och filter. Länken fungerar där den lokala appen körs och använder dess aktuella dataset. Den sparar inga kommentarer eller frysta data. CSV-exporterna innehåller urvalets underlag; varaktighetsgrafen samplar punkter men CSV-exporten behåller alla valda kvartar.

## Uppdatera data

Använd projektets befintliga nedladdningsskript när ny källdata behövs. Generera därefter utdraget med `python3 generate_intelligence_dashboard.py`. Utvecklingsservern får nya data efter omladdning; produktionsservern kräver nytt `build` och omstart.

Data skrivs till `public/data/snapshots/<datasetversion>/`, och `public/data/summary.json` pekar atomiskt på den färdiga versionen. Detaljfrågor använder versionens sökväg, vilket gör att en redan öppen analys behåller konsekventa data. Versioner gallras inte automatiskt. Utdragen innehåller intern park- och PPA-data och är Git-ignorerade; de kan återskapas från de lokala källorna. En ren checkout måste därför köra Python-exporten innan frontendens typkontroll eller bygge.

## Struktur

```text
../elpris/intelligence_data.py       Normalisering, beräkningar, versionerad export
../generate_intelligence_dashboard.py CLI
app/Dashboard.tsx                    Navigation och övergripande urval
app/Views.tsx                        Fem arbetsytor och detaljladdning
app/components.tsx                  Gemensamma diagram och kontroller
app/analysis.mjs                     As-of, tidsserier och CSV
app/use-query.ts                     URL som levande analysurval
public/data/                        Genererade interna data, inte källkod
```

Python använder UTC-nycklar och Europe/Stockholm för affärsperioder. Nätleverans baseras på `effective_power_mw`, där giltig nätmätare inklusive noll har företräde, annars ett märkt inverterestimat. Energiförlust kan inte härledas enbart ur saknade mätvärden. PR räknas på samma giltiga energi-/POA-intervall och hålls tillbaka vid låg täckning.

## Verifiering

```sh
python3 -m pytest tests/test_intelligence_data.py -q
npm --prefix energy_dashboard run typecheck
npm --prefix energy_dashboard run lint
npm --prefix energy_dashboard test
npm --prefix energy_dashboard run build
```

Se [arkitekturgranskningen](../docs/plans/2026-09-08-dashboard-architecture.md) för fynd, definitioner, datakällor och målarkitektur. PostgreSQL/API, inloggning, avtalsrevisioner, automatisk uppdatering och batterianalys är fortsatta etapper.
