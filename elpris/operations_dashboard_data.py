"""Operations dashboard data calculations.

Computes metrics for the Operations section of dashboard v2:
- Specific Yield per park (kWh/kWp)
- Negative price exposure
- Tracker gain (Hova vs fixed-tilt)
- Meter loss analysis
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import (
    PARK_CAPACITY_KWP,
    PARK_EXPORT_LIMIT,
    PARK_ZONES,
    PARKS_PROFILE_DIR,
    QUARTERLY_DIR,
)

SWEDEN_TZ = ZoneInfo("Europe/Stockholm")
UTC_TZ = ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_park_15min(park_key: str) -> list[dict]:
    """Load 15-min park data from extended CSV.

    Returns list of {timestamp_utc: datetime, power_mw: float,
    active_power_mw: float|None, effective_power_mw: float,
    irradiance_poa: float|None, availability: float|None}.

    `power_mw` is the grid meter reading (ActivePowerMeter).
    `active_power_mw` is the inverter output (ActivePower).
    `effective_power_mw` is the best available energy reading:
        meter if available, else inverter. Use this for energy aggregation
        when meter coverage is incomplete (e.g. small parks like Stenstorp).

    Stuck-value detection: When the park is down, ActivePower sometimes
    reports a constant stale value (e.g. Stenstorp showed 0.1792 MW for
    10 straight days during downtime). Days where active_power_mw has
    the SAME value across ALL intervals and power_mw is entirely missing
    are detected and effective_power_mw is forced to 0 for those days.
    """
    zone = PARK_ZONES.get(park_key)
    if not zone:
        return []
    csv_path = PARKS_PROFILE_DIR / f"{park_key}_{zone}.csv"
    if not csv_path.exists():
        return []

    # Max plausible power: DC capacity in MW (generous upper bound)
    max_mw = PARK_CAPACITY_KWP.get(park_key, 50000) / 1000

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row["timestamp"])
            ts_utc = ts.astimezone(UTC_TZ)
            power = float(row.get("power_mw") or 0)
            if power > max_mw:
                continue  # Sensor error

            active_power = None
            if "active_power_mw" in row and row["active_power_mw"]:
                ap_val = float(row["active_power_mw"])
                if ap_val <= max_mw:  # Sanity check
                    active_power = ap_val

            # Effective power: meter (preferred) → inverter → 0
            effective = power if power > 0 else (active_power or 0)

            rec = {
                "timestamp_utc": ts_utc,
                "date": ts_utc.strftime("%Y-%m-%d"),
                "year": ts_utc.year,
                "month": ts_utc.month,
                "power_mw": power,
                "effective_power_mw": effective,
            }
            if active_power is not None:
                rec["active_power_mw"] = active_power
            if "irradiance_poa" in row and row["irradiance_poa"]:
                rec["irradiance_poa"] = float(row["irradiance_poa"])
            if "availability" in row and row["availability"]:
                rec["availability"] = float(row["availability"])
            records.append(rec)

    # Post-process: detect and neutralize stuck-value days (Stenstorp issue)
    from collections import defaultdict
    by_date: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_date[rec["date"]].append(rec)

    for date_key, day_records in by_date.items():
        # Check if meter is entirely missing this day
        meter_missing = all(r["power_mw"] == 0 for r in day_records)
        if not meter_missing:
            continue

        # Collect unique active_power_mw values
        ap_values = set(
            r.get("active_power_mw") for r in day_records
            if r.get("active_power_mw") is not None
        )

        # If there's exactly one unique value and ActivePower is non-zero,
        # the sensor is stuck on a stale value — treat as park off.
        if len(ap_values) == 1 and next(iter(ap_values)) > 0:
            for rec in day_records:
                rec["effective_power_mw"] = 0.0
                rec["_stuck_value"] = True  # for debugging/diagnostics

    return records


def load_spot_prices_15min(zone: str) -> dict[str, list[dict]]:
    """Load quarterly spot prices as 15-min data.

    Returns dict keyed by ISO date -> list of {timestamp_utc, eur_mwh}.
    """
    zone_dir = QUARTERLY_DIR / zone
    if not zone_dir.exists():
        return {}

    by_date: dict[str, list[dict]] = defaultdict(list)
    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["time_start"])
                ts_utc = ts.astimezone(UTC_TZ)
                date_key = ts_utc.strftime("%Y-%m-%d")
                eur_mwh = float(row["EUR_per_kWh"]) * 1000
                by_date[date_key].append({
                    "timestamp_utc": ts_utc,
                    "eur_mwh": eur_mwh,
                })
    return dict(by_date)


# ---------------------------------------------------------------------------
# Feature 2: Specific Yield
# ---------------------------------------------------------------------------

def calculate_specific_yield() -> dict[str, list[dict]]:
    """Calculate monthly specific yield (kWh/kWp) per park.

    Returns {park_key: [{year, month, yield_kwh_kwp, energy_mwh}, ...]}.
    """
    result: dict[str, list[dict]] = {}

    for park_key, capacity_kwp in PARK_CAPACITY_KWP.items():
        records = load_park_15min(park_key)
        if not records:
            continue

        # Aggregate energy per month
        monthly: dict[tuple[int, int], float] = defaultdict(float)
        for rec in records:
            # energy_mwh = power_mw * 0.25 (15-min interval)
            monthly[(rec["year"], rec["month"])] += rec["power_mw"] * 0.25

        park_data = []
        for (year, month), energy_mwh in sorted(monthly.items()):
            # specific yield: MWh / (kWp / 1000) = MWh / MWp = kWh/kWp
            sy = energy_mwh / (capacity_kwp / 1000)
            park_data.append({
                "year": year,
                "month": month,
                "yield_kwh_kwp": round(sy, 2),
                "energy_mwh": round(energy_mwh, 2),
            })

        result[park_key] = park_data

    return result


# ---------------------------------------------------------------------------
# Feature 10: Negative price exposure
# ---------------------------------------------------------------------------

def calculate_negative_price_exposure() -> dict[str, list[dict]]:
    """Calculate monthly negative price exposure per park.

    Returns {park_key: [{year, month, neg_hours, neg_volume_mwh, neg_revenue_eur}, ...]}.
    """
    result: dict[str, list[dict]] = {}

    for park_key in PARK_CAPACITY_KWP:
        zone = PARK_ZONES[park_key]
        park_data = load_park_15min(park_key)
        spot_data = load_spot_prices_15min(zone)

        if not park_data or not spot_data:
            continue

        # Index park data by timestamp for fast lookup
        park_by_ts: dict[str, float] = {}
        for rec in park_data:
            ts_key = rec["timestamp_utc"].strftime("%Y-%m-%dT%H:%M")
            park_by_ts[ts_key] = rec["power_mw"]

        monthly: dict[tuple[int, int], dict] = defaultdict(
            lambda: {"neg_hours": 0, "neg_volume_mwh": 0, "neg_revenue_eur": 0}
        )

        for date_key, prices in spot_data.items():
            for price_rec in prices:
                ts_key = price_rec["timestamp_utc"].strftime("%Y-%m-%dT%H:%M")
                power = park_by_ts.get(ts_key, 0)
                price = price_rec["eur_mwh"]

                if price < 0 and power > 0:
                    ym = (price_rec["timestamp_utc"].year, price_rec["timestamp_utc"].month)
                    monthly[ym]["neg_hours"] += 0.25
                    monthly[ym]["neg_volume_mwh"] += power * 0.25
                    monthly[ym]["neg_revenue_eur"] += power * 0.25 * price

        park_result = []
        for (year, month), data in sorted(monthly.items()):
            park_result.append({
                "year": year,
                "month": month,
                "neg_hours": round(data["neg_hours"], 2),
                "neg_volume_mwh": round(data["neg_volume_mwh"], 2),
                "neg_revenue_eur": round(data["neg_revenue_eur"], 2),
            })

        result[park_key] = park_result

    return result


# ---------------------------------------------------------------------------
# Feature 11: Tracker gain (Hova vs fixed-tilt SE3 parks)
# ---------------------------------------------------------------------------

def calculate_tracker_gain() -> list[dict]:
    """Calculate Hova tracker gain vs Bjorke + Skakelbacken (fixed SE3).

    Returns [{year, month, sy_hova, sy_fixed_avg, gain_pct}, ...].
    """
    sy_data = calculate_specific_yield()

    hova = {(r["year"], r["month"]): r["yield_kwh_kwp"] for r in sy_data.get("hova", [])}
    bjorke = {(r["year"], r["month"]): r["yield_kwh_kwp"] for r in sy_data.get("bjorke", [])}
    skakelbacken = {(r["year"], r["month"]): r["yield_kwh_kwp"] for r in sy_data.get("skakelbacken", [])}

    result = []
    for ym in sorted(hova):
        sy_h = hova[ym]
        # Need at least one fixed-tilt park for comparison
        fixed_vals = [v for v in [bjorke.get(ym), skakelbacken.get(ym)] if v is not None and v > 0]
        if not fixed_vals or sy_h <= 0:
            continue
        fixed_avg = sum(fixed_vals) / len(fixed_vals)
        # Skip months with low production — percentage comparison not meaningful
        if fixed_avg < 5.0 or sy_h < 5.0:
            continue

        gain = (sy_h / fixed_avg - 1) * 100

        result.append({
            "year": ym[0],
            "month": ym[1],
            "sy_hova": round(sy_h, 2),
            "sy_fixed_avg": round(fixed_avg, 2),
            "gain_pct": round(gain, 1),
        })

    return result


# ---------------------------------------------------------------------------
# Feature 14: Meter loss analysis
# ---------------------------------------------------------------------------

def calculate_meter_loss() -> dict[str, list[dict]]:
    """Calculate daily meter loss (inverter sum vs grid meter) per park.

    Returns {park_key: [{year, month, date, loss_pct}, ...]}.
    Only includes days with sufficient production (> 0.1 MW avg).
    """
    result: dict[str, list[dict]] = {}

    for park_key in PARK_CAPACITY_KWP:
        records = load_park_15min(park_key)
        if not records:
            continue

        # Aggregate daily: sum of (active_power - power_meter) / sum of active_power
        daily_inv: dict[str, float] = defaultdict(float)
        daily_meter: dict[str, float] = defaultdict(float)
        daily_count: dict[str, int] = defaultdict(int)

        for rec in records:
            ap = rec.get("active_power_mw")
            pm = rec.get("power_mw", 0)
            if ap is not None and ap > 0.1 and pm > 0:
                daily_inv[rec["date"]] += ap
                daily_meter[rec["date"]] += pm
                daily_count[rec["date"]] += 1

        park_data = []
        for date_key in sorted(daily_inv):
            if daily_count[date_key] < 4:  # Need at least 1 hour of data
                continue
            inv_total = daily_inv[date_key]
            meter_total = daily_meter[date_key]
            if inv_total > 0:
                loss_pct = (1 - meter_total / inv_total) * 100
                d = date.fromisoformat(date_key)
                park_data.append({
                    "year": d.year,
                    "month": d.month,
                    "date": date_key,
                    "loss_pct": round(loss_pct, 2),
                })

        if park_data:
            result[park_key] = park_data

    return result


# ---------------------------------------------------------------------------
# Main calculator
# ---------------------------------------------------------------------------

def calculate_operations_data() -> dict:
    """Calculate all operations dashboard data.

    Returns dict with all feature data for JSON embedding.
    """
    print("Beraknar Operations-data...")

    print("  Specific Yield...")
    specific_yield = calculate_specific_yield()

    print("  Negativ pris-exponering...")
    negative_price = calculate_negative_price_exposure()

    print("  Tracker-gain...")
    tracker_gain = calculate_tracker_gain()

    print("  Meterforlust...")
    meter_loss = calculate_meter_loss()

    return {
        "parks": list(PARK_CAPACITY_KWP.keys()),
        "park_zones": PARK_ZONES,
        "park_capacity_kwp": PARK_CAPACITY_KWP,
        "park_export_limit": PARK_EXPORT_LIMIT,
        "specific_yield": specific_yield,
        "negative_price": negative_price,
        "tracker_gain": tracker_gain,
        "meter_loss": meter_loss,
    }
