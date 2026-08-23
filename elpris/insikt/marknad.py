"""Marknad & intäkt — data för Insikts andra sektion.

Fyra block, vart och ett med klartextinsikter överst (designprincipen i
docs/plans/2026-08-22-insikt-produkt-spec.md):

1. **Intäkt & PPA** — fleet-capture vs baseload per månad (13 mån),
   PPA-effekt i k€ YTD och PPA-boken mot senaste forward
   (återanvänder :func:`elpris.rework_portfolio.build_ppa_view`).
2. **Obalanskostnad** — per-park-aggregat senaste 12 mån ur
   :mod:`elpris.insikt.obalans` (spann persistens↔budgetform).
3. **Kannibalisering** — regression + framskrivning ur
   :mod:`elpris.insikt.kannibalisering`.
4. **Forward-läge** — konvergensserier + lookback-tabell ur
   ``dashboard_v2_data.load_forward_curve_data``:s ``forward_history``
   (layout enligt "Kort A"/"Kort B" i
   docs/plans/2026-05-03-futures-historical-tracking-design.md — de
   korten landar HÄR, inte i unified).

Payload-beskärning (dokumenterad):

* Obalans: bara ``last12``-aggregatet per park behålls (månadsraderna
  behövs inte i UI:t).
* Konvergensserierna decimeras med :func:`decimate_series` — dagliga
  punkter de sista 365 dagarna före leveransstart, veckovis (första
  handelsdagen per ISO-vecka) dessförinnan. Sista punkten behålls alltid.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from ..config import ZONES
from ..rework_portfolio import build_ppa_view, fmt_num
from .obalans import build_obalans_data, build_obalans_insights
from .kannibalisering import (
    build_kannibalisering_data,
    build_kannibalisering_insights,
)

# Dagliga punkter behålls så här många dagar före leveransstart;
# tidigare historik decimeras till en punkt per ISO-vecka.
DAILY_WINDOW_DAYS = 365

# T-fönster i lookback-tabellen: månader före leveransstart.
LOOKBACK_MONTHS = (12, 6, 3, 1)
# Största avstånd (dagar) mellan målfönstret och närmaste settlement-dag.
LOOKBACK_TOLERANCE_DAYS = 7


# ---------------------------------------------------------------------------
# Intäkt & PPA
# ---------------------------------------------------------------------------

def build_fleet_revenue_series(parks: Dict[str, dict]) -> List[dict]:
    """Volymviktad fleet-serie per månad: capture, capture med PPA, baseload.

    Som :func:`elpris.rework_portfolio.build_fleet_series` men med
    volymviktad ``baseload_eur_mwh`` (behövs för capture-vs-baseload-
    beviset). Månader utan intäktsdata utelämnas.

    Returns:
        [{"month": "YYYY-MM", "capture", "capture_ppa", "baseload",
          "volume_mwh", "is_partial"}, ...] äldst → nyast.
    """
    acc: Dict[str, dict] = {}
    for park in (parks or {}).values():
        for m in park.get("months", []):
            rev = m.get("revenue_eur")
            vol = m.get("bazefield_volume_mwh")
            if rev is None or vol is None or vol <= 0:
                continue
            key = f"{m['year']}-{m['month']:02d}"
            a = acc.setdefault(key, {
                "rev": 0.0, "rev_ppa": 0.0, "vol": 0.0,
                "base_w": 0.0, "base_vol": 0.0, "partial": False,
            })
            a["rev"] += rev
            rev_ppa = m.get("revenue_eur_ppa")
            a["rev_ppa"] += rev_ppa if rev_ppa is not None else rev
            a["vol"] += vol
            base = m.get("baseload_eur_mwh")
            if base is not None:
                a["base_w"] += base * vol
                a["base_vol"] += vol
            if m.get("is_partial"):
                a["partial"] = True

    out: List[dict] = []
    for key in sorted(acc):
        a = acc[key]
        out.append({
            "month": key,
            "capture": round(a["rev"] / a["vol"], 2),
            "capture_ppa": round(a["rev_ppa"] / a["vol"], 2),
            "baseload": (
                round(a["base_w"] / a["base_vol"], 2)
                if a["base_vol"] > 0 else None
            ),
            "volume_mwh": round(a["vol"], 1),
            "is_partial": a["partial"],
        })
    return out


def _ppa_uplift_ytd(parks: Dict[str, dict]) -> Optional[dict]:
    """PPA-effekt (rev_ppa − rev_spot) summerad över innevarande år."""
    years = [
        m["year"]
        for p in (parks or {}).values()
        for m in p.get("months", [])
    ]
    if not years:
        return None
    year = max(years)
    uplift = 0.0
    has = False
    for p in parks.values():
        for m in p.get("months", []):
            if m.get("year") != year:
                continue
            rev = m.get("revenue_eur")
            rev_ppa = m.get("revenue_eur_ppa")
            if rev is not None and rev_ppa is not None:
                uplift += rev_ppa - rev
                has = True
    if not has:
        return None
    return {"year": year, "uplift_eur": round(uplift, 0)}


def build_intakt_insights(
    fleet_series: List[dict],
    ppa_uplift: Optional[dict],
    ppa_view: dict,
) -> List[dict]:
    """Mallinsikter för intäktsblocket: capture-läge, PPA-effekt, PPA-bok."""
    insights: List[dict] = []

    closed = [
        m for m in fleet_series
        if not m.get("is_partial") and m.get("capture") is not None
    ]
    if closed:
        m = closed[-1]
        base = m.get("baseload")
        if base:
            prem = (m["capture"] / base - 1.0) * 100.0
            rel = "över" if prem >= 0 else "under"
            insights.append({
                "text": (
                    f"Senaste stängda månaden ({m['month']}) realiserade "
                    f"portföljen {fmt_num(m['capture'], 1)} €/MWh mot "
                    f"baseload {fmt_num(base, 1)} €/MWh — "
                    f"{fmt_num(abs(prem), 0)} % {rel} baseload. Gapet är "
                    "solens kannibalisering i praktiken: produktionen "
                    "ligger i timmarna då priset pressas."
                ),
                "tone": "neg" if prem < -3 else (
                    "pos" if prem > 3 else "neutral"
                ),
            })

    if ppa_uplift is not None:
        u = ppa_uplift["uplift_eur"]
        verb = "tillfört" if u >= 0 else "kostat"
        insights.append({
            "text": (
                f"PPA-kontrakten har {verb} "
                f"{fmt_num(abs(u) / 1000.0, 1)} k€ hittills "
                f"{ppa_uplift['year']} relativt ren spotförsäljning — "
                "fasta priser i SEK skyddar nedsidan så länge spot ligger "
                "under kontraktsnivåerna."
            ),
            "tone": "pos" if u > 0 else ("neg" if u < 0 else "neutral"),
        })

    rows = [
        r for r in ppa_view.get("rows", [])
        if r.get("has_ppa")
        and r.get("ppa_price_eur_mwh") is not None
        and r.get("fwd_eur_mwh") is not None
    ]
    if rows:
        itm = [r for r in rows if r["ppa_price_eur_mwh"] > r["fwd_eur_mwh"]]
        fwd_label = ppa_view.get("fwd_label") or "forward"
        insights.append({
            "text": (
                f"{len(itm)} av {len(rows)} PPA-kontrakt ligger över "
                f"terminsmarknadens {fwd_label} för sin zon — boken är "
                f"{'in' if len(itm) >= (len(rows) + 1) // 2 else 'out of'}"
                "-the-money mot att sälja samma volym på forward idag. "
                "Jämförelsen är baseload mot solprofil och överskattar "
                "därmed PPA-fördelen något."
            ),
            "tone": "pos" if len(itm) >= (len(rows) + 1) // 2 else "neutral",
        })

    if not insights:
        insights.append({
            "text": "Ingen intäktsdata tillgänglig ännu.",
            "tone": "neutral",
        })
    return insights


# ---------------------------------------------------------------------------
# Forward: decimering + lookback
# ---------------------------------------------------------------------------

def decimate_series(
    series: List[dict],
    delivery_start: str,
    daily_window_days: int = DAILY_WINDOW_DAYS,
) -> List[dict]:
    """Decimera en daglig settlement-serie för konvergensgrafen.

    Punkter inom ``daily_window_days`` dagar före ``delivery_start``
    behålls dagligt; äldre historik decimeras till första handelsdagen
    per ISO-vecka. Sista punkten i serien behålls alltid (den kan vara
    slutfixen).

    Args:
        series: [{"date": "YYYY-MM-DD", "price": float}, ...] sorterad.
        delivery_start: kontraktets leveransstart (ISO-datum).

    Returns:
        Beskuren lista, samma format och ordning.
    """
    if not series:
        return []
    cutoff = (
        date.fromisoformat(delivery_start)
        - timedelta(days=daily_window_days)
    ).isoformat()

    out: List[dict] = []
    seen_weeks: set = set()
    last_idx = len(series) - 1
    for i, rec in enumerate(series):
        d = rec["date"]
        if d >= cutoff or i == last_idx:
            out.append(rec)
            continue
        iso = date.fromisoformat(d).isocalendar()
        wk = (iso[0], iso[1])
        if wk not in seen_weeks:
            seen_weeks.add(wk)
            out.append(rec)
    return out


def _shift_months(d: date, months_back: int) -> date:
    """Datum ``months_back`` kalendermånader före ``d`` (dag klampas)."""
    y = d.year
    m = d.month - months_back
    while m <= 0:
        m += 12
        y -= 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
                      else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, day)


def _implied_by_date(
    sys_series: List[dict], epad_series: List[dict]
) -> Dict[str, float]:
    """Zone-implied (SYS + EPAD) per datum där båda serierna har fix."""
    epad = {r["date"]: r["price"] for r in epad_series or []}
    out: Dict[str, float] = {}
    for r in sys_series or []:
        e = epad.get(r["date"])
        if e is not None:
            out[r["date"]] = r["price"] + e
    return out


def lookback_value(
    implied_by_date: Dict[str, float],
    delivery_start: str,
    months_before: int,
    tolerance_days: int = LOOKBACK_TOLERANCE_DAYS,
) -> Optional[float]:
    """Zone-implied närmast ``delivery_start − months_before`` månader.

    Målet är kalendermånads-skiftat (T-3mo för leverans 1 apr = 1 jan);
    närmaste settlement-dag inom ±``tolerance_days`` dagar väljs. Vid
    lika avstånd vinner den tidigare dagen. ``None`` om ingen dag finns
    i fönstret.
    """
    if not implied_by_date:
        return None
    target = _shift_months(date.fromisoformat(delivery_start), months_before)
    best: Optional[tuple] = None
    for d_str, price in implied_by_date.items():
        dist = abs((date.fromisoformat(d_str) - target).days)
        if dist > tolerance_days:
            continue
        key = (dist, d_str)
        if best is None or key < best[0]:
            best = (key, price)
    return round(best[1], 2) if best else None


def build_lookback_rows(
    forward_history: Dict[str, dict],
    today: Optional[date] = None,
) -> List[dict]:
    """Lookback-tabellens rader: en per (kontrakt, zon).

    Kolumner per rad: T-12/6/3/1-implied, final implied, realiserad spot,
    fel (final − realiserad) i €/MWh och %. ``delivered`` skiljer
    levererade kontrakt (helt utfall) från pågående (partiellt utfall —
    felet färgas inte i UI:t förrän leveransen är klar).
    """
    today = today or date.today()
    rows: List[dict] = []
    for label, h in (forward_history or {}).items():
        sys_series = h.get("sys_series") or []
        delivered = (h.get("delivery_end") or "") < today.isoformat()
        for zone in ZONES:
            epad_series = (h.get("epad_series") or {}).get(zone)
            if not epad_series:
                continue
            implied = _implied_by_date(sys_series, epad_series)
            if not implied:
                continue
            final_date = max(implied)
            final = round(implied[final_date], 2)
            realised = (h.get("realised_spot") or {}).get(zone)
            err = err_pct = None
            if realised is not None:
                err = round(final - realised, 2)
                if realised:
                    err_pct = round(100.0 * err / realised, 1)
            row = {
                "contract": label,
                "zone": zone,
                "delivery_start": h.get("delivery_start"),
                "delivery_end": h.get("delivery_end"),
                "delivered": delivered,
                "is_clean_final": h.get("is_clean_final"),
                "final": final,
                "final_date": final_date,
                "realised": realised,
                "error": err,
                "error_pct": err_pct,
            }
            for months in LOOKBACK_MONTHS:
                row[f"t{months}"] = lookback_value(
                    implied, h.get("delivery_start"), months
                )
            rows.append(row)
    rows.sort(key=lambda r: (r["delivery_start"] or "", r["zone"]),
              reverse=True)
    return rows


def build_forward_insights(
    lookback_rows: List[dict],
    forward_history: Dict[str, dict],
) -> List[dict]:
    """Mallinsikter för forwardblocket ur lookback-tabellen."""
    insights: List[dict] = []

    scored = [
        r for r in lookback_rows
        if r["delivered"] and r.get("is_clean_final")
        and r.get("error") is not None
    ]
    if scored:
        errs = [abs(r["error"]) for r in scored]
        mean_err = sum(errs) / len(errs)
        worst = max(scored, key=lambda r: abs(r["error"]))
        insights.append({
            "text": (
                f"För de levererade kontrakten med ren slutfix missade "
                f"terminsmarknaden utfallet med i snitt "
                f"{fmt_num(mean_err, 1)} €/MWh vid sista notering — mest i "
                f"{worst['contract']} {worst['zone']} "
                f"({fmt_num(worst['error'], 1)} €/MWh mot realiserat "
                f"{fmt_num(worst['realised'], 1)}). Forwardpriset är ett "
                "marknadsläge, inte en prognos med den precisionen."
            ),
            "tone": "neutral" if mean_err <= 5 else "neg",
        })

    stale = sorted(
        label for label, h in (forward_history or {}).items()
        if not h.get("is_clean_final")
    )
    if stale:
        insights.append({
            "text": (
                f"OBS: {', '.join(stale)} saknar slutnotering nära "
                "leveransstart — historiken slutade uppdateras i källan "
                "långt före leverans, så konvergensen kan inte utvärderas "
                "för de kontrakten."
            ),
            "tone": "neg",
        })

    ongoing = [
        (label, h) for label, h in (forward_history or {}).items()
        if (h.get("delivery_end") or "") >= date.today().isoformat()
    ]
    if ongoing:
        labels = ", ".join(sorted(l for l, _ in ongoing))
        insights.append({
            "text": (
                f"{labels} är i leverans nu — realiserat-strecket i grafen "
                "är hittills-snitt och flyttar sig tills perioden stängt."
            ),
            "tone": "neutral",
        })

    if not insights:
        insights.append({
            "text": (
                "Ingen forwardhistorik med levererade kontrakt ännu — "
                "konvergensen kan utvärderas först när ett kontrakt gått "
                "genom leverans."
            ),
            "tone": "neutral",
        })
    return insights


def _prune_forward_history(forward_history: Dict[str, dict]) -> Dict[str, dict]:
    """Beskär forward_history för inline-JSON: decimerade serier."""
    out: Dict[str, dict] = {}
    for label, h in (forward_history or {}).items():
        start = h.get("delivery_start") or "1970-01-01"
        out[label] = {
            "type": h.get("type"),
            "delivery_start": h.get("delivery_start"),
            "delivery_end": h.get("delivery_end"),
            "final_settlement_date": h.get("final_settlement_date"),
            "is_clean_final": h.get("is_clean_final"),
            "sys_series": decimate_series(h.get("sys_series") or [], start),
            "epad_series": {
                z: decimate_series(s or [], start)
                for z, s in (h.get("epad_series") or {}).items()
            },
            "realised_spot": h.get("realised_spot") or {},
        }
    return out


# ---------------------------------------------------------------------------
# Huvudingång
# ---------------------------------------------------------------------------

def _load_forward() -> Optional[dict]:
    """Ladda forwarddata (spot per zon + Nasdaq/Euronext-CSV:er)."""
    from ..dashboard_v2_data import load_forward_curve_data, load_spot_prices

    spot_data: Dict[str, dict] = {}
    for zone in ZONES:
        s = load_spot_prices(zone)
        if s:
            spot_data[zone] = s
    return load_forward_curve_data(spot_data)


def build_marknad_data(
    parks: Dict[str, dict],
    forward: Optional[dict] = None,
    obalans: Optional[dict] = None,
    kannibalisering: Optional[dict] = None,
) -> Dict[str, Any]:
    """Bygg hela datastrukturen för sektionen Marknad & intäkt.

    Args:
        parks: parkdata från :func:`build_parkoversikt_data` (månaderna
            bär redan revenue/PPA-fälten) — datainsamlingen körs EN gång
            i generate_insikt-flödet och delas mellan sektionerna.
        forward: valfri injicerad forwarddata (tester); annars laddas
            den via ``load_forward_curve_data``.
        obalans: valfri injicerad obalansdata (tester).
        kannibalisering: valfri injicerad kannibaliseringsdata (tester).
    """
    # --- Block 1: Intäkt & PPA ---
    if forward is None:
        forward = _load_forward()
    fleet_series = build_fleet_revenue_series(parks)
    ppa_uplift = _ppa_uplift_ytd(parks)
    ppa_view = build_ppa_view({"parks": parks}, forward)
    intakt = {
        "fleet_series": fleet_series,
        "ppa_uplift_ytd": ppa_uplift,
        "ppa_view": ppa_view,
        "insights": build_intakt_insights(fleet_series, ppa_uplift, ppa_view),
    }

    # --- Block 2: Obalanskostnad ---
    if obalans is None:
        obalans = build_obalans_data()
    obalans_parks = []
    for park_key, p in sorted((obalans.get("parks") or {}).items()):
        if not p.get("last12"):
            continue
        name = (parks.get(park_key) or {}).get("name") or park_key.capitalize()
        obalans_parks.append({
            "park": park_key,
            "name": name,
            "zone": p.get("zone"),
            "last12": p["last12"],
        })
    obalans_parks.sort(
        key=lambda r: -(r["last12"].get("cost_per_mwh_a") or 0.0)
    )
    obalans_block = {
        "parks": obalans_parks,
        "portfolio_last12": (obalans.get("portfolio") or {}).get("last12"),
        "method": obalans.get("method"),
        "insights": build_obalans_insights(obalans),
    }

    # --- Block 3: Kannibalisering ---
    if kannibalisering is None:
        kannibalisering = build_kannibalisering_data()
    kanni_block = {
        "zones": kannibalisering.get("zones"),
        "best_zone": kannibalisering.get("best_zone"),
        "assumptions": kannibalisering.get("assumptions"),
        "insights": build_kannibalisering_insights(kannibalisering),
    }

    # --- Block 4: Forward-läge ---
    history = (forward or {}).get("forward_history") or {}
    lookback = build_lookback_rows(history)
    forward_block = {
        "settlement_date": (forward or {}).get("settlement_date"),
        "history": _prune_forward_history(history),
        "lookback": lookback,
        "health": (forward or {}).get("forward_health")
        or {"stale_finals": [], "approaching_expiry": []},
        "insights": build_forward_insights(lookback, history),
    }

    return {
        "intakt": intakt,
        "obalans": obalans_block,
        "kannibalisering": kanni_block,
        "forward": forward_block,
    }
