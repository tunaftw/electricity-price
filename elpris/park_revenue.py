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

from .config import PARK_CAPACITY_KWP, PARK_ZONES
from .operations_dashboard_data import load_park_15min, load_spot_prices_15min


def calculate_park_revenue_capture() -> Dict[str, List[dict]]:
    """Beräkna realiserad capture & revenue per park-månad.

    Returnerar {park_key: [{year, month, volume_mwh, revenue_eur,
    capture_eur_mwh, baseload_eur_mwh, capture_premium_pct}, ...]}
    sorterat äldst → nyast. Endast parker med både Bazefield- och
    spot-data inkluderas.
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

        # Aggregera per (year, month).
        # m_data[ym] = {"volume_mwh", "revenue_eur",
        #               "spot_sum_eur", "spot_n"}
        m_data: dict[tuple[int, int], dict] = defaultdict(
            lambda: {"volume_mwh": 0.0, "revenue_eur": 0.0,
                     "spot_sum_eur": 0.0, "spot_n": 0}
        )

        for date_key, prices in spot.items():
            for price_rec in prices:
                ts_utc = price_rec["timestamp_utc"]
                ts_key = ts_utc.strftime("%Y-%m-%dT%H:%M")
                price = price_rec["eur_mwh"]
                power = park_by_ts.get(ts_key, 0.0)

                ym = (ts_utc.year, ts_utc.month)
                bucket = m_data[ym]
                bucket["spot_sum_eur"] += price
                bucket["spot_n"] += 1
                if power > 0:
                    energy = power * 0.25  # MWh per 15 min
                    bucket["volume_mwh"] += energy
                    bucket["revenue_eur"] += energy * price

        out = []
        for (year, month), b in sorted(m_data.items()):
            volume = b["volume_mwh"]
            revenue = b["revenue_eur"]
            capture = (revenue / volume) if volume > 0 else None
            baseload = (b["spot_sum_eur"] / b["spot_n"]
                        if b["spot_n"] > 0 else None)
            premium = None
            if capture is not None and baseload is not None and baseload != 0:
                premium = (capture / baseload - 1.0) * 100.0
            # Hoppa över helt tomma månader (inga spot-priser alls)
            if b["spot_n"] == 0:
                continue
            out.append({
                "year": year,
                "month": month,
                "volume_mwh": round(volume, 2),
                "revenue_eur": round(revenue, 2),
                "capture_eur_mwh": round(capture, 2) if capture is not None else None,
                "baseload_eur_mwh": round(baseload, 2) if baseload is not None else None,
                "capture_premium_pct": round(premium, 2) if premium is not None else None,
            })
        if out:
            result[park_key] = out

    return result
