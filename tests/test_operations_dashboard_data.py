"""Tester för operations_dashboard_data — lokal månadsbokföring (A10).

Negativpris-exponering och specific yield ska bucketas på svensk lokal månad,
inte UTC — annars läcker de första lokala timmarna av en månad till fel
rapportmånad.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris import operations_dashboard_data as ops  # noqa: E402
from elpris.config import parse_iso  # noqa: E402


def _patch_single_park(monkeypatch, park_rec, spot_recs):
    monkeypatch.setattr(ops, "PARK_CAPACITY_KWP", {"testpark": 1000})
    monkeypatch.setattr(ops, "PARK_ZONES", {"testpark": "SE3"})
    monkeypatch.setattr(ops, "load_park_15min", lambda pk: park_rec)
    monkeypatch.setattr(ops, "load_spot_prices_15min", lambda z: spot_recs)


def test_negative_price_boundary_hour_buckets_to_local_month(monkeypatch):
    # 2026-03-31 22:30 UTC = 2026-04-01 00:30 CEST -> ska bokföras som april
    ts = parse_iso("2026-03-31T22:30:00Z")
    park_rec = [{"timestamp_utc": ts, "effective_power_mw": 2.0}]
    spot_recs = {"2026-03-31": [{"timestamp_utc": ts, "eur_mwh": -5.0}]}
    _patch_single_park(monkeypatch, park_rec, spot_recs)

    result = ops.calculate_negative_price_exposure()["testpark"]

    assert len(result) == 1
    assert (result[0]["year"], result[0]["month"]) == (2026, 4)
    assert result[0]["neg_hours"] == 0.25


def test_specific_yield_boundary_hour_buckets_to_local_month(monkeypatch):
    ts = parse_iso("2026-01-31T23:30:00Z")  # = 2026-02-01 00:30 CET -> februari
    park_rec = [{"timestamp_utc": ts, "effective_power_mw": 4.0}]
    _patch_single_park(monkeypatch, park_rec, {})

    result = ops.calculate_specific_yield()["testpark"]

    assert len(result) == 1
    assert (result[0]["year"], result[0]["month"]) == (2026, 2)
