#!/usr/bin/env python3
"""Generate Dashboard v2 — interactive drill-down electricity price dashboard.

Dark Bloomberg-inspired theme with Plotly.js. Drill-down: year → month → day.
Capture prices for solar (3 profiles), wind, hydro, nuclear.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.dashboard_v2_data import calculate_dashboard_v2_data


def _build_html(data: dict) -> str:
    data_json = json.dumps(data, ensure_ascii=False, indent=None)

    html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Elpris Dashboard v2</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
    --bg: #1a1a2e;
    --bg-card: #16213e;
    --bg-sidebar: #0f1629;
    --bg-hover: #1e2d4a;
    --text: #e0e0e0;
    --text-muted: #8892a4;
    --text-bright: #ffffff;
    --border: #2a3550;
    --accent: #4a9eff;
    --accent-dim: rgba(74, 158, 255, 0.15);
    --font: 'SF Pro Display', 'Segoe UI', system-ui, -apple-system, sans-serif;
    --font-mono: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
    --radius: 8px;
    --shadow: 0 2px 8px rgba(0,0,0,0.3);

    /* Product color system — swapped per dashboard */
    --product: #E8A04B;
    --product-dim: rgba(232, 160, 75, 0.15);
    --product-glow: rgba(232, 160, 75, 0.35);
    --product-hint: rgba(232, 160, 75, 0.30);
    --product-contrast: #0b1220;
}}
body.product-capture {{
    --product: #E8A04B;
    --product-dim: rgba(232, 160, 75, 0.15);
    --product-glow: rgba(232, 160, 75, 0.35);
    --product-hint: rgba(232, 160, 75, 0.30);
    --product-contrast: #0b1220;
}}
body.product-bess {{
    --product: #2DD4BF;
    --product-dim: rgba(45, 212, 191, 0.15);
    --product-glow: rgba(45, 212, 191, 0.35);
    --product-hint: rgba(45, 212, 191, 0.30);
    --product-contrast: #0b1220;
}}
body.product-futures {{
    --product: #A78BFA;
    --product-dim: rgba(167, 139, 250, 0.15);
    --product-glow: rgba(167, 139, 250, 0.35);
    --product-hint: rgba(167, 139, 250, 0.30);
    --product-contrast: #0b1220;
}}

html {{ scroll-behavior: smooth; }}
body {{
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    min-height: 100vh;
    overflow-x: hidden;
}}

/* ===== Topbar ===== */
.topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.8rem 1.5rem;
    background: linear-gradient(135deg, #0f1629 0%, #1a1a2e 100%);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
}}
.topbar-title {{
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--text-bright);
    letter-spacing: -0.01em;
}}
.topbar-title span {{
    color: var(--accent);
}}
.zone-buttons {{
    display: flex;
    gap: 4px;
}}
.zone-btn {{
    padding: 6px 16px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.15s;
    font-family: var(--font);
}}
.zone-btn:hover {{
    background: var(--bg-hover);
    color: var(--text);
}}
.zone-btn.active {{
    background: var(--product);
    color: var(--product-contrast);
    border-color: var(--product);
}}
.topbar-meta {{
    font-size: 0.75rem;
    color: var(--text-muted);
}}

/* ===== Layout ===== */
.layout {{
    display: flex;
    min-height: calc(100vh - 52px);
}}

/* ===== Sidebar ===== */
.sidebar {{
    width: 220px;
    min-width: 220px;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border);
    padding: 1rem 0;
    overflow-y: auto;
}}
.sidebar-section {{
    padding: 0 1rem;
    margin-bottom: 1.2rem;
}}
.sidebar-title {{
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
}}
.sidebar-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    cursor: pointer;
    font-size: 0.82rem;
    color: var(--text);
    user-select: none;
}}
.sidebar-item:hover {{
    color: var(--text-bright);
}}
.sidebar-item input[type="checkbox"] {{
    appearance: none;
    -webkit-appearance: none;
    width: 14px;
    height: 14px;
    border: 2px solid var(--border);
    border-radius: 3px;
    cursor: pointer;
    position: relative;
    flex-shrink: 0;
}}
.sidebar-item input[type="checkbox"]:checked {{
    border-color: var(--product);
    background: var(--product);
}}
.sidebar-item input[type="checkbox"]:checked::after {{
    content: '';
    position: absolute;
    top: 1px;
    left: 4px;
    width: 4px;
    height: 7px;
    border: solid var(--product-contrast);
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
}}
.color-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}}

/* ===== Main Content ===== */
.main {{
    flex: 1;
    padding: 1.2rem;
    overflow-y: auto;
}}

/* ===== Breadcrumb ===== */
.breadcrumb {{
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 1rem;
    font-size: 0.85rem;
}}
.breadcrumb-item {{
    color: var(--product);
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    transition: background 0.15s;
}}
.breadcrumb-item:hover {{
    background: var(--product-dim);
}}
.breadcrumb-current {{
    color: var(--text-bright);
    font-weight: 600;
}}
.breadcrumb-sep {{
    color: var(--text-muted);
    font-size: 0.7rem;
}}

/* ===== Cards ===== */
.card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.2rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow);
}}
.card-title {{
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-bright);
    margin-bottom: 0.8rem;
}}

/* ===== Charts ===== */
.chart-container {{
    width: 100%;
    min-height: 420px;
}}
.chart-secondary {{
    min-height: 250px;
}}

/* ===== Summary Stats ===== */
.stats-row {{
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
}}
.stat-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.8rem 1.2rem;
    flex: 1;
    min-width: 140px;
}}
.stats-row .stat-card:first-child {{
    box-shadow: inset 3px 0 0 var(--product);
}}
.stat-label {{
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    margin-bottom: 2px;
}}
.stat-value {{
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text-bright);
    font-family: var(--font-mono);
}}
.stat-unit {{
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 400;
}}

/* ===== Footer ===== */
.footer {{
    padding: 1rem 1.5rem;
    text-align: center;
    font-size: 0.72rem;
    color: var(--text-muted);
    border-top: 1px solid var(--border);
}}
.footer a {{ color: var(--accent); text-decoration: none; }}
.footer a:hover {{ text-decoration: underline; }}

/* ===== Dashboard tabs ===== */
.dash-tab {{
    transition: opacity 0.2s, border-color 0.2s, box-shadow 0.2s;
    padding-bottom: 8px;
    border-bottom: 2px solid transparent;
    opacity: 0.4;
}}
.dash-tab:hover {{ opacity: 0.8; }}
.dash-tab.active {{
    opacity: 1;
    border-bottom-color: var(--product);
    box-shadow: 0 2px 12px -2px var(--product-glow);
}}
.dash-tab:not(.active):hover {{
    border-bottom-color: var(--product-hint);
}}

/* ===== Focus rings ===== */
button:focus-visible,
.dash-tab:focus-visible,
.zone-btn:focus-visible,
.sidebar-item:focus-visible,
.breadcrumb-item:focus-visible {{
    outline: 2px solid var(--product);
    outline-offset: 2px;
}}

/* ===== Responsive ===== */
@media (max-width: 768px) {{
    .sidebar {{ display: none; }}
    .topbar {{ flex-wrap: wrap; gap: 0.5rem; }}
    .layout {{ flex-direction: column; }}
}}
</style>
</head>
<body class="product-capture">

<!-- Topbar -->
<div class="topbar">
    <div style="display:flex;align-items:center;gap:1.2rem">
        <div class="topbar-title dash-tab active" id="tab-capture" onclick="switchDashboard('capture')" style="cursor:pointer"><span>ELPRIS</span> CAPTURE</div>
        <div class="topbar-title dash-tab" id="tab-bess" onclick="switchDashboard('bess')" style="cursor:pointer"><span>ELPRIS</span> BESS</div>
        <div class="topbar-title dash-tab" id="tab-futures" onclick="switchDashboard('futures')" style="cursor:pointer"><span>ELPRIS</span> FUTURES</div>
    </div>
    <div class="zone-buttons" id="zone-buttons"></div>
    <div class="topbar-meta">Genererad: {data["generated"][:10]}</div>
</div>

<!-- Layout -->
<div class="layout">

    <!-- Sidebar (capture only) -->
    <aside class="sidebar" id="sidebar"></aside>
    <!-- Sidebar (BESS only) -->
    <aside class="sidebar" id="bess-sidebar" style="display:none"></aside>

    <!-- Main -->
    <main class="main">
        <!-- Capture sections -->
        <div id="capture-view">
            <div class="breadcrumb" id="breadcrumb"></div>
            <div class="stats-row" id="stats-row"></div>
            <div class="card">
                <div class="card-title" id="chart-title">Capture Prices</div>
                <div id="main-chart" class="chart-container"></div>
            </div>
            <div class="card">
                <div class="card-title">Capture Ratio (capture / baseload)</div>
                <div id="ratio-chart" class="chart-container chart-secondary"></div>
            </div>
        </div>
        <!-- BESS sections -->
        <div id="bess-view" style="display:none">
            <div style="display:flex;gap:1rem;margin-bottom:0.8rem;align-items:center">
                <span style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);font-weight:600">Enhet:</span>
                <div style="display:flex;gap:4px">
                    <button id="unit-per-mw" onclick="setBessUnit('per_mw')" style="padding:6px 14px;border:1px solid var(--border);background:var(--product);color:var(--product-contrast);font-size:0.75rem;font-weight:600;cursor:pointer;border-radius:6px;font-family:var(--font)">EUR/MW</button>
                    <button id="unit-per-mwh" onclick="setBessUnit('per_mwh')" style="padding:6px 14px;border:1px solid var(--border);background:transparent;color:var(--text-muted);font-size:0.75rem;font-weight:600;cursor:pointer;border-radius:6px;font-family:var(--font)">EUR/MWh</button>
                </div>
            </div>
            <div style="padding:0.6rem 0.9rem;margin-bottom:0.8rem;background:rgba(167,139,250,0.08);border-left:3px solid #a78bfa;border-radius:4px;font-size:0.75rem;color:var(--text-muted);line-height:1.5">
                <strong style="color:var(--text)">Revenue stacking caveat:</strong> Stödtjänster (FCR/aFRR/mFRR-CM) och arbitrage kan inte staplas fullt ut &mdash; samma batterikapacitet kan inte samtidigt vara bokad i flera marknader. Siffrorna visar <em>teoretisk maxintäkt per marknad</em> vid 100% tillgänglighet. Aktivera profiler individuellt eller jämför dem med reservation.
            </div>
            <div class="breadcrumb" id="bess-breadcrumb"></div>
            <div class="stats-row" id="bess-stats-row"></div>
            <div class="card">
                <div class="card-title" id="bess-chart-title">Arbitrage Revenue</div>
                <div id="bess-main-chart" class="chart-container"></div>
            </div>
            <div class="card">
                <div class="card-title" id="bess-secondary-title">Spread &mdash; dagligt prisintervall (max &minus; min)</div>
                <div style="font-size:0.75rem;color:var(--text-muted);margin-top:-0.4rem;margin-bottom:0.8rem;line-height:1.4" id="bess-secondary-subtitle">
                    Dagligt: max(timpris) &minus; min(timpris) f&ouml;r varje dag.
                    M&aring;nadsvis/&aring;rsvis: medelv&auml;rde av dagliga spreads i perioden.
                    Teoretiskt &ouml;vre tak f&ouml;r intradagsarbitrage (EUR/MWh omsatt) innan effektivitetsf&ouml;rluster.
                </div>
                <div id="bess-secondary-chart" class="chart-container chart-secondary"></div>
            </div>
        </div>
        <!-- Futures sections -->
        <div id="futures-view" style="display:none">
            <div class="card" id="forward-section">
                <div class="card-title" id="forward-title">Forward Curve</div>
                <div id="forward-chart" class="chart-container"></div>
            </div>
            <div class="card" id="epad-section">
                <div class="card-title">EPAD Spread (alla zoner)</div>
                <div id="epad-chart" class="chart-container chart-secondary"></div>
            </div>
            <div class="card" id="fwd-vs-spot-section">
                <div class="card-title">Forward vs Realiserat Spot</div>
                <div id="fwd-vs-spot-chart" class="chart-container chart-secondary"></div>
            </div>
        </div>
    </main>
</div>

<!-- Footer -->
<div class="footer">
    <strong>Elpris Dashboard v2</strong> &mdash; Svea Solar |
    K&auml;llor: <a href="https://www.elprisetjustnu.se/" target="_blank">elprisetjustnu.se</a>,
    <a href="https://transparency.entsoe.eu/" target="_blank">ENTSO-E</a>,
    PVsyst,
    <a href="https://www.nasdaq.com/" target="_blank">Nasdaq</a> |
    Capture = &Sigma;(pris &times; produktion) / &Sigma;(produktion)
</div>

<script>
// ================================================================
// DATA
// ================================================================
const DATA = {data_json};

// ================================================================
// STATE
// ================================================================
let state = {{
    dashboard: 'capture',
    zone: DATA.zones.includes('SE3') ? 'SE3' : DATA.zones[0],
    view: 'yearly',
    year: null,
    month: null,
    enabled: new Set(Object.keys(DATA.profiles).filter(k =>
        !k.startsWith('arb_') && k !== 'spread' && !k.startsWith('sol_bess_') && k !== 'sol_only' && !k.startsWith('anc_')
    )),
    bess_view: 'yearly',
    bess_year: null,
    bess_month: null,
    bess_enabled: new Set(Object.keys(DATA.profiles).filter(k =>
        k.startsWith('arb_') || k === 'spread' || k.startsWith('sol_bess_') || k === 'sol_only'
    )),
    bess_unit: 'per_mw',
}};

// ================================================================
// CONSTANTS
// ================================================================
const MONTH_NAMES = ['Jan','Feb','Mar','Apr','Maj','Jun','Jul','Aug','Sep','Okt','Nov','Dec'];
const MONTH_FULL = ['Januari','Februari','Mars','April','Maj','Juni','Juli','Augusti','September','Oktober','November','December'];

const PLOTLY_DARK = {{
    plot_bgcolor: '#16213e',
    paper_bgcolor: '#16213e',
    font: {{ family: "'SF Pro Display', 'Segoe UI', system-ui, sans-serif", size: 12, color: '#e0e0e0' }},
    xaxis: {{
        gridcolor: '#2a3550',
        zerolinecolor: '#2a3550',
        tickfont: {{ color: '#8892a4' }},
    }},
    yaxis: {{
        gridcolor: '#2a3550',
        zerolinecolor: '#2a3550',
        tickfont: {{ color: '#8892a4' }},
        title: {{ font: {{ color: '#8892a4', size: 11 }} }},
    }},
    legend: {{
        orientation: 'h',
        yanchor: 'bottom',
        y: 1.02,
        xanchor: 'center',
        x: 0.5,
        font: {{ size: 11, color: '#e0e0e0' }},
        bgcolor: 'rgba(0,0,0,0)',
    }},
    margin: {{ t: 40, r: 20, b: 40, l: 60 }},
    hoverlabel: {{ bgcolor: '#0f1629', bordercolor: '#2a3550', font: {{ color: '#e0e0e0', size: 12 }} }},
}};

function fmt(v, d) {{
    if (v === null || v === undefined) return '\u2013';
    return v.toFixed(d !== undefined ? d : 1);
}}

function isRevenueProfile(k) {{
    return (DATA.profile_meta || {{}})[k]?.type === 'revenue';
}}
function isSpreadProfile(k) {{
    return (DATA.profile_meta || {{}})[k]?.type === 'spread';
}}

// ================================================================
// INIT
// ================================================================
function init() {{
    buildZoneButtons();
    buildSidebar();
    buildBessSidebar();
    render();
}}

function buildZoneButtons() {{
    const container = document.getElementById('zone-buttons');
    DATA.zones.forEach(z => {{
        const btn = document.createElement('button');
        btn.className = 'zone-btn' + (z === state.zone ? ' active' : '');
        btn.textContent = z;
        btn.onclick = () => {{
            state.zone = z;
            container.querySelectorAll('.zone-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            render();
        }};
        container.appendChild(btn);
    }});
}}

function buildSidebar() {{
    const sidebar = document.getElementById('sidebar');
    let html = '';

    // Power type sections
    const sections = [
        ['PRISER', ['baseload']],
        ['SOL', Object.keys(DATA.profiles).filter(k => k.startsWith('sol_') && !k.startsWith('sol_bess') && k !== 'sol_only')],
        ['PRODUKTION', ['wind', 'hydro', 'nuclear']],
        ['PARKER', Object.keys(DATA.profiles).filter(k => k.startsWith('park_'))],
    ];

    sections.forEach(([title, keys]) => {{
        const available = keys.filter(k => k in DATA.profiles);
        if (available.length === 0) return;

        html += '<div class="sidebar-section">';
        html += '<div class="sidebar-title">' + title + '</div>';
        available.forEach(k => {{
            const color = DATA.colors[k] || '#888';
            const checked = state.enabled.has(k) ? 'checked' : '';
            html += '<label class="sidebar-item">';
            html += '<input type="checkbox" data-profile="' + k + '" ' + checked + '>';
            html += '<span class="color-dot" style="background:' + color + '"></span>';
            html += DATA.profiles[k];
            html += '</label>';
        }});
        html += '</div>';
    }});

    sidebar.innerHTML = html;

    // Bind checkbox events
    sidebar.querySelectorAll('input[type="checkbox"]').forEach(cb => {{
        cb.addEventListener('change', () => {{
            const k = cb.dataset.profile;
            if (cb.checked) state.enabled.add(k);
            else state.enabled.delete(k);
            render();
        }});
    }});
}}

// ================================================================
// NAVIGATION
// ================================================================
function navigateTo(view, year, month) {{
    state.view = view;
    state.year = year || null;
    state.month = month || null;
    render();
}}

function updateBreadcrumb() {{
    const bc = document.getElementById('breadcrumb');
    let html = '';

    if (state.view === 'yearly') {{
        html = '<span class="breadcrumb-current">' + state.zone + ' \u2014 \u00c5rs\u00f6versikt</span>';
    }} else if (state.view === 'monthly') {{
        html = '<span class="breadcrumb-item" onclick="navigateTo(\\x27yearly\\x27)">\u00c5rs\u00f6versikt</span>';
        html += '<span class="breadcrumb-sep">\u203a</span>';
        html += '<span class="breadcrumb-current">' + state.year + '</span>';
    }} else if (state.view === 'daily') {{
        html = '<span class="breadcrumb-item" onclick="navigateTo(\\x27yearly\\x27)">\u00c5rs\u00f6versikt</span>';
        html += '<span class="breadcrumb-sep">\u203a</span>';
        html += '<span class="breadcrumb-item" onclick="navigateTo(\\x27monthly\\x27,' + state.year + ')">' + state.year + '</span>';
        html += '<span class="breadcrumb-sep">\u203a</span>';
        html += '<span class="breadcrumb-current">' + MONTH_FULL[state.month - 1] + '</span>';
    }}

    bc.innerHTML = html;
}}

// ================================================================
// RENDER
// ================================================================
function switchDashboard(which) {{
    state.dashboard = which;
    document.body.className = 'product-' + which;

    ['capture', 'bess', 'futures'].forEach(t => {{
        document.getElementById('tab-' + t).classList.toggle('active', t === which);
    }});

    document.getElementById('capture-view').style.display = which === 'capture' ? '' : 'none';
    document.getElementById('bess-view').style.display = which === 'bess' ? '' : 'none';
    document.getElementById('futures-view').style.display = which === 'futures' ? '' : 'none';
    document.getElementById('sidebar').style.display = which === 'capture' ? '' : 'none';
    document.getElementById('bess-sidebar').style.display = which === 'bess' ? '' : 'none';

    render();
}}

function render() {{
    if (state.dashboard === 'capture') {{
        updateBreadcrumb();
        if (state.view === 'yearly') renderYearly();
        else if (state.view === 'monthly') renderMonthly();
        else if (state.view === 'daily') renderDaily();
    }} else if (state.dashboard === 'bess') {{
        renderBess();
    }} else {{
        renderForwardCurve();
    }}
}}

// ================================================================
// YEARLY VIEW
// ================================================================
function renderYearly() {{
    const zoneData = DATA.data[state.zone] || {{}};
    const baseloadData = zoneData.baseload?.yearly || [];
    const years = baseloadData.map(r => r.year);

    document.getElementById('chart-title').textContent = state.zone + ' \u2014 Capture Prices per \u00e5r';

    // Stats — latest full year
    updateStats(baseloadData, zoneData, years);

    // Main chart: grouped bars
    const traces = [];
    const profileKeys = getEnabledProfiles(zoneData);

    profileKeys.forEach(k => {{
        const yearlyData = zoneData[k]?.yearly || [];
        const vals = years.map(y => {{
            const r = yearlyData.find(d => d.year === y);
            return r ? (k === 'baseload' ? r.baseload : r.capture) : null;
        }});
        traces.push({{
            x: years.map(String),
            y: vals,
            name: DATA.profiles[k],
            type: 'bar',
            marker: {{ color: DATA.colors[k] || '#888', opacity: k === 'baseload' ? 0.5 : 0.85 }},
            hovertemplate: DATA.profiles[k] + '<br>%{{x}}: %{{y:.1f}} EUR/MWh<extra></extra>',
        }});
    }});

    const layout = {{
        ...PLOTLY_DARK,
        barmode: 'group',
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'category' }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: 'EUR/MWh', rangemode: 'tozero' }},
    }};

    Plotly.newPlot('main-chart', traces, layout, {{ responsive: true, displayModeBar: false }});

    // Click → drill down
    document.getElementById('main-chart').on('plotly_click', (ev) => {{
        if (ev.points.length > 0) {{
            const year = parseInt(ev.points[0].x);
            navigateTo('monthly', year);
        }}
    }});

    // Ratio chart
    renderRatioChart(profileKeys, zoneData, 'yearly', years);
}}

function updateStats(baseloadData, zoneData, years) {{
    const statsRow = document.getElementById('stats-row');
    // Use latest year with data
    const latestYear = years[years.length - 1];
    const bl = baseloadData.find(r => r.year === latestYear);

    let html = '';
    html += statCard('Baseload ' + latestYear, bl ? fmt(bl.baseload) : '\u2013', 'EUR/MWh');

    ['sol_syd', 'sol_ov', 'sol_tracker', 'wind', 'hydro', 'nuclear'].forEach(k => {{
        if (!state.enabled.has(k) || !zoneData[k]) return;
        const d = zoneData[k].yearly?.find(r => r.year === latestYear);
        if (d) {{
            html += statCard(DATA.profiles[k] + ' ' + latestYear, fmt(d.capture), 'EUR/MWh', d.ratio);
        }}
    }});

    statsRow.innerHTML = html;
}}

function statCard(label, value, unit, ratio) {{
    let ratioHtml = '';
    if (ratio !== undefined && ratio !== null) {{
        const pct = (ratio * 100).toFixed(0);
        const color = ratio >= 0.95 ? '#10b981' : ratio >= 0.8 ? '#f59e0b' : '#ef4444';
        ratioHtml = '<div style="font-size:0.8rem;margin-top:2px;color:' + color + ';font-weight:600">' + pct + '% av baseload</div>';
    }}
    return '<div class="stat-card"><div class="stat-label">' + label +
           '</div><div class="stat-value">' + value +
           ' <span class="stat-unit">' + unit + '</span></div>' + ratioHtml + '</div>';
}}

// ================================================================
// MONTHLY VIEW
// ================================================================
function renderMonthly() {{
    const zoneData = DATA.data[state.zone] || {{}};
    const profileKeys = getEnabledProfiles(zoneData);

    document.getElementById('chart-title').textContent =
        state.zone + ' \u2014 Capture Prices per m\u00e5nad ' + state.year;

    // Stats for this year
    const baseloadYearly = zoneData.baseload?.yearly?.find(r => r.year === state.year);
    const statsRow = document.getElementById('stats-row');
    let html = '';
    html += statCard('Baseload ' + state.year, baseloadYearly ? fmt(baseloadYearly.baseload) : '\u2013', 'EUR/MWh');
    profileKeys.filter(k => k !== 'baseload').forEach(k => {{
        const d = zoneData[k]?.yearly?.find(r => r.year === state.year);
        if (d) html += statCard(DATA.profiles[k], fmt(d.capture), 'EUR/MWh', d.ratio);
    }});

    statsRow.innerHTML = html;

    // Chart
    const months = Array.from({{length: 12}}, (_, i) => i + 1);
    const traces = [];

    profileKeys.forEach(k => {{
        const monthlyData = zoneData[k]?.monthly || [];
        const vals = months.map(m => {{
            const r = monthlyData.find(d => d.year === state.year && d.month === m);
            return r ? (k === 'baseload' ? r.baseload : r.capture) : null;
        }});
        traces.push({{
            x: months.map(m => MONTH_NAMES[m - 1]),
            y: vals,
            name: DATA.profiles[k],
            type: 'bar',
            marker: {{ color: DATA.colors[k] || '#888', opacity: k === 'baseload' ? 0.5 : 0.85 }},
            hovertemplate: DATA.profiles[k] + '<br>%{{x}} ' + state.year + ': %{{y:.1f}} EUR/MWh<extra></extra>',
        }});
    }});

    const layout = {{
        ...PLOTLY_DARK,
        barmode: 'group',
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'category' }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: 'EUR/MWh', rangemode: 'tozero' }},
    }};

    Plotly.newPlot('main-chart', traces, layout, {{ responsive: true, displayModeBar: false }});

    document.getElementById('main-chart').on('plotly_click', (ev) => {{
        if (ev.points.length > 0) {{
            const monthIdx = months[ev.points[0].pointIndex];
            navigateTo('daily', state.year, monthIdx);
        }}
    }});

    // Ratio chart
    renderRatioChart(profileKeys, zoneData, 'monthly', months);
}}

// ================================================================
// DAILY VIEW
// ================================================================
function renderDaily() {{
    const zoneData = DATA.data[state.zone] || {{}};
    const profileKeys = getEnabledProfiles(zoneData);

    document.getElementById('chart-title').textContent =
        state.zone + ' \u2014 Dagliga capture prices ' + MONTH_FULL[state.month - 1] + ' ' + state.year;

    // Stats
    const statsRow = document.getElementById('stats-row');
    const blMonthly = zoneData.baseload?.monthly?.find(r => r.year === state.year && r.month === state.month);
    let html = '';
    html += statCard('Baseload', blMonthly ? fmt(blMonthly.baseload) : '\u2013', 'EUR/MWh');
    profileKeys.filter(k => k !== 'baseload').forEach(k => {{
        const d = zoneData[k]?.monthly?.find(r => r.year === state.year && r.month === state.month);
        if (d) html += statCard(DATA.profiles[k], fmt(d.capture), 'EUR/MWh', d.ratio);
    }});

    statsRow.innerHTML = html;

    // Get daily data for this month
    const traces = [];

    profileKeys.forEach(k => {{
        const dailyData = (zoneData[k]?.daily || []).filter(
            d => d.year === state.year && d.month === state.month
        );
        if (dailyData.length === 0) return;

        const dates = dailyData.map(d => d.date);
        const vals = dailyData.map(d => k === 'baseload' ? d.baseload : d.capture);

        traces.push({{
            x: dates,
            y: vals,
            name: DATA.profiles[k],
            type: 'scatter',
            mode: 'lines+markers',
            marker: {{ size: 4 }},
            line: {{ color: DATA.colors[k] || '#888', width: k === 'baseload' ? 1.5 : 2 }},
            opacity: k === 'baseload' ? 0.6 : 1,
            hovertemplate: DATA.profiles[k] + '<br>%{{x}}: %{{y:.1f}} EUR/MWh<extra></extra>',
        }});
    }});

    const layout = {{
        ...PLOTLY_DARK,
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'date', tickformat: '%d %b' }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: 'EUR/MWh', rangemode: 'tozero' }},
        showlegend: true,
    }};

    Plotly.newPlot('main-chart', traces, layout, {{ responsive: true, displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'] }});

    // Ratio chart for daily
    renderDailyRatioChart(profileKeys, zoneData);
}}

// ================================================================
// RATIO CHART
// ================================================================
function renderRatioChart(profileKeys, zoneData, period, xValues) {{
    const traces = [];
    const nonBaseload = profileKeys.filter(k => k !== 'baseload');

    if (period === 'yearly') {{
        nonBaseload.forEach(k => {{
            const data = zoneData[k]?.yearly || [];
            const vals = xValues.map(y => {{
                const r = data.find(d => d.year === y);
                return r ? r.ratio : null;
            }});
            traces.push({{
                x: xValues.map(String),
                y: vals,
                name: DATA.profiles[k],
                type: 'scatter',
                mode: 'lines+markers',
                line: {{ color: DATA.colors[k] || '#888', width: 2 }},
                marker: {{ size: 6 }},
                hovertemplate: DATA.profiles[k] + '<br>%{{x}}: %{{y:.3f}}<extra></extra>',
            }});
        }});
    }} else if (period === 'monthly') {{
        nonBaseload.forEach(k => {{
            const data = zoneData[k]?.monthly || [];
            const vals = xValues.map(m => {{
                const r = data.find(d => d.year === state.year && d.month === m);
                return r ? r.ratio : null;
            }});
            traces.push({{
                x: xValues.map(m => MONTH_NAMES[m - 1]),
                y: vals,
                name: DATA.profiles[k],
                type: 'scatter',
                mode: 'lines+markers',
                line: {{ color: DATA.colors[k] || '#888', width: 2 }},
                marker: {{ size: 5 }},
                hovertemplate: DATA.profiles[k] + '<br>%{{x}}: %{{y:.3f}}<extra></extra>',
            }});
        }});
    }}

    const layout = {{
        ...PLOTLY_DARK,
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'category' }},
        yaxis: {{
            ...PLOTLY_DARK.yaxis,
            title: 'Ratio',
            range: [0, 2],
        }},
        shapes: [{{
            type: 'line', x0: 0, x1: 1, xref: 'paper',
            y0: 1, y1: 1, yref: 'y',
            line: {{ color: '#ffffff', width: 1, dash: 'dash' }},
        }}],
        showlegend: false,
        margin: {{ ...PLOTLY_DARK.margin, t: 20 }},
    }};

    Plotly.newPlot('ratio-chart', traces, layout, {{ responsive: true, displayModeBar: false }});
}}

function renderDailyRatioChart(profileKeys, zoneData) {{
    const traces = [];
    const nonBaseload = profileKeys.filter(k => k !== 'baseload');

    nonBaseload.forEach(k => {{
        const data = (zoneData[k]?.daily || []).filter(
            d => d.year === state.year && d.month === state.month
        );
        if (data.length === 0) return;

        traces.push({{
            x: data.map(d => d.date),
            y: data.map(d => d.ratio),
            name: DATA.profiles[k],
            type: 'scatter',
            mode: 'lines+markers',
            line: {{ color: DATA.colors[k] || '#888', width: 2 }},
            marker: {{ size: 4 }},
            hovertemplate: DATA.profiles[k] + '<br>%{{x}}: %{{y:.3f}}<extra></extra>',
        }});
    }});

    const layout = {{
        ...PLOTLY_DARK,
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'date', tickformat: '%d %b' }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: 'Ratio', range: [0, 2] }},
        shapes: [{{
            type: 'line', x0: 0, x1: 1, xref: 'paper',
            y0: 1, y1: 1, yref: 'y',
            line: {{ color: '#ffffff', width: 1, dash: 'dash' }},
        }}],
        showlegend: false,
        margin: {{ ...PLOTLY_DARK.margin, t: 20 }},
    }};

    Plotly.newPlot('ratio-chart', traces, layout, {{ responsive: true, displayModeBar: false }});
}}

// ================================================================
// BESS SIDEBAR
// ================================================================
function buildBessSidebar() {{
    const sidebar = document.getElementById('bess-sidebar');
    let html = '';

    const arbKeys = Object.keys(DATA.profiles).filter(k => k.startsWith('arb_')).sort((a, b) => {{
        return parseInt(a.replace('arb_', '').replace('h', '')) - parseInt(b.replace('arb_', '').replace('h', ''));
    }});
    const solKeys = Object.keys(DATA.profiles).filter(k => k === 'sol_only' || k.startsWith('sol_bess_')).sort((a, b) => {{
        if (a === 'sol_only') return -1;
        if (b === 'sol_only') return 1;
        return parseInt(a.replace('sol_bess_', '').replace('h', '')) - parseInt(b.replace('sol_bess_', '').replace('h', ''));
    }});

    // Ancillary services ordered: FCR-N, FCR-D up/down, aFRR up/down, mFRR-CM up/down
    const ancOrder = ['anc_fcr_n', 'anc_fcr_d_up', 'anc_fcr_d_down', 'anc_afrr_up', 'anc_afrr_down', 'anc_mfrr_cm_up', 'anc_mfrr_cm_down'];
    const ancKeys = ancOrder.filter(k => k in DATA.profiles);

    const sections = [
        ['ARBITRAGE', arbKeys],
        ['STÖDTJÄNSTER', ancKeys],
        ['SOL', solKeys],
        ['KONTEXT', ['spread'].filter(k => k in DATA.profiles)],
    ];

    sections.forEach(([title, keys]) => {{
        const available = keys.filter(k => k in DATA.profiles);
        if (available.length === 0) return;

        html += '<div class="sidebar-section">';
        html += '<div class="sidebar-title">' + title + '</div>';
        available.forEach(k => {{
            const color = DATA.colors[k] || '#888';
            const checked = state.bess_enabled.has(k) ? 'checked' : '';
            html += '<label class="sidebar-item">';
            html += '<input type="checkbox" data-bess-profile="' + k + '" ' + checked + '>';
            html += '<span class="color-dot" style="background:' + color + '"></span>';
            html += DATA.profiles[k];
            html += '</label>';
        }});
        html += '</div>';
    }});

    sidebar.innerHTML = html;

    sidebar.querySelectorAll('input[type="checkbox"]').forEach(cb => {{
        cb.addEventListener('change', () => {{
            const k = cb.dataset.bessProfile;
            if (cb.checked) state.bess_enabled.add(k);
            else state.bess_enabled.delete(k);
            renderBess();
        }});
    }});
}}

// ================================================================
// BESS NAVIGATION
// ================================================================
function navigateToBess(view, year, month) {{
    state.bess_view = view;
    state.bess_year = year || null;
    state.bess_month = month || null;
    renderBess();
}}

function updateBessBreadcrumb() {{
    const bc = document.getElementById('bess-breadcrumb');
    let html = '';
    if (state.bess_view === 'yearly') {{
        html = '<span class="breadcrumb-current">' + state.zone + ' \u2014 BESS \u00c5rs\u00f6versikt</span>';
    }} else if (state.bess_view === 'monthly') {{
        html = '<span class="breadcrumb-item" onclick="navigateToBess(\\x27yearly\\x27)">\u00c5rs\u00f6versikt</span>';
        html += '<span class="breadcrumb-sep">\u203a</span>';
        html += '<span class="breadcrumb-current">' + state.bess_year + '</span>';
    }} else if (state.bess_view === 'daily') {{
        html = '<span class="breadcrumb-item" onclick="navigateToBess(\\x27yearly\\x27)">\u00c5rs\u00f6versikt</span>';
        html += '<span class="breadcrumb-sep">\u203a</span>';
        html += '<span class="breadcrumb-item" onclick="navigateToBess(\\x27monthly\\x27,' + state.bess_year + ')">' + state.bess_year + '</span>';
        html += '<span class="breadcrumb-sep">\u203a</span>';
        html += '<span class="breadcrumb-current">' + MONTH_FULL[state.bess_month - 1] + '</span>';
    }}
    bc.innerHTML = html;
}}

// ================================================================
// BESS RENDERING
// ================================================================
function renderBess() {{
    updateBessBreadcrumb();
    if (state.bess_view === 'yearly') renderBessYearly();
    else if (state.bess_view === 'monthly') renderBessMonthly();
    else if (state.bess_view === 'daily') renderBessDaily();
}}

function getBessProfiles(zoneData) {{
    return Object.keys(DATA.profiles).filter(k =>
        state.bess_enabled.has(k) && zoneData[k] &&
        (k.startsWith('arb_') || k === 'spread' || k.startsWith('sol_bess_') || k === 'sol_only' || k.startsWith('anc_'))
    );
}}

function isSolCapture(k) {{
    return k.startsWith('sol_bess_') || k === 'sol_only';
}}

function getArbDuration(k) {{
    const m = k.match(/arb_(\d+)h/);
    return m ? parseInt(m[1]) : 1;
}}

function transformArbValue(k, v) {{
    if (v === null || v === undefined) return v;
    if (!k.startsWith('arb_')) return v;
    if (state.bess_unit === 'per_mwh') {{
        return v / getArbDuration(k);
    }}
    return v;
}}

function bessArbUnit() {{
    return state.bess_unit === 'per_mw' ? 'EUR/MW' : 'EUR/MWh';
}}

function setBessUnit(unit) {{
    state.bess_unit = unit;
    const mwBtn = document.getElementById('unit-per-mw');
    const mwhBtn = document.getElementById('unit-per-mwh');
    if (unit === 'per_mw') {{
        mwBtn.style.background = 'var(--product)';
        mwBtn.style.color = 'var(--product-contrast)';
        mwhBtn.style.background = 'transparent';
        mwhBtn.style.color = 'var(--text-muted)';
    }} else {{
        mwBtn.style.background = 'transparent';
        mwBtn.style.color = 'var(--text-muted)';
        mwhBtn.style.background = 'var(--product)';
        mwhBtn.style.color = 'var(--product-contrast)';
    }}
    renderBess();
}}

function renderBessYearly() {{
    const zoneData = DATA.data[state.zone] || {{}};
    const profileKeys = getBessProfiles(zoneData);

    document.getElementById('bess-chart-title').textContent = state.zone + ' \u2014 BESS Revenue per \u00e5r';

    // Find years from any available BESS profile
    let years = [];
    profileKeys.forEach(k => {{
        const yd = zoneData[k]?.yearly || [];
        yd.forEach(d => {{ if (!years.includes(d.year)) years.push(d.year); }});
    }});
    years.sort();

    // Stats — latest year
    const latestYear = years[years.length - 1];
    const statsRow = document.getElementById('bess-stats-row');
    let html = '';

    const arbUnit = bessArbUnit();
    profileKeys.forEach(k => {{
        const d = zoneData[k]?.yearly?.find(r => r.year === latestYear);
        if (!d) return;

        if (isRevenueProfile(k)) {{
            const cycleStr = d.cycles ? ' (' + Math.round(d.cycles) + ' cykler)' : '';
            const tv = transformArbValue(k, d.capture);
            html += statCard(
                DATA.profiles[k] + ' ' + latestYear,
                tv ? tv.toLocaleString('sv-SE', {{maximumFractionDigits: 0}}) : '\u2013',
                arbUnit + cycleStr
            );
        }} else if (isSpreadProfile(k)) {{
            html += statCard('Spread ' + latestYear + ' (\u00d8 dagligt)', fmt(d.capture), 'EUR/MWh (max\u2212min)');
        }} else {{
            html += statCard(DATA.profiles[k] + ' ' + latestYear, fmt(d.capture), 'EUR/MWh', d.ratio);
        }}
    }});
    statsRow.innerHTML = html;

    // Main chart: dual y-axis (arb on left, sol_bess on right, skip spread)
    const traces = [];
    const hasArb = profileKeys.some(k => k.startsWith('arb_'));
    const hasSolBess = profileKeys.some(k => isSolCapture(k));

    profileKeys.forEach(k => {{
        if (isSpreadProfile(k)) return;

        const yearlyData = zoneData[k]?.yearly || [];
        const vals = years.map(y => {{
            const r = yearlyData.find(d => d.year === y);
            return r ? transformArbValue(k, r.capture) : null;
        }});

        const trace = {{
            x: years.map(String),
            y: vals,
            name: DATA.profiles[k],
            type: 'bar',
            marker: {{ color: DATA.colors[k] || '#888', opacity: 0.85 }},
        }};

        if (isSolCapture(k)) {{
            trace.yaxis = 'y2';
            trace.hovertemplate = DATA.profiles[k] + '<br>%{{x}}: %{{y:.1f}} EUR/MWh<extra></extra>';
        }} else {{
            trace.hovertemplate = DATA.profiles[k] + '<br>%{{x}}: %{{y:,.0f}} ' + arbUnit + '<extra></extra>';
        }}

        traces.push(trace);
    }});

    const layout = {{
        ...PLOTLY_DARK,
        barmode: 'group',
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'category' }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: arbUnit + '/\u00e5r', rangemode: 'tozero' }},
    }};

    if (hasSolBess) {{
        layout.yaxis2 = {{
            ...PLOTLY_DARK.yaxis,
            title: {{ text: 'EUR/MWh', font: {{ color: '#8892a4', size: 11 }} }},
            overlaying: 'y',
            side: 'right',
            rangemode: 'tozero',
            showgrid: false,
        }};
        layout.margin = {{ ...PLOTLY_DARK.margin, r: 60 }};
    }}

    Plotly.newPlot('bess-main-chart', traces, layout, {{ responsive: true, displayModeBar: false }});

    // Click → drill down
    document.getElementById('bess-main-chart').on('plotly_click', (ev) => {{
        if (ev.points.length > 0) {{
            const year = parseInt(ev.points[0].x);
            navigateToBess('monthly', year);
        }}
    }});

    // Secondary chart: spread
    renderBessSpreadChart(profileKeys, zoneData, 'yearly', years);
}}

function renderBessMonthly() {{
    const zoneData = DATA.data[state.zone] || {{}};
    const profileKeys = getBessProfiles(zoneData);

    document.getElementById('bess-chart-title').textContent =
        state.zone + ' \u2014 BESS Revenue per m\u00e5nad ' + state.bess_year;

    const months = Array.from({{length: 12}}, (_, i) => i + 1);

    // Stats for this year
    const statsRow = document.getElementById('bess-stats-row');
    let html = '';
    const arbUnit = bessArbUnit();
    profileKeys.forEach(k => {{
        const d = zoneData[k]?.yearly?.find(r => r.year === state.bess_year);
        if (!d) return;

        if (isRevenueProfile(k)) {{
            const cycleStr = d.cycles ? ' (' + Math.round(d.cycles) + ' cykler)' : '';
            const tv = transformArbValue(k, d.capture);
            html += statCard(
                DATA.profiles[k],
                tv ? tv.toLocaleString('sv-SE', {{maximumFractionDigits: 0}}) : '\u2013',
                arbUnit + cycleStr
            );
        }} else if (isSpreadProfile(k)) {{
            html += statCard('Spread (\u00d8 dagligt)', fmt(d.capture), 'EUR/MWh (max\u2212min)');
        }} else {{
            html += statCard(DATA.profiles[k], fmt(d.capture), 'EUR/MWh', d.ratio);
        }}
    }});
    statsRow.innerHTML = html;

    // Chart
    const traces = [];
    const hasSolBess = profileKeys.some(k => isSolCapture(k));

    profileKeys.forEach(k => {{
        if (isSpreadProfile(k)) return;

        const monthlyData = zoneData[k]?.monthly || [];
        const vals = months.map(m => {{
            const r = monthlyData.find(d => d.year === state.bess_year && d.month === m);
            return r ? transformArbValue(k, r.capture) : null;
        }});

        const trace = {{
            x: months.map(m => MONTH_NAMES[m - 1]),
            y: vals,
            name: DATA.profiles[k],
            type: 'bar',
            marker: {{ color: DATA.colors[k] || '#888', opacity: 0.85 }},
        }};

        if (isSolCapture(k)) {{
            trace.yaxis = 'y2';
            trace.hovertemplate = DATA.profiles[k] + '<br>%{{x}} ' + state.bess_year + ': %{{y:.1f}} EUR/MWh<extra></extra>';
        }} else {{
            trace.hovertemplate = DATA.profiles[k] + '<br>%{{x}} ' + state.bess_year + ': %{{y:,.0f}} ' + arbUnit + '<extra></extra>';
        }}

        traces.push(trace);
    }});

    const layout = {{
        ...PLOTLY_DARK,
        barmode: 'group',
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'category' }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: arbUnit, rangemode: 'tozero' }},
    }};

    if (hasSolBess) {{
        layout.yaxis2 = {{
            ...PLOTLY_DARK.yaxis,
            title: {{ text: 'EUR/MWh', font: {{ color: '#8892a4', size: 11 }} }},
            overlaying: 'y',
            side: 'right',
            rangemode: 'tozero',
            showgrid: false,
        }};
        layout.margin = {{ ...PLOTLY_DARK.margin, r: 60 }};
    }}

    Plotly.newPlot('bess-main-chart', traces, layout, {{ responsive: true, displayModeBar: false }});

    document.getElementById('bess-main-chart').on('plotly_click', (ev) => {{
        if (ev.points.length > 0) {{
            const monthIdx = months[ev.points[0].pointIndex];
            navigateToBess('daily', state.bess_year, monthIdx);
        }}
    }});

    // Secondary chart: spread
    renderBessSpreadChart(profileKeys, zoneData, 'monthly', months);
}}

function renderBessDaily() {{
    const zoneData = DATA.data[state.zone] || {{}};
    const profileKeys = getBessProfiles(zoneData);

    document.getElementById('bess-chart-title').textContent =
        state.zone + ' \u2014 BESS Daglig ' + MONTH_FULL[state.bess_month - 1] + ' ' + state.bess_year;

    // Stats
    const statsRow = document.getElementById('bess-stats-row');
    let html = '';
    const arbUnit = bessArbUnit();
    profileKeys.forEach(k => {{
        const d = zoneData[k]?.monthly?.find(r => r.year === state.bess_year && r.month === state.bess_month);
        if (!d) return;

        if (isRevenueProfile(k)) {{
            const cycleStr = d.cycles ? ' (' + Math.round(d.cycles) + ' cykler)' : '';
            const tv = transformArbValue(k, d.capture);
            html += statCard(
                DATA.profiles[k],
                tv ? tv.toLocaleString('sv-SE', {{maximumFractionDigits: 0}}) : '\u2013',
                arbUnit + cycleStr
            );
        }} else if (isSpreadProfile(k)) {{
            html += statCard('Spread (\u00d8 dagligt)', fmt(d.capture), 'EUR/MWh (max\u2212min)');
        }} else {{
            html += statCard(DATA.profiles[k], fmt(d.capture), 'EUR/MWh', d.ratio);
        }}
    }});
    statsRow.innerHTML = html;

    // Daily lines
    const traces = [];
    const hasSolBess = profileKeys.some(k => isSolCapture(k));

    profileKeys.forEach(k => {{
        if (isSpreadProfile(k)) return;

        const dailyData = (zoneData[k]?.daily || []).filter(
            d => d.year === state.bess_year && d.month === state.bess_month
        );
        if (dailyData.length === 0) return;

        const dates = dailyData.map(d => d.date);
        const vals = dailyData.map(d => transformArbValue(k, d.capture));

        const trace = {{
            x: dates,
            y: vals,
            name: DATA.profiles[k],
            type: 'scatter',
            mode: 'lines+markers',
            marker: {{ size: 4 }},
            line: {{ color: DATA.colors[k] || '#888', width: 2 }},
        }};

        if (isSolCapture(k)) {{
            trace.yaxis = 'y2';
            trace.hovertemplate = DATA.profiles[k] + '<br>%{{x|%d %b}}: %{{y:.1f}} EUR/MWh<extra></extra>';
        }} else {{
            trace.hovertemplate = DATA.profiles[k] + '<br>%{{x|%d %b}}: %{{y:.1f}} ' + arbUnit +
                (dailyData[0]?.cycles !== undefined ? '<br>Cykler: %{{customdata:.1f}}' : '') +
                '<extra></extra>';
            trace.customdata = dailyData.map(d => d.cycles);
        }}

        traces.push(trace);
    }});

    const layout = {{
        ...PLOTLY_DARK,
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'date', tickformat: '%d %b' }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: arbUnit, rangemode: 'tozero' }},
        showlegend: true,
    }};

    if (hasSolBess) {{
        layout.yaxis2 = {{
            ...PLOTLY_DARK.yaxis,
            title: {{ text: 'EUR/MWh', font: {{ color: '#8892a4', size: 11 }} }},
            overlaying: 'y',
            side: 'right',
            rangemode: 'tozero',
            showgrid: false,
        }};
        layout.margin = {{ ...PLOTLY_DARK.margin, r: 60 }};
    }}

    Plotly.newPlot('bess-main-chart', traces, layout, {{ responsive: true, displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'] }});

    // Secondary chart: spread as shaded area
    renderBessDailySpreadChart(profileKeys, zoneData);
}}

function renderBessSpreadChart(profileKeys, zoneData, period, xValues) {{
    const secondaryDiv = document.getElementById('bess-secondary-chart');

    if (!state.bess_enabled.has('spread') || !zoneData.spread) {{
        secondaryDiv.parentElement.style.display = 'none';
        return;
    }}
    secondaryDiv.parentElement.style.display = '';

    const spreadData = period === 'yearly' ? zoneData.spread?.yearly : zoneData.spread?.monthly;
    if (!spreadData) {{
        secondaryDiv.parentElement.style.display = 'none';
        return;
    }}

    const vals = xValues.map(x => {{
        const r = period === 'yearly'
            ? spreadData.find(d => d.year === x)
            : spreadData.find(d => d.year === state.bess_year && d.month === x);
        return r ? r.capture : null;
    }});

    const traces = [{{
        x: period === 'yearly' ? xValues.map(String) : xValues.map(m => MONTH_NAMES[m - 1]),
        y: vals,
        name: 'Spread',
        type: 'bar',
        marker: {{ color: DATA.colors.spread || '#94a3b8', opacity: 0.6 }},
        hovertemplate: '<b>%{{x}}</b><br>\u00d8 dagligt max\u2212min: %{{y:.1f}} EUR/MWh<br><i>medelv\u00e4rde av (max-timpris \u2212 min-timpris) per dag</i><extra></extra>',
    }}];

    const layout = {{
        ...PLOTLY_DARK,
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'category' }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: 'EUR/MWh', rangemode: 'tozero' }},
        showlegend: false,
        margin: {{ ...PLOTLY_DARK.margin, t: 20 }},
    }};

    Plotly.newPlot('bess-secondary-chart', traces, layout, {{ responsive: true, displayModeBar: false }});
}}

function renderBessDailySpreadChart(profileKeys, zoneData) {{
    const secondaryDiv = document.getElementById('bess-secondary-chart');

    if (!state.bess_enabled.has('spread') || !zoneData.spread) {{
        secondaryDiv.parentElement.style.display = 'none';
        return;
    }}
    secondaryDiv.parentElement.style.display = '';

    const spreadDays = (zoneData.spread?.daily || []).filter(
        d => d.year === state.bess_year && d.month === state.bess_month
    );

    if (spreadDays.length === 0) {{
        secondaryDiv.parentElement.style.display = 'none';
        return;
    }}

    const traces = [
        {{
            x: spreadDays.map(d => d.date),
            y: spreadDays.map(d => d.max_price),
            name: 'H\u00f6gsta timpris',
            type: 'scatter',
            mode: 'lines',
            line: {{ color: '#94a3b8', width: 1 }},
            hovertemplate: 'Max-timpris: %{{y:.1f}} EUR/MWh<extra></extra>',
        }},
        {{
            x: spreadDays.map(d => d.date),
            y: spreadDays.map(d => d.min_price),
            name: 'L\u00e4gsta timpris',
            type: 'scatter',
            mode: 'lines',
            line: {{ color: '#94a3b8', width: 1 }},
            fill: 'tonexty',
            fillcolor: 'rgba(148, 163, 184, 0.15)',
            hovertemplate: 'Min-timpris: %{{y:.1f}} EUR/MWh<extra></extra>',
        }},
    ];

    // Add spread (max - min) as a line
    traces.push({{
        x: spreadDays.map(d => d.date),
        y: spreadDays.map(d => d.capture),
        name: 'Spread (max\u2212min)',
        type: 'scatter',
        mode: 'lines+markers',
        line: {{ color: DATA.colors.spread || '#94a3b8', width: 2 }},
        marker: {{ size: 3 }},
        hovertemplate: 'Dagsspread (max\u2212min): %{{y:.1f}} EUR/MWh<extra></extra>',
    }});

    const layout = {{
        ...PLOTLY_DARK,
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'date', tickformat: '%d %b' }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: 'EUR/MWh', rangemode: 'tozero' }},
        showlegend: false,
        margin: {{ ...PLOTLY_DARK.margin, t: 20 }},
    }};

    Plotly.newPlot('bess-secondary-chart', traces, layout, {{ responsive: true, displayModeBar: false }});
}}

// ================================================================
// HELPERS
// ================================================================
function getEnabledProfiles(zoneData) {{
    // Return profile keys that are enabled AND have data for this zone
    return Object.keys(DATA.profiles).filter(k =>
        state.enabled.has(k) && zoneData[k]
    );
}}

// ================================================================
// FORWARD CURVE
// ================================================================
function renderForwardCurve() {{
    const fwd = DATA.forward;
    if (!fwd || !fwd.contracts || fwd.contracts.length === 0) {{
        return;
    }}

    const zone = state.zone;
    const labels = fwd.contracts.map(c => c.label);  // passed to renderEpadSpread

    document.getElementById('forward-title').textContent =
        zone + ' — Forward Curve (settlement: ' + fwd.settlement_date + ')';

    // Swedish month abbreviations (no trailing period)
    const SV_MONTHS = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'];

    // Date helpers: treat dates as UTC to avoid timezone shifts
    const parseDate = (s) => new Date(s + 'T00:00:00Z').getTime();
    const midpoint = (start, end) => {{
        const s = parseDate(start);
        const e = parseDate(end) + 86399000;  // end-of-day for the end date
        return new Date((s + e) / 2).toISOString();
    }};
    const periodWidthMs = (start, end) => {{
        const s = parseDate(start);
        const e = parseDate(end) + 86399000;
        return (e - s) * 0.9;  // 10% gap between adjacent bars
    }};
    const monthName = (dateStr) => SV_MONTHS[new Date(dateStr + 'T00:00:00Z').getUTCMonth()];

    // Separate quarters and years
    const quarters = fwd.contracts.filter(c => c.type === 'quarter');
    const years = fwd.contracts.filter(c => c.type === 'year');

    // --- Quarter bar data ---
    const qX = quarters.map(c => midpoint(c.start, c.end));
    const qWidths = quarters.map(c => periodWidthMs(c.start, c.end));
    const qSysVals = quarters.map(c => fwd.sys[c.label] ?? null);
    const qEpadVals = quarters.map(c => {{
        const e = (fwd.epad[zone] || {{}})[c.label];
        return e !== undefined ? e : null;
    }});
    const qZoneVals = quarters.map(c => (fwd.zone_fwd[zone] || {{}})[c.label] ?? null);

    // Stacked-bar encoding: when EPAD < 0, SYS bar shrinks to zone_price,
    // and EPAD overlay (|EPAD|) sits on top back up to SYS level
    const qSysBarVals = qSysVals.map((s, i) => {{
        if (s === null) return null;
        const e = qEpadVals[i];
        if (e !== null && e < 0) return s + e;
        return s;
    }});
    const qEpadBarVals = qEpadVals.map(e => e !== null ? Math.abs(e) : null);
    const qEpadColors = qEpadVals.map(e => e !== null && e >= 0 ? '#10b981' : '#ef4444');

    const qHoverTemplates = quarters.map((c, i) => {{
        const z = qZoneVals[i];
        const s = qSysVals[i];
        const e = qEpadVals[i];
        const yr = c.start.slice(0, 4);
        return '<b>' + zone + ' ' + c.label + '</b><br>' +
            'Period: ' + monthName(c.start) + '–' + monthName(c.end) + ' ' + yr + '<br>' +
            'Zonpris: ' + (z !== null ? z.toFixed(2) : '-') + ' EUR/MWh<br>' +
            'SYS: ' + (s !== null ? s.toFixed(2) : '-') + '<br>' +
            'EPAD: ' + (e !== null ? (e >= 0 ? '+' : '') + e.toFixed(2) : '-') +
            '<extra></extra>';
    }});

    // --- Year plateau data (3 points per year + null separator for gap) ---
    const yX = [];
    const yY = [];
    const yText = [];
    const yHovers = [];
    years.forEach(c => {{
        const price = (fwd.zone_fwd[zone] || {{}})[c.label];
        const sys = fwd.sys[c.label];
        const epad = (fwd.epad[zone] || {{}})[c.label];
        if (price === undefined || price === null) return;
        const yr = c.start.slice(0, 4);
        const hover = '<b>' + zone + ' ' + c.label + '</b><br>' +
            'Period: jan–dec ' + yr + '<br>' +
            'Zonpris: ' + price.toFixed(2) + ' EUR/MWh<br>' +
            'SYS: ' + (sys !== undefined ? sys.toFixed(2) : '-') + '<br>' +
            'EPAD: ' + (epad !== undefined ? (epad >= 0 ? '+' : '') + epad.toFixed(2) : '-') +
            '<extra></extra>';
        yX.push(c.start + 'T00:00:00Z', midpoint(c.start, c.end), c.end + 'T23:59:59Z', null);
        yY.push(price, price, price, null);
        yText.push('', c.label + ': ' + price.toFixed(1), '', '');
        yHovers.push(hover, hover, hover, '');
    }});

    // --- Annotations: zone-price labels above each quarter bar ---
    const annotations = quarters.map((c, i) => ({{
        x: midpoint(c.start, c.end),
        y: qZoneVals[i],
        text: qZoneVals[i] !== null ? qZoneVals[i].toFixed(1) : '',
        showarrow: false,
        xanchor: 'center',
        yanchor: 'bottom',
        font: {{ color: '#e0e0e0', size: 10 }},
        yshift: 4,
    }}));

    // --- Shapes: subtle vertical gridlines at year boundaries ---
    const yearSet = new Set();
    fwd.contracts.forEach(c => {{
        yearSet.add(parseInt(c.start.slice(0, 4)));
        yearSet.add(parseInt(c.end.slice(0, 4)) + 1);
    }});
    const shapes = Array.from(yearSet).sort((a, b) => a - b).map(yr => ({{
        type: 'line',
        xref: 'x',
        yref: 'paper',
        x0: yr + '-01-01',
        x1: yr + '-01-01',
        y0: 0,
        y1: 1,
        line: {{ color: '#2a3550', width: 1 }},
        layer: 'below',
    }}));

    // --- Custom tick values: Q-label per quarter, YR-label for years w/o quarters ---
    const lastQuarterEnd = quarters.length > 0 ? quarters[quarters.length - 1].end : '0000-01-01';
    const tickvals = [];
    const ticktext = [];
    quarters.forEach(c => {{
        tickvals.push(midpoint(c.start, c.end));
        ticktext.push(c.label);
    }});
    years.forEach(c => {{
        if (c.start > lastQuarterEnd) {{
            tickvals.push(midpoint(c.start, c.end));
            ticktext.push(c.label);
        }}
    }});

    const traces = [
        {{
            x: qX,
            y: qSysBarVals,
            width: qWidths,
            name: 'SYS',
            type: 'bar',
            marker: {{ color: '#4a9eff', opacity: 0.7 }},
            hovertemplate: qHoverTemplates,
        }},
        {{
            x: qX,
            y: qEpadBarVals,
            width: qWidths,
            name: 'EPAD',
            type: 'bar',
            marker: {{ color: qEpadColors, opacity: 0.85 }},
            hoverinfo: 'skip',
        }},
        {{
            x: yX,
            y: yY,
            name: 'YR-kontrakt',
            type: 'scatter',
            mode: 'lines+text',
            text: yText,
            textposition: 'top center',
            textfont: {{ color: '#e0e0e0', size: 10 }},
            line: {{ color: '#ffffff', width: 2.5 }},
            hovertemplate: yHovers,
        }},
    ];

    const layout = {{
        ...PLOTLY_DARK,
        barmode: 'stack',
        hovermode: 'closest',
        xaxis: {{
            ...PLOTLY_DARK.xaxis,
            type: 'date',
            tickvals: tickvals,
            ticktext: ticktext,
            tickangle: -45,
        }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: 'EUR/MWh', rangemode: 'tozero' }},
        shapes: shapes,
        annotations: annotations,
        showlegend: true,
    }};

    Plotly.newPlot('forward-chart', traces, layout, {{ responsive: true, displayModeBar: false }});

    // --- EPAD Spread: all zones ---
    renderEpadSpread(fwd, labels);

    // --- Forward vs Spot ---
    renderForwardVsSpot(fwd);
}}

function renderEpadSpread(fwd, labels) {{
    const zoneColors = {{
        'SE1': '#67e8f9',
        'SE2': '#86efac',
        'SE3': '#fde68a',
        'SE4': '#fca5a5',
    }};

    const traces = [];
    DATA.zones.forEach(z => {{
        const vals = labels.map(l => {{
            const e = (fwd.epad[z] || {{}})[l];
            return e !== undefined ? e : null;
        }});
        traces.push({{
            x: labels,
            y: vals,
            name: z,
            type: 'bar',
            marker: {{ color: zoneColors[z] || '#888', opacity: 0.8 }},
            hovertemplate: z + ' %{{x}}: %{{y:.2f}} EUR/MWh<extra></extra>',
        }});
    }});

    // Mark periods where no EPAD data exists for any zone. Nasdaq only
    // publishes EPAD futures for the nearest ~3 quarters and ~4 years
    // (liquidity drops off beyond that), so longer-dated SYS contracts
    // have no EPAD counterpart.
    const shapes = [];
    const annotations = [];
    labels.forEach((l, i) => {{
        const hasAny = DATA.zones.some(z => (fwd.epad[z] || {{}})[l] !== undefined);
        if (!hasAny) {{
            shapes.push({{
                type: 'rect',
                xref: 'x',
                yref: 'paper',
                x0: i - 0.5,
                x1: i + 0.5,
                y0: 0,
                y1: 1,
                fillcolor: 'rgba(255, 255, 255, 0.04)',
                line: {{ width: 0 }},
                layer: 'below',
            }});
            annotations.push({{
                x: i,
                xref: 'x',
                y: 0,
                yref: 'y',
                text: 'n/a',
                font: {{ color: '#64748b', size: 10 }},
                showarrow: false,
                textangle: -90,
            }});
        }}
    }});

    const layout = {{
        ...PLOTLY_DARK,
        barmode: 'group',
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'category', tickangle: -45 }},
        yaxis: {{
            ...PLOTLY_DARK.yaxis,
            title: 'EPAD (EUR/MWh)',
            zeroline: true,
            zerolinecolor: '#ffffff',
            zerolinewidth: 1,
        }},
        shapes: shapes,
        annotations: annotations,
        showlegend: true,
        margin: {{ ...PLOTLY_DARK.margin, t: 20 }},
    }};

    Plotly.newPlot('epad-chart', traces, layout, {{ responsive: true, displayModeBar: false }});
}}

function renderForwardVsSpot(fwd) {{
    const expired = fwd.expired_contracts || [];
    const zone = state.zone;
    const realized = fwd.spot_realized[zone] || {{}};

    const labels = expired.map(c => c.label).filter(l => l in realized);
    if (labels.length === 0) {{
        document.getElementById('fwd-vs-spot-section').style.display = 'none';
        return;
    }}
    document.getElementById('fwd-vs-spot-section').style.display = '';

    const fwdVals = labels.map(l => realized[l] ? realized[l].forward : null);
    const spotVals = labels.map(l => realized[l] ? realized[l].spot_avg : null);

    const traces = [
        {{
            x: labels,
            y: fwdVals,
            name: 'Forward',
            type: 'bar',
            marker: {{ color: '#4a9eff', opacity: 0.7 }},
            hovertemplate: 'Forward %{{x}}: %{{y:.1f}} EUR/MWh<extra></extra>',
        }},
        {{
            x: labels,
            y: spotVals,
            name: 'Realiserat spot',
            type: 'bar',
            marker: {{ color: '#10b981', opacity: 0.8 }},
            hovertemplate: 'Spot %{{x}}: %{{y:.1f}} EUR/MWh<extra></extra>',
        }},
    ];

    const layout = {{
        ...PLOTLY_DARK,
        barmode: 'group',
        xaxis: {{ ...PLOTLY_DARK.xaxis, type: 'category' }},
        yaxis: {{ ...PLOTLY_DARK.yaxis, title: 'EUR/MWh', rangemode: 'tozero' }},
        showlegend: true,
        margin: {{ ...PLOTLY_DARK.margin, t: 20 }},
    }};

    Plotly.newPlot('fwd-vs-spot-chart', traces, layout, {{ responsive: true, displayModeBar: false }});
}}

// ================================================================
// GO
// ================================================================
document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""

    return html


def main() -> None:
    print("Beräknar dashboard v2 data...")
    data = calculate_dashboard_v2_data()

    zones = data.get("zones", [])
    profiles = data.get("profiles", {})
    print(f"  Zoner: {len(zones)}, Profiler: {len(profiles)}")

    output_dir = PROJECT_ROOT / "Resultat" / "rapporter"
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")

    # HTML
    print("Genererar HTML...")
    html = _build_html(data)
    html_path = output_dir / f"dashboard_v2_{today}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    size_mb = html_path.stat().st_size / (1024 * 1024)
    print(f"  HTML: {html_path} ({size_mb:.1f} MB)")

    # Excel (with hourly data)
    print("Genererar Excel (inkl. timdata)...")
    from elpris.excel_export_v2 import generate_dashboard_excel
    excel_data = calculate_dashboard_v2_data(
        granularities=["yearly", "monthly", "daily", "hourly"]
    )
    xlsx_path = output_dir / f"dashboard_v2_{today}.xlsx"
    generate_dashboard_excel(excel_data, xlsx_path)
    size_mb = xlsx_path.stat().st_size / (1024 * 1024)
    print(f"  Excel: {xlsx_path} ({size_mb:.1f} MB)")

    print("\nKlart!")


if __name__ == "__main__":
    main()
