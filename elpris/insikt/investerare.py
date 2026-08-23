"""Investerarrapport — en kurerad månadssida ur Insikts befintliga moduler.

Ingen ny analys görs här. Modulen **väljer ut** och **formulerar** det som
redan finns:

* :func:`..parkoversikt.build_parkoversikt_data` — per-park månader,
  förlustkaskad, budget (PVsyst TMY), realiserad intäkt/capture.
* :func:`..obalans.build_obalans_data` — simulerad obalanskostnad, spann.
* :func:`..rework_market_analysis.analyze_zone_quarters` — spotsnitt och
  negativa timmar per zon och månad.

Designprincipen är densamma som i övriga Insikt
(docs/plans/2026-08-22-insikt-produkt-spec.md): **slutsats först**. Hero-
texten är en regelgenererad exekutiv sammanfattning; tabellen och grafen
under är beviset.

Tonen är investerarens, inte driftteknikerns: inga inverter-ID:n, inga
alarmkoder — men avvikelser döljs inte. En park som ligger −79,6 % mot
budget står med den siffran och med en kort orsaksangivelse, inklusive
datakvalitetsförbehåll när orsaksanalysen inte går att lita på.

Publika ingångar::

    >>> from elpris.insikt.investerare import (
    ...     build_investor_data, render_investor_html)
    >>> data = build_investor_data(2026, 7)
    >>> html = render_investor_html(data)

Alla byggfunktioner utom :func:`build_investor_data` är rena — de tar
datastrukturer och returnerar datastrukturer, rör inte filsystemet.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

from ..rework_portfolio import fmt_num, fmt_signed_pct
from .parkoversikt import (
    BUDGET_TOLERANCE_PCT,
    _dominant_cause,
    _dq_flagged,
    _month_name,
)

#: Antal månader i historikgrafen (bakåt t.o.m. rapportmånaden).
HISTORY_MONTHS = 13

__all__ = [
    "build_investor_data",
    "render_investor_html",
    "build_executive_summary",
    "build_park_rows",
    "build_portfolio_kpis",
    "build_history",
    "build_ppa_effect",
    "build_market_stats",
    "latest_closed_period",
]


# ---------------------------------------------------------------------------
# Månadshjälpare
# ---------------------------------------------------------------------------

def _key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _shift(year: int, month: int, back: int) -> tuple:
    """(year, month) förskjuten ``back`` månader bakåt."""
    idx = year * 12 + (month - 1) - back
    return idx // 12, idx % 12 + 1


def _select_month(months: List[dict], year: int, month: int) -> Optional[dict]:
    """Stängd månadsrad för (year, month), annars None."""
    for m in months or []:
        if m.get("year") == year and m.get("month") == month:
            if m.get("is_partial"):
                return None
            return m
    return None


def latest_closed_period(parkoversikt: dict) -> Optional[tuple]:
    """Senaste stängda månaden i portföljen som (year, month)."""
    key = (parkoversikt.get("kpis") or {}).get("latest_closed_month")
    if key:
        return int(key[:4]), int(key[5:7])
    keys = [
        (m["year"], m["month"])
        for p in (parkoversikt.get("parks") or {}).values()
        for m in (p.get("months") or [])
        if not m.get("is_partial") and m.get("energy_mwh") is not None
    ]
    return max(keys) if keys else None


def _ytd(months: List[dict], year: int, upto_month: int) -> dict:
    """Summera energi vs budget för året t.o.m. ``upto_month`` (inklusive).

    Skiljer sig från ``parkoversikt.build_ytd_summary`` genom att den
    klipper vid rapportmånaden — en rapport för juni ska inte innehålla
    juli.
    """
    energy = budget = 0.0
    seen = False
    for m in months or []:
        if m.get("year") != year or m.get("month", 0) > upto_month:
            continue
        if m.get("is_partial"):
            continue
        energy += m.get("energy_mwh") or 0.0
        budget += m.get("budget_mwh") or 0.0
        seen = True
    vs = round((energy / budget - 1.0) * 100.0, 1) if budget > 0 else None
    # 2 decimaler = samma precision som källans månadsrader; annars
    # ackumuleras avrundningsfel när portföljen summeras över 8 parker.
    return {
        "energy_mwh": round(energy, 2) if seen else None,
        "budget_mwh": round(budget, 2) if seen else None,
        "vs_budget_pct": vs,
    }


# ---------------------------------------------------------------------------
# Per-park-rader
# ---------------------------------------------------------------------------

def _cause_text(row_month: dict) -> Optional[str]:
    """Kort orsaksangivelse i klartext för månadens avvikelse.

    Är månaden datakvalitetsflaggad returneras None — då sväljer
    residualen hela gapet och "oförklarad förlust" vore en skenbar
    förklaring. Avvikelsen redovisas ändå, men utan orsak.
    """
    vs = row_month.get("vs_budget_pct")
    if vs is None or abs(vs) <= BUDGET_TOLERANCE_PCT:
        return None
    if _dq_flagged(row_month.get("losses")):
        return None
    cause = _dominant_cause(row_month.get("losses"), negative=vs < 0)
    if not cause:
        return None
    label, share = cause
    # Andelen kan överstiga 100 % när andra poster drar åt andra hållet —
    # då säger siffran mer om modellen än om parken, och utelämnas.
    if vs < 0 and share is not None and 0 < share <= 100:
        return f"{label} ({fmt_num(share, 0)} % av gapet)"
    return label


def build_park_rows(
    parks: Dict[str, dict], year: int, month: int
) -> List[dict]:
    """En rad per park för rapportmånaden (rent urval ur parkdatat).

    Parker utan stängd rapportmånad tas med men med ``energy_mwh=None`` —
    en tom rad är ärligare än en utelämnad park.
    """
    rows: List[dict] = []
    for key, park in (parks or {}).items():
        months = park.get("months") or []
        m = _select_month(months, year, month)
        ytd = _ytd(months, year, month)
        losses = (m or {}).get("losses")
        rows.append({
            "key": key,
            "name": park.get("name") or key.capitalize(),
            "zone": park.get("zone") or "",
            "capacity_mwp": park.get("capacity_mwp"),
            "energy_mwh": (m or {}).get("energy_mwh"),
            "budget_mwh": (m or {}).get("budget_mwh"),
            "vs_budget_pct": (m or {}).get("vs_budget_pct"),
            "ytd_energy_mwh": ytd["energy_mwh"],
            "ytd_budget_mwh": ytd["budget_mwh"],
            "ytd_vs_budget_pct": ytd["vs_budget_pct"],
            "revenue_eur": (m or {}).get("revenue_eur"),
            "revenue_eur_ppa": (m or {}).get("revenue_eur_ppa"),
            "volume_mwh": (m or {}).get("bazefield_volume_mwh"),
            "capture_eur_mwh": (m or {}).get("capture_eur_mwh"),
            "baseload_eur_mwh": (m or {}).get("baseload_eur_mwh"),
            "cause": _cause_text(m) if m else None,
            "dq_flag": _dq_flagged(losses),
            "has_month": m is not None,
        })
    rows.sort(key=lambda r: r["name"])
    return rows


# ---------------------------------------------------------------------------
# Portfölj-KPI:er
# ---------------------------------------------------------------------------

def build_portfolio_kpis(rows: List[dict]) -> dict:
    """Aggregera park-raderna till portföljens KPI:er.

    Capture och baseload volymviktas över de parker som har
    intäktsdata; energi/budget summeras över parker med stängd månad.
    """
    energy = budget = 0.0
    ytd_energy = ytd_budget = 0.0
    revenue = revenue_ppa = volume = 0.0
    baseload_w = 0.0
    reporting = 0
    has_rev = has_ppa = False

    for r in rows or []:
        if r.get("energy_mwh") is not None:
            energy += r["energy_mwh"]
            budget += r.get("budget_mwh") or 0.0
            reporting += 1
        ytd_energy += r.get("ytd_energy_mwh") or 0.0
        ytd_budget += r.get("ytd_budget_mwh") or 0.0

        vol = r.get("volume_mwh")
        rev = r.get("revenue_eur")
        if vol and rev is not None:
            revenue += rev
            volume += vol
            has_rev = True
            bl = r.get("baseload_eur_mwh")
            if bl is not None:
                baseload_w += bl * vol
            rev_ppa = r.get("revenue_eur_ppa")
            if rev_ppa is not None:
                revenue_ppa += rev_ppa
                has_ppa = True
            else:
                revenue_ppa += rev

    capture = round(revenue / volume, 1) if volume > 0 else None
    baseload = round(baseload_w / volume, 1) if volume > 0 else None
    premium = (
        round((capture / baseload - 1.0) * 100.0, 1)
        if capture is not None and baseload else None
    )
    return {
        "park_count": len(rows or []),
        "reporting_park_count": reporting,
        "capacity_mwp": round(
            sum(r.get("capacity_mwp") or 0.0 for r in rows or []), 2
        ),
        "energy_mwh": round(energy, 1) if reporting else None,
        "budget_mwh": round(budget, 1) if reporting else None,
        "vs_budget_pct": (
            round((energy / budget - 1.0) * 100.0, 1) if budget > 0 else None
        ),
        "ytd_energy_mwh": round(ytd_energy, 1) if ytd_budget > 0 else None,
        "ytd_budget_mwh": round(ytd_budget, 1) if ytd_budget > 0 else None,
        "ytd_vs_budget_pct": (
            round((ytd_energy / ytd_budget - 1.0) * 100.0, 1)
            if ytd_budget > 0 else None
        ),
        "revenue_eur": round(revenue, 0) if has_rev else None,
        "revenue_eur_ppa": round(revenue_ppa, 0) if has_ppa else None,
        "volume_mwh": round(volume, 1) if has_rev else None,
        "capture_eur_mwh": capture,
        "baseload_eur_mwh": baseload,
        "capture_premium_pct": premium,
    }


# ---------------------------------------------------------------------------
# Historik + PPA-effekt
# ---------------------------------------------------------------------------

def build_history(
    parks: Dict[str, dict], year: int, month: int, n: int = HISTORY_MONTHS
) -> List[dict]:
    """Portföljens produktion vs budget per månad, ``n`` mån t.o.m. (year, month).

    Månader där ingen park har stängd data utelämnas helt (hellre en
    kortare serie än en falsk nolla).
    """
    out: List[dict] = []
    for back in range(n - 1, -1, -1):
        y, mo = _shift(year, month, back)
        energy = budget = 0.0
        found = False
        for park in (parks or {}).values():
            m = _select_month(park.get("months") or [], y, mo)
            if m is None or m.get("energy_mwh") is None:
                continue
            energy += m["energy_mwh"]
            budget += m.get("budget_mwh") or 0.0
            found = True
        if not found:
            continue
        out.append({
            "month": _key(y, mo),
            "label": _MONTH_ABBR[mo - 1],
            "year_label": str(y),
            "energy_mwh": round(energy, 1),
            "budget_mwh": round(budget, 1) if budget > 0 else None,
            "vs_budget_pct": (
                round((energy / budget - 1.0) * 100.0, 1) if budget > 0 else None
            ),
            "is_report_month": (y, mo) == (year, month),
        })
    return out


_MONTH_ABBR = [
    "jan", "feb", "mar", "apr", "maj", "jun",
    "jul", "aug", "sep", "okt", "nov", "dec",
]


def build_ppa_effect(
    parks: Dict[str, dict], year: int, upto_month: int
) -> Optional[dict]:
    """PPA-bokens effekt hittills i år: intäkt med PPA − ren spotintäkt.

    Returnerar None när ingen park har både spot- och PPA-intäkt.
    """
    uplift = 0.0
    spot = 0.0
    park_names: List[str] = []
    for park in (parks or {}).values():
        park_uplift = 0.0
        seen = False
        for m in park.get("months") or []:
            if m.get("year") != year or m.get("month", 0) > upto_month:
                continue
            if m.get("is_partial"):
                continue
            rev = m.get("revenue_eur")
            rev_ppa = m.get("revenue_eur_ppa")
            if rev is None or rev_ppa is None:
                continue
            park_uplift += rev_ppa - rev
            spot += rev
            seen = True
        if seen:
            uplift += park_uplift
            park_names.append(park.get("name") or "?")
    if not park_names:
        return None
    return {
        "uplift_eur": round(uplift, 0),
        "spot_revenue_eur": round(spot, 0),
        "uplift_pct": round(uplift / spot * 100.0, 1) if spot else None,
        "park_count": len(park_names),
        "parks": sorted(park_names),
    }


# ---------------------------------------------------------------------------
# Marknadskontext (spotsnitt + negativa timmar per zon)
# ---------------------------------------------------------------------------

def build_market_stats(years: Iterable[int]) -> Dict[str, Dict[str, dict]]:
    """{zon: {"YYYY-MM": {avg, neg_hours, ...}}} för angivna år.

    Läser bara de aktuella årens quarterly-CSV:er och kör dem genom
    ``rework_market_analysis.analyze_zone_quarters`` — samma byggsten som
    rework-dashboarden, ingen ny analyslogik.
    """
    from ..config import QUARTERLY_DIR, ZONES
    from ..rework_market_analysis import analyze_zone_quarters

    out: Dict[str, Dict[str, dict]] = {}
    for zone in ZONES:
        rows: List[dict] = []
        for y in sorted(set(years)):
            path = QUARTERLY_DIR / zone / f"{y}.csv"
            if not path.exists():
                continue
            with open(path, "r", encoding="utf-8") as fh:
                rows.extend(csv.DictReader(fh))
        if not rows:
            continue
        result = analyze_zone_quarters(rows)
        out[zone] = {m["month"]: m for m in result["monthly"]}
    return out


def build_market_context(
    market: Dict[str, Dict[str, dict]],
    year: int,
    month: int,
    portfolio_zones: Optional[Iterable[str]] = None,
) -> Optional[dict]:
    """2–3 meningar marknadskontext för rapportmånaden.

    Begränsas till de elområden portföljen faktiskt ligger i — en
    investerare bryr sig om SE3/SE4, inte om SE1:s vattenkraftsöverskott.
    Utelämnas hellre än gissas: saknas spotdata returneras None.
    """
    key = _key(year, month)
    prev_y, prev_m = _shift(year, month, 1)
    prev_key = _key(prev_y, prev_m)

    wanted = {z for z in (portfolio_zones or []) if z}
    candidates = [z for z in sorted(market or {}) if not wanted or z in wanted]

    zones: List[dict] = []
    for zone in candidates:
        rec = (market[zone] or {}).get(key)
        if not rec:
            continue
        prev = (market[zone] or {}).get(prev_key) or {}
        zones.append({
            "zone": zone,
            "avg_eur_mwh": rec.get("avg"),
            "neg_hours": rec.get("neg_hours"),
            "avg_daily_spread": rec.get("avg_daily_spread"),
            "prev_avg_eur_mwh": prev.get("avg"),
        })
    if not zones:
        return None

    mname = _month_name(month)
    zone_list = ", ".join(z["zone"] for z in zones)
    lo = min(zones, key=lambda z: z["avg_eur_mwh"])
    hi = max(zones, key=lambda z: z["avg_eur_mwh"])
    if lo["zone"] == hi["zone"]:
        sentences = [
            f"Spotpriset i {mname} snittade {fmt_num(hi['avg_eur_mwh'], 0)} "
            f"€/MWh i {hi['zone']}, där portföljen ligger."
        ]
    else:
        sentences = [
            f"Spotpriset i {mname} snittade {fmt_num(lo['avg_eur_mwh'], 0)} "
            f"€/MWh i {lo['zone']} och {fmt_num(hi['avg_eur_mwh'], 0)} €/MWh i "
            f"{hi['zone']} — {fmt_num(hi['avg_eur_mwh'] - lo['avg_eur_mwh'], 0)} "
            f"€/MWh i skillnad mellan portföljens elområden."
        ]

    neg_total = sum(z["neg_hours"] or 0.0 for z in zones)
    if neg_total > 0:
        worst = max(zones, key=lambda z: z["neg_hours"] or 0.0)
        sentences.append(
            f"Negativa spotpriser förekom under {fmt_num(neg_total, 1)} timmar i "
            f"portföljens elområden, varav {fmt_num(worst['neg_hours'], 1)} "
            f"timmar i {worst['zone']}."
        )
    else:
        sentences.append(
            f"Inga timmar med negativt spotpris noterades i {zone_list} under "
            "månaden."
        )

    with_prev = [z for z in zones if z.get("prev_avg_eur_mwh")]
    if with_prev:
        diffs = [
            (z["avg_eur_mwh"] / z["prev_avg_eur_mwh"] - 1.0) * 100.0
            for z in with_prev
        ]
        avg_diff = sum(diffs) / len(diffs)
        riktning = "lägre" if avg_diff < 0 else "högre"
        sentences.append(
            f"Jämfört med {_month_name(prev_m)} låg snittpriset "
            f"{fmt_num(abs(avg_diff), 0)} % {riktning}."
        )

    return {"zones": zones, "sentences": sentences[:3]}


# ---------------------------------------------------------------------------
# Obalanskostnad (spann)
# ---------------------------------------------------------------------------

def build_imbalance_summary(obalans: Optional[dict]) -> Optional[dict]:
    """Portföljens simulerade obalanskostnad senaste 12 mån, som ett spann."""
    port = ((obalans or {}).get("portfolio") or {}).get("last12")
    if not port or port.get("cost_per_mwh_a") is None:
        return None
    lo_tot = min(port["cost_eur_a"], port["cost_eur_b"])
    hi_tot = max(port["cost_eur_a"], port["cost_eur_b"])
    lo = min(port["cost_per_mwh_a"], port["cost_per_mwh_b"])
    hi = max(port["cost_per_mwh_a"], port["cost_per_mwh_b"])
    return {
        "low_eur": lo_tot,
        "high_eur": hi_tot,
        "low_eur_mwh": lo,
        "high_eur_mwh": hi,
        "volume_mwh": port.get("volume_mwh"),
        "park_count": port.get("park_count"),
    }


# ---------------------------------------------------------------------------
# Exekutiv sammanfattning
# ---------------------------------------------------------------------------

def _largest_deviator(rows: List[dict]) -> Optional[dict]:
    """Parken med störst absolut budgetavvikelse i rapportmånaden."""
    cand = [r for r in rows or [] if r.get("vs_budget_pct") is not None]
    if not cand:
        return None
    return max(cand, key=lambda r: abs(r["vs_budget_pct"]))


def build_executive_summary(data: dict) -> List[str]:
    """3–4 meningar i klartext: utfall, orsak, YTD-läge, viktig händelse.

    Regelverk:

    1. Månadens portföljutfall mot budget.
    2. Största avvikaren namnges — även när avvikelsen är negativ — med
       dominerande orsak ur förlustkaskaden när sådan finns.
    3. YTD-läget ("hittills i år").
    4. Datakvalitetsflagga om någon parks orsaksanalys är osäker, annars
       realiserat capture mot baseload. Utelämnas om inget av dem finns.
    """
    period = data.get("period") or {}
    kpis = data.get("portfolio") or {}
    rows = data.get("parks") or []
    label = period.get("label") or "perioden"

    if not rows or kpis.get("energy_mwh") is None:
        return [
            f"Ingen stängd produktionsdata finns för {label} — rapporten kan "
            "inte sammanfatta utfallet."
        ]

    out: List[str] = []

    # 1. Månadens utfall
    vs = kpis.get("vs_budget_pct")
    energy_s = fmt_num(kpis.get("energy_mwh"), 0)
    if vs is None:
        out.append(
            f"Portföljens {kpis.get('reporting_park_count')} rapporterande "
            f"parker producerade {energy_s} MWh i {label}; budget saknas för "
            "perioden så avvikelsen kan inte bedömas."
        )
    else:
        rel = "över" if vs >= 0 else "under"
        out.append(
            f"Portföljen producerade {energy_s} MWh i {label}, "
            f"{fmt_num(abs(vs), 1)} % {rel} budget "
            f"({fmt_num(kpis.get('budget_mwh'), 0)} MWh)."
        )

    # 2. Största avvikaren
    dev = _largest_deviator(rows)
    if dev is not None:
        if abs(dev["vs_budget_pct"]) <= BUDGET_TOLERANCE_PCT:
            out.append(
                "Ingen enskild park avvek mer än "
                f"{fmt_num(BUDGET_TOLERANCE_PCT, 0)} % mot budget under "
                "månaden."
            )
        else:
            riktning = (
                "starkast" if dev["vs_budget_pct"] > 0 else "svagast"
            )
            cause = dev.get("cause")
            clause = f"; dominerande förklaring är {cause}" if cause else ""
            out.append(
                f"{dev['name']} ({dev['zone']}) avvek mest och gick "
                f"{riktning} med {fmt_signed_pct(dev['vs_budget_pct'])} mot "
                f"budget{clause}."
            )

    # 3. YTD
    ytd_vs = kpis.get("ytd_vs_budget_pct")
    if kpis.get("ytd_energy_mwh") is not None:
        if ytd_vs is None:
            out.append(
                f"Hittills i år uppgår produktionen till "
                f"{fmt_num(kpis['ytd_energy_mwh'], 0)} MWh."
            )
        else:
            rel = "över" if ytd_vs >= 0 else "under"
            out.append(
                f"Hittills i år uppgår produktionen till "
                f"{fmt_num(kpis['ytd_energy_mwh'], 0)} MWh, "
                f"{fmt_num(abs(ytd_vs), 1)} % {rel} budget "
                f"({fmt_num(kpis.get('ytd_budget_mwh'), 0)} MWh)."
            )

    # 4. Datakvalitet före allt annat — annars capture
    flagged = [r["name"] for r in rows if r.get("dq_flag")]
    if flagged:
        namn = ", ".join(sorted(flagged))
        subject = "parken" if len(flagged) == 1 else "parkerna"
        out.append(
            f"Instrålningsdata saknas för {namn} i {period.get('month_label') or label}"
            f" — den redovisade avvikelsen är verklig, men orsaksanalysen för "
            f"{subject} är osäker och siffran ska läsas med det förbehållet."
        )
    elif kpis.get("capture_eur_mwh") is not None:
        prem = kpis.get("capture_premium_pct")
        if prem is None:
            out.append(
                f"Realiserat capture-pris uppgick till "
                f"{fmt_num(kpis['capture_eur_mwh'], 1)} €/MWh."
            )
        else:
            rel = "över" if prem >= 0 else "under"
            out.append(
                f"Realiserat capture-pris uppgick till "
                f"{fmt_num(kpis['capture_eur_mwh'], 1)} €/MWh, "
                f"{fmt_num(abs(prem), 0)} % {rel} periodens baseload "
                f"({fmt_num(kpis.get('baseload_eur_mwh'), 1)} €/MWh)."
            )

    return out


# ---------------------------------------------------------------------------
# Huvudingång
# ---------------------------------------------------------------------------

def build_investor_data(
    year: Optional[int] = None,
    month: Optional[int] = None,
    *,
    parkoversikt: Optional[dict] = None,
    obalans: Optional[dict] = None,
    market: Optional[dict] = None,
) -> Dict[str, Any]:
    """Bygg hela investerarrapportens datastruktur.

    Args:
        year, month: rapportmånad. Utelämnas båda används senaste
            stängda månaden i portföljen.
        parkoversikt, obalans, market: förberäknade indata (för test och
            snabb iteration). Saknas de byggs de från källmodulerna.

    Returns:
        dict med ``period``, ``portfolio``, ``parks``, ``history``,
        ``ppa``, ``imbalance``, ``market``, ``summary``, ``method``.
    """
    if parkoversikt is None:
        from .parkoversikt import build_parkoversikt_data
        parkoversikt = build_parkoversikt_data()

    parks_raw: Dict[str, dict] = parkoversikt.get("parks") or {}

    if year is None or month is None:
        period = latest_closed_period(parkoversikt)
        if period is None:
            year, month = date.today().year, date.today().month
        else:
            year, month = period

    rows = build_park_rows(parks_raw, year, month)
    kpis = build_portfolio_kpis(rows)

    if market is None:
        market = build_market_stats({year, year - 1})
    if obalans is None:
        from .obalans import build_obalans_data
        try:
            obalans = build_obalans_data(months_back=14)
        except Exception:  # pragma: no cover - datakälla kan saknas
            obalans = None

    data: Dict[str, Any] = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "period": {
            "year": year,
            "month": month,
            "month_key": _key(year, month),
            "month_label": _month_name(month),
            "label": f"{_month_name(month)} {year}",
            "label_cap": f"{_month_name(month, capitalize=True)} {year}",
        },
        "portfolio": kpis,
        "parks": rows,
        "history": build_history(parks_raw, year, month),
        "ppa": build_ppa_effect(parks_raw, year, month),
        "imbalance": build_imbalance_summary(obalans),
        "market": build_market_context(
            market, year, month,
            portfolio_zones={r["zone"] for r in rows if r.get("zone")},
        ),
        "method": {
            "budget": (
                "Budget är PVsyst TMY per park (manuella justeringar enligt "
                "PARK_BUDGET_OVERRIDES). Månadsbudgeten är oreviderad — "
                "avvikelser mot budget är alltså både väder och drift."
            ),
            "capture": (
                "Capture-pris = intäkt dividerat med producerad volym, "
                "beräknat per 15-minutersintervall mot day ahead-spot i "
                "parkens elområde. Baseload är samma periods enkla "
                "tidsmedelvärde av spotpriset."
            ),
            "imbalance": (
                "Obalanskostnad är simulerad mot eSett-avräkningspriser för "
                "två prognosansatser (D-1-persistens respektive budgetform) "
                "och redovisas därför som ett spann, inte ett utfall."
            ),
            "source": (
                "Produktion från Bazefield (15 min), spotpris från "
                "elprisetjustnu.se, obalanspriser från eSett."
            ),
        },
    }
    data["summary"] = build_executive_summary(data)
    return data


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _esc(s: Any) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _delta_cls(value: Optional[float], tol: float = BUDGET_TOLERANCE_PCT) -> str:
    if value is None:
        return ""
    if abs(value) <= tol:
        return " neutral"
    return " pos" if value > 0 else " neg"


def _kpi(label: str, value: str, sub: str = "", cls: str = "") -> str:
    sub_html = f'<div class="sub{cls}">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi"><div class="lbl">{_esc(label)}</div>'
        f'<div class="val">{value}</div>{sub_html}</div>'
    )


def _render_history_svg(history: List[dict]) -> str:
    """13-månaders stapelgraf som ren inline-SVG (ingen JS, ingen CDN).

    Staplar = faktisk produktion, vit markering = budget för samma månad.
    """
    if not history:
        return '<p class="empty">Ingen historik tillgänglig.</p>'

    w, h = 980, 300
    pad_l, pad_r, pad_t, pad_b = 56, 12, 18, 46
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    peak = max(
        [m["energy_mwh"] for m in history]
        + [m["budget_mwh"] or 0.0 for m in history]
    )
    if peak <= 0:
        peak = 1.0
    # Runda upp till snygg skala
    step = 10 ** (len(str(int(peak))) - 1)
    top = step
    while top < peak:
        top += step / 2.0
    n = len(history)
    slot = plot_w / n
    bar_w = min(slot * 0.56, 46.0)

    def y_of(v: float) -> float:
        return pad_t + plot_h - (v / top) * plot_h

    parts: List[str] = [
        f'<svg viewBox="0 0 {w} {h}" role="img" class="chart" '
        f'aria-label="Produktion per månad mot budget" '
        f'xmlns="http://www.w3.org/2000/svg">'
    ]

    # Gridlinjer + y-etiketter
    ticks = 4
    for i in range(ticks + 1):
        v = top * i / ticks
        y = y_of(v)
        parts.append(
            f'<line class="grid" x1="{pad_l}" y1="{y:.1f}" '
            f'x2="{w - pad_r}" y2="{y:.1f}"/>'
        )
        parts.append(
            f'<text class="ytick" x="{pad_l - 8}" y="{y + 4:.1f}" '
            f'text-anchor="end">{_esc(fmt_num(v, 0))}</text>'
        )

    for i, m in enumerate(history):
        cx = pad_l + slot * (i + 0.5)
        x = cx - bar_w / 2
        y = y_of(m["energy_mwh"])
        bh = max(pad_t + plot_h - y, 0.6)
        cls = "bar report" if m.get("is_report_month") else "bar"
        parts.append(
            f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" '
            f'width="{bar_w:.1f}" height="{bh:.1f}" rx="2"/>'
        )
        if m.get("budget_mwh"):
            by = y_of(m["budget_mwh"])
            parts.append(
                f'<line class="budget" x1="{x - 3:.1f}" y1="{by:.1f}" '
                f'x2="{x + bar_w + 3:.1f}" y2="{by:.1f}"/>'
            )
        parts.append(
            f'<text class="xtick" x="{cx:.1f}" y="{h - pad_b + 18:.0f}" '
            f'text-anchor="middle">{_esc(m["label"])}</text>'
        )
        if i == 0 or m["label"] == "jan":
            parts.append(
                f'<text class="xyear" x="{cx:.1f}" y="{h - pad_b + 32:.0f}" '
                f'text-anchor="middle">{_esc(m["year_label"])}</text>'
            )

    parts.append(
        f'<line class="axis" x1="{pad_l}" y1="{pad_t + plot_h:.1f}" '
        f'x2="{w - pad_r}" y2="{pad_t + plot_h:.1f}"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _render_park_table(rows: List[dict], period_label: str) -> str:
    head = (
        "<thead><tr>"
        "<th>Park</th><th>Zon</th><th>MWp</th>"
        f"<th>{_esc(period_label)} MWh</th><th>Budget MWh</th><th>Mot budget</th>"
        "<th>Hittills i år MWh</th><th>Mot budget YTD</th><th>Kommentar</th>"
        "</tr></thead>"
    )
    body: List[str] = []
    for r in rows:
        if not r.get("has_month"):
            comment = "Ingen stängd data för månaden"
        else:
            if r.get("dq_flag"):
                comment = "Instrålningsdata saknas — orsaken kan inte fastställas"
            elif r.get("cause"):
                comment = r["cause"][0].upper() + r["cause"][1:]
            else:
                comment = "I linje med budget"
        body.append(
            "<tr>"
            f'<td class="park">{_esc(r["name"])}</td>'
            f'<td>{_esc(r["zone"])}</td>'
            f'<td>{_esc(fmt_num(r.get("capacity_mwp"), 1))}</td>'
            f'<td>{_esc(fmt_num(r.get("energy_mwh"), 0))}</td>'
            f'<td>{_esc(fmt_num(r.get("budget_mwh"), 0))}</td>'
            f'<td class="d{_delta_cls(r.get("vs_budget_pct"))}">'
            f'{_esc(fmt_signed_pct(r.get("vs_budget_pct")))}</td>'
            f'<td>{_esc(fmt_num(r.get("ytd_energy_mwh"), 0))}</td>'
            f'<td class="d{_delta_cls(r.get("ytd_vs_budget_pct"))}">'
            f'{_esc(fmt_signed_pct(r.get("ytd_vs_budget_pct")))}</td>'
            f'<td class="note">{_esc(comment)}</td>'
            "</tr>"
        )
    return (
        '<div class="tbl-wrap"><table>' + head
        + "<tbody>" + "".join(body) + "</tbody></table></div>"
    )


def render_investor_html(data: dict) -> str:
    """Rendera investerarrapporten som fristående HTML (utan externa beroenden)."""
    period = data.get("period") or {}
    kpis = data.get("portfolio") or {}
    rows = data.get("parks") or []
    label = period.get("label", "")
    label_cap = period.get("label_cap", label)

    summary_html = "".join(
        f"<p>{_esc(s)}</p>" for s in (data.get("summary") or [])
    )

    # --- KPI-rad -----------------------------------------------------------
    kpi_cards = [
        _kpi(
            f"Produktion {label}",
            f'{_esc(fmt_num(kpis.get("energy_mwh"), 0))} <span class="unit">MWh</span>',
            f'{_esc(fmt_signed_pct(kpis.get("vs_budget_pct")))} mot budget '
            f'{_esc(fmt_num(kpis.get("budget_mwh"), 0))} MWh',
            _delta_cls(kpis.get("vs_budget_pct")),
        ),
        _kpi(
            f'Hittills {period.get("year", "")}',
            f'{_esc(fmt_num(kpis.get("ytd_energy_mwh"), 0))} <span class="unit">MWh</span>',
            f'{_esc(fmt_signed_pct(kpis.get("ytd_vs_budget_pct")))} mot budget '
            f'{_esc(fmt_num(kpis.get("ytd_budget_mwh"), 0))} MWh',
            _delta_cls(kpis.get("ytd_vs_budget_pct")),
        ),
    ]
    if kpis.get("capture_eur_mwh") is not None:
        kpi_cards.append(_kpi(
            "Realiserat capture",
            f'{_esc(fmt_num(kpis["capture_eur_mwh"], 1))} <span class="unit">€/MWh</span>',
            f'{_esc(fmt_signed_pct(kpis.get("capture_premium_pct"), 0))} mot '
            f'baseload {_esc(fmt_num(kpis.get("baseload_eur_mwh"), 1))} €/MWh',
            _delta_cls(kpis.get("capture_premium_pct"), tol=0.0),
        ))
    if kpis.get("revenue_eur") is not None:
        rev_ppa = kpis.get("revenue_eur_ppa")
        sub = (
            f'Med PPA-bok {_esc(fmt_num(rev_ppa / 1000.0, 0))} k€'
            if rev_ppa is not None else "Ren spotförsäljning"
        )
        kpi_cards.append(_kpi(
            f"Intäkt {label} (spot)",
            f'{_esc(fmt_num(kpis["revenue_eur"] / 1000.0, 0))} <span class="unit">k€</span>',
            sub,
        ))
    kpi_cards.append(_kpi(
        "Portfölj",
        f'{_esc(fmt_num(kpis.get("capacity_mwp"), 1))} <span class="unit">MWp</span>',
        f'{kpis.get("reporting_park_count", 0)} av {kpis.get("park_count", 0)} '
        "parker med stängd månad",
    ))

    # --- Sidoblock: PPA, obalans, marknad ----------------------------------
    blocks: List[str] = []
    ppa = data.get("ppa")
    if ppa:
        sign = "tillfört" if ppa["uplift_eur"] >= 0 else "kostat"
        cls = "pos" if ppa["uplift_eur"] >= 0 else "neg"
        pct = (
            f' ({_esc(fmt_signed_pct(ppa.get("uplift_pct"), 1))} mot ren spot)'
            if ppa.get("uplift_pct") is not None else ""
        )
        blocks.append(
            '<div class="block"><h3>PPA-boken</h3>'
            f'<p class="lead {cls}">{_esc(fmt_num(abs(ppa["uplift_eur"]) / 1000.0, 0))} k€ '
            f'{sign} hittills {period.get("year", "")}</p>'
            f'<p>Jämfört med att sälja hela volymen på spot har PPA-kontrakten '
            f'{sign} {_esc(fmt_num(abs(ppa["uplift_eur"]) / 1000.0, 0))} k€ '
            f'över {ppa["park_count"]} parker{pct}.</p></div>'
        )
    imb = data.get("imbalance")
    if imb:
        blocks.append(
            '<div class="block"><h3>Obalanskostnad, senaste 12 mån</h3>'
            f'<p class="lead">{_esc(fmt_num(imb["low_eur"] / 1000.0, 0))}–'
            f'{_esc(fmt_num(imb["high_eur"] / 1000.0, 0))} k€</p>'
            f'<p>Motsvarar {_esc(fmt_num(imb["low_eur_mwh"], 1))}–'
            f'{_esc(fmt_num(imb["high_eur_mwh"], 1))} €/MWh producerad över '
            f'{imb.get("park_count", 0)} parker, rullande fram till senaste '
            'avräknade månad. Spannet speglar prognoskvalitet: den lägre '
            'änden motsvarar en bättre prognos än den högre.</p></div>'
        )
    market = data.get("market")
    if market:
        sent = " ".join(market.get("sentences") or [])
        blocks.append(
            '<div class="block"><h3>Marknaden</h3>'
            f"<p>{_esc(sent)}</p></div>"
        )
    blocks_html = (
        f'<div class="blocks">{"".join(blocks)}</div>' if blocks else ""
    )

    method = data.get("method") or {}
    method_html = "".join(
        f"<li>{_esc(method[k])}</li>"
        for k in ("budget", "capture", "imbalance", "source")
        if method.get(k)
    )

    legend = (
        '<div class="legend">'
        '<span><i class="sw-bar"></i>Faktisk produktion</span>'
        '<span><i class="sw-budget"></i>Budget (PVsyst TMY)</span>'
        "</div>"
    )

    return _SHELL.format(
        title=_esc(f"Investerarrapport {label_cap}"),
        css=_CSS,
        label=_esc(label),
        label_cap=_esc(label_cap),
        generated=_esc((data.get("generated") or "")[:16].replace("T", " ")),
        summary=summary_html,
        kpis="".join(kpi_cards),
        chart=_render_history_svg(data.get("history") or []),
        chart_months=len(data.get("history") or []),
        legend=legend,
        table=_render_park_table(rows, period.get("month_label", "").capitalize()),
        blocks=blocks_html,
        method=method_html,
    )


_SHELL = """<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Svea Solar</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%230e7c86'/%3E%3Cpath d='M8 22 13 14 18 18 24 9' stroke='%23de9b26' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<style>{css}</style>
</head>
<body>
<article class="page">

  <header class="masthead">
    <div class="brand"><span class="mark"></span>
      <div><div class="bt">Svea Solar</div>
      <div class="bs">Solportfölj · investerarrapport</div></div></div>
    <div class="period">{label_cap}</div>
  </header>

  <section class="hero">
    <div class="kicker">Sammanfattning</div>
    <h1>Portföljens utfall i {label}</h1>
    <div class="lede">{summary}</div>
  </section>

  <section class="kpi-strip">{kpis}</section>

  <section class="card chart-card">
    <div class="card-head">
      <h2>Produktion mot budget, senaste {chart_months} månaderna</h2>
      <p>MWh per månad för hela portföljen. Budgetnivån är PVsyst TMY,
         oreviderad för faktiskt väder.</p>
    </div>
    {chart}
    {legend}
  </section>

  <section class="card table-card">
    <div class="card-head">
      <h2>Parkerna</h2>
      <p>Utfall per park för månaden och för året hittills. Avvikelser
         redovisas som de är; kommentaren namnger den dominerande posten i
         förlustkaskaden när en sådan kan pekas ut.</p>
    </div>
    {table}
  </section>

  {blocks}

  <footer class="foot">
    <div class="foot-h">Metod och källor</div>
    <ul>{method}</ul>
    <p class="gen">Genererad {generated} ur Svea Solars interna
      analyssystem. Siffrorna är oreviderade.</p>
  </footer>

