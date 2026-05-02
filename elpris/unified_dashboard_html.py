"""Track A renderer — extends dashboard_v2 with an ASSETS tab.

Strategy: re-use the entire dashboard_v2 HTML body (CAPTURE / BESS / FUTURES
+ the original OPERATIONS plumbing), then perform surgical text substitutions
that rename the OPERATIONS tab into a new ASSETS tab. Subsequent tasks add
the fleet / park-card / table / drill-down UI inside the ASSETS view.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from generate_dashboard_v2 import _build_html as _build_v2_html  # noqa: E402


# ---------------------------------------------------------------------------
# Initial assets-view scaffold (placeholder body — populated in later tasks)
# ---------------------------------------------------------------------------

ASSETS_VIEW_HTML = """
<div id="assets-view" style="display:none">
    <div class="card">
        <div class="card-title">Assets</div>
        <div style="color:var(--text-muted);font-size:0.85rem;line-height:1.5">
            ASSETS-fliken byggs ut i kommande commits: fleet KPI, parkkort,
            j&auml;mf&ouml;relsetabell och drill-down.
        </div>
    </div>
</div>
""".strip()


# ---------------------------------------------------------------------------
# Stub renderAssets so switchDashboard('assets') doesn't error
# ---------------------------------------------------------------------------

ASSETS_JS = r"""
// ================================================================
// ASSETS TAB (stub — populated in later tasks)
// ================================================================
window.renderAssets = function() {};
""".strip()


def _merge_data(unified: dict) -> dict:
    """Build a single DATA dict consumed by both v2 and the new ASSETS tab.

    The v2 body reads top-level keys (zones, profiles, data, operations, …);
    we splat market into the root and attach the asset/meta blobs alongside.
    """
    market = unified.get("market", {}) or {}
    merged = dict(market)
    merged["assets"] = unified.get("assets", {})
    merged["meta"] = unified.get("meta", {})
    if "generated" not in merged:
        merged["generated"] = unified.get("generated", "")
    return merged


def _patch_v2_html(html: str) -> str:
    """Apply the surgical edits that turn dashboard_v2 into the unified Track A."""

    # 1. Update <title>
    html = html.replace(
        "<title>Elpris Dashboard v2</title>",
        "<title>Elpris Unified Dashboard</title>",
        1,
    )

    # 2. Topbar: rename OPERATIONS tab → ASSETS
    html = html.replace(
        '<div class="topbar-title dash-tab" id="tab-operations" onclick="switchDashboard(\'operations\')" style="cursor:pointer"><span>ELPRIS</span> OPERATIONS</div>',
        '<div class="topbar-title dash-tab" id="tab-assets" onclick="switchDashboard(\'assets\')" style="cursor:pointer"><span>ELPRIS</span> ASSETS</div>',
        1,
    )

    # 3. Sidebar block — rename operations-sidebar to assets-sidebar (kept hidden)
    html = html.replace(
        '<aside class="sidebar" id="operations-sidebar" style="display:none"></aside>',
        '<aside class="sidebar" id="assets-sidebar" style="display:none"></aside>',
        1,
    )

    # 4. Replace the entire "<!-- Operations sections -->" block (operations-view div)
    # with the new ASSETS view.
    ops_open = '<!-- Operations sections -->'
    end_marker = '</div>\n        </div>\n    </main>'  # closes operations-view + main wrapper
    if ops_open in html:
        before, _, rest = html.partition(ops_open)
        end_idx = rest.find(end_marker)
        if end_idx != -1:
            after = '</div>\n    </main>' + rest[end_idx + len(end_marker):]
            html = (
                before
                + '<!-- ASSETS sections -->\n        '
                + ASSETS_VIEW_HTML
                + '\n        '
                + after
            )

    # 5. switchDashboard JS — operates on rendered HTML (single braces).
    html = html.replace(
        "['capture', 'bess', 'futures', 'operations'].forEach(t => {",
        "['capture', 'bess', 'futures', 'assets'].forEach(t => {",
        1,
    )
    html = html.replace(
        "document.getElementById('operations-view').style.display = which === 'operations' ? '' : 'none';",
        "document.getElementById('assets-view').style.display = which === 'assets' ? '' : 'none';",
        1,
    )
    html = html.replace(
        "document.getElementById('operations-sidebar').style.display = which === 'operations' ? '' : 'none';",
        "document.getElementById('assets-sidebar').style.display = which === 'assets' ? '' : 'none';",
        1,
    )
    # Disable the now-stale ops-sidebar init (assets-sidebar is empty)
    html = html.replace(
        "if (which === 'operations' && !state.ops_initialized) {",
        "if (false /* assets tab no longer uses ops sidebar */) {",
        1,
    )

    # 6. render() dispatcher — point 'assets' to renderAssets()
    html = html.replace(
        "} else if (state.dashboard === 'operations') {",
        "} else if (state.dashboard === 'assets') {",
        1,
    )
    html = html.replace(
        "        renderOperations();\n    } else {\n        renderForwardCurve();",
        "        renderAssets();\n    } else {\n        renderForwardCurve();",
        1,
    )

    # 7. Inject the ASSETS_JS block just before the GO marker
    html = html.replace(
        "// ================================================================\n// GO\n// ================================================================",
        ASSETS_JS + "\n\n// ================================================================\n// GO\n// ================================================================",
        1,
    )

    return html


def render_track_a(data: dict) -> str:
    """Render the Track A unified dashboard (Bloomberg-dark theme).

    `data` is the dict produced by `elpris.unified_dashboard_data.build_unified_data()`.
    """
    merged = _merge_data(data)
    base = _build_v2_html(merged)
    return _patch_v2_html(base)
