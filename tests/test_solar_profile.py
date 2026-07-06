"""Tester för solprofil-viktning — särskilt skottdags-fallback (29 feb)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris import entsoe_profile, solar_profile  # noqa: E402


# ---------------------------------------------------------------------------
# PVsyst — TMY har alltid 365 dagar, så (2, 29, h) saknas alltid
# ---------------------------------------------------------------------------

def test_pvsyst_weight_leap_day_falls_back_to_feb_28(monkeypatch):
    """PVsyst TMY saknar 29 feb; viktningen ska falla tillbaka på 28 feb
    istället för att returnera 0 och tappa hela skottdagens produktion."""
    fake_profile = {(2, 28, 12): 0.42}
    monkeypatch.setattr(solar_profile, "load_pvsyst_profile",
                        lambda name: fake_profile)

    ts = datetime(2024, 2, 29, 12)  # 2024 är skottår
    assert solar_profile.get_pvsyst_weight(ts, "whatever") == 0.42


def test_pvsyst_weight_normal_day_unchanged(monkeypatch):
    """Fallbacken får inte påverka vanliga dagar."""
    fake_profile = {(2, 28, 12): 0.42, (6, 1, 12): 0.9}
    monkeypatch.setattr(solar_profile, "load_pvsyst_profile",
                        lambda name: fake_profile)

    assert solar_profile.get_pvsyst_weight(datetime(2025, 6, 1, 12), "x") == 0.9


def test_pvsyst_weight_missing_non_leap_key_still_zero(monkeypatch):
    """En helt saknad nyckel som inte är 29 feb ska fortsatt ge 0.0."""
    monkeypatch.setattr(solar_profile, "load_pvsyst_profile",
                        lambda name: {(6, 1, 12): 0.9})

    assert solar_profile.get_pvsyst_weight(datetime(2025, 6, 1, 3), "x") == 0.0


# ---------------------------------------------------------------------------
# ENTSO-E — profilen KAN ha 29 feb (om datat täcker skottår); annars fallback
# ---------------------------------------------------------------------------

def test_entsoe_weight_leap_day_uses_own_value_when_present(monkeypatch):
    """Om ENTSO-E-profilen har 29 feb ska den egna vikten användas."""
    monkeypatch.setattr(entsoe_profile, "get_entsoe_profile",
                        lambda zone, gt: {(2, 29, 12): 0.03, (2, 28, 12): 0.02})

    assert entsoe_profile.get_entsoe_weight(
        datetime(2024, 2, 29, 12), "SE3", "solar") == 0.03


def test_entsoe_weight_leap_day_falls_back_when_absent(monkeypatch):
    """Om ENTSO-E-profilen saknar 29 feb ska den falla tillbaka på 28 feb."""
    monkeypatch.setattr(entsoe_profile, "get_entsoe_profile",
                        lambda zone, gt: {(2, 28, 12): 0.02})

    assert entsoe_profile.get_entsoe_weight(
        datetime(2024, 2, 29, 12), "SE3", "solar") == 0.02
