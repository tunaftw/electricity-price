"""Tester för load_incidents (Sektion 17 — manuell incident/work-log JSON).

Täcker: saknad fil, giltig fil, trasig JSON, saknade valfria fält,
saknade toppnivå-nycklar. Monkeypatchar elpris.config.RESULTAT_DIR enligt
mönstret i tests/test_update_all_auto_reports.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris import config  # noqa: E402
from elpris.performance_report_data import (  # noqa: E402
    Incident,
    WorkLogEntry,
    load_incidents,
)


def _incidenter_dir(tmp_path: Path) -> Path:
    d = tmp_path / "operationsdata" / "incidenter"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_missing_file_returns_empty_and_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTAT_DIR", tmp_path)

    incidents, work_log, has_data = load_incidents("horby", 2026, 6)

    assert incidents == []
    assert work_log == []
    assert has_data is False


def test_valid_file_parses_both_lists(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTAT_DIR", tmp_path)
    d = _incidenter_dir(tmp_path)
    payload = {
        "incidents": [
            {
                "date": "2026-06-14",
                "issue_id": 574,
                "fault_type": "Inverter Failure",
                "equipment": "INV 1-4",
                "description": "Inverter offline",
                "start": "2026-06-14T17:36:00",
                "end": "2026-06-14T17:44:00",
                "priority": "Med",
                "status": "Resolved",
                "gen_loss_kwh": 12.5,
            }
        ],
        "work_carried_out": [
            {
                "date": "2026-06-22",
                "activity": "Visuell inspektion paneler",
                "status": "Completed",
                "remarks": "Inga avvikelser",
            }
        ],
    }
    (d / "horby_2026-06.json").write_text(json.dumps(payload), encoding="utf-8")

    incidents, work_log, has_data = load_incidents("horby", 2026, 6)

    assert has_data is True
    assert len(incidents) == 1
    assert isinstance(incidents[0], Incident)
    assert incidents[0].date == "2026-06-14"
    assert incidents[0].issue_id == 574
    assert incidents[0].fault_type == "Inverter Failure"
    assert incidents[0].gen_loss_kwh == 12.5

    assert len(work_log) == 1
    assert isinstance(work_log[0], WorkLogEntry)
    assert work_log[0].activity == "Visuell inspektion paneler"


def test_malformed_json_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTAT_DIR", tmp_path)
    d = _incidenter_dir(tmp_path)
    (d / "horby_2026-06.json").write_text("{not valid json,,,", encoding="utf-8")

    incidents, work_log, has_data = load_incidents("horby", 2026, 6)

    assert incidents == []
    assert work_log == []
    assert has_data is False


def test_missing_optional_fields_default_to_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTAT_DIR", tmp_path)
    d = _incidenter_dir(tmp_path)
    payload = {
        "incidents": [{"date": "2026-06-01"}],
        "work_carried_out": [{"date": "2026-06-02"}],
    }
    (d / "horby_2026-06.json").write_text(json.dumps(payload), encoding="utf-8")

    incidents, work_log, has_data = load_incidents("horby", 2026, 6)

    assert has_data is True
    assert incidents == [Incident(date="2026-06-01")]
    assert work_log == [WorkLogEntry(date="2026-06-02")]


def test_missing_top_level_keys_yield_empty_lists(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTAT_DIR", tmp_path)
    d = _incidenter_dir(tmp_path)
    (d / "horby_2026-06.json").write_text("{}", encoding="utf-8")

    incidents, work_log, has_data = load_incidents("horby", 2026, 6)

    assert incidents == []
    assert work_log == []
    assert has_data is True
