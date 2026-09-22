"""Tester för futures-nedladdningen (Nasdaq-historik + Euronext-settlements).

Euronext-fixturerna i tests/fixtures/ är riktiga svar från live.euronext.com
hämtade tisdag 2026-09-22 ~22:30 CEST (efter dagens settlement):

* ``euronext_listing_*`` — getPricesFutures (alla löptider i en klass).
* ``euronext_history_*`` — getHistoricalPricePopup (daterade sessioner).
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from elpris import dashboard_v2_data, nasdaq

FIXTURES = Path(__file__).parent / "fixtures"
OLD_HEADER = "date,contract,daily_fix_eur,bid_eur,ask_eur,high_eur,low_eur,open_interest"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Euronext-parsning
# ---------------------------------------------------------------------------

def test_parse_listing_sys_quarters_all_maturities():
    listing = nasdaq.parse_euronext_listing(_fixture("euronext_listing_NSBQ_20260922.html"))

    assert listing["date"] == "2026-09-22"
    # Alla 9 kvartal listas — inte bara rank 1..6 som i den gamla snapshoten.
    assert [m["delivery"] for m in listing["maturities"]] == [
        "Q4 2026", "Q1 2027", "Q2 2027", "Q3 2027", "Q4 2027",
        "Q1 2028", "Q2 2028", "Q3 2028", "Q4 2028",
    ]
    q4 = listing["maturities"][0]
    assert q4["md"] == "31-12-2026"
    assert q4["settle"] == "104.01"
    assert q4["oi"] == "5758"          # tusentalsavgränsare borttagen
    assert q4["tot_vol"] == "285"
    assert (q4["open"], q4["high"], q4["low"]) == ("108.00", "108.15", "101.00")
    assert q4["bid"] == ""             # "-" -> tomt


def test_parse_listing_epad_years_with_dash_cells():
    listing = nasdaq.parse_euronext_listing(_fixture("euronext_listing_STBY_20260922.html"))

    assert listing["date"] == "2026-09-22"
    assert [m["md"] for m in listing["maturities"]] == [
        "31-12-2027", "31-12-2028", "31-12-2029", "31-12-2030",
    ]
    yr27 = listing["maturities"][0]
    assert yr27["settle"] == "-4.70"
    assert yr27["oi"] == "1459"
    assert yr27["last"] == "" and yr27["open"] == ""


def test_parse_listing_months():
    listing = nasdaq.parse_euronext_listing(_fixture("euronext_listing_NSBM_20260922.html"))
    deliveries = [m["delivery"] for m in listing["maturities"]]
    assert deliveries[0] == "Sep 2026"
    assert "Mar 2027" in deliveries


@pytest.mark.parametrize(
    "kind,delivery,expected",
    [
        ("Q", "Q4 2026", "Q4-26"),
        ("Q", "Q1 2028", "Q1-28"),
        ("YR", "2027", "YR-27"),
        ("YR", "2036", "YR-36"),
        ("M", "Oct 2026", "MOCT-26"),
        ("M", "Sept 2026", "MSEP-26"),
        ("Q", "2027", None),
        ("YR", "Q4 2026", None),
        ("M", "Foo 2026", None),
        ("Q", "", None),
    ],
)
def test_euronext_contract_suffix(kind, delivery, expected):
    assert nasdaq.euronext_contract_suffix(kind, delivery) == expected


def test_month_symbols_are_ignored_by_legacy_q_yr_parser():
    # Äldre konsumenter (dashboard_v2_data, intelligence_data) läser bara
    # Q/YR — månadssymbolerna får inte feltolkas som kvartal/år.
    assert dashboard_v2_data._parse_contract_period("ENOFUTBLMOCT-26") is None
    assert dashboard_v2_data._parse_contract_period("SYSTOFUTBLMDEC-26") is None


def test_parse_history_uses_printed_trading_dates():
    sessions = nasdaq.parse_euronext_history(
        _fixture("euronext_history_STBY_2027_20260922.html")
    )

    assert len(sessions) == 10
    assert [s["date"] for s in sessions] == sorted(s["date"] for s in sessions)
    assert sessions[-1] == {
        "date": "2026-09-22", "open": "", "high": "", "low": "",
        "settle": "-4.70", "volume": "21",
    }
    # Helgen 19–20 sep finns inte — varje rad är en handelsdag.
    assert "2026-09-19" not in {s["date"] for s in sessions}
    assert "2026-09-18" in {s["date"] for s in sessions}


def test_parse_history_ohlc():
    sessions = nasdaq.parse_euronext_history(
        _fixture("euronext_history_NSBQ_Q4-2026_20260922.html")
    )
    assert sessions[-1] == {
        "date": "2026-09-22", "open": "108.00", "high": "108.15",
        "low": "101.00", "settle": "104.01", "volume": "285",
    }
    assert sessions[-2]["date"] == "2026-09-21"
    assert sessions[-2]["settle"] == "108.49"


# ---------------------------------------------------------------------------
# Handelsdag: dated history + publiceringsregeln
# ---------------------------------------------------------------------------

def _history():
    return [
        {"date": "2026-09-21", "open": "", "high": "", "low": "", "settle": "-5.00", "volume": "0"},
        {"date": "2026-09-22", "open": "", "high": "", "low": "", "settle": "-4.70", "volume": "21"},
    ]


def test_build_rows_dates_come_from_history_and_listing_extras_attach_to_same_session():
    listing_row = {"settle": "-4.70", "oi": "1459", "bid": "-4.80", "ask": "-4.60"}
    rows = nasdaq.build_euronext_rows(
        "SYSTOFUTBLYR-27", _history(), listing_row, "2026-09-22", "2026-09-22T20:39:10Z"
    )

    assert [r["date"] for r in rows] == ["2026-09-21", "2026-09-22"]
    latest = rows[-1]
    assert latest["daily_fix_eur"] == "-4.70"
    assert latest["open_interest"] == "1459"
    assert (latest["bid_eur"], latest["ask_eur"]) == ("-4.80", "-4.60")
    assert latest["volume"] == "21"
    assert latest["source"] == "euronext"
    assert latest["fetched_at"] == "2026-09-22T20:39:10Z"
    assert rows[0]["open_interest"] == ""  # OI bara för den session listningen visar


@pytest.mark.parametrize(
    "listing_date,listing_settle",
    [
        ("2026-09-23", "-4.70"),  # listningen visar redan nästa handelsdag
        ("2026-09-22", "-5.00"),  # listningen visar ännu föregående settlement
    ],
)
def test_build_rows_drops_listing_extras_when_session_is_not_proven(listing_date, listing_settle):
    listing_row = {"settle": listing_settle, "oi": "1459", "bid": "", "ask": ""}
    rows = nasdaq.build_euronext_rows("SYSTOFUTBLYR-27", _history(), listing_row, listing_date)
    assert all(r["open_interest"] == "" for r in rows)


@pytest.mark.parametrize(
    "fetched_utc,expected",
    [
        # Tis 22 sep 21:12 CEST (UTC+2) -> samma dag (bekräftat mot historiken)
        (datetime(2026, 9, 22, 19, 12, tzinfo=timezone.utc), "2026-09-22"),
        # Ons 15 jul 13:25 CEST -> före publicering -> tisdag (bekräftat)
        (datetime(2026, 7, 15, 11, 25, tzinfo=timezone.utc), "2026-07-14"),
        # Lör 12 sep 08:21 CEST -> fredag (bekräftat)
        (datetime(2026, 9, 12, 6, 21, tzinfo=timezone.utc), "2026-09-11"),
        # Sön 23 aug 22:38 CEST -> fredag (bekräftat)
        (datetime(2026, 8, 23, 20, 38, tzinfo=timezone.utc), "2026-08-21"),
        # Mån 10:00 -> fredag
        (datetime(2026, 9, 21, 8, 0, tzinfo=timezone.utc), "2026-09-18"),
        # Mån exakt 18:00 CEST -> måndag
        (datetime(2026, 9, 21, 16, 0, tzinfo=timezone.utc), "2026-09-21"),
        # Fre 17:59 CEST -> torsdag
        (datetime(2026, 9, 18, 15, 59, tzinfo=timezone.utc), "2026-09-17"),
        # Vintertid: tis 1 dec 18:30 CET (UTC+1) -> samma dag
        (datetime(2026, 12, 1, 17, 30, tzinfo=timezone.utc), "2026-12-01"),
        # Vintertid: tis 1 dec 17:30 CET -> måndag
        (datetime(2026, 12, 1, 16, 30, tzinfo=timezone.utc), "2026-11-30"),
    ],
)
def test_settlement_date_for_fetch(fetched_utc, expected):
    assert nasdaq.settlement_date_for_fetch(fetched_utc).isoformat() == expected


def test_settlement_date_for_fetch_treats_naive_as_utc():
    naive = datetime(2026, 9, 22, 19, 12)
    assert nasdaq.settlement_date_for_fetch(naive).isoformat() == "2026-09-22"


# ---------------------------------------------------------------------------
# CSV-schema: bakåtkompatibilitet + dedup
# ---------------------------------------------------------------------------

def _write_old_csv(path, lines):
    path.write_text("\n".join([OLD_HEADER] + lines) + "\n")


def test_old_schema_rows_get_inferred_source(tmp_path):
    path = tmp_path / "sys_baseload.csv"
    _write_old_csv(path, [
        "2026-04-29,ENOFUTBLYR-27,46.45,46.40,46.50,46.60,46.30,4100",
        "2026-07-03,ENOFUTBLYR-27,48.55,,,,,4035",
    ])

    rows = nasdaq.load_futures_csv(path)

    assert [r["source"] for r in rows] == ["nasdaq", "euronext"]
    assert all(r["fetched_at"] == "" for r in rows)
    assert rows[0]["bid_eur"] == "46.40"
    assert set(rows[0]) == set(nasdaq.CSV_FIELDS)


def test_save_upgrades_header_and_keeps_old_columns_readable(tmp_path):
    import csv

    path = tmp_path / "sys_baseload.csv"
    _write_old_csv(path, ["2026-04-29,ENOFUTBLYR-27,46.45,,,,,4100"])

    nasdaq.save_to_csv([], path)

    header = path.read_text().splitlines()[0].split(",")
    assert header[:8] == OLD_HEADER.split(",")      # gamla kolumner först, samma ordning
    assert header[8:] == ["open_eur", "volume", "source", "fetched_at"]
    row = next(csv.DictReader(path.open()))
    assert row["daily_fix_eur"] == "46.45" and row["source"] == "nasdaq"


def test_refetch_same_trading_date_replaces_instead_of_duplicating(tmp_path):
    path = tmp_path / "epad_se3_sto.csv"
    first = {
        "date": "2026-09-22", "contract": "SYSTOFUTBLYR-27", "daily_fix_eur": "-4.60",
        "open_interest": "1459", "source": "euronext", "fetched_at": "2026-09-22T15:00:00Z",
    }
    corrected = {
        "date": "2026-09-22", "contract": "SYSTOFUTBLYR-27", "daily_fix_eur": "-4.70",
        "volume": "21", "source": "euronext", "fetched_at": "2026-09-22T17:15:00Z",
    }

    assert nasdaq.save_to_csv([first], path) == 1
    assert nasdaq.save_to_csv([corrected], path) == 1
    assert nasdaq.save_to_csv([corrected], path) == 1  # idempotent

    (row,) = nasdaq.load_futures_csv(path)
    assert row["daily_fix_eur"] == "-4.70"        # ny settlement vinner
    assert row["volume"] == "21"
    assert row["open_interest"] == "1459"          # fält den nya hämtningen saknar behålls
    assert row["fetched_at"] == "2026-09-22T17:15:00Z"


def test_identical_refetch_keeps_first_fetched_at(tmp_path):
    path = tmp_path / "epad_se3_sto.csv"
    row = {
        "date": "2026-09-22", "contract": "SYSTOFUTBLYR-27", "daily_fix_eur": "-4.70",
        "volume": "21", "source": "euronext", "fetched_at": "2026-09-22T17:15:00Z",
    }
    nasdaq.save_to_csv([row], path)
    before = path.read_bytes()
    nasdaq.save_to_csv([dict(row, fetched_at="2026-09-23T17:15:00Z")], path)
    assert path.read_bytes() == before  # ingen churn i CSV:n


def test_euronext_never_overwrites_nasdaq_row(tmp_path):
    path = tmp_path / "sys_baseload.csv"
    _write_old_csv(path, ["2026-04-28,ENOFUTBLYR-27,46.03,46.00,46.10,,,4000"])

    nasdaq.save_to_csv([{
        "date": "2026-04-28", "contract": "ENOFUTBLYR-27", "daily_fix_eur": "99.99",
        "source": "euronext", "fetched_at": "2026-09-22T20:00:00Z",
    }, {
        "date": "2026-04-02", "contract": "ENOFUTBLYR-27", "daily_fix_eur": "46.10",
        "source": "euronext", "fetched_at": "2026-09-22T20:00:00Z",
    }], path)

    rows = {r["date"]: r for r in nasdaq.load_futures_csv(path)}
    assert rows["2026-04-28"]["daily_fix_eur"] == "46.03"
    assert rows["2026-04-28"]["source"] == "nasdaq"
    assert rows["2026-04-02"]["source"] == "euronext"  # hål i Nasdaq-historiken fylls


# ---------------------------------------------------------------------------
# Omdatering av gamla fetch-daterade snapshot-rader
# ---------------------------------------------------------------------------

def _legacy(d, contract, fix, oi=""):
    return nasdaq._normalize_row({
        "date": d, "contract": contract, "daily_fix_eur": fix, "open_interest": oi,
    })


HIST = {
    "ENOFUTBLYR-27": {"2026-09-10": "116.00", "2026-09-11": "116.90", "2026-09-14": "121.90"},
    "ENOFUTBLQ4-26": {"2026-09-10": "110.00", "2026-09-11": "111.75", "2026-09-14": "113.00"},
}


def test_redate_weekend_snapshot_to_friday():
    rows = [
        _legacy("2026-09-12", "ENOFUTBLYR-27", "116.90", "4829"),
        _legacy("2026-09-12", "ENOFUTBLQ4-26", "111.75"),
    ]
    out, report = nasdaq.redate_legacy_euronext_rows(rows, HIST)

    assert sorted((r["date"], r["contract"]) for r in out) == [
        ("2026-09-11", "ENOFUTBLQ4-26"), ("2026-09-11", "ENOFUTBLYR-27"),
    ]
    assert next(r for r in out if r["contract"] == "ENOFUTBLYR-27")["open_interest"] == "4829"
    assert report == [{
        "snapshot_date": "2026-09-12", "trading_date": "2026-09-11",
        "rows": 2, "compared": 2, "ambiguous": False, "dropped": 0,
    }]


def test_redate_weekday_snapshot_fetched_before_publication():
    # Hämtad mån 14 sep före 18:00 -> visade fredagens settlement.
    rows = [
        _legacy("2026-09-14", "ENOFUTBLYR-27", "116.90"),
        _legacy("2026-09-14", "ENOFUTBLQ4-26", "111.75"),
    ]
    out, report = nasdaq.redate_legacy_euronext_rows(rows, HIST)
    assert {r["date"] for r in out} == {"2026-09-11"}
    assert report[0]["trading_date"] == "2026-09-11"


def test_redate_keeps_same_day_snapshot_and_is_idempotent():
    rows = [_legacy("2026-09-14", "ENOFUTBLYR-27", "121.90")]
    out, report = nasdaq.redate_legacy_euronext_rows(rows, HIST)
    assert out[0]["date"] == "2026-09-14"
    out2, _ = nasdaq.redate_legacy_euronext_rows(out, HIST)
    assert out2 == out


def test_redate_requires_every_row_in_group_to_match():
    # YR-27 matchar fredag men Q4-26 matchar ingen dag -> olöst, ligger kvar;
    # raden vars datum har en annan daterad settlement tas bort.
    rows = [
        _legacy("2026-09-12", "ENOFUTBLYR-27", "116.90"),
        _legacy("2026-09-12", "ENOFUTBLQ4-26", "999.00"),
        _legacy("2026-09-14", "ENOFUTBLQ4-26", "1.00"),
    ]
    out, report = nasdaq.redate_legacy_euronext_rows(rows, HIST)
    by_snap = {g["snapshot_date"]: g for g in report}
    assert by_snap["2026-09-12"]["trading_date"] is None
    assert by_snap["2026-09-14"]["dropped"] == 1
    assert sorted((r["date"], r["contract"]) for r in out) == [
        ("2026-09-12", "ENOFUTBLQ4-26"), ("2026-09-12", "ENOFUTBLYR-27"),
    ]


def test_redate_leaves_nasdaq_and_fresh_rows_alone():
    nasdaq_row = _legacy("2026-04-29", "ENOFUTBLYR-27", "46.45")
    fresh = nasdaq._normalize_row({
        "date": "2026-09-12", "contract": "ENOFUTBLYR-27", "daily_fix_eur": "116.90",
        "fetched_at": "2026-09-22T20:00:00Z",
    })
    out, report = nasdaq.redate_legacy_euronext_rows([nasdaq_row, fresh], HIST)
    assert out == [nasdaq_row, fresh]
    assert report == []


# ---------------------------------------------------------------------------
# End-to-end mot fixturer (ingen nätverkstrafik)
# ---------------------------------------------------------------------------

def test_update_euronext_futures_is_idempotent(tmp_path, monkeypatch):
    listing = _fixture("euronext_listing_STBY_20260922.html")
    history = _fixture("euronext_history_STBY_2027_20260922.html")
    calls = []

    def fake_get(session, url, params=None, referer=None):
        calls.append(url)
        return history if "getHistoricalPricePopup" in url else listing

    monkeypatch.setattr(nasdaq, "_euronext_get", fake_get)
    monkeypatch.setattr(nasdaq, "REQUEST_DELAY", 0)

    kwargs = dict(n_sessions=10, data_dir=tmp_path, log=lambda _m: None,
                  files=["epad_se3_sto.csv"], kinds=("YR",))
    summary, errors = nasdaq.update_euronext_futures(**kwargs)
    assert errors == []
    # 4 löptider x 10 sessioner (samma historikfixtur för alla löptider)
    assert summary["epad_se3_sto.csv"]["rows"] == 40
    assert summary["epad_se3_sto.csv"]["latest"] == "2026-09-22"

    summary2, _ = nasdaq.update_euronext_futures(**kwargs)
    assert summary2["epad_se3_sto.csv"] == {"rows": 40, "new": 0, "latest": "2026-09-22"}

    rows = nasdaq.load_futures_csv(tmp_path / "epad_se3_sto.csv")
    yr27 = [r for r in rows if r["contract"] == "SYSTOFUTBLYR-27"]
    assert yr27[-1]["date"] == "2026-09-22"
    assert yr27[-1]["open_interest"] == "1459"   # listningen visar samma session
    assert all(r["source"] == "euronext" for r in rows)
    assert len(calls) == 2 * (1 + 4)


# ---------------------------------------------------------------------------
# Forward-kurvan (dashboard_v2_data) mot blandad Nasdaq/Euronext-data
# ---------------------------------------------------------------------------

def test_forward_curve_excludes_stale_active_contracts(tmp_path, monkeypatch):
    data_dir = tmp_path / "futures"
    data_dir.mkdir()
    (data_dir / "sys_baseload.csv").write_text(
        "\n".join(
            [
                OLD_HEADER,
                "2026-04-29,ENOFUTBLQ3-26,48.50,,,,,",
                "2026-07-03,ENOFUTBLQ4-26,72.95,,,,,5102",
                "2026-07-03,ENOFUTBLYR-27,48.55,,,,,4035",
            ]
        )
        + "\n"
    )
    for filename in [
        "epad_se1_lul.csv",
        "epad_se2_sun.csv",
        "epad_se3_sto.csv",
        "epad_se4_mal.csv",
    ]:
        (data_dir / filename).write_text(OLD_HEADER + "\n")

    monkeypatch.setattr(dashboard_v2_data, "NASDAQ_DATA_DIR", data_dir)

    forward = dashboard_v2_data.load_forward_curve_data({})

    labels = [c["label"] for c in forward["contracts"]]
    assert forward["settlement_date"] == "2026-07-03"
    assert "Q3-26" not in labels
    assert labels[:2] == ["Q4-26", "YR-27"]
    # Inga EPAD-ben -> inget zonpris (aldrig SYS förklätt till SE-pris).
    assert forward["zone_fwd"]["SE3"] == {"Q4-26": None, "YR-27": None}
