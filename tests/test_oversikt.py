"""Tester för Översikt (elpris/oversikt/).

Fokus på reglerna som bär sidans siffror: budgetjämförelse vid saknad data,
capture-kvot mot rätt prisperiod, portföljaggregat, batteri-DP, ENTSO-E-
luckfyllnad och terminsjämförelser på-eller-före.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.config import SWEDEN_TZ  # noqa: E402
from elpris.oversikt import batteri, common, portfolj, terminer  # noqa: E402
from elpris.oversikt.render import render_oversikt  # noqa: E402
from elpris.solar_geometry import solar_elevation_deg  # noqa: E402

COORDS = (58.85, 14.20)
UTC = timezone.utc


# ---------------------------------------------------------------------------
# Portföljen
# ---------------------------------------------------------------------------

def _june_quarters():
    start = datetime(2026, 6, 1, tzinfo=SWEDEN_TZ).astimezone(UTC)
    end = datetime(2026, 7, 1, tzinfo=SWEDEN_TZ).astimezone(UTC)
    t = start
    while t < end:
        yield t
        t += timedelta(minutes=15)


def _clear_sky_mw(t):
    elev = solar_elevation_deg(t + timedelta(minutes=7, seconds=30), *COORDS)
    return max(0.0, math.sin(math.radians(elev))) if elev > 5 else 0.0


@pytest.fixture
def synthetic_park(monkeypatch):
    """En park vars produktion exakt följer budgetens fördelningsvikt."""
    budget_total = sum(_clear_sky_mw(t) * 0.25 for t in _june_quarters())
    prices = {}
    for t in _june_quarters():
        day = t.astimezone(SWEDEN_TZ).day
        prices[int(t.timestamp())] = 50.0 if day <= 15 else 100.0

    def setup(drop_days=(), scale=1.0):
        recs = []
        for t in _june_quarters():
            day = t.astimezone(SWEDEN_TZ).day
            if day in drop_days:
                continue
            recs.append({"timestamp_utc": t, "energy_source": "meter",
                         "effective_power_mw": _clear_sky_mw(t) * scale})
        monkeypatch.setattr(portfolj, "park_records", lambda p: tuple(recs))
        monkeypatch.setattr(portfolj, "quarter_prices", lambda z: prices)
        monkeypatch.setattr(portfolj, "get_budget", lambda p, y, m: {"energy_mwh": budget_total})
        monkeypatch.setattr(portfolj, "PARK_ZONES", {"testpark": "SE3"})
        monkeypatch.setattr(portfolj, "PARK_COORDS", {"testpark": COORDS})
        monkeypatch.setattr(portfolj, "PARK_CAPACITY_KWP", {"testpark": 1000})
        monkeypatch.setattr(portfolj, "PARK_METADATA", {"testpark": {"display_name": "Test"}})
        monkeypatch.setattr(portfolj, "FIRST_MONTH", "2026-06")
        data_end = int(datetime(2026, 7, 1, tzinfo=SWEDEN_TZ).timestamp())
        return portfolj.build_park("testpark", data_end)["months"]["2026-06"]

    return setup


def test_complete_month_on_budget(synthetic_park):
    m = synthetic_park()
    assert m["coverage"] == pytest.approx(1.0)
    assert m["vs_budget"] == pytest.approx(0.0, abs=1e-3)


def test_missing_days_do_not_count_as_underperformance(synthetic_park):
    # Fem dygn saknas: rå jämförelse vore ≈ −17 %, men budgeten för tid med
    # data ska ge ≈ 0 eftersom parken presterade exakt enligt budget.
    m = synthetic_park(drop_days=(10, 11, 12, 13, 14))
    assert 0.8 < m["coverage"] < 0.86
    assert m["vs_budget"] == pytest.approx(0.0, abs=5e-3)


def test_real_underperformance_is_visible(synthetic_park):
    m = synthetic_park(scale=0.9)
    assert m["vs_budget"] == pytest.approx(-0.10, abs=1e-3)


def test_low_coverage_gives_no_budget_comparison(synthetic_park):
    m = synthetic_park(drop_days=tuple(range(1, 11)))
    assert m["coverage"] < portfolj.MIN_COVERAGE_FOR_BUDGET
    assert m["vs_budget"] is None


def test_capture_ratio_uses_prices_of_observed_days(synthetic_park):
    # Bara första halvan (pris 50) har data. Kvoten ska jämföra mot 50, inte
    # mot månadens snitt 75 — annars ser parken ut att ha 67 % capture.
    m = synthetic_park(drop_days=tuple(range(16, 31)))
    assert m["capture_eur"] == pytest.approx(50.0)
    assert m["baseload_eur"] == pytest.approx(50.0)
    assert m["capture_ratio"] == pytest.approx(1.0)


def test_aggregate_excludes_low_coverage_parks_from_budget_only():
    ok = {"energy_mwh": 100.0, "budget_obs_mwh": 100.0, "budget_period_mwh": 100.0,
          "vs_budget": 0.0, "value_eur": 5000.0, "baseload_eur": 50.0, "neg_share": 0.0}
    bad = {"energy_mwh": 20.0, "budget_obs_mwh": 30.0, "budget_period_mwh": 100.0,
           "vs_budget": None, "value_eur": 1000.0, "baseload_eur": 50.0, "neg_share": 0.0}
    a = portfolj.aggregate([("horby", "SE4", 1000, ok), ("fjallskar", "SE3", 1000, bad)])
    assert a["energy_mwh"] == 120.0              # produktionen räknas
    assert a["vs_budget"] == pytest.approx(0.0)  # men inte i budgetjämförelsen
    assert a["parks_excluded"] == ["fjallskar"]
    assert a["coverage"] == pytest.approx(130 / 200)
    assert a["capture_eur"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Batteri
# ---------------------------------------------------------------------------

def test_one_cycle_buys_low_sells_high():
    # Ladda två billiga timmar, sälj två dyra: (50 + 50) × 0,88 − 0 = 88.
    assert batteri.best_one_cycle([10, 0, 0, 50, 50, 10], 1.0, 2) == pytest.approx(88.0)


def test_one_cycle_cannot_sell_before_buying():
    # Fallande priser: ingen lönsam ordning finns.
    assert batteri.best_one_cycle([100, 80, 60, 40, 20], 1.0, 2) == 0.0


def test_one_cycle_limits_to_one_charge():
    # Två dalar och två toppar: bara en laddning (2 block) tillåts.
    prices = [0, 100, 0, 100]
    assert batteri.best_one_cycle(prices, 1.0, 2) == pytest.approx(2 * 100 * 0.88 - 0)
    # Med ett block per laddning blir det ändå max 2 block totalt.
    assert batteri.best_one_cycle([0, 0, 100, 0, 100], 1.0, 2) == pytest.approx(176.0)


# ---------------------------------------------------------------------------
# ENTSO-E-sol
# ---------------------------------------------------------------------------

def test_solar_gap_fill_rules(tmp_path, monkeypatch):
    zone_dir = tmp_path / "XX"
    zone_dir.mkdir()
    rows = [
        # natt: 0 kl 20, nästa punkt kl 04 (8 h lucka) → fylls med 0
        ("2025-06-01T20:00:00+00:00", 0.0),
        ("2025-06-02T04:00:00+00:00", 100.0),
        # hög punkt följd av 5 h lucka → avbrott, fylls bara en timme
        ("2025-06-02T05:00:00+00:00", 900.0),
        ("2025-06-02T10:00:00+00:00", 800.0),
    ]
    (zone_dir / "solar_2025.csv").write_text(
        "time_start,zone,psr_type,generation_mw,resolution_minutes\n" +
        "".join(f"{t},XX,solar,{v},60\n" for t, v in rows))
    monkeypatch.setattr(common, "ENTSOE_GEN_DIR", tmp_path)
    common.solar_quarters.cache_clear()
    try:
        q = common.solar_quarters("XX")
    finally:
        common.solar_quarters.cache_clear()
    ts = lambda s: int(datetime.fromisoformat(s).timestamp())  # noqa: E731
    assert q[ts("2025-06-02T02:00:00+00:00")] == 0.0           # nattlucka fylld
    assert q[ts("2025-06-02T05:45:00+00:00")] == 900.0         # första timmen
    assert ts("2025-06-02T07:00:00+00:00") not in q            # avbrottet ofyllt
    assert q[ts("2025-06-02T10:15:00+00:00")] == 800.0


# ---------------------------------------------------------------------------
# Terminer
# ---------------------------------------------------------------------------

def test_on_or_before_never_looks_ahead():
    series = [("2026-04-29", 40.0), ("2026-07-05", 50.0), ("2026-09-22", 60.0)]
    assert terminer._on_or_before(series, "2026-06-23") == ("2026-04-29", 40.0)
    assert terminer._on_or_before(series, "2026-04-01") is None


def test_terminer_table_marks_stale_references(monkeypatch):
    fwd = {
        "zones": {
            "SE3": {"YR-27": [("2026-04-29", 41.8, 46.5, -4.7), ("2026-09-15", 62.4, 67.1, -4.7),
                              ("2026-09-22", 60.0, 64.7, -4.7)]},
            "SE4": {"YR-27": [("2026-09-22", 78.4, 64.7, 13.7)]},
        },
        "contracts": {"YR-27": {"kind": "YR", "delivery_start": "2027-01-01", "delivery_end": "2027-12-31"}},
    }
    monkeypatch.setattr(terminer, "load_zonal_forward_history", lambda zones: fwd)
    monkeypatch.setattr(terminer, "_read_settlements", lambda path: {"YR-27": {"2026-09-22": 64.7}})
    data_end = int(datetime(2026, 9, 22, tzinfo=SWEDEN_TZ).timestamp())
    d = terminer.build_terminer_data(data_end)
    row = d["table"]["SE3"]["YR-27"]
    assert row["value"] == 60.0
    assert row["changes"]["1v"]["delta"] == pytest.approx(-2.4)
    three = row["changes"]["3m"]           # mål 2026-06-23 → 04-29, 55 dagar före
    assert three["ref_date"] == "2026-04-29" and three["stale"] is True
    assert d["table"]["SE4"]["YR-27"]["changes"]["1v"] is None
    assert d["gaps"] and d["gaps"][0]["from"] == "2026-04-30"
    assert d["default_contract"] == "YR-27"


# ---------------------------------------------------------------------------
# Renderaren
# ---------------------------------------------------------------------------

def test_render_embeds_data_and_escapes_script_end():
    data = {"generated": "2026-09-22 22:00", "dataset": "</script><b>x", "portfolj": {}, "marknad": {},
            "terminer": None, "batteri": {}, "datastatus": {}, "definitions": []}
    html = render_oversikt(data)
    assert html.startswith("<!DOCTYPE html>")
    assert "<\\/script><b>x" in html          # kan inte avsluta script-blocket
    assert 'lang="sv"' in html and "Portföljen" in html


def test_page_javascript_parses(tmp_path):
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node saknas")
    from elpris.oversikt.render import JS
    path = tmp_path / "page.js"
    path.write_text("const D = {};\n" + JS, encoding="utf-8")
    subprocess.run([node, "--check", str(path)], check=True)


def test_calendar_outside_precomputed_range():
    cal = common.LocalCalendar(2021, 2022)
    for stamp, day in [("2020-12-31T12:00", "2020-12-31"), ("2023-01-01T00:30", "2023-01-01"),
                       ("2028-06-01T12:00", "2028-06-01")]:
        epoch = int(datetime.fromisoformat(stamp).replace(tzinfo=SWEDEN_TZ).timestamp())
        assert cal.day(epoch) == day


def test_render_inlines_plotly_when_vendored():
    # Förhandsvisningar och mejlklienter blockerar externa skript: Plotly ska
    # bäddas in så att sidan fungerar utan nätåtkomst.
    from elpris.oversikt import render
    if not render.PLOTLY_VENDOR.exists():
        pytest.skip("vendor/plotly.min.js saknas")
    html = render_oversikt({"generated": "", "dataset": "", "portfolj": {}, "marknad": {},
                            "terminer": None, "batteri": {}, "datastatus": {}, "definitions": []})
    assert "cdn.plot.ly" not in html
    assert "plotly.js v" in html
