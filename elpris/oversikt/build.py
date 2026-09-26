"""Sätter ihop all data för Electricity Price (Översikt) till en JSON-bar struktur."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict

from ..config import SWEDEN_TZ
from .batteri import build_batteri_data
from .common import spot_end_epoch
from .datastatus import build_datastatus
from .marknad import build_marknad_data
from .portfolj import PARK_ORDER, build_portfolj_data
from .terminer import build_terminer_data

# Ordlistan visas under "How we calculate" och i ?-knapparna (samma text på
# båda ställena). Nyckel, term, förklaring. Gränssnittet är på engelska.
DEFINITIONS = [
    ("production", "Production",
     "Metered delivery to the grid, summed quarter-hour by quarter-hour. The grid meter comes first. The inverter "
     "value is used only when the meter is missing <i>and</i> the inverter shows live values. Quarter-hours without "
     "a trustworthy signal (dead meter, frozen inverter) are not counted: they are unknown, not zero. Night always "
     "counts as zero."),
    ("coverage", "Data coverage",
     "Share of daylight (sun more than 5° above the horizon) with a trustworthy measurement. Each quarter-hour is "
     "weighted by the height of the sun, so a missing noon weighs more than a missing dawn."),
    ("vs_budget", "Versus budget",
     "Production compared with the PVsyst budget for <i>the same time that has metered data</i>. The monthly budget "
     "is spread over the month's quarter-hours with the same sun-height weight. Shown only when data coverage is at "
     "least 80%. The portfolio figure uses the parks that pass that threshold, and the page always says which. "
     "Check on 57 complete park-months: with 6 random days removed, the adjusted comparison lands a median of "
     "2 percentage points from the true value (90% within 6). Without the adjustment the error is 19 points."),
    ("specific_yield", "Specific yield",
     "Production per installed DC capacity (kWh/kWp). Compares parks of different size. Below 95% data coverage "
     "the value is too low and is marked as incomplete."),
    ("spot_value", "Spot value",
     "Production multiplied by the spot price in the park's bidding zone, quarter-hour by quarter-hour. What the "
     "power was worth on the day-ahead market, not invoiced revenue: PPA terms, fees and imbalance are not included."),
    ("capture_price", "Capture price",
     "Spot value divided by production: what one MWh of solar output was worth on average."),
    ("capture_ratio", "Capture rate (park and portfolio)",
     "Capture price divided by the average spot price (all hours of the day) in the same zone, over the days the "
     "park has metered data. For the portfolio the zones' spot prices are weighted by production."),
    ("capture_rate", "Solar capture rate (market)",
     "Spot price weighted by the zone's <i>actual</i> solar output according to ENTSO-E, divided by the spot price "
     "for the same period. Actual output rather than a typical-year profile, because sunny days are also cheap "
     "days. A PVsyst profile gives 5–8 percentage points too high a rate, a generic profile 12–15."),
    ("design_capture", "Capture by panel design",
     "Spot price weighted by PVsyst typical-year profiles for south-facing, east–west and single-axis tracker "
     "systems. A model, not measured output: the level is 5–8 points too high, so read it as the difference "
     "between designs."),
    ("baseload", "Spot price (baseload)",
     "Time-weighted average day-ahead price in the zone, all hours of the day."),
    ("area_price", "Area price (futures)",
     "Nordic system price (SYS) plus the area differential (EPAD) for the same contract on the same trading day. "
     "If one leg is missing no price is shown; it is never replaced by SYS alone."),
    ("epad", "EPAD",
     "Electricity Price Area Differential: a futures contract on the difference between a bidding zone's price "
     "and the Nordic system price."),
    ("spread", "Daily spread",
     "Average price of the day's 2 most expensive hours minus the average of the 2 cheapest."),
    ("arbitrage", "Arbitrage cap",
     "What a 1 MW / 2 MWh battery could have earned with one full cycle per day, 88% round-trip efficiency and "
     "perfect knowledge of the day's prices. A ceiling, not a forecast."),
    ("ancillary", "Ancillary services (FCR, aFRR, mFRR-CM)",
     "Capacity paid for being ready to regulate the grid frequency: FCR-N and FCR-D (containment), aFRR "
     "(automatic restoration) and mFRR-CM (manual restoration, capacity market). Shown as the revenue per MW at "
     "100% availability with every bid accepted. An upper bound that cannot be added to arbitrage."),
    ("poa", "POA",
     "Plane-of-array irradiance: sunlight measured in the plane of the panels (W/m²)."),
    ("time", "Time and currency",
     "Months and days follow Swedish time (CET/CEST). All prices are in EUR/MWh. Hourly prices before 1 Oct 2025 "
     "apply to all four quarter-hours of the hour."),
]


def _step(label: str, fn: Callable[[], Any]) -> Any:
    t0 = time.time()
    out = fn()
    print(f"  {label}: {time.time() - t0:.1f} s", file=sys.stderr)
    return out


def build_oversikt_data() -> Dict[str, Any]:
    from .tillagg import build_tillagg_data
    portfolj = _step("portfölj", build_portfolj_data)
    marknad = _step("marknad", build_marknad_data)
    market_end = min(e for e in (spot_end_epoch(z) for z in ("SE3", "SE4")) if e)
    batteri = _step("batteri", lambda: build_batteri_data(market_end))
    terminer = _step("terminer", lambda: build_terminer_data(market_end))
    ref_day = max(portfolj["data_end"], marknad["data_end"])
    datastatus = _step("datastatus", lambda: build_datastatus(ref_day, portfolj, terminer))
    tillagg = _step("tillägg från Track C", lambda: build_tillagg_data(list(PARK_ORDER)))
    now = datetime.now(SWEDEN_TZ)
    return {
        "generated": now.strftime("%Y-%m-%d %H:%M"),
        "dataset": f"parks to {portfolj['data_end']}, spot to {marknad['data_end']}",
        "portfolj": portfolj,
        "marknad": marknad,
        "terminer": terminer,
        "batteri": batteri,
        "datastatus": datastatus,
        "tillagg": tillagg,
        "definitions": DEFINITIONS,
    }
