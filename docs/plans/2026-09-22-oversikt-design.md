# Översikt: portföljen och elmarknaden på en sida

Datum: 2026-09-22. Status: första versionen byggd och verifierad i webbläsare.
Den väntar på Pontus granskning. Den ersätter ännu inte Track C på Sites.

## Varför en ny sida

Granskningen 2026-09-22 av Insikt och Track C visade att röran mest kom av
tre saker. Layouten var en mindre del av problemet.

1. **Felaktiga siffror visades som fakta.** Parkladdaren gjorde om fastfrusna
   invertervärden och nattvärden till produktion:
   - Fjällskär, augusti: 413 MWh mellan kl. 23 och 03.
   - Hova, juli: 80 MWh mellan kl. 23 och 03.
   - Fjällskär, september: invertern stod på exakt 7,69 MW i alla kvartar.

   Insikts "augusti −0,1 % mot budget" blev därför rätt av en slump.
2. **Sidorna motsade varandra.** Batterikalkylen gav en internränta (IRR) på
   166 % på den ena sidan och 43 års återbetalningstid på den andra. Capture
   hade tre olika definitioner, alla med samma namn. Förkortningen "IRR"
   betydde både instrålning och internränta.
3. **Fokus och definitioner var otydliga.** SE1 var standardzon. Delmånader
   visades som färdiga resultat. SEK och EUR blandades. Flera analyser gick
   inte att fatta beslut på: en regression på 4 punkter, obalanssimuleringar
   och IRR på perfekt framsyn.

Beslut (Pontus, 2026-09-22):
- En ny statisk HTML-sida från grunden, i samma pipeline som Insikt.
- Läsare: Pontus och det interna teamet.
- Allt anges i EUR/MWh.
- Datafixarna görs först, sedan byggs alla fyra delarna.

## Principer

- Varje sektion öppnar med en mening i klartext. Diagrammet är beviset.
- Inget tal visas utan enhet, period och jämförelse.
- **Okänt är inte noll.** Saknad data redovisas som datatäckning bredvid
  siffran. Den räknas aldrig som dålig prestation.
- SE3/SE4 är standard. Övriga zoner (SE1, SE2, DK1, DK2) går att slå på.
- Svensk tid för alla månader och dygn. Alla priser i EUR/MWh.
- Signatur: **dagremsor**. Varje park får en rad små staplar, en per dag,
  som visar datatäckningen. Då syns underlaget bredvid siffran. Fjällskärs
  döda mätare den 18 augusti syns direkt.

## Sidan

| Del | Innehåll |
|---|---|
| Portföljen | Månadsväljare, en klartextmening och fem tal: produktion, mot budget, spotvärde, capturepris och datatäckning, alla med värde för hittills i år. Tabell med 8 parker. Klick på en park visar dess 13 senaste månader och dagar mot budget. |
| Elmarknaden | Spotpris per månad, solens capture rate per månad (faktisk sol från ENTSO-E) och en årstabell per zon med en jämförelse mot samma period förra året. |
| Terminer | Områdespris (SYS+EPAD) för SE3/SE4, med förändring över 1 v, 1 m, 3 m och 12 m. Kontraktshistorik. "Vad marknaden trodde och vad det blev." |
| Batteri | Dagsspread (2 h) och arbitrage-tak med en cykel per dag (1 MW / 2 MWh, 88 % verkningsgrad), per månad och år. |
| Datastatus | Kända problem (upptäcks automatiskt), senaste datum per källa och definitioner. |

Medvetet utelämnat i version 1:
- PR/PI, förlustkaskad och temperaturkorrigering, eftersom instrålningsdatan
  inte går att lita på (se nedan).
- Tillgänglighet, eftersom fältet är ifyllt i under 10 % av kvartarna och har
  värden över 100 %.
- PPA-intäkt, som är ett modellantagande och inte avtalsutfall.
- Obalans, kannibaliseringsregression och batteri-IRR.

Allt detta kan läggas till när underlaget håller.

## Definitioner

Samma text visas under "Så räknar vi" på sidan (`elpris/oversikt/build.py`).

- **Produktion:** mätaren gäller först. Invertern används bara om mätaren
  saknas och invertern inte är fryst. Fryst betyder samma värde över 0,01 MW i
  8 kvartar eller fler i rad, där körningen når in i natten eller varar minst
  6 timmar. Natt, det vill säga solhöjd under −3°, räknas
  som noll. Varje kvart märks med `energy_source`: meter, inverter, night
  eller missing (`load_park_15min`).
- **Datatäckning:** andelen av dagsljuset (solhöjd över 5°) med en trovärdig
  mätning. Varje kvart vägs med sin(solhöjd).
- **Mot budget:** produktionen jämförs med PVsyst-budgeten för *samma tid som
  har mätdata*. Månadsbudgeten fördelas över kvartarna med samma vikt. Talet
  visas bara när täckningen är minst 80 %.
  - Kontroll på 57 kompletta park-månader: med 6 slumpvis borttagna dygn
    ligger den justerade siffran i median 2,3 procentenheter från facit (90 %
    inom 5,7). Utan justering blir felet 19,3 procentenheter.
  - Med 3 borttagna dygn: 1,5 respektive 9,7 procentenheter.
