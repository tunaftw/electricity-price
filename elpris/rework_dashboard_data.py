"""Datakomposition för rework-dashboarden.

Anropar ``build_unified_data()`` EN gång (den beprövade pipelinen för
park-KPI:er, capture per profil, forward m.m.), **beskär** payloaden
till det som faktiskt renderas, och lägger till rework-analyserna:
marknadsstatistik, cannibalisering, orientering, obalans, PPA-vy,
datakvalitet och klartext-insikter.

Pruning-funktionerna är rena (dict in → dict ut) och enhetstestas i
``tests/test_rework_analysis.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .rework_capture_analysis import build_cannibalization, build_orientation
from .rework_imbalance import build_imbalance_analysis
from .rework_market_analysis import build_market_analysis
from .rework_portfolio import (
    build_data_quality,
    build_insights,
    build_portfolio_overview,
    build_ppa_view,
)

# Profiler vi behåller ur market["data"] (zon-capture).
CAPTURE_PROFILE_KEYS = ["baseload", "sol_syd", "sol_ov", "sol_tracker"]

# Granulariteter vi behåller (dagliga serier slängs — rework renderar
# månads/års-nivå; park-dagligt finns i assets.daily_by_month).
CAPTURE_GRANULARITIES = ["yearly", "monthly"]

# Forward-nycklar vi behåller (forward_history med dagliga serier per
# kontrakt slängs — kurva + realiserat räcker för rework-vyn).
FORWARD_KEEP_KEYS = [
    "settlement_date", "contracts", "expired_contracts",
    "sys", "epad", "zone_fwd", "spot_realized",
]


def prune_capture_data(market_data: Dict[str, Any]) -> Dict[str, Any]:
    """Behåll baseload + solprofiler, yearly+monthly, per zon."""
    out: Dict[str, Any] = {}
    for zone, profiles in (market_data or {}).items():
        zone_out: Dict[str, Any] = {}
        for key in CAPTURE_PROFILE_KEYS:
            prof = profiles.get(key)
            if not prof:
                continue
            kept = {
                g: prof[g] for g in CAPTURE_GRANULARITIES if g in prof
            }
            if kept:
                zone_out[key] = kept
        if zone_out:
            out[zone] = zone_out
    return out


def prune_forward(forward: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Släng dagliga settlement-serier; behåll kurva + realiserat."""
    if not forward:
        return None
    return {k: forward[k] for k in FORWARD_KEEP_KEYS if k in forward}


def prune_operations(operations: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Behåll specific yield + tracker-gain (neg-pris ligger i assets)."""
    ops = operations or {}
    return {
        "specific_yield": ops.get("specific_yield", {}),
        "tracker_gain": ops.get("tracker_gain", []),
        "park_capacity_kwp": ops.get("park_capacity_kwp", {}),
        "park_zones": ops.get("park_zones", {}),
    }


def _coverage_meta(
    market_analysis: Dict[str, Any],
    assets: Dict[str, Any],
    forward: Optional[Dict[str, Any]],
    imbalance: Dict[str, Any],
    cannibalization: Dict[str, Any],
) -> Dict[str, Any]:
    """Täckningsinfo för footern: 'data t.o.m.' per källa."""
    spot_last = None
    for zone_data in market_analysis.get("zones", {}).values():
        ts = zone_data.get("last_ts")
        if ts and (spot_last is None or ts > spot_last):
            spot_last = ts

    park_last = None
    for park in (assets or {}).get("parks", {}).values():
        ts = park.get("last_data_ts")
        if ts and (park_last is None or ts > park_last):
            park_last = ts

    esett_last = None
    for zone_data in imbalance.get("zones", {}).values():
        months = zone_data.get("monthly") or []
        if months:
            m = months[-1]["month"]
            if esett_last is None or m > esett_last:
                esett_last = m

    installed_last = None
    for recs in (
        cannibalization.get("installed", {}).get("solar", {}).values()
    ):
        if recs:
            y = recs[-1]["year"]
            if installed_last is None or y > installed_last:
                installed_last = y

    return {
        "spot_through": spot_last[:10] if spot_last else None,
        "parks_through": park_last[:10] if park_last else None,
        "futures_through": (forward or {}).get("settlement_date"),
        "esett_through": esett_last,
        "installed_through": installed_last,
    }


def build_rework_data() -> Dict[str, Any]:
    """Bygg hela datastrukturen för rework-dashboarden.

    Returns:
        JSON-serialiserbar dict med nycklarna ``generated``, ``meta``,
        ``portfolio``, ``assets``, ``capture``, ``validation``,
        ``forward``, ``operations``, ``market_analysis``,
        ``cannibalization``, ``orientation``, ``imbalance``, ``ppa``,
        ``data_quality``, ``insights``.
    """
    # Importeras här så att modulen kan importeras (för tester av rena
    # funktioner) utan att dra in hela unified-kedjan.
    from .unified_dashboard_data import build_unified_data

    print("Bygger unified-data (återanvänd pipeline)...")
    unified = build_unified_data()
    market = unified.get("market", {}) or {}
    assets = unified.get("assets", {}) or {}

    print("Bygger rework-analyser...")
    market_analysis = build_market_analysis()
    cannibalization = build_cannibalization(market.get("data", {}) or {})
    orientation = build_orientation(market.get("data", {}) or {})
    imbalance = build_imbalance_analysis()

    portfolio = build_portfolio_overview(assets)
    forward = prune_forward(market.get("forward"))
    ppa = build_ppa_view(assets, forward)
    print("Bygger datakvalitet...")
    data_quality = build_data_quality()

    insights = build_insights(
        portfolio=portfolio,
        market_analysis=market_analysis,
        cannibalization=cannibalization,
        orientation=orientation,
        imbalance=imbalance,
        ppa_view=ppa,
    )

    meta = {
        "zones": market.get("zones", []),
        "coverage": _coverage_meta(
            market_analysis, assets, forward, imbalance, cannibalization
        ),
    }

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "meta": meta,
        "portfolio": portfolio,
        "assets": assets,
        "capture": prune_capture_data(market.get("data", {}) or {}),
        "validation": market.get("validation", {}),
        "forward": forward,
        "operations": prune_operations(market.get("operations")),
        "market_analysis": market_analysis,
        "cannibalization": cannibalization,
        "orientation": orientation,
        "imbalance": imbalance,
        "ppa": ppa,
        "data_quality": data_quality,
        "insights": insights,
    }
