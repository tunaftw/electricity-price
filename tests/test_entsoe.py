from datetime import date

import pytest

from elpris import entsoe


class DummyResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        self.reason = ""

    def raise_for_status(self):
        import requests

        raise requests.HTTPError(f"{self.status_code} Error", response=self)


def test_entsoe_authentication_failure_is_not_retried(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return DummyResponse(
            401,
            """
            <Acknowledgement_MarketDocument>
              <Reason>
                <code>999</code>
                <text>Authentication failed.</text>
              </Reason>
            </Acknowledgement_MarketDocument>
            """,
        )

    monkeypatch.setattr(entsoe.requests, "get", fake_get)

    with pytest.raises(Exception) as exc_info:
        entsoe.fetch_entsoe_data(
            "actual_generation",
            "SE1",
            date(2026, 7, 1),
            date(2026, 7, 4),
            psr_type="solar",
            token="invalid-token",
        )

    assert len(calls) == 1
    assert "Authentication failed" in str(exc_info.value)
    assert "failed.." not in str(exc_info.value)
    assert "ENTSOE_TOKEN" in str(exc_info.value)


# ---------------------------------------------------------------------------
# A03 gap filling, DK zones, price rows
# ---------------------------------------------------------------------------

import csv  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import tenacity  # noqa: E402

from elpris.config import SWEDEN_TZ  # noqa: E402


def _price_xml(eic: str, periods: list[tuple[str, str, str, list[tuple[int, float]]]],
               curve_type: str = "A03") -> str:
    """Minimal A44 Publication_MarketDocument, one TimeSeries per period."""
    ts = []
    for i, (start, end, resolution, points) in enumerate(periods, 1):
        pts = "".join(
            f"<Point><position>{p}</position><price.amount>{v}</price.amount></Point>"
            for p, v in points
        )
        ts.append(f"""
        <TimeSeries>
          <mRID>{i}</mRID>
          <businessType>A62</businessType>
          <in_Domain.mRID codingScheme="A01">{eic}</in_Domain.mRID>
          <out_Domain.mRID codingScheme="A01">{eic}</out_Domain.mRID>
          <curveType>{curve_type}</curveType>
          <Period>
            <timeInterval><start>{start}</start><end>{end}</end></timeInterval>
            <resolution>{resolution}</resolution>
            {pts}
          </Period>
        </TimeSeries>""")
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">'
        + "".join(ts) + "</Publication_MarketDocument>"
    )


