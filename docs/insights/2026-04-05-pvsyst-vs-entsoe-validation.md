# PVsyst-profiler vs ENTSO-E faktisk sol-capture

**Datum:** 2026-04-05
**Analys:** `analyze_solar_profiles.py`
**Status:** Förstudie — bör tolkas med försiktighet

## Huvudfynd

**PVsyst-profilerna (south_lundby, ew_boda, tracker_sweden) överestimerar
solcapture-priset med ~10 % i medel** jämfört med ENTSO-E:s faktiska nationella
solproduktion för SE2-SE4 åren 2022-2025.

Avvikelsen växer med åren — från -5 % (2022) till +17-29 % (2024).

## Resultat

Analys på 12 observationer per zon (3 profiler × 4 fullständiga år 2022-2025).
Partiella år (2021, 2026, SE1) är exkluderade.

### Per zon (medel över 3 profiler, 4 år)

| Zon | PVsyst EUR/MWh | ENTSO-E EUR/MWh | Avvikelse |
|-----|---|---|---|
| SE2 | 31.95 | 30.66 | **+7.3 %** |
| SE3 | 62.58 | 61.42 | **+12.3 %** |
| SE4 | 76.61 | 74.01 | **+11.1 %** |

SE1 har inte tillräckligt med ENTSO-E-solsekvens för att ingå — solkapaciteten
där är marginell och data börjar först 2021-12-14.

### Per profil (över alla zoner och år)

| Profil | Medelavvikelse | Max |avvikelse| |
|---|---|---|
| sol_syd | +9.9 % | 29.3 % |
| sol_ov  | +10.2 % | 26.2 % |
| sol_tracker | +10.6 % | 29.0 % |

Alla tre profiler beter sig ungefär likadant — detta är inte en enskild felaktig
profil, utan en systematisk egenskap.

### Trend över år (SE3, medel av 3 profiler)

| År | PVsyst | ENTSO-E | Avvikelse |
|---|---|---|---|
| 2022 | 146.6 | 157.2 | **-6.7 %** |
| 2023 | 45.2 | 40.1 | **+12.7 %** |
| 2024 | 27.1 | 21.1 | **+28.2 %** |
| 2025 | 31.4 | 27.2 | **+15.3 %** |

**Avvikelsen växer över tid.**

## Tolkning

Troligaste förklaringen är **kannibaliseringseffekt** med ökande sol-penetration:

- PVsyst-profilerna är fasta årsprofiler från specifika parker (Lundby, Boda).
  De beskriver en typisk produktionsform över året.
- ENTSO-E-kurvan är faktiskt nationellt totalt — när en sol-rik dag inträffar
  producerar HELA Sverige mycket sol samtidigt, vilket pressar ner priset.
- PVsyst "vet" inte att dessa soliga timmar har extra lågt pris — den applicerar
  sin profil mot samma prisserie oavsett.
- Effekten blir starkare när:
  - Sol-penetrationen ökar (mer solel under samma timmar)
  - Priser blir mer volatila med högre negativa utfall

2024 uppvisar den största avvikelsen. Det är också ett år med hög volatilitet
och mycket timmar med nära-noll-priser på dagtid i södra Sverige.

## Affärsimplikation

**Capture-prognoser baserade på PVsyst-profiler bör justeras ner med
5-15 % beroende på zon och tidsperiod.**

- För nya projekt i SE3/SE4: använd en **cannibalization discount** på PVsyst-
  baserat capture-pris. Ett försiktigt antagande är 10-12 % nedjustering.
- För historisk rapportering: behåll PVsyst-profilen men redovisa även ENTSO-E
  som referens.
- När mer sol byggs ut i SE3/SE4 kommer avvikelsen troligen att växa.

**Detta är inte en kritisk felkälla** — PVsyst-profilerna är fortfarande
användbara för relativ jämförelse och form-analys. Men för absoluta
capture-tal finns en systematisk optimistisk bias som bör flaggas.

## Begränsningar

- Analysen jämför en **zon-genomsnittlig ENTSO-E-sol** mot en **typisk park-
  profil**. En specifik anläggning kan avvika i motsatt riktning.
- PVsyst-profilerna är normaliserade (power per MWp); ENTSO-E är absolut MW.
  Enhets-skillnader påverkar inte capture-beräkningen (vikterna kancellerar ut)
  men det kan påverka intuition.
- Endast 4 fullständiga år — begränsad statistisk säkerhet. Bör byggas på med
  varje nytt år.

## Rekommenderad uppföljning

1. **Dokumentera justeringsfaktor** i `CLAUDE.md` så framtida konsumenter av
   capture-siffror känner till biasen.
2. **Lägg till en visualisering i dashboard v2** som visar PVsyst vs ENTSO-E
   per år för SE2-SE4. Förslagsvis som en ny undervy i "Validering" eller
   integrerat i sol-vyn.
3. **Övervaka trenden** — kör analysen årligen. Om avvikelsen fortsätter växa
   kan en dynamisk justering behövas baserad på installerad sol-kapacitet.
4. **Överväg att använda ENTSO-E-baserad solcapture som primär referens** för
   nya projektvärderingar i SE3/SE4, med PVsyst som form-indikator.
