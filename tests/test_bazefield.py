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