def _generation_xml(eic: str, start: str, end: str, resolution: str,
                    points: list[tuple[int, float]], curve_type: str = "A03") -> str:
    pts = "".join(
        f"<Point><position>{p}</position><quantity>{v}</quantity></Point>"
        for p, v in points
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
    <GL_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0">
      <TimeSeries>
        <mRID>1</mRID>
        <businessType>A01</businessType>
        <inBiddingZone_Domain.mRID codingScheme="A01">{eic}</inBiddingZone_Domain.mRID>
        <quantity_Measure_Unit.name>MAW</quantity_Measure_Unit.name>
        <curveType>{curve_type}</curveType>
        <MktPSRType><psrType>B16</psrType></MktPSRType>
        <Period>
          <timeInterval><start>{start}</start><end>{end}</end></timeInterval>
          <resolution>{resolution}</resolution>
          {pts}
        </Period>
      </TimeSeries>
    </GL_MarketDocument>"""


def test_dk_zone_mapping():
    assert entsoe.ENTSOE_ZONES["DK1"] == "10YDK-1--------W"
    assert entsoe.ENTSOE_ZONES["DK2"] == "10YDK-2--------M"
    assert entsoe.ENTSOE_ZONE_BY_EIC["10YDK-2--------M"] == "DK2"
    # Swedish mapping unchanged
    assert entsoe.ENTSOE_ZONES["SE3"] == "10Y1001A1001A46L"
    assert list(entsoe.SWEDISH_ZONES) == ["SE1", "SE2", "SE3", "SE4"]
    from elpris.config import DK_ZONES, ZONES

    assert list(entsoe.SWEDISH_ZONES) == ZONES
    assert list(entsoe.DANISH_ZONES) == DK_ZONES


def test_price_parser_forward_fills_a03_gaps():
    # One hour at PT15M: positions 2 and 4 omitted (repeat of previous).
    xml = _price_xml("10YDK-1--------W", [
        ("2025-09-30T22:00Z", "2025-09-30T23:00Z", "PT15M", [(1, 102.6), (3, 86.03)]),
    ])
    recs = list(entsoe.parse_prices_xml(xml))
    assert [r["price_eur_mwh"] for r in recs] == [102.6, 102.6, 86.03, 86.03]
    assert [r["time_start"] for r in recs] == [
        "2025-09-30T22:00:00+00:00",
        "2025-09-30T22:15:00+00:00",
        "2025-09-30T22:30:00+00:00",
        "2025-09-30T22:45:00+00:00",
    ]
    assert {r["zone"] for r in recs} == {"DK1"}
    assert {r["resolution_minutes"] for r in recs} == {15}


def test_price_parser_a03_trailing_repeat_fills_to_interval_end():
    # 23-hour DST day, last 3 hours repeat position 20.
    xml = _price_xml("10YDK-2--------M", [
        ("2024-03-30T23:00Z", "2024-03-31T22:00Z", "PT60M",
         [(i, float(i)) for i in range(1, 21)]),
    ])
    recs = list(entsoe.parse_prices_xml(xml))
    assert len(recs) == 23
    assert [r["price_eur_mwh"] for r in recs[-4:]] == [20.0, 20.0, 20.0, 20.0]
    assert recs[-1]["time_start"] == "2024-03-31T21:00:00+00:00"
    assert {r["zone"] for r in recs} == {"DK2"}


def test_price_parser_a01_does_not_invent_missing_points():
    xml = _price_xml("10YDK-1--------W", [
        ("2024-01-01T23:00Z", "2024-01-02T03:00Z", "PT60M", [(1, 10.0), (3, 30.0)]),
    ], curve_type="A01")
    recs = list(entsoe.parse_prices_xml(xml))
    assert [r["price_eur_mwh"] for r in recs] == [10.0, 30.0]


def test_generation_parser_forward_fills_a03_gaps():
    # 6 hours: night zero at pos 1 (repeated to pos 3), 5 MW at pos 4-5, 7 at 6.
    xml = _generation_xml(
        "10YDK-2--------M", "2025-11-01T00:00Z", "2025-11-01T06:00Z", "PT60M",
        [(1, 0.0), (4, 5.0), (6, 7.0)],
    )
    recs = list(entsoe.parse_generation_xml(xml))
    assert [r["generation_mw"] for r in recs] == [0.0, 0.0, 0.0, 5.0, 5.0, 7.0]
    assert recs[0]["time_start"] == "2025-11-01T00:00:00+00:00"
    assert recs[-1]["time_start"] == "2025-11-01T05:00:00+00:00"
    assert {r["zone"] for r in recs} == {"DK2"}
    assert {r["psr_type"] for r in recs} == {"solar"}
    assert {r["resolution_minutes"] for r in recs} == {60}


def test_generation_parser_partial_day_stops_at_interval_end():
    # ENTSO-E sets timeInterval.end to the last published slot — fill only to it.
    xml = _generation_xml(
        "10Y1001A1001A46L", "2026-09-22T00:00Z", "2026-09-22T01:00Z", "PT15M",
        [(1, 3.5)],
    )
    recs = list(entsoe.parse_generation_xml(xml))
    assert [r["generation_mw"] for r in recs] == [3.5] * 4
    assert recs[-1]["time_start"] == "2026-09-22T00:45:00+00:00"
    assert recs[0]["zone"] == "SE3"


def test_dedupe_prefers_finest_resolution():
    recs = [
        {"time_start": "2025-10-01T22:00:00+00:00", "resolution_minutes": 60, "price_eur_mwh": 1.0},
        {"time_start": "2025-10-01T23:00:00+00:00", "resolution_minutes": 60, "price_eur_mwh": 2.0},
    ] + [
        {"time_start": f"2025-10-01T22:{m:02d}:00+00:00", "resolution_minutes": 15, "price_eur_mwh": 9.0}
        for m in (0, 15, 30, 45)
    ]
    out = entsoe.dedupe_price_records(recs)
    assert [(r["time_start"][11:16], r["resolution_minutes"]) for r in out] == [
        ("22:00", 15), ("22:15", 15), ("22:30", 15), ("22:45", 15), ("23:00", 60),
    ]


def test_fetch_prices_uses_dk_eic_and_local_day_bounds(monkeypatch):
    seen = {}

    class OK:
        status_code = 200
        text = "<ok/>"

    def fake_get(url, params=None, timeout=None):
        seen.update(params)
        return OK()

    monkeypatch.setattr(entsoe.requests, "get", fake_get)
    entsoe.fetch_entsoe_data(
        "day_ahead_prices", "DK2", date(2025, 6, 1), date(2025, 6, 30), token="t"
    )
    assert seen["documentType"] == "A44"
    assert seen["in_Domain"] == seen["out_Domain"] == "10YDK-2--------M"
    # Local (CEST) midnight -> 22:00 UTC the day before
    assert seen["periodStart"] == "202505312200"
    assert seen["periodEnd"] == "202506302200"

    seen.clear()
    entsoe.fetch_entsoe_data(
        "actual_generation", "DK1", date(2025, 6, 1), date(2025, 6, 30),
        psr_type="solar", token="t",
    )
    assert seen["in_Domain"] == "10YDK-1--------W"
    assert seen["psrType"] == "B16"
    # Generation keeps the historical UTC day bounds
    assert seen["periodStart"] == "202506010000"
    assert seen["periodEnd"] == "202507010000"


def test_fetch_errors_redact_token(monkeypatch):
    class Bad:
        status_code = 400
        text = "<Acknowledgement_MarketDocument><Reason><text>Bad thing</text></Reason></Acknowledgement_MarketDocument>"
        reason = "Bad Request"

    once = entsoe.fetch_entsoe_data.retry_with(stop=tenacity.stop_after_attempt(1))

    monkeypatch.setattr(entsoe.requests, "get", lambda *a, **k: Bad())
    with pytest.raises(Exception) as exc_info:
        once("day_ahead_prices", "DK1", date(2025, 1, 1), date(2025, 1, 2), token="SECRET123")
    # tenacity wraps the error in RetryError; _describe_error unwraps it.
    msg = entsoe._describe_error(exc_info.value)
    assert msg == "HTTP 400: Bad thing"

    def boom(*a, **k):
        raise entsoe.requests.ConnectionError(
            "Max retries exceeded with url: /api?securityToken=SECRET123&documentType=A44"
        )

    monkeypatch.setattr(entsoe.requests, "get", boom)
    with pytest.raises(Exception) as exc_info:
        once("day_ahead_prices", "DK1", date(2025, 1, 1), date(2025, 1, 2), token="SECRET123")
    msg = entsoe._describe_error(exc_info.value)
    assert "SECRET123" not in msg
    assert "securityToken=***" in msg
    assert msg.startswith("ConnectionError:")


def test_price_rows_match_swedish_spot_format():
    recs = [
        # 2025-10-01 00:00 CEST, 15-min
        {"time_start": "2025-09-30T22:00:00+00:00", "resolution_minutes": 15, "price_eur_mwh": 102.6},
        # Hourly winter row, tiny and zero prices
        {"time_start": "2023-01-01T01:00:00+00:00", "resolution_minutes": 60, "price_eur_mwh": 0.09},
        {"time_start": "2023-01-01T02:00:00+00:00", "resolution_minutes": 60, "price_eur_mwh": 0.0},
        # Date without EXR -> SEK/EXR empty
        {"time_start": "2021-06-01T10:00:00+00:00", "resolution_minutes": 60, "price_eur_mwh": -5.5},
    ]
    exr = {"2025-10-01": "11.0", "2023-01-01": "11.185089"}
    rows = entsoe.price_records_to_rows(recs, exr)
    assert rows[0] == {
        "time_start": "2025-10-01T00:00:00+02:00",
        "time_end": "2025-10-01T00:15:00+02:00",
        "SEK_per_kWh": "1.1286",
        "EUR_per_kWh": "0.1026",
        "EXR": "11.0",
    }
    assert rows[1]["time_start"] == "2023-01-01T02:00:00+01:00"
    assert rows[1]["time_end"] == "2023-01-01T03:00:00+01:00"
    assert rows[1]["EUR_per_kWh"] == "9e-05"      # same repr as elprisetjustnu
    assert rows[1]["SEK_per_kWh"] == "0.00101"
    assert rows[2]["EUR_per_kWh"] == "0" and rows[2]["SEK_per_kWh"] == "0"
    assert rows[3]["EUR_per_kWh"] == "-0.0055"
    assert rows[3]["SEK_per_kWh"] == "" and rows[3]["EXR"] == ""
    assert list(rows[0]) == entsoe.PRICE_CSV_FIELDS


def test_price_row_dst_fall_back_is_unique_and_ordered(tmp_path, monkeypatch):
    monkeypatch.setattr(entsoe, "SPOT_DIR", tmp_path)
    # 2025-10-26: 02:00-03:00 local occurs twice (00:00Z CEST, 01:00Z CET)
    recs = [
        {"time_start": f"2025-10-26T0{h}:{m:02d}:00+00:00", "resolution_minutes": 15,
         "price_eur_mwh": float(h * 100 + m)}
        for h in (1, 0) for m in (0, 15, 30, 45)
    ]
    rows = entsoe.price_records_to_rows(recs, {})
    entsoe.save_price_rows("DK1", rows, {"2025-10-26": "10.9"})
    with open(tmp_path / "DK1" / "2025.csv") as f:
        saved = list(csv.DictReader(f))
    assert [r["time_start"] for r in saved] == [
        "2025-10-26T02:00:00+02:00", "2025-10-26T02:15:00+02:00",
        "2025-10-26T02:30:00+02:00", "2025-10-26T02:45:00+02:00",
        "2025-10-26T02:00:00+01:00", "2025-10-26T02:15:00+01:00",
        "2025-10-26T02:30:00+01:00", "2025-10-26T02:45:00+01:00",
    ]
    assert saved[3]["time_end"] == "2025-10-26T02:00:00+01:00"
    # EXR was missing at conversion time and filled on save
    assert all(r["EXR"] == "10.9" for r in saved)
    assert saved[4]["SEK_per_kWh"] == "1.09"  # 100 EUR/MWh * 10.9 / 1000
    assert entsoe.get_latest_price_end("DK1") == datetime(2025, 10, 26, 2, 0, tzinfo=timezone.utc)


def test_backfill_exr_and_se_prices_do_not_touch_spot_dir(tmp_path, monkeypatch):
    spot = tmp_path / "spot"
    monkeypatch.setattr(entsoe, "SPOT_DIR", spot)
    monkeypatch.setattr(entsoe, "ENTSOE_DIR", tmp_path / "entsoe")
    rows = entsoe.price_records_to_rows(
        [{"time_start": "2026-09-21T22:00:00+00:00", "resolution_minutes": 15, "price_eur_mwh": 50.0}],
        {},
    )
    entsoe.save_price_rows("DK2", rows)
    assert entsoe.backfill_exr("DK2", {"2026-09-22": "11.2"}) == [2026]
    with open(spot / "DK2" / "2026.csv") as f:
        row = next(csv.DictReader(f))
    assert row["EXR"] == "11.2" and row["SEK_per_kWh"] == "0.56"
    assert entsoe.backfill_exr("DK2", {"2026-09-22": "11.2"}) == []

    # SE prices from ENTSO-E never land in the elprisetjustnu folder
    assert entsoe.get_price_dir("SE3") == tmp_path / "entsoe" / "prices" / "SE3"
    assert entsoe.get_price_dir("DK1") == spot / "DK1"


def test_load_exr_by_date_reads_se3(tmp_path, monkeypatch):
    monkeypatch.setattr(entsoe, "SPOT_DIR", tmp_path)
    (tmp_path / "SE3").mkdir()
    (tmp_path / "SE3" / "2026.csv").write_text(
        "time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR\n"
        "2026-01-01T00:00:00+01:00,2026-01-01T00:15:00+01:00,0.41771,0.03867,10.801826\n"
        "2026-01-02T00:00:00+01:00,2026-01-02T00:15:00+01:00,0.4,0.04,10.9\n"
    )
    assert entsoe.load_exr_by_date() == {"2026-01-01": "10.801826", "2026-01-02": "10.9"}


def test_fetch_with_fallback_splits_failed_month():
    calls = []

    def fetch(s, e):
        calls.append((s, e))
        if (e - s).days > 6:
            raise RuntimeError("HTTP 400: too much")
        if s == date(2025, 11, 15):
            raise RuntimeError("still bad")
        return [{"d": s}]

    records, failures = entsoe._fetch_with_fallback(
        fetch, date(2025, 11, 1), date(2025, 11, 30), verbose=False
    )
    assert calls[0] == (date(2025, 11, 1), date(2025, 11, 30))
    assert len(records) == 4  # 1-7, 8-14, 22-28, 29-30
    assert failures == ["2025-11-15..2025-11-21: still bad"]


def test_month_chunks():
    assert list(entsoe._month_chunks(date(2025, 12, 15), date(2026, 2, 3))) == [
        (date(2025, 12, 15), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 3)),
    ]


# ---------------------------------------------------------------------------
# entsoe_download.py job planning
# ---------------------------------------------------------------------------

def _plan(argv):
    import entsoe_download

    return entsoe_download.plan_jobs(entsoe_download.build_parser().parse_args(argv))


def test_cli_default_run_includes_dk_solar_and_prices():
    gen, prices = _plan([])
    assert gen == [
        (["SE1", "SE2", "SE3", "SE4"], ["solar", "wind_onshore"]),
        (["DK1", "DK2"], ["solar"]),
    ]
    assert prices == ["DK1", "DK2"]
    assert _plan(["--no-dk"]) == ([(["SE1", "SE2", "SE3", "SE4"], ["solar", "wind_onshore"])], [])


def test_cli_explicit_swedish_zones_unchanged():
    # This is exactly what update_all.py passes today: SE only, no DK.
    gen, prices = _plan(["--zones", "SE1", "SE2", "SE3", "SE4", "--types", "solar", "wind_onshore"])
    assert gen == [(["SE1", "SE2", "SE3", "SE4"], ["solar", "wind_onshore"])]
    assert prices == []
    gen, prices = _plan(["--zones", "SE3", "--with-dk"])
    assert gen[1] == (["DK1", "DK2"], ["solar"]) and prices == ["DK1", "DK2"]


def test_cli_dk_generation_and_prices():
    assert _plan(["--zones", "DK1", "DK2", "--types", "solar"]) == ([(["DK1", "DK2"], ["solar"])], [])
    assert _plan(["--prices"]) == ([], ["DK1", "DK2"])
    assert _plan(["--prices", "--zones", "DK2"]) == ([], ["DK2"])
