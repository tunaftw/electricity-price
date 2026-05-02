"""Track A renderer — extends dashboard_v2 with an ASSETS tab.

Entry point: ``render_track_a(unified_data)``. Currently a stub returning a
minimal placeholder. Subsequent tasks layer in: v2 body port, fleet KPIs,
park cards, comparison table, drill-down, and filters.
"""
from __future__ import annotations

import json


def render_track_a(data: dict) -> str:
    """Render the Track A unified dashboard (Bloomberg-dark theme)."""
    summary = (
        f"top-level keys: {sorted(data.keys())}<br>"
        f"market keys: {sorted((data.get('market') or {}).keys())[:8]}<br>"
        f"asset parks: {len((data.get('assets') or {}).get('parks') or {})}"
    )
    return (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<title>Elpris Unified Dashboard (WIP)</title></head>"
        f"<body style='font-family:sans-serif;padding:2rem'><h1>Track A — WIP</h1><p>{summary}</p></body></html>"
    )
