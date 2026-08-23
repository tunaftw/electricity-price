"""Parköversikt — data + klartextinsikter för Insikts första sektion.

Bygger på assets-byggstenarna i ``unified_dashboard_data`` (importerade,
inte kopierade) och lägger till det som gör Insikt till en produkt:
**en genererad slutsats i klartext per park och för portföljen**, enligt
designprincipen i docs/plans/2026-08-22-insikt-produkt-spec.md —
"varje vy leder med en slutsats i klartext, grafen under är beviset".

Publika ingångar:

* :func:`build_parkoversikt_data` — hela datastrukturen för renderaren.
* :func:`build_park_insight` — {"text", "tone"} för en park (ren funktion,
  tar en park-dict med ``months`` i samma format som
  ``unified_dashboard_data._build_park_months`` producerar).
* :func:`build_portfolio_insights` — 2–4 portföljinsikter.

Inga parknamn eller zoner är hårdkodade i insiktslogiken — allt läses ur
datastrukturen.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from ..rework_portfolio import fmt_num, fmt_signed_pct

# ---------------------------------------------------------------------------
# Regelverkets konstanter
# ---------------------------------------------------------------------------

#: |vs_budget_pct| <= denna gräns → "i linje med budget" (neutral ton).
BUDGET_TOLERANCE_PCT = 3.0

#: Residual > denna andel av budget (och irr_shortfall == 0) →
#: datakvalitetsflagga: instrålningsdata saknas, orsaksanalysen är osäker.
RESIDUAL_DQ_SHARE = 0.30

#: Antal stängda månader i rad åt samma håll som krävs för trendmeningen.
TREND_MONTHS = 3

#: Förlustposter i kaskaden, i visningsordning (budget → faktisk).
LOSS_KEYS = [
    "irradiance_shortfall_mwh",
    "availability_mwh",
    "temperature_mwh",
    "clipping_mwh",
    "residual_mwh",
]

#: Klartextnamn vid negativ avvikelse (posten är en förlust).
LOSS_LABELS_NEG = {
    "irradiance_shortfall_mwh": "svag instrålning",
    "availability_mwh": "tillgänglighetsbortfall",
    "temperature_mwh": "varmare än normalt",
    "clipping_mwh": "exportbegränsning",
    "residual_mwh": "oförklarad förlust — kräver utredning",
}

#: Klartextnamn vid positiv avvikelse (posten är negativ = ett tillskott).
LOSS_LABELS_POS = {
    "irradiance_shortfall_mwh": "stark instrålning",
    "availability_mwh": "bättre tillgänglighet än väntat",
    "temperature_mwh": "svalare än normalt",
    "clipping_mwh": "mindre exportbegränsning än väntat",
    "residual_mwh": "produktion över modellförväntan",
}

_MONTHS_SV = [
    "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december",
]


def _month_name(month: int, capitalize: bool = False) -> str:
    name = _MONTHS_SV[month - 1]
    return name.capitalize() if capitalize else name


# ---------------------------------------------------------------------------
# Månadsurval
# ---------------------------------------------------------------------------

def _closed_months(months: List[dict]) -> List[dict]:
    """Stängda månader med energidata, äldst → nyast (bevarar ordning)."""
    return [
        m for m in (months or [])
        if not m.get("is_partial") and m.get("energy_mwh") is not None
    ]


def _latest_closed(months: List[dict]) -> Optional[dict]:
    closed = _closed_months(months)
    return closed[-1] if closed else None


def _latest_partial(months: List[dict]) -> Optional[dict]:
    partials = [m for m in (months or []) if m.get("is_partial")]
    return partials[-1] if partials else None


def build_ytd_summary(months: List[dict], year: int) -> dict:
    """Summera energi vs budget för ett kalenderår (inkl. MTD-månaden —
    dess budget är redan pro-ratad uppströms så jämförelsen är rättvis)."""
    energy = 0.0
    budget = 0.0
    for m in months or []:
        if m.get("year") != year:
            continue
        energy += m.get("energy_mwh") or 0.0
        budget += m.get("budget_mwh") or 0.0
    vs = round((energy / budget - 1.0) * 100.0, 1) if budget > 0 else None
    return {
        "year": year,
        "energy_mwh": round(energy, 2),
        "budget_mwh": round(budget, 2),
        "vs_budget_pct": vs,
    }


# ---------------------------------------------------------------------------
# Insiktsregler per park
# ---------------------------------------------------------------------------

def _dq_flagged(losses: Optional[dict]) -> bool:
    """Datakvalitetsflagga: irr_shortfall == 0 och residual > 30 % av budget.

    Verkligt mönster (t.ex. Hörby juli 2026): när POA-data saknas blir
    instrålningskomponenten 0 och residualen sväljer hela gapet —
    orsaksanalysen är då inte att lita på.
    """
    if not losses:
        return False
    irr = losses.get("irradiance_shortfall_mwh") or 0.0
    residual = losses.get("residual_mwh") or 0.0
    budget = losses.get("budget_mwh") or 0.0
    return abs(irr) < 1e-9 and budget > 0 and residual > RESIDUAL_DQ_SHARE * budget


def _dominant_cause(
    losses: Optional[dict], negative: bool
) -> Optional[tuple[str, Optional[float]]]:
    """(klartextnamn, andel-av-gapet-i-%) för den dominerande förlustposten.

    Vid negativ avvikelse: största (positiva) förlustposten, med andel av
    gapet budget − faktisk. Vid positiv avvikelse: mest negativa posten
    (= största tillskottet), utan andel.
    """
    if not losses:
        return None
    comps = {k: (losses.get(k) or 0.0) for k in LOSS_KEYS}
    if negative:
        key = max(comps, key=lambda k: comps[k])
        val = comps[key]
        if val <= 0:
            return None
        gap = (losses.get("budget_mwh") or 0.0) - (losses.get("actual_mwh") or 0.0)
        share = 100.0 * val / gap if gap > 0 else None
        return LOSS_LABELS_NEG[key], share
    key = min(comps, key=lambda k: comps[k])
    val = comps[key]
    if val >= 0:
        return None
    return LOSS_LABELS_POS[key], None


def _trend_sentence(closed: List[dict]) -> Optional[str]:
    """"Tredje månaden i rad över/under budget." om de TREND_MONTHS senaste
    stängda månaderna alla avviker åt samma håll (tecken på vs_budget_pct)."""
    if len(closed) < TREND_MONTHS:
        return None
    tail = [m.get("vs_budget_pct") for m in closed[-TREND_MONTHS:]]
    if any(v is None for v in tail):
        return None
    if all(v > 0 for v in tail):
        return "Tredje månaden i rad över budget."
    if all(v < 0 for v in tail):
        return "Tredje månaden i rad under budget."
    return None


def build_park_insight(park: dict) -> dict:
    """Generera parkens klartextinsikt: {"text": str, "tone": pos|neg|neutral}.

    Regelverk (max 2 meningar):

    1. Status mot budget för senaste stängda månad (±3 %-tolerans).
    2. Dominerande orsak ur förlustkaskaden, namngiven på svenska.
    3. Mening 2 är datakvalitetsflaggan om den triggar, annars trendmeningen
       (tre månader i rad åt samma håll).
    """
    months = park.get("months") or []
    closed = _closed_months(months)
    if not closed:
        return {
            "text": "Ingen stängd månad med data ännu.",
            "tone": "neutral",
        }

    latest = closed[-1]
    mname = _month_name(latest["month"], capitalize=True)
    energy_s = fmt_num(latest.get("energy_mwh"), 0)
    vs = latest.get("vs_budget_pct")

    if vs is None:
        return {
            "text": (
                f"{mname}: {energy_s} MWh — budget saknas, "
                "avvikelse kan inte bedömas."
            ),
            "tone": "neutral",
        }

    losses = latest.get("losses")

    # Mening 1: status + dominerande orsak
    if abs(vs) <= BUDGET_TOLERANCE_PCT:
        tone = "neutral"
        sentence = (
            f"{mname}: {energy_s} MWh — i linje med budget "
            f"({fmt_signed_pct(vs)})."
        )
    elif vs > 0:
        tone = "pos"
        cause = _dominant_cause(losses, negative=False)
        clause = f" — främst {cause[0]}" if cause else ""
        sentence = (
            f"{mname}: {energy_s} MWh, {fmt_signed_pct(vs)} mot budget "
            f"({fmt_num(latest.get('budget_mwh'), 0)} MWh){clause}."
        )
    else:
        tone = "neg"
        cause = _dominant_cause(losses, negative=True)
        clause = ""
        if cause:
            label, share = cause
            share_s = (
                f" ({fmt_num(share, 0)} % av gapet)" if share is not None else ""
            )
            clause = f" — största förklaring: {label}{share_s}"
        sentence = (
            f"{mname}: {energy_s} MWh, {fmt_signed_pct(vs)} mot budget "
            f"({fmt_num(latest.get('budget_mwh'), 0)} MWh){clause}."
        )

    # Mening 2: datakvalitetsflagga prioriteras före trend (max 2 meningar)
    if _dq_flagged(losses):
        sentence += (
            " OBS: instrålningsdata saknas för månaden — "
            "orsaksanalysen är osäker."
        )
    else:
        trend = _trend_sentence(closed)
        if trend:
            sentence += f" {trend}"

    return {"text": sentence, "tone": tone}


# ---------------------------------------------------------------------------
# Per-park-summering
# ---------------------------------------------------------------------------

def build_park_summary(park: dict) -> dict:
    """Berika en park-dict med latest_closed / mtd / ytd / insight.

    Ren funktion: rör inte filsystemet, muterar inte input.
    """
    months = park.get("months") or []
    latest_closed = _latest_closed(months)
    mtd = _latest_partial(months)
    ref = mtd or latest_closed
    year = ref["year"] if ref else date.today().year

    out = dict(park)
    out["latest_closed"] = latest_closed
    out["mtd"] = mtd
    out["ytd"] = build_ytd_summary(months, year)
    out["insight"] = build_park_insight(park)
    return out


# ---------------------------------------------------------------------------
# Portföljinsikter
# ---------------------------------------------------------------------------

def _tone_from_vs(vs: Optional[float]) -> str:
    if vs is None or abs(vs) <= BUDGET_TOLERANCE_PCT:
        return "neutral"
    return "pos" if vs > 0 else "neg"


def _portfolio_latest_closed_key(parks: Dict[str, dict]) -> Optional[tuple]:
    """Senaste (year, month) bland parkernas stängda månader."""
    keys = [
        (p["latest_closed"]["year"], p["latest_closed"]["month"])
        for p in parks.values() if p.get("latest_closed")
    ]
    return max(keys) if keys else None


def build_portfolio_insights(data: dict) -> List[dict]:
    """2–4 portföljinsikter: YTD-läge, största avvikare, PPA-effekt,
    ev. datakvalitetsvarning. Varje post: {"text", "tone"}."""
    parks: Dict[str, dict] = data.get("parks") or {}
    insights: List[dict] = []
    if not parks:
        return [{"text": "Ingen parkdata tillgänglig.", "tone": "neutral"}]

    # 1. YTD-läge för portföljen
    energy = sum((p.get("ytd") or {}).get("energy_mwh") or 0.0
                 for p in parks.values())
    budget = sum((p.get("ytd") or {}).get("budget_mwh") or 0.0
                 for p in parks.values())
    capacity = sum(p.get("capacity_mwp") or 0.0 for p in parks.values())
    years = [p["ytd"]["year"] for p in parks.values() if p.get("ytd")]
    year = max(years) if years else date.today().year
    vs = round((energy / budget - 1.0) * 100.0, 1) if budget > 0 else None
    rel = "över" if (vs or 0) >= 0 else "under"
    insights.append({
        "text": (
            f"Portföljens {len(parks)} parker ({fmt_num(capacity, 1)} MWp) "
            f"har producerat {fmt_num(energy)} MWh hittills {year} — "
            f"{fmt_num(abs(vs), 1) if vs is not None else '–'} % {rel} budget."
        ),
        "tone": _tone_from_vs(vs),
    })

    # 2. Största positiva och negativa avvikaren, senaste stängda månaden
    lk = _portfolio_latest_closed_key(parks)
    if lk:
        rows = []
        for p in parks.values():
            lc = p.get("latest_closed")
            if (lc and (lc["year"], lc["month"]) == lk
                    and lc.get("vs_budget_pct") is not None):
                rows.append((p.get("name", "?"), lc["vs_budget_pct"]))
        if len(rows) >= 2:
            best = max(rows, key=lambda r: r[1])
            worst = min(rows, key=lambda r: r[1])
            if best[0] != worst[0]:
                insights.append({
                    "text": (
                        f"Senaste stängda månaden ({_month_name(lk[1])}) "
                        f"gick {best[0]} bäst ({fmt_signed_pct(best[1])} "
                        f"mot budget) och {worst[0]} svagast "
                        f"({fmt_signed_pct(worst[1])})."
                    ),
                    "tone": "neutral",
                })

    # 3. PPA-effekt hittills i år (bara parker med PPA-intäktsdata)
    uplift = 0.0
    has_ppa_data = False
    for p in parks.values():
        p_year = (p.get("ytd") or {}).get("year")
        for m in p.get("months") or []:
            if m.get("year") != p_year:
                continue
            rev = m.get("revenue_eur")
            rev_ppa = m.get("revenue_eur_ppa")
            if rev is not None and rev_ppa is not None:
                uplift += rev_ppa - rev
                has_ppa_data = True
    if has_ppa_data:
        verb = "tillfört" if uplift >= 0 else "kostat"
        insights.append({
            "text": (
                f"PPA-kontrakten har {verb} "
                f"{fmt_num(abs(uplift) / 1000.0, 1)} k€ hittills i år "
                f"relativt ren spotförsäljning."
            ),
            "tone": _tone_from_vs(uplift if uplift != 0 else None) if abs(uplift) > 0 else "neutral",
        })

    # 4. Datakvalitetsvarning om någon parks senaste månad är flaggad
    flagged = [
        p.get("name", "?") for p in parks.values()
        if p.get("latest_closed") and _dq_flagged(p["latest_closed"].get("losses"))
    ]
    if flagged and len(insights) < 4:
        subject = (
            "parken" if len(flagged) == 1 else "dessa parker"
        )
        insights.append({
            "text": (
                "OBS: instrålningsdata saknas senaste stängda månaden för "
                f"{', '.join(sorted(flagged))} — orsaksanalysen för "
                f"{subject} är osäker."
            ),
            "tone": "neg",
        })

    return insights[:4]


# ---------------------------------------------------------------------------
# KPI:er + huvudingång
# ---------------------------------------------------------------------------

def _build_kpis(parks: Dict[str, dict]) -> dict:
    """Portfölj-KPI:er för hero-sektionen, baserade på senaste stängda
    månaden (aggregerad över parker som rapporterat den) + YTD."""
    lk = _portfolio_latest_closed_key(parks)
    energy = budget = revenue = volume = 0.0
    if lk:
        for p in parks.values():
            lc = p.get("latest_closed")
            if not lc or (lc["year"], lc["month"]) != lk:
                continue
            energy += lc.get("energy_mwh") or 0.0
            budget += lc.get("budget_mwh") or 0.0
            rev = lc.get("revenue_eur")
            vol = lc.get("bazefield_volume_mwh")
            if rev is not None and vol is not None:
                revenue += rev
                volume += vol

    ytd_energy = sum((p.get("ytd") or {}).get("energy_mwh") or 0.0
                     for p in parks.values())
    ytd_budget = sum((p.get("ytd") or {}).get("budget_mwh") or 0.0
                     for p in parks.values())

    return {
        "latest_closed_month": f"{lk[0]}-{lk[1]:02d}" if lk else None,
        "latest_closed_label": (
            f"{_month_name(lk[1])} {lk[0]}" if lk else None
        ),
        "energy_mwh": round(energy, 1),
        "budget_mwh": round(budget, 1),
        "vs_budget_pct": (
            round((energy / budget - 1.0) * 100.0, 1) if budget > 0 else None
        ),
        "capture_eur_mwh": round(revenue / volume, 1) if volume > 0 else None,
        "ytd_energy_mwh": round(ytd_energy, 1),
        "ytd_budget_mwh": round(ytd_budget, 1),
        "ytd_vs_budget_pct": (
            round((ytd_energy / ytd_budget - 1.0) * 100.0, 1)
            if ytd_budget > 0 else None
        ),
        "park_count": len(parks),
        "total_capacity_mwp": round(
            sum(p.get("capacity_mwp") or 0.0 for p in parks.values()), 2
        ),
    }


def build_parkoversikt_data() -> Dict[str, Any]:
    """Bygg hela datastrukturen för Insikts parköversikt.

    Återanvänder ``unified_dashboard_data._build_assets_section`` för
    per-park-månaderna (13 mån, MTD pro-ratad, förlustkaskad, intäkt)
    och lägger insiktslagret ovanpå. Daglig data beskärs till senaste
    stängda månaden per park (drilldownens energiband).
    """
    from ..unified_dashboard_data import _build_assets_section

    assets = _build_assets_section(market={})

    parks: Dict[str, dict] = {}
    for key, park in (assets.get("parks") or {}).items():
        summary = build_park_summary(park)
        # Beskär daglig data: bara senaste stängda månaden behövs i UI:t
        daily = park.get("daily_by_month") or {}
        keep: Dict[str, list] = {}
        lc = summary.get("latest_closed")
        if lc:
            k = f"{lc['year']}-{lc['month']:02d}"
            if k in daily:
                keep[k] = daily[k]
        summary["daily_by_month"] = keep
        parks[key] = summary

    data: Dict[str, Any] = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "parks": parks,
        "fleet": assets.get("fleet"),
    }
    data["kpis"] = _build_kpis(parks)
    data["portfolio_insights"] = build_portfolio_insights(data)
    return data