- **Capture-kvot (park):** capturepriset delat med spotpriset dygnet runt
  under de dygn parken har data. Fjällskär hade data bara för 1–18 augusti,
  då priset i SE3 var 43 €/MWh mot 85 €/MWh resten av månaden. Utan
  begränsningen såg dess kvot ut som 47 % i stället för rätt värde.
- **Solens capture rate (marknad):** faktisk solproduktion enligt ENTSO-E,
  inte en typårsprofil. PVsyst-profilen ger 5–8 procentenheter för hög kvot.
- **Områdespris:** SYS + EPAD från samma handelsdag. Saknas ett av benen visas
  inget pris, aldrig SYS ensamt.
- **Arbitrage-tak:** räknas fram med en optimering per lokalt dygn, på
  timpriser, med högst en laddning per dygn. Det är ett tak, inte en prognos.
  Handel på kvartspriser ger cirka 7 % mer.

## Teknik

- **En fristående HTML-fil med Plotly inbäddat.** Plotly (v3.3.0, MIT)
  ligger i `elpris/oversikt/vendor/`. Förhandsvisningen i Claude-appen
  blockerar externa skript, så den första versionen, som hämtade Plotly från
  CDN, visade tomma sektioner.
- **Varje sektion och varje diagram renderas isolerat.** Ett fel i ett
  diagram stoppar inte resten av sidan. Saknas Plotly visas tabellerna och
  texterna ändå.

## Datafixar (gjorda 2026-09-22)

1. **Strikt energiregel** i `load_park_15min`. Den påverkar alla
   konsumenter: Track C, Insikt, månadsrapporter och puls.
   - En signal räknas som fryst när samma värde upprepas i minst 8 kvartar
     *och* körningen når in i natten eller varar minst 6 timmar. Kortare
     platåer mitt på dagen är exportgränsen (Tången 4,528 MW) och räknas
     som produktion.
   - Mätarvärden under −2 % av kapaciteten är ogiltiga. Hörby visade −8 MW
     den 22–24 juli.
   - Resultatet cachas per filversion, så ett anrop tar 12 ms i stället för
     0,4 s. Track C anropar laddaren 1 088 gånger per bygge.

   Effekt i MWh:

   | Park | Månad | Före | Efter |
   |---|---|---|---|
   | Fjällskär | augusti | 2 588 | 1 688 |
   | Fjällskär | juli | 3 412 | 3 062 |
   | Hörby | september | 1 515 | 1 156 |
   | Hörby | juli | 872 | 734 |
   | Hova | juli | 1 432 | 1 314 |
   | Tången | april | 821 | 786 |

   Konsumenter som ännu räknar "missing" som noll listas i uppföljningen
   nedan. Obalansberäkningen är redan rättad.
2. **EPAD-buggen.** Saknad EPAD ger nu inget områdespris
   (`dashboard_v2_data`). Lookback använder senaste notering på eller före
   måldatumet.
3. **Terminshistoriken.** Euronext har en historiktabell med riktig handelsdag
   per rad. Luckan 30 apr–4 jul är fylld (103 handelsdagar), och gamla
   ögonblicksbilder har fått rätt handelsdag. `futures_daily.py` och
   `scripts/se.elpris.futures-daily.plist` hämtar varje vardag kl. 19:15.
   Jobbet behöver installeras manuellt, se `scripts/README.md`.
4. **DK1/DK2** laddas ner via ENTSO-E: priser och sol från 2022. ENTSO-E:s
   A03-luckor, alltså upprepade värden som utelämnats, fylls nu i parsern. De
   svenska solfilerna har laddats om med den rättade parsern.

## Fynd som kräver uppföljning

- **Instrålningsdatan (POA) ligger cirka 2 timmar efter produktionen i 7 av 8
  parker sedan april 2026.** Produktionens tidsstämplar stämmer mot solens
  middag. PR på kvartsnivå i månadsrapporterna blir därmed fel.
  Månadssummorna påverkas knappt. En separat uppgift är föreslagen.
- **Hörbys instrålningsgivare** ger orimliga värden (över 1 500 W/m²) sedan
  29 juli.
- **Fjällskärs elmätare** har inte rapporterat sedan 18 augusti.
- **Stenstorps budget** bygger fortfarande på rapporten från maj 2025
  (Meteonorm). Den nyare rapporten (Solcast) ger −5,2 %.
- **ENTSO-E:s solvolymer** täcker troligen bara en del av produktionen. De
  används som vikter, inte som produktionsnivå.
- **YR-26 och Q1-26 saknas i terminsarkivet.** Euronext levererar inte
  utgångna kontrakt. Q3-26 saknar noteringar 30 apr–30 jun av samma skäl.
- **Äldre konsumenter räknar okänd data som noll.** Det gäller
  månadsrapporten, specific yield i Track C, puls och park_revenue. De bör
  få samma täckningsregel som Översikt. En separat uppgift är föreslagen.

## Nästa steg (förslag)

1. Pontus granskar sidan. Därefter byts Track C mot Översikt på Sites.
2. Installera det dagliga terminsjobbet med launchd.
3. Rätta POA-förskjutningen. Därefter kan PR komma tillbaka som eget tal med
   täckningsregel.
4. Riv delar av Insikt/Track C i takt med att Översikt ersätter dem.
