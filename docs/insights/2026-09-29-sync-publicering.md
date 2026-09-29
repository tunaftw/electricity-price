# Synk och publicering 2026-09-29

`git fetch origin` och `git merge --ff-only origin/main` bekräftade att inga
inkommande commits saknades. De fem lokala commits som väntade på push samt
datauppdateringen `f3b830c` pushades till GitHub tillsammans med de fyra
`arkiv/*-2026-09`-taggarna.

`python update_all.py` slutfördes med exitkod 0. Spotpriser, samtliga åtta parker,
ENTSO-E, temperatur, Mimer, eSett och terminer uppdaterades. Spot- och parkdata
går till och med 28 september; senaste terminsavslut är också 28 september.
Capture- och batteri-Excel, Electricity Price, artefaktversionen och daglig puls
genererades. Per-park månadsrapporter begärdes inte och hoppades över.

De nordiska marknadsunderlagen som behövs för att återskapa vyn lades till i Git:
senaste terminsbilden, historiska Energinet-spotpriser och aktuellt danskt
produktionsutdrag. Äldre lokala cachefiler och engångsrapporter lämnades orörda.

## Publicerad ChatGPT Site

- URL: https://solportfoljen-intelligence.pontus-skog.chatgpt.site
- Projekt: `appgprj_6a6a34015f8881918c972446251f0f6f`
- Källcommit: `b78b6744678841a2b2ae97ca56674b18345f9c49`
- Version: `appgprj_6a6a34015f8881918c972446251f0f6f~appgver_e20f6d23eec481918ddd5fd16a3638cd`
- Deployment: `appgdep_6abbd6765b708191af5c6f76cce366c8`, status `succeeded`.

Aktuell Sites-källa hämtades före ändringen. `public/dashboard.html` ersattes
med huvudversionen Electricity Price från samma synkade underlag, och skalets
språk och titel uppdaterades. Befintlig privat åtkomst bevarades.

Sites-pluginets lokala hjälpskript försvann efter att källan hade synkats.
Reservvägen använde projektets befintliga `npm run build`, vanlig Git-push med
kortlivad credential via dold standardinmatning och ett kontrollerat arkiv av
`dist/`, följt av Sites ordinarie publiceringsverktyg. Inga credentials sparades.

## Verifiering och kvarstående publicering

190 Python-tester och fyra sajttester godkändes. Produktionsbygget lyckades.
De 672 tillagda kvartpriserna per svensk zon jämfördes med föregående commit:
historiken var oförändrad, intervallen sammanhängande och prisvärdena ändliga.
Terminsfilerna saknade dubbletter per handelsdatum och kontrakt. Arkivets
dashboard var byteidentisk med den pushade sajtkällan; projekt-ID och Worker
kontrollerades. Sites bekräftade lyckad publicering.

Claude-artefaktens uppdaterade HTML finns i
`Resultat/rapporter/electricity_price_20260929_artifact.html`. Publiceringen i
Claude återstår eftersom webbläsaren kräver användarens inloggning.

Kända statusnotiser kvarstår: historisk settlementtäckning för Q1-26 och en
pulsvarning som förväntar dagens spotpriser trots att ordinarie `update.py`
avsiktligt hämtar till och med gårdagen. Ingen nedladdning rapporterade fel.
