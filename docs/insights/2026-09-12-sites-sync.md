# Data- och Sites-uppdatering 2026-09-12

Ordinarie `update_all.py --reports` slutfördes med exitkod 0. Installerad kapacitet uppdaterades separat med `installed_download.py`. Analysrums lokala utdrag regenererades efter terminsuppdateringen.

- Spotpriser och samtliga åtta parker: till och med 2026-09-11.
- ENTSO-E sol/vind, Mimer, eSett och temperatur synkade.
- Terminer: Euronext-snapshot 2026-09-12; Nasdaq returnerade inga aktiva kontrakt.
- Historisk varning kvarstår: Q1-26 saknar senare settlement efter 2025-03-28.
- Dashboard, Excelrapporter, åtta augustirapporter och daglig puls genererade.
- Separat inverter-backfill ingick inte i masterkörningen.

## Publicerad Site

Portfolio Intelligence: https://solportfoljen-intelligence.pontus-skog.chatgpt.site

Projekt-ID: `appgprj_6a6a34015f8881918c972446251f0f6f`.
Version 2, deployment `appgdep_6aa4f678f83481919ea5c5684d3e595e`, status `succeeded`.
Källcommit: `a6d2754f4fa52b7001f040e5238669cd70ed9b6b`.

**Hämta alltid aktuell Sites-källa före nästa uppdatering.** Den lokala katalogen
`portfolio_hub_prototype` är en äldre konceptprototyp trots samma projekt-ID.
Sites-källan är en iframe-wrapper kring `public/dashboard.html` (Track C).
Denna körning använde en separat worktree på `/tmp/elpris-sites-20260912` från
Sites-remote. Den befintliga publicerade HTML-mallen bevarades; DATA och
uppdateringstiden ersattes med den nya dashboardens data. Augustirapporterna
lades i `public/` för dashboardens befintliga rapportlänkar. Nuvarande publika
åtkomst bevarades. `energy_dashboard` saknar registrerat Site-ID och publicerades inte.

Verifiering: produktionsbygge, JavaScript-syntax för alla nio HTML-filer,
parkernas senaste datum, terminsdatum och arkivets filinnehåll. Efter lyckad
publicering hämtades live-dashboarden och dess inbäddade DATA jämfördes exakt
med det lokalt validerade underlaget. En augustirapport hämtades också utan fel.

Körningslogg: `Resultat/logs/sync_sites_20260912.log`.