</article>
</body>
</html>
"""


# Nordic Clarity-tokens, kopierade från insikt/render.py och anpassade för
# en utskriftsvänlig ensidesrapport (inga interaktiva tillstånd, A4-regler).
_CSS = r"""
:root {
  --bg: #f6f8f9;
  --card: #ffffff;
  --ink: #16242f;
  --muted: #5b6b78;
  --faint: #8a98a4;
  --line: #e3e9ed;
  --teal: #0e7c86;
  --teal-deep: #0a5961;
  --teal-soft: #d8ecee;
  --amber: #de9b26;
  --coral: #d95f4c;
  --green: #2e9e6b;
  --navy: #1d3a4f;
  --radius: 10px;
  --shadow: 0 1px 2px rgba(22,36,47,.05), 0 4px 16px rgba(22,36,47,.06);
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI',
    Helvetica, Arial, sans-serif;
  font-size: 14.5px; line-height: 1.55; -webkit-font-smoothing: antialiased;
}
.page { max-width: 1080px; margin: 0 auto; padding: 24px 28px 56px; }

/* ---------- Masthead ---------- */
.masthead {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding-bottom: 14px; border-bottom: 2px solid var(--navy);
}
.brand { display: flex; align-items: center; gap: 12px; }
.mark {
  width: 34px; height: 34px; border-radius: 9px; flex: 0 0 auto;
  background: conic-gradient(from 220deg, var(--teal-deep), var(--teal) 55%, var(--amber));
}
.bt { font-weight: 700; font-size: 15px; letter-spacing: -.01em; }
.bs { font-size: 11.5px; color: var(--faint); }
.period {
  font-size: 13px; font-weight: 700; color: var(--navy);
  text-transform: uppercase; letter-spacing: .1em;
}

