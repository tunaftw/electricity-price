"""Battery arbitrage analysis - intraday volatility and revenue calculations.

This module provides both legacy (simplified) and optimal (DP-based) battery
arbitrage calculations. The optimal algorithm uses dynamic programming to
find the best charge/discharge schedule while respecting State of Charge (SoC)
constraints.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from statistics import mean, stdev, median
from typing import Optional

from .config import QUARTERLY_DIR, RAW_DIR, ZONES, DATA_DIR

# Battery parameters
ROUND_TRIP_EFFICIENCY = 0.88  # 88% round-trip efficiency

# Reports directory
REPORTS_DIR = DATA_DIR / "reports"


def read_price_data_by_day(zone: str, year: int | None = None) -> dict[date, list[dict]]:
    """
    Read price data and group by day.

    Args:
        zone: Electricity zone (SE1-SE4)
        year: Optional year filter

    Returns:
        Dict mapping date to list of price records for that day
    """
    # Try quarterly data first (15-min resolution), fall back to raw (hourly)
    base_dir = QUARTERLY_DIR if QUARTERLY_DIR.exists() else RAW_DIR
    zone_dir = base_dir / zone

    if not zone_dir.exists():
        return {}

    by_day: dict[date, list[dict]] = defaultdict(list)

    for csv_file in sorted(zone_dir.glob("*.csv")):
        # Filter by year if specified
        if year:
            try:
                file_year = int(csv_file.stem.split("-")[0])
                if file_year != year:
                    continue
            except ValueError:
                continue

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["time_start"])
                price_eur = float(row.get("EUR_per_kWh", 0)) * 1000  # Convert to EUR/MWh
                price_sek = float(row.get("SEK_per_kWh", 0)) * 1000  # Convert to SEK/MWh

                by_day[ts.date()].append({
                    "timestamp": ts,
                    "hour": ts.hour,
                    "minute": ts.minute,
                    "price_eur": price_eur,
                    "price_sek": price_sek,
                })

    return dict(by_day)


def extract_daily_stats(zone: str, year: int | None = None) -> list[dict]:
    """
    Extract daily price statistics for a zone.

    Args:
        zone: Electricity zone
        year: Optional year filter

    Returns:
        List of daily stats dicts
    """
    by_day = read_price_data_by_day(zone, year)

    daily_stats = []

    for day, records in sorted(by_day.items()):
        if not records:
            continue

        prices = [r["price_eur"] for r in records]

        min_price = min(prices)
        max_price = max(prices)
        spread = max_price - min_price
        avg_price = mean(prices)
        median_price = median(prices)
        std_price = stdev(prices) if len(prices) > 1 else 0

        # Find hours with min/max prices
        min_record = min(records, key=lambda r: r["price_eur"])
        max_record = max(records, key=lambda r: r["price_eur"])

        daily_stats.append({
            "date": day,
            "zone": zone,
            "min_eur": round(min_price, 2),
            "max_eur": round(max_price, 2),
            "spread": round(spread, 2),
            "avg_eur": round(avg_price, 2),
            "median_eur": round(median_price, 2),
            "std_eur": round(std_price, 2),
            "min_hour": min_record["hour"],
            "max_hour": max_record["hour"],
            "records": len(records),
        })

    return daily_stats


def extract_hourly_profile(zone: str, year: int | None = None) -> dict[int, float]:
    """
    Calculate average price per hour (0-23) for a zone.

    Args:
        zone: Electricity zone
        year: Optional year filter

    Returns:
        Dict mapping hour (0-23) to average EUR/MWh
    """
    by_day = read_price_data_by_day(zone, year)

    hourly_prices: dict[int, list[float]] = defaultdict(list)

    for records in by_day.values():
        for r in records:
            hourly_prices[r["hour"]].append(r["price_eur"])

    return {
        hour: round(mean(prices), 2)
        for hour, prices in sorted(hourly_prices.items())
    }


def calculate_1cycle_revenue(
    daily_stats: list[dict],
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> dict:
    """
    Calculate arbitrage revenue for 1 cycle per day strategy.

    Strategy: Charge at daily minimum, discharge at daily maximum.

    Args:
        daily_stats: List of daily stats from extract_daily_stats
        efficiency: Round-trip efficiency (0-1)

    Returns:
        Dict with revenue statistics
    """
    total_revenue = 0.0
    profitable_days = 0
    revenues = []

    for day in daily_stats:
        # Revenue = sell price * efficiency - buy price
        # For 1 MWh capacity discharging 1 MWh
        buy_price = day["min_eur"]
        sell_price = day["max_eur"]

        # Net revenue after efficiency loss
        revenue = sell_price * efficiency - buy_price

        if revenue > 0:
            profitable_days += 1
            total_revenue += revenue

        revenues.append({
            "date": day["date"],
            "buy_price": buy_price,
            "sell_price": sell_price,
            "gross_spread": day["spread"],
            "net_revenue": round(revenue, 2),
            "buy_hour": day["min_hour"],
            "sell_hour": day["max_hour"],
        })

    return {
        "total_revenue_eur": round(total_revenue, 2),
        "avg_daily_revenue": round(total_revenue / len(daily_stats), 2) if daily_stats else 0,
        "profitable_days": profitable_days,
        "total_days": len(daily_stats),
        "profitable_pct": round(profitable_days / len(daily_stats) * 100, 1) if daily_stats else 0,
        "daily_revenues": revenues,
    }


def calculate_2cycle_revenue(
    zone: str,
    year: int | None = None,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> dict:
    """
    Calculate arbitrage revenue for 2 cycles per day strategy.

    Strategy:
    - Cycle 1: Charge night (00-06), discharge morning peak (07-10)
    - Cycle 2: Charge midday (11-15), discharge evening peak (17-21)

    Args:
        zone: Electricity zone
        year: Optional year filter
        efficiency: Round-trip efficiency (0-1)

    Returns:
        Dict with revenue statistics
    """
    by_day = read_price_data_by_day(zone, year)

    total_revenue = 0.0
    profitable_days = 0
    revenues = []

    for day, records in sorted(by_day.items()):
        if not records:
            continue

        # Group by hour
        by_hour: dict[int, list[float]] = defaultdict(list)
        for r in records:
            by_hour[r["hour"]].append(r["price_eur"])

        # Calculate average price per hour
        hourly_avg = {h: mean(p) for h, p in by_hour.items()}

        # Cycle 1: Night charge (00-06) -> Morning discharge (07-10)
        night_hours = [h for h in range(0, 7) if h in hourly_avg]
        morning_hours = [h for h in range(7, 11) if h in hourly_avg]

        if night_hours and morning_hours:
            night_price = mean([hourly_avg[h] for h in night_hours])
            morning_price = mean([hourly_avg[h] for h in morning_hours])
            cycle1_revenue = morning_price * efficiency - night_price
        else:
            cycle1_revenue = 0

        # Cycle 2: Midday charge (11-15) -> Evening discharge (17-21)
        midday_hours = [h for h in range(11, 16) if h in hourly_avg]
        evening_hours = [h for h in range(17, 22) if h in hourly_avg]

        if midday_hours and evening_hours:
            midday_price = mean([hourly_avg[h] for h in midday_hours])
            evening_price = mean([hourly_avg[h] for h in evening_hours])
            cycle2_revenue = evening_price * efficiency - midday_price
        else:
            cycle2_revenue = 0

        # Only count positive revenue
        day_revenue = max(0, cycle1_revenue) + max(0, cycle2_revenue)

        if day_revenue > 0:
            profitable_days += 1
            total_revenue += day_revenue

        revenues.append({
            "date": day,
            "cycle1_revenue": round(cycle1_revenue, 2),
            "cycle2_revenue": round(cycle2_revenue, 2),
            "total_revenue": round(day_revenue, 2),
        })

    return {
        "total_revenue_eur": round(total_revenue, 2),
        "avg_daily_revenue": round(total_revenue / len(revenues), 2) if revenues else 0,
        "profitable_days": profitable_days,
        "total_days": len(revenues),
        "profitable_pct": round(profitable_days / len(revenues) * 100, 1) if revenues else 0,
        "daily_revenues": revenues,
    }


def aggregate_by_month(daily_stats: list[dict]) -> list[dict]:
    """
    Aggregate daily stats by month.

    Args:
        daily_stats: List of daily stats

    Returns:
        List of monthly aggregates
    """
    by_month: dict[str, list[dict]] = defaultdict(list)

    for day in daily_stats:
        month_key = day["date"].strftime("%Y-%m")
        by_month[month_key].append(day)

    monthly = []
    for month, days in sorted(by_month.items()):
        spreads = [d["spread"] for d in days]
        monthly.append({
            "period": month,
            "zone": days[0]["zone"],
            "avg_spread": round(mean(spreads), 2),
            "median_spread": round(median(spreads), 2),
            "max_spread": round(max(spreads), 2),
            "min_spread": round(min(spreads), 2),
            "std_spread": round(stdev(spreads), 2) if len(spreads) > 1 else 0,
            "days": len(days),
        })

    return monthly


def aggregate_by_year(daily_stats: list[dict]) -> list[dict]:
    """
    Aggregate daily stats by year.

    Args:
        daily_stats: List of daily stats

    Returns:
        List of yearly aggregates
    """
    by_year: dict[int, list[dict]] = defaultdict(list)

    for day in daily_stats:
        by_year[day["date"].year].append(day)

    yearly = []
    for year, days in sorted(by_year.items()):
        spreads = [d["spread"] for d in days]
        yearly.append({
            "period": str(year),
            "zone": days[0]["zone"],
            "avg_spread": round(mean(spreads), 2),
            "median_spread": round(median(spreads), 2),
            "max_spread": round(max(spreads), 2),
            "min_spread": round(min(spreads), 2),
            "std_spread": round(stdev(spreads), 2) if len(spreads) > 1 else 0,
            "days": len(days),
        })

    return yearly


def format_terminal_table(
    monthly_stats: list[dict],
    revenue_stats: dict,
    zone: str,
) -> str:
    """Format stats as terminal table."""
    lines = []
    lines.append(f"\nBattery Arbitrage Analysis - {zone}")
    lines.append("=" * 90)
    lines.append(f"{'Period':<10} | {'Avg Spread':>12} | {'Median':>10} | {'Max Spread':>12} | {'Days':>6} | {'Revenue':>12}")
    lines.append("-" * 90)

    for m in monthly_stats:
        # Find revenue for this month
        month_revenues = [
            r for r in revenue_stats["daily_revenues"]
            if r["date"].strftime("%Y-%m") == m["period"]
        ]
        # Support both 1-cycle (net_revenue) and 2-cycle (total_revenue) formats
        revenue_key = "net_revenue" if "net_revenue" in month_revenues[0] else "total_revenue" if month_revenues else "net_revenue"
        month_revenue = sum(r.get(revenue_key, 0) for r in month_revenues if r.get(revenue_key, 0) > 0)

        lines.append(
            f"{m['period']:<10} | "
            f"{m['avg_spread']:>10.2f}  | "
            f"{m.get('median_spread', 0):>8.2f}  | "
            f"{m['max_spread']:>10.2f}  | "
            f"{m['days']:>6} | "
            f"{month_revenue:>10.2f}  "
        )

    lines.append("=" * 90)
    lines.append(f"Total Revenue: {revenue_stats['total_revenue_eur']:,.2f} EUR/MW")
    lines.append(f"Profitable Days: {revenue_stats['profitable_days']}/{revenue_stats['total_days']} ({revenue_stats['profitable_pct']:.1f}%)")

    return "\n".join(lines)


# =============================================================================
# OPTIMAL BATTERY ARBITRAGE WITH DYNAMIC PROGRAMMING
# =============================================================================


@dataclass
class QuarterAction:
    """Action for a single quarter period."""

    quarter_idx: int
    timestamp: Optional[datetime]
    action: str  # 'charge', 'discharge', 'idle'
    price_eur: float
    soc_before: float
    soc_after: float
    revenue: float  # negative for charge cost, positive for discharge revenue


@dataclass
class ArbitrageResult:
    """Result of battery arbitrage optimization."""

    revenue_eur: float
    schedule: list[QuarterAction] = field(default_factory=list)
    buy_quarters: list[int] = field(default_factory=list)
    sell_quarters: list[int] = field(default_factory=list)
    buy_prices: list[float] = field(default_factory=list)
    sell_prices: list[float] = field(default_factory=list)
    avg_buy_price: float = 0.0
    avg_sell_price: float = 0.0
    soc_trace: list[float] = field(default_factory=list)
    charges_used: int = 0
    discharges_used: int = 0


def optimize_battery_arbitrage(
    prices: list[float],
    timestamps: Optional[list[datetime]] = None,
    max_cycles: int = 1,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
    capacity_mwh: float = 1.0,
    power_mw: float = 1.0,
) -> ArbitrageResult:
    """
    Optimal battery arbitrage using dynamic programming.

    Finds the optimal charge/discharge schedule that maximizes revenue while
    respecting State of Charge (SoC) constraints. The algorithm considers
    all possible combinations of charge/discharge quarters and selects the
    one with maximum profit.

    Args:
        prices: List of quarterly prices in EUR/MWh (typically 96 for a full day)
        timestamps: Optional list of timestamps for each quarter
        max_cycles: Number of complete charge/discharge cycles (1 or 2)
        efficiency: Round-trip efficiency (applied at discharge)
        capacity_mwh: Battery capacity in MWh (default 1.0)
        power_mw: Battery power in MW (default 1.0 for 1C rate)

    Returns:
        ArbitrageResult with optimal schedule, revenue, and SoC trace

    Algorithm:
        Uses backward dynamic programming with state space:
        - t: quarter index (0 to n-1)
        - soc: state of charge (0, 0.25, 0.5, 0.75, 1.0 MWh for 1C rate)
        - charges: number of charge actions used
        - discharges: number of discharge actions used

        Complexity: O(n × 5 × (4×max_cycles+1)²) ≈ O(12,000) for 1-cycle
    """
    n_quarters = len(prices)
    if n_quarters == 0:
        return ArbitrageResult(revenue_eur=0.0)

    # Energy per quarter at given power rate (0.25 MWh at 1 MW for 15 min)
    quarter_energy = power_mw * 0.25

    # Discrete SoC levels (for 1 MWh battery at 1C: 0, 0.25, 0.5, 0.75, 1.0)
    n_soc_levels = int(capacity_mwh / quarter_energy) + 1
    soc_levels = [i * quarter_energy for i in range(n_soc_levels)]
    soc_to_idx = {round(soc, 4): i for i, soc in enumerate(soc_levels)}

    max_charges = 4 * max_cycles
    max_discharges = 4 * max_cycles

    # Initialize DP table with -infinity (impossible states)
    # dp[t][s][c][d] = maximum revenue achievable from quarter t onwards
    #                  given current SoC index s, c charges used, d discharges used
    NEG_INF = float("-inf")

    # Using nested lists for DP table
    dp = [
        [
            [[NEG_INF for _ in range(max_discharges + 1)] for _ in range(max_charges + 1)]
            for _ in range(n_soc_levels)
        ]
        for _ in range(n_quarters + 1)
    ]

    # Base case: at end of day, no more revenue possible from any valid state
    for s in range(n_soc_levels):
        for c in range(max_charges + 1):
            for d in range(max_discharges + 1):
                dp[n_quarters][s][c][d] = 0.0

    # Backward DP iteration
    for t in range(n_quarters - 1, -1, -1):
        price = prices[t]

        for s in range(n_soc_levels):
            soc = soc_levels[s]

            for c in range(max_charges + 1):
                for d in range(max_discharges + 1):
                    best = NEG_INF

                    # Action 1: Idle (always possible)
                    future_idle = dp[t + 1][s][c][d]
                    if future_idle > best:
                        best = future_idle

                    # Action 2: Charge (if room in battery and charges available)
                    if soc + quarter_energy <= capacity_mwh + 0.001 and c < max_charges:
                        new_s = s + 1
                        cost = price * quarter_energy  # Cost to buy electricity
                        future_charge = dp[t + 1][new_s][c + 1][d]
                        if future_charge != NEG_INF:
                            value = -cost + future_charge
                            if value > best:
                                best = value

                    # Action 3: Discharge (if energy in battery and discharges available)
                    if soc >= quarter_energy - 0.001 and d < max_discharges:
                        new_s = s - 1
                        revenue = price * quarter_energy * efficiency
                        future_discharge = dp[t + 1][new_s][c][d + 1]
                        if future_discharge != NEG_INF:
                            value = revenue + future_discharge
                            if value > best:
                                best = value

                    dp[t][s][c][d] = best

    # Optimal value starts at t=0, soc=0 (empty battery), no actions used
    optimal_revenue = dp[0][0][0][0]

    # If no profitable strategy exists, return zero
    if optimal_revenue <= 0 or optimal_revenue == NEG_INF:
        return ArbitrageResult(
            revenue_eur=0.0,
            soc_trace=[0.0] * (n_quarters + 1),
        )

    # Reconstruct optimal schedule via forward pass
    schedule = []
    soc_trace = [0.0]
    buy_quarters = []
    sell_quarters = []
    buy_prices = []
    sell_prices = []

    s = 0  # Start with empty battery (SoC index = 0)
    c = 0  # Charges used
    d = 0  # Discharges used

    for t in range(n_quarters):
        price = prices[t]
        soc = soc_levels[s]
        ts = timestamps[t] if timestamps else None

        best_action = "idle"
        best_value = dp[t + 1][s][c][d]

        # Check if charging is optimal
        if soc + quarter_energy <= capacity_mwh + 0.001 and c < max_charges:
            new_s = s + 1
            cost = price * quarter_energy
            value = -cost + dp[t + 1][new_s][c + 1][d]
            if value > best_value + 1e-9:
                best_value = value
                best_action = "charge"

        # Check if discharging is optimal
        if soc >= quarter_energy - 0.001 and d < max_discharges:
            new_s = s - 1
            revenue = price * quarter_energy * efficiency
            value = revenue + dp[t + 1][new_s][c][d + 1]
            if value > best_value + 1e-9:
                best_value = value
                best_action = "discharge"

        # Calculate SoC changes and revenue for this quarter
        soc_before = soc
        quarter_revenue = 0.0

        if best_action == "charge":
            soc_after = soc + quarter_energy
            quarter_revenue = -price * quarter_energy  # Cost (negative)
            s += 1
            c += 1
            buy_quarters.append(t)
            buy_prices.append(price)
        elif best_action == "discharge":
            soc_after = soc - quarter_energy
            quarter_revenue = price * quarter_energy * efficiency  # Revenue (positive)
            s -= 1
            d += 1
            sell_quarters.append(t)
            sell_prices.append(price)
        else:
            soc_after = soc

        schedule.append(
            QuarterAction(
                quarter_idx=t,
                timestamp=ts,
                action=best_action,
                price_eur=price,
                soc_before=round(soc_before, 4),
                soc_after=round(soc_after, 4),
                revenue=round(quarter_revenue, 4),
            )
        )
        soc_trace.append(round(soc_after, 4))

    # Calculate averages
    avg_buy = mean(buy_prices) if buy_prices else 0.0
    avg_sell = mean(sell_prices) if sell_prices else 0.0

    return ArbitrageResult(
        revenue_eur=round(optimal_revenue, 2),
        schedule=schedule,
        buy_quarters=buy_quarters,
        sell_quarters=sell_quarters,
        buy_prices=buy_prices,
        sell_prices=sell_prices,
        avg_buy_price=round(avg_buy, 2),
        avg_sell_price=round(avg_sell, 2),
        soc_trace=soc_trace,
        charges_used=c,
        discharges_used=d,
    )


def read_quarter_prices(zone: str, day: date) -> list[dict]:
    """
    Read all quarter prices for a specific day.

    Args:
        zone: Electricity zone (SE1-SE4)
        day: Date to read

    Returns:
        List of dicts with timestamp and price_eur for each quarter,
        sorted chronologically
    """
    by_day = read_price_data_by_day(zone)

    if day not in by_day:
        return []

    records = by_day[day]
    return sorted(records, key=lambda r: r["timestamp"])


def calculate_optimal_daily_arbitrage(
    zone: str,
    day: date,
    max_cycles: int = 1,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> ArbitrageResult:
    """
    Run optimal battery arbitrage for a single day.

    Args:
        zone: Electricity zone (SE1-SE4)
        day: Date to optimize
        max_cycles: 1 or 2 complete cycles
        efficiency: Round-trip efficiency

    Returns:
        ArbitrageResult with optimal schedule and revenue
    """
    records = read_quarter_prices(zone, day)

    if not records:
        return ArbitrageResult(revenue_eur=0.0)

    prices = [r["price_eur"] for r in records]
    timestamps = [r["timestamp"] for r in records]

    return optimize_battery_arbitrage(
        prices=prices,
        timestamps=timestamps,
        max_cycles=max_cycles,
        efficiency=efficiency,
    )


def calculate_optimal_1cycle_revenue(
    zone: str,
    year: int | None = None,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> dict:
    """
    Calculate 1-cycle revenue using optimal DP algorithm.

    This is the recommended method for accurate arbitrage calculations.
    It properly accounts for SoC constraints and selects optimal quarters
    for charging and discharging.

    Args:
        zone: Electricity zone (SE1-SE4)
        year: Optional year filter
        efficiency: Round-trip efficiency (0-1)

    Returns:
        Dict with revenue statistics and daily breakdown
    """
    by_day = read_price_data_by_day(zone, year)

    total_revenue = 0.0
    profitable_days = 0
    daily_results = []

    for day, records in sorted(by_day.items()):
        if not records:
            continue

        # Sort records chronologically
        records = sorted(records, key=lambda r: r["timestamp"])
        prices = [r["price_eur"] for r in records]
        timestamps = [r["timestamp"] for r in records]

        # Run DP optimization
        result = optimize_battery_arbitrage(
            prices=prices,
            timestamps=timestamps,
            max_cycles=1,
            efficiency=efficiency,
        )

        if result.revenue_eur > 0:
            profitable_days += 1
            total_revenue += result.revenue_eur

        daily_results.append({
            "date": day,
            "revenue_eur": result.revenue_eur,
            "avg_buy_price": result.avg_buy_price,
            "avg_sell_price": result.avg_sell_price,
            "buy_quarters": result.buy_quarters,
            "sell_quarters": result.sell_quarters,
            "charges_used": result.charges_used,
            "discharges_used": result.discharges_used,
        })

    n_days = len(daily_results)

    return {
        "total_revenue_eur": round(total_revenue, 2),
        "avg_daily_revenue": round(total_revenue / n_days, 2) if n_days else 0,
        "profitable_days": profitable_days,
        "total_days": n_days,
        "profitable_pct": round(profitable_days / n_days * 100, 1) if n_days else 0,
        "daily_results": daily_results,
    }


def calculate_optimal_2cycle_revenue(
    zone: str,
    year: int | None = None,
    efficiency: float = ROUND_TRIP_EFFICIENCY,
) -> dict:
    """
    Calculate 2-cycle revenue using optimal DP algorithm.

    Finds the optimal schedule for 2 complete charge/discharge cycles per day.
    Unlike the legacy fixed-window approach, this optimizes freely across
    all quarters.

    Args:
        zone: Electricity zone (SE1-SE4)
        year: Optional year filter
        efficiency: Round-trip efficiency (0-1)

    Returns:
        Dict with revenue statistics and daily breakdown
    """
    by_day = read_price_data_by_day(zone, year)

    total_revenue = 0.0
    profitable_days = 0
    daily_results = []

    for day, records in sorted(by_day.items()):
        if not records:
            continue

        # Sort records chronologically
        records = sorted(records, key=lambda r: r["timestamp"])
        prices = [r["price_eur"] for r in records]
        timestamps = [r["timestamp"] for r in records]

        # Run DP optimization with 2 cycles
        result = optimize_battery_arbitrage(
            prices=prices,
            timestamps=timestamps,
            max_cycles=2,
            efficiency=efficiency,
        )

        if result.revenue_eur > 0:
            profitable_days += 1
            total_revenue += result.revenue_eur

        daily_results.append({
            "date": day,
            "revenue_eur": result.revenue_eur,
            "avg_buy_price": result.avg_buy_price,
            "avg_sell_price": result.avg_sell_price,
            "buy_quarters": result.buy_quarters,
            "sell_quarters": result.sell_quarters,
            "charges_used": result.charges_used,
            "discharges_used": result.discharges_used,
        })

    n_days = len(daily_results)

    return {
        "total_revenue_eur": round(total_revenue, 2),
        "avg_daily_revenue": round(total_revenue / n_days, 2) if n_days else 0,
        "profitable_days": profitable_days,
        "total_days": n_days,
        "profitable_pct": round(profitable_days / n_days * 100, 1) if n_days else 0,
        "daily_results": daily_results,
    }


def format_optimal_schedule(result: ArbitrageResult, day: date) -> str:
    """Format optimal schedule as readable string."""
    lines = []
    lines.append(f"\nOptimal Schedule for {day}")
    lines.append("=" * 70)

    if result.revenue_eur <= 0:
        lines.append("No profitable arbitrage opportunity.")
        return "\n".join(lines)

    lines.append(f"{'Time':<12} {'Action':<10} {'Price EUR/MWh':>14} {'SoC':>12}")
    lines.append("-" * 70)

    for action in result.schedule:
        if action.action != "idle":
            time_str = action.timestamp.strftime("%H:%M") if action.timestamp else f"Q{action.quarter_idx}"
            soc_str = f"{action.soc_before:.2f} → {action.soc_after:.2f}"
            lines.append(
                f"{time_str:<12} {action.action.upper():<10} {action.price_eur:>14.2f} {soc_str:>12}"
            )

    lines.append("-" * 70)
    lines.append(f"Avg buy price:   {result.avg_buy_price:>8.2f} EUR/MWh")
    lines.append(f"Avg sell price:  {result.avg_sell_price:>8.2f} EUR/MWh")
    lines.append(f"Net revenue:     {result.revenue_eur:>8.2f} EUR/MWh")
    lines.append(f"Cycles:          {result.charges_used // 4} complete")

    return "\n".join(lines)
