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
        <div class="card-title">Fleet Overview</div>
        <div id="fleet-kpi-row" style="display:flex;gap:1rem;margin-top:0.6rem;flex-wrap:wrap"></div>
    </div>
    <div class="card">
        <div class="card-title">Parker</div>
        <div style="font-size:0.72rem;color:var(--text-muted);margin-top:-0.4rem;margin-bottom:0.8rem;line-height:1.4">
            Klicka p&aring; en park f&ouml;r drill-down. F&auml;rg:
            <span style="color:#4ADE80">gr&ouml;n &ge; +5%</span>,
            <span style="color:#fde68a">gul &plusmn;5%</span>,
            <span style="color:#f87171">r&ouml;d &le; -5%</span> mot budget.
        </div>
        <div id="park-cards-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1rem"></div>
    </div>
</div>
""".strip()


# ---------------------------------------------------------------------------
# CSS additions for the ASSETS tab
# ---------------------------------------------------------------------------

ASSETS_CSS = r"""
/* ===== ASSETS TAB ===== */
.assets-kpi {
    flex: 1 1 160px;
    min-width: 160px;
    background: var(--bg-sidebar);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.7rem 0.9rem;
}
.assets-kpi-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-weight: 600;
    margin-bottom: 0.35rem;
}
.assets-kpi-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text-bright);
    font-family: var(--font-mono);
}
.assets-kpi-sub {
    margin-top: 0.3rem;
    font-size: 0.7rem;
    color: var(--text-muted);
}
.assets-kpi.vsb-green  .assets-kpi-value { color: #4ADE80; }
.assets-kpi.vsb-yellow .assets-kpi-value { color: #fde68a; }
.assets-kpi.vsb-red    .assets-kpi-value { color: #f87171; }
.assets-kpi.vsb-green  { border-left: 3px solid #4ADE80; }
.assets-kpi.vsb-yellow { border-left: 3px solid #fde68a; }
.assets-kpi.vsb-red    { border-left: 3px solid #f87171; }

.park-card {
    background: var(--bg-sidebar);
    border: 1px solid var(--border);
    border-left: 3px solid var(--border);
    border-radius: var(--radius);
    padding: 0.9rem 1rem;
    cursor: pointer;
    transition: transform 0.12s, border-color 0.12s, box-shadow 0.12s;
}
.park-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 14px rgba(0,0,0,0.35);
    border-color: var(--product);
}
.park-card.vsb-green  { border-left-color: #4ADE80; }
.park-card.vsb-yellow { border-left-color: #fde68a; }
.park-card.vsb-red    { border-left-color: #f87171; }
.park-card-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.6rem;
}
.park-card-name {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-bright);
}
.park-card-zone {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-muted);
    background: var(--bg-card);
    padding: 2px 8px;
    border-radius: 4px;
    border: 1px solid var(--border);
}
.park-card-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: var(--text);
    padding: 2px 0;
}
.park-card-row span:first-child { color: var(--text-muted); }
.park-card-spark { margin-top: 0.6rem; }
""".strip()


# ---------------------------------------------------------------------------
# Assets-tab JS module
# ---------------------------------------------------------------------------

ASSETS_JS = r"""
// ================================================================
// ASSETS TAB
// ================================================================
(function() {
    var ASSETS = (window.DATA && DATA.assets) ? DATA.assets : null;

    function vsBudgetClass(pct) {
        if (pct === null || pct === undefined || isNaN(pct)) return '';
        if (pct >= 5) return 'vsb-green';
        if (pct <= -5) return 'vsb-red';
        return 'vsb-yellow';
    }
    function fmtNum(v, d) {
        if (v === null || v === undefined || isNaN(v)) return '–';
        return Number(v).toLocaleString(undefined, {
            minimumFractionDigits: d || 0,
            maximumFractionDigits: d || 0,
        });
    }
    function fmtPct(v, d) {
        if (v === null || v === undefined || isNaN(v)) return '–';
        var sign = v >= 0 ? '+' : '';
        return sign + Number(v).toFixed(d === undefined ? 1 : d) + '%';
    }

    function kpiTile(label, value, sub, cls) {
        return '<div class="assets-kpi ' + (cls || '') + '">' +
            '<div class="assets-kpi-label">' + label + '</div>' +
            '<div class="assets-kpi-value">' + value + '</div>' +
            (sub ? '<div class="assets-kpi-sub">' + sub + '</div>' : '') +
            '</div>';
    }

    function vsBudgetColor(pct) {
        if (pct === null || pct === undefined || isNaN(pct)) return '#8892a4';
        if (pct >= 5) return '#4ADE80';
        if (pct <= -5) return '#f87171';
        return '#fde68a';
    }

    function latestMonthKey() {
        if (!ASSETS || !ASSETS.parks) return null;
        var maxKey = null;
        Object.values(ASSETS.parks).forEach(function(p) {
            (p.months || []).forEach(function(m) {
                var k = m.year + '-' + String(m.month).padStart(2, '0');
                if (maxKey === null || k > maxKey) maxKey = k;
            });
        });
        return maxKey;
    }

    function parkMonth(park, monthKey) {
        return (park.months || []).find(function(m) {
            return (m.year + '-' + String(m.month).padStart(2, '0')) === monthKey;
        });
    }

    function sparkline(months) {
        if (!months || months.length === 0) return '';
        var W = 96, H = 26;
        var BARW = Math.max(2, Math.floor(W / months.length) - 1);
        var max = Math.max.apply(null, months.map(function(m) { return m.energy_mwh || 0; })) || 1;
        var bars = months.map(function(m, i) {
            var v = (m.energy_mwh || 0) / max;
            var h = Math.max(1, Math.round(H * v));
            return '<rect x="' + (i * (BARW + 1)) + '" y="' + (H - h) +
                '" width="' + BARW + '" height="' + h + '" fill="#67e8f9" opacity="0.85"/>';
        }).join('');
        return '<svg width="' + W + '" height="' + H + '" style="display:block">' + bars + '</svg>';
    }

    function renderFleetKPIs() {
        var fleet = ASSETS && ASSETS.fleet;
        var row = document.getElementById('fleet-kpi-row');
        if (!fleet) {
            row.innerHTML = '<div style="color:var(--text-muted);padding:1rem">Ingen fleet-data.</div>';
            return;
        }
        var tiles = [
            kpiTile('Parker', fleet.park_count, ''),
            kpiTile('Installerat', fmtNum(fleet.total_capacity_mwp, 1) + ' MWp', ''),
            kpiTile(fleet.latest_month + ' Energi',
                    fmtNum(fleet.total_energy_mwh, 0) + ' MWh', ''),
            kpiTile('vs Budget', fmtPct(fleet.vs_budget_pct, 1), '',
                    vsBudgetClass(fleet.vs_budget_pct)),
        ];
        row.innerHTML = tiles.join('');
    }

    function renderParkCards() {
        var monthKey = latestMonthKey();
        var grid = document.getElementById('park-cards-grid');
        if (!ASSETS || !ASSETS.parks) {
            grid.innerHTML = '<div style="color:var(--text-muted)">Inga parker.</div>';
            return;
        }
        var entries = Object.entries(ASSETS.parks);
        grid.innerHTML = entries.map(function(e) {
            var pk = e[0], p = e[1];
            var m = parkMonth(p, monthKey);
            var vs = m ? m.vs_budget_pct : null;
            var spark = sparkline(p.months || []);
            return '<div class="park-card ' + vsBudgetClass(vs) + '" data-park="' + pk + '" onclick="window.assetsOnPark && window.assetsOnPark(\'' + pk + '\')">' +
                '<div class="park-card-head">' +
                    '<div class="park-card-name">' + (p.name || pk) + '</div>' +
                    '<div class="park-card-zone">' + (p.zone || '') + '</div>' +
                '</div>' +
                '<div class="park-card-row"><span>Kapacitet</span><span>' + fmtNum(p.capacity_mwp, 2) + ' MWp</span></div>' +
                '<div class="park-card-row"><span>Energi (' + (monthKey || '-') + ')</span><span>' + (m ? fmtNum(m.energy_mwh, 0) + ' MWh' : '–') + '</span></div>' +
                '<div class="park-card-row"><span>Budget</span><span>' + (m ? fmtNum(m.budget_mwh, 0) + ' MWh' : '–') + '</span></div>' +
                '<div class="park-card-row" style="font-weight:700;color:' + vsBudgetColor(vs) + '"><span>vs Budget</span><span>' + (m ? fmtPct(vs) : '–') + '</span></div>' +
                '<div class="park-card-row"><span>Yield</span><span>' + (m ? fmtNum(m.yield_kwh_kwp, 1) + ' kWh/kWp' : '–') + '</span></div>' +
                '<div class="park-card-spark">' + spark + '</div>' +
            '</div>';
        }).join('');
    }

    // Default click handler — overridden when drill-down is wired in.
    window.assetsOnPark = function(pk) { console.log('park click:', pk); };

    window.renderAssets = function() {
        if (!ASSETS) {
            document.getElementById('assets-view').innerHTML =
                '<div style="padding:2rem;color:var(--text-muted)">Ingen asset-data tillg&auml;nglig.</div>';
            return;
        }
        renderFleetKPIs();
        renderParkCards();
    };
})();
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

    # 0. Inject ASSETS CSS just before </style>
    html = html.replace("</style>", ASSETS_CSS + "\n</style>", 1)

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
