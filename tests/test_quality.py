"""Tester för elpris.quality — datakvalitetsmodulen."""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.quality import check_spot_price_file


def _write_csv(tmp_path: Path, content: str) -> Path:
    """Skriv en test-CSV och returnera sökvägen."""
    f = tmp_path / "2024.csv"
    f.write_text(dedent(content).strip(), encoding="utf-8")
    return f


def test_clean_data_no_issues(tmp_path):
    """En komplett 3-timmarsperiod ska inte ge några issues."""
    csv = _write_csv(tmp_path, """
        time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR
        2024-06-01T00:00:00+02:00,2024-06-01T01:00:00+02:00,0.50,0.05,10.0
        2024-06-01T01:00:00+02:00,2024-06-01T02:00:00+02:00,0.45,0.045,10.0
        2024-06-01T02:00:00+02:00,2024-06-01T03:00:00+02:00,0.40,0.04,10.0
    """)
    issues, n = check_spot_price_file(csv, "SE3", 2024)
    assert n == 3
    assert [i for i in issues if i.severity == "error"] == []
    assert [i for i in issues if i.severity == "warning"] == []


def test_detects_real_gap(tmp_path):
    """En saknad timme ska flaggas som riktigt gap."""
    csv = _write_csv(tmp_path, """
        time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR
        2024-06-01T00:00:00+02:00,2024-06-01T01:00:00+02:00,0.50,0.05,10.0
        2024-06-01T02:00:00+02:00,2024-06-01T03:00:00+02:00,0.40,0.04,10.0
    """)
    issues, _ = check_spot_price_file(csv, "SE3", 2024)
    gap_issues = [i for i in issues if i.kind == "gap"]
    assert len(gap_issues) == 1
    assert gap_issues[0].severity == "warning"  # 60 min = warning (< 120)
    assert "1 riktig(a)" in gap_issues[0].message


def test_detects_duplicate(tmp_path):
    """Duplicerade timestamps ska flaggas som error."""
    csv = _write_csv(tmp_path, """
        time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR
        2024-06-01T00:00:00+02:00,2024-06-01T01:00:00+02:00,0.50,0.05,10.0
        2024-06-01T00:00:00+02:00,2024-06-01T01:00:00+02:00,0.51,0.051,10.0
    """)
    issues, _ = check_spot_price_file(csv, "SE3", 2024)
    dup_issues = [i for i in issues if i.kind == "duplicate"]
    assert len(dup_issues) == 1
    assert dup_issues[0].severity == "error"


def test_dst_fall_transition_not_flagged(tmp_path):
    """DST höst-övergång ska inte flaggas som gap."""
    # Höst-DST 2024: 27 okt 03:00 CEST → 02:00 CET
    csv = _write_csv(tmp_path, """
        time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR
        2024-10-27T01:00:00+02:00,2024-10-27T02:00:00+02:00,0.50,0.05,10.0
        2024-10-27T02:00:00+02:00,2024-10-27T03:00:00+01:00,0.50,0.05,10.0
        2024-10-27T02:00:00+01:00,2024-10-27T03:00:00+01:00,0.50,0.05,10.0
        2024-10-27T03:00:00+01:00,2024-10-27T04:00:00+01:00,0.50,0.05,10.0
    """)
    issues, _ = check_spot_price_file(csv, "SE3", 2024)
    gap_issues = [i for i in issues if i.kind == "gap"]
    assert gap_issues == [], f"DST should not flag gaps but got: {[i.message for i in gap_issues]}"


def test_dst_spring_transition_not_flagged(tmp_path):
    """DST vår-övergång ska inte flaggas som gap."""
    # Vår-DST 2024: 31 mar 02:00 CET → 03:00 CEST
    csv = _write_csv(tmp_path, """
        time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR
        2024-03-31T00:00:00+01:00,2024-03-31T01:00:00+01:00,0.50,0.05,10.0
        2024-03-31T01:00:00+01:00,2024-03-31T03:00:00+02:00,0.50,0.05,10.0
        2024-03-31T03:00:00+02:00,2024-03-31T04:00:00+02:00,0.50,0.05,10.0
    """)
    issues, _ = check_spot_price_file(csv, "SE3", 2024)
    gap_issues = [i for i in issues if i.kind == "gap"]
    assert gap_issues == [], f"Spring DST should not flag gaps but got: {[i.message for i in gap_issues]}"


def test_detects_extreme_price(tmp_path):
    """Orimligt höga/låga priser ska flaggas som varning."""
    csv = _write_csv(tmp_path, """
        time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR
        2024-06-01T00:00:00+02:00,2024-06-01T01:00:00+02:00,0.50,0.05,10.0
        2024-06-01T01:00:00+02:00,2024-06-01T02:00:00+02:00,50.00,5.0,10.0
        2024-06-01T02:00:00+02:00,2024-06-01T03:00:00+02:00,-10.00,-1.0,10.0
    """)
    issues, _ = check_spot_price_file(csv, "SE3", 2024)
    extreme_issues = [i for i in issues if i.kind == "extreme_price"]
    assert len(extreme_issues) == 2
    assert all(i.severity == "warning" for i in extreme_issues)


def test_detects_large_gap_as_error(tmp_path):
    """Luckor > 120 min ska bli error, inte warning."""
    csv = _write_csv(tmp_path, """
        time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR
        2024-06-01T00:00:00+02:00,2024-06-01T01:00:00+02:00,0.50,0.05,10.0
        2024-06-01T05:00:00+02:00,2024-06-01T06:00:00+02:00,0.40,0.04,10.0
    """)
    issues, _ = check_spot_price_file(csv, "SE3", 2024)
    gap_issues = [i for i in issues if i.kind == "gap"]
    assert len(gap_issues) == 1
    assert gap_issues[0].severity == "error"


def test_missing_file(tmp_path):
    """Saknad fil ska flaggas som error."""
    missing = tmp_path / "nonexistent.csv"
    issues, n = check_spot_price_file(missing, "SE3", 2024)
    assert n == 0
    assert any(i.kind == "missing_file" for i in issues)


def test_parse_error(tmp_path):
    """Felformaterade rader ska flaggas."""
    csv = _write_csv(tmp_path, """
        time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR
        not-a-date,2024-06-01T01:00:00+02:00,0.50,0.05,10.0
    """)
    issues, _ = check_spot_price_file(csv, "SE3", 2024)
    assert any(i.kind == "parse_error" for i in issues)


def test_real_data_se2_2022_gap(tmp_path):
    """Regressions-test: SE2/2022 har 4 riktiga luckor (från riktig data)."""
    # Detta är riktiga data-rader från SE2/2022 runt den första luckan
    csv = _write_csv(tmp_path, """
        time_start,time_end,SEK_per_kWh,EUR_per_kWh,EXR
        2022-09-04T22:00:00+02:00,2022-09-04T23:00:00+02:00,2.58,0.24,10.74
        2022-09-05T00:00:00+02:00,2022-09-05T01:00:00+02:00,1.96,0.18,10.73
    """)
    issues, _ = check_spot_price_file(csv, "SE2", 2022)
    gap_issues = [i for i in issues if i.kind == "gap"]
    assert len(gap_issues) == 1
    # Timmen 23:00-00:00 saknas
    assert "1 riktig(a)" in gap_issues[0].message
