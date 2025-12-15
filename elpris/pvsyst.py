"""PVsyst hourly data parser and profile normalization."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .config import DATA_DIR

# Directory for processed solar profiles
SOLAR_PROFILES_DIR = DATA_DIR / "solar_profiles"

# Specific yield calibration (kWh/kWp) for Swedish latitude
SPECIFIC_YIELD_EW = 911       # E-W bifacial (Böda Sand, 1064 kWh/m² GHI)
SPECIFIC_YIELD_SOUTH = 1012   # South bifacial (Lundby)
SPECIFIC_YIELD_TRACKER = 1202 # Single-axis tracker bifacial (Hova)


def parse_pvsyst_hourly(filepath: Path) -> Iterator[dict]:
    """
    Parse PVsyst hourly CSV export.

    Expected format:
    - Lines 1-13: Header/metadata (skipped)
    - Line 14+: Data rows with format DD/MM/YY HH:MM,col1,col2,...
    - Supports both comma (,) and semicolon (;) as delimiter

    Args:
        filepath: Path to PVsyst CSV file

    Yields:
        Dict with month, day, hour, power_kw
    """
    with open(filepath, "r", encoding="latin-1") as f:
        lines = f.readlines()

    # Find header row (contains "date" or "E_Grid")
    header_idx = None
    for i, line in enumerate(lines):
        if "E_Grid" in line and "date" in line.lower():
            header_idx = i
            break

    if header_idx is None:
        raise ValueError("Could not find header row with 'date' and 'E_Grid'")

    # Detect delimiter (comma or semicolon)
    header_line = lines[header_idx].strip()
    delimiter = ";" if ";" in header_line else ","

    # Parse header to find E_Grid column
    header = header_line.split(delimiter)
    try:
        egrid_col = header.index("E_Grid")
    except ValueError:
        raise ValueError("Could not find 'E_Grid' column in header")

    # Skip header row + unit row
    data_start = header_idx + 2

    for line in lines[data_start:]:
        line = line.strip()
        if not line:
            continue

        parts = line.split(delimiter)
        if len(parts) <= egrid_col:
            continue

        # Parse timestamp: DD/MM/YY HH:MM or DD/MM/YYYY HH:MM
        timestamp_str = parts[0].strip()
        dt = None
        for fmt in ["%d/%m/%y %H:%M", "%d/%m/%Y %H:%M"]:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            continue

        # Parse E_Grid (power in kW)
        try:
            power_kw = float(parts[egrid_col])
        except ValueError:
            continue

        # Set negative values to 0 (standby consumption not relevant)
        if power_kw < 0:
            power_kw = 0.0

        yield {
            "month": dt.month,
            "day": dt.day,
            "hour": dt.hour,
            "power_kw": power_kw,
        }


def calculate_system_size(records: list[dict], specific_yield: float = SPECIFIC_YIELD_EW) -> float:
    """
    Calculate system size from annual energy production.

    Args:
        records: List of hourly records with power_kw
        specific_yield: Expected kWh/kWp per year

    Returns:
        System size in kWp
    """
    # Sum hourly power (kW * 1h = kWh)
    total_kwh = sum(r["power_kw"] for r in records)
    return total_kwh / specific_yield


def normalize_profile(records: list[dict], system_kwp: float) -> list[dict]:
    """
    Normalize power output to 1 MW reference system.

    Args:
        records: List of hourly records with power_kw
        system_kwp: System size in kWp

    Returns:
        Records with added power_mw field (normalized to 1 MW)
    """
    system_mw = system_kwp / 1000

    for r in records:
        # Power per MW of installed capacity
        r["power_mw"] = r["power_kw"] / 1000 / system_mw if system_mw > 0 else 0.0

    return records


def save_profile(records: list[dict], name: str) -> Path:
    """
    Save normalized profile to CSV.

    Args:
        records: Normalized records with month, day, hour, power_mw
        name: Profile name (e.g., "ew_boda")

    Returns:
        Path to saved file
    """
    SOLAR_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SOLAR_PROFILES_DIR / f"{name}.csv"

    fieldnames = ["month", "day", "hour", "power_mw"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in sorted(records, key=lambda x: (x["month"], x["day"], x["hour"])):
            writer.writerow({
                "month": r["month"],
                "day": r["day"],
                "hour": r["hour"],
                "power_mw": round(r["power_mw"], 6),
            })

    return output_path


def process_pvsyst_file(
    filepath: Path,
    profile_name: str,
    specific_yield: float = SPECIFIC_YIELD_EW,
    verbose: bool = True,
) -> dict:
    """
    Process a PVsyst hourly file into a normalized profile.

    Args:
        filepath: Path to PVsyst CSV
        profile_name: Name for the output profile
        specific_yield: Expected kWh/kWp per year
        verbose: Print progress

    Returns:
        Dict with processing statistics
    """
    if verbose:
        print(f"Parsing PVsyst file: {filepath.name}")

    # Parse file
    records = list(parse_pvsyst_hourly(filepath))

    if not records:
        raise ValueError("No valid records found in file")

    if verbose:
        print(f"  Parsed {len(records)} hourly records")

    # Calculate system size
    system_kwp = calculate_system_size(records, specific_yield)

    if verbose:
        total_mwh = sum(r["power_kw"] for r in records) / 1000
        print(f"  Annual production: {total_mwh:.1f} MWh")
        print(f"  Estimated system size: {system_kwp:.1f} kWp ({system_kwp/1000:.2f} MWp)")

    # Normalize
    records = normalize_profile(records, system_kwp)

    # Find peak
    max_power = max(r["power_mw"] for r in records)

    if verbose:
        print(f"  Peak power (normalized): {max_power:.3f} MW per MW installed")

    # Save
    output_path = save_profile(records, profile_name)

    if verbose:
        print(f"  Saved to: {output_path}")

    return {
        "records": len(records),
        "system_kwp": system_kwp,
        "total_mwh": sum(r["power_kw"] for r in records) / 1000,
        "peak_mw": max_power,
        "output_path": output_path,
    }


def load_profile(name: str) -> dict[tuple, float]:
    """
    Load a saved solar profile.

    Args:
        name: Profile name (e.g., "ew_boda")

    Returns:
        Dict mapping (month, day, hour) to power_mw
    """
    filepath = SOLAR_PROFILES_DIR / f"{name}.csv"

    if not filepath.exists():
        raise FileNotFoundError(f"Profile not found: {filepath}")

    profile = {}

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row["month"]), int(row["day"]), int(row["hour"]))
            profile[key] = float(row["power_mw"])

    return profile
