"""LLM-genererad Executive Summary (STUB — ej aktiverat).

=== Status: PLACEHOLDER FÖR FRAMTIDA ARBETE ===

Denna modul är en stub som dokumenterar planen för att låta Claude API
generera prosaisk Executive Summary för månadsrapporterna istället för
den nuvarande mall-baserade texten i performance_report_html.py.

Modulen är INTE aktiverad idag. Nuvarande implementation i
`performance_report_html.py:_render_executive_summary()` använder en
mall-baserad approach som fungerar utan externa beroenden och är
automatiserbar.

-----------------------------------------------------------------------------
VARFÖR ÄR DET INTE AKTIVERAT?
-----------------------------------------------------------------------------

Anthropic API kräver en egen API-nyckel som är separat från Claude Code
(CLI-verktyget som Svea Solar använder för utveckling). API-nyckeln är för
programmatisk access till Claude från Python-skript.

För att aktivera denna modul krävs:
1. Konto på https://console.anthropic.com
2. Generera API-nyckel
3. ~$0.50/år i API-kostnader (försumbart)

Detta är en liten administrativ investering men räknades inte vara värd
det för initial MVP. Kan aktiveras senare om önskemål finns.

-----------------------------------------------------------------------------
AKTIVERINGS-CHECKLIST
-----------------------------------------------------------------------------

När du är redo att aktivera LLM-genererad summary:

[ ] 1. Skapa konto på https://console.anthropic.com
[ ] 2. Generera API-nyckel (Settings → API Keys → Create Key)
[ ] 3. Lägg till i .env:
       ANTHROPIC_API_KEY=sk-ant-api03-...

[ ] 4. Installera SDK:
       pip install anthropic>=0.40
       (lägg också till i requirements.txt)

[ ] 5. Uncomment implementation i denna fil (generate_executive_summary)
       Ta bort NotImplementedError-raise, aktivera den riktiga koden.

[ ] 6. Uppdatera performance_report_html.py:_render_executive_summary():
       Försök först LLM, fall tillbaka på mall-text vid fel:

           from .llm_summary import generate_executive_summary
           try:
               prose = generate_executive_summary(report)
               return f'<div>...{prose}...</div>'
           except Exception:
               pass  # Fall back to mall-text (befintlig kod)

[ ] 7. Skapa cache-mapp:
       mkdir -p Resultat/cache/llm_summary

[ ] 8. Testa:
       python generate_performance_report.py --park horby --month 2026-03
       → Sektion 19 ska nu visa LLM-genererad svensk prosa

-----------------------------------------------------------------------------
DESIGN-BESLUT
-----------------------------------------------------------------------------

- **Model:** `claude-sonnet-4-6`
  Sonnet är tillräckligt smart för prosaisk summary och betydligt billigare
  än Opus. Snabbt svar (<5s).

- **Språk:** Svenska. Prompt och output på svenska för konsistens med
  resten av rapporten.

- **Format:** 3 stycken med rubriker:
  1. **Översikt** — Vad hände denna månad? Huvuddrivare?
  2. **Viktiga observationer** — Punktlista med 3-5 insikter
  3. **Sammanfattande bedömning** — Är parken på rätt kurs? YTD-perspektiv?
  Max 250 ord totalt.

- **Cache:** Varje genererad text sparas i
    Resultat/cache/llm_summary/{park}_{zone}_{year}-{month}.txt
  Nästa körning läser cache istället för att anropa API. Cache invalideras
  bara om KPI-värden ändras markant (implementeras inte initialt).

- **Kostnad:** ~500 input + 600 output tokens per rapport
  Sonnet 4.6: $3/$15 per million tokens
  → ~$0.01 per rapport
  → 8 parker × 12 månader = ~$0.96/år för hela portföljen

- **Fallback:** Om API-nyckel saknas eller anrop failar, används befintlig
  mall-text. Rapportgenereringen ska ALDRIG blockeras av LLM-fel.

- **Säkerhet:** API-nyckeln ska aldrig committas. Den ligger i .env som är
  git-ignored.

-----------------------------------------------------------------------------
IMPLEMENTATION-SKISS (kommenterad kod — klar att aktivera)
-----------------------------------------------------------------------------
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .performance_report_data import MonthlyReport


# Cache-katalog för LLM-genererade summaries
# Skapas vid första körning om den inte finns
_CACHE_DIR = Path(__file__).parent.parent / "Resultat" / "cache" / "llm_summary"


def generate_executive_summary(report: "MonthlyReport") -> str:
    """Generera prosaisk Executive Summary via Claude API.

    Args:
        report: Komplett MonthlyReport för en park och månad.

    Returns:
        Markdown-formaterad svensk prosa (3 stycken).

    Raises:
        NotImplementedError: Modulen är inte aktiverad. Se docstring i
            modulen för aktiveringsinstruktioner.
    """
    raise NotImplementedError(
        "LLM Executive Summary är inte aktiverat. "
        "Se elpris/llm_summary.py för aktiveringsinstruktioner. "
        "Kräver ANTHROPIC_API_KEY i .env och 'pip install anthropic'."
    )

    # ------------------------------------------------------------
    # IMPLEMENTATION (uncomment när redo att aktivera)
    # ------------------------------------------------------------
    #
    # import os
    # from anthropic import Anthropic
    #
    # # Check cache first
    # cache_key = f"{report.park_key}_{report.zone}_{report.year}-{report.month:02d}.txt"
    # cache_file = _CACHE_DIR / cache_key
    # if cache_file.exists():
    #     return cache_file.read_text(encoding="utf-8")
    #
    # # Build prompt from report data
    # energy_delta = ((report.actual_energy_mwh / report.budget_energy_mwh - 1) * 100
    #                 if report.budget_energy_mwh > 0 else 0)
    #
    # prompt = f"""Skriv en professionell månadssammanfattning på svenska för solparken
    # {report.park_display_name} ({report.zone}, {report.capacity_mwp:.1f} MWp DC).
    #
    # PERIOD: {report.month_name} {report.year}
    #
    # NYCKELTAL:
    # - Faktisk produktion: {report.actual_energy_mwh:.0f} MWh
    # - Budget: {report.budget_energy_mwh:.0f} MWh
    # - Avvikelse mot budget: {energy_delta:+.1f}%
    # - Specific Yield: {report.yield_kwh_kwp:.1f} kWh/kWp
    # - Performance Ratio: {report.performance_ratio_pct or 'N/A'}% (budget: {report.budget_pr_pct:.1f}%)
    #
    # FÖRLUSTER (MWh):
    # - Curtailment: {report.losses.curtailment_loss_mwh:.1f}
    # - Instrålningsunderskott: {report.losses.irradiance_shortfall_loss_mwh:.1f}
    # - Tillgänglighetsförlust: {report.losses.availability_loss_mwh:.1f}
    # - Temperaturförlust: {report.losses.temperature_loss_mwh:.1f}
    # - Övriga förluster: {report.losses.other_losses_mwh:.1f}
    #
    # STRUKTUR (3 stycken med rubriker):
    # 1. **Översikt** — Vad hände denna månad? Huvuddrivare för produktionen?
    # 2. **Viktiga observationer** — Punktlista med 3-5 insikter (kursivera siffror)
    # 3. **Sammanfattande bedömning** — Är parken på rätt kurs?
    #
    # TON: Saklig, koncis, professionell. Använd "parken" eller parknamnet, inte "vi".
    # FORMAT: Markdown med rubriker (**fet**) och punktlistor.
    # LÄNGD: Max 250 ord."""
    #
    # client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    # response = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=600,
    #     messages=[{"role": "user", "content": prompt}],
    # )
    # text = response.content[0].text
    #
    # # Save to cache
    # _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # cache_file.write_text(text, encoding="utf-8")
    #
    # return text
