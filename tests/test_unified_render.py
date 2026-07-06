"""Tester för unified-renderarens payload-beskärning (D1b).

Endast CAPTURE-fliken ritar profil-``daily``, och bara för nycklarna i
``CAPTURE_PROFILE_GROUPS``. Övriga profilers ``daily`` ska strippas ur den
inbäddade payloaden (≈13 MB dödvikt) utan att röra monthly/yearly/hourly.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.unified_dashboard_v3_html import _prune_unused_daily  # noqa: E402


def _zone_data():
    return {
        "SE3": {
            "baseload": {"daily": [1, 2], "monthly": [3], "yearly": [4]},
            "sol_syd": {"daily": [1], "monthly": [2]},
            "arb_1h": {"daily": [9, 9, 9], "monthly": [1], "yearly": [2]},
            "anc_fcr_n": {"daily": [7], "monthly": [8]},
            "park_horby_SE4": {"daily": [5], "monthly": [6]},
        }
    }


def test_prune_keeps_daily_for_whitelisted_profiles():
    out = _prune_unused_daily(_zone_data())
    assert out["SE3"]["baseload"]["daily"] == [1, 2]
    assert out["SE3"]["sol_syd"]["daily"] == [1]


def test_prune_drops_daily_for_non_whitelisted_profiles():
    out = _prune_unused_daily(_zone_data())
    assert "daily" not in out["SE3"]["arb_1h"]
    assert "daily" not in out["SE3"]["anc_fcr_n"]
    assert "daily" not in out["SE3"]["park_horby_SE4"]


def test_prune_preserves_monthly_and_yearly():
    out = _prune_unused_daily(_zone_data())
    assert out["SE3"]["arb_1h"]["monthly"] == [1]
    assert out["SE3"]["arb_1h"]["yearly"] == [2]
    assert out["SE3"]["anc_fcr_n"]["monthly"] == [8]


def test_prune_does_not_mutate_input():
    data = _zone_data()
    _prune_unused_daily(data)
    # Originalet ska vara orört (funktionen bygger nya dictar)
    assert "daily" in data["SE3"]["arb_1h"]
