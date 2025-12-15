"""Behind-the-Meter (BTM) solar+battery optimization.

This module calculates optimal battery operation for solar parks where:
- Battery can ONLY charge from solar production (no grid import)
- Battery can discharge to grid at any time
- Goal: Maximize revenue by storing solar for high-price hours

The algorithm uses dynamic programming to find the optimal charge/discharge
schedule while respecting State of Charge (SoC) constraints.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from statistics import mean
from typing import Optional

from .battery import read_price_data_by_day, ROUND_TRIP_EFFICIENCY
from .config import DATA_DIR
from .solar_profile import get_pvsyst_weight, load_pvsyst_profile, SOLAR_PROFILES_DIR


@dataclass
class BTMQuarterResult:
    """Result for a single quarter in BTM analysis."""

    timestamp: Optional[datetime]
    solar_mwh: float
    price_eur: float
    action: str  # 'sell', 'charge', 'discharge', 'charge+sell'
    sold_mwh: float
    charged_mwh: float
    discharged_mwh: float
    soc_before: float
    soc_after: float
    revenue_eur: float


@dataclass
class BTMDayResult:
    """Result for a full day of BTM optimization."""

    date: date
    total_solar_mwh: float
    revenue_direct_eur: float  # Revenue if all solar sold immediately
    revenue_with_battery_eur: float  # Revenue with optimal battery usage
    battery_gain_eur: float  # Extra revenue from battery
    avg_price_direct: float  # Average price when selling directly
    avg_price_with_battery: float  # Effective average price with battery
    total_charged_mwh: float
    total_discharged_mwh: float
    cycles: float  # Number of full battery cycles
    schedule: list[BTMQuarterResult] = field(default_factory=list)


def get_solar_production_mw(
    timestamp: datetime,
    installed_mwp: float,
    profile: str = "south_lundby",
) -> float:
    """
    Get solar power output in MW for a given timestamp.

    Args:
        timestamp: The datetime to get production for
        installed_mwp: Installed solar capacity in MWp (DC)
        profile: Solar profile name (e.g., 'south_lundby', 'ew_boda')

    Returns:
        Power output in MW (AC, after inverter losses)
    """
    # Get normalized weight from profile (MW per MW installed)
    weight = get_pvsyst_weight(timestamp, profile)

    # Scale by installed capacity
    # PVsyst profiles are normalized to 1 MW, so direct multiplication works
    return weight * installed_mwp


def get_daily_solar_production(
    day: date,
    installed_mwp: float,
    profile: str = "south_lundby",
) -> list[tuple[datetime, float]]:
    """
    Get solar production for all 96 quarters of a day.

    Args:
        day: Date to get production for
        installed_mwp: Installed capacity in MWp
        profile: Solar profile name

    Returns:
        List of (timestamp, power_mw) tuples for each quarter
    """
    production = []

    for hour in range(24):
        for minute in [0, 15, 30, 45]:
            ts = datetime(day.year, day.month, day.day, hour, minute)
            power_mw = get_solar_production_mw(ts, installed_mwp, profile)
            production.append((ts, power_mw))

    return production


def optimize_btm_day(
    prices: list[float],
    solar_mw: list[float],
    timestamps: Optional[list[datetime]] = None,
    battery_mwh: float = 1.0,
    battery_mw: float = 1.0,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> tuple[float, float, list[BTMQuarterResult]]:
    """
    Optimize BTM solar+battery for a single day using dynamic programming.

    The battery can only charge from solar production (no grid import).
    Revenue comes from selling solar directly or storing it for later.

    Args:
        prices: List of quarterly prices in EUR/MWh (96 quarters)
        solar_mw: List of solar power output in MW for each quarter
        timestamps: Optional list of timestamps
        battery_mwh: Battery capacity in MWh
        battery_mw: Battery power rating in MW (charge/discharge rate)
        efficiency: Round-trip efficiency (applied at discharge)

    Returns:
        Tuple of (revenue_direct, revenue_with_battery, schedule)
    """
    n_quarters = len(prices)
    if n_quarters == 0 or len(solar_mw) != n_quarters:
        return 0.0, 0.0, []

    # Quarter duration in hours
    quarter_hours = 0.25

    # Calculate direct revenue (selling all solar immediately)
    revenue_direct = 0.0
    for t in range(n_quarters):
        solar_mwh_t = solar_mw[t] * quarter_hours
        revenue_direct += solar_mwh_t * prices[t]

    # If no battery, return direct revenue with simple schedule
    if battery_mwh <= 0 or battery_mw <= 0:
        schedule = []
        for t in range(n_quarters):
            solar_mwh_t = solar_mw[t] * quarter_hours
            ts = timestamps[t] if timestamps else None
            schedule.append(BTMQuarterResult(
                timestamp=ts,
                solar_mwh=solar_mwh_t,
                price_eur=prices[t],
                action="sell",
                sold_mwh=round(solar_mwh_t, 4),
                charged_mwh=0,
                discharged_mwh=0,
                soc_before=0,
                soc_after=0,
                revenue_eur=round(solar_mwh_t * prices[t], 4),
            ))
        return round(revenue_direct, 2), round(revenue_direct, 2), schedule

    # Max energy per quarter based on battery power
    max_quarter_energy = battery_mw * quarter_hours

    # Discretize SoC (using steps of max_quarter_energy for simplicity)
    soc_step = max_quarter_energy
    n_soc_levels = int(battery_mwh / soc_step) + 1
    soc_levels = [i * soc_step for i in range(n_soc_levels)]

    # DP: dp[soc_idx] = max revenue from current quarter onwards
    NEG_INF = float("-inf")

    # Initialize for last quarter + 1 (base case)
    dp_next = [0.0 for _ in range(n_soc_levels)]

    # Track decisions for reconstruction
    decisions = []

    # Backward DP iteration
    for t in range(n_quarters - 1, -1, -1):
        price = prices[t]
        solar_mwh = solar_mw[t] * quarter_hours

        dp_curr = [NEG_INF for _ in range(n_soc_levels)]
        decision_t = [None for _ in range(n_soc_levels)]

        for s_idx in range(n_soc_levels):
            soc = soc_levels[s_idx]
            best_value = NEG_INF
            best_decision = None

            # Option 1: Sell all solar, keep battery idle
            # Revenue = solar_mwh * price
            value = solar_mwh * price + dp_next[s_idx]
            if value > best_value:
                best_value = value
                best_decision = ("sell", 0, 0)

            # Option 2: Charge battery from solar (if solar > 0 and room in battery)
            if solar_mwh > 0 and soc < battery_mwh:
                # Max we can charge this quarter
                available_capacity = battery_mwh - soc
                charge_possible = min(solar_mwh, max_quarter_energy, available_capacity)

                for charge_steps in range(1, int(charge_possible / soc_step) + 1):
                    charge_mwh = charge_steps * soc_step
                    if charge_mwh > solar_mwh:
                        break

                    sold_mwh = solar_mwh - charge_mwh
                    new_s_idx = s_idx + charge_steps

                    if new_s_idx < n_soc_levels:
                        value = sold_mwh * price + dp_next[new_s_idx]
                        if value > best_value:
                            best_value = value
                            best_decision = ("charge", charge_mwh, 0)

            # Option 3: Discharge battery (can combine with selling solar)
            if soc > 0:
                discharge_possible = min(soc, max_quarter_energy)

                for discharge_steps in range(1, int(discharge_possible / soc_step) + 1):
                    discharge_mwh = discharge_steps * soc_step
                    new_s_idx = s_idx - discharge_steps

                    if new_s_idx >= 0:
                        # Revenue from solar + discharged energy (with efficiency loss)
                        total_sold = solar_mwh + discharge_mwh * efficiency
                        value = total_sold * price + dp_next[new_s_idx]
                        if value > best_value:
                            best_value = value
                            best_decision = ("discharge", 0, discharge_mwh)

            dp_curr[s_idx] = best_value
            decision_t[s_idx] = best_decision

        decisions.insert(0, decision_t)
        dp_next = dp_curr

    # Optimal value starting with empty battery (soc=0)
    revenue_with_battery = dp_next[0]

    # Reconstruct schedule
    schedule = []
    soc = 0.0
    s_idx = 0

    for t in range(n_quarters):
        price = prices[t]
        solar_mwh = solar_mw[t] * quarter_hours
        ts = timestamps[t] if timestamps else None
        decision = decisions[t][s_idx]

        if decision is None:
            # Fallback: just sell solar
            action = "sell"
            charged = 0.0
            discharged = 0.0
            sold = solar_mwh
        else:
            action_type, charged, discharged = decision

            if action_type == "sell":
                action = "sell"
                sold = solar_mwh
            elif action_type == "charge":
                sold = solar_mwh - charged
                action = "charge" if sold == 0 else "charge+sell"
                s_idx += int(charged / soc_step)
            else:  # discharge
                sold = solar_mwh + discharged * efficiency
                action = "discharge" if solar_mwh == 0 else "discharge+sell"
                s_idx -= int(discharged / soc_step)

        soc_before = soc
        soc_after = soc + charged - discharged
        revenue = sold * price

        schedule.append(BTMQuarterResult(
            timestamp=ts,
            solar_mwh=solar_mwh,
            price_eur=price,
            action=action,
            sold_mwh=round(sold, 4),
            charged_mwh=round(charged, 4),
            discharged_mwh=round(discharged, 4),
            soc_before=round(soc_before, 4),
            soc_after=round(soc_after, 4),
            revenue_eur=round(revenue, 4),
        ))

        soc = soc_after

    return round(revenue_direct, 2), round(revenue_with_battery, 2), schedule


def calculate_btm_day(
    zone: str,
    day: date,
    installed_mwp: float,
    battery_mwh: float,
    battery_mw: float,
    profile: str = "south_lundby",
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> BTMDayResult:
    """
    Calculate BTM optimization for a specific day.

    Args:
        zone: Electricity zone (SE1-SE4)
        day: Date to analyze
        installed_mwp: Installed solar capacity in MWp
        battery_mwh: Battery capacity in MWh
        battery_mw: Battery power in MW
        profile: Solar profile name
        efficiency: Round-trip efficiency

    Returns:
        BTMDayResult with all metrics
    """
    # Get price data for the day
    by_day = read_price_data_by_day(zone)

    if day not in by_day:
        return BTMDayResult(
            date=day,
            total_solar_mwh=0,
            revenue_direct_eur=0,
            revenue_with_battery_eur=0,
            battery_gain_eur=0,
            avg_price_direct=0,
            avg_price_with_battery=0,
            total_charged_mwh=0,
            total_discharged_mwh=0,
            cycles=0,
        )

    records = sorted(by_day[day], key=lambda r: r["timestamp"])
    prices = [r["price_eur"] for r in records]
    timestamps = [r["timestamp"] for r in records]

    # Get solar production for each quarter
    solar_production = get_daily_solar_production(day, installed_mwp, profile)
    solar_mw = [p[1] for p in solar_production]

    # Ensure we have matching lengths (take minimum if different)
    n = min(len(prices), len(solar_mw))
    prices = prices[:n]
    solar_mw = solar_mw[:n]
    timestamps = timestamps[:n]

    # Run optimization
    revenue_direct, revenue_with_battery, schedule = optimize_btm_day(
        prices=prices,
        solar_mw=solar_mw,
        timestamps=timestamps,
        battery_mwh=battery_mwh,
        battery_mw=battery_mw,
        efficiency=efficiency,
    )

    # Calculate metrics
    total_solar = sum(s.solar_mwh for s in schedule)
    total_charged = sum(s.charged_mwh for s in schedule)
    total_discharged = sum(s.discharged_mwh for s in schedule)
    cycles = total_discharged / battery_mwh if battery_mwh > 0 else 0

    avg_price_direct = revenue_direct / total_solar if total_solar > 0 else 0
    avg_price_with_battery = revenue_with_battery / total_solar if total_solar > 0 else 0

    return BTMDayResult(
        date=day,
        total_solar_mwh=round(total_solar, 2),
        revenue_direct_eur=revenue_direct,
        revenue_with_battery_eur=revenue_with_battery,
        battery_gain_eur=round(revenue_with_battery - revenue_direct, 2),
        avg_price_direct=round(avg_price_direct, 2),
        avg_price_with_battery=round(avg_price_with_battery, 2),
        total_charged_mwh=round(total_charged, 2),
        total_discharged_mwh=round(total_discharged, 2),
        cycles=round(cycles, 2),
        schedule=schedule,
    )


def calculate_btm_annual(
    zone: str,
    year: int,
    installed_mwp: float,
    battery_mwh: float,
    battery_mw: float,
    profile: str = "south_lundby",
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> dict:
    """
    Calculate annual BTM revenue with battery vs without.

    Args:
        zone: Electricity zone (SE1-SE4)
        year: Year to analyze
        installed_mwp: Installed solar capacity in MWp
        battery_mwh: Battery capacity in MWh
        battery_mw: Battery power in MW
        profile: Solar profile name
        efficiency: Round-trip efficiency

    Returns:
        Dict with annual metrics and monthly breakdown
    """
    by_day = read_price_data_by_day(zone, year)

    total_solar = 0.0
    total_revenue_direct = 0.0
    total_revenue_battery = 0.0
    total_cycles = 0.0
    monthly_results = defaultdict(lambda: {
        "solar_mwh": 0, "revenue_direct": 0, "revenue_battery": 0, "cycles": 0, "days": 0
    })
    daily_results = []

    for day in sorted(by_day.keys()):
        result = calculate_btm_day(
            zone=zone,
            day=day,
            installed_mwp=installed_mwp,
            battery_mwh=battery_mwh,
            battery_mw=battery_mw,
            profile=profile,
            efficiency=efficiency,
        )

        total_solar += result.total_solar_mwh
        total_revenue_direct += result.revenue_direct_eur
        total_revenue_battery += result.revenue_with_battery_eur
        total_cycles += result.cycles

        month_key = f"{day.year}-{day.month:02d}"
        monthly_results[month_key]["solar_mwh"] += result.total_solar_mwh
        monthly_results[month_key]["revenue_direct"] += result.revenue_direct_eur
        monthly_results[month_key]["revenue_battery"] += result.revenue_with_battery_eur
        monthly_results[month_key]["cycles"] += result.cycles
        monthly_results[month_key]["days"] += 1

        daily_results.append({
            "date": day,
            "solar_mwh": result.total_solar_mwh,
            "revenue_direct": result.revenue_direct_eur,
            "revenue_battery": result.revenue_with_battery_eur,
            "battery_gain": result.battery_gain_eur,
            "cycles": result.cycles,
        })

    battery_gain = total_revenue_battery - total_revenue_direct
    avg_price_direct = total_revenue_direct / total_solar if total_solar > 0 else 0
    avg_price_battery = total_revenue_battery / total_solar if total_solar > 0 else 0

    return {
        "zone": zone,
        "year": year,
        "installed_mwp": installed_mwp,
        "battery_mwh": battery_mwh,
        "battery_mw": battery_mw,
        "profile": profile,
        "total_solar_mwh": round(total_solar, 2),
        "revenue_direct_eur": round(total_revenue_direct, 2),
        "revenue_with_battery_eur": round(total_revenue_battery, 2),
        "battery_gain_eur": round(battery_gain, 2),
        "avg_price_direct": round(avg_price_direct, 2),
        "avg_price_with_battery": round(avg_price_battery, 2),
        "total_cycles": round(total_cycles, 1),
        "monthly": dict(monthly_results),
        "daily": daily_results,
    }


def compare_battery_sizes(
    zone: str,
    year: int,
    installed_mwp: float,
    battery_sizes_mwh: list[float],
    profile: str = "south_lundby",
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> list[dict]:
    """
    Compare different battery sizes for a solar park.

    Args:
        zone: Electricity zone (SE1-SE4)
        year: Year to analyze
        installed_mwp: Installed solar capacity in MWp
        battery_sizes_mwh: List of battery sizes to compare (in MWh)
        profile: Solar profile name
        efficiency: Round-trip efficiency

    Returns:
        List of dicts with results for each battery size
    """
    results = []

    # First calculate baseline (no battery)
    baseline = calculate_btm_annual(
        zone=zone,
        year=year,
        installed_mwp=installed_mwp,
        battery_mwh=0,
        battery_mw=0,
        profile=profile,
        efficiency=efficiency,
    )

    results.append({
        "battery_mwh": 0,
        "battery_mw": 0,
        "revenue_eur": baseline["revenue_direct_eur"],
        "gain_vs_baseline": 0,
        "gain_per_mwh": 0,
        "cycles": 0,
        "avg_price": baseline["avg_price_direct"],
    })

    # Calculate for each battery size
    for battery_mwh in battery_sizes_mwh:
        if battery_mwh <= 0:
            continue

        # Assume 1C rate (battery_mw = battery_mwh)
        battery_mw = battery_mwh

        annual = calculate_btm_annual(
            zone=zone,
            year=year,
            installed_mwp=installed_mwp,
            battery_mwh=battery_mwh,
            battery_mw=battery_mw,
            profile=profile,
            efficiency=efficiency,
        )

        gain = annual["revenue_with_battery_eur"] - baseline["revenue_direct_eur"]
        gain_per_mwh = gain / battery_mwh if battery_mwh > 0 else 0

        results.append({
            "battery_mwh": battery_mwh,
            "battery_mw": battery_mw,
            "revenue_eur": annual["revenue_with_battery_eur"],
            "gain_vs_baseline": round(gain, 2),
            "gain_per_mwh": round(gain_per_mwh, 2),
            "cycles": annual["total_cycles"],
            "avg_price": annual["avg_price_with_battery"],
        })

    return results


def format_btm_summary(annual_result: dict) -> str:
    """Format annual BTM result as terminal output."""
    lines = []
    lines.append(f"\nBehind-the-Meter Analysis - {annual_result['zone']}")
    lines.append("=" * 60)
    lines.append(f"Solar park: {annual_result['installed_mwp']} MWp ({annual_result['profile']} profile)")
    lines.append(f"Battery: {annual_result['battery_mwh']} MWh / {annual_result['battery_mw']} MW")
    lines.append("")
    lines.append(f"{annual_result['year']} Annual Results:")
    lines.append("-" * 60)
    lines.append(f"{'':25} {'Without Battery':>17} {'With Battery':>15}")
    lines.append(f"{'Solar production:':25} {annual_result['total_solar_mwh']:>14,.0f} MWh {'-':>15}")
    lines.append(f"{'Revenue:':25} {annual_result['revenue_direct_eur']:>14,.0f} EUR {annual_result['revenue_with_battery_eur']:>12,.0f} EUR")
    lines.append(f"{'Avg price:':25} {annual_result['avg_price_direct']:>12.2f} EUR/MWh {annual_result['avg_price_with_battery']:>10.2f} EUR/MWh")
    lines.append("")
    lines.append(f"Battery gain: +{annual_result['battery_gain_eur']:,.0f} EUR ({annual_result['battery_gain_eur']/annual_result['revenue_direct_eur']*100:.1f}%)")
    lines.append(f"Total cycles: {annual_result['total_cycles']:.0f}")

    return "\n".join(lines)


def format_battery_comparison(results: list[dict], installed_mwp: float) -> str:
    """Format battery size comparison as terminal output."""
    lines = []
    lines.append(f"\nBattery Size Comparison - {installed_mwp} MWp Solar Park")
    lines.append("=" * 75)
    lines.append(f"{'Battery':<12} {'Revenue':>14} {'Gain vs 0':>14} {'Gain/MWh':>12} {'Cycles':>10}")
    lines.append("-" * 75)

    for r in results:
        gain_str = f"+{r['gain_vs_baseline']:,.0f}" if r['gain_vs_baseline'] > 0 else "-"
        gain_mwh_str = f"{r['gain_per_mwh']:,.0f}" if r['battery_mwh'] > 0 else "-"
        cycles_str = f"{r['cycles']:.0f}" if r['battery_mwh'] > 0 else "-"

        lines.append(
            f"{r['battery_mwh']:.0f} MWh      "
            f"{r['revenue_eur']:>11,.0f} EUR "
            f"{gain_str:>14} "
            f"{gain_mwh_str:>12} "
            f"{cycles_str:>10}"
        )

    # Find optimal (best gain per MWh)
    optimal = max(
        [r for r in results if r['battery_mwh'] > 0],
        key=lambda x: x['gain_per_mwh'],
        default=None
    )

    if optimal:
        lines.append("")
        pct = optimal['battery_mwh'] / installed_mwp * 100
        lines.append(f"Recommendation: {optimal['battery_mwh']:.0f} MWh ({pct:.0f}% of PV) - best gain per MWh")

    return "\n".join(lines)
