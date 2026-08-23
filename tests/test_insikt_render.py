"""Tester för Insikt-renderarens datalogik (marknad + sektionsregister).

Fokus: det som är regressionskänsligt i marknadssektionen —
konvergensseriernas decimering, lookback-fönsterurvalet och den
volymviktade fleet-intäktsserien.
"""

from datetime import date, timedelta

from elpris.insikt.marknad import (
    _shift_months,
    build_fleet_revenue_series,
    build_lookback_rows,
    decimate_series,
    lookback_value,
)
from elpris.insikt.render import SECTIONS, render_insikt


# ---------------------------------------------------------------------------
# decimate_series
# ---------------------------------------------------------------------------

def _daily_series(start: str, end: str) -> list:
    d = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    out = []
    price = 40.0
    while d <= stop:
        if d.weekday() < 5:  # handelsdagar
            out.append({"date": d.isoformat(), "price": price})
            price += 0.01
        d += timedelta(days=1)
    return out


class TestDecimateSeries:
    def test_daily_kept_within_window(self):
        series = _daily_series("2025-06-02", "2026-03-31")
        out = decimate_series(series, "2026-04-01")
        # Hela serien ligger inom 365 dagar före leveransstart → orörd.
        assert out == series

    def test_weekly_before_window(self):
        series = _daily_series("2024-01-01", "2026-03-31")
        out = decimate_series(series, "2026-04-01")
        cutoff = "2025-04-01"
        recent = [r for r in out if r["date"] >= cutoff]
        recent_src = [r for r in series if r["date"] >= cutoff]
        # Dagligt efter cutoff.
        assert recent == recent_src
        # Veckovis före cutoff: max en punkt per ISO-vecka.
        old = [r for r in out if r["date"] < cutoff]
        weeks = [
            date.fromisoformat(r["date"]).isocalendar()[:2] for r in old
        ]
        assert len(weeks) == len(set(weeks))
        # Rejäl decimering: ~1/5 av handelsdagarna.
        old_src = [r for r in series if r["date"] < cutoff]
        assert len(old) < 0.3 * len(old_src)

    def test_last_point_always_kept(self):
        series = _daily_series("2020-01-01", "2020-06-30")
        out = decimate_series(series, "2026-04-01")
        assert out[-1] == series[-1]

    def test_empty(self):
        assert decimate_series([], "2026-04-01") == []

    def test_order_preserved_no_duplicates(self):
        series = _daily_series("2023-01-01", "2026-03-31")
        out = decimate_series(series, "2026-04-01")
        dates = [r["date"] for r in out]
        assert dates == sorted(dates)
        assert len(dates) == len(set(dates))


# ---------------------------------------------------------------------------
# lookback_value + _shift_months
# ---------------------------------------------------------------------------

class TestShiftMonths:
    def test_simple(self):
        assert _shift_months(date(2026, 4, 1), 3) == date(2026, 1, 1)

    def test_year_wrap(self):
        assert _shift_months(date(2026, 4, 1), 12) == date(2025, 4, 1)
        assert _shift_months(date(2026, 1, 1), 6) == date(2025, 7, 1)

    def test_day_clamp(self):
        # 31 mars − 1 mån → 28 feb (ej skottår 2026).
        assert _shift_months(date(2026, 3, 31), 1) == date(2026, 2, 28)
        assert _shift_months(date(2024, 3, 31), 1) == date(2024, 2, 29)


class TestLookbackValue:
    def test_exact_hit(self):
        implied = {"2026-01-01": 55.0, "2026-01-05": 60.0}
        assert lookback_value(implied, "2026-04-01", 3) == 55.0

    def test_nearest_within_tolerance(self):
        implied = {"2026-01-05": 60.0, "2026-01-20": 70.0}
        assert lookback_value(implied, "2026-04-01", 3) == 60.0

    def test_none_outside_tolerance(self):
        implied = {"2026-01-09": 60.0}  # 8 dagar från 1 jan
        assert lookback_value(implied, "2026-04-01", 3) is None

    def test_tie_prefers_earlier_date(self):
        implied = {"2025-12-30": 50.0, "2026-01-03": 51.0}  # båda 2 dagar
        assert lookback_value(implied, "2026-04-01", 3) == 50.0

    def test_empty(self):
        assert lookback_value({}, "2026-04-01", 3) is None


# ---------------------------------------------------------------------------
# build_lookback_rows
# ---------------------------------------------------------------------------

