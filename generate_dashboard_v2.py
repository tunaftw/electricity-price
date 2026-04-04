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
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
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
    border-color: var(--accent);
    background: var(--accent);
}}
.sidebar-item input[type="checkbox"]:checked::after {{
    content: '';
    position: absolute;
    top: 1px;
    left: 4px;
    width: 4px;
    height: 7px;
    border: solid #fff;
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
    color: var(--accent);
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    transition: background 0.15s;
}}
.breadcrumb-item:hover {{
    background: var(--accent-dim);
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

/* ===== Responsive ===== */
@media (max-width: 768px) {{
    .sidebar {{ display: none; }}
    .topbar {{ flex-wrap: wrap; gap: 0.5rem; }}
    .layout {{ flex-direction: column; }}
}}
</style>
</head>
<body>

<!-- Topbar -->
<div class="topbar">
    <div class="topbar-title"><span>ELPRIS</span> DASHBOARD</div>
    <div class="zone-buttons" id="zone-buttons"></div>
    <div class="topbar-meta">Genererad: {data["generated"][:10]}</div>
</div>

<!-- Layout -->
<div class="layout">

    <!-- Sidebar -->
    <aside class="sidebar" id="sidebar"></aside>

    <!-- Main -->
    <main class="main">
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
    </main>
</div>

<!-- Footer -->
<div class="footer">
    <strong>Elpris Dashboard v2</strong> &mdash; Svea Solar |
    K&auml;llor: <a href="https://www.elprisetjustnu.se/" target="_blank">elprisetjustnu.se</a>,
    <a href="https://transparency.entsoe.eu/" target="_blank">ENTSO-E</a>,
    PVsyst |
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
    zone: DATA.zones.includes('SE3') ? 'SE3' : DATA.zones[0],
    view: 'yearly',
    year: null,
    month: null,
    enabled: new Set(Object.keys(DATA.profiles)),
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

// ================================================================
// INIT
// ================================================================
function init() {{
    buildZoneButtons();
    buildSidebar();
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
        ['SOL', Object.keys(DATA.profiles).filter(k => k.startsWith('sol_'))],
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
function render() {{
    updateBreadcrumb();

    if (state.view === 'yearly') renderYearly();
    else if (state.view === 'monthly') renderMonthly();
    else if (state.view === 'daily') renderDaily();
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

    ['sol_syd', 'wind', 'hydro', 'nuclear'].forEach(k => {{
        if (!state.enabled.has(k) || !zoneData[k]) return;
        const d = zoneData[k].yearly?.find(r => r.year === latestYear);
        if (d) {{
            html += statCard(DATA.profiles[k] + ' ' + latestYear, fmt(d.capture), 'EUR/MWh');
        }}
    }});

    statsRow.innerHTML = html;
}}

function statCard(label, value, unit) {{
    return '<div class="stat-card"><div class="stat-label">' + label +
           '</div><div class="stat-value">' + value +
           ' <span class="stat-unit">' + unit + '</span></div></div>';
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
        if (d) html += statCard(DATA.profiles[k], fmt(d.capture), 'EUR/MWh');
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
        if (d) html += statCard(DATA.profiles[k], fmt(d.capture), 'EUR/MWh');
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
            line: {{ color: DATA.colors[k] || '#888', width: k === 'baseload' ? 1.5 : 2 }},
            marker: {{ size: 4 }},
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
// HELPERS
// ================================================================
function getEnabledProfiles(zoneData) {{
    // Return profile keys that are enabled AND have data for this zone
    return Object.keys(DATA.profiles).filter(k =>
        state.enabled.has(k) && zoneData[k]
    );
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

    # Excel
    print("Genererar Excel...")
    from elpris.excel_export_v2 import generate_dashboard_excel
    xlsx_path = output_dir / f"dashboard_v2_{today}.xlsx"
    generate_dashboard_excel(data, xlsx_path)
    size_kb = xlsx_path.stat().st_size / 1024
    print(f"  Excel: {xlsx_path} ({size_kb:.0f} KB)")

    print("\nKlart!")


if __name__ == "__main__":
    main()
