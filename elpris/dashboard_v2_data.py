"""Dashboard v2 data module.

Calculates capture prices for all power types:
- Baseload (arithmetic mean of spot prices)
- Solar (PVsyst profiles: syd, öst-väst, tracker + auto-discovered parks)
- Wind (ENTSO-E actual generation)
- Hydro (ENTSO-E actual generation)
- Nuclear (ENTSO-E actual generation)

Aggregates to day/month/year for drill-down navigation.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import QUARTERLY_DIR, ENTSOE_DATA_DIR, NASDAQ_DATA_DIR, ZONES, RESULTAT_DIR
from .bess_dashboard_data import calculate_bess_data, BESS_PROFILE_META

SWEDEN_TZ = ZoneInfo("Europe/Stockholm")
UTC_TZ = ZoneInfo("UTC")
ENTSOE_GEN_DIR = ENTSOE_DATA_DIR / "generation"
PROFILES_DIR = RESULTAT_DIR / "profiler" / "beraknade"
PARKS_DIR = RESULTAT_DIR / "profiler" / "parker"

# Standard PVsyst solar profiles
STANDARD_SOLAR_PROFILES = {
    "sol_syd": ("south_lundby", "Sol Syd"),
    "sol_ov": ("ew_boda", "Sol Öst-Väst"),
    "sol_tracker": ("tracker_sweden", "Sol Tracker"),
}

# ENTSO-E generation types for capture calculation
ENTSOE_CAPTURE_TYPES = {
    "wind": ("wind_onshore", "Vind"),
    "hydro": ("hydro_water_reservoir", "Vattenkraft"),
    "nuclear": ("nuclear", "Kärnkraft"),
}

# Colors per profile (used by frontend)
PROFILE_COLORS = {
    "baseload": "#ffffff",
    "sol_syd": "#ffd700",
    "sol_ov": "#ff8c00",
    "sol_tracker": "#ff6347",
    "wind": "#00d4aa",
    "hydro": "#4169e1",
    "nuclear": "#dc143c",
}

# Muted palette for park profiles
_PARK_COLORS = [
    "#a78bfa", "#67e8f9", "#86efac", "#fde68a", "#fca5a5",
    "#c4b5fd", "#99f6e4", "#bbf7d0", "#fef08a", "#fecaca",
]


def load_spot_prices(zone: str) -> dict[str, list[dict]]:
    """Load quarterly spot prices for a zone, averaged to hourly.

    Returns dict keyed by ISO date (YYYY-MM-DD) containing lists of
    {utc_hour: int, eur_mwh: float} records.
    """
    zone_dir = QUARTERLY_DIR / zone
    if not zone_dir.exists():
        return {}

    hourly_acc: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for csv_file in sorted(zone_dir.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["time_start"])
                ts_utc = ts.astimezone(UTC_TZ)
                date_key = ts_utc.strftime("%Y-%m-%d")
                hour = ts_utc.hour
                eur_mwh = float(row["EUR_per_kWh"]) * 1000
                hourly_acc[date_key][hour].append(eur_mwh)

    result: dict[str, list[dict]] = {}
    for date_key in sorted(hourly_acc):
        hours = hourly_acc[date_key]
        result[date_key] = [
            {"utc_hour": h, "eur_mwh": sum(hours[h]) / len(hours[h])}
            for h in sorted(hours)
        ]
    return result


def load_entsoe_generation(
    zone: str, gen_type: str
) -> dict[str, dict[int, float]]:
    """Load ENTSO-E actual generation data.

    Returns dict keyed by ISO date (YYYY-MM-DD) -> {utc_hour: generation_mw}.
    """
    zone_dir = ENTSOE_GEN_DIR / zone
    if not zone_dir.exists():
        return {}

    result: dict[str, dict[int, float]] = defaultdict(dict)

    for csv_file in sorted(zone_dir.glob(f"{gen_type}_*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row["time_start"].replace("Z", "+00:00")
                ts = datetime.fromisoformat(ts_str)
                date_key = ts.strftime("%Y-%m-%d")
                result[date_key][ts.hour] = float(row["generation_mw"])

    return dict(result)


def load_pvsyst_profile(name: str) -> dict[tuple[int, int, int], float]:
    """Load PVsyst profile: (month, day, hour) -> power_mw."""
    filepath = PROFILES_DIR / f"{name}.csv"
    if not filepath.exists():
        return {}

    profile: dict[tuple[int, int, int], float] = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row["month"]), int(row["day"]), int(row["hour"]))
            profile[key] = float(row["power_mw"])
    return profile


def load_pvsyst_profile_from_path(
    filepath: Path,
) -> dict[tuple[int, int, int], float]:
    """Load PVsyst profile from an arbitrary path."""
    profile: dict[tuple[int, int, int], float] = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row["month"]), int(row["day"]), int(row["hour"]))
            profile[key] = float(row["power_mw"])
    return profile


def discover_park_profiles() -> dict[str, tuple[str, str]]:
    """Auto-discover park profiles from Resultat/profiler/parker/.

    Naming convention: parkname_SE3.csv -> zone SE3
    Returns {key: (filename_stem, display_name)}.
    """
    if not PARKS_DIR.exists():
        return {}

    parks: dict[str, tuple[str, str]] = {}
    for f in sorted(PARKS_DIR.glob("*.csv")):
        stem = f.stem
        parts = stem.rsplit("_", 1)
        if len(parts) == 2 and parts[1] in ZONES:
            park_name = parts[0].replace("_", " ").title()
            zone = parts[1]
            parks[f"park_{stem}"] = (stem, f"{park_name} ({zone})")
    return parks


# ---------------------------------------------------------------------------
# Capture calculation engines
# ---------------------------------------------------------------------------

def _calculate_entsoe_capture(
    spot_prices: dict[str, list[dict]],
    generation: dict[str, dict[int, float]],
) -> dict[str, dict]:
    """Calculate capture prices using actual ENTSO-E generation data."""
    daily: dict[str, dict] = {}

    for date_key in sorted(spot_prices):
        if date_key not in generation:
            continue

        hours = spot_prices[date_key]
        gen = generation[date_key]
        d = date.fromisoformat(date_key)

        sum_weighted = 0.0
        sum_gen = 0.0
        sum_price = 0.0
        count = 0

        for h_rec in hours:
            h = h_rec["utc_hour"]
            price = h_rec["eur_mwh"]
            gen_mw = gen.get(h, 0.0)

            sum_weighted += price * gen_mw
            sum_gen += gen_mw
            sum_price += price
            count += 1

        if count > 0:
            daily[date_key] = {
                "date": d,
                "year": d.year,
                "month": d.month,
                "sum_weighted": sum_weighted,
                "sum_gen": sum_gen,
                "sum_price": sum_price,
                "count": count,
            }

    return daily


def _calculate_profile_capture(
    spot_prices: dict[str, list[dict]],
    profile: dict[tuple[int, int, int], float],
) -> dict[str, dict]:
    """Calculate capture prices using a PVsyst profile (month/day/hour)."""
    daily: dict[str, dict] = {}

    for date_key in sorted(spot_prices):
        hours = spot_prices[date_key]
        d = date.fromisoformat(date_key)

        sum_weighted = 0.0
        sum_weight = 0.0
        sum_price = 0.0
        count = 0

        for h_rec in hours:
            price = h_rec["eur_mwh"]
            utc_dt = datetime(
                d.year, d.month, d.day, h_rec["utc_hour"], tzinfo=UTC_TZ
            )
            local_dt = utc_dt.astimezone(SWEDEN_TZ)

            key = (local_dt.month, local_dt.day, local_dt.hour)
            weight = profile.get(key, 0.0)

            sum_weighted += price * weight
            sum_weight += weight
            sum_price += price
            count += 1

        if count > 0:
            daily[date_key] = {
                "date": d,
                "year": d.year,
                "month": d.month,
                "sum_weighted": sum_weighted,
                "sum_gen": sum_weight,
                "sum_price": sum_price,
                "count": count,
            }

    return daily


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _round_or_none(value: float | None, decimals: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, decimals)


def _finalize(sum_weighted: float, sum_gen: float, sum_price: float,
              count: int) -> tuple[float | None, float | None, float | None]:
    baseload = sum_price / count if count > 0 else None
    capture = sum_weighted / sum_gen if sum_gen > 0 else None
    ratio = capture / baseload if capture and baseload and baseload > 0 else None
    return (
        _round_or_none(baseload),
        _round_or_none(capture),
        _round_or_none(ratio, 3),
    )


def _aggregate_daily(daily_data: dict[str, dict]) -> list[dict]:
    result = []
    for date_key in sorted(daily_data):
        d = daily_data[date_key]
        baseload, capture, ratio = _finalize(
            d["sum_weighted"], d["sum_gen"], d["sum_price"], d["count"]
        )
        result.append({
            "date": date_key,
            "year": d["year"],
            "month": d["month"],
            "baseload": baseload,
            "capture": capture,
            "ratio": ratio,
        })
    return result


def _aggregate_to_monthly(daily_data: dict[str, dict]) -> list[dict]:
    monthly_acc: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"sw": 0.0, "sg": 0.0, "sp": 0.0, "c": 0}
    )
    for d in daily_data.values():
        key = (d["year"], d["month"])
        acc = monthly_acc[key]
        acc["sw"] += d["sum_weighted"]
        acc["sg"] += d["sum_gen"]
        acc["sp"] += d["sum_price"]
        acc["c"] += d["count"]

    result = []
    for (year, month) in sorted(monthly_acc):
        acc = monthly_acc[(year, month)]
        baseload, capture, ratio = _finalize(acc["sw"], acc["sg"], acc["sp"], acc["c"])
        result.append({
            "year": year,
            "month": month,
            "baseload": baseload,
            "capture": capture,
            "ratio": ratio,
        })
    return result


def _aggregate_to_yearly(daily_data: dict[str, dict]) -> list[dict]:
    yearly_acc: dict[int, dict] = defaultdict(
        lambda: {"sw": 0.0, "sg": 0.0, "sp": 0.0, "c": 0}
    )
    for d in daily_data.values():
        acc = yearly_acc[d["year"]]
        acc["sw"] += d["sum_weighted"]
        acc["sg"] += d["sum_gen"]
        acc["sp"] += d["sum_price"]
        acc["c"] += d["count"]

    result = []
    for year in sorted(yearly_acc):
        acc = yearly_acc[year]
        baseload, capture, ratio = _finalize(acc["sw"], acc["sg"], acc["sp"], acc["c"])
        result.append({
            "year": year,
            "baseload": baseload,
            "capture": capture,
            "ratio": ratio,
        })
    return result


# ---------------------------------------------------------------------------
# Forward curve data (Nasdaq futures)
# ---------------------------------------------------------------------------

def _parse_contract_period(symbol: str) -> tuple[str, str, str, str] | None:
    """Parse a contract symbol into (label, type, start_date, end_date).

    Examples:
        ENOFUTBLYR-27   -> ("YR-27", "year", "2027-01-01", "2027-12-31")
        ENOFUTBLQ2-26   -> ("Q2-26", "quarter", "2026-04-01", "2026-06-30")
        SYSTOFUTBLYR-27 -> ("YR-27", "year", "2027-01-01", "2027-12-31")
    """
    import re
    m = re.search(r'(YR|Q(\d))-(\d{2})$', symbol)
    if not m:
        return None
    period_type = m.group(1)
    year = 2000 + int(m.group(3))

    if period_type == "YR":
        return (f"YR-{m.group(3)}", "year", f"{year}-01-01", f"{year}-12-31")

    quarter = int(m.group(2))
    q_starts = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}
    q_ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
    return (
        f"Q{quarter}-{m.group(3)}",
        "quarter",
        f"{year}-{q_starts[quarter]}",
        f"{year}-{q_ends[quarter]}",
    )


def load_forward_curve_data(spot_data: dict[str, dict]) -> dict | None:
    """Load latest futures settlement prices and build forward curve.

    Args:
        spot_data: {zone: {date_key: [hours]}} for realized spot comparison

    Returns dict with:
        settlement_date: str
        contracts: [{label, type, start, end, sort_key}]
        sys: {label: price}
        epad: {zone: {label: price}}
        zone_fwd: {zone: {label: price}}  (sys + epad)
        spot_realized: {zone: {label: avg_price}}  for expired periods
    """
    if not NASDAQ_DATA_DIR.exists():
        return None

    sys_file = NASDAQ_DATA_DIR / "sys_baseload.csv"
    if not sys_file.exists():
        return None

    # Load SYS baseload: get latest daily_fix per contract
    sys_prices: dict[str, float] = {}
    settlement_date = ""
    with open(sys_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fix = row.get("daily_fix_eur", "").strip()
            if fix:
                try:
                    sys_prices[row["contract"]] = float(fix)
                    if row["date"] > settlement_date:
                        settlement_date = row["date"]
                except ValueError:
                    pass

    # Keep only the latest price per contract (last row wins since CSV is sorted)
    # Already handled by overwriting in the loop above

    # Load EPADs per zone
    epad_files = {
        "SE1": "epad_se1_lul.csv",
        "SE2": "epad_se2_sun.csv",
        "SE3": "epad_se3_sto.csv",
        "SE4": "epad_se4_mal.csv",
    }

    epad_prices: dict[str, dict[str, float]] = {}
    for zone, filename in epad_files.items():
        filepath = NASDAQ_DATA_DIR / filename
        if not filepath.exists():
            continue
        epad_prices[zone] = {}
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fix = row.get("daily_fix_eur", "").strip()
                if fix:
                    try:
                        epad_prices[zone][row["contract"]] = float(fix)
                    except ValueError:
                        pass

    # Build contract list from SYS contracts
    contracts = []
    for symbol in sys_prices:
        parsed = _parse_contract_period(symbol)
        if not parsed:
            continue
        label, ctype, start, end = parsed
        # Sort key: start_date then type (quarters before years for same start)
        sort_key = start + ("0" if ctype == "quarter" else "1")
        contracts.append({
            "label": label, "type": ctype,
            "start": start, "end": end, "sort_key": sort_key,
            "symbol": symbol,
        })

    contracts.sort(key=lambda c: c["sort_key"])

    # Filter: only future/current periods (end date >= settlement_date)
    # and skip quarters that overlap with year contracts already shown
    today_str = settlement_date or date.today().isoformat()
    active_contracts = [c for c in contracts if c["end"] >= today_str]

    # Build the final data
    sys_fwd: dict[str, float] = {}
    for c in active_contracts:
        price = sys_prices.get(c["symbol"])
        if price is not None:
            sys_fwd[c["label"]] = round(price, 2)

    epad_fwd: dict[str, dict[str, float]] = {}
    for zone in ZONES:
        if zone not in epad_prices:
            continue
        epad_fwd[zone] = {}
        for c in active_contracts:
            # EPAD symbol has different prefix but same suffix
            epad_symbol = None
            for sym in epad_prices[zone]:
                parsed_e = _parse_contract_period(sym)
                if parsed_e and parsed_e[0] == c["label"]:
                    epad_symbol = sym
                    break
            if epad_symbol:
                epad_fwd[zone][c["label"]] = round(
                    epad_prices[zone][epad_symbol], 2
                )

    # Calculate zone forward prices (SYS + EPAD)
    zone_fwd: dict[str, dict[str, float]] = {}
    for zone in ZONES:
        zone_fwd[zone] = {}
        for label, sys_price in sys_fwd.items():
            epad = epad_fwd.get(zone, {}).get(label, 0)
            zone_fwd[zone][label] = round(sys_price + epad, 2)

    # Calculate realized spot averages for expired periods
    spot_realized: dict[str, dict[str, float]] = {}
    expired_contracts = [c for c in contracts if c["end"] < today_str]
    for zone in ZONES:
        zone_spot = spot_data.get(zone, {})
        if not zone_spot:
            continue
        spot_realized[zone] = {}
        for c in expired_contracts:
            # Average spot price over the contract period
            total_price = 0.0
            count = 0
            for date_key, hours in zone_spot.items():
                if c["start"] <= date_key <= c["end"]:
                    for h in hours:
                        total_price += h["eur_mwh"]
                        count += 1
            if count > 0:
                # Also check what the forward was pricing this before delivery
                fwd_price = sys_prices.get(c["symbol"])
                epad_price = 0
                if zone in epad_prices:
                    for sym, p in epad_prices[zone].items():
                        parsed_e = _parse_contract_period(sym)
                        if parsed_e and parsed_e[0] == c["label"]:
                            epad_price = p
                            break
                if fwd_price is not None:
                    spot_realized[zone][c["label"]] = {
                        "spot_avg": round(total_price / count, 2),
                        "forward": round(fwd_price + epad_price, 2),
                    }

    contract_labels = [
        {"label": c["label"], "type": c["type"]}
        for c in active_contracts
    ]

    expired_labels = [
        {"label": c["label"], "type": c["type"]}
        for c in expired_contracts
        if any(c["label"] in spot_realized.get(z, {}) for z in ZONES)
    ]

    return {
        "settlement_date": settlement_date,
        "contracts": contract_labels,
        "expired_contracts": expired_labels,
        "sys": sys_fwd,
        "epad": epad_fwd,
        "zone_fwd": zone_fwd,
        "spot_realized": spot_realized,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def calculate_dashboard_v2_data() -> dict:
    """Calculate all data for Dashboard v2.

    Returns JSON-serializable dict with:
    - profiles: {key: label} for all available profiles
    - colors: {key: hex_color}
    - data: {zone: {profile_key: {yearly, monthly, daily}}}
    """
    # Discover profiles
    profiles: dict[str, str] = {"baseload": "Baseload"}
    for key, (_, label) in STANDARD_SOLAR_PROFILES.items():
        profiles[key] = label
    for key, (_, label) in ENTSOE_CAPTURE_TYPES.items():
        profiles[key] = label
    park_profiles = discover_park_profiles()
    for key, (_, label) in park_profiles.items():
        profiles[key] = label

    # Load PVsyst profiles
    pvsyst_loaded: dict[str, dict[tuple[int, int, int], float]] = {}
    for key, (filename, _) in STANDARD_SOLAR_PROFILES.items():
        p = load_pvsyst_profile(filename)
        if p:
            pvsyst_loaded[key] = p
    for key, (stem, _) in park_profiles.items():
        park_file = PARKS_DIR / f"{stem}.csv"
        if park_file.exists():
            pvsyst_loaded[key] = load_pvsyst_profile_from_path(park_file)

    # Colors
    colors = dict(PROFILE_COLORS)
    for i, key in enumerate(park_profiles):
        colors[key] = _PARK_COLORS[i % len(_PARK_COLORS)]

    data: dict[str, dict] = {}
    for zone in ZONES:
        print(f"  Beräknar {zone}...")
        spot = load_spot_prices(zone)
        if not spot:
            continue

        zone_data: dict[str, dict] = {}

        # Baseload — arithmetic mean (no weighting)
        baseload_daily: dict[str, dict] = {}
        for date_key, hours in spot.items():
            d = date.fromisoformat(date_key)
            s = sum(h["eur_mwh"] for h in hours)
            c = len(hours)
            baseload_daily[date_key] = {
                "date": d, "year": d.year, "month": d.month,
                "sum_weighted": s, "sum_gen": c,
                "sum_price": s, "count": c,
            }
        zone_data["baseload"] = {
            "yearly": _aggregate_to_yearly(baseload_daily),
            "monthly": _aggregate_to_monthly(baseload_daily),
            "daily": _aggregate_daily(baseload_daily),
        }

        # Solar profiles (PVsyst)
        for key, profile in pvsyst_loaded.items():
            # Park profiles: only calculate for matching zone
            if key.startswith("park_"):
                stem = park_profiles[key][0]
                park_zone = stem.rsplit("_", 1)[1]
                if park_zone != zone:
                    continue

            daily = _calculate_profile_capture(spot, profile)
            if daily:
                zone_data[key] = {
                    "yearly": _aggregate_to_yearly(daily),
                    "monthly": _aggregate_to_monthly(daily),
                    "daily": _aggregate_daily(daily),
                }

        # ENTSO-E actual generation (wind, hydro, nuclear)
        for key, (gen_type, _) in ENTSOE_CAPTURE_TYPES.items():
            gen = load_entsoe_generation(zone, gen_type)
            if not gen:
                continue
            daily = _calculate_entsoe_capture(spot, gen)
            if daily:
                zone_data[key] = {
                    "yearly": _aggregate_to_yearly(daily),
                    "monthly": _aggregate_to_monthly(daily),
                    "daily": _aggregate_daily(daily),
                }

        data[zone] = zone_data

    # BESS arbitrage calculations
    print("Beräknar BESS arbitrage...")
    spot_by_zone = {}
    for zone in ZONES:
        s = load_spot_prices(zone)
        if s:
            spot_by_zone[zone] = s

    bess_result = calculate_bess_data(spot_by_zone, pvsyst_loaded, list(spot_by_zone.keys()))

    # Merge BESS data into main data
    profiles.update(bess_result["profiles"])
    colors.update(bess_result["colors"])
    for zone in bess_result["data"]:
        if zone in data:
            data[zone].update(bess_result["data"][zone])
        else:
            data[zone] = bess_result["data"][zone]

    # Forward curve data
    print("  Laddar forward curve data...")
    spot_for_fwd = {}
    for zone in ZONES:
        spot = load_spot_prices(zone)
        if spot:
            spot_for_fwd[zone] = spot
    forward = load_forward_curve_data(spot_for_fwd)

    result = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "zones": [z for z in ZONES if z in data],
        "profiles": profiles,
        "colors": colors,
        "profile_meta": dict(BESS_PROFILE_META),
        "data": data,
    }
    if forward:
        result["forward"] = forward
        print(f"    {len(forward['contracts'])} aktiva kontrakt, settlement: {forward['settlement_date']}")

    return result
