"""Tester för forward_history / forward_health i load_forward_curve_data.

Fokus på de regression-känsliga delarna: delivery-parsning ur kontraktssymbol,
is_clean_final-fönstret (7 dagar före delivery_start) och att endast levererade
eller pågående kontrakt tas med i forward_history.
"""

from datetime import date, timedelta

import pytest

from elpris import dashboard_v2_data
from elpris.dashboard_v2_data import (
    _parse_contract_period,
    build_forward_health,
    is_clean_final,
)


CSV_HEADER = "date,contract,daily_fix_eur,bid_eur,ask_eur,high_eur,low_eur,open_interest"

EPAD_FILES = [
    "epad_se1_lul.csv",
    "epad_se2_sun.csv",
    "epad_se3_sto.csv",
    "epad_se4_mal.csv",
]


def _write_csv(path, rows):
    """Skriv en futures-CSV där rows är (date, contract, daily_fix)-tupler."""
    lines = [CSV_HEADER]
    for row_date, contract, fix in rows:
        lines.append(f"{row_date},{contract},{fix},,,,,")
    path.write_text("\n".join(lines) + "\n")


def _iso(days_from_today: int) -> str:
    return (date.today() + timedelta(days=days_from_today)).isoformat()


# ---------------------------------------------------------------------------
# _parse_contract_period
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("ENOFUTBLYR-27", ("YR-27", "year", "2027-01-01", "2027-12-31")),
        ("ENOFUTBLQ1-26", ("Q1-26", "quarter", "2026-01-01", "2026-03-31")),
        ("ENOFUTBLQ2-26", ("Q2-26", "quarter", "2026-04-01", "2026-06-30")),
        ("ENOFUTBLQ3-26", ("Q3-26", "quarter", "2026-07-01", "2026-09-30")),
        ("ENOFUTBLQ4-26", ("Q4-26", "quarter", "2026-10-01", "2026-12-31")),
        # EPAD-prefix ger samma label — det är så SYS och EPAD matchas ihop.
        ("SYSTOFUTBLQ2-26", ("Q2-26", "quarter", "2026-04-01", "2026-06-30")),
        ("SYMALFUTBLYR-30", ("YR-30", "year", "2030-01-01", "2030-12-31")),
    ],
)
def test_parse_contract_period(symbol, expected):
    assert _parse_contract_period(symbol) == expected


def test_parse_contract_period_rejects_unknown_symbols():
    assert _parse_contract_period("ENOFUTBLM1-26") is None
    assert _parse_contract_period("ERIC B") is None
    assert _parse_contract_period("") is None


# ---------------------------------------------------------------------------
# is_clean_final
# ---------------------------------------------------------------------------

def test_is_clean_final_accepts_fix_on_delivery_start():
    assert is_clean_final("2026-04-01", "2026-04-01") is True


def test_is_clean_final_accepts_fix_day_before_delivery():
    assert is_clean_final("2026-03-31", "2026-04-01") is True


def test_is_clean_final_accepts_fix_exactly_seven_days_before():
    # Gränsfall: exakt på 7-dagarsfönstrets kant räknas som rent.
    assert is_clean_final("2026-03-25", "2026-04-01") is True


def test_is_clean_final_rejects_fix_eight_days_before():
    assert is_clean_final("2026-03-24", "2026-04-01") is False


def test_is_clean_final_rejects_fix_many_months_before():
    # Q1-26-luckan: sista fix 2025-03-28 trots leveransstart 2026-01-01.
    assert is_clean_final("2025-03-28", "2026-01-01") is False


# ---------------------------------------------------------------------------
# build_forward_health
# ---------------------------------------------------------------------------

def _health_entry(label, start, end, last_fix):
    return {"label": label, "start": start, "end": end, "last_fix": last_fix}


def test_forward_health_flags_stale_final_for_delivered_contract():
    health = build_forward_health([
        _health_entry("Q1-26", "2026-01-01", "2026-03-31", "2025-03-28"),
    ], today=date(2026, 8, 22))

    assert health["approaching_expiry"] == []
    assert health["stale_finals"] == [{
        "contract": "Q1-26",
        "expected_near": "2025-12-31",
        "last_fix": "2025-03-28",
    }]