/* ---------- Hero ---------- */
.hero { padding: 26px 0 6px; max-width: 860px; }
.kicker {
  text-transform: uppercase; letter-spacing: .14em; font-size: 11px;
  font-weight: 700; color: var(--teal); margin-bottom: 6px;
}
h1 { margin: 0 0 12px; font-size: 32px; font-weight: 800;
  letter-spacing: -.02em; line-height: 1.15; }
.lede p {
  margin: 0 0 9px; font-family: Georgia, 'Source Serif 4', serif;
  font-size: 16px; line-height: 1.6;
}
.lede p:first-child { font-size: 17.5px; }

/* ---------- KPI ---------- */
.kpi-strip {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px; margin: 20px 0 24px;
}
.kpi {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 14px 16px; box-shadow: var(--shadow);
}
.kpi .lbl { font-size: 10.5px; text-transform: uppercase; letter-spacing: .09em;
  color: var(--faint); font-weight: 700; }
.kpi .val { font-size: 25px; font-weight: 800; letter-spacing: -.02em;
  font-variant-numeric: tabular-nums; margin-top: 3px; }
.kpi .val .unit { font-size: 13px; font-weight: 600; color: var(--faint); }
.kpi .sub { font-size: 12px; color: var(--muted); margin-top: 3px;
  font-variant-numeric: tabular-nums; }
