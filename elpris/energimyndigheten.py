"""Energimyndigheten PxWeb API client for installed capacity statistics.

Provides access to solar and wind power installation data from Sweden's
official energy statistics database.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path
from typing import Iterator

import requests

from .config import INSTALLED_DATA_DIR

# PxWeb API base URL
PXWEB_BASE = "https://pxexternal.energimyndigheten.se/api/v1/sv/Energimyndighetens_statistikdatabas/Officiell_energistatistik"

# Table IDs
TABLES = {
    "solar": "Natanslutna_solcellsanlaggningar/EN0123_1.px",
    "solar_per_capita": "Natanslutna_solcellsanlaggningar/EN0123_2.px",
    "wind_national": "Vindkraftsstatistik/EN0105_1.px",
    "wind_elarea": "Vindkraftsstatistik/EN0105_2.px",
    "wind_county": "Vindkraftsstatistik/EN0105_3.px",
    "wind_municipality": "Vindkraftsstatistik/EN0105_4.px",
    "wind_land_sea": "Vindkraftsstatistik/EN0105_5.px",
}

# Data directory
INSTALLED_DIR = INSTALLED_DATA_DIR


def fetch_table_metadata(table_key: str) -> dict:
    """
    Fetch metadata for a table (available years, variables, etc.).

    Args:
        table_key: Key from TABLES dict

    Returns:
        Table metadata as dict
    """
    if table_key not in TABLES:
        raise ValueError(f"Unknown table: {table_key}. Use: {list(TABLES.keys())}")

    url = f"{PXWEB_BASE}/{TABLES[table_key]}"
    response = requests.get(url, timeout=30, verify=False)
    response.raise_for_status()
    return response.json()


def fetch_wind_by_elarea(years: list[str] | None = None) -> str:
    """
    Fetch wind power statistics by electricity area (SE1-SE4).

    Args:
        years: List of year indices (e.g., ["21"] for 2024), None for all

    Returns:
        CSV content with wind power data
    """
    url = f"{PXWEB_BASE}/{TABLES['wind_elarea']}"

    # Get metadata to find available years
    meta = fetch_table_metadata("wind_elarea")
    year_var = next(v for v in meta["variables"] if v["code"] == "År")
    available_years = year_var["values"]

    if years is None:
        years = available_years

    query = {
        "query": [
            {"code": "År", "selection": {"filter": "item", "values": years}},
            {"code": "Elområde", "selection": {"filter": "item", "values": ["0", "1", "2", "3"]}},
            {"code": "Kategori", "selection": {"filter": "item", "values": ["0", "1", "2"]}},
        ],
        "response": {"format": "csv"},
    }

    response = requests.post(url, json=query, timeout=60, verify=False)
    response.raise_for_status()
    return response.text


def fetch_solar_installations(years: list[str] | None = None) -> str:
    """
    Fetch solar installation statistics by region.

    Args:
        years: List of year indices, None for all

    Returns:
        CSV content with solar installation data
    """
    url = f"{PXWEB_BASE}/{TABLES['solar']}"

    # Get metadata
    meta = fetch_table_metadata("solar")
    year_var = next(v for v in meta["variables"] if v["code"] == "År")
    available_years = year_var["values"]

    if years is None:
        years = available_years

    # Find the region and power class variables
    region_var = next((v for v in meta["variables"] if "region" in v["code"].lower() or "län" in v["code"].lower()), None)
    power_var = next((v for v in meta["variables"] if "effekt" in v["code"].lower() or "klass" in v["code"].lower()), None)

    query_items = [
        {"code": "År", "selection": {"filter": "item", "values": years}},
    ]

    # Add region if available
    if region_var:
        query_items.append({
            "code": region_var["code"],
            "selection": {"filter": "item", "values": region_var["values"]}
        })

    # Add power class if available
    if power_var:
        query_items.append({
            "code": power_var["code"],
            "selection": {"filter": "item", "values": power_var["values"]}
        })

    query = {
        "query": query_items,
        "response": {"format": "csv"},
    }

    response = requests.post(url, json=query, timeout=60, verify=False)
    response.raise_for_status()
    return response.text


def parse_wind_csv(csv_content: str) -> Iterator[dict]:
    """
    Parse wind power CSV from PxWeb.

    Yields:
        Dict with year, zone, turbines, installed_mw, production_gwh
    """
    # Fix encoding issues
    csv_content = csv_content.replace("�", "å").replace("Ã¥", "å")

    reader = csv.DictReader(io.StringIO(csv_content))

    for row in reader:
        try:
            # Find the year column (may be "År" or similar)
            year = None
            for key in row.keys():
                if "r" in key.lower() and len(row[key]) == 4:
                    year = row[key]
                    break

            # Find zone
            zone = None
            for key in row.keys():
                if "omr" in key.lower():
                    zone = row[key]
                    break

            if not year or not zone:
                continue

            yield {
                "year": int(year),
                "zone": zone,
                "turbines": int(float(row.get("Antal verk, st", 0))),
                "installed_mw": float(row.get("Installerad effekt, MW", 0)),
                "production_gwh": float(row.get("Elproduktion, GWh", 0)),
            }
        except (ValueError, KeyError):
            continue


def parse_solar_csv(csv_content: str) -> Iterator[dict]:
    """
    Parse solar installation CSV from PxWeb.

    Yields:
        Dict with parsed solar data
    """
    # Fix encoding
    csv_content = csv_content.replace("�", "å").replace("Ã¥", "å")

    reader = csv.DictReader(io.StringIO(csv_content))

    for row in reader:
        try:
            result = {}
            for key, value in row.items():
                # Clean key
                clean_key = key.lower().replace(" ", "_").replace(",", "")
                clean_key = clean_key.replace("å", "a").replace("ä", "a").replace("ö", "o")

                # Try to convert to number
                try:
                    if "." in value:
                        result[clean_key] = float(value)
                    else:
                        result[clean_key] = int(value)
                except ValueError:
                    result[clean_key] = value

            yield result
        except Exception:
            continue


def save_wind_data(records: list[dict]) -> Path:
    """Save wind power data to CSV."""
    INSTALLED_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = INSTALLED_DIR / "wind_by_elarea.csv"

    fieldnames = ["year", "zone", "turbines", "installed_mw", "production_gwh"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(records, key=lambda x: (x["year"], x["zone"])))

    return csv_path


def save_solar_data(records: list[dict], filename: str = "solar_installations.csv") -> Path:
    """Save solar installation data to CSV."""
    INSTALLED_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = INSTALLED_DIR / filename

    if not records:
        return csv_path

    fieldnames = list(records[0].keys())

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return csv_path


def download_installed_capacity(verbose: bool = True) -> dict:
    """
    Download all installed capacity data.

    Returns:
        Dict with download statistics
    """
    import warnings
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    results = {"wind": 0, "solar": 0}

    # Download wind data
    if verbose:
        print("Downloading wind power statistics by electricity area...")

    try:
        csv_content = fetch_wind_by_elarea()
        records = list(parse_wind_csv(csv_content))
        save_wind_data(records)
        results["wind"] = len(records)
        if verbose:
            print(f"  Saved {len(records)} wind power records")
    except Exception as e:
        if verbose:
            print(f"  Error downloading wind data: {e}")

    # Download solar data
    if verbose:
        print("Downloading solar installation statistics...")

    try:
        csv_content = fetch_solar_installations()
        records = list(parse_solar_csv(csv_content))
        save_solar_data(records)
        results["solar"] = len(records)
        if verbose:
            print(f"  Saved {len(records)} solar installation records")
    except Exception as e:
        if verbose:
            print(f"  Error downloading solar data: {e}")

    if verbose:
        print(f"\nData saved to: {INSTALLED_DIR}")

    return results
