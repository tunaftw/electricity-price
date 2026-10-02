from datetime import date, datetime, timezone

from elpris.datastatus import kontrollera, tacker_dagen

DAG = date(2026, 10, 1)


def test_aware_timestamps_are_read_in_stockholm_time():
    # 21:45 UTC is 23:45 CEST: the last quarter of the day.
    assert tacker_dagen(datetime(2026, 10, 1, 21, 45, tzinfo=timezone.utc), DAG)
    # 23:45 UTC the day before is 01:45 CEST on the day: almost nothing of it.
    assert not tacker_dagen(datetime(2026, 9, 30, 23, 45, tzinfo=timezone.utc), DAG)


def test_naive_timestamps_are_taken_as_they_are():
    assert tacker_dagen(datetime(2026, 10, 1, 23, 0), DAG)
    assert not tacker_dagen(datetime(2026, 10, 1, 22, 0), DAG)
    assert tacker_dagen(datetime(2026, 10, 2, 0, 0), DAG)


def test_dates_and_missing_values():
    assert tacker_dagen(date(2026, 10, 1), DAG)
    assert not tacker_dagen(date(2026, 9, 30), DAG)
    assert not tacker_dagen(None, DAG)


def test_kontrollera_lists_what_is_missing():
    idag = date(2026, 10, 2)
    hamtare = {
        "Spot SE3": lambda: datetime(2026, 10, 1, 23, 45, tzinfo=timezone.utc),
        "eSett SE3": lambda: datetime(2026, 9, 30, 23, 30, tzinfo=timezone.utc),
        "Bazefield hova": lambda: None,
    }
    resultat = kontrollera(idag, hamtare, temperatur={"hova": lambda: date(2026, 9, 26)})
    assert resultat["dag"] == "2026-10-01"
    assert not resultat["komplett"]
    assert resultat["saknas"] == [
        "eSett SE3 (senast 2026-10-01 01:30)",
        "Bazefield hova (ingen data)",
    ]


def test_temperature_may_lag_a_week():
    idag = date(2026, 10, 2)
    ok = kontrollera(idag, {}, temperatur={"hova": lambda: date(2026, 9, 25)})
    assert ok["komplett"]
    gammal = kontrollera(idag, {}, temperatur={"hova": lambda: date(2026, 9, 24)})
    assert gammal["saknas"] == ["Temperatur hova (senast 2026-09-24)"]
