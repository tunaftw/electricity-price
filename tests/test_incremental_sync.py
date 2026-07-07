"""Tester för inkrementell synk-resiliens (P2a).

get_latest_timestamp i esett/entsoe/mimer läste tidigare bara den NYASTE
årsfilen. Om den är tom (header-only, t.ex. en nyss touchad nästa-års-fil)
returnerades None → inkrementell logik tvingade full historik-omhämtning.
Fixen (som storage.py redan har): gå nyaste→äldsta tills en fil med data hittas.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris import entsoe, esett, mimer  # noqa: E402

_HEADER = "time_start,value\n"


def _write(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HEADER + "".join(rows), encoding="utf-8")


def test_esett_falls_back_to_older_file_when_newest_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(esett, "ESETT_DIR", tmp_path)
    zone_dir = tmp_path / "imbalance" / "SE3"
    _write(zone_dir / "2025.csv", ["2025-12-31T23:00:00Z,1\n"])
    _write(zone_dir / "2026.csv", [])  # header only

    ts = esett.get_latest_timestamp("SE3")
    assert ts is not None
    assert (ts.year, ts.month, ts.day) == (2025, 12, 31)


def test_entsoe_falls_back_to_older_file_when_newest_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(entsoe, "ENTSOE_DIR", tmp_path)
    gen_dir = tmp_path / "generation" / "SE3"
    _write(gen_dir / "solar_2025.csv", ["2025-12-31T22:00:00+00:00,1\n"])
    _write(gen_dir / "solar_2026.csv", [])

    ts = entsoe.get_latest_timestamp("SE3", "solar")
    assert ts is not None
    assert (ts.year, ts.month, ts.day) == (2025, 12, 31)


def test_mimer_falls_back_to_older_file_when_newest_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(mimer, "MIMER_DIR", tmp_path)
    prod_dir = tmp_path / "fcr"
    _write(prod_dir / "2025.csv", ["2025-12-31T23:00:00,1\n"])
    _write(prod_dir / "2026.csv", [])

    ts = mimer.get_latest_timestamp("fcr")
    assert ts is not None
    assert (ts.year, ts.month, ts.day) == (2025, 12, 31)


def test_returns_none_when_all_files_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(mimer, "MIMER_DIR", tmp_path)
    prod_dir = tmp_path / "fcr"
    _write(prod_dir / "2025.csv", [])
    _write(prod_dir / "2026.csv", [])

    assert mimer.get_latest_timestamp("fcr") is None