def test_forward_health_ignores_delivered_contract_with_clean_final():
    health = build_forward_health([
        _health_entry("Q2-26", "2026-04-01", "2026-06-30", "2026-03-31"),
    ], today=date(2026, 8, 22))

    assert health["stale_finals"] == []


def test_forward_health_flags_approaching_expiry():
    today = date(2026, 8, 22)
    health = build_forward_health([
        # Leverans om 10 dagar, senaste fix 30 dagar gammal.
        _health_entry(
            "Q4-26",
            (today + timedelta(days=10)).isoformat(),
            (today + timedelta(days=100)).isoformat(),
            (today - timedelta(days=30)).isoformat(),
        ),
    ], today=today)

    assert health["stale_finals"] == []
    assert health["approaching_expiry"] == [{
        "contract": "Q4-26",
        "delivery_start": (today + timedelta(days=10)).isoformat(),
        "last_fix": (today - timedelta(days=30)).isoformat(),
        "days_stale": 30,
    }]


def test_forward_health_ignores_approaching_contract_with_fresh_fix():
    today = date(2026, 8, 22)
    health = build_forward_health([
        _health_entry(
            "Q4-26",
            (today + timedelta(days=10)).isoformat(),
            (today + timedelta(days=100)).isoformat(),
            (today - timedelta(days=2)).isoformat(),
        ),
    ], today=today)

    assert health["approaching_expiry"] == []


def test_forward_health_ignores_contract_beyond_14_day_horizon():
    today = date(2026, 8, 22)
    health = build_forward_health([
        _health_entry(
            "Q1-27",
            (today + timedelta(days=40)).isoformat(),
            (today + timedelta(days=130)).isoformat(),
            (today - timedelta(days=60)).isoformat(),
        ),
    ], today=today)

    assert health["approaching_expiry"] == []


# ---------------------------------------------------------------------------
# forward_history-bygget via load_forward_curve_data
# ---------------------------------------------------------------------------

def _quarter_symbol(prefix: str, day: date) -> str:
    """Bygg kontraktssymbol för kvartalet som innehåller ``day``."""
    quarter = (day.month - 1) // 3 + 1
    return f"{prefix}Q{quarter}-{str(day.year)[-2:]}"


