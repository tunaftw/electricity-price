"""Tester för bazefield — särskilt att chunk-fel loggas och spåras.

Bazefield är portföljens största datakälla. Tidigare sväljdes API-fel tyst
(``except: print``) utan spår, så update_all/cron kunde rapportera 'klart'
trots glapp. Dessa tester gardera att fel nu ger både failure_log-post och
en ``failed_chunks``-lista + status 'partial'.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris import bazefield, failure_log  # noqa: E402


def test_download_park_logs_and_tracks_failed_chunk(monkeypatch, tmp_path):
    monkeypatch.setattr(failure_log, "LOG_DIR", tmp_path)
    monkeypatch.setattr(failure_log, "FAILURE_LOG", tmp_path / "failed.csv")
    monkeypatch.setattr(bazefield.time, "sleep", lambda *a, **k: None)

    def boom(*a, **k):
        raise RuntimeError("API 500")

    monkeypatch.setattr(bazefield, "fetch_park_data", boom)
    monkeypatch.setattr(bazefield, "fetch_weather_data", lambda *a, **k: [])

    before = failure_log.failure_count()
    result = bazefield.download_park(
        "horby",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
        verbose=False,
        api_key="fake",
    )

    assert result["failed_chunks"] == ["2026-01-01..2026-01-03"]
    assert result["status"] == "partial"
    assert failure_log.failure_count() - before == 1


def test_download_park_success_has_no_failed_chunks(monkeypatch, tmp_path):
    monkeypatch.setattr(failure_log, "LOG_DIR", tmp_path)
    monkeypatch.setattr(failure_log, "FAILURE_LOG", tmp_path / "failed.csv")
    monkeypatch.setattr(bazefield.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(bazefield, "fetch_park_data", lambda *a, **k: [])
    monkeypatch.setattr(bazefield, "fetch_weather_data", lambda *a, **k: [])

    result = bazefield.download_park(
        "horby",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
        verbose=False,
        api_key="fake",
    )

    assert result["failed_chunks"] == []
    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Väderstationens lufttemperatur (TempAmbient → temp_air)
# ---------------------------------------------------------------------------

def test_fetch_weather_data_filters_temp_sentinels_and_nan(monkeypatch):
    """Bazefield rapporterar ~6553 och NaN när givaren strular."""
    raw = {
        "IrradianceGHI": [
            {"timestamp": "2026-07-10T12:00:00+02:00", "value": 800.0},
            {"timestamp": "2026-07-10T12:15:00+02:00", "value": 810.0},
            {"timestamp": "2026-07-10T12:30:00+02:00", "value": 790.0},
        ],
        "TempAmbient": [
            {"timestamp": "2026-07-10T12:00:00+02:00", "value": 21.4},
            {"timestamp": "2026-07-10T12:15:00+02:00", "value": 6553.4},
            {"timestamp": "2026-07-10T12:30:00+02:00", "value": float("nan")},
        ],
    }
    monkeypatch.setattr(bazefield, "fetch_timeseries", lambda *a, **k: raw)

    records = bazefield.fetch_weather_data("horby", date(2026, 7, 10), date(2026, 7, 11))

    assert [r.get("temp_air") for r in records] == [21.4, None, None]
    assert len(records) == 3  # GHI-raderna finns kvar


def test_save_weather_data_migrates_old_header_without_temp_air(tmp_path, monkeypatch):
    monkeypatch.setattr(bazefield, "PARKS_PROFILE_DIR", tmp_path)
    csv_path = tmp_path / "horby_SE4_weather.csv"
    csv_path.write_text(
        "timestamp,ghi,wind_speed,humidity\n"
        "2026-07-10T12:00:00+02:00,800.0,3.1,55.0\n",
        encoding="utf-8",
    )

    saved = bazefield.save_weather_data(
        "horby",
        [{
            "timestamp": "2026-07-10T12:15:00+02:00",
            "ghi": 810.0,
            "wind_speed": 3.4,
            "humidity": 54.0,
            "temp_air": 21.4,
        }],
    )

    import csv as _csv

    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))

    assert saved == 1
    assert list(rows[0].keys()) == bazefield.WEATHER_CSV_FIELDS
    assert rows[0]["temp_air"] == ""       # gammal rad behåller tomt fält
    assert rows[1]["temp_air"] == "21.4"
    assert len(rows) == 2
