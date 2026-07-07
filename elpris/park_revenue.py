"""Realized capture price & revenue per park-month.

Joinar Bazefield 15-min produktion (effective_power_mw, meter→inverter
fallback) med spot-priser 15-min för parkens zon. Resultatet är en
faktisk-marknads-baserad capture-prismetrik per park, till skillnad
från generiska zon-capture-priser baserade på PVsyst-profiler.

Skillnaden mellan park-capture och zon-capture (sol_syd / sol_ov /
sol_tracker) är i sig en KPI: avslöjar tracker-värde, curtailment-
respons, mätarfel och downtime mitt på dagen.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .config import PARK_CAPACITY_KWP, PARK_ZONES, local_year_month
from .operations_dashboard_data import load_park_15min, load_spot_prices_15min
from .park_config import get_ppa


def calculate_park_revenue_capture() -> Dict[str, List[dict]]:
    """Beräkna realiserad capture & revenue per park-månad.

    Returnerar {park_key: [{year, month, volume_mwh, revenue_eur,
    capture_eur_mwh, baseload_eur_mwh, capture_premium_pct,
    revenue_eur_ppa, capture_eur_mwh_ppa, ppa_price_sek_mwh,
    ppa_price_eur_mwh_avg, effective_baseload_eur_mwh_ppa,
    ppa_share_pct}, ...]} sorterat äldst → nyast.

    Två varianter av realiserad intäkt beräknas när PPA-kontrakt finns
    för parken (``park_config.PARK_PPA``):

    * ``revenue_eur`` / ``capture_eur_mwh`` — 100% spot, EUR/MWh.
    * ``revenue_eur_ppa`` / ``capture_eur_mwh_ppa`` — blandning där
      ``share_pct`` av faktiskt producerad volym ersätts till fast
      PPA-pris i SEK och konverteras till EUR per 15-min med samma
      EXR som spot-CSV:n använder.

    PPA är knuten till volym: downtime/curtailment trycker ner båda.

    ``ppa_price_eur_mwh_avg`` är tidsviktat snitt över månadens alla
    spot-perioder (price_sek / EXR(t)), används för att räkna ut
    ``effective_baseload_eur_mwh_ppa`` = share × ppa_eur_avg +
    (1-share) × baseload_eur. Detta ger en konsistent referens för
    waterfall-dekomposition i PPA-läge.
    """
    result: Dict[str, List[dict]] = {}

    # Cacha spot per zon för att undvika att läsa CSV:erna 8 gånger
    spot_cache: dict[str, dict[str, list[dict]]] = {}

    for park_key in PARK_CAPACITY_KWP:
        zone = PARK_ZONES.get(park_key)
        if not zone:
            continue

        park_records = load_park_15min(park_key)
        if not park_records:
            continue

        if zone not in spot_cache:
            spot_cache[zone] = load_spot_prices_15min(zone)
        spot = spot_cache[zone]
        if not spot:
            continue

        # Index park-data per timestamp för join
        park_by_ts: Dict[str, float] = {}
        for r in park_records:
            ts_key = r["timestamp_utc"].strftime("%Y-%m-%dT%H:%M")
            park_by_ts[ts_key] = r["effective_power_mw"]

        ppa = get_ppa(park_key)
        share = (ppa["share_pct"] / 100.0) if ppa else 0.0
        ppa_sek = ppa["price_sek_mwh"] if ppa else None

        # Aggregera per (year, month).
        m_data: dict[tuple[int, int], dict] = defaultdict(
            lambda: {
                "volume_mwh": 0.0,
                "revenue_eur": 0.0,           # 100% spot
                "revenue_eur_ppa": 0.0,       # blended
                "spot_sum_eur": 0.0,          # för time-weighted baseload
                "spot_n": 0,
                "ppa_eur_sum": 0.0,           # Σ price_sek/EXR(t) över alla spot-perioder
                "ppa_eur_n": 0,               # antal perioder med giltig EXR
            }
        )

        for date_key, prices in spot.items():
            for price_rec in prices:
                ts_utc = price_rec["timestamp_utc"]
                ts_key = ts_utc.strftime("%Y-%m-%dT%H:%M")
                price = price_rec["eur_mwh"]
                exr = price_rec.get("sek_per_eur")
                power = park_by_ts.get(ts_key, 0.0)

                ym = local_year_month(ts_utc)
                bucket = m_data[ym]
                bucket["spot_sum_eur"] += price
                bucket["spot_n"] += 1

                # Tidsviktat PPA-pris i EUR (för effective baseload)
                if ppa is not None and exr:
                    bucket["ppa_eur_sum"] += ppa_sek / exr
                    bucket["ppa_eur_n"] += 1

                if power > 0:
                    energy = power * 0.25  # MWh per 15 min
                    bucket["volume_mwh"] += energy
                    bucket["revenue_eur"] += energy * price
                    if ppa is not None and exr:
                        ppa_eur_t = ppa_sek / exr
                        bucket["revenue_eur_ppa"] += energy * (
                            share * ppa_eur_t + (1.0 - share) * price
                        )
                    else:
                        # Park utan PPA: PPA-revenue = spot-revenue
                        bucket["revenue_eur_ppa"] += energy * price

        out = []
        for (year, month), b in sorted(m_data.items()):
            # Hoppa över helt tomma månader (inga spot-priser alls)
            if b["spot_n"] == 0:
                continue
            volume = b["volume_mwh"]
            revenue = b["revenue_eur"]
            revenue_ppa = b["revenue_eur_ppa"]
            capture = (revenue / volume) if volume > 0 else None
            capture_ppa = (revenue_ppa / volume) if volume > 0 else None
            baseload = b["spot_sum_eur"] / b["spot_n"]
            premium = None
            if capture is not None and baseload != 0:
                premium = (capture / baseload - 1.0) * 100.0

            row = {
                "year": year,
                "month": month,
                "volume_mwh": round(volume, 2),
                "revenue_eur": round(revenue, 2),
                "capture_eur_mwh": round(capture, 2) if capture is not None else None,
                "baseload_eur_mwh": round(baseload, 2),
                "capture_premium_pct": round(premium, 2) if premium is not None else None,
            }

            if ppa is not None and b["ppa_eur_n"] > 0:
                ppa_eur_avg = b["ppa_eur_sum"] / b["ppa_eur_n"]
                eff_baseload_ppa = share * ppa_eur_avg + (1.0 - share) * baseload
                row["revenue_eur_ppa"] = round(revenue_ppa, 2)
                row["capture_eur_mwh_ppa"] = (
                    round(capture_ppa, 2) if capture_ppa is not None else None
                )
                row["ppa_price_sek_mwh"] = ppa_sek
                row["ppa_price_eur_mwh_avg"] = round(ppa_eur_avg, 2)
                row["effective_baseload_eur_mwh_ppa"] = round(eff_baseload_ppa, 2)
                row["ppa_share_pct"] = ppa["share_pct"]
            else:
                row["revenue_eur_ppa"] = None
                row["capture_eur_mwh_ppa"] = None
                row["ppa_price_sek_mwh"] = None
                row["ppa_price_eur_mwh_avg"] = None
                row["effective_baseload_eur_mwh_ppa"] = None
                row["ppa_share_pct"] = None

            out.append(row)
        if out:
            result[park_key] = out

    return result
