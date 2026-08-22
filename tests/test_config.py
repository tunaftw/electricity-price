"""Tester för elpris.config — delad ISO-parser (parse_iso).

datetime.fromisoformat('...Z') kastar ValueError på Python 3.9 (men inte 3.11).
parse_iso normaliserar 'Z' -> '+00:00' så Z-suffixad data (t.ex. eSett) parsas
konsekvent istället för att krascha eller tyst droppas.
"""

from __future__ import annotations

import sys
from datetime import timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.config import (  # noqa: E402
    PARK_CAPACITY_KWP,
    SWEDEN_TZ,
    local_year_month,
    parse_iso,
)
from elpris.park_config import (  # noqa: E402
    PARK_BUDGET_OVERRIDES,
    PARK_DEGRADATION_PCT_PER_YEAR,
    get_budget,
    list_parks,
)
from elpris.park_product_data import PARK_PRODUCT_DATA  # noqa: E402


def test_parse_iso_handles_z_suffix():
    ts = parse_iso("2024-01-01T00:00:00Z")
    assert ts.year == 2024 and ts.hour == 0
    assert ts.utcoffset() == timezone.utc.utcoffset(None)


def test_parse_iso_handles_explicit_offset():
    ts = parse_iso("2024-06-01T10:00:00+02:00")
    assert ts.hour == 10
    assert ts.utcoffset().total_seconds() == 2 * 3600


def test_parse_iso_handles_naive():
    ts = parse_iso("2024-01-01T00:00:00")
    assert ts.tzinfo is None
    assert ts.year == 2024


# ---------------------------------------------------------------------------
# local_year_month — bucketa månader på svensk lokaltid, inte UTC
# ---------------------------------------------------------------------------

def test_local_year_month_summer_boundary_rolls_to_next_month():
    """2026-03-31 22:30 UTC = 2026-04-01 00:30 CEST (UTC+2) -> april, inte mars."""
    ts = parse_iso("2026-03-31T22:30:00Z")
    assert local_year_month(ts) == (2026, 4)


def test_local_year_month_winter_boundary_rolls_to_next_month():
    """2026-01-31 23:30 UTC = 2026-02-01 00:30 CET (UTC+1) -> februari."""
    ts = parse_iso("2026-01-31T23:30:00Z")
    assert local_year_month(ts) == (2026, 2)


def test_local_year_month_midday_unchanged():
    ts = parse_iso("2026-06-15T10:00:00Z")
    assert local_year_month(ts) == (2026, 6)


# ---------------------------------------------------------------------------
# PARK_BUDGET_OVERRIDES — månadsbudget från PVsyst SRC Forecast-rapporterna
# ---------------------------------------------------------------------------

MONTH_KEYS = [f"2026-{m:02d}" for m in range(1, 13)]


def _override_parks():
    return sorted(PARK_BUDGET_OVERRIDES)


@pytest.mark.parametrize("park", _override_parks())
def test_override_has_all_twelve_months(park):
    """Varje park i overrides täcker hela året — annars faller enstaka
    månader tyst tillbaka på den generiska profilskalningen."""
    assert sorted(PARK_BUDGET_OVERRIDES[park]) == MONTH_KEYS


@pytest.mark.parametrize("park", _override_parks())
def test_override_months_have_positive_values(park):
    """Alla tre fälten ska finnas och energi/instrålning vara > 0."""
    for month_key, budget in PARK_BUDGET_OVERRIDES[park].items():
        assert set(budget) == {"energy_mwh", "irradiation_kwh_m2", "pr_pct"}, \
            f"{park} {month_key}: fel nycklar"
        assert budget["energy_mwh"] > 0, f"{park} {month_key}: energy_mwh <= 0"
        assert budget["irradiation_kwh_m2"] > 0, \
            f"{park} {month_key}: irradiation_kwh_m2 <= 0"
        assert 0 < budget["pr_pct"] <= 100, \
            f"{park} {month_key}: pr_pct {budget['pr_pct']} utanför (0, 100]"


@pytest.mark.parametrize("park", _override_parks())
def test_override_july_exceeds_january(park):
    """Grov säsongskontroll: juli ska ge mer än januari i samtliga parker.
    Fångar om en kolumn eller radordning kastats om vid extraktion."""
    jul = PARK_BUDGET_OVERRIDES[park]["2026-07"]["energy_mwh"]
    jan = PARK_BUDGET_OVERRIDES[park]["2026-01"]["energy_mwh"]
    assert jul > jan, f"{park}: juli {jul} MWh <= januari {jan} MWh"


@pytest.mark.parametrize("park", _override_parks())
def test_override_annual_sum_matches_expected_yield(park):
    """Σ av de tolv månaderna ska matcha parkens PVsyst-årsproduktion
    (expected_annual_yield_kwh_kwp × PARK_CAPACITY_KWP) inom ±5 %."""
    total_mwh = sum(
        b["energy_mwh"] for b in PARK_BUDGET_OVERRIDES[park].values()
    )
    capacity_kwp = PARK_CAPACITY_KWP[park]
    expected_mwh = (
        PARK_PRODUCT_DATA[park]["expected_annual_yield_kwh_kwp"]
        * capacity_kwp
        / 1000.0
    )
    deviation = abs(total_mwh - expected_mwh) / expected_mwh
    assert deviation <= 0.05, (
        f"{park}: Σmånader {total_mwh:.1f} MWh mot förväntat "
        f"{expected_mwh:.1f} MWh ({deviation * 100:.2f} % avvikelse)"
    )


@pytest.mark.parametrize("park", _override_parks())
def test_override_annual_pr_matches_park_pr(park):
    """PVsyst-identiteten PR_år = ΣE_Grid / (ΣGlobInc × kWp) ska reproducera
    parkens expected_pr_pct. Fångar förväxlade GlobInc/GlobEff-kolumner."""
    months = PARK_BUDGET_OVERRIDES[park].values()
    total_mwh = sum(b["energy_mwh"] for b in months)
    total_irr = sum(b["irradiation_kwh_m2"] for b in months)
    capacity_kwp = PARK_CAPACITY_KWP[park]

    pr_pct = total_mwh * 1000.0 / (total_irr * capacity_kwp) * 100.0
    expected_pr = PARK_PRODUCT_DATA[park]["expected_pr_pct"]
    assert abs(pr_pct - expected_pr) <= 0.5, (
        f"{park}: härledd års-PR {pr_pct:.2f} % mot förväntad "
        f"{expected_pr:.2f} %"
    )


@pytest.mark.parametrize("park", _override_parks())
def test_get_budget_returns_override(park):
    """get_budget ska plocka override:n, inte profil-fallbacken."""
    assert get_budget(park, 2026, 7) == PARK_BUDGET_OVERRIDES[park]["2026-07"]


def test_all_configured_parks_have_overrides():
    """Alla åtta parker är täckta — ingen ligger kvar på fallbacken."""
    assert set(PARK_BUDGET_OVERRIDES) == set(list_parks())


def test_degradation_constant_is_sane():
    assert 0.0 < PARK_DEGRADATION_PCT_PER_YEAR < 2.0
