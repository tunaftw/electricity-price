"""Solar and wind production profiles for Sweden."""

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .config import DATA_DIR
from .entsoe_profile import get_entsoe_weight, list_available_entsoe_profiles

# Directory for solar profiles
SOLAR_PROFILES_DIR = DATA_DIR / "solar_profiles"

# Cache for loaded PVsyst profiles
_pvsyst_profiles: dict[str, dict[tuple, float]] = {}

# Typical Swedish solar profile - relative production per hour (0-23)
# Based on average annual pattern, normalized to sum = 1.0 per day
# Peak production around 11:00-14:00
HOURLY_PROFILE_SWEDEN = {
    0: 0.000,
    1: 0.000,
    2: 0.000,
    3: 0.000,
    4: 0.002,
    5: 0.015,
    6: 0.040,
    7: 0.070,
    8: 0.095,
    9: 0.115,
    10: 0.130,
    11: 0.135,
    12: 0.135,
    13: 0.130,
    14: 0.115,
    15: 0.095,
    16: 0.070,
    17: 0.040,
    18: 0.015,
    19: 0.002,
    20: 0.000,
    21: 0.000,
    22: 0.000,
    23: 0.000,
}

# Monthly adjustment factors (Sweden varies significantly by season)
# January = 1, December = 12
MONTHLY_FACTORS_SWEDEN = {
    1: 0.15,   # January - very low sun
    2: 0.30,   # February
    3: 0.55,   # March
    4: 0.85,   # April
    5: 1.15,   # May
    6: 1.30,   # June - peak
    7: 1.25,   # July
    8: 1.00,   # August
    9: 0.70,   # September
    10: 0.40,  # October
    11: 0.20,  # November
    12: 0.10,  # December - lowest
}


def get_solar_weight(timestamp: datetime, profile: str = "sweden") -> float:
    """
    Get solar production weight for a given timestamp.

    Returns a relative weight (not absolute production).
    Higher weight = more solar production expected at this time.

    Args:
        timestamp: The datetime to get weight for
        profile: Which profile to use:
            - "sweden": Generic Swedish profile (monthly/hourly factors)
            - "entsoe_solar_SE3": ENTSO-E actual solar for SE3
            - "entsoe_wind_SE3": ENTSO-E actual wind for SE3
            - Other names: PVsyst profiles from data/solar_profiles/

    Returns:
        Relative solar production weight
    """
    if profile == "sweden":
        # Use generic Swedish profile
        hour = timestamp.hour
        month = timestamp.month

        hourly_weight = HOURLY_PROFILE_SWEDEN.get(hour, 0.0)
        monthly_factor = MONTHLY_FACTORS_SWEDEN.get(month, 1.0)

        return hourly_weight * monthly_factor
    elif profile.startswith("entsoe_"):
        # ENTSO-E based profile: entsoe_solar_SE3, entsoe_wind_SE3, etc.
        parts = profile.split("_")
        if len(parts) >= 3:
            gen_type = parts[1]  # solar, wind_onshore
            zone = parts[2]      # SE1, SE2, SE3, SE4
            # Handle wind_onshore (entsoe_wind_onshore_SE3)
            if len(parts) == 4:
                gen_type = f"{parts[1]}_{parts[2]}"
                zone = parts[3]
            return get_entsoe_weight(timestamp, zone, gen_type)
        return 0.0
    else:
        # Try to load PVsyst profile
        return get_pvsyst_weight(timestamp, profile)


def get_quarterly_solar_weight(timestamp: datetime, profile: str = "sweden") -> float:
    """
    Get solar production weight for a 15-minute period.

    Interpolates linearly between hourly weights for smoother transitions.

    Args:
        timestamp: Start of the 15-minute period
        profile: Which profile to use

    Returns:
        Relative solar production weight
    """
    minute = timestamp.minute
    current_weight = get_solar_weight(timestamp, profile)

    # If at the start of hour, no interpolation needed
    if minute == 0:
        return current_weight

    # Get next hour's weight for interpolation
    next_hour = timestamp.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    next_weight = get_solar_weight(next_hour, profile)

    # Linear interpolation: weight = current + (next - current) * (minute / 60)
    fraction = minute / 60.0
    return current_weight + (next_weight - current_weight) * fraction


def load_pvsyst_profile(name: str) -> dict[tuple, float]:
    """
    Load a PVsyst-generated solar profile.

    Args:
        name: Profile name (e.g., "ew_boda")

    Returns:
        Dict mapping (month, day, hour) to power_mw (normalized to 1 MW)
    """
    global _pvsyst_profiles

    if name in _pvsyst_profiles:
        return _pvsyst_profiles[name]

    filepath = SOLAR_PROFILES_DIR / f"{name}.csv"

    if not filepath.exists():
        raise FileNotFoundError(f"Profile not found: {filepath}")

    import csv

    profile = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row["month"]), int(row["day"]), int(row["hour"]))
            profile[key] = float(row["power_mw"])

    _pvsyst_profiles[name] = profile
    return profile


def get_pvsyst_weight(timestamp: datetime, profile_name: str) -> float:
    """
    Get solar production weight from a PVsyst profile.

    Args:
        timestamp: The datetime to get weight for
        profile_name: Name of the PVsyst profile

    Returns:
        Power output in MW per MW installed (0.0 to ~0.9)
    """
    profile = load_pvsyst_profile(profile_name)
    key = (timestamp.month, timestamp.day, timestamp.hour)
    return profile.get(key, 0.0)


def list_available_profiles() -> list[str]:
    """List all available production profiles (solar, wind)."""
    profiles = ["sweden"]  # Generic profile always available

    # Add PVsyst profiles
    if SOLAR_PROFILES_DIR.exists():
        for f in SOLAR_PROFILES_DIR.glob("*.csv"):
            profiles.append(f.stem)

    # Add ENTSO-E profiles (solar and wind per zone)
    profiles.extend(list_available_entsoe_profiles())

    return sorted(profiles)
