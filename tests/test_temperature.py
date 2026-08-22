"""Tester för elpris.temperature — ERA5-parsning, CSV-merge, loader, klimatologi.

Ingen nätverksåtkomst: HTTP mockas och TEMPERATURE_DATA_DIR pekas om till tmp_path.
"""

from __future__ import annotations

import csv
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris import temperature  # noqa: E402
from elpris.config import UTC_TZ  # noqa: E402


@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    """Peka om temperatur-CSV-katalogen till en tom tmp-katalog."""
    monkeypatch.setattr(temperature, "TEMPERATURE_DATA_DIR", tmp_path)
    return tmp_path


def _write_csv(path: Path, rows: list[tuple[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=temperature.CSV_FIELDS)
        w.writeheader()
        for ts, temp in rows:
            w.writerow({"timestamp": ts, "temp_c": temp})


def _read_csv(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Koordinater
# ---------------------------------------------------------------------------

def test_park_coords_cover_all_eight_parks():
    from elpris.config import PARK_ZONES

    assert set(temperature.PARK_COORDS) == set(PARK_ZONES)


@pytest.mark.parametrize(
    "park,lat_range",
    [
        ("horby", (55.9, 56.3)),
        ("agerum", (55.9, 56.3)),
        ("tangen", (55.9, 56.3)),
        ("fjallskar", (58.6, 58.8)),
        ("hova", (58.8, 59.1)),
        ("bjorke", (60.7, 61.0)),
        ("skakelbacken", (60.0, 61.5)),
        ("stenstorp", (58.0, 58.5)),
    ],
)
def test_park_coords_land_in_the_right_part_of_sweden(park, lat_range):
    lat, lon = temperature.PARK_COORDS[park]
    lo, hi = lat_range
    assert lo <= lat <= hi, f"{park} latitud {lat} utanför {lat_range}"
    assert 10.0 <= lon <= 20.0, f"{park} longitud {lon} utanför Sverige"


# ---------------------------------------------------------------------------
# Parsning av Open-Meteo-JSON
# ---------------------------------------------------------------------------

def test_parse_hourly_response_maps_time_and_temperature():
    payload = {
        "hourly": {
            "time": ["2024-08-01T00:00", "2024-08-01T01:00"],
            "temperature_2m": [17.3, 16.85],
        }
    }

    rows = temperature.parse_hourly_response(payload)

    assert rows == [
        {"timestamp": "2024-08-01T00:00:00+00:00", "temp_c": 17.3},
        {"timestamp": "2024-08-01T01:00:00+00:00", "temp_c": 16.85},
    ]


def test_parse_hourly_response_skips_nulls_and_sentinels():
    payload = {
        "hourly": {
            "time": [
                "2024-08-01T00:00",
                "2024-08-01T01:00",
                "2024-08-01T02:00",
                "2024-08-01T03:00",
            ],
            # null (ej klar reanalys), sentinel (Bazefield-liknande), giltigt, sträng
            "temperature_2m": [None, 6553.4, 12.0, "nan"],
        }
    }

    rows = temperature.parse_hourly_response(payload)

    assert [r["timestamp"] for r in rows] == ["2024-08-01T02:00:00+00:00"]
    assert rows[0]["temp_c"] == 12.0


def test_parse_hourly_response_raises_on_api_error():
    with pytest.raises(ValueError, match="Open-Meteo error"):
        temperature.parse_hourly_response(
            {"error": True, "reason": "Latitude must be in range"}
        )


def test_parse_hourly_response_handles_empty_payload():
    assert temperature.parse_hourly_response({}) == []


def test_fetch_temperature_requests_expected_params(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "hourly": {
                    "time": ["2015-01-01T00:00"],
                    "temperature_2m": [-3.4],
                }
            }

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setattr(temperature.requests, "get", fake_get)

    rows = temperature.fetch_temperature(56.05, 14.67, date(2015, 1, 1), date(2015, 12, 31))

    assert captured["url"] == temperature.ERA5_URL
    assert captured["params"]["latitude"] == 56.05
    assert captured["params"]["longitude"] == 14.67
    assert captured["params"]["start_date"] == "2015-01-01"
    assert captured["params"]["end_date"] == "2015-12-31"
    assert captured["params"]["hourly"] == "temperature_2m"
    assert captured["params"]["timezone"] == "UTC"
    assert rows == [{"timestamp": "2015-01-01T00:00:00+00:00", "temp_c": -3.4}]


# ---------------------------------------------------------------------------
# CSV-merge
# ---------------------------------------------------------------------------

def test_save_temperature_data_creates_file_with_header(fake_data_dir):
    added = temperature.save_temperature_data(
        "horby",
        [
            {"timestamp": "2024-08-01T01:00:00+00:00", "temp_c": 16.0},
            {"timestamp": "2024-08-01T00:00:00+00:00", "temp_c": 17.0},
        ],
    )

    path = temperature.get_temperature_csv_path("horby")
    rows = _read_csv(path)

    assert added == 2
    assert [r["timestamp"] for r in rows] == [
        "2024-08-01T00:00:00+00:00",
        "2024-08-01T01:00:00+00:00",
    ]
    assert list(rows[0].keys()) == temperature.CSV_FIELDS


def test_save_temperature_data_does_not_duplicate_timestamps(fake_data_dir):
    first = [
        {"timestamp": "2024-08-01T00:00:00+00:00", "temp_c": 17.0},
        {"timestamp": "2024-08-01T01:00:00+00:00", "temp_c": 16.0},
    ]
    temperature.save_temperature_data("horby", first)

    # Överlappande hämtning: en dubblett + en ny timme
    added = temperature.save_temperature_data(
        "horby",
        [
            {"timestamp": "2024-08-01T01:00:00+00:00", "temp_c": 16.0},
            {"timestamp": "2024-08-01T02:00:00+00:00", "temp_c": 15.5},
        ],
    )

    rows = _read_csv(temperature.get_temperature_csv_path("horby"))
    timestamps = [r["timestamp"] for r in rows]

    assert added == 1
    assert len(timestamps) == len(set(timestamps)) == 3


def test_save_temperature_data_overwrites_value_for_existing_timestamp(fake_data_dir):
    temperature.save_temperature_data(
        "horby", [{"timestamp": "2024-08-01T00:00:00+00:00", "temp_c": 17.0}]
    )
    temperature.save_temperature_data(
        "horby", [{"timestamp": "2024-08-01T00:00:00+00:00", "temp_c": 18.5}]
    )

    rows = _read_csv(temperature.get_temperature_csv_path("horby"))

    assert len(rows) == 1
    assert rows[0]["temp_c"] == "18.5"


def test_save_temperature_data_ignores_empty_input(fake_data_dir):
    assert temperature.save_temperature_data("horby", []) == 0
    assert not temperature.get_temperature_csv_path("horby").exists()


def test_get_latest_stored_date(fake_data_dir):
    assert temperature.get_latest_stored_date("horby") is None

    temperature.save_temperature_data(
        "horby",
        [
            {"timestamp": "2024-08-01T00:00:00+00:00", "temp_c": 17.0},
            {"timestamp": "2024-08-03T23:00:00+00:00", "temp_c": 12.0},
        ],
    )

    assert temperature.get_latest_stored_date("horby") == date(2024, 8, 3)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def test_load_park_temperature_returns_utc_datetimes(fake_data_dir):
    _write_csv(
        temperature.get_temperature_csv_path("hova"),
        [("2024-08-01T00:00:00+00:00", "17.3"), ("2024-08-01T01:00:00+00:00", "16.1")],
    )

    records = temperature.load_park_temperature("hova")

    assert len(records) == 2
    assert records[0]["timestamp_utc"] == datetime(2024, 8, 1, 0, 0, tzinfo=UTC_TZ)
    assert records[0]["temp_c"] == 17.3


def test_load_park_temperature_missing_file_returns_empty(fake_data_dir):
    assert temperature.load_park_temperature("hova") == []


def test_load_park_temperature_filters_on_date_range(fake_data_dir):
    _write_csv(
        temperature.get_temperature_csv_path("hova"),
        [
            ("2024-07-31T23:00:00+00:00", "10.0"),
            ("2024-08-01T00:00:00+00:00", "11.0"),
            ("2024-08-02T23:00:00+00:00", "12.0"),
            ("2024-08-03T00:00:00+00:00", "13.0"),
        ],
    )

    records = temperature.load_park_temperature(
        "hova", start=date(2024, 8, 1), end=date(2024, 8, 2)
    )

    assert [r["temp_c"] for r in records] == [11.0, 12.0]


def test_load_park_temperature_accepts_datetime_bounds(fake_data_dir):
    _write_csv(
        temperature.get_temperature_csv_path("hova"),
        [
            ("2024-08-01T00:00:00+00:00", "11.0"),
            ("2024-08-01T01:00:00+00:00", "12.0"),
            ("2024-08-01T02:00:00+00:00", "13.0"),
        ],
    )

    records = temperature.load_park_temperature(
        "hova",
        start=datetime(2024, 8, 1, 1, tzinfo=UTC_TZ),
        end=datetime(2024, 8, 1, 1, tzinfo=UTC_TZ),
    )

    assert [r["temp_c"] for r in records] == [12.0]


def test_load_park_temperature_sorts_and_skips_broken_rows(fake_data_dir):
    _write_csv(
        temperature.get_temperature_csv_path("hova"),
        [
            ("2024-08-01T02:00:00+00:00", "13.0"),
            ("2024-08-01T00:00:00+00:00", "11.0"),
            ("2024-08-01T01:00:00+00:00", ""),
            ("inte-ett-datum", "9.0"),
        ],
    )

    records = temperature.load_park_temperature("hova")

    assert [r["temp_c"] for r in records] == [11.0, 13.0]


def test_load_park_temperature_map_keys_on_whole_hours(fake_data_dir):
    _write_csv(
        temperature.get_temperature_csv_path("hova"),
        [("2024-08-01T00:00:00+00:00", "17.3"), ("2024-08-01T01:00:00+00:00", "16.1")],
    )

    lookup = temperature.load_park_temperature_map("hova")

    # Ett 15-min-värde från Bazefield ska kunna slås upp på sin timme
    quarter = datetime(2024, 8, 1, 1, 45, tzinfo=UTC_TZ)
    assert lookup[quarter.replace(minute=0)] == 16.1


# ---------------------------------------------------------------------------
# Månadsklimatologi
# ---------------------------------------------------------------------------

def _synthetic_year(year: int, month_temps: dict[int, float]) -> list[tuple[str, str]]:
    """En observation per dygn i varje månad, med månadens temperatur."""
    rows = []
    day = date(year, 1, 1)
    while day.year == year:
        temp = month_temps[day.month]
        rows.append((f"{day.isoformat()}T12:00:00+00:00", str(temp)))
        day += timedelta(days=1)
    return rows


def test_monthly_climatology_averages_calendar_months_across_years(fake_data_dir):
    year_a = {m: float(m) for m in range(1, 13)}          # jan=1 ... dec=12
    year_b = {m: float(m) + 2.0 for m in range(1, 13)}    # 2 grader varmare

    rows = _synthetic_year(2015, year_a) + _synthetic_year(2016, year_b)
    _write_csv(temperature.get_temperature_csv_path("bjorke"), rows)

    clim = temperature.monthly_climatology("bjorke")

    assert set(clim) == set(range(1, 13))
    assert clim[1] == 2.0    # (1 + 3) / 2
    assert clim[7] == 8.0    # (7 + 9) / 2
    assert clim[12] == 13.0  # (12 + 14) / 2


def test_monthly_climatology_excludes_incomplete_years(fake_data_dir):
    full = _synthetic_year(2015, {m: 5.0 for m in range(1, 13)})
    # Ofullständigt år: bara januari, och orimligt varmt — ska inte påverka
    partial = [("2016-01-15T12:00:00+00:00", "30.0")]
    _write_csv(temperature.get_temperature_csv_path("bjorke"), full + partial)

    clim = temperature.monthly_climatology("bjorke")

    assert clim[1] == 5.0


def test_monthly_climatology_falls_back_when_no_complete_year(fake_data_dir):
    _write_csv(
        temperature.get_temperature_csv_path("bjorke"),
        [
            ("2026-07-01T12:00:00+00:00", "20.0"),
            ("2026-07-02T12:00:00+00:00", "22.0"),
            ("2026-08-01T12:00:00+00:00", "18.0"),
        ],
    )

    clim = temperature.monthly_climatology("bjorke")

    assert clim == {7: 21.0, 8: 18.0}


def test_monthly_climatology_weights_years_equally(fake_data_dir):
    """Ett år med tätare observationer får inte dominera medelvärdet."""
    sparse = _synthetic_year(2015, {m: 0.0 for m in range(1, 13)})
    dense = _synthetic_year(2016, {m: 10.0 for m in range(1, 13)})
    # Dubblera 2016 med extra timmar samma dygn
    dense_extra = [(ts.replace("T12:", "T18:"), v) for ts, v in dense]
    _write_csv(
        temperature.get_temperature_csv_path("bjorke"),
        sparse + dense + dense_extra,
    )

    clim = temperature.monthly_climatology("bjorke")

    assert clim[6] == 5.0


def test_monthly_climatology_missing_file_returns_empty(fake_data_dir):
    assert temperature.monthly_climatology("bjorke") == {}