.kpi .sub.pos { color: var(--green); font-weight: 600; }
.kpi .sub.neg { color: var(--coral); font-weight: 600; }
.kpi .sub.neutral { color: var(--muted); }

/* ---------- Kort ---------- */
.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: var(--shadow);
  padding: 16px 18px 14px; margin-bottom: 20px;
}
.card-head h2 { margin: 0 0 4px; font-size: 17px; font-weight: 800;
  letter-spacing: -.015em; }
.card-head p { margin: 0 0 12px; color: var(--muted); font-size: 12.5px;
  max-width: 74ch; }

/* ---------- Graf ---------- */
.chart { width: 100%; height: auto; display: block; }
.chart .bar { fill: var(--teal); }
.chart .bar.report { fill: var(--navy); }
.chart .budget { stroke: var(--amber); stroke-width: 2; }
.chart .grid { stroke: var(--line); stroke-width: 1; }
.chart .axis { stroke: var(--muted); stroke-width: 1; }
.chart .ytick, .chart .xtick, .chart .xyear {
  font-family: 'Inter', Helvetica, Arial, sans-serif; fill: var(--faint);
  font-size: 11px; font-variant-numeric: tabular-nums;
}
.chart .xtick { fill: var(--muted); }
.legend { display: flex; gap: 18px; font-size: 12px; color: var(--muted);
  margin-top: 4px; padding-left: 56px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { display: inline-block; }
.sw-bar { width: 12px; height: 12px; border-radius: 2px; background: var(--teal); }
.sw-budget { width: 14px; height: 3px; background: var(--amber); }

/* ---------- Tabell ---------- */
.tbl-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { padding: 8px 10px; text-align: right; white-space: nowrap;
  font-variant-numeric: tabular-nums; }
th:first-child, td:first-child { text-align: left; }
thead th {
  border-bottom: 2px solid var(--ink); font-size: 10.5px;
  text-transform: uppercase; letter-spacing: .06em; color: var(--muted);
}
tbody tr { border-bottom: 1px solid var(--line); }
td.park { font-weight: 600; }
td.d.pos { color: var(--green); font-weight: 600; }
td.d.neg { color: var(--coral); font-weight: 600; }
td.d.neutral { color: var(--muted); }
td.note { text-align: left; white-space: normal; color: var(--muted);
  font-size: 12px; max-width: 34ch; }

/* ---------- Sidoblock ---------- */
.blocks { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px; margin-bottom: 20px; }
.block {
  background: var(--card); border: 1px solid var(--line);
  border-left: 4px solid var(--teal); border-radius: var(--radius);
  padding: 14px 16px; box-shadow: var(--shadow);
}
.block h3 { margin: 0 0 6px; font-size: 13px; text-transform: uppercase;
  letter-spacing: .08em; color: var(--teal-deep); }
.block p { margin: 0 0 6px; font-size: 13px; color: var(--muted); }
.block .lead { font-size: 21px; font-weight: 800; color: var(--ink);
  letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
.block .lead.pos { color: var(--green); }
.block .lead.neg { color: var(--coral); }
.empty { color: var(--faint); font-size: 13px; }

/* ---------- Sidfot ---------- */
.foot { border-top: 1px solid var(--line); padding-top: 14px;
  color: var(--faint); font-size: 11.5px; }
.foot-h { text-transform: uppercase; letter-spacing: .1em; font-weight: 700;
  font-size: 10.5px; color: var(--muted); margin-bottom: 6px; }
.foot ul { margin: 0 0 8px; padding-left: 18px; }
.foot li { margin-bottom: 3px; max-width: 92ch; }
.foot .gen { margin: 0; }

/* ---------- Utskrift: A4, inga skuggor, kontrollerade sidbrytningar ------ */
@page { size: A4 portrait; margin: 14mm 12mm; }
@media print {
  body { background: #fff; font-size: 9.5pt; }
  .page { max-width: none; padding: 0; }
  .card, .kpi, .block {
    box-shadow: none; border: 1px solid #d7dee3;
    break-inside: avoid; page-break-inside: avoid;
  }
  .kpi-strip, .blocks {
    break-inside: avoid; page-break-inside: avoid; gap: 8px;
  }
  .hero { break-after: avoid; page-break-after: avoid; padding: 16px 0 4px; }
  h1 { font-size: 20pt; }
  .lede p, .lede p:first-child { font-size: 10pt; }
  .kpi-strip { grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
    margin: 14px 0 16px; }
  .kpi { padding: 9px 10px; }
  .kpi .val { font-size: 14pt; }
  .kpi .lbl { font-size: 7pt; }
  .kpi .sub { font-size: 8pt; }
  .card { margin-bottom: 14px; padding: 12px 14px 10px; }
  .card-head h2 { font-size: 12pt; }
  .card-head p { font-size: 8.5pt; }
  /* Tabellen ska rymmas på A4-bredden — utskriften har ingen horisontell
     scroll, så bara kommentarskolumnen tillåts radbryta. */
  .tbl-wrap { overflow: visible; }
  table { font-size: 8pt; }
  th, td { padding: 4px 5px; }
  td.note, thead th:last-child { white-space: normal; width: 22%;
    font-size: 7.5pt; max-width: none; }
  /* Låt parktabellens kort flyta över sidbrytning — raderna hålls hela.
     Annars skjuts hela kortet till nästa sida och lämnar en tom halvsida. */
  .table-card { break-inside: auto; page-break-inside: auto; }
  .table-card tr { break-inside: avoid; page-break-inside: avoid; }
  .legend { font-size: 8pt; padding-left: 40px; }
  .blocks { grid-template-columns: repeat(3, 1fr); }
  .block { padding: 10px 12px; }
  .block h3 { font-size: 9pt; }
  .block p { font-size: 8.5pt; }
  .block .lead { font-size: 14pt; }
  .foot { break-before: avoid; page-break-before: avoid; font-size: 7.5pt; }
  a[href]:after { content: ""; }
}
"""
