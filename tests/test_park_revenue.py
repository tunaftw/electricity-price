"""Tester för elpris.park_revenue — realiserad capture & revenue per park."""

from elpris.park_revenue import calculate_park_revenue_capture


def test_calculate_returns_dict_with_parks():
    result = calculate_park_revenue_capture()
    # Minst en park ska ha resultat (Hörby är längst i drift)
    assert isinstance(result, dict)
    assert "horby" in result
    assert len(result["horby"]) > 0


def test_records_have_required_fields():
    result = calculate_park_revenue_capture()
    required = {
        "year", "month", "volume_mwh", "revenue_eur",
        "capture_eur_mwh", "baseload_eur_mwh", "capture_premium_pct",
    }
    for park, records in result.items():
        for rec in records:
            assert required.issubset(rec.keys()), (
                f"missing fields in {park}: {required - set(rec.keys())}"
            )


def test_capture_consistent_with_revenue_volume():
    """capture_eur_mwh = revenue_eur / volume_mwh (med round-2-tolerans)."""
    result = calculate_park_revenue_capture()
    for park, records in result.items():
        for rec in records:
            if rec["volume_mwh"] > 0 and rec["capture_eur_mwh"] is not None:
                expected = rec["revenue_eur"] / rec["volume_mwh"]
                assert abs(rec["capture_eur_mwh"] - expected) < 0.5, (
                    f"{park} {rec['year']}-{rec['month']}: "
                    f"capture {rec['capture_eur_mwh']} != "
                    f"revenue/volume {expected}"
                )


def test_records_sorted_chronologically():
    result = calculate_park_revenue_capture()
    for park, records in result.items():
        keys = [(r["year"], r["month"]) for r in records]
        assert keys == sorted(keys), f"{park} not sorted"


def test_premium_computed_when_baseload_nonzero():
    result = calculate_park_revenue_capture()
    for park, records in result.items():
        for rec in records:
            if (rec["capture_eur_mwh"] is not None
                    and rec["baseload_eur_mwh"]
                    and rec["baseload_eur_mwh"] != 0):
                expected_prem = (
                    (rec["capture_eur_mwh"] / rec["baseload_eur_mwh"] - 1.0) * 100.0
                )
                assert rec["capture_premium_pct"] is not None
                assert abs(rec["capture_premium_pct"] - expected_prem) < 0.1
