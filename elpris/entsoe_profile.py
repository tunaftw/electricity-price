"""ENTSO-E based production profiles for solar and wind.

Generates normalized production profiles from actual ENTSO-E generation data.
These profiles can be used for capture price calculation weighted by real production.
"""

from __future__ import annotations

import csv
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from .config import ENTSOE_DATA_DIR

# Swedish timezone for proper UTC -> local time conversion
SWEDEN_TZ = ZoneInfo("Europe/Stockholm")

# Directory for ENTSO-E generation data
ENTSOE_DIR = ENTSOE_DATA_DIR / "generation"

# Supported generation types
GENERATION_TYPES = ["solar", "wind_onshore"]

# Cache for loaded profiles
_profile_cache: dict[tuple[str, str], dict[tuple[int, int, int], float]] = {}


def load_entsoe_generation(
    zone: str,
    gen_type: str,
    years: Optional[list[int]] = None,
) -> list[dict]:
    """
    Load ENTSO-E generation data for a zone and type.

    Args:
        zone: Electricity zone (SE1-SE4)
        gen_type: Generation type (solar, wind_onshore)
        years: List of years to load (None = all available)

    Returns:
        List of dicts with time_start, generation_mw
    """
    zone_dir = ENTSOE_DIR / zone
    if not zone_dir.exists():
        return []

    records = []
    pattern = f"{gen_type}_*.csv"

    for csv_file in sorted(zone_dir.glob(pattern)):
        # Extract year from filename
        year = int(csv_file.stem.split("_")[-1])
        if years and year not in years:
            continue

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append({
                    "time_start": row["time_start"],
                    "generation_mw": float(row["generation_mw"]),
                })

    return records


def create_typical_profile(
    zone: str,
    gen_type: str,
    years: Optional[list[int]] = None,
) -> dict[tuple[int, int, int], float]:
    """
    Create a typical annual profile from ENTSO-E data.

    Aggregates generation data by (month, day, hour) and normalizes
    so that the sum of all weights equals 1.0.

    Args:
        zone: Electricity zone
        gen_type: Generation type
        years: Years to include (None = all)

    Returns:
        Dict mapping (month, day, hour) to normalized weight
    """
    records = load_entsoe_generation(zone, gen_type, years)
    if not records:
        return {}

    # Aggregate by (month, day, hour)
    aggregated: dict[tuple[int, int, int], list[float]] = {}

    for rec in records:
        ts_utc = datetime.fromisoformat(rec["time_start"].replace("Z", "+00:00"))
        # Convert UTC to local Swedish time (handles CET/CEST automatically)
        ts_local = ts_utc.astimezone(SWEDEN_TZ)

        key = (ts_local.month, ts_local.day, ts_local.hour)

        if key not in aggregated:
            aggregated[key] = []
        aggregated[key].append(rec["generation_mw"])

    # Calculate mean for each time slot
    profile: dict[tuple[int, int, int], float] = {}
    for key, values in aggregated.items():
        profile[key] = sum(values) / len(values)

    # Normalize so sum = 1.0
    total = sum(profile.values())
    if total > 0:
        profile = {k: v / total for k, v in profile.items()}

    return profile


def get_entsoe_profile(zone: str, gen_type: str) -> dict[tuple[int, int, int], float]:
    """
    Get ENTSO-E profile, using cache.

    Args:
        zone: Electricity zone (SE1-SE4)
        gen_type: Generation type (solar, wind_onshore)

    Returns:
        Normalized profile dict
    """
    cache_key = (zone, gen_type)

    if cache_key not in _profile_cache:
        _profile_cache[cache_key] = create_typical_profile(zone, gen_type)

    return _profile_cache[cache_key]


def get_entsoe_weight(timestamp: datetime, zone: str, gen_type: str) -> float:
    """
    Get production weight for a given timestamp from ENTSO-E profile.

    Args:
        timestamp: The datetime to get weight for
        zone: Electricity zone (SE1-SE4)
        gen_type: Generation type (solar, wind_onshore)

    Returns:
        Normalized production weight (sum of all weights = 1.0)
    """
    profile = get_entsoe_profile(zone, gen_type)

    if not profile:
        return 0.0

    key = (timestamp.month, timestamp.day, timestamp.hour)
    return profile.get(key, 0.0)


def list_available_entsoe_profiles() -> list[str]:
    """
    List all available ENTSO-E profile combinations.

    Returns:
        List of profile names like "entsoe_solar_SE3", "entsoe_wind_SE3"
    """
    profiles = []

    for zone_dir in sorted(ENTSOE_DIR.iterdir()):
        if not zone_dir.is_dir():
            continue
        zone = zone_dir.name

        for gen_type in GENERATION_TYPES:
            pattern = f"{gen_type}_*.csv"
            if list(zone_dir.glob(pattern)):
                profiles.append(f"entsoe_{gen_type}_{zone}")

    return profiles


def save_profile_csv(zone: str, gen_type: str, output_dir: Optional[Path] = None) -> Path:
    """
    Save a typical profile to CSV for inspection/debugging.

    Format: month,day,hour,weight

    Args:
        zone: Electricity zone
        gen_type: Generation type
        output_dir: Output directory (default: data/profiles/)

    Returns:
        Path to saved file
    """
    if output_dir is None:
        output_dir = DATA_DIR / "profiles"

    output_dir.mkdir(parents=True, exist_ok=True)

    profile = get_entsoe_profile(zone, gen_type)
    output_file = output_dir / f"{gen_type}_{zone}.csv"

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["month", "day", "hour", "weight"])

        for key in sorted(profile.keys()):
            month, day, hour = key
            weight = profile[key]
            writer.writerow([month, day, hour, f"{weight:.8f}"])

    return output_file


def save_all_profiles(output_dir: Optional[Path] = None) -> list[Path]:
    """
    Generate and save all available ENTSO-E profiles.

    Args:
        output_dir: Output directory

    Returns:
        List of saved file paths
    """
    saved = []

    for profile_name in list_available_entsoe_profiles():
        # Parse name: entsoe_solar_SE3 or entsoe_wind_onshore_SE3
        parts = profile_name.split("_")
        # entsoe_solar_SE3 -> ["entsoe", "solar", "SE3"]
        # entsoe_wind_onshore_SE3 -> ["entsoe", "wind", "onshore", "SE3"]
        if len(parts) == 3:
            gen_type = parts[1]
            zone = parts[2]
        elif len(parts) == 4:
            gen_type = f"{parts[1]}_{parts[2]}"
            zone = parts[3]
        else:
            continue

        path = save_profile_csv(zone, gen_type, output_dir)
        saved.append(path)
        print(f"Saved: {path}")

    return saved
