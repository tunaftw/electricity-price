"""Operations dashboard data calculations.

Computes metrics for the Operations section of dashboard v2:
- Specific Yield per park (kWh/kWp)
- Negative price exposure
- Tracker gain (Hova vs fixed-tilt)
- Meter loss analysis
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from .bazefield import parse_bazefield_ts
from .config import (
    PARK_CAPACITY_KWP,
    PARK_EXPORT_LIMIT,
    PARK_ZONES,
    PARKS_PROFILE_DIR,
    QUARTERLY_DIR,
    SWEDEN_TZ,
    UTC_TZ,
    local_year_month,
)
from .solar_geometry import solar_elevation_deg
from .temperature import PARK_COORDS


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_park_15min(park_key: str) -> list[dict]:
    """Load 15-min park data from extended CSV.

    Returns list of {timestamp_utc: datetime, power_mw: float,
    active_power_mw: float|None, effective_power_mw: float,
    irradiance_poa: float|None, availability: float|None}.

    `power_mw` is the grid meter reading (ActivePowerMeter), 0 when missing.
    `active_power_mw` is the inverter output (ActivePower).
    `effective_power_mw` is the energy reading to aggregate. It is decided
    per quarter by strict rules (see `_classify_energy_source`) and the
    choice is recorded in `energy_source`:

        "night"    — sun below the horizon: 0, whatever the signals say
        "meter"    — valid grid meter reading (negative clipped to 0)
        "inverter" — meter missing, inverter reading live and plausible
        "missing"  — neither signal can be trusted: 0 and NOT a real zero

    Only "meter" and "inverter" quarters are observed production; callers
    that compare against budget must look at `energy_source` (or use
    `daylight_coverage`) so that "missing" is not mistaken for downtime.

    Why so strict: the earlier meter→inverter fallback (`power > 0 else
    inverter`) produced phantom energy — inverters that freeze on their
    last value keep "producing" through the night (Fjällskär Aug 2026:
    413 MWh between 23 and 03) and dead meters were silently replaced by
    frozen inverter values (Fjällskär Sep 2026: 7.69 MW in every quarter).
    """
    zone = PARK_ZONES.get(park_key)
    if not zone:
        return []
    csv_path = PARKS_PROFILE_DIR / f"{park_key}_{zone}.csv"
    if not csv_path.exists():
        return []

    # Max plausible power: DC capacity in MW (generous upper bound)
    max_mw = PARK_CAPACITY_KWP.get(park_key, 50000) / 1000
    coords = PARK_COORDS.get(park_key)

    # Parsing + solar geometry is the expensive part and some dashboards call
    # this hundreds of times per build. Cache per file version and hand out
    # fresh dicts so callers may still mutate their records.
    stat = csv_path.stat()
    key = (str(csv_path), stat.st_mtime_ns, stat.st_size, max_mw, coords)
    cached = _PARK_CACHE.get(key)
    if cached is None:
        cached = _parse_park_csv(csv_path, max_mw, coords)
        # One entry per park file: drop older versions of the same file.
        for old in [k for k in _PARK_CACHE if k[0] == key[0]]:
            del _PARK_CACHE[old]
        _PARK_CACHE[key] = cached
    return [dict(r) for r in cached]


_PARK_CACHE: dict = {}


def _parse_park_csv(csv_path: Path, max_mw: float, coords) -> list[dict]:
    """Parse one park CSV and apply the strict energy rules (uncached)."""
    by_ts: dict[datetime, dict] = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = parse_bazefield_ts(row["timestamp"])
            ts_utc = ts.astimezone(UTC_TZ)
            meter = _plausible_mw(row.get("power_mw"), max_mw)
            inverter = _plausible_mw(row.get("active_power_mw"), max_mw)

            rec = {
                "timestamp_utc": ts_utc,
                "date": ts_utc.strftime("%Y-%m-%d"),
                "year": ts_utc.year,
                "month": ts_utc.month,
                "power_mw": meter if meter is not None else 0.0,
                "_meter": meter,
                "_inverter": inverter,
            }
            if inverter is not None:
                rec["active_power_mw"] = inverter
            if "irradiance_poa" in row and row["irradiance_poa"]:
                poa = _finite(row["irradiance_poa"])
                if poa is not None:
                    rec["irradiance_poa"] = poa
            if "availability" in row and row["availability"]:
                avail = _finite(row["availability"])
                if avail is not None:
                    rec["availability"] = avail
            # Files are appended by incremental syncs and are not always in
            # time order; the last row for a timestamp wins.
            by_ts[ts_utc] = rec

    records = [by_ts[ts] for ts in sorted(by_ts)]
    elevations = [
        solar_elevation_deg(r["timestamp_utc"] + _HALF_QUARTER, *coords) if coords is not None else None
        for r in records
    ]
    frozen_meter = _frozen_mask([r["_meter"] for r in records], elevations)
    frozen_inverter = _frozen_mask([r["_inverter"] for r in records], elevations)

    for i, rec in enumerate(records):
        elevation = elevations[i]
        rec["sun_elevation_deg"] = elevation
        meter = None if frozen_meter[i] else rec.pop("_meter")
        inverter = None if frozen_inverter[i] else rec.pop("_inverter")
        rec.pop("_meter", None)
        rec.pop("_inverter", None)
        if frozen_meter[i]:
            rec["power_mw"] = 0.0
        if frozen_inverter[i] and (elevation is None or elevation > 0):
            # Read by rework_portfolio / meter-loss diagnostics. Only daylight
            # quarters: an inverter parked on its last value overnight is
            # handled by the night rule and is not a daytime outage.
            rec["_stuck_value"] = True
        source, value = _classify_energy_source(meter, inverter, elevation)
        rec["energy_source"] = source
        rec["effective_power_mw"] = value

    return records


# Strict energy rules — see load_park_15min.
NIGHT_ELEVATION_DEG = -3.0     # below this a PV park cannot export
DAYLIGHT_ELEVATION_DEG = 10.0  # above this an inverter at exactly 0 is suspect
FROZEN_RUN_QUARTERS = 8        # identical reading ≥ 2 h in a row …
FROZEN_DAYTIME_RUN_QUARTERS = 24  # … is frozen if it reaches into night, or lasts ≥ 6 h
FROZEN_MIN_MW = 0.01           # a run of zeros is not "frozen" (night, downtime)
NEGATIVE_METER_SHARE = 0.02    # meter below −2 % of capacity is not a real reading
_HALF_QUARTER = timedelta(minutes=7, seconds=30)  # elevation at mid-interval


def _finite(raw) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def _plausible_mw(raw, max_mw: float) -> float | None:
    """Reading in MW, or None when missing or physically implausible.

    Above DC capacity is a sensor error. Far below zero is too: a solar park's
    own consumption is a few tens of kW, so e.g. −8 MW on an 18 MWp park is a
    sign flip or garbage (Hörby 2026-07-22..24), not "zero production".
    """
    value = _finite(raw) if raw not in (None, "") else None
    if value is None or value > max_mw or value < -NEGATIVE_METER_SHARE * max_mw:
        return None
    return value


def _frozen_mask(values: list[float | None],
                 elevations: list[float | None] | None = None) -> list[bool]:
    """True where a non-zero reading is frozen.

    A run of ≥ FROZEN_RUN_QUARTERS identical readings counts as frozen when it
    reaches into the night (a live PV signal cannot hold a non-zero value in
    darkness) or lasts ≥ FROZEN_DAYTIME_RUN_QUARTERS. A shorter plateau in full
    daylight is usually a park held at its export limit (Tången at 4.528 MW
    for 2–4 h on clear days) and is real production.
    """
    mask = [False] * len(values)
    start = 0
    n = len(values)
    while start < n:
        value = values[start]
        end = start + 1
        if value is not None:
            key = round(value, 4)
            while end < n and values[end] is not None and round(values[end], 4) == key:
                end += 1
            length = end - start
            if length >= FROZEN_RUN_QUARTERS and value > FROZEN_MIN_MW:
                touches_night = elevations is None or any(
                    elevations[j] is not None and elevations[j] < NIGHT_ELEVATION_DEG
                    for j in range(start, end)
                )
                if touches_night or length >= FROZEN_DAYTIME_RUN_QUARTERS:
                    for j in range(start, end):
                        mask[j] = True
        start = end
    return mask


def _classify_energy_source(
    meter: float | None, inverter: float | None, sun_elevation: float | None,
) -> tuple[str, float]:
    """Choose the energy reading for one quarter: (energy_source, MW)."""
    if sun_elevation is not None and sun_elevation < NIGHT_ELEVATION_DEG:
        return "night", 0.0
    if meter is not None:
        return "meter", max(meter, 0.0)
    if inverter is not None:
        # Without a meter, an inverter at exactly 0 in full daylight cannot be
        # told apart from a dead signal — call it unknown, not downtime.
        if inverter <= 0 and sun_elevation is not None and sun_elevation > DAYLIGHT_ELEVATION_DEG:
            return "missing", 0.0
        return "inverter", max(inverter, 0.0)
    return "missing", 0.0


def daylight_coverage(
    park_key: str,
    records: list[dict],
    start_utc: datetime,
    end_utc: datetime,
    min_elevation_deg: float = 5.0,
) -> float | None:
    """Share of daylight in [start_utc, end_utc) with observed production.

    Every expected quarter with the sun above ``min_elevation_deg`` is
    weighted by sin(elevation) — a rough proxy for how much energy that
    quarter should carry — so a missing noon counts more than a missing
    dawn. A quarter is covered when its record has energy_source "meter"
    or "inverter". Returns 0–1, or None when the park has no coordinates.
    """
    coords = PARK_COORDS.get(park_key)
    if coords is None:
        return None
    observed = {
        r["timestamp_utc"]
        for r in records
        if start_utc <= r["timestamp_utc"] < end_utc
        and r.get("energy_source") in ("meter", "inverter")
    }
    total = covered = 0.0
    ts = start_utc
    step = timedelta(minutes=15)
    while ts < end_utc:
        elevation = solar_elevation_deg(ts + _HALF_QUARTER, *coords)
        if elevation > min_elevation_deg:
            weight = math.sin(math.radians(elevation))
            total += weight
            if ts in observed:
                covered += weight
        ts += step
    if total == 0:
        return None
    return covered / total


def load_spot_prices_15min(zone: str) -> dict[str, list[dict]]:
    """Load quarterly spot prices as 15-min data.

    Returns dict keyed by ISO date -> list of
    {timestamp_utc, eur_mwh, sek_per_eur}. ``sek_per_eur`` is the EXR
    column from the source CSV (SEK per 1 EUR), used to convert
    SEK-denominated PPA prices into EUR for revenue blending. Falls
    back to None when EXR is missing/zero in the row.
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
                exr_raw = row.get("EXR")
                try:
                    sek_per_eur = float(exr_raw) if exr_raw else None
                    if sek_per_eur is not None and sek_per_eur <= 0:
                        sek_per_eur = None
                except (TypeError, ValueError):
                    sek_per_eur = None
                by_date[date_key].append({
                    "timestamp_utc": ts_utc,
                    "eur_mwh": eur_mwh,
                    "sek_per_eur": sek_per_eur,
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

        # Aggregate energy per month using effective_power_mw (meter→inverter
        # fallback) so parks with broken meter coverage (e.g. Stenstorp) still
        # report yield based on inverter readings.
        monthly: dict[tuple[int, int], float] = defaultdict(float)
        for rec in records:
            ym = local_year_month(rec["timestamp_utc"])
            monthly[ym] += rec["effective_power_mw"] * 0.25

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

        # Index park data by timestamp for fast lookup. Use effective_power_mw
        # so meter-gap parks (Stenstorp) still get accurate negative-price
        # exposure from inverter readings.
        park_by_ts: dict[str, float] = {}
        for rec in park_data:
            ts_key = rec["timestamp_utc"].strftime("%Y-%m-%dT%H:%M")
            park_by_ts[ts_key] = rec["effective_power_mw"]

        monthly: dict[tuple[int, int], dict] = defaultdict(
            lambda: {"neg_hours": 0, "neg_volume_mwh": 0, "neg_revenue_eur": 0}
        )

        for date_key, prices in spot_data.items():
            for price_rec in prices:
                ts_key = price_rec["timestamp_utc"].strftime("%Y-%m-%dT%H:%M")
                power = park_by_ts.get(ts_key, 0)
                price = price_rec["eur_mwh"]

                if price < 0 and power > 0:
                    ym = local_year_month(price_rec["timestamp_utc"])
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
            if rec.get("_stuck_value"):
                continue  # frozen inverter value, not a real reading
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
