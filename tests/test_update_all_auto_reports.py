"""Tests for update_all.py auto-reports functionality."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import helpers from update_all.py
from update_all import previous_month, reports_exist_for_month  # noqa: E402


# ---------------------------------------------------------------------------
# previous_month() tests
# ---------------------------------------------------------------------------

def test_previous_month_mid_month():
    """Test previous_month for a mid-month date."""
    today = date(2026, 7, 22)
    assert previous_month(today) == "2026-06"


def test_previous_month_january_rolls_to_december():
    """Test that January rolls back to previous year's December."""
    today = date(2026, 1, 15)
    assert previous_month(today) == "2025-12"


def test_previous_month_first_of_month():
    """Test previous_month for the first day of a month."""
    today = date(2026, 3, 1)
    assert previous_month(today) == "2026-02"


def test_previous_month_last_of_month():
    """Test previous_month for the last day of a month."""
    today = date(2026, 7, 31)
    assert previous_month(today) == "2026-06"


def test_previous_month_february_in_leap_year():
    """Test previous_month for February in a leap year."""
    today = date(2024, 3, 1)
    assert previous_month(today) == "2024-02"


def test_previous_month_march_after_leap_year_february():
    """Test previous_month for March (previous month was leap year February)."""
    today = date(2024, 3, 15)
    assert previous_month(today) == "2024-02"


def test_previous_month_no_argument_returns_string():
    """Test that previous_month(None) returns a valid month string."""
    result = previous_month(None)
    # Should be in format "YYYY-MM"
    parts = result.split("-")
    assert len(parts) == 2
    assert len(parts[0]) == 4  # Year
    assert len(parts[1]) == 2  # Month
    assert parts[0].isdigit()
    assert parts[1].isdigit()


# ---------------------------------------------------------------------------
# reports_exist_for_month() tests
# ---------------------------------------------------------------------------

def test_reports_exist_all_files_present(tmp_path, monkeypatch):
    """Test reports_exist_for_month returns True when all files exist."""
    # Monkeypatch RESULTAT_DIR to use tmp_path
    from elpris import config
    original_resultat_dir = config.RESULTAT_DIR
    monkeypatch.setattr(config, "RESULTAT_DIR", tmp_path)

    reports_dir = tmp_path / "rapporter"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Create all expected report files for 2026-06
    for park_key, zone in config.PARK_ZONES.items():
        filename = f"performance_{park_key}_{zone}_2026-06.html"
        (reports_dir / filename).write_text(f"<html>Report for {park_key}</html>")

    # Should return True
    assert reports_exist_for_month("2026-06") is True

    # Restore
    monkeypatch.setattr(config, "RESULTAT_DIR", original_resultat_dir)


def test_reports_exist_one_file_missing(tmp_path, monkeypatch):
    """Test reports_exist_for_month returns False when one file is missing."""
    from elpris import config
    original_resultat_dir = config.RESULTAT_DIR
    monkeypatch.setattr(config, "RESULTAT_DIR", tmp_path)

    reports_dir = tmp_path / "rapporter"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Create all but one report file
    parks = list(config.PARK_ZONES.items())
    for park_key, zone in parks[:-1]:  # All except the last one
        filename = f"performance_{park_key}_{zone}_2026-06.html"
        (reports_dir / filename).write_text(f"<html>Report for {park_key}</html>")

    # Should return False
    assert reports_exist_for_month("2026-06") is False

    # Restore
    monkeypatch.setattr(config, "RESULTAT_DIR", original_resultat_dir)


def test_reports_exist_empty_directory(tmp_path, monkeypatch):
    """Test reports_exist_for_month returns False when reports directory is empty."""
    from elpris import config
    original_resultat_dir = config.RESULTAT_DIR
    monkeypatch.setattr(config, "RESULTAT_DIR", tmp_path)

    reports_dir = tmp_path / "rapporter"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # No files created
    # Should return False
    assert reports_exist_for_month("2026-06") is False

    # Restore
    monkeypatch.setattr(config, "RESULTAT_DIR", original_resultat_dir)


def test_reports_exist_wrong_month(tmp_path, monkeypatch):
    """Test reports_exist_for_month with files from a different month."""
    from elpris import config
    original_resultat_dir = config.RESULTAT_DIR
    monkeypatch.setattr(config, "RESULTAT_DIR", tmp_path)

    reports_dir = tmp_path / "rapporter"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Create files for 2026-05, not 2026-06
    for park_key, zone in config.PARK_ZONES.items():
        filename = f"performance_{park_key}_{zone}_2026-05.html"
        (reports_dir / filename).write_text(f"<html>Report for {park_key}</html>")

    # Should return False when checking for 2026-06
    assert reports_exist_for_month("2026-06") is False

    # Restore
    monkeypatch.setattr(config, "RESULTAT_DIR", original_resultat_dir)
