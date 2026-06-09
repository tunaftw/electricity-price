"""Portföljaggregat, PPA-vy, datakvalitet och klartext-insikter.

Bygger på assets-sektionen från ``unified_dashboard_data`` (per-park
månads-KPI:er med budget, intäkt och negativpris-exponering) och
komponerar:

* **Flottserie** — portföljens produktion/budget/intäkt per månad.
* **YTD-läge** — innevarande års totaler + senaste stängda månad.
* **PPA-vy** — kontrakterade priser vs realiserad capture vs forward,
  samt YTD-uplift i EUR av hedgen.
* **Datakvalitet** — mätartäckning, stuck-value-dagar, availability-
  täckning per park (gör tyst sensorröta synlig).
* **Klartext-insikter** — svenska meningar med riktiga tal, beräknade
  i Python så att dashboarden kan läsas som en rapport.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Dict, List, Optional

from .config import PARK_CAPACITY_KWP, PARK_ZONES, PARKS_PROFILE_DIR
from .operations_dashboard_data import load_park_15min

# ---------------------------------------------------------------------------
# Talformatering (svenska)
# ---------------------------------------------------------------------------

_NBSP = "\u202f"  # smalt hårt mellanslag som tusentalsavgränsare


def fmt_num(value, decimals: int = 0) -> str:
    """Formatera tal svenskt: 12 345,6 (None → '–')."""
    if value is None:
        return "–"
    s = f"{float(value):,.{decimals}f}"
    return s.replace(",", _NBSP).replace(".", ",")


def fmt_signed_pct(value, decimals: int = 1) -> str:
    """Formatera procent med tecken: +4,2 % / −3,1 % (None → '–')."""
    if value is None:
        return "–"
    sign = "+" if value >= 0 else "−"
    return f"{sign}{fmt_num(abs(value), decimals)} %"


# ---------------------------------------------------------------------------
# Flottserie + YTD
# ---------------------------------------------------------------------------

def build_fleet_series(assets: dict) -> List[dict]:
    """Summera per-park-månader till en portföljserie.

    Returns:
        [{"month": "YYYY-MM", "energy_mwh", "budget_mwh", "vs_budget_pct",
          "revenue_eur", "revenue_ppa_eur", "volume_mwh", "capture",
          "capture_ppa", "is_partial"}, ...] sorterat äldst → nyast.
    """
    acc: Dict[str, dict] = defaultdict(
        lambda: {
            "energy": 0.0, "budget": 0.0, "rev": 0.0, "rev_ppa": 0.0,
            "vol": 0.0, "partial": False, "has_rev": False,
        }
    )
    parks = (assets or {}).get("parks", {})
    for park in parks.values():
        for m in park.get("months", []):
            key = f"{m['year']}-{m['month']:02d}"
            a = acc[key]
            a["energy"] += m.get("energy_mwh") or 0.0
            a["budget"] += m.get("budget_mwh") or 0.0
            if m.get("is_partial"):
                a["partial"] = True
            rev = m.get("revenue_eur")
            if rev is not None:
                a["rev"] += rev
                a["has_rev"] = True
                rev_ppa = m.get("revenue_eur_ppa")
                a["rev_ppa"] += rev_ppa if rev_ppa is not None else rev
            vol = m.get("bazefield_volume_mwh")
            if vol is not None:
                a["vol"] += vol

    out: List[dict] = []
    for key in sorted(acc):
        a = acc[key]
        vs = (
            round((a["energy"] / a["budget"] - 1.0) * 100.0, 1)
            if a["budget"] > 0 else None
        )
        capture = round(a["rev"] / a["vol"], 2) if a["vol"] > 0 else None
        capture_ppa = (
            round(a["rev_ppa"] / a["vol"], 2) if a["vol"] > 0 else None
        )
        out.append({
            "month": key,
            "energy_mwh": round(a["energy"], 1),
            "budget_mwh": round(a["budget"], 1),
            "vs_budget_pct": vs,
            "revenue_eur": round(a["rev"], 0) if a["has_rev"] else None,
            "revenue_ppa_eur": round(a["rev_ppa"], 0) if a["has_rev"] else None,
            "volume_mwh": round(a["vol"], 1) if a["vol"] > 0 else None,
            "capture": capture,
            "capture_ppa": capture_ppa,
            "is_partial": a["partial"],
        })
    return out


def _latest_closed_key(fleet_series: List[dict]) -> Optional[str]:
    closed = [m for m in fleet_series if not m["is_partial"]
              and (m["energy_mwh"] or 0) > 0]
    return closed[-1]["month"] if closed else None


def build_portfolio_overview(assets: dict) -> dict:
    """Bygg portföljöversikten: flottserie, YTD, senaste stängda månad."""
    fleet_series = build_fleet_series(assets)
    parks = (assets or {}).get("parks", {})

    total_capacity = sum(
        p.get("capacity_mwp") or 0.0 for p in parks.values()
    )

    ytd = None
    latest_closed = None
    if fleet_series:
        current_year = int(fleet_series[-1]["month"][:4])
        ytd_months = [
            m for m in fleet_series if m["month"].startswith(str(current_year))
        ]
        e = sum(m["energy_mwh"] or 0 for m in ytd_months)
        b = sum(m["budget_mwh"] or 0 for m in ytd_months)
        rev = sum(m["revenue_eur"] or 0 for m in ytd_months)
        rev_ppa = sum(m["revenue_ppa_eur"] or 0 for m in ytd_months)
        vol = sum(m["volume_mwh"] or 0 for m in ytd_months)
        ytd = {
            "year": current_year,
            "energy_mwh": round(e, 1),
            "budget_mwh": round(b, 1),
            "vs_budget_pct": (
                round((e / b - 1.0) * 100.0, 1) if b > 0 else None
            ),
            "revenue_eur": round(rev, 0),
            "revenue_ppa_eur": round(rev_ppa, 0),
            "ppa_uplift_eur": round(rev_ppa - rev, 0),
            "capture": round(rev / vol, 2) if vol > 0 else None,
            "capture_ppa": round(rev_ppa / vol, 2) if vol > 0 else None,
        }

        closed_key = _latest_closed_key(fleet_series)
        if closed_key:
            m = next(x for x in fleet_series if x["month"] == closed_key)
            baseload_w = 0.0
            baseload_vol = 0.0
            avail_w = 0.0
            avail_cap = 0.0
            year_i, month_i = int(closed_key[:4]), int(closed_key[5:7])
            for park in parks.values():
                pm = next(
                    (x for x in park.get("months", [])
                     if x["year"] == year_i and x["month"] == month_i),
                    None,
                )
                if pm is None:
                    continue
                vol_p = pm.get("bazefield_volume_mwh")
                base = pm.get("baseload_eur_mwh")
                if vol_p and base is not None:
                    baseload_w += base * vol_p
                    baseload_vol += vol_p
                avail = pm.get("availability_pct")
                cap_mw = park.get("capacity_mwp") or 0.0
                if avail is not None and cap_mw > 0:
                    avail_w += avail * cap_mw
                    avail_cap += cap_mw
            baseload = (
                round(baseload_w / baseload_vol, 2) if baseload_vol > 0 else None
            )
            premium = None
            if m["capture"] is not None and baseload:
                premium = round((m["capture"] / baseload - 1.0) * 100.0, 1)
            latest_closed = {
                "month": closed_key,
                "energy_mwh": m["energy_mwh"],
                "budget_mwh": m["budget_mwh"],
                "vs_budget_pct": m["vs_budget_pct"],
                "capture": m["capture"],
                "capture_ppa": m["capture_ppa"],
                "baseload": baseload,
                "capture_premium_pct": premium,
                "availability_pct": (
                    round(avail_w / avail_cap, 1) if avail_cap > 0 else None
                ),
            }

    # Per-park YTD-rader (för översiktstabellen)
    park_ytd: List[dict] = []
    if fleet_series:
        current_year = int(fleet_series[-1]["month"][:4])
        for key, park in parks.items():
            months = [
                m for m in park.get("months", []) if m["year"] == current_year
            ]
            if not months:
                continue
            e = sum(m.get("energy_mwh") or 0 for m in months)
            b = sum(m.get("budget_mwh") or 0 for m in months)
            rev = sum(m.get("revenue_eur") or 0 for m in months)
            vol = sum(m.get("bazefield_volume_mwh") or 0 for m in months)
            neg = sum(m.get("neg_price_volume_mwh") or 0 for m in months)
            cap_kwp = (park.get("capacity_mwp") or 0) * 1000.0
            park_ytd.append({
                "park": key,
                "name": park.get("name") or key.capitalize(),
                "zone": park.get("zone"),
                "capacity_mwp": park.get("capacity_mwp"),
                "energy_mwh": round(e, 1),
                "budget_mwh": round(b, 1),
                "vs_budget_pct": (
                    round((e / b - 1.0) * 100.0, 1) if b > 0 else None
                ),
                "yield_kwh_kwp": (
                    round(e * 1000.0 / cap_kwp, 1) if cap_kwp > 0 else None
                ),
                "capture": round(rev / vol, 2) if vol > 0 else None,
                "neg_volume_mwh": round(neg, 1),
            })
        park_ytd.sort(key=lambda r: -(r["energy_mwh"] or 0))

    return {
        "total_capacity_mwp": round(total_capacity, 3),
        "park_count": len(parks),
        "fleet_series": fleet_series,
        "ytd": ytd,
        "latest_closed": latest_closed,
        "park_ytd": park_ytd,
    }


# ---------------------------------------------------------------------------
# PPA vs marknad
# ---------------------------------------------------------------------------

def _front_year_label(forward: Optional[dict]) -> Optional[str]:
    """Första årskontraktet i forwardkurvan (t.ex. 'YR-27')."""
    if not forward:
        return None
    for c in forward.get("contracts", []):
        if c.get("type") == "year":
            return c.get("label")
    return None


def build_ppa_view(assets: dict, forward: Optional[dict]) -> dict:
    """PPA-kontrakt vs realiserad capture vs terminsmarknad per park."""
    parks = (assets or {}).get("parks", {})
    fwd_label = _front_year_label(forward)
    zone_fwd = (forward or {}).get("zone_fwd", {})
    settlement = (forward or {}).get("settlement_date")

    rows: List[dict] = []
    current_year = None
    for key, park in parks.items():
        months = park.get("months", [])
        if months:
            y = max(m["year"] for m in months)
            current_year = y if current_year is None else max(current_year, y)

    for key, park in parks.items():
        ppa = park.get("ppa")
        months = park.get("months", [])
        # Senaste månad med revenue-data (stängd)
        rev_months = [
            m for m in months
            if m.get("capture_eur_mwh") is not None and not m.get("is_partial")
        ]
        latest = rev_months[-1] if rev_months else None

        uplift_ytd = 0.0
        has_uplift = False
        if current_year is not None:
            for m in months:
                if m["year"] != current_year:
                    continue
                rev = m.get("revenue_eur")
                rev_ppa = m.get("revenue_eur_ppa")
                if rev is not None and rev_ppa is not None:
                    uplift_ytd += rev_ppa - rev
                    has_uplift = True

        zone = park.get("zone")
        rows.append({
            "park": key,
            "name": park.get("name") or key.capitalize(),
            "zone": zone,
            "has_ppa": ppa is not None,
            "ppa_price_sek_mwh": (ppa or {}).get("price_sek_mwh"),
            "ppa_share_pct": (ppa or {}).get("share_pct"),
            "ppa_price_eur_mwh": (latest or {}).get("ppa_price_eur_mwh_avg"),
            "capture_spot_eur_mwh": (latest or {}).get("capture_eur_mwh"),
            "capture_month": (
                f"{latest['year']}-{latest['month']:02d}" if latest else None
            ),
            "fwd_eur_mwh": (
                zone_fwd.get(zone, {}).get(fwd_label) if fwd_label else None
            ),
            "uplift_ytd_eur": round(uplift_ytd, 0) if has_uplift else None,
        })

    rows.sort(key=lambda r: (not r["has_ppa"], r["name"]))
    return {
        "rows": rows,
        "fwd_label": fwd_label,
        "settlement_date": settlement,
        "ytd_year": current_year,
    }


# ---------------------------------------------------------------------------
# Datakvalitet
# ---------------------------------------------------------------------------

def build_data_quality(window_days: int = 90) -> List[dict]:
    """Datakvalitet per park över senaste ``window_days`` dagarna.

    * ``meter_share_pct`` — andel av energin som kommer från grid-mätaren
      (resten är inverter-fallback via effective_power_mw).
    * ``stuck_days`` — dagar där stuck-value-detektionen slog till.
    * ``availability_coverage_pct`` — andel 15-min-intervall med
      availability-signal.
    """
    out: List[dict] = []
    for park_key in PARK_CAPACITY_KWP:
        records = load_park_15min(park_key)
        zone = PARK_ZONES.get(park_key, "")
        if not records:
            out.append({
                "park": park_key, "zone": zone, "last_ts": None,
                "meter_share_pct": None, "stuck_days": None,
                "availability_coverage_pct": None, "has_weather": False,
            })
            continue

        last_ts = max(r["timestamp_utc"] for r in records)
        cutoff = last_ts - timedelta(days=window_days)
        recent = [r for r in records if r["timestamp_utc"] >= cutoff]

        meter_e = sum(r["power_mw"] * 0.25 for r in recent)
        eff_e = sum(r["effective_power_mw"] * 0.25 for r in recent)
        stuck_dates = {
            r["date"] for r in recent if r.get("_stuck_value")
        }
        with_avail = sum(1 for r in recent if r.get("availability") is not None)

        weather_path = PARKS_PROFILE_DIR / f"{park_key}_{zone}_weather.csv"

        out.append({
            "park": park_key,
            "zone": zone,
            "last_ts": last_ts.isoformat(),
            "meter_share_pct": (
                round(meter_e / eff_e * 100.0, 1) if eff_e > 0 else None
            ),
            "stuck_days": len(stuck_dates),
            "availability_coverage_pct": (
                round(with_avail / len(recent) * 100.0, 1) if recent else None
            ),
            "has_weather": weather_path.exists(),
            "window_days": window_days,
        })
    return out


# ---------------------------------------------------------------------------
# Klartext-insikter
# ---------------------------------------------------------------------------

def _tone(value, good_when_positive: bool = True) -> str:
    if value is None:
        return "neutral"
    if value >= 0:
        return "pos" if good_when_positive else "neg"
    return "neg" if good_when_positive else "pos"


def _ytd_neg_hours(monthly: List[dict], year: int, upto_month: int) -> float:
    total = 0.0
    for m in monthly:
        y, mo = int(m["month"][:4]), int(m["month"][5:7])
        if y == year and mo <= upto_month:
            total += m.get("neg_hours") or 0.0
    return total


def build_insights(
    portfolio: dict,
    market_analysis: dict,
    cannibalization: dict,
    orientation: dict,
    imbalance: dict,
    ppa_view: dict,
    home_zone: str = "SE3",
) -> Dict[str, List[dict]]:
    """Generera klartext-slutsatser (svenska) ur de beräknade sektionerna.

    Returns:
        {"oversikt": [{"text": str, "tone": "pos"|"neg"|"neutral"}], ...}
    """
    insights: Dict[str, List[dict]] = {
        "oversikt": [], "marknad": [], "capture": [], "risk": [],
    }

    # --- Översikt -----------------------------------------------------
    ytd = portfolio.get("ytd")
    if ytd and ytd.get("energy_mwh"):
        vs = ytd.get("vs_budget_pct")
        rel = "över" if (vs or 0) >= 0 else "under"
        insights["oversikt"].append({
            "text": (
                f"Portföljens {portfolio['park_count']} parker "
                f"({fmt_num(portfolio['total_capacity_mwp'], 1)} MWp) har "
                f"producerat {fmt_num(ytd['energy_mwh'])} MWh hittills "
                f"{ytd['year']} — {fmt_num(abs(vs), 1) if vs is not None else '–'}"
                f" % {rel} budget."
            ),
            "tone": _tone(vs),
        })
    lc = portfolio.get("latest_closed")
    if lc:
        prem = lc.get("capture_premium_pct")
        insights["oversikt"].append({
            "text": (
                f"Senaste stängda månad ({lc['month']}): "
                f"{fmt_num(lc['energy_mwh'])} MWh "
                f"({fmt_signed_pct(lc['vs_budget_pct'])} mot budget), "
                f"realiserat capture {fmt_num(lc['capture'], 1)} €/MWh"
                + (
                    f" ({fmt_signed_pct(prem)} mot zonernas baseload)."
                    if prem is not None else "."
                )
            ),
            "tone": _tone(lc.get("vs_budget_pct")),
        })
    if ytd and ytd.get("ppa_uplift_eur") is not None:
        uplift = ytd["ppa_uplift_eur"]
        verb = "tillfört" if uplift >= 0 else "kostat"
        insights["oversikt"].append({
            "text": (
                f"PPA-kontrakten har {verb} "
                f"{fmt_num(abs(uplift) / 1000.0, 0)} k€ hittills i år "
                f"relativt ren spotförsäljning."
            ),
            "tone": _tone(uplift),
        })

    # --- Marknad ------------------------------------------------------
    zones_ma = market_analysis.get("zones", {})
    home = zones_ma.get(home_zone, {})
    yearly = home.get("yearly", [])
    if len(yearly) >= 2:
        cur = yearly[-1]
        prev_complete = next(
            (y for y in reversed(yearly[:-1]) if y.get("complete")), None
        )
        if prev_complete:
            insights["marknad"].append({
                "text": (
                    f"Spotpriset i {home_zone} snittar "
                    f"{fmt_num(cur['avg'], 1)} €/MWh hittills {cur['year']}, "
                    f"mot {fmt_num(prev_complete['avg'], 1)} €/MWh helåret "
                    f"{prev_complete['year']}."
                ),
                "tone": "neutral",
            })
    # Negativa timmar like-for-like (SE4 = mest utsatt zon)
    se4 = zones_ma.get("SE4", {})
    monthly_se4 = se4.get("monthly", [])
    if monthly_se4:
        last = monthly_se4[-1]["month"]
        cur_year, cur_month = int(last[:4]), int(last[5:7])
        neg_now = _ytd_neg_hours(monthly_se4, cur_year, cur_month)
        neg_prev = _ytd_neg_hours(monthly_se4, cur_year - 1, cur_month)
        if neg_prev > 0 or neg_now > 0:
            trend = "färre" if neg_now <= neg_prev else "fler"
            insights["marknad"].append({
                "text": (
                    f"Negativa pristimmar i SE4 jan–{cur_month:02d}: "
                    f"{fmt_num(neg_now)} h i år mot {fmt_num(neg_prev)} h "
                    f"samma period i fjol — {trend} negativa timmar."
                ),
                "tone": _tone(neg_prev - neg_now),
            })
    # Intradagsspread-trend
    if len(yearly) >= 3:
        spreads = [
            (y["year"], y["intraday_spread"]) for y in yearly
            if y.get("intraday_spread") is not None
        ]
        if len(spreads) >= 3:
            (y1, s1), (y2, s2) = spreads[-2], spreads[-1]
            riktning = "vidgas" if s2 > s1 else "krymper"
            insights["marknad"].append({
                "text": (
                    f"Intradagsspreaden i {home_zone} {riktning}: "
                    f"{fmt_num(s2, 1)} €/MWh {y2} mot {fmt_num(s1, 1)} "
                    f"€/MWh {y1} — duck curve-dynamiken stärker värdet av "
                    f"flex och öst-väst-profiler."
                ),
                "tone": "neutral",
            })

    # --- Capture ------------------------------------------------------
    ratio_yearly = cannibalization.get("ratio_yearly", {}).get(home_zone, [])
    installed = (
        cannibalization.get("installed", {}).get("solar", {}).get(home_zone, [])
    )
    complete_ratios = [
        r for r in ratio_yearly if r.get("ratio") is not None
    ]
    if len(complete_ratios) >= 2 and installed:
        first = complete_ratios[0]
        # senaste hela år = näst sista om sista året är partiellt
        years_complete = {
            y["year"] for y in yearly if y.get("complete")
        }
        last_full = next(
            (r for r in reversed(complete_ratios)
             if r["year"] in years_complete),
            complete_ratios[-1],
        )
        inst_first = installed[0]
        inst_last = installed[-1]
        insights["capture"].append({
            "text": (
                f"Capture ratio för sydvänd sol i {home_zone} har gått från "
                f"{fmt_num(first['ratio'], 2)} ({first['year']}) till "
                f"{fmt_num(last_full['ratio'], 2)} ({last_full['year']}) "
                f"medan installerad sol i zonen växt från "
                f"{fmt_num(inst_first['mw'] / 1000.0, 1)} till "
                f"{fmt_num(inst_last['mw'] / 1000.0, 1)} GW "
                f"({inst_first['year']}–{inst_last['year']}). "
                f"Cannibaliseringen är strukturell, inte cyklisk."
            ),
            "tone": "neg",
        })
    # Orientering: EUR/kWp senaste hela år
    eur_kwp = orientation.get("eur_per_kwp", {}).get("SE4", [])
    prem = orientation.get("premium_vs_syd", {}).get("SE4", [])
    if eur_kwp and prem:
        years_w_data = [
            r for r in eur_kwp
            if r.get("syd") is not None and r.get("ov") is not None
        ]
        if years_w_data:
            r = years_w_data[-1]
            p = next(
                (x for x in prem if x["year"] == r["year"]), {}
            )
            ov_prem = p.get("ov_pct")
            if ov_prem is not None:
                vinnare = "syd" if (r["syd"] or 0) >= (r["ov"] or 0) else "öst-väst"
                insights["capture"].append({
                    "text": (
                        f"Öst-väst gav {fmt_signed_pct(ov_prem)} capture-pris "
                        f"mot syd i SE4 {r['year']}, men lägre specifik "
                        f"produktion. Netto per installerad kWp: "
                        f"{fmt_num(r['syd'], 1)} € (syd) vs "
                        f"{fmt_num(r['ov'], 1)} € (öst-väst) — "
                        f"{vinnare} vinner fortfarande på årsbasis."
                    ),
                    "tone": "neutral",
                })
            tr = r.get("tracker")
            if tr is not None and r.get("syd"):
                diff_pct = (tr / r["syd"] - 1.0) * 100.0
                insights["capture"].append({
                    "text": (
                        f"Tracker levererar {fmt_num(tr, 1)} €/kWp "
                        f"({fmt_signed_pct(diff_pct)} mot syd) i SE4 "
                        f"{r['year']} tack vare både högre produktion och "
                        f"bättre timing — i linje med Hovas faktiska "
                        f"överavkastning som portföljens enda tracker."
                    ),
                    "tone": "pos",
                })

    # --- Risk ---------------------------------------------------------
    fwd_label = ppa_view.get("fwd_label")
    rows = ppa_view.get("rows", [])
    if fwd_label:
        se3_fwd = next(
            (r["fwd_eur_mwh"] for r in rows
             if r["zone"] == home_zone and r["fwd_eur_mwh"] is not None),
            None,
        )
        if se3_fwd is not None:
            insights["risk"].append({
                "text": (
                    f"Terminsmarknaden prissätter {home_zone} baseload "
                    f"{fwd_label} till {fmt_num(se3_fwd, 1)} €/MWh "
                    f"(settlement {ppa_view.get('settlement_date')})."
                ),
                "tone": "neutral",
            })
    imb = imbalance.get("zones", {}).get(home_zone, {}).get("last12")
    if imb:
        insights["risk"].append({
            "text": (
                f"Obalanspriset i {home_zone} avvek i snitt "
                f"{fmt_num(imb['mean_abs_diff'], 1)} €/MWh från spot senaste "
                f"12 mån ({imb['from_month']}–{imb['to_month']}) — proxyn "
                f"för vad varje MWh prognosfel kostar en producent."
            ),
            "tone": "neutral",
        })
    ppa_rows = [r for r in rows if r["has_ppa"]
                and r.get("ppa_price_eur_mwh") is not None]
    if ppa_rows:
        avg_ppa = sum(r["ppa_price_eur_mwh"] for r in ppa_rows) / len(ppa_rows)
        fwd_vals = [
            r["fwd_eur_mwh"] for r in ppa_rows if r.get("fwd_eur_mwh") is not None
        ]
        if fwd_vals:
            avg_fwd = sum(fwd_vals) / len(fwd_vals)
            rel = "över" if avg_ppa >= avg_fwd else "under"
            insights["risk"].append({
                "text": (
                    f"Snittat PPA-pris {fmt_num(avg_ppa, 1)} €/MWh ligger "
                    f"{rel} forwardkurvan ({fmt_num(avg_fwd, 1)} €/MWh "
                    f"{fwd_label}) — hedgarna är "
                    f"{'in the money' if avg_ppa >= avg_fwd else 'out of the money'} "
                    f"relativt marknadens förväntan."
                ),
                "tone": _tone(avg_ppa - avg_fwd),
            })

    return insights
