"""Tester för elpris.failure_log — strukturerad loggning av download-fel."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from elpris import failure_log


@pytest.fixture
def tmp_log(tmp_path, monkeypatch):
    """Pekar om FAILURE_LOG till en temp-fil per test."""
    log_path = tmp_path / "failed_chunks.csv"
    monkeypatch.setattr(failure_log, "LOG_DIR", tmp_path)
    monkeypatch.setattr(failure_log, "FAILURE_LOG", log_path)
    return log_path


def test_log_failure_creates_csv_with_header(tmp_log: Path):
    failure_log.log_failure("entsoe", "SE3", "2024-01-01..2024-03-31", "HTTP 503")
    assert tmp_log.exists()

    with open(tmp_log, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "entsoe"
    assert row["scope"] == "SE3"
    assert row["chunk"] == "2024-01-01..2024-03-31"
    assert row["error"] == "HTTP 503"
    # ISO-8601 UTC timestamp
    ts = datetime.fromisoformat(row["recorded_at"])
    assert ts.tzinfo is not None


def test_log_failure_appends(tmp_log: Path):
    failure_log.log_failure("esett", "SE1", "2024-Q1", "first")
    failure_log.log_failure("esett", "SE2", "2024-Q1", "second")

    with open(tmp_log, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    assert [r["scope"] for r in rows] == ["SE1", "SE2"]
    assert [r["error"] for r in rows] == ["first", "second"]


def test_log_failure_truncates_long_errors(tmp_log: Path):
    long_msg = "x" * 1000
    failure_log.log_failure("mimer", "fcr", "2024-01", long_msg)

    with open(tmp_log, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows[0]["error"]) == 500


def test_log_chunk_failures_splits_chunk_and_error(tmp_log: Path):
    chunks = [
        "2024-01-01..2024-03-31: HTTPError 503",
        "2024-04-01..2024-06-30: ConnectionError timeout",
    ]
    n = failure_log.log_chunk_failures("entsoe", "SE3_solar", chunks)
    assert n == 2

    with open(tmp_log, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert rows[0]["chunk"] == "2024-01-01..2024-03-31"
    assert rows[0]["error"] == "HTTPError 503"
    assert rows[1]["chunk"] == "2024-04-01..2024-06-30"
    assert rows[1]["error"] == "ConnectionError timeout"
    assert all(r["scope"] == "SE3_solar" for r in rows)


def test_log_chunk_failures_handles_chunk_without_error_separator(tmp_log: Path):
    failure_log.log_chunk_failures("nasdaq", "SYSTO", ["2024-01-01"])

    with open(tmp_log, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["chunk"] == "2024-01-01"
    assert rows[0]["error"] == ""


def test_recent_failures_filters_by_age(tmp_log: Path):
    # Skriv en gammal post och en färsk post
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(timespec="seconds")
    fresh_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with open(tmp_log, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=failure_log._FIELDS)
        writer.writeheader()
        writer.writerow({"recorded_at": old_ts, "source": "entsoe", "scope": "SE3",
                         "chunk": "old", "error": "old"})
        writer.writerow({"recorded_at": fresh_ts, "source": "esett", "scope": "SE1",
                         "chunk": "new", "error": "new"})

    recent = failure_log.recent_failures(hours=24)
    assert len(recent) == 1
    assert recent[0]["chunk"] == "new"


def test_recent_failures_empty_when_no_log(tmp_log: Path):
    # tmp_log finns inte ännu — fixturen pekar bara om sökvägen
    assert not tmp_log.exists()
    assert failure_log.recent_failures() == []
