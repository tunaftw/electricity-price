"""Tester för elpris.unified_dashboard_data — Phase 1 backend för unified dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.unified_dashboard_data import build_unified_data


# Module-level cache: build_unified_data() är dyr (laddar massor av CSV).
# Bygg en gång och dela mellan alla tester.
_DATA_CACHE: dict = {}


def _data() -> dict:
    if "data" not in _DATA_CACHE:
        _DATA_CACHE["data"] = build_unified_data()
    return _DATA_CACHE["data"]


# ---------------------------------------------------------------------------
# Task 1.1 — scaffold
# ---------------------------------------------------------------------------

def test_build_unified_data_top_level_keys():
    """build_unified_data() ska returnera dict med top-level keys."""
    data = _data()
    assert isinstance(data, dict)
    for key in ("generated", "market", "assets", "meta"):
        assert key in data, f"Saknar top-level key: {key}"


# ---------------------------------------------------------------------------
# Task 1.2 — market data
# ---------------------------------------------------------------------------

def test_market_contains_dashboard_v2_keys():
    """data['market'] ska innehålla nycklar från dashboard_v2_data."""
    market = _data()["market"]
    # Verifierat genom att läsa dashboard_v2_data.calculate_dashboard_v2_data()
    for key in ("zones", "profiles", "colors", "data"):
        assert key in market, f"market saknar nyckel: {key}"


def test_meta_populated_from_market():
    """meta ska innehålla zones/profiles/colors från market."""
    meta = _data()["meta"]
    market = _data()["market"]
    assert meta["zones"] == market["zones"]
    assert meta["profiles"] == market["profiles"]
    assert meta["colors"] == market["colors"]


# ---------------------------------------------------------------------------
# Task 1.3 — per-park monthly KPIs
# ---------------------------------------------------------------------------

EXPECTED_PARK_KEYS = {
    "horby", "fjallskar", "agerum", "hova",
    "skakelbacken", "stenstorp", "tangen", "bjorke",
}


def test_assets_has_all_parks():
    """data['assets']['parks'] ska innehålla alla 8 parker."""
    parks = _data()["assets"]["parks"]
    assert isinstance(parks, dict)
    assert set(parks.keys()) == EXPECTED_PARK_KEYS


def test_park_record_shape():
    """Varje park ska ha name, zone, capacity_mwp, months."""
    parks = _data()["assets"]["parks"]
    for park_key, park in parks.items():
        assert "name" in park, f"{park_key} saknar name"
        assert "zone" in park, f"{park_key} saknar zone"
        assert "capacity_mwp" in park, f"{park_key} saknar capacity_mwp"
        assert "months" in park, f"{park_key} saknar months"
        assert isinstance(park["months"], list)


def test_park_month_record_fields():
    """Månadsrecords ska ha förväntade fält när det finns data."""
    parks = _data()["assets"]["parks"]
    # Hitta minst en park med data
    parks_with_data = [p for p in parks.values() if p["months"]]
    assert parks_with_data, "Ingen park hade några månadsdata"
    sample = parks_with_data[0]["months"][0]
    for field in ("year", "month", "energy_mwh", "budget_mwh",
                  "vs_budget_pct", "yield_kwh_kwp", "pr_pct"):
        assert field in sample, f"Saknat fält i månadsrecord: {field}"


# ---------------------------------------------------------------------------
# Task 1.4 — fleet overview
# ---------------------------------------------------------------------------

def test_assets_fleet_section_exists():
    """data['assets']['fleet'] ska innehålla flotta-KPI:er."""
    fleet = _data()["assets"]["fleet"]
    for field in ("latest_month", "park_count", "total_capacity_mwp",
                  "total_energy_mwh", "vs_budget_pct"):
        assert field in fleet, f"fleet saknar fält: {field}"


def test_assets_fleet_park_count_matches():
    """park_count ska matcha antalet parker som har någon data."""
    parks = _data()["assets"]["parks"]
    fleet = _data()["assets"]["fleet"]
    parks_with_data = sum(1 for p in parks.values() if p["months"])
    # park_count räknar parker som bidragit till latest_month, så
    # det är ≤ parks_with_data
    assert fleet["park_count"] <= parks_with_data
    assert fleet["park_count"] >= 0


# ---------------------------------------------------------------------------
# Task 1.5 — operations metrics per park
# ---------------------------------------------------------------------------

def test_park_months_have_neg_price_fields():
    """Varje månadsrecord ska ha neg_price_hours och neg_price_volume_mwh."""
    parks = _data()["assets"]["parks"]
    parks_with_data = [p for p in parks.values() if p["months"]]
    assert parks_with_data, "Ingen park hade några månadsdata"
    for park in parks_with_data:
        for m in park["months"]:
            assert "neg_price_hours" in m, (
                f"Saknar neg_price_hours i {park['name']} "
                f"{m['year']}-{m['month']}"
            )
            assert "neg_price_volume_mwh" in m