def _history_fixture() -> dict:
    sys_series = [
        {"date": "2025-12-30", "price": 40.0},
        {"date": "2026-03-02", "price": 45.0},
        {"date": "2026-03-27", "price": 47.0},
    ]
    epad = [
        {"date": "2025-12-30", "price": 10.0},
        {"date": "2026-03-02", "price": 12.0},
        {"date": "2026-03-27", "price": 13.0},
    ]
    return {
        "Q2-26": {
            "type": "quarter",
            "delivery_start": "2026-04-01",
            "delivery_end": "2026-06-30",
            "final_settlement_date": "2026-03-27",
            "is_clean_final": True,
            "sys_series": sys_series,
            "epad_series": {"SE4": epad},
            "realised_spot": {"SE4": 70.0},
        }
    }


class TestBuildLookbackRows:
    def test_row_values(self):
        rows = build_lookback_rows(
            _history_fixture(), today=date(2026, 8, 23)
        )
        assert len(rows) == 1
        r = rows[0]
        assert r["contract"] == "Q2-26"
        assert r["zone"] == "SE4"
        assert r["delivered"] is True
        assert r["t3"] == 50.0       # 2025-12-30: 40 + 10
        assert r["t1"] == 57.0       # 2026-03-02: 45 + 12 (närmast 1 mars)
        assert r["t12"] is None      # ingen data 12 mån före
        assert r["final"] == 60.0    # 47 + 13
        assert r["error"] == -10.0   # 60 − 70
        assert r["error_pct"] == -14.3

    def test_pending_contract_flag(self):
        rows = build_lookback_rows(
            _history_fixture(), today=date(2026, 5, 1)
        )
        assert rows[0]["delivered"] is False

    def test_zone_without_epad_skipped(self):
        hist = _history_fixture()
        rows = build_lookback_rows(hist, today=date(2026, 8, 23))
        zones = {r["zone"] for r in rows}
        assert zones == {"SE4"}


# ---------------------------------------------------------------------------
# build_fleet_revenue_series
# ---------------------------------------------------------------------------

class TestFleetRevenueSeries:
    def test_volume_weighted(self):
        parks = {
            "a": {"months": [{
                "year": 2026, "month": 6, "is_partial": False,
                "revenue_eur": 1000.0, "revenue_eur_ppa": 1200.0,
                "bazefield_volume_mwh": 20.0, "baseload_eur_mwh": 60.0,
            }]},
            "b": {"months": [{
                "year": 2026, "month": 6, "is_partial": False,
                "revenue_eur": 3000.0, "revenue_eur_ppa": None,
                "bazefield_volume_mwh": 40.0, "baseload_eur_mwh": 90.0,
            }]},
        }
        out = build_fleet_revenue_series(parks)
        assert len(out) == 1
        m = out[0]
        assert m["month"] == "2026-06"
        assert m["capture"] == round(4000.0 / 60.0, 2)
        # PPA: park b saknar PPA → spot-revenue som fallback.
        assert m["capture_ppa"] == round((1200.0 + 3000.0) / 60.0, 2)
        # Baseload volymviktad: (60*20 + 90*40) / 60 = 80.
        assert m["baseload"] == 80.0
        assert m["is_partial"] is False

    def test_months_without_revenue_skipped(self):
        parks = {"a": {"months": [{
            "year": 2026, "month": 6, "is_partial": False,
            "revenue_eur": None, "bazefield_volume_mwh": 20.0,
        }]}}
        assert build_fleet_revenue_series(parks) == []


# ---------------------------------------------------------------------------
# Sektionsregistret + skalet
# ---------------------------------------------------------------------------

class TestRenderSections:
    def test_registry_has_three_sections(self):
        ids = [sid for sid, _, _ in SECTIONS]
        assert ids == ["parker", "marknad", "bess"]

    def test_render_includes_all_sections_and_nav(self):
        html = render_insikt({"generated": "2026-08-23", "parks": {}})
        for sid in ("parker", "marknad", "bess"):
            assert f'<section id="{sid}">' in html
            assert f'data-sec="{sid}"' in html
        # Lazy-render-krokar för marknads-/BESS-blocken.
        for hook in ("intakt", "obalans", "kanni", "forward",
                     "bessStack", "bessAcc", "bessKalkyl", "bessBtm"):
            assert f'data-render="{hook}"' in html
