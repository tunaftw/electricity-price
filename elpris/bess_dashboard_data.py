"""BESS dashboard data – hourly arbitrage optimizer and profile definitions.

Provides an hourly dynamic-programming arbitrage optimizer for battery energy
storage systems (BESS) and the profile/color constants consumed by the v2
dashboard.  The optimizer works on hourly spot-price arrays (EUR/MWh) and
returns revenue, cycle count, and average buy/sell prices for a given battery
configuration.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from statistics import mean
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROUND_TRIP_EFFICIENCY = 0.88  # 88 % round-trip efficiency
DURATION_PRESETS = [1, 2, 4]  # hours (C-rate = 1 for all presets)
POWER_MW = 1.0  # reference power for revenue normalisation

# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

ARBITRAGE_PROFILES: dict[str, str] = {
    "arb_1h": "Arbitrage 1h",
    "arb_2h": "Arbitrage 2h",
    "arb_4h": "Arbitrage 4h",
}

SPREAD_PROFILES: dict[str, str] = {
    "spread": "Spread (min/max)",
}

SOL_BESS_PROFILES: dict[str, str] = {
    "sol_bess_1h": "Sol+BESS 1h",
    "sol_bess_2h": "Sol+BESS 2h",
    "sol_bess_4h": "Sol+BESS 4h",
}

# ---------------------------------------------------------------------------
# Color definitions
# ---------------------------------------------------------------------------

ARBITRAGE_COLORS: dict[str, str] = {
    "arb_1h": "#f59e0b",
    "arb_2h": "#d97706",
    "arb_4h": "#b45309",
}

SPREAD_COLORS: dict[str, str] = {
    "spread": "#94a3b8",
}

SOL_BESS_COLORS: dict[str, str] = {
    "sol_bess_1h": "#2dd4bf",
    "sol_bess_2h": "#14b8a6",
    "sol_bess_4h": "#0d9488",
}

# ---------------------------------------------------------------------------
# Profile metadata (type + unit for each profile key)
# ---------------------------------------------------------------------------

BESS_PROFILE_META: dict[str, dict[str, str]] = {
    # Arbitrage – revenue per MW installed power
    "arb_1h":      {"type": "revenue", "unit": "EUR/MW"},
    "arb_2h":      {"type": "revenue", "unit": "EUR/MW"},
    "arb_4h":      {"type": "revenue", "unit": "EUR/MW"},
    # Spread – simple min/max spread
    "spread":      {"type": "spread",  "unit": "EUR/MWh"},
    # Sol+BESS – capture price improvement
    "sol_bess_1h": {"type": "capture", "unit": "EUR/MWh"},
    "sol_bess_2h": {"type": "capture", "unit": "EUR/MWh"},
    "sol_bess_4h": {"type": "capture", "unit": "EUR/MWh"},
}


# ---------------------------------------------------------------------------
# Hourly DP arbitrage optimizer
# ---------------------------------------------------------------------------

def optimize_hourly_arbitrage(
    prices: list[float],
    capacity_mwh: float,
    power_mw: float = POWER_MW,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> tuple[float, float, float, float]:
    """Optimal intraday battery arbitrage via backward dynamic programming.

    The algorithm discretises the State of Charge (SoC) into levels separated
    by ``power_mw`` (i.e. the energy charged/discharged in one hour at rated
    power).  At every hour, three actions are evaluated:

    * **idle** – SoC unchanged, no cash flow.
    * **charge** – SoC increases by ``power_mw``; cost = price × power_mw.
    * **discharge** – SoC decreases by ``power_mw``; revenue = price ×
      power_mw × efficiency.

    A backward pass fills the DP table; a forward pass reconstructs the
    schedule and computes average buy / sell prices.

    Parameters
    ----------
    prices : list[float]
        Hourly spot prices in EUR/MWh (one value per hour).
    capacity_mwh : float
        Usable energy capacity of the battery (MWh).
    power_mw : float, optional
        Rated charge/discharge power (MW). Defaults to 1.0.
    efficiency : float, optional
        Round-trip efficiency applied at discharge. Defaults to 0.88.

    Returns
    -------
    tuple[float, float, float, float]
        ``(revenue_eur, cycles, avg_buy_price, avg_sell_price)``

        * *revenue_eur* – net revenue in EUR (rounded to 2 dp).
        * *cycles* – number of full equivalent cycles (rounded to 2 dp).
        * *avg_buy_price* – volume-weighted average charge price (EUR/MWh).
        * *avg_sell_price* – volume-weighted average discharge price (EUR/MWh).

        Returns ``(0, 0, 0, 0)`` when no profitable strategy exists.
    """
    n = len(prices)
    if n == 0:
        return (0.0, 0.0, 0.0, 0.0)

    # Energy per step (1 hour at rated power)
    energy_step = power_mw  # MWh per hour

    # Discrete SoC levels: 0, energy_step, 2*energy_step, … , capacity_mwh
    n_levels = int(round(capacity_mwh / energy_step)) + 1
    soc_levels = [i * energy_step for i in range(n_levels)]

    NEG_INF = float("-inf")

    # DP table: dp[t][s] = max revenue achievable from hour t to end,
    #           given SoC index s at the start of hour t.
    # We only need two layers (current + next) to save memory.
    next_dp = [0.0] * n_levels  # base case: at end, 0 revenue from any SoC

    # We store the full table for the forward pass reconstruction.
    dp = [[0.0] * n_levels for _ in range(n + 1)]
    # dp[n] is already all zeros (base case)

    # --- backward pass ---
    for t in range(n - 1, -1, -1):
        price = prices[t]
        for s in range(n_levels):
            best = dp[t + 1][s]  # idle

            # charge: SoC goes up one level
            if s + 1 < n_levels:
                cost = price * energy_step
                val = -cost + dp[t + 1][s + 1]
                if val > best:
                    best = val

            # discharge: SoC goes down one level
            if s - 1 >= 0:
                rev = price * energy_step * efficiency
                val = rev + dp[t + 1][s - 1]
                if val > best:
                    best = val

            dp[t][s] = best

    # Optimal revenue starting empty (SoC index 0)
    optimal = dp[0][0]

    if optimal <= 0:
        return (0.0, 0.0, 0.0, 0.0)

    # --- forward pass: reconstruct schedule ---
    s = 0  # start empty
    buy_prices: list[float] = []
    sell_prices: list[float] = []
    total_charged = 0.0
    total_discharged = 0.0

    for t in range(n):
        price = prices[t]
        best_val = dp[t + 1][s]
        best_action = "idle"

        # check charge
        if s + 1 < n_levels:
            cost = price * energy_step
            val = -cost + dp[t + 1][s + 1]
            if val > best_val + 1e-9:
                best_val = val
                best_action = "charge"

        # check discharge
        if s - 1 >= 0:
            rev = price * energy_step * efficiency
            val = rev + dp[t + 1][s - 1]
            if val > best_val + 1e-9:
                best_val = val
                best_action = "discharge"

        if best_action == "charge":
            buy_prices.append(price)
            total_charged += energy_step
            s += 1
        elif best_action == "discharge":
            sell_prices.append(price)
            total_discharged += energy_step
            s -= 1

    # Compute outputs
    revenue_eur = round(optimal, 2)
    cycles = round(total_discharged / capacity_mwh, 2) if capacity_mwh > 0 else 0.0
    avg_buy = round(mean(buy_prices), 2) if buy_prices else 0.0
    avg_sell = round(mean(sell_prices), 2) if sell_prices else 0.0

    return (revenue_eur, cycles, avg_buy, avg_sell)


# ---------------------------------------------------------------------------
# Daily spread calculation
# ---------------------------------------------------------------------------

def calculate_daily_spread(
    prices: list[float],
) -> tuple[float, float, float]:
    """Calculate the daily price spread (max - min).

    Parameters
    ----------
    prices : list[float]
        Hourly spot prices in EUR/MWh.

    Returns
    -------
    tuple[float, float, float]
        ``(spread, min_price, max_price)`` all rounded to 2 decimals.
        Returns ``(0.0, 0.0, 0.0)`` for empty input.
    """
    if not prices:
        return (0.0, 0.0, 0.0)

    lo = min(prices)
    hi = max(prices)
    spread = hi - lo
    return (round(spread, 2), round(lo, 2), round(hi, 2))


# ---------------------------------------------------------------------------
# BTM solar+BESS optimizer
# ---------------------------------------------------------------------------

def optimize_btm_hourly(
    prices: list[float],
    solar_mw: list[float],
    capacity_mwh: float,
    power_mw: float = POWER_MW,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> tuple[float, float]:
    """Optimal behind-the-meter solar+battery strategy via backward DP.

    The battery can **only** charge from solar production (no grid import).
    At each hour the optimizer chooses between:

    * **sell all** – sell all solar output, battery idle.
    * **charge** – store up to ``min(solar_available, remaining_capacity,
      power_mw)`` in the battery, sell the rest of solar.
    * **discharge** – sell solar output *plus* battery discharge (up to
      ``power_mw``), applying round-trip efficiency to discharged energy.

    Parameters
    ----------
    prices : list[float]
        Hourly spot prices in EUR/MWh.
    solar_mw : list[float]
        Hourly solar output in MW (energy per hour = solar_mw MWh).
    capacity_mwh : float
        Usable energy capacity of the battery (MWh).
    power_mw : float, optional
        Rated charge/discharge power (MW). Defaults to 1.0.
    efficiency : float, optional
        Round-trip efficiency applied at discharge. Defaults to 0.88.

    Returns
    -------
    tuple[float, float]
        ``(revenue_direct_eur, revenue_with_battery_eur)`` both rounded to
        2 decimals.

        * *revenue_direct_eur* – revenue from selling all solar directly.
        * *revenue_with_battery_eur* – optimal revenue with battery.
    """
    n = len(prices)
    if n == 0:
        return (0.0, 0.0)

    # Direct revenue (no battery)
    revenue_direct = sum(
        solar_mw[t] * prices[t] for t in range(min(n, len(solar_mw)))
    )

    # If no battery capacity, both revenues are the same
    if capacity_mwh <= 0:
        rd = round(revenue_direct, 2)
        return (rd, rd)

    # Use finer SoC discretisation (0.25 MWh steps) so that fractional solar
    # production (typically 0.1–0.8 MW) can actually charge the battery.
    soc_step = 0.25  # MWh per SoC level
    n_levels = int(round(capacity_mwh / soc_step)) + 1
    max_power_steps = int(round(power_mw / soc_step))  # max steps per hour

    # Ensure solar_mw is at least as long as prices (pad with zeros)
    solar = list(solar_mw) + [0.0] * max(0, n - len(solar_mw))

    # DP table: dp[t][s] = max revenue from hour t to end, given SoC index s
    dp = [[0.0] * n_levels for _ in range(n + 1)]

    # --- backward pass ---
    for t in range(n - 1, -1, -1):
        price = prices[t]
        sun = solar[t]  # solar energy available this hour (MWh)

        for s in range(n_levels):
            # Option 1: sell all solar, battery idle
            best = sun * price + dp[t + 1][s]

            # Option 2: charge from solar (various amounts)
            # Can charge up to min(solar available, remaining capacity, power limit)
            max_charge_steps = min(
                n_levels - 1 - s,  # room in battery (in steps)
                int(sun / soc_step) if soc_step > 0 else 0,  # solar available
                max_power_steps,  # power limit per hour
            )
            for c in range(1, max_charge_steps + 1):
                charge_energy = c * soc_step
                sell_solar = sun - charge_energy  # sell remainder
                val = sell_solar * price + dp[t + 1][s + c]
                if val > best:
                    best = val

            # Option 3: discharge battery (various amounts) + sell all solar
            max_discharge_steps = min(
                s,  # energy in battery (in steps)
                max_power_steps,  # power limit per hour
            )
            for d in range(1, max_discharge_steps + 1):
                discharge_energy = d * soc_step * efficiency
                val = sun * price + discharge_energy * price + dp[t + 1][s - d]
                if val > best:
                    best = val

            dp[t][s] = best

    revenue_with_battery = dp[0][0]

    return (round(revenue_direct, 2), round(revenue_with_battery, 2))


# ---------------------------------------------------------------------------
# Timezone constant
# ---------------------------------------------------------------------------

SWEDEN_TZ = ZoneInfo("Europe/Stockholm")
UTC_TZ = ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _aggregate_bess(
    daily_data: dict[str, dict],
    value_field: str,
) -> dict[str, list]:
    """Aggregate BESS daily data to yearly/monthly/daily format.

    Parameters
    ----------
    daily_data : dict
        Keyed by date_key ("YYYY-MM-DD"). Values are dicts with at minimum:
        date (date obj), year (int), month (int), plus *value_field*.
    value_field : str
        ``"revenue"`` sums across periods; ``"spread"`` averages.

    Returns
    -------
    dict with "yearly", "monthly", "daily" lists.
    """
    use_sum = value_field == "revenue"

    # --- daily ---
    daily_list: list[dict] = []
    for date_key in sorted(daily_data):
        d = daily_data[date_key]
        entry: dict = {
            "date": date_key,
            "year": d["year"],
            "month": d["month"],
            "capture": round(d[value_field], 2),
            "baseload": None,
            "ratio": None,
        }
        if "cycles" in d:
            entry["cycles"] = d["cycles"]
        if "avg_buy" in d:
            entry["avg_buy"] = d["avg_buy"]
        if "avg_sell" in d:
            entry["avg_sell"] = d["avg_sell"]
        if "min_price" in d:
            entry["min_price"] = d["min_price"]
        if "max_price" in d:
            entry["max_price"] = d["max_price"]
        daily_list.append(entry)

    # --- monthly ---
    monthly_acc: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"values": [], "cycles": 0.0, "has_cycles": False}
    )
    for d in daily_data.values():
        key = (d["year"], d["month"])
        acc = monthly_acc[key]
        acc["values"].append(d[value_field])
        if "cycles" in d:
            acc["cycles"] += d["cycles"]
            acc["has_cycles"] = True

    monthly_list: list[dict] = []
    for (year, month) in sorted(monthly_acc):
        acc = monthly_acc[(year, month)]
        vals = acc["values"]
        agg_val = sum(vals) if use_sum else (sum(vals) / len(vals) if vals else 0)
        entry = {
            "year": year,
            "month": month,
            "capture": round(agg_val, 2),
            "baseload": None,
            "ratio": None,
        }
        if acc["has_cycles"]:
            entry["cycles"] = round(acc["cycles"], 2)
        monthly_list.append(entry)

    # --- yearly ---
    yearly_acc: dict[int, dict] = defaultdict(
        lambda: {"values": [], "cycles": 0.0, "has_cycles": False}
    )
    for d in daily_data.values():
        acc = yearly_acc[d["year"]]
        acc["values"].append(d[value_field])
        if "cycles" in d:
            acc["cycles"] += d["cycles"]
            acc["has_cycles"] = True

    yearly_list: list[dict] = []
    for year in sorted(yearly_acc):
        acc = yearly_acc[year]
        vals = acc["values"]
        agg_val = sum(vals) if use_sum else (sum(vals) / len(vals) if vals else 0)
        entry = {
            "year": year,
            "capture": round(agg_val, 2),
            "baseload": None,
            "ratio": None,
        }
        if acc["has_cycles"]:
            entry["cycles"] = round(acc["cycles"], 2)
        yearly_list.append(entry)

    return {"yearly": yearly_list, "monthly": monthly_list, "daily": daily_list}


def _aggregate_sol_bess(daily_data: dict[str, dict]) -> dict[str, list]:
    """Aggregate sol+BESS data to standard capture price format.

    Parameters
    ----------
    daily_data : dict
        Keyed by date_key. Values have: date, year, month,
        sum_weighted_battery, sum_gen, sum_price, count.

    Returns
    -------
    dict with "yearly", "monthly", "daily" lists, each entry containing
    baseload, capture, ratio.
    """

    def _finalize(sw: float, sg: float, sp: float, c: int) -> tuple:
        baseload = round(sp / c, 2) if c > 0 else None
        capture = round(sw / sg, 2) if sg > 0 else None
        ratio = (
            round(capture / baseload, 3)
            if capture is not None and baseload and baseload > 0
            else None
        )
        return baseload, capture, ratio

    # --- daily ---
    daily_list: list[dict] = []
    for date_key in sorted(daily_data):
        d = daily_data[date_key]
        bl, cap, rat = _finalize(
            d["sum_weighted_battery"], d["sum_gen"], d["sum_price"], d["count"]
        )
        daily_list.append({
            "date": date_key,
            "year": d["year"],
            "month": d["month"],
            "baseload": bl,
            "capture": cap,
            "ratio": rat,
        })

    # --- monthly ---
    monthly_acc: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"sw": 0.0, "sg": 0.0, "sp": 0.0, "c": 0}
    )
    for d in daily_data.values():
        key = (d["year"], d["month"])
        acc = monthly_acc[key]
        acc["sw"] += d["sum_weighted_battery"]
        acc["sg"] += d["sum_gen"]
        acc["sp"] += d["sum_price"]
        acc["c"] += d["count"]

    monthly_list: list[dict] = []
    for (year, month) in sorted(monthly_acc):
        acc = monthly_acc[(year, month)]
        bl, cap, rat = _finalize(acc["sw"], acc["sg"], acc["sp"], acc["c"])
        monthly_list.append({
            "year": year,
            "month": month,
            "baseload": bl,
            "capture": cap,
            "ratio": rat,
        })

    # --- yearly ---
    yearly_acc: dict[int, dict] = defaultdict(
        lambda: {"sw": 0.0, "sg": 0.0, "sp": 0.0, "c": 0}
    )
    for d in daily_data.values():
        acc = yearly_acc[d["year"]]
        acc["sw"] += d["sum_weighted_battery"]
        acc["sg"] += d["sum_gen"]
        acc["sp"] += d["sum_price"]
        acc["c"] += d["count"]

    yearly_list: list[dict] = []
    for year in sorted(yearly_acc):
        acc = yearly_acc[year]
        bl, cap, rat = _finalize(acc["sw"], acc["sg"], acc["sp"], acc["c"])
        yearly_list.append({
            "year": year,
            "baseload": bl,
            "capture": cap,
            "ratio": rat,
        })

    return {"yearly": yearly_list, "monthly": monthly_list, "daily": daily_list}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def calculate_bess_data(
    spot_prices_by_zone: dict[str, dict[str, list[dict]]],
    pvsyst_profiles: dict[str, dict[tuple[int, int, int], float]],
    zones: list[str],
) -> dict:
    """Calculate BESS dashboard data for all zones.

    Parameters
    ----------
    spot_prices_by_zone : dict
        ``{zone: {date_key: [{utc_hour: int, eur_mwh: float}]}}``.
    pvsyst_profiles : dict
        ``{profile_key: {(month, day, hour): power_mw}}``.
    zones : list[str]
        List of zone strings (e.g. ``["SE1", "SE2", "SE3", "SE4"]``).

    Returns
    -------
    dict with profiles, colors, profile_meta, and data per zone/profile.
    """
    data: dict[str, dict] = {}

    for zone in zones:
        print(f"  BESS {zone}...")
        spot = spot_prices_by_zone.get(zone, {})
        if not spot:
            continue

        # Build daily_prices: {date_key: [price_h0, ..., price_h23]}
        daily_prices: dict[str, list[float]] = {}
        for date_key in sorted(spot):
            hours = spot[date_key]
            price_by_hour: dict[int, float] = {}
            for h_rec in hours:
                price_by_hour[h_rec["utc_hour"]] = h_rec["eur_mwh"]
            # Build ordered list for hours 0..23
            if price_by_hour:
                max_h = max(price_by_hour.keys())
                prices = [price_by_hour.get(h, 0.0) for h in range(max_h + 1)]
                daily_prices[date_key] = prices

        zone_data: dict[str, dict] = {}

        # --- Standalone Arbitrage ---
        for duration in DURATION_PRESETS:
            profile_key = f"arb_{duration}h"
            capacity_mwh = POWER_MW * duration
            arb_daily: dict[str, dict] = {}

            for date_key, prices in daily_prices.items():
                d = date.fromisoformat(date_key)
                revenue, cycles, avg_buy, avg_sell = optimize_hourly_arbitrage(
                    prices, capacity_mwh
                )
                arb_daily[date_key] = {
                    "date": d,
                    "year": d.year,
                    "month": d.month,
                    "revenue": revenue,
                    "cycles": cycles,
                    "avg_buy": avg_buy,
                    "avg_sell": avg_sell,
                }

            zone_data[profile_key] = _aggregate_bess(arb_daily, "revenue")

        # --- Spread ---
        spread_daily: dict[str, dict] = {}
        for date_key, prices in daily_prices.items():
            d = date.fromisoformat(date_key)
            spread, min_p, max_p = calculate_daily_spread(prices)
            spread_daily[date_key] = {
                "date": d,
                "year": d.year,
                "month": d.month,
                "spread": spread,
                "min_price": min_p,
                "max_price": max_p,
            }
        zone_data["spread"] = _aggregate_bess(spread_daily, "spread")

        # --- Solar+BESS ---
        sol_profile = pvsyst_profiles.get("sol_syd", {})
        if sol_profile:
            for duration in DURATION_PRESETS:
                profile_key = f"sol_bess_{duration}h"
                capacity_mwh = POWER_MW * duration
                sol_bess_daily: dict[str, dict] = {}

                for date_key, prices in daily_prices.items():
                    d = date.fromisoformat(date_key)
                    n_hours = len(prices)

                    # Build solar_mw array aligned to UTC hours
                    solar_mw: list[float] = []
                    for utc_hour in range(n_hours):
                        utc_dt = datetime(
                            d.year, d.month, d.day, utc_hour, tzinfo=UTC_TZ
                        )
                        local_dt = utc_dt.astimezone(SWEDEN_TZ)
                        key = (local_dt.month, local_dt.day, local_dt.hour)
                        solar_mw.append(sol_profile.get(key, 0.0))

                    rev_direct, rev_battery = optimize_btm_hourly(
                        prices, solar_mw, capacity_mwh
                    )

                    # sum_gen = total solar production (MWh)
                    sum_gen = sum(solar_mw)
                    # sum_price = sum of hourly spot prices
                    sum_price = sum(prices)
                    count = n_hours

                    sol_bess_daily[date_key] = {
                        "date": d,
                        "year": d.year,
                        "month": d.month,
                        "sum_weighted_battery": rev_battery,
                        "sum_gen": sum_gen,
                        "sum_price": sum_price,
                        "count": count,
                    }

                zone_data[profile_key] = _aggregate_sol_bess(sol_bess_daily)

        data[zone] = zone_data

    return {
        "profiles": {**ARBITRAGE_PROFILES, **SPREAD_PROFILES, **SOL_BESS_PROFILES},
        "colors": {**ARBITRAGE_COLORS, **SPREAD_COLORS, **SOL_BESS_COLORS},
        "profile_meta": dict(BESS_PROFILE_META),
        "data": data,
    }
