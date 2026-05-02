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
