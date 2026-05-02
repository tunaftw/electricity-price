"""Tester för elpris.dashboard_v2_data."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.dashboard_v2_data import load_park_actual_data


# ---------------------------------------------------------------------------
# load_park_actual_data — empty cell handling
# ---------------------------------------------------------------------------

def test_load_park_actual_data_handles_empty_power_mw(tmp_path):
    """Empty `power_mw`-celler ska behandlas som 0 (saknad mätardata),
    inte krascha med ValueError.

    Bazefield CSV-filer kan ha tomma celler för intervall där mätaren
    inte rapporterade. operations_dashboard_data.py-mönstret är att
    behandla tomma värden som 0 — vi följer samma konvention.
    """
    csv_path = tmp_path / "test_park_SE3.csv"
    csv_path.write_text(
        "timestamp,power_mw,active_power_mw,irradiance_poa,availability\n"
        # En rad med tom power_mw — får inte krascha
        "2024-08-27T00:00:00.0000000+02:00,,0.0001,2.2537,\n"
        # En rad med riktigt värde
        "2024-08-27T00:15:00.0000000+02:00,0.5,0.5,2.5,1.0\n"
        # En rad med tom power_mw i en annan timme
        "2024-08-27T01:00:00.0000000+02:00,,0.0,0.0,\n"
    )

    # Måste inte krascha med ValueError
    result = load_park_actual_data(csv_path)

    assert isinstance(result, dict)
    # Tre rader → fördelade över två UTC-timmar (00:00+02 = 22:00 UTC dagen
    # innan, 00:15+02 = 22:15 UTC, 01:00+02 = 23:00 UTC).
    # Värdena från tomma celler ska räknas som 0 i medelvärdet.
    all_values = []
    for date_data in result.values():
        for hour_avg in date_data.values():
            assert isinstance(hour_avg, float)
            all_values.append(hour_avg)
    assert all_values, "Förväntade minst ett aggregerat värde"


def test_load_park_actual_data_all_empty_returns_zero(tmp_path):
    """Om hela timmen är tom → medelvärdet ska vara 0."""
    csv_path = tmp_path / "all_empty_SE3.csv"
    csv_path.write_text(
        "timestamp,power_mw\n"
        "2024-08-27T00:00:00.0000000+02:00,\n"
        "2024-08-27T00:15:00.0000000+02:00,\n"
        "2024-08-27T00:30:00.0000000+02:00,\n"
        "2024-08-27T00:45:00.0000000+02:00,\n"
    )

    result = load_park_actual_data(csv_path)

    # Alla värden ska vara 0.0 eftersom alla power_mw är tomma
    for date_data in result.values():
        for hour_avg in date_data.values():
            assert hour_avg == 0.0
