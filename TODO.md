# Analysuppgifter - Solpark & Batteri

## Solcellsparker (IPP)

- [ ] **Capture price vs faktisk produktion**
  - Jämför beräknad capture med ENTSO-E faktisk solproduktion
  - Validera PPA-prissättning
  - Filer: `elpris/capture.py`, `data/raw/entsoe/generation/*/solar_*.csv`

- [ ] **Kannibaliseringseffekt**
  - Korrelera capture ratio mot installerad solkapacitet över tid
  - Förstå framtida intäktsrisk
  - Filer: `data/raw/installed/solar_installations.csv`

- [ ] **Zonspread-analys**
  - SE4 vs SE3 capture price differens
  - Optimera placering av nya parker

- [ ] **Säsongsanalys**
  - Capture price per månad/säsong med volatilitet
  - Budgetering och likviditetsplanering

- [ ] **Prognosfelkostnad**
  - Faktisk obalanskostnad baserat på eSett-data
  - Värdera prognostjänster/batterilager
  - Filer: `data/raw/esett/imbalance/*/`, `elpris/forecast_error.py`

---

## Batterilager

- [ ] **Stackade intäkter**
  - Kombinera arbitrage + FCR + aFRR + mFRR
  - Realistisk business case
  - Filer: `data/raw/mimer/fcr/`, `data/raw/mimer/afrr/`, `elpris/battery.py`

- [ ] **FCR vs arbitrage trade-off**
  - Timme-för-timme jämförelse av optimal strategi
  - Maximera intäkter

- [ ] **Obalansintäkter**
  - Använda eSett-data för att beräkna BRP-stöd
  - Värdera batteritjänster mot BRP

- [ ] **Volatilitetsanalys**
  - Daglig/veckovis prisspread och frekvens
  - Dimensionera batterikapacitet (MWh/MW ratio)

- [ ] **Korrelation sol-pris**
  - När solproduktion är hög → låga priser → laddningsmöjlighet
  - Co-location strategi

---

## Kombinerade analyser (sol + batteri)

- [ ] **Co-location värde**
  - Batteri vid solpark: shifta produktion, minska obalans
  - Investeringsbeslut

- [ ] **Obalanshedging**
  - Hur mycket batteri behövs för att eliminera obalanskostnad?
  - Optimal batterikapacitet

- [ ] **Negativa priser**
  - Frekvens och varaktighet av negativa priser vs solproduktion
  - Curtailment-strategi

- [ ] **Intradag-optimering**
  - Prisskillnad dag-ahead vs faktiskt (implicit intraday)
  - Handelsstrategier

---

## Prioritetsordning

1. Capture price vs faktisk produktion (validerar befintlig funktionalitet)
2. Stackade intäkter (batterivärde)
3. Volatilitetsanalys (batteridesign)
4. Negativa priser (aktuellt problem)
5. Co-location värde (investeringsbeslut)
