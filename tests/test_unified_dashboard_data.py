"""Tester för elpris.unified_dashboard_data — Phase 1 backend för unified dashboard."""

from __future__ import annotations

import json
import re
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
# Irradiation fields per month
# ---------------------------------------------------------------------------

def test_park_month_record_has_irradiation_fields():
    """Senaste månadsrecordet ska innehålla irradiation-fält."""
    parks = _data()["assets"]["parks"]
    parks_with_data = [p for p in parks.values() if p["months"]]
    assert parks_with_data, "Ingen park hade några månadsdata"
    for park in parks_with_data:
        latest = park["months"][-1]
        for field in ("actual_irr_kwh_m2", "budget_irr_kwh_m2", "vs_budget_irr_pct"):
            assert field in latest, (
                f"Saknat fält i månadsrecord ({park['name']}): {field}"
            )


def test_park_month_budget_irradiation_is_positive():
    """För minst en park ska budget_irr_kwh_m2 vara > 0 i senaste månaden."""
    parks = _data()["assets"]["parks"]
    found_positive = False
    for park in parks.values():
        if not park["months"]:
            continue
        latest = park["months"][-1]
        v = latest.get("budget_irr_kwh_m2")
        if v is not None and v > 0:
            found_positive = True
            break
    assert found_positive, (
        "Förväntade att minst en park har budget_irr_kwh_m2 > 0 i senaste månaden"
    )


# ---------------------------------------------------------------------------
# Task 1.4 — fleet overview
# ---------------------------------------------------------------------------

def test_assets_fleet_section_exists():
    """data['assets']['fleet'] ska innehålla flotta-KPI:er."""
    fleet = _data()["assets"]["fleet"]
    for field in ("latest_month", "park_count", "total_capacity_mwp",
                  "total_energy_mwh", "vs_budget_pct"):
        assert field in fleet, f"fleet saknar fält: {field}"


def test_assets_fleet_latest_month_is_yyyy_mm_string():
    """fleet.latest_month ska vara en sträng på formen 'YYYY-MM'."""
    fleet = _data()["assets"]["fleet"]
    latest = fleet["latest_month"]
    # Endast None tillåts om ingen park har data alls
    if latest is None:
        return
    assert isinstance(latest, str), (
        f"latest_month måste vara str, fick {type(latest).__name__}"
    )
    assert re.match(r"^\d{4}-\d{2}$", latest), (
        f"latest_month måste matcha 'YYYY-MM', fick {latest!r}"
    )


def test_assets_fleet_park_count_matches():
    """park_count ska matcha antalet parker som har någon data."""
    parks = _data()["assets"]["parks"]
    fleet = _data()["assets"]["fleet"]
    parks_with_data = sum(1 for p in parks.values() if p["months"])
    # park_count räknar parker som bidragit till latest_month, så
    # det är ≤ parks_with_data
    assert fleet["park_count"] <= parks_with_data
    assert 0 < fleet["park_count"] <= 8


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


# ---------------------------------------------------------------------------
# Task 1.6 — tracker-gain summary
# ---------------------------------------------------------------------------

def test_assets_tracker_gain_exists():
    """data['assets']['tracker_gain'] ska finnas med monthly-lista."""
    tg = _data()["assets"]["tracker_gain"]
    assert isinstance(tg, dict)
    assert "monthly" in tg
    assert isinstance(tg["monthly"], list)


# ---------------------------------------------------------------------------
# Phase 2 fix — daily-by-month per park
# ---------------------------------------------------------------------------

def test_park_has_daily_by_month():
    """Varje park ska ha en daily_by_month dict (tom om data saknas)."""
    parks = _data()["assets"]["parks"]
    for park_key, park in parks.items():
        assert "daily_by_month" in park, f"{park_key} saknar daily_by_month"
        assert isinstance(park["daily_by_month"], dict)


def test_daily_by_month_keys_are_yyyy_mm():
    """Nycklarna ska följa formatet YYYY-MM."""
    parks = _data()["assets"]["parks"]
    for park in parks.values():
        for key in park["daily_by_month"].keys():
            assert re.match(r"^\d{4}-\d{2}$", key), (
                f"Ogiltig nyckel i daily_by_month: {key!r}"
            )


def test_daily_by_month_record_fields():
    """Varje daglig record ska ha förväntade fält."""
    parks = _data()["assets"]["parks"]
    sample = None
    for park in parks.values():
        for month_key, days in park["daily_by_month"].items():
            if days:
                sample = days[0]
                break
        if sample is not None:
            break
    if sample is None:
        # Ingen park har dagsdata — acceptabelt om Bazefield-data saknas
        return
    for field in ("day", "date", "weekday", "energy_mwh",
                  "yield_kwh_kwp", "expected_mwh", "pr_pct"):
        assert field in sample, f"Saknat fält i daglig record: {field}"


def test_daily_by_month_limited_to_recent_months():
    """daily_by_month ska bara innehålla senaste DAILY_HISTORY_MONTHS månaderna."""
    from elpris.unified_dashboard_data import DAILY_HISTORY_MONTHS
    parks = _data()["assets"]["parks"]
    for park in parks.values():
        assert len(park["daily_by_month"]) <= DAILY_HISTORY_MONTHS


# ---------------------------------------------------------------------------
# Phase 2 fix — capture-by-zone reference
# ---------------------------------------------------------------------------

def test_assets_has_capture_by_zone():
    """data['assets']['capture_by_zone'] ska finnas."""
    assets = _data()["assets"]
    assert "capture_by_zone" in assets
    assert isinstance(assets["capture_by_zone"], dict)


def test_capture_by_zone_record_shape():
    """Varje record i capture_by_zone[zone] ska ha month + capture_eur_mwh."""
    cap = _data()["assets"]["capture_by_zone"]
    if not cap:
        return  # acceptabelt om ingen marknadsdata finns
    for zone, records in cap.items():
        assert isinstance(records, list)
        if records:
            sample = records[0]
            assert "month" in sample
            assert "capture_eur_mwh" in sample
            assert re.match(r"^\d{4}-\d{2}$", sample["month"])


# ---------------------------------------------------------------------------
# Task 1.7 — smoke test
# ---------------------------------------------------------------------------

def test_build_unified_data_no_errors_and_serializable():
    """build_unified_data() ska inte krascha och resultatet ska gå att
    serialisera till JSON med default=str (för date/datetime-objekt).
    """
    data = build_unified_data()
    serialized = json.dumps(data, default=str)
    assert len(serialized) > 1000, (
        f"Förväntade > 1000 tecken JSON, fick {len(serialized)}"
    )