def _shift(iso: str, days: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


@pytest.fixture
def futures_dir(tmp_path, monkeypatch):
    """Syntetisk futures-katalog med ett levererat, ett pågående och ett
    ännu ej påbörjat kontrakt.

    Kontrakten härleds ur dagens datum (kvartalet för ett år sedan, dagens
    kvartal, och ett kvartal ~200 dagar fram) så att testet inte ruttnar,
    och fix-datumen sätts relativt varje kontrakts egen leveransstart så att
    is_clean_final blir deterministiskt oavsett när sviten körs.
    """
    data_dir = tmp_path / "futures"
    data_dir.mkdir()
    today = date.today()

    delivered_sym = _quarter_symbol("ENOFUTBL", today - timedelta(days=365))
    ongoing_sym = _quarter_symbol("ENOFUTBL", today)
    pending_sym = _quarter_symbol("ENOFUTBL", today + timedelta(days=200))

    delivered_label, _, delivered_start, delivered_end = _parse_contract_period(delivered_sym)
    ongoing_label, _, ongoing_start, _ = _parse_contract_period(ongoing_sym)
    pending_label, _, _, _ = _parse_contract_period(pending_sym)

    _write_csv(data_dir / "sys_baseload.csv", [
        # Levererat kontrakt: handeln slutade långt före leveransstart.
        (_shift(delivered_start, -60), delivered_sym, "40.00"),
        (_shift(delivered_start, -40), delivered_sym, "42.00"),
        # Pågående kontrakt: fix ända fram till igår.
        (_shift(ongoing_start, -30), ongoing_sym, "50.00"),
        (_iso(-1), ongoing_sym, "51.00"),
        # Ej påbörjat kontrakt.
        (_iso(-1), pending_sym, "60.00"),
    ])

    delivered_epad = _quarter_symbol("SYSTOFUTBL", today - timedelta(days=365))
    ongoing_epad = _quarter_symbol("SYSTOFUTBL", today)
    for filename in EPAD_FILES:
        _write_csv(data_dir / filename, [
            (_shift(delivered_start, -60), delivered_epad, "-3.00"),
            (_iso(-1), ongoing_epad, "-4.00"),
        ])

    monkeypatch.setattr(dashboard_v2_data, "NASDAQ_DATA_DIR", data_dir)
    return {
        "dir": data_dir,
        "delivered": delivered_label,
        "delivered_start": delivered_start,
        "delivered_end": delivered_end,
        "delivered_final": _shift(delivered_start, -40),
        "delivered_first": _shift(delivered_start, -60),
        "ongoing": ongoing_label,
        "pending": pending_label,
    }


def test_forward_history_excludes_contracts_not_yet_in_delivery(futures_dir):
    forward = dashboard_v2_data.load_forward_curve_data({})
    hist = forward["forward_history"]

    assert futures_dir["delivered"] in hist
    assert futures_dir["ongoing"] in hist
    assert futures_dir["pending"] not in hist


def test_forward_history_schema_and_clean_final_flag(futures_dir):
    forward = dashboard_v2_data.load_forward_curve_data({})
    entry = forward["forward_history"][futures_dir["delivered"]]

    assert set(entry) >= {
        "delivery_start", "delivery_end", "final_settlement_date",
        "is_clean_final", "sys_series", "epad_series", "realised_spot",
    }
    assert entry["delivery_start"] == futures_dir["delivered_start"]
    assert entry["delivery_end"] == futures_dir["delivered_end"]
    # Sista fix ligger 40 dagar före leveransstart → inte ren final.
    assert entry["is_clean_final"] is False
    assert entry["final_settlement_date"] == futures_dir["delivered_final"]
    assert entry["sys_series"] == [
        {"date": futures_dir["delivered_first"], "price": 40.0},
        {"date": futures_dir["delivered_final"], "price": 42.0},
    ]


def test_forward_history_marks_ongoing_contract_as_clean_final(futures_dir):
    forward = dashboard_v2_data.load_forward_curve_data({})
    entry = forward["forward_history"][futures_dir["ongoing"]]

    # Handeln pågick in i leveransperioden → ren final.
    assert entry["is_clean_final"] is True
    assert entry["final_settlement_date"] == _iso(-1)


def test_forward_history_maps_epad_series_per_zone(futures_dir):
    forward = dashboard_v2_data.load_forward_curve_data({})
    entry = forward["forward_history"][futures_dir["delivered"]]

    # Alla fyra zonfilerna innehåller samma syntetiska SYSTO-symbol, så varje
    # zon ska få en serie via label-matchningen.
    assert sorted(entry["epad_series"]) == ["SE1", "SE2", "SE3", "SE4"]
    assert entry["epad_series"]["SE3"] == [
        {"date": futures_dir["delivered_first"], "price": -3.0}
    ]


def test_forward_history_computes_realised_spot_for_delivered_contract(futures_dir):
    label = futures_dir["delivered"]
    # Bygg spot-data som täcker hela leveransperioden för SE3.
    start = date.fromisoformat(futures_dir["delivered_start"])
    end = date.fromisoformat(futures_dir["delivered_end"])

    spot = {"SE3": {}}
    day = start
    while day <= end:
        spot["SE3"][day.isoformat()] = [{"eur_mwh": 100.0}, {"eur_mwh": 50.0}]
        day += timedelta(days=1)

    forward = dashboard_v2_data.load_forward_curve_data(spot)
    realised = forward["forward_history"][label]["realised_spot"]

    assert realised["SE3"] == 75.0
    assert "SE1" not in realised


def test_forward_history_is_empty_without_contracts_in_delivery(tmp_path, monkeypatch):
    data_dir = tmp_path / "futures"
    data_dir.mkdir()
    future_year = date.today().year + 3
    _write_csv(data_dir / "sys_baseload.csv", [
        (_iso(-1), f"ENOFUTBLYR-{str(future_year)[-2:]}", "45.00"),
    ])
    for filename in EPAD_FILES:
        _write_csv(data_dir / filename, [])

    monkeypatch.setattr(dashboard_v2_data, "NASDAQ_DATA_DIR", data_dir)

    forward = dashboard_v2_data.load_forward_curve_data({})
    assert forward["forward_history"] == {}
    # Kontraktet ska fortfarande synas som aktivt i forward-kurvan.
    assert [c["label"] for c in forward["contracts"]] == [
        f"YR-{str(future_year)[-2:]}"
    ]
