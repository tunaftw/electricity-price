"""Capture price calculation for solar production."""

from __future__ import annotations

import csv
from datetime import datetime, date
from pathlib import Path
from typing import Iterator

from .config import QUARTERLY_DIR, RAW_DIR, ZONES
from .solar_profile import get_quarterly_solar_weight


def read_price_data(
    zone: str,
    start_date: date | None = None,
    end_date: date | None = None,
    use_quarterly: bool = True,
) -> Iterator[dict]:
    """
    Read price data for a zone, optionally filtered by date range.

    Args:
        zone: Electricity zone (SE1-SE4)
        start_date: Start date filter (inclusive)
        end_date: End date filter (inclusive)
        use_quarterly: Use quarterly (15-min) data if available

    Yields:
        Price records as dicts with time_start, SEK_per_kWh, etc.
    """
    base_dir = QUARTERLY_DIR if use_quarterly else RAW_DIR
    zone_dir = base_dir / zone

    if not zone_dir.exists():
        return

    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["time_start"])
                row_date = ts.date()

                if start_date and row_date < start_date:
                    continue
                if end_date and row_date > end_date:
                    continue

                row["_timestamp"] = ts
                row["_date"] = row_date
                yield row


def calculate_capture_price(
    zone: str,
    start_date: date | None = None,
    end_date: date | None = None,
    solar_profile: str = "sweden",
) -> dict:
    """
    Calculate capture price for solar production.

    Capture price = Σ(price × solar_weight) / Σ(solar_weight)

    Args:
        zone: Electricity zone
        start_date: Start of period
        end_date: End of period
        solar_profile: Solar profile to use

    Returns:
        Dict with capture_price, average_price, capture_ratio, etc.
    """
    total_weighted_price = 0.0
    total_solar_weight = 0.0
    total_price = 0.0
    record_count = 0

    for row in read_price_data(zone, start_date, end_date):
        ts = row["_timestamp"]
        price = float(row["SEK_per_kWh"])
        solar_weight = get_quarterly_solar_weight(ts, solar_profile)

        total_weighted_price += price * solar_weight
        total_solar_weight += solar_weight
        total_price += price
        record_count += 1

    if record_count == 0:
        return {
            "zone": zone,
            "start_date": start_date,
            "end_date": end_date,
            "capture_price": None,
            "average_price": None,
            "capture_ratio": None,
            "record_count": 0,
        }

    average_price = total_price / record_count
    capture_price = total_weighted_price / total_solar_weight if total_solar_weight > 0 else 0

    return {
        "zone": zone,
        "start_date": start_date,
        "end_date": end_date,
        "capture_price": capture_price,
        "average_price": average_price,
        "capture_ratio": capture_price / average_price if average_price > 0 else None,
        "record_count": record_count,
    }


def calculate_capture_by_period(
    zone: str,
    start_date: date | None = None,
    end_date: date | None = None,
    period: str = "month",  # "day", "week", "month", "year"
    solar_profile: str = "sweden",
) -> list[dict]:
    """
    Calculate capture price aggregated by period.

    Args:
        zone: Electricity zone
        start_date: Start of analysis period
        end_date: End of analysis period
        period: Aggregation period ("day", "week", "month", "year")
        solar_profile: Solar profile to use

    Returns:
        List of dicts with capture stats per period
    """
    # Group data by period
    period_data: dict[str, dict] = {}

    for row in read_price_data(zone, start_date, end_date):
        ts = row["_timestamp"]
        price = float(row["SEK_per_kWh"])
        solar_weight = get_quarterly_solar_weight(ts, solar_profile)

        # Determine period key
        if period == "day":
            key = ts.strftime("%Y-%m-%d")
        elif period == "week":
            key = ts.strftime("%Y-W%W")
        elif period == "month":
            key = ts.strftime("%Y-%m")
        elif period == "year":
            key = ts.strftime("%Y")
        else:
            raise ValueError(f"Unknown period: {period}")

        if key not in period_data:
            period_data[key] = {
                "period": key,
                "weighted_price": 0.0,
                "solar_weight": 0.0,
                "total_price": 0.0,
                "count": 0,
            }

        period_data[key]["weighted_price"] += price * solar_weight
        period_data[key]["solar_weight"] += solar_weight
        period_data[key]["total_price"] += price
        period_data[key]["count"] += 1

    # Calculate final metrics
    results = []
    for key in sorted(period_data.keys()):
        p = period_data[key]
        avg_price = p["total_price"] / p["count"] if p["count"] > 0 else 0
        cap_price = p["weighted_price"] / p["solar_weight"] if p["solar_weight"] > 0 else 0

        results.append({
            "period": key,
            "capture_price_sek": round(cap_price, 4),
            "average_price_sek": round(avg_price, 4),
            "capture_ratio": round(cap_price / avg_price, 3) if avg_price > 0 else None,
            "records": p["count"],
        })

    return results
