"""Tester för elpris.unified_dashboard_data — Phase 1 backend för unified dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.unified_dashboard_data import build_unified_data


# ---------------------------------------------------------------------------
# Task 1.1 — scaffold
# ---------------------------------------------------------------------------

def test_build_unified_data_top_level_keys():
    """build_unified_data() ska returnera dict med top-level keys."""
    data = build_unified_data()
    assert isinstance(data, dict)
    for key in ("generated", "market", "assets", "meta"):
        assert key in data, f"Saknar top-level key: {key}"
