"""Tester för elpris.futures_zonal — zonforward (SYS + EPAD) per handelsdag."""

import pytest

from elpris.dashboard_v2_data import _parse_contract_period
from elpris.futures_zonal import load_zonal_forward_history, parse_contract_label

OLD_HEADER = "date,contract,daily_fix_eur,bid_eur,ask_eur,high_eur,low_eur,open_interest"
NEW_HEADER = OLD_HEADER + ",open_eur,volume,source,fetched_at"


@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("ENOFUTBLYR-27", ("YR-27", "YR", "2027-01-01", "2027-12-31")),
        ("SYSTOFUTBLQ1-27", ("Q1-27", "Q", "2027-01-01", "2027-03-31")),
        ("SYMALFUTBLQ4-26", ("Q4-26", "Q", "2026-10-01", "2026-12-31")),
        ("ENOFUTBLMFEB-28", ("MFEB-28", "M", "2028-02-01", "2028-02-29")),
        ("SYSTOFUTBLMOCT-26", ("MOCT-26", "M", "2026-10-01", "2026-10-31")),
        ("YR-30", ("YR-30", "YR", "2030-01-01", "2030-12-31")),
    ],
)
def test_parse_contract_label(symbol, expected):
    meta = parse_contract_label(symbol)
    assert (meta["label"], meta["kind"], meta["delivery_start"], meta["delivery_end"]) == expected


@pytest.mark.parametrize("symbol", ["", "ENOFUTBLM1-26", "ENOFUTBLQ5-26", "ENOFUTBLWK42-26", "ERIC B"])
def test_parse_contract_label_rejects_unknown(symbol):
    assert parse_contract_label(symbol) is None


@pytest.mark.parametrize("symbol", ["ENOFUTBLYR-27", "ENOFUTBLQ2-26", "SYLULFUTBLQ3-27"])
def test_parse_contract_label_agrees_with_dashboard_parser(symbol):
    label, _ctype, start, end = _parse_contract_period(symbol)
    meta = parse_contract_label(symbol)
    assert (meta["label"], meta["delivery_start"], meta["delivery_end"]) == (label, start, end)


def _write(path, header, rows):
    extra = header.count(",") - 2
    lines = [header] + [f"{d},{c},{p}" + "," * extra for d, c, p in rows]
    path.write_text("\n".join(lines) + "\n")


@pytest.fixture
def futures_dir(tmp_path):
    d = tmp_path / "futures"
    d.mkdir()
    # SYS i gammalt 8-kolumnsschema, EPAD i nytt 12-kolumnsschema.
    _write(d / "sys_baseload.csv", OLD_HEADER, [
        ("2026-09-18", "ENOFUTBLYR-27", "67.90"),
        ("2026-09-21", "ENOFUTBLYR-27", "66.55"),
        ("2026-09-22", "ENOFUTBLYR-27", "64.65"),
        ("2026-09-22", "ENOFUTBLQ4-26", "104.01"),
        ("2026-09-22", "ENOFUTBLMOCT-26", "99.25"),
        ("2026-09-22", "ENOFUTBLYR-33", "52.25"),   # EPAD saknas helt
        ("2026-09-22", "ENOFUTBLYR-28", ""),        # tom fix ignoreras
    ])
    _write(d / "epad_se3_sto.csv", NEW_HEADER, [
        ("2026-09-18", "SYSTOFUTBLYR-27", "-5.00"),
        # 21/9 saknas -> ingen zonobservation den dagen
        ("2026-09-22", "SYSTOFUTBLYR-27", "-4.70"),
        ("2026-09-22", "SYSTOFUTBLQ4-26", "-11.35"),
        ("2026-09-22", "SYSTOFUTBLMOCT-26", "-8.47"),
        ("2026-09-22", "SYSTOFUTBLQ1-27", "-12.13"),  # SYS saknar Q1-27
    ])
    _write(d / "epad_se4_mal.csv", NEW_HEADER, [
        ("2026-09-21", "SYMALFUTBLYR-27", "14.15"),
        ("2026-09-22", "SYMALFUTBLYR-27", "13.76"),
    ])
    return d


def test_zonal_only_where_both_legs_settled_same_date(futures_dir):
    out = load_zonal_forward_history(("SE3", "SE4"), data_dir=futures_dir)

    assert out["zones"]["SE3"]["YR-27"] == [
        ("2026-09-18", 62.9, 67.9, -5.0),
        ("2026-09-22", 59.95, 64.65, -4.7),
    ]
    assert out["zones"]["SE4"]["YR-27"] == [
        ("2026-09-21", 80.7, 66.55, 14.15),
        ("2026-09-22", 78.41, 64.65, 13.76),
    ]
    # SYS utan EPAD (YR-33) och EPAD utan SYS (Q1-27) ger ingen serie.
    assert "YR-33" not in out["zones"]["SE3"]
    assert "Q1-27" not in out["zones"]["SE3"]


def test_contracts_metadata_and_ordering(futures_dir):
    out = load_zonal_forward_history(("SE3",), data_dir=futures_dir)

    # Sorterat på leveransstart, sedan label.
    assert list(out["zones"]["SE3"]) == ["MOCT-26", "Q4-26", "YR-27"]
    assert out["contracts"] == {
        "MOCT-26": {"kind": "M", "delivery_start": "2026-10-01", "delivery_end": "2026-10-31"},
        "Q4-26": {"kind": "Q", "delivery_start": "2026-10-01", "delivery_end": "2026-12-31"},
        "YR-27": {"kind": "YR", "delivery_start": "2027-01-01", "delivery_end": "2027-12-31"},
    }


def test_missing_epad_file_gives_empty_zone(futures_dir):
    out = load_zonal_forward_history(("SE1",), data_dir=futures_dir)
    assert out == {"zones": {"SE1": {}}, "contracts": {}}


def test_unknown_zone_raises(futures_dir):
    with pytest.raises(ValueError):
        load_zonal_forward_history(("DK1",), data_dir=futures_dir)
