"""Tester för den strikta energiregeln i load_park_15min.

Fallen är tagna ur verklig parkdata (sep 2026): inverter som står kvar på
dagens sista värde genom natten (Hova, Fjällskär), död mätare ersatt av en
fastfrusen inverter (Fjällskär 7,69 MW) och mätare som fryser (Agerum).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris import operations_dashboard_data as ops  # noqa: E402
from elpris.solar_geometry import solar_elevation_deg  # noqa: E402

UTC = timezone.utc
# Hova-koordinater — ger realistisk solhöjd i testerna.
COORDS = (58.85, 14.20)


def _write_park(tmp_path, monkeypatch, rows):
    """rows: list of (utc datetime, meter, inverter) — None = tom cell."""
    monkeypatch.setattr(ops, "PARKS_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(ops, "PARK_ZONES", {"testpark": "SE3"})
    monkeypatch.setattr(ops, "PARK_CAPACITY_KWP", {"testpark": 20000})
    monkeypatch.setattr(ops, "PARK_COORDS", {"testpark": COORDS})
    lines = ["timestamp,power_mw,active_power_mw,irradiance_poa,availability"]
    for ts, meter, inverter in rows:
        stamp = ts.astimezone(timezone(timedelta(hours=2))).strftime(
            "%Y-%m-%dT%H:%M:%S.0000000+02:00")
        m = "" if meter is None else str(meter)
        i = "" if inverter is None else str(inverter)
        lines.append(f"{stamp},{m},{i},,")
    (tmp_path / "testpark_SE3.csv").write_text("\n".join(lines) + "\n")
    return ops.load_park_15min("testpark")


def _quarters(start, n):
    return [start + timedelta(minutes=15 * k) for k in range(n)]


NOON = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)      # 12:00 CEST, sol högt
MIDNIGHT = datetime(2026, 7, 15, 23, 0, tzinfo=UTC)  # 01:00 CEST, sol under horisonten


def test_solar_elevation_is_sane():
    assert solar_elevation_deg(NOON, *COORDS) > 45
    assert solar_elevation_deg(MIDNIGHT, *COORDS) < -3
    # Vintersolstånd mitt på dagen i Mellansverige: låg men positiv sol.
    winter_noon = datetime(2025, 12, 21, 11, 0, tzinfo=UTC)
    assert 0 < solar_elevation_deg(winter_noon, *COORDS) < 10


def test_night_inverter_value_is_not_production(tmp_path, monkeypatch):
    # Hova juli 2026: invertern står kvar på kvällens värde hela natten.
    rows = [(ts, None, 3.21 + 0.01 * k) for k, ts in enumerate(_quarters(MIDNIGHT, 4))]
    recs = _write_park(tmp_path, monkeypatch, rows)
    assert {r["energy_source"] for r in recs} == {"night"}
    assert sum(r["effective_power_mw"] for r in recs) == 0


def test_frozen_inverter_with_dead_meter_is_missing(tmp_path, monkeypatch):
    # Fjällskär sep 2026: mätaren död, invertern 7,69 MW i varje kvart, dag
    # som natt. 12:00 → 03:00 CEST nästa dygn.
    rows = [(ts, None, 7.69) for ts in _quarters(NOON, 60)]
    recs = _write_park(tmp_path, monkeypatch, rows)
    assert {r["energy_source"] for r in recs} <= {"missing", "night"}
    assert all(r["effective_power_mw"] == 0 for r in recs)
    day = [r for r in recs if r["sun_elevation_deg"] > 0]
    assert day and all(r.get("_stuck_value") for r in day)
    assert not any(r.get("_stuck_value") for r in recs if r["sun_elevation_deg"] < -3)


def test_live_inverter_fills_missing_meter(tmp_path, monkeypatch):
    rows = [(ts, None, 5.0 + 0.1 * k) for k, ts in enumerate(_quarters(NOON, 4))]
    recs = _write_park(tmp_path, monkeypatch, rows)
    assert {r["energy_source"] for r in recs} == {"inverter"}
    assert recs[0]["effective_power_mw"] == pytest.approx(5.0)


def test_short_repeat_is_not_frozen(tmp_path, monkeypatch):
    # Sju identiska kvartar (< 2 h) räknas som verklig produktion.
    rows = [(ts, None, 6.0) for ts in _quarters(NOON, ops.FROZEN_RUN_QUARTERS - 1)]
    recs = _write_park(tmp_path, monkeypatch, rows)
    assert {r["energy_source"] for r in recs} == {"inverter"}


def test_meter_wins_and_negative_meter_is_zero(tmp_path, monkeypatch):
    rows = [(NOON, 4.0, 9.0), (NOON + timedelta(minutes=15), -0.02, 9.1)]
    recs = _write_park(tmp_path, monkeypatch, rows)
    assert [r["energy_source"] for r in recs] == ["meter", "meter"]
    assert [r["effective_power_mw"] for r in recs] == [4.0, 0.0]


def test_frozen_meter_falls_back_to_live_inverter(tmp_path, monkeypatch):
    # Agerum jul 2025: mätaren stod på 1,7905 MW i fyra dygn.
    rows = [(ts, 1.7905, 5.0 + 0.01 * k) for k, ts in enumerate(_quarters(NOON, 60))]
    recs = _write_park(tmp_path, monkeypatch, rows)
    day = [r for r in recs if r["sun_elevation_deg"] > 0]
    assert {r["energy_source"] for r in day} == {"inverter"}
    assert all(r["power_mw"] == 0 for r in recs)


def test_inverter_zero_in_daylight_without_meter_is_unknown(tmp_path, monkeypatch):
    recs = _write_park(tmp_path, monkeypatch, [(NOON, None, 0.0)])
    assert recs[0]["energy_source"] == "missing"


def test_unsorted_and_duplicate_rows(tmp_path, monkeypatch):
    t0, t1 = NOON, NOON + timedelta(minutes=15)
    rows = [(t1, 2.0, None), (t0, 1.0, None), (t1, 3.0, None)]
    recs = _write_park(tmp_path, monkeypatch, rows)
    assert [r["timestamp_utc"] for r in recs] == [t0, t1]
    assert recs[1]["effective_power_mw"] == 3.0  # sista raden vinner


def test_daylight_coverage_weights_missing_noon(tmp_path, monkeypatch):
    day = datetime(2026, 7, 14, 22, 0, tzinfo=UTC)  # 00:00 CEST
    quarters = _quarters(day, 96)
    full = _write_park(tmp_path, monkeypatch,
                       [(ts, 1.0 + (k % 3) * 0.1, None) for k, ts in enumerate(quarters)])
    assert ops.daylight_coverage("testpark", full, day, day + timedelta(days=1)) == pytest.approx(1.0)

    # Tappa 10:00–14:00 lokal tid: mer än 4/17 av dagsljusvikten försvinner.
    gap = [(ts, None if 8 <= ts.hour < 12 else 1.0 + (k % 3) * 0.1, None)
           for k, ts in enumerate(quarters)]
    recs = _write_park(tmp_path, monkeypatch, gap)
    cov = ops.daylight_coverage("testpark", recs, day, day + timedelta(days=1))
    assert 0.55 < cov < 0.75


def test_daytime_export_limit_plateau_is_real_production(tmp_path, monkeypatch):
    # Tången 2026-06-23: mätaren saknas, invertern står på exportgränsen
    # 4,528 MW i 3 h mitt på dagen medan instrålningen stiger. Det är verklig
    # produktion, inte en frusen signal.
    rows = [(ts, None, 4.528) for ts in _quarters(NOON - timedelta(hours=1), 12)]
    recs = _write_park(tmp_path, monkeypatch, rows)
    assert {r["energy_source"] for r in recs} == {"inverter"}
    assert sum(r["effective_power_mw"] for r in recs) == pytest.approx(12 * 4.528)


def test_long_daytime_freeze_is_missing(tmp_path, monkeypatch):
    # Samma värde i ≥ 6 h i dagsljus räknas som fryst även utan natt.
    start = datetime(2026, 7, 15, 5, 0, tzinfo=UTC)  # 07–13 CEST, sol uppe
    rows = [(ts, None, 3.33) for ts in _quarters(start, ops.FROZEN_DAYTIME_RUN_QUARTERS)]
    recs = _write_park(tmp_path, monkeypatch, rows)
    assert {r["energy_source"] for r in recs} == {"missing"}


def test_frozen_value_into_night_is_missing(tmp_path, monkeypatch):
    # Hova: invertern håller kvällens värde (> 0) in i natten.
    evening = datetime(2026, 7, 15, 18, 0, tzinfo=UTC)  # 20:00 CEST → natt
    rows = [(ts, None, 1.25) for ts in _quarters(evening, 16)]
    recs = _write_park(tmp_path, monkeypatch, rows)
    assert all(r["effective_power_mw"] == 0 for r in recs)
    assert "inverter" not in {r["energy_source"] for r in recs}


def test_large_negative_meter_is_not_zero_production(tmp_path, monkeypatch):
    # Hörby 2026-07-22: mätaren visar −8 MW mitt på dagen (teckenfel/skräp).
    # Det ska falla tillbaka på invertern, inte bli "produktion 0".
    rows = [(NOON, -8.0, 6.1), (NOON + timedelta(minutes=15), -0.05, 6.2)]
    recs = _write_park(tmp_path, monkeypatch, rows)
    assert recs[0]["energy_source"] == "inverter"
    assert recs[0]["effective_power_mw"] == pytest.approx(6.1)
    assert recs[1]["energy_source"] == "meter"      # liten egenförbrukning är giltig
    assert recs[1]["effective_power_mw"] == 0.0


def test_loader_returns_independent_copies(tmp_path, monkeypatch):
    recs = _write_park(tmp_path, monkeypatch, [(NOON, 4.0, None)])
    recs[0]["effective_power_mw"] = 999
    again = ops.load_park_15min("testpark")
    assert again[0]["effective_power_mw"] == 4.0
