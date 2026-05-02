"""Unified dashboard data — Phase 1 backend.

Aggregerar data från befintliga moduler (dashboard_v2_data,
operations_dashboard_data, performance_report_data) till en enda
JSON-serialiserbar struktur som de fyra unified-flikarna
(CAPTURE / BESS / FUTURES / ASSETS) konsumerar.

Library-modul: ingen CLI / ingen `__main__`-block.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from .dashboard_v2_data import calculate_dashboard_v2_data


def _empty_market() -> Dict[str, Any]:
    """Tom market-struktur när dashboard_v2_data inte kan beräknas
    (t.ex. på grund av datafel eller saknade källor).
    """
    return {
        "zones": [],
        "profiles": {},
        "colors": {},
        "data": {},
    }


def _build_market_section() -> Dict[str, Any]:
    """Hämta marknadsdata från dashboard_v2_data.

    Returnerar dict med zones, profiles, colors, data, validation,
    heatmap, operations, forward (om tillgängligt) m.fl. Vid fel i
    underliggande beräkning returneras en tom struktur så att unified
    builder fortfarande är användbar.
    """
    try:
        return calculate_dashboard_v2_data()
    except Exception as exc:
        # Logga men låt bygget fortsätta — bättre med partial data än crash.
        print(f"[unified_dashboard] market beräkning misslyckades: {exc}")
        return _empty_market()


def _build_meta_section(market: Dict[str, Any]) -> Dict[str, Any]:
    """Plocka ut zones/profiles/colors från market för frontend-rendering."""
    return {
        "zones": market.get("zones", []),
        "profiles": market.get("profiles", {}),
        "colors": market.get("colors", {}),
    }


def build_unified_data() -> Dict[str, Any]:
    """Bygger den samlade datastrukturen för unified dashboard.

    Returnerar en JSON-serialiserbar dict med top-level keys:
        - generated: ISO-timestamp för när data byggdes
        - market: marknadsdata (zoner, capture-priser, BESS, futures)
        - assets: per-park KPI:er + flotta-översikt
        - meta: zoner, profiler, färger (för frontend-rendering)
    """
    market = _build_market_section()
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "market": market,
        "assets": {},
        "meta": _build_meta_section(market),
    }
