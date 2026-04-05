"""Ancillary services (stödtjänster) data module for dashboard v2.

Computes BESS revenue from frequency regulation markets:
- FCR-N / FCR-D up / FCR-D down (Primary reserves, SVK Mimer)
- aFRR up / aFRR down (Automatic FRR, per zone)
- mFRR-CM up / mFRR-CM down (Manual FRR capacity market, per zone)

Assumes 100% availability (theoretical max revenue per MW) — a BESS
bidding into the market every hour at the clearing price. Actual
revenues depend on bid acceptance rates and dispatch schedules.

All prices from SvK Mimer are EUR/MW per hour. Annual revenue at 1 MW
continuous provision = sum(hourly_price) over the year.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from .config import MIMER_DATA_DIR, ZONES

# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

# Zone mapping: Mimer uses SN1..SN4, dashboard uses SE1..SE4
MIMER_ZONE_MAP = {"SN1": "SE1", "SN2": "SE2", "SN3": "SE3", "SN4": "SE4"}

ANCILLARY_PROFILES: dict[str, str] = {
    "anc_fcr_n":       "FCR-N",
    "anc_fcr_d_up":    "FCR-D upp",
    "anc_fcr_d_down":  "FCR-D ned",
    "anc_afrr_up":     "aFRR upp",
    "anc_afrr_down":   "aFRR ned",
    "anc_mfrr_cm_up":  "mFRR-CM upp",
    "anc_mfrr_cm_down": "mFRR-CM ned",
}

# Violet/purple palette — distinct from amber (arbitrage) and teal (sol+BESS)
ANCILLARY_COLORS: dict[str, str] = {
    "anc_fcr_n":       "#a78bfa",  # violet-400
    "anc_fcr_d_up":    "#8b5cf6",  # violet-500
    "anc_fcr_d_down":  "#7c3aed",  # violet-600
    "anc_afrr_up":     "#c084fc",  # purple-400
    "anc_afrr_down":   "#a855f7",  # purple-500
    "anc_mfrr_cm_up":  "#e879f9",  # fuchsia-400
    "anc_mfrr_cm_down": "#d946ef",  # fuchsia-500
}

ANCILLARY_PROFILE_META: dict[str, dict[str, str]] = {
    key: {"type": "revenue", "unit": "EUR/MW"}
    for key in ANCILLARY_PROFILES
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_fcr_data() -> dict[str, dict[str, float]]:
    """Load FCR data (aggregate, not zone-specific).

    Returns dict keyed by column name ("fcr_n", "fcr_d_up", "fcr_d_down"),
    mapping to {iso_timestamp: price_eur_mw}.
    """
    fcr_dir = MIMER_DATA_DIR / "fcr"
    if not fcr_dir.exists():
        return {}

    prices: dict[str, dict[str, float]] = {
        "fcr_n": {},
        "fcr_d_up": {},
        "fcr_d_down": {},
    }

    for csv_file in sorted(fcr_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = row["time_start"]
                try:
                    prices["fcr_n"][ts] = float(row.get("fcr_n_price_eur_mw", 0) or 0)
                    prices["fcr_d_up"][ts] = float(row.get("fcr_d_up_price_eur_mw", 0) or 0)
                    prices["fcr_d_down"][ts] = float(row.get("fcr_d_down_price_eur_mw", 0) or 0)
                except (ValueError, TypeError):
                    continue

    return prices


def load_afrr_data() -> dict[str, dict[str, dict[str, float]]]:
    """Load aFRR data per zone.

    Returns {zone: {field: {iso_timestamp: price_eur_mw}}}
    where field is "up" or "down".
    """
    afrr_dir = MIMER_DATA_DIR / "afrr"
    if not afrr_dir.exists():
        return {}

    result: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {"up": {}, "down": {}}
    )

    for csv_file in sorted(afrr_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mimer_zone = row.get("zone", "").strip()
                zone = MIMER_ZONE_MAP.get(mimer_zone)
                if not zone:
                    continue
                ts = row["time_start"]
                try:
                    result[zone]["up"][ts] = float(row.get("afrr_up_price_eur_mw", 0) or 0)
                    result[zone]["down"][ts] = float(row.get("afrr_down_price_eur_mw", 0) or 0)
                except (ValueError, TypeError):
                    continue

    return {z: dict(v) for z, v in result.items()}


def load_mfrr_cm_data() -> dict[str, dict[str, dict[str, float]]]:
    """Load mFRR-CM data per zone.

    Returns {zone: {field: {iso_timestamp: price_eur_mw}}}
    where field is "up" or "down".
    """
    mfrr_cm_dir = MIMER_DATA_DIR / "mfrr_cm"
    if not mfrr_cm_dir.exists():
        return {}

    result: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {"up": {}, "down": {}}
    )

    for csv_file in sorted(mfrr_cm_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mimer_zone = row.get("zone", "").strip()
                zone = MIMER_ZONE_MAP.get(mimer_zone)
                if not zone:
                    continue
                ts = row["time_start"]
                try:
                    result[zone]["up"][ts] = float(row.get("mfrr_cm_up_price_eur_mw", 0) or 0)
                    result[zone]["down"][ts] = float(row.get("mfrr_cm_down_price_eur_mw", 0) or 0)
                except (ValueError, TypeError):
                    continue

    return {z: dict(v) for z, v in result.items()}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _aggregate_hourly_to_periods(
    hourly: dict[str, float],
) -> dict[str, list]:
    """Aggregate hourly EUR/MW prices to daily/monthly/yearly revenue.

    Revenue = sum of hourly prices (assuming 1 MW continuously available).
    Unit: EUR/MW per period.

    Returns {"yearly": [...], "monthly": [...], "daily": [...]}
    """
    daily_acc: dict[str, dict] = defaultdict(
        lambda: {"sum": 0.0, "count": 0, "year": 0, "month": 0}
    )

    for ts_str, price in hourly.items():
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            continue
        date_key = ts.strftime("%Y-%m-%d")
        acc = daily_acc[date_key]
        acc["sum"] += price
        acc["count"] += 1
        acc["year"] = ts.year
        acc["month"] = ts.month

    # Daily list
    daily_list: list[dict] = []
    for date_key in sorted(daily_acc):
        d = daily_acc[date_key]
        daily_list.append({
            "date": date_key,
            "year": d["year"],
            "month": d["month"],
            "capture": round(d["sum"], 2),  # daily revenue EUR/MW
            "baseload": None,
            "ratio": None,
        })

    # Monthly — sum of daily
    monthly_acc: dict[tuple[int, int], float] = defaultdict(float)
    for d in daily_acc.values():
        monthly_acc[(d["year"], d["month"])] += d["sum"]
    monthly_list: list[dict] = [
        {
            "year": y,
            "month": m,
            "capture": round(v, 2),
            "baseload": None,
            "ratio": None,
        }
        for (y, m), v in sorted(monthly_acc.items())
    ]

    # Yearly — sum of daily
    yearly_acc: dict[int, float] = defaultdict(float)
    for d in daily_acc.values():
        yearly_acc[d["year"]] += d["sum"]
    yearly_list: list[dict] = [
        {
            "year": y,
            "capture": round(v, 2),
            "baseload": None,
            "ratio": None,
        }
        for y, v in sorted(yearly_acc.items())
    ]

    return {
        "yearly": yearly_list,
        "monthly": monthly_list,
        "daily": daily_list,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def calculate_ancillary_data(zones: list[str]) -> dict:
    """Calculate ancillary services revenue data for all zones.

    Args:
        zones: List of zones (e.g., ["SE1", "SE2", "SE3", "SE4"])

    Returns dict with:
        profiles: {key: label}
        colors: {key: hex}
        profile_meta: {key: {type, unit}}
        data: {zone: {profile_key: {yearly, monthly, daily}}}
    """
    print("Beräknar stödtjänster...")

    # Load data once (FCR is the same across all zones)
    fcr = load_fcr_data()
    afrr = load_afrr_data()
    mfrr_cm = load_mfrr_cm_data()

    data: dict[str, dict] = {}

    for zone in zones:
        print(f"  Stödtjänster {zone}...")
        zone_data: dict[str, dict] = {}

        # FCR — same data for all zones (national market)
        if "fcr_n" in fcr and fcr["fcr_n"]:
            zone_data["anc_fcr_n"] = _aggregate_hourly_to_periods(fcr["fcr_n"])
        if "fcr_d_up" in fcr and fcr["fcr_d_up"]:
            zone_data["anc_fcr_d_up"] = _aggregate_hourly_to_periods(fcr["fcr_d_up"])
        if "fcr_d_down" in fcr and fcr["fcr_d_down"]:
            zone_data["anc_fcr_d_down"] = _aggregate_hourly_to_periods(fcr["fcr_d_down"])

        # aFRR — per zone
        zone_afrr = afrr.get(zone, {})
        if zone_afrr.get("up"):
            zone_data["anc_afrr_up"] = _aggregate_hourly_to_periods(zone_afrr["up"])
        if zone_afrr.get("down"):
            zone_data["anc_afrr_down"] = _aggregate_hourly_to_periods(zone_afrr["down"])

        # mFRR-CM — per zone
        zone_mfrr = mfrr_cm.get(zone, {})
        if zone_mfrr.get("up"):
            zone_data["anc_mfrr_cm_up"] = _aggregate_hourly_to_periods(zone_mfrr["up"])
        if zone_mfrr.get("down"):
            zone_data["anc_mfrr_cm_down"] = _aggregate_hourly_to_periods(zone_mfrr["down"])

        if zone_data:
            data[zone] = zone_data

    return {
        "profiles": dict(ANCILLARY_PROFILES),
        "colors": dict(ANCILLARY_COLORS),
        "profile_meta": dict(ANCILLARY_PROFILE_META),
        "data": data,
    }
