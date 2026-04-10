"""HTML-rendering för månadsvis prestandarapport.

Genererar en fristående, professionell HTML-rapport med Plotly.js-diagram
för en solparks månatliga prestanda. Enda externa beroende är Plotly CDN.
"""

import json
from typing import Optional

from .performance_report_data import (
    DailyData,
    DayDetail,
    LossCascade,
    MonthlyReport,
    MonthSummary,
)

# ---------------------------------------------------------------------------
# Konstanter
# ---------------------------------------------------------------------------

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"

# Svea Solar Professional Light Theme
_C = {
    "bg": "#f8fafc",
    "card": "#ffffff",
    "text": "#1e293b",
    "muted": "#64748b",
    "primary": "#1a365d",
    "accent": "#2563eb",
    "amber": "#f59e0b",
    "green": "#10b981",
    "red": "#ef4444",
    "chart_dark": "#1e40af",
    "chart_light": "#93c5fd",
    "chart_amber": "#f59e0b",
    "good_bg": "#dcfce7",
    "bad_bg": "#fee2e2",
    "gradient_start": "#1a365d",
    "gradient_end": "#2563eb",
}

# Svenska fullständiga månadsnamn (1-indexerat)
_MONTH_FULL_SV = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Svenska korta månadsnamn (1-indexerat, för kompakta tabellhuvud)
_MONTH_SV = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


# ---------------------------------------------------------------------------
# Hjälpfunktioner
# ---------------------------------------------------------------------------

def _fmt(value, decimals: int = 1, suffix: str = "") -> str:
    """Formatera tal eller returnera '—' vid None."""
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}{suffix}".replace(",", "\u202f")


def _fmt_pct(value, decimals: int = 1) -> str:
    """Formatera procenttal."""
    return _fmt(value, decimals, "%")


def _fmt_delta(value, decimals: int = 1) -> str:
    """Formatera delta med +/- tecken."""
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.{decimals}f}".replace(",", "\u202f")


def _color_cell(value, positive_is_good: bool = True) -> str:
    """Returnera bakgrundsfärg för en delta-cell."""
    if value is None:
        return ""
    if positive_is_good:
        return f'background-color: {_C["good_bg"]}' if value >= 0 else f'background-color: {_C["bad_bg"]}'
    else:
        return f'background-color: {_C["good_bg"]}' if value <= 0 else f'background-color: {_C["bad_bg"]}'


def _safe_json(obj) -> str:
    """JSON-serialisera med None → null."""
    return json.dumps(obj, ensure_ascii=False)


def _plotly_config() -> str:
    """Standard Plotly-konfiguration."""
    return json.dumps({
        "responsive": True,
        "displayModeBar": False,
    })


def _section_id(n: int) -> str:
    return f"section-{n}"


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def _render_css() -> str:
    return f"""<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        background: {_C['bg']};
        color: {_C['text']};
        line-height: 1.6;
    }}
    .cover {{
        background: linear-gradient(135deg, {_C['gradient_start']}, {_C['gradient_end']});
        color: #ffffff;
        padding: 60px 40px;
        text-align: center;
    }}
    .cover .brand {{ font-size: 14px; letter-spacing: 4px; text-transform: uppercase; opacity: 0.8; margin-bottom: 16px; }}
    .cover h1 {{ font-size: 42px; font-weight: 700; margin-bottom: 8px; }}
    .cover .subtitle {{ font-size: 20px; font-weight: 300; opacity: 0.9; margin-bottom: 4px; }}
    .cover .meta {{ font-size: 16px; opacity: 0.7; margin-top: 12px; }}

    .toc {{
        position: sticky; top: 0; z-index: 100;
        background: {_C['card']}; border-bottom: 1px solid #e2e8f0;
        padding: 10px 20px; display: flex; flex-wrap: wrap; gap: 6px 16px;
        font-size: 13px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}
    .toc a {{
        color: {_C['accent']}; text-decoration: none; white-space: nowrap;
    }}
    .toc a:hover {{ text-decoration: underline; }}

    .content {{ max-width: 1280px; margin: 0 auto; padding: 24px 20px; }}

    .section {{
        margin-bottom: 32px;
        page-break-inside: avoid;
    }}
    .section-title {{
        font-size: 22px; font-weight: 700; color: {_C['primary']};
        border-bottom: 3px solid {_C['accent']}; padding-bottom: 8px;
        margin-bottom: 20px;
    }}

    .card {{
        background: {_C['card']}; border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 20px;
        margin-bottom: 16px;
    }}

    .kpi-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }}
    .kpi-card {{
        background: {_C['card']}; border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 20px; text-align: center;
        border-top: 3px solid {_C['accent']};
    }}
    .kpi-card .kpi-value {{ font-size: 32px; font-weight: 700; color: {_C['primary']}; }}
    .kpi-card .kpi-label {{ font-size: 13px; color: {_C['muted']}; margin-top: 4px; }}

    .gauge-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }}
    .gauge-card {{ background: {_C['card']}; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 16px; }}

    .params-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    .params-table th {{ text-align: left; padding: 8px 12px; background: {_C['bg']}; color: {_C['muted']}; font-weight: 600; border-bottom: 1px solid #e2e8f0; }}
    .params-table td {{ padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }}
    .params-table tr:last-child td {{ border-bottom: none; }}

    .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .data-table th {{
        background: {_C['primary']}; color: #ffffff; padding: 8px 10px;
        text-align: right; font-weight: 600; white-space: nowrap;
        position: sticky; top: 0;
    }}
    .data-table th:first-child {{ text-align: left; }}
    .data-table td {{ padding: 6px 10px; border-bottom: 1px solid #f1f5f9; text-align: right; }}
    .data-table td:first-child {{ text-align: left; font-weight: 500; }}
    .data-table tr:hover {{ background: #f8fafc; }}
    .data-table .total-row {{ font-weight: 700; background: {_C['bg']}; border-top: 2px solid {_C['primary']}; }}

    .table-scroll {{ max-height: 500px; overflow-y: auto; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}

    .insight-box {{
        background: #eff6ff; border-left: 4px solid {_C['accent']};
        padding: 16px 20px; border-radius: 0 8px 8px 0; margin-top: 16px;
        font-size: 14px; color: {_C['text']};
    }}

    .formula-box {{
        background: {_C['bg']}; border: 1px solid #e2e8f0;
        padding: 12px 16px; border-radius: 8px; margin: 12px 0;
        font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;
        text-align: center; color: {_C['muted']};
    }}

    .side-by-side {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}

    .placeholder-card {{
        background: {_C['card']}; border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 40px 20px;
        text-align: center; border: 2px dashed #e2e8f0;
    }}
    .placeholder-card .ph-icon {{ font-size: 48px; margin-bottom: 12px; }}
    .placeholder-card .ph-title {{ font-size: 18px; font-weight: 600; color: {_C['primary']}; margin-bottom: 8px; }}
    .placeholder-card .ph-msg {{ font-size: 14px; color: {_C['muted']}; max-width: 400px; margin: 0 auto; }}

    .ppm-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .ppm-table th, .ppm-table td {{
        padding: 8px 6px; text-align: center;
        border: 1px solid #e2e8f0;
    }}
    .ppm-table thead th {{
        background: {_C['primary']}; color: #fff; font-weight: 600;
    }}
    .ppm-table .ppm-task-col {{ text-align: left; min-width: 220px; }}
    .ppm-table .ppm-task-cell {{ text-align: left; color: {_C['text']}; font-weight: 500; }}
    .ppm-table .ppm-freq-col, .ppm-table .ppm-freq-cell {{
        min-width: 70px; color: {_C['muted']}; font-size: 12px;
    }}
    .ppm-table .ppm-month-col {{ min-width: 45px; font-size: 11px; }}
    .ppm-table .ppm-cell {{ color: #94a3b8; }}
    .ppm-table .ppm-scheduled {{
        background: #dbeafe; color: {_C['accent']};
        font-size: 16px;
    }}
    .ppm-table .ppm-current-month {{
        background: #fef3c7 !important;
        border-left: 2px solid {_C['amber']};
        border-right: 2px solid {_C['amber']};
    }}
    .ppm-table .ppm-scheduled.ppm-current-month {{
        background: #fde68a !important;
    }}
    .ppm-table tbody tr:hover td {{ background: #f1f5f9; }}
    .ppm-table tbody tr:hover td.ppm-scheduled {{ background: #bfdbfe; }}

    /* Inverter & alarm tables (Phase 6) */
    .inverter-table, .ranking-table, .alarm-table, .alarm-detail-table {{
        width: 100%; border-collapse: collapse; font-size: 12px;
        margin-top: 8px;
    }}
    .inverter-table th, .ranking-table th, .alarm-table th, .alarm-detail-table th {{
        background: {_C['primary']}; color: #fff;
        padding: 6px 8px; text-align: left; font-weight: 600;
    }}
    .inverter-table td, .ranking-table td, .alarm-table td, .alarm-detail-table td {{
        padding: 5px 8px; border-bottom: 1px solid #e2e8f0;
    }}
    .inverter-table tbody tr:hover, .alarm-table tbody tr:hover {{
        background: #f1f5f9;
    }}
    .inverter-table .num, .ranking-table .num, .alarm-table .num, .alarm-detail-table .num {{
        text-align: right; font-variant-numeric: tabular-nums;
    }}
    .inverter-table .rank-cell {{
        text-align: center; color: {_C['muted']}; font-size: 11px;
    }}
    .inverter-table .inactive-row {{
        background: #fef2f2; color: {_C['muted']}; font-style: italic;
    }}
    .inverter-table .cf-good {{ color: {_C['green']}; font-weight: 600; }}
    .inverter-table .cf-bad {{ color: {_C['red']}; font-weight: 600; }}
    .ranking-table .rank-num {{
        text-align: center; font-weight: 700; color: {_C['accent']};
        width: 30px;
    }}
    .transformer-group {{ margin-bottom: 20px; }}
    .ts-header {{
        background: #f1f5f9; padding: 8px 12px; border-radius: 6px;
        margin-bottom: 8px; font-size: 13px; color: {_C['text']};
    }}
    .alarm-detail-table {{ font-size: 11px; }}
    .alarm-detail-table td {{ padding: 4px 8px; }}

    .warning-box {{
        background: #fef3c7; border-left: 4px solid {_C['amber']};
        padding: 12px 16px; margin: 12px 0; border-radius: 6px;
        font-size: 13px; color: {_C['text']};
    }}

    .data-quality-alert {{
        background: #dbeafe; border-left: 4px solid {_C['accent']};
        padding: 14px 18px; margin: 16px 0; border-radius: 6px;
        font-size: 13px; line-height: 1.5; color: {_C['text']};
    }}
    .data-quality-alert strong {{ color: {_C['primary']}; }}

    .chart-container {{ min-height: 350px; }}

    @media print {{
        .toc {{ display: none; }}
        .section {{ page-break-inside: avoid; }}
        .cover {{ page-break-after: always; }}
        body {{ background: #fff; }}
        .card, .kpi-card, .gauge-card {{ box-shadow: none; border: 1px solid #e2e8f0; }}
    }}

    @media (max-width: 900px) {{
        .kpi-row {{ grid-template-columns: repeat(2, 1fr); }}
        .gauge-row, .side-by-side {{ grid-template-columns: 1fr; }}
    }}
</style>"""


# ---------------------------------------------------------------------------
# Header / Cover
# ---------------------------------------------------------------------------

def _render_header(report: MonthlyReport) -> str:
    month_full = _MONTH_FULL_SV[report.month]
    return f"""<div class="cover">
    <div class="brand">SVEA SOLAR</div>
    <h1>{report.park_display_name}</h1>
    <div class="subtitle">Performance Report</div>
    <div class="subtitle" style="font-size: 24px; font-weight: 500; margin-top: 8px;">{month_full} {report.year}</div>
    <div class="meta">{report.park_location} &middot; {report.zone}</div>
</div>"""


# ---------------------------------------------------------------------------
# Table of Contents
# ---------------------------------------------------------------------------

def _render_toc() -> str:
    sections = [
        (1, "Summary"),
        (2, "YTD"),
        (3, "Daily Generation"),
        (4, "PR &amp; Temperature"),
        (5, "Expected vs Actual"),
        (6, "Performance Index"),
        (7, "Efficiency"),
        (8, "Power &amp; Irradiance"),
        (9, "Losses (MWh)"),
        (10, "Losses (%)"),
        (11, "Curtailment &amp; Irradiation"),
        (12, "Best &amp; Worst Day"),
        (13, "Top 5 / Bottom 5"),
        (14, "Inverter Yield"),
        (15, "Inverter Efficiency"),
        (16, "PPM Schedule"),
        (17, "Incidents"),
        (18, "Alarms"),
        (19, "Executive Summary"),
    ]
    links = " ".join(
        f'<a href="#{_section_id(n)}">{n}. {label}</a>'
        for n, label in sections
    )
    return f'<nav class="toc">{links}</nav>'


# ---------------------------------------------------------------------------
# Section 1: Monthly Performance Summary
# ---------------------------------------------------------------------------

def _render_monthly_summary(report: MonthlyReport) -> str:
    r = report

    # KPI cards — only show cards where data is actually available
    # (hide PR, Verkningsgrad or Modultemp if None to avoid "—" clutter)
    kpi_entries = [
        (r.yield_kwh_kwp, "Yield (kWh/kWp)"),  # Always shown (never None)
    ]
    if r.performance_ratio_pct is not None:
        kpi_entries.append((r.performance_ratio_pct, "Performance Ratio (%)"))
    if r.efficiency_pct is not None:
        kpi_entries.append((r.efficiency_pct, "Efficiency (%)"))
    if r.avg_module_temp_c is not None:
        kpi_entries.append((r.avg_module_temp_c, "Avg Module Temp (\u00b0C)"))

    kpi_cards_html = '<div class="kpi-row">'
    for value, label in kpi_entries:
        kpi_cards_html += f"""
    <div class="kpi-card">
        <div class="kpi-value">{_fmt(value)}</div>
        <div class="kpi-label">{label}</div>
    </div>"""
    kpi_cards_html += '\n</div>'
    kpi_cards = kpi_cards_html

    # Gauge chart data
    energy_pct = (r.actual_energy_mwh / r.budget_energy_mwh * 100) if r.budget_energy_mwh > 0 else 0
    irr_pct = (r.actual_irradiation_kwh_m2 / r.budget_irradiation_kwh_m2 * 100) if (
        r.actual_irradiation_kwh_m2 is not None and r.budget_irradiation_kwh_m2 > 0
    ) else None

    gauge_energy = {
        "type": "indicator",
        "mode": "gauge+number+delta",
        "value": round(r.actual_energy_mwh, 1),
        "delta": {"reference": round(r.budget_energy_mwh, 1), "relative": False,
                  "increasing": {"color": _C["green"]}, "decreasing": {"color": _C["red"]}},
        "title": {"text": "Actual Energy (MWh)"},
        "gauge": {
            "axis": {"range": [0, round(r.budget_energy_mwh * 1.3, 0)]},
            "bar": {"color": _C["chart_dark"]},
            "steps": [
                {"range": [0, round(r.budget_energy_mwh, 1)], "color": "#e0e7ff"},
            ],
            "threshold": {
                "line": {"color": _C["red"], "width": 3},
                "thickness": 0.8,
                "value": round(r.budget_energy_mwh, 1),
            },
        },
    }

    gauge_irr_value = round(r.actual_irradiation_kwh_m2, 1) if r.actual_irradiation_kwh_m2 is not None else 0
    gauge_irr = {
        "type": "indicator",
        "mode": "gauge+number+delta",
        "value": gauge_irr_value,
        "delta": {"reference": round(r.budget_irradiation_kwh_m2, 1), "relative": False,
                  "increasing": {"color": _C["green"]}, "decreasing": {"color": _C["red"]}},
        "title": {"text": "Irradiation (kWh/m\u00b2)"},
        "gauge": {
            "axis": {"range": [0, round(r.budget_irradiation_kwh_m2 * 1.3, 0)]},
            "bar": {"color": _C["chart_amber"]},
            "steps": [
                {"range": [0, round(r.budget_irradiation_kwh_m2, 1)], "color": "#fef3c7"},
            ],
            "threshold": {
                "line": {"color": _C["red"], "width": 3},
                "thickness": 0.8,
                "value": round(r.budget_irradiation_kwh_m2, 1),
            },
        },
    }

    gauge_layout = {
        "height": 250,
        "margin": {"t": 60, "b": 20, "l": 30, "r": 30},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "color": _C["text"]},
    }

    gauges_html = f"""<div class="gauge-row">
    <div class="gauge-card">
        <div id="gauge-energy" class="chart-container" style="min-height:250px;"></div>
    </div>
    <div class="gauge-card">
        <div id="gauge-irr" class="chart-container" style="min-height:250px;"></div>
    </div>
</div>"""

    gauge_scripts = f"""
Plotly.newPlot('gauge-energy', [{_safe_json(gauge_energy)}], {_safe_json(gauge_layout)}, {_plotly_config()});
Plotly.newPlot('gauge-irr', [{_safe_json(gauge_irr)}], {_safe_json(gauge_layout)}, {_plotly_config()});
"""

    # Key Project Parameters table
    meta = r.metadata

    # Format helpers for new fields
    def _fmt_int(v):
        return _fmt(v, 0) if v is not None else "\u2014"

    def _fmt_tracking(meta):
        if not meta.get("tracking"):
            return "No (fixed tilt)"
        ttype = meta.get("tracking_type", "")
        if "single_axis" in ttype:
            return "Yes \u2014 single-axis tracker"
        if "dual_axis" in ttype:
            return "Yes \u2014 dual-axis tracker"
        return "Yes"

    def _fmt_tilt(meta):
        if meta.get("tracking"):
            return "N/A (tracker)"
        ta = meta.get("tilt_angle")
        return f"{ta}\u00b0" if ta is not None else "\u2014"

    def _fmt_azimuth(meta):
        if meta.get("tracking"):
            return "N/A (tracker)"
        az = meta.get("azimuth")
        if az is None:
            return "\u2014"
        return f"{az}\u00b0 ({'south' if abs(az) < 5 else 'south' + ('-west' if az > 0 else '-east')})"

    def _fmt_transformer(meta):
        cap = meta.get("transformer_capacity_kva")
        cnt = meta.get("transformer_count")
        if cap is None or cnt is None:
            return "\u2014"
        return f"{cnt} \u00d7 {cap:,} kVA".replace(",", " ")

    annual_yield = meta.get("expected_annual_yield_kwh_kwp")
    annual_energy_mwh = (annual_yield * r.capacity_kwp / 1000) if annual_yield else None

    params_rows = [
        # --- Identitet ---
        ("Park", r.park_display_name),
        ("Location", r.park_location),
        ("Bidding Zone", r.zone),
        ("Commissioning (COD)", meta.get("commissioning_date", "\u2014")),
        # --- Kapacitet ---
        ("DC Capacity", f"{_fmt(r.capacity_kwp, 0)} kWp ({_fmt(r.capacity_mwp, 2)} MWp)"),
        ("AC Capacity", f"{_fmt(meta.get('ac_capacity_mwac'), 2)} MWac" if meta.get("ac_capacity_mwac") else "\u2014"),
        ("Grid Connection", f"{_fmt(meta.get('grid_limit_mwac'), 2)} MWac" if meta.get("grid_limit_mwac") else "\u2014"),
        ("Export Limit", _fmt((meta.get("export_limit") or 0) * 100, 0) + "% of DC" if meta.get("export_limit") else "\u2014"),
        # --- Moduler ---
        ("Module Type", meta.get("module_type", "\u2014")),
        ("Module Wp", f"{_fmt_int(meta.get('module_wp'))} Wp"),
        ("Number of Modules", _fmt_int(meta.get("num_modules"))),
        # --- Invertrar ---
        ("Inverter Manufacturer", meta.get("inverter_manufacturer", "\u2014")),
        ("Inverter Model", meta.get("inverter_model", "\u2014")),
        ("Number of Inverters", _fmt_int(meta.get("num_inverters"))),
        # --- Geometri ---
        ("Tracking", _fmt_tracking(meta)),
        ("Tilt Angle", _fmt_tilt(meta)),
        ("Azimuth", _fmt_azimuth(meta)),
        # --- Transformator ---
        ("Transformer", _fmt_transformer(meta)),
        # --- Performance baseline ---
        ("Expected Annual Yield", f"{_fmt(annual_yield, 0)} kWh/kWp ({_fmt(annual_energy_mwh, 0)} MWh)" if annual_yield else "\u2014"),
        ("Budget PR (PVsyst)", _fmt_pct(r.budget_pr_pct)),
    ]
    params_html = '<table class="params-table">'
    params_html += '<tr><th>Parameter</th><th>Value</th></tr>'
    for p, v in params_rows:
        params_html += f"<tr><td>{p}</td><td>{v}</td></tr>"
    params_html += "</table>"

    # Insight text
    energy_delta_pct = ((r.actual_energy_mwh / r.budget_energy_mwh - 1) * 100) if r.budget_energy_mwh > 0 else 0
    delta_word = "below budget" if energy_delta_pct < 0 else "above budget"
    irr_insight = ""
    if r.actual_irradiation_kwh_m2 is not None and r.budget_irradiation_kwh_m2 > 0:
        irr_delta = ((r.actual_irradiation_kwh_m2 / r.budget_irradiation_kwh_m2 - 1) * 100)
        irr_word = "lower" if irr_delta < 0 else "higher"
        irr_insight = f" Irradiation was {abs(irr_delta):.1f}% {irr_word} than budgeted ({_fmt(r.actual_irradiation_kwh_m2)} vs {_fmt(r.budget_irradiation_kwh_m2)} kWh/m\u00b2)."

    insight = (
        f"The park produced <strong>{_fmt(r.actual_energy_mwh)} MWh</strong>, "
        f"which is <strong>{abs(energy_delta_pct):.1f}% {delta_word}</strong> "
        f"({_fmt(r.budget_energy_mwh)} MWh).{irr_insight}"
    )
    if r.performance_ratio_pct is not None:
        pr_delta = r.performance_ratio_pct - r.budget_pr_pct
        pr_word = "below" if pr_delta < 0 else "above"
        insight += f" PR reached <strong>{_fmt(r.performance_ratio_pct)}%</strong> ({abs(pr_delta):.1f} percentage points {pr_word} budget)."

    html = f"""<div class="section" id="{_section_id(1)}">
    <h2 class="section-title">1. Monthly Performance Summary</h2>
    {kpi_cards}
    {gauges_html}
    <div class="card">{params_html}</div>
    <div class="insight-box">{insight}</div>
</div>"""

    return html, gauge_scripts


# ---------------------------------------------------------------------------
# Section 2: Summary YTD
# ---------------------------------------------------------------------------

def _render_ytd(report: MonthlyReport) -> str:
    ytd = report.ytd
    if not ytd:
        return f'<div class="section" id="{_section_id(2)}"><h2 class="section-title">2. Year-To-Date Summary</h2><div class="card"><p>No YTD data available.</p></div></div>', ""

    # Table
    rows = ""
    for ms in ytd:
        vs_energy_style = _color_cell(-ms.vs_budget_energy_mwh, positive_is_good=True)
        vs_irr_style = ""
        vs_irr_val = "\u2014"
        if ms.vs_budget_irr is not None:
            vs_irr_style = _color_cell(-ms.vs_budget_irr, positive_is_good=True)
            vs_irr_val = _fmt(ms.vs_budget_irr)

        rows += f"""<tr>
    <td>{ms.month_name}</td>
    <td>{_fmt(ms.capacity_mwp, 2)}</td>
    <td>{_fmt(ms.budget_energy_mwh)}</td>
    <td>{_fmt(ms.actual_energy_mwh)}</td>
    <td>{_fmt(ms.curtailment_mwh)}</td>
    <td style="{vs_energy_style}">{_fmt_delta(-ms.vs_budget_energy_mwh)}</td>
    <td>{_fmt(ms.norm_yield_mwh_mwp)}</td>
    <td>{_fmt(ms.wc_budget_mwh)}</td>
    <td>{_fmt(ms.losses_mwh)}</td>
    <td>{_fmt(ms.budget_irr_kwh_m2)}</td>
    <td>{_fmt(ms.actual_irr_kwh_m2) if ms.actual_irr_kwh_m2 is not None else "\u2014"}</td>
    <td style="{vs_irr_style}">{vs_irr_val}</td>
    <td>{_fmt_pct(ms.budget_pr_pct)}</td>
    <td>{_fmt_pct(ms.actual_pr_pct) if ms.actual_pr_pct is not None else "\u2014"}</td>
    <td>{_fmt(ms.availability_loss_mwh)}</td>
</tr>"""

    # Totals
    tot_budget = sum(m.budget_energy_mwh for m in ytd)
    tot_actual = sum(m.actual_energy_mwh for m in ytd)
    tot_curt = sum(m.curtailment_mwh for m in ytd)
    tot_losses = sum(m.losses_mwh for m in ytd)
    tot_avail = sum(m.availability_loss_mwh for m in ytd)
    tot_vs = tot_actual - tot_budget
    tot_vs_style = _color_cell(tot_vs)
    rows += f"""<tr class="total-row">
    <td>Total</td><td></td>
    <td>{_fmt(tot_budget)}</td><td>{_fmt(tot_actual)}</td><td>{_fmt(tot_curt)}</td>
    <td style="{tot_vs_style}">{_fmt_delta(tot_vs)}</td>
    <td></td><td></td><td>{_fmt(tot_losses)}</td>
    <td></td><td></td><td></td><td></td><td></td><td>{_fmt(tot_avail)}</td>
</tr>"""

    table = f"""<div class="table-scroll"><table class="data-table">
<thead><tr>
    <th>Month</th><th>Capacity (MWp)</th><th>Budget (MWh)</th><th>Actual (MWh)</th>
    <th>Curtail (MWh)</th><th>vs Budget</th><th>Norm Yield</th><th>WC Budget</th>
    <th>Losses</th><th>Bud Irr</th><th>Act Irr</th><th>vs Irr</th>
    <th>Bud PR</th><th>Act PR</th><th>Avail Loss</th>
</tr></thead><tbody>{rows}</tbody></table></div>"""

    # Chart: grouped bars + lines
    months = [ms.month_name for ms in ytd]
    budget_vals = [round(ms.budget_energy_mwh, 1) for ms in ytd]
    actual_vals = [round(ms.actual_energy_mwh, 1) for ms in ytd]
    budget_irr = [round(ms.budget_irr_kwh_m2, 1) for ms in ytd]
    actual_irr = [ms.actual_irr_kwh_m2 if ms.actual_irr_kwh_m2 is not None else None for ms in ytd]

    traces = [
        {"x": months, "y": budget_vals, "name": "Budget (MWh)", "type": "bar",
         "marker": {"color": _C["chart_light"]}, "yaxis": "y"},
        {"x": months, "y": actual_vals, "name": "Actual (MWh)", "type": "bar",
         "marker": {"color": _C["chart_dark"]}, "yaxis": "y"},
        {"x": months, "y": budget_irr, "name": "Budget Irr (kWh/m\u00b2)", "type": "scatter",
         "mode": "lines+markers", "line": {"color": _C["chart_amber"], "dash": "dash"},
         "marker": {"size": 6}, "yaxis": "y2"},
    ]
    if any(v is not None for v in actual_irr):
        traces.append(
            {"x": months, "y": actual_irr, "name": "Actual Irr (kWh/m\u00b2)", "type": "scatter",
             "mode": "lines+markers", "line": {"color": _C["amber"]},
             "marker": {"size": 6}, "yaxis": "y2"}
        )

    layout = {
        "barmode": "group",
        "height": 380,
        "margin": {"t": 30, "b": 40, "l": 60, "r": 60},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 12, "color": _C["text"]},
        "legend": {"orientation": "h", "y": -0.15},
        "yaxis": {"title": "Energy (MWh)", "gridcolor": "#e2e8f0"},
        "yaxis2": {"title": "Irradiation (kWh/m\u00b2)", "overlaying": "y", "side": "right", "gridcolor": "transparent"},
    }

    script = f"""Plotly.newPlot('chart-ytd', {_safe_json(traces)}, {_safe_json(layout)}, {_plotly_config()});"""

    html = f"""<div class="section" id="{_section_id(2)}">
    <h2 class="section-title">2. Year-To-Date Summary</h2>
    <div class="card">{table}</div>
    <div class="card"><div id="chart-ytd" class="chart-container"></div></div>
</div>"""

    return html, script


# ---------------------------------------------------------------------------
# Section 3: Daily Generation Summary
# ---------------------------------------------------------------------------

def _render_daily_generation(report: MonthlyReport) -> str:
    daily = report.daily
    if not daily:
        return f'<div class="section" id="{_section_id(3)}"><h2 class="section-title">3. Daily Generation</h2><div class="card"><p>No daily data.</p></div></div>', ""

    rows = ""
    for d in daily:
        rows += f"""<tr>
    <td>{d.day} ({d.weekday})</td>
    <td>{_fmt(d.actual_energy_mwh)}</td>
    <td>{_fmt(d.actual_irradiation_kwh_m2) if d.actual_irradiation_kwh_m2 is not None else "\u2014"}</td>
    <td>{_fmt(d.norm_yield_kwh_kwp, 2)}</td>
</tr>"""

    # Totals
    tot_energy = sum(d.actual_energy_mwh for d in daily)
    irr_vals = [d.actual_irradiation_kwh_m2 for d in daily if d.actual_irradiation_kwh_m2 is not None]
    tot_irr = sum(irr_vals) if irr_vals else None
    tot_yield = sum(d.norm_yield_kwh_kwp for d in daily)
    rows += f"""<tr class="total-row">
    <td>Total</td><td>{_fmt(tot_energy)}</td>
    <td>{_fmt(tot_irr) if tot_irr is not None else "\u2014"}</td>
    <td>{_fmt(tot_yield, 2)}</td>
</tr>"""

    table = f"""<div class="table-scroll"><table class="data-table">
<thead><tr><th>Day</th><th>Energy (MWh)</th><th>Irr (kWh/m\u00b2)</th><th>Norm Yield (kWh/kWp)</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""

    # Chart
    days = [d.day for d in daily]
    energy = [round(d.actual_energy_mwh, 2) for d in daily]
    irr = [round(d.actual_irradiation_kwh_m2, 2) if d.actual_irradiation_kwh_m2 is not None else None for d in daily]

    traces = [
        {"x": days, "y": energy, "name": "Energy (MWh)", "type": "bar",
         "marker": {"color": _C["chart_dark"]}, "yaxis": "y"},
    ]
    if any(v is not None for v in irr):
        traces.append(
            {"x": days, "y": irr, "name": "Irradiation (kWh/m\u00b2)", "type": "scatter",
             "mode": "lines+markers", "line": {"color": _C["chart_amber"], "width": 2},
             "marker": {"size": 5}, "yaxis": "y2"}
        )

    layout = {
        "height": 350,
        "margin": {"t": 20, "b": 40, "l": 60, "r": 60},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 12, "color": _C["text"]},
        "legend": {"orientation": "h", "y": -0.15},
        "xaxis": {"title": "Day", "dtick": 1},
        "yaxis": {"title": "Energy (MWh)", "gridcolor": "#e2e8f0"},
        "yaxis2": {"title": "Irradiation (kWh/m\u00b2)", "overlaying": "y", "side": "right", "gridcolor": "transparent"},
    }

    # Insight
    best_d = max(daily, key=lambda d: d.actual_energy_mwh)
    worst_d = min(daily, key=lambda d: d.actual_energy_mwh)
    avg_e = tot_energy / len(daily)
    insight = (
        f"Average daily generation: <strong>{_fmt(avg_e)} MWh</strong>. "
        f"Highest: day {best_d.day} ({_fmt(best_d.actual_energy_mwh)} MWh), "
        f"lowest: day {worst_d.day} ({_fmt(worst_d.actual_energy_mwh)} MWh)."
    )

    script = f"""Plotly.newPlot('chart-daily-gen', {_safe_json(traces)}, {_safe_json(layout)}, {_plotly_config()});"""

    html = f"""<div class="section" id="{_section_id(3)}">
    <h2 class="section-title">3. Daily Generation</h2>
    <div class="card">{table}</div>
    <div class="card"><div id="chart-daily-gen" class="chart-container"></div></div>
    <div class="insight-box">{insight}</div>
</div>"""

    return html, script


# ---------------------------------------------------------------------------
# Section 4: PR vs Temperature Trends
# ---------------------------------------------------------------------------

def _render_pr_temp(report: MonthlyReport) -> str:
    daily = report.daily
    if not daily:
        return f'<div class="section" id="{_section_id(4)}"><h2 class="section-title">4. PR &amp; Temperature</h2><div class="card"><p>No data.</p></div></div>', ""

    rows = ""
    for d in daily:
        rows += f"""<tr>
    <td>{d.day} ({d.weekday})</td>
    <td>{_fmt(d.performance_ratio_pct) if d.performance_ratio_pct is not None else "\u2014"}</td>
    <td>{_fmt(d.avg_ambient_temp_c) if d.avg_ambient_temp_c is not None else "\u2014"}</td>
    <td>{_fmt(d.avg_module_temp_c) if d.avg_module_temp_c is not None else "\u2014"}</td>
</tr>"""

    table = f"""<div class="table-scroll"><table class="data-table">
<thead><tr><th>Day</th><th>PR (%)</th><th>Ambient Temp (\u00b0C)</th><th>Module Temp (\u00b0C)</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""

    days = [d.day for d in daily]
    pr_vals = [round(d.performance_ratio_pct, 1) if d.performance_ratio_pct is not None else None for d in daily]
    mod_temp = [round(d.avg_module_temp_c, 1) if d.avg_module_temp_c is not None else None for d in daily]

    traces = [
        {"x": days, "y": pr_vals, "name": "PR (%)", "type": "bar",
         "marker": {"color": _C["chart_dark"]}, "yaxis": "y"},
    ]
    if any(v is not None for v in mod_temp):
        traces.append(
            {"x": days, "y": mod_temp, "name": "Module Temp (\u00b0C)", "type": "scatter",
             "mode": "lines+markers", "line": {"color": _C["chart_amber"], "width": 2},
             "marker": {"size": 5}, "yaxis": "y2"}
        )

    layout = {
        "height": 350,
        "margin": {"t": 20, "b": 40, "l": 60, "r": 60},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 12, "color": _C["text"]},
        "legend": {"orientation": "h", "y": -0.15},
        "xaxis": {"title": "Day", "dtick": 1},
        "yaxis": {"title": "PR (%)", "gridcolor": "#e2e8f0"},
        "yaxis2": {"title": "Module Temp (\u00b0C)", "overlaying": "y", "side": "right", "gridcolor": "transparent"},
    }

    script = f"""Plotly.newPlot('chart-pr-temp', {_safe_json(traces)}, {_safe_json(layout)}, {_plotly_config()});"""

    html = f"""<div class="section" id="{_section_id(4)}">
    <h2 class="section-title">4. Performance Ratio &amp; Temperature</h2>
    <div class="card">{table}</div>
    <div class="card"><div id="chart-pr-temp" class="chart-container"></div></div>
</div>"""

    return html, script


# ---------------------------------------------------------------------------
# Section 5: Expected vs Actual Generation
# ---------------------------------------------------------------------------

def _render_expected_vs_actual(report: MonthlyReport) -> str:
    daily = report.daily
    if not daily:
        return f'<div class="section" id="{_section_id(5)}"><h2 class="section-title">5. Expected vs Actual</h2><div class="card"><p>No data.</p></div></div>', ""

    rows = ""
    for d in daily:
        rows += f"""<tr>
    <td>{d.day} ({d.weekday})</td>
    <td>{_fmt(d.expected_gen_mwh) if d.expected_gen_mwh is not None else "\u2014"}</td>
    <td>{_fmt(d.actual_energy_mwh)}</td>
</tr>"""

    table = f"""<div class="table-scroll"><table class="data-table">
<thead><tr><th>Day</th><th>Expected (MWh)</th><th>Actual (MWh)</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""

    days = [d.day for d in daily]
    expected = [round(d.expected_gen_mwh, 2) if d.expected_gen_mwh is not None else None for d in daily]
    actual = [round(d.actual_energy_mwh, 2) for d in daily]

    traces = [
        {"x": days, "y": expected, "name": "Expected (MWh)", "type": "scatter",
         "mode": "lines", "fill": "tozeroy",
         "fillcolor": "rgba(147,197,253,0.3)", "line": {"color": _C["chart_light"], "width": 1}},
        {"x": days, "y": actual, "name": "Actual (MWh)", "type": "scatter",
         "mode": "lines", "fill": "tozeroy",
         "fillcolor": "rgba(30,64,175,0.3)", "line": {"color": _C["chart_dark"], "width": 2}},
    ]

    layout = {
        "height": 350,
        "margin": {"t": 20, "b": 40, "l": 60, "r": 30},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 12, "color": _C["text"]},
        "legend": {"orientation": "h", "y": -0.15},
        "xaxis": {"title": "Day", "dtick": 1},
        "yaxis": {"title": "Energy (MWh)", "gridcolor": "#e2e8f0"},
    }

    formula = "Expected Gen = Irradiation \u00d7 DC Capacity \u00d7 Standard PR"

    script = f"""Plotly.newPlot('chart-exp-act', {_safe_json(traces)}, {_safe_json(layout)}, {_plotly_config()});"""

    html = f"""<div class="section" id="{_section_id(5)}">
    <h2 class="section-title">5. Expected vs Actual Generation</h2>
    <div class="card"><div id="chart-exp-act" class="chart-container"></div></div>
    <div class="formula-box">{formula}</div>
    <div class="card">{table}</div>
</div>"""

    return html, script


# ---------------------------------------------------------------------------
# Section 6: Performance Index
# ---------------------------------------------------------------------------

def _render_performance_index(report: MonthlyReport) -> str:
    daily = report.daily
    if not daily:
        return f'<div class="section" id="{_section_id(6)}"><h2 class="section-title">6. Performance Index</h2><div class="card"><p>No data.</p></div></div>', ""

    rows = ""
    for d in daily:
        pi = d.performance_index_pct
        if pi is not None:
            if pi >= 80:
                icon = "\U0001f7e2"  # green circle
            elif pi >= 60:
                icon = "\U0001f7e1"  # yellow circle
            else:
                icon = "\U0001f534"  # red circle
        else:
            icon = "\u2014"
        rows += f"""<tr>
    <td>{d.day} ({d.weekday})</td>
    <td>{icon}</td>
    <td>{_fmt(pi) if pi is not None else "\u2014"}</td>
</tr>"""

    table = f"""<div class="table-scroll"><table class="data-table">
<thead><tr><th>Day</th><th>Status</th><th>PI (%)</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""

    days = [d.day for d in daily]
    pi_vals = [round(d.performance_index_pct, 1) if d.performance_index_pct is not None else None for d in daily]

    # Colors based on value
    colors = []
    for v in pi_vals:
        if v is None:
            colors.append("#d1d5db")
        elif v >= 80:
            colors.append(_C["green"])
        elif v >= 60:
            colors.append(_C["amber"])
        else:
            colors.append(_C["red"])

    traces = [
        {"x": days, "y": pi_vals, "type": "bar",
         "marker": {"color": colors}, "name": "PI (%)"},
    ]

    # Reference lines
    shapes = [
        {"type": "line", "x0": 0.5, "x1": max(days) + 0.5, "y0": 80, "y1": 80,
         "line": {"color": _C["green"], "width": 2, "dash": "dash"}},
        {"type": "line", "x0": 0.5, "x1": max(days) + 0.5, "y0": 100, "y1": 100,
         "line": {"color": _C["chart_dark"], "width": 2, "dash": "dash"}},
    ]

    layout = {
        "height": 350,
        "margin": {"t": 20, "b": 40, "l": 60, "r": 30},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 12, "color": _C["text"]},
        "showlegend": False,
        "xaxis": {"title": "Day", "dtick": 1},
        "yaxis": {"title": "Performance Index (%)", "gridcolor": "#e2e8f0"},
        "shapes": shapes,
    }

    # Insight
    valid_pi = [v for v in pi_vals if v is not None]
    if valid_pi:
        avg_pi = sum(valid_pi) / len(valid_pi)
        good_days = sum(1 for v in valid_pi if v >= 80)
        insight = (
            f"Average PI: <strong>{avg_pi:.1f}%</strong>. "
            f"<strong>{good_days}</strong> of {len(valid_pi)} days reached \u2265 80% PI."
        )
    else:
        insight = "No PI values calculated (missing irradiation data)."

    script = f"""Plotly.newPlot('chart-pi', {_safe_json(traces)}, {_safe_json(layout)}, {_plotly_config()});"""

    html = f"""<div class="section" id="{_section_id(6)}">
    <h2 class="section-title">6. Performance Index</h2>
    <div class="card"><div id="chart-pi" class="chart-container"></div></div>
    <div class="card">{table}</div>
    <div class="insight-box">{insight}</div>
</div>"""

    return html, script


# ---------------------------------------------------------------------------
# Section 7: Efficiency vs Module Temp vs Irradiation
# ---------------------------------------------------------------------------

def _render_efficiency(report: MonthlyReport) -> str:
    daily = report.daily
    if not daily:
        return f'<div class="section" id="{_section_id(7)}"><h2 class="section-title">7. Efficiency</h2><div class="card"><p>No data.</p></div></div>', ""

    days = [d.day for d in daily]
    eff = [round(d.efficiency_pct, 1) if d.efficiency_pct is not None else None for d in daily]
    mod_temp = [round(d.avg_module_temp_c, 1) if d.avg_module_temp_c is not None else None for d in daily]
    irr = [round(d.actual_irradiation_kwh_m2, 2) if d.actual_irradiation_kwh_m2 is not None else None for d in daily]

    has_eff = any(v is not None for v in eff)
    has_temp = any(v is not None for v in mod_temp)
    has_irr = any(v is not None for v in irr)

    scripts = ""

    # Chart a) Efficiency vs Module Temp
    traces_a = []
    if has_eff:
        traces_a.append(
            {"x": days, "y": eff, "name": "Efficiency (%)", "type": "scatter",
             "mode": "lines", "fill": "tozeroy",
             "fillcolor": "rgba(30,64,175,0.15)", "line": {"color": _C["chart_dark"], "width": 2}, "yaxis": "y"}
        )
    if has_temp:
        traces_a.append(
            {"x": days, "y": mod_temp, "name": "Module Temp (\u00b0C)", "type": "scatter",
             "mode": "lines", "fill": "tozeroy",
             "fillcolor": "rgba(245,158,11,0.15)", "line": {"color": _C["chart_amber"], "width": 2}, "yaxis": "y2"}
        )

    layout_a = {
        "height": 300,
        "margin": {"t": 30, "b": 40, "l": 60, "r": 60},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 12, "color": _C["text"]},
        "legend": {"orientation": "h", "y": -0.2},
        "title": {"text": "Efficiency vs Module Temperature", "font": {"size": 14}},
        "xaxis": {"title": "Day", "dtick": 1},
        "yaxis": {"title": "Efficiency (%)", "gridcolor": "#e2e8f0"},
        "yaxis2": {"title": "Module Temp (\u00b0C)", "overlaying": "y", "side": "right", "gridcolor": "transparent"},
    }

    # Chart b) Efficiency vs Irradiation
    traces_b = []
    if has_eff:
        traces_b.append(
            {"x": days, "y": eff, "name": "Efficiency (%)", "type": "scatter",
             "mode": "lines", "fill": "tozeroy",
             "fillcolor": "rgba(30,64,175,0.15)", "line": {"color": _C["chart_dark"], "width": 2}, "yaxis": "y"}
        )
    if has_irr:
        traces_b.append(
            {"x": days, "y": irr, "name": "Irradiation (kWh/m\u00b2)", "type": "scatter",
             "mode": "lines", "fill": "tozeroy",
             "fillcolor": "rgba(245,158,11,0.15)", "line": {"color": _C["chart_amber"], "width": 2}, "yaxis": "y2"}
        )

    layout_b = dict(layout_a)
    layout_b["title"] = {"text": "Efficiency vs Irradiation", "font": {"size": 14}}
    layout_b["yaxis2"] = {"title": "Irradiation (kWh/m\u00b2)", "overlaying": "y", "side": "right", "gridcolor": "transparent"}

    scripts = f"""
Plotly.newPlot('chart-eff-temp', {_safe_json(traces_a)}, {_safe_json(layout_a)}, {_plotly_config()});
Plotly.newPlot('chart-eff-irr', {_safe_json(traces_b)}, {_safe_json(layout_b)}, {_plotly_config()});
"""

    no_data_msg = ""
    if not has_eff:
        no_data_msg = '<div class="insight-box">Efficiency data missing (requires both ActivePower and ActivePowerMeter).</div>'

    html = f"""<div class="section" id="{_section_id(7)}">
    <h2 class="section-title">7. Efficiency vs Module Temperature &amp; Irradiation</h2>
    {no_data_msg}
    <div class="side-by-side">
        <div class="card"><div id="chart-eff-temp" class="chart-container" style="min-height:300px;"></div></div>
        <div class="card"><div id="chart-eff-irr" class="chart-container" style="min-height:300px;"></div></div>
    </div>
</div>"""

    return html, scripts


# ---------------------------------------------------------------------------
# Section 8: Power vs Irradiation Trend (small multiples)
# ---------------------------------------------------------------------------

def _render_power_irr_trend(report: MonthlyReport) -> str:
    daily = report.daily
    if not daily:
        return f'<div class="section" id="{_section_id(8)}"><h2 class="section-title">8. Power &amp; Irradiance per Day</h2><div class="card"><p>No data.</p></div></div>', ""

    # We need the day details from the report's best/worst detail pattern
    # but we don't have all days' 15-min data. We'll create a message if unavailable.
    # Check if best_day_detail exists as a proxy for 15-min data availability
    if report.best_day_detail is None and report.worst_day_detail is None:
        html = f"""<div class="section" id="{_section_id(8)}">
    <h2 class="section-title">8. Power &amp; Irradiance per Day</h2>
    <div class="insight-box">
        15-minute data for small charts per day requires detailed data loading.
        See section 12 for best and worst day profiles.
    </div>
</div>"""
        return html, ""

    # Build a simplified view using available day details
    charts_html = ""
    scripts = ""
    chart_count = 0

    details_to_show = []
    if report.best_day_detail:
        details_to_show.append(("Best Day", report.best_day_detail))
    if report.worst_day_detail:
        details_to_show.append(("Worst Day", report.worst_day_detail))

    # Also show best/worst from best_days list (top 5) with available details
    for detail_label, detail in details_to_show:
        chart_id = f"chart-power-irr-{chart_count}"
        chart_count += 1

        traces = [
            {"x": detail.timestamps, "y": detail.power_mw, "name": "Power (MW)",
             "type": "scatter", "mode": "lines", "fill": "tozeroy",
             "fillcolor": "rgba(30,64,175,0.2)", "line": {"color": _C["chart_dark"], "width": 2},
             "yaxis": "y"},
        ]
        irr_clean = [v for v in detail.irradiance_wm2 if v is not None]
        if irr_clean:
            traces.append(
                {"x": detail.timestamps, "y": detail.irradiance_wm2, "name": "Irradiance (W/m\u00b2)",
                 "type": "scatter", "mode": "lines", "fill": "tozeroy",
                 "fillcolor": "rgba(245,158,11,0.15)", "line": {"color": _C["chart_amber"], "width": 1.5},
                 "yaxis": "y2"}
            )

        layout = {
            "height": 250,
            "margin": {"t": 30, "b": 30, "l": 50, "r": 50},
            "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 11, "color": _C["text"]},
            "title": {"text": f"{detail_label}: {detail.date_str}", "font": {"size": 13}},
            "legend": {"orientation": "h", "y": -0.25, "font": {"size": 10}},
            "xaxis": {"title": ""},
            "yaxis": {"title": "MW", "gridcolor": "#e2e8f0"},
            "yaxis2": {"title": "W/m\u00b2", "overlaying": "y", "side": "right", "gridcolor": "transparent"},
        }

        charts_html += f'<div class="card"><div id="{chart_id}" class="chart-container" style="min-height:250px;"></div></div>'
        scripts += f"""Plotly.newPlot('{chart_id}', {_safe_json(traces)}, {_safe_json(layout)}, {_plotly_config()});\n"""

    html = f"""<div class="section" id="{_section_id(8)}">
    <h2 class="section-title">8. Power &amp; Irradiance per Day</h2>
    <div class="side-by-side">{charts_html}</div>
</div>"""

    return html, scripts


# ---------------------------------------------------------------------------
# Section 9: Energy Loss Cascade (MWh)
# ---------------------------------------------------------------------------

def _render_loss_cascade_mwh(report: MonthlyReport) -> str:
    lc = report.losses

    categories = [
        "Budget", "Curtailment", "Irradiance Shortfall",
        "Availability", "Temperature", "Other", "Actual"
    ]
    values = [
        lc.budget_energy_mwh,
        -lc.curtailment_loss_mwh,
        -lc.irradiance_shortfall_loss_mwh,
        -lc.availability_loss_mwh,
        -lc.temperature_loss_mwh,
        -lc.other_losses_mwh,
        lc.actual_energy_mwh,
    ]

    measure = ["absolute", "relative", "relative", "relative", "relative", "relative", "total"]

    traces = [{
        "type": "waterfall",
        "orientation": "v",
        "measure": measure,
        "x": categories,
        "y": [round(v, 2) for v in values],
        "textposition": "outside",
        "text": [_fmt(abs(v)) for v in values],
        "connector": {"line": {"color": "#e2e8f0"}},
        "increasing": {"marker": {"color": _C["green"]}},
        "decreasing": {"marker": {"color": _C["red"]}},
        "totals": {"marker": {"color": _C["chart_dark"]}},
    }]

    layout = {
        "height": 400,
        "margin": {"t": 30, "b": 60, "l": 60, "r": 30},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 12, "color": _C["text"]},
        "showlegend": False,
        "yaxis": {"title": "Energy (MWh)", "gridcolor": "#e2e8f0"},
    }

    # Table
    table_rows = [
        ("Budget", _fmt(lc.budget_energy_mwh)),
        ("Curtailment", _fmt(-lc.curtailment_loss_mwh)),
        ("Irradiance Shortfall", _fmt(-lc.irradiance_shortfall_loss_mwh)),
        ("Availability Loss", _fmt(-lc.availability_loss_mwh)),
        ("Temperature Loss", _fmt(-lc.temperature_loss_mwh)),
        ("Other Losses", _fmt(-lc.other_losses_mwh)),
        ("<strong>Actual Generation</strong>", f"<strong>{_fmt(lc.actual_energy_mwh)}</strong>"),
    ]
    table_html = '<table class="params-table"><tr><th>Category</th><th>MWh</th></tr>'
    for label, val in table_rows:
        table_html += f"<tr><td>{label}</td><td>{val}</td></tr>"
    table_html += "</table>"

    script = f"""Plotly.newPlot('chart-loss-mwh', {_safe_json(traces)}, {_safe_json(layout)}, {_plotly_config()});"""

    html = f"""<div class="section" id="{_section_id(9)}">
    <h2 class="section-title">9. Loss Analysis (MWh)</h2>
    <div class="card"><div id="chart-loss-mwh" class="chart-container"></div></div>
    <div class="card">{table_html}</div>
</div>"""

    return html, script


# ---------------------------------------------------------------------------
# Section 10: Energy Loss Cascade (%)
# ---------------------------------------------------------------------------

def _render_loss_cascade_pct(report: MonthlyReport) -> str:
    lc = report.losses
    budget = lc.budget_energy_mwh if lc.budget_energy_mwh > 0 else 1.0

    def to_pct(v):
        return round(v / budget * 100, 2)

    categories = [
        "Budget", "Curtailment", "Irradiance Shortfall",
        "Availability", "Temperature", "Other", "Actual"
    ]
    values_pct = [
        100.0,
        -to_pct(lc.curtailment_loss_mwh),
        -to_pct(lc.irradiance_shortfall_loss_mwh),
        -to_pct(lc.availability_loss_mwh),
        -to_pct(lc.temperature_loss_mwh),
        -to_pct(lc.other_losses_mwh),
        to_pct(lc.actual_energy_mwh),
    ]
    measure = ["absolute", "relative", "relative", "relative", "relative", "relative", "total"]

    traces = [{
        "type": "waterfall",
        "orientation": "v",
        "measure": measure,
        "x": categories,
        "y": [round(v, 2) for v in values_pct],
        "textposition": "outside",
        "text": [f"{abs(v):.1f}%" for v in values_pct],
        "connector": {"line": {"color": "#e2e8f0"}},
        "increasing": {"marker": {"color": _C["green"]}},
        "decreasing": {"marker": {"color": _C["red"]}},
        "totals": {"marker": {"color": _C["chart_dark"]}},
    }]

    layout = {
        "height": 400,
        "margin": {"t": 30, "b": 60, "l": 60, "r": 30},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 12, "color": _C["text"]},
        "showlegend": False,
        "yaxis": {"title": "Share of Budget (%)", "gridcolor": "#e2e8f0"},
    }

    # Table
    table_rows = [
        ("Budget", "100.0%"),
        ("Curtailment", f"{-to_pct(lc.curtailment_loss_mwh):.1f}%"),
        ("Irradiance Shortfall", f"{-to_pct(lc.irradiance_shortfall_loss_mwh):.1f}%"),
        ("Availability Loss", f"{-to_pct(lc.availability_loss_mwh):.1f}%"),
        ("Temperature Loss", f"{-to_pct(lc.temperature_loss_mwh):.1f}%"),
        ("Other Losses", f"{-to_pct(lc.other_losses_mwh):.1f}%"),
        ("<strong>Actual Generation</strong>", f"<strong>{to_pct(lc.actual_energy_mwh):.1f}%</strong>"),
    ]
    table_html = '<table class="params-table"><tr><th>Category</th><th>% of Budget</th></tr>'
    for label, val in table_rows:
        table_html += f"<tr><td>{label}</td><td>{val}</td></tr>"
    table_html += "</table>"

    script = f"""Plotly.newPlot('chart-loss-pct', {_safe_json(traces)}, {_safe_json(layout)}, {_plotly_config()});"""

    html = f"""<div class="section" id="{_section_id(10)}">
    <h2 class="section-title">10. Loss Analysis (%)</h2>
    <div class="card"><div id="chart-loss-pct" class="chart-container"></div></div>
    <div class="card">{table_html}</div>
</div>"""

    return html, script


# ---------------------------------------------------------------------------
# Section 11: Curtailment & Irradiance Shortfall Loss Trend
# ---------------------------------------------------------------------------

def _render_curtailment_irr_trend(report: MonthlyReport) -> str:
    ytd = report.ytd
    if not ytd:
        return f'<div class="section" id="{_section_id(11)}"><h2 class="section-title">11. Curtailment &amp; Irradiance Shortfall</h2><div class="card"><p>No YTD data.</p></div></div>', ""

    months = [ms.month_name for ms in ytd]

    # Curtailment MWh
    curt_mwh = [round(ms.curtailment_mwh, 2) for ms in ytd]
    # Curtailment % of budget
    curt_pct = [round(ms.curtailment_mwh / ms.budget_energy_mwh * 100, 1) if ms.budget_energy_mwh > 0 else 0 for ms in ytd]

    # Irradiance shortfall (vs_budget_irr is budget - actual, positive = shortfall)
    irr_shortfall_kwh = [round(ms.vs_budget_irr, 2) if ms.vs_budget_irr is not None else 0 for ms in ytd]
    irr_shortfall_pct = [
        round(ms.vs_budget_irr / ms.budget_irr_kwh_m2 * 100, 1)
        if (ms.vs_budget_irr is not None and ms.budget_irr_kwh_m2 > 0) else 0
        for ms in ytd
    ]

    traces_curt = [
        {"x": months, "y": curt_mwh, "type": "bar", "name": "MWh",
         "marker": {"color": _C["chart_dark"]}},
    ]
    layout_curt = {
        "height": 280,
        "margin": {"t": 30, "b": 40, "l": 50, "r": 30},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 11, "color": _C["text"]},
        "title": {"text": "Curtailment (MWh)", "font": {"size": 13}},
        "showlegend": False,
        "yaxis": {"gridcolor": "#e2e8f0"},
    }

    traces_curt_pct = [
        {"x": months, "y": curt_pct, "type": "bar", "name": "%",
         "marker": {"color": _C["accent"]}},
    ]
    layout_curt_pct = dict(layout_curt)
    layout_curt_pct["title"] = {"text": "Curtailment (% of Budget)", "font": {"size": 13}}

    traces_irr = [
        {"x": months, "y": irr_shortfall_kwh, "type": "bar", "name": "kWh/m\u00b2",
         "marker": {"color": _C["chart_amber"]}},
    ]
    layout_irr = dict(layout_curt)
    layout_irr["title"] = {"text": "Irradiance Shortfall (kWh/m\u00b2)", "font": {"size": 13}}

    traces_irr_pct = [
        {"x": months, "y": irr_shortfall_pct, "type": "bar", "name": "%",
         "marker": {"color": _C["amber"]}},
    ]
    layout_irr_pct = dict(layout_curt)
    layout_irr_pct["title"] = {"text": "Irradiance Shortfall (% of Budget)", "font": {"size": 13}}

    script = f"""
Plotly.newPlot('chart-curt-mwh', {_safe_json(traces_curt)}, {_safe_json(layout_curt)}, {_plotly_config()});
Plotly.newPlot('chart-curt-pct', {_safe_json(traces_curt_pct)}, {_safe_json(layout_curt_pct)}, {_plotly_config()});
Plotly.newPlot('chart-irr-short-mwh', {_safe_json(traces_irr)}, {_safe_json(layout_irr)}, {_plotly_config()});
Plotly.newPlot('chart-irr-short-pct', {_safe_json(traces_irr_pct)}, {_safe_json(layout_irr_pct)}, {_plotly_config()});
"""

    html = f"""<div class="section" id="{_section_id(11)}">
    <h2 class="section-title">11. Curtailment &amp; Irradiance Shortfall (YTD Trend)</h2>
    <div class="side-by-side">
        <div>
            <div class="card"><div id="chart-curt-mwh" class="chart-container" style="min-height:280px;"></div></div>
            <div class="card"><div id="chart-curt-pct" class="chart-container" style="min-height:280px;"></div></div>
        </div>
        <div>
            <div class="card"><div id="chart-irr-short-mwh" class="chart-container" style="min-height:280px;"></div></div>
            <div class="card"><div id="chart-irr-short-pct" class="chart-container" style="min-height:280px;"></div></div>
        </div>
    </div>
</div>"""

    return html, script


# ---------------------------------------------------------------------------
# Section 12: Best & Worst Performance Day
# ---------------------------------------------------------------------------

def _render_day_detail_card(label: str, detail: Optional[DayDetail], day_data: Optional[DailyData], chart_id: str) -> tuple[str, str]:
    """Rendera ett kort med 15-min profil för en dag."""
    if detail is None or day_data is None:
        card = f"""<div class="card" style="text-align:center; padding:40px;">
    <div style="font-size:16px; font-weight:600; color:{_C['primary']};">{label}</div>
    <div style="color:{_C['muted']}; margin-top:8px;">No detail data available.</div>
</div>"""
        return card, ""

    energy_str = _fmt(day_data.actual_energy_mwh)
    pr_str = _fmt(day_data.performance_ratio_pct) if day_data.performance_ratio_pct is not None else "\u2014"

    traces = [
        {"x": detail.timestamps, "y": detail.power_mw, "name": "Power (MW)",
         "type": "scatter", "mode": "lines", "fill": "tozeroy",
         "fillcolor": "rgba(30,64,175,0.2)", "line": {"color": _C["chart_dark"], "width": 2},
         "yaxis": "y"},
    ]
    if any(v is not None for v in detail.irradiance_wm2):
        traces.append(
            {"x": detail.timestamps, "y": detail.irradiance_wm2, "name": "Irradiance (W/m\u00b2)",
             "type": "scatter", "mode": "lines",
             "line": {"color": _C["chart_amber"], "width": 1.5}, "yaxis": "y2"}
        )

    layout = {
        "height": 250,
        "margin": {"t": 10, "b": 30, "l": 50, "r": 50},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 11, "color": _C["text"]},
        "legend": {"orientation": "h", "y": -0.3, "font": {"size": 10}},
        "xaxis": {},
        "yaxis": {"title": "MW", "gridcolor": "#e2e8f0"},
        "yaxis2": {"title": "W/m\u00b2", "overlaying": "y", "side": "right", "gridcolor": "transparent"},
    }

    card = f"""<div class="card">
    <div style="text-align:center; margin-bottom:8px;">
        <div style="font-size:16px; font-weight:600; color:{_C['primary']};">{label}</div>
        <div style="font-size:14px; color:{_C['muted']};">{detail.date_str}</div>
        <div style="font-size:20px; font-weight:700; color:{_C['text']}; margin-top:4px;">{energy_str} MWh</div>
        <div style="font-size:13px; color:{_C['muted']};">PR: {pr_str}%</div>
    </div>
    <div id="{chart_id}" class="chart-container" style="min-height:250px;"></div>
</div>"""

    script = f"""Plotly.newPlot('{chart_id}', {_safe_json(traces)}, {_safe_json(layout)}, {_plotly_config()});"""
    return card, script


def _render_best_worst_day(report: MonthlyReport) -> str:
    best_day_data = report.best_days[0] if report.best_days else None
    worst_day_data = report.worst_days[0] if report.worst_days else None

    best_card, best_script = _render_day_detail_card(
        "Best Generation Day", report.best_day_detail, best_day_data, "chart-best-day"
    )
    worst_card, worst_script = _render_day_detail_card(
        "Worst Generation Day", report.worst_day_detail, worst_day_data, "chart-worst-day"
    )

    html = f"""<div class="section" id="{_section_id(12)}">
    <h2 class="section-title">12. Best &amp; Worst Generation Day</h2>
    <div class="side-by-side">{best_card}{worst_card}</div>
</div>"""

    return html, best_script + "\n" + worst_script


# ---------------------------------------------------------------------------
# Section 13: Top 5 Best Days + Top 5 Worst Days
# ---------------------------------------------------------------------------

def _render_top5_table(days: list, label: str) -> str:
    if not days:
        return f"<p>No {label.lower()} days.</p>"

    rows = ""
    for i, d in enumerate(days, 1):
        rows += f"""<tr>
    <td>{i}</td>
    <td>{d.date_str}</td>
    <td>{_fmt(d.actual_energy_mwh)}</td>
    <td>{_fmt(d.actual_irradiation_kwh_m2) if d.actual_irradiation_kwh_m2 is not None else "\u2014"}</td>
    <td>{_fmt(d.avg_module_temp_c) if d.avg_module_temp_c is not None else "\u2014"}</td>
    <td>{_fmt(d.performance_ratio_pct) if d.performance_ratio_pct is not None else "\u2014"}</td>
    <td>{d.weekday}</td>
</tr>"""

    return f"""<table class="data-table">
<thead><tr><th>#</th><th>Date</th><th>Energy (MWh)</th><th>Irr (kWh/m\u00b2)</th><th>Mod. Temp (\u00b0C)</th><th>PR (%)</th><th>Weekday</th></tr></thead>
<tbody>{rows}</tbody></table>"""


def _render_top5(report: MonthlyReport) -> str:
    best_table = _render_top5_table(report.best_days, "best")
    worst_table = _render_top5_table(report.worst_days, "worst")

    # Bar charts
    best_labels = [d.date_str[-2:] for d in report.best_days]
    best_vals = [round(d.actual_energy_mwh, 2) for d in report.best_days]
    worst_labels = [d.date_str[-2:] for d in report.worst_days]
    worst_vals = [round(d.actual_energy_mwh, 2) for d in report.worst_days]

    traces_best = [{"x": best_labels, "y": best_vals, "type": "bar",
                    "marker": {"color": _C["green"]}, "name": "MWh"}]
    traces_worst = [{"x": worst_labels, "y": worst_vals, "type": "bar",
                     "marker": {"color": _C["red"]}, "name": "MWh"}]

    bar_layout = {
        "height": 220,
        "margin": {"t": 20, "b": 30, "l": 50, "r": 20},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 11, "color": _C["text"]},
        "showlegend": False,
        "yaxis": {"title": "MWh", "gridcolor": "#e2e8f0"},
    }

    script = f"""
Plotly.newPlot('chart-top5-best', {_safe_json(traces_best)}, {_safe_json(bar_layout)}, {_plotly_config()});
Plotly.newPlot('chart-top5-worst', {_safe_json(traces_worst)}, {_safe_json(bar_layout)}, {_plotly_config()});
"""

    html = f"""<div class="section" id="{_section_id(13)}">
    <h2 class="section-title">13. Top 5 Best &amp; Worst Days</h2>
    <div class="side-by-side">
        <div>
            <div class="card">
                <h3 style="color:{_C['green']}; margin-bottom:12px;">Top 5 Best Days</h3>
                {best_table}
                <div id="chart-top5-best" style="min-height:220px; margin-top:12px;"></div>
            </div>
        </div>
        <div>
            <div class="card">
                <h3 style="color:{_C['red']}; margin-bottom:12px;">Top 5 Worst Days</h3>
                {worst_table}
                <div id="chart-top5-worst" style="min-height:220px; margin-top:12px;"></div>
            </div>
        </div>
    </div>
</div>"""

    return html, script


# ---------------------------------------------------------------------------
# Sections 14, 15, 18: Inverter & alarm data (Phase 6)
# ---------------------------------------------------------------------------

def _render_placeholder(section_num: int, title: str, icon: str, message: str) -> str:
    return f"""<div class="section" id="{_section_id(section_num)}">
    <h2 class="section-title">{section_num}. {title}</h2>
    <div class="placeholder-card">
        <div class="ph-icon">{icon}</div>
        <div class="ph-title">{title}</div>
        <div class="ph-msg">{message}</div>
    </div>
</div>"""


def _render_inverter_yield(report: MonthlyReport) -> tuple[str, str]:
    """Sektion 14: Inverter Yield — tabell + ranking."""
    if not report.has_inverter_data or not report.inverters:
        return _render_placeholder(
            14, "Inverter Yield", "\u2699\ufe0f",
            "Inverter-level data missing for this park. Run 'python bazefield_download.py --inverters' to sync."
        ), ""

    inverters = report.inverters
    by_rank = sorted(inverters, key=lambda m: m.rank)

    # Datakvalitets-check: inverter-sum vs park-meter
    # När Bazefield saknar inverter-level data (non-communicating inverters)
    # blir inverter-sum mycket l\u00e4gre \u00e4n meter. Det m\u00e5ste tydligt
    # kommuniceras s\u00e5 att rapporten inte ser ut som att halva parken \u00e4r nere.
    inverter_sum_mwh = sum(inv.total_energy_kwh for inv in inverters) / 1000.0
    meter_mwh = report.actual_energy_mwh
    gap_pct = 0.0
    if meter_mwh > 0:
        gap_pct = (1 - inverter_sum_mwh / meter_mwh) * 100
    data_quality_warning = ""
    if gap_pct > 10:
        inactive_count_calc = sum(1 for inv in inverters if inv.days_active == 0)
        data_quality_warning = (
            f'<div class="data-quality-alert">'
            f'<strong>\u2139\ufe0f Data Quality:</strong> Inverter-level reporting '
            f'(<strong>{inverter_sum_mwh:,.0f} MWh</strong>) is <strong>{gap_pct:.0f}% lower</strong> '
            f'than grid meter ({meter_mwh:,.0f} MWh). '
            f'This is because inverters can produce without reporting to Bazefield '
            f'("non-communicating but producing"). '
            f'{"The figures below show <strong>only what has actually been reported</strong> &mdash; " if inactive_count_calc > 0 else ""}'
            f'<strong>the inverter ranking should be considered indicative, not absolute</strong>. '
            f'The real park production ({meter_mwh:,.0f} MWh) is correct and shown in section 1.'
            f'</div>'
        ).replace(",", " ")

    # Top 5 + bottom 5 ranking
    top5 = by_rank[:5]
    bottom5 = by_rank[-5:] if len(by_rank) > 5 else []

    def _ranking_row(inv, color_class):
        return (
            f'<tr><td class="rank-num">{inv.rank}</td>'
            f'<td>{inv.name}</td>'
            f'<td class="num">{inv.total_energy_kwh:,.0f}</td>'
            f'<td class="num">{inv.avg_capacity_factor_pct:.1f}%</td>'
            f'</tr>'
        ).replace(",", " ")

    top_table = '<table class="ranking-table"><thead><tr><th>#</th><th>Inverter</th><th>kWh</th><th>CF%</th></tr></thead><tbody>'
    for inv in top5:
        top_table += _ranking_row(inv, "good")
    top_table += '</tbody></table>'

    bottom_table = '<table class="ranking-table"><thead><tr><th>#</th><th>Inverter</th><th>kWh</th><th>CF%</th></tr></thead><tbody>'
    for inv in bottom5:
        top_class = "bad" if inv.total_energy_kwh < 1 else ""
        bottom_table += _ranking_row(inv, top_class)
    bottom_table += '</tbody></table>'

    # Sammanfattnings-statistik
    total_energy = sum(inv.total_energy_kwh for inv in inverters)
    avg_cf = sum(inv.avg_capacity_factor_pct for inv in inverters if inv.days_active > 0)
    active_count = sum(1 for inv in inverters if inv.days_active > 0)
    avg_cf = (avg_cf / active_count) if active_count else 0

    inactive_count = sum(1 for inv in inverters if inv.days_active == 0)
    inactive_warning = ""
    # Visa "inactive inverters"-varning ENDAST om data-kvalitets-gap är litet,
    # dvs när noll-produktion faktiskt är verklig (inte bara saknad data).
    if inactive_count and gap_pct < 10:
        inactive_names = [inv.name for inv in inverters if inv.days_active == 0]
        inactive_warning = (
            f'<div class="warning-box">\u26a0\ufe0f <strong>{inactive_count} inverters without production:</strong> '
            f'{", ".join(inactive_names[:5])}{("..." if len(inactive_names) > 5 else "")}</div>'
        )

    # Stora tabellen — gruppera per transformer för läsbarhet
    by_transformer: dict[str, list] = {}
    for inv in sorted(inverters, key=lambda m: m.name):
        by_transformer.setdefault(inv.transformer, []).append(inv)

    transformer_html = ""
    for ts, ts_inverters in by_transformer.items():
        ts_total = sum(i.total_energy_kwh for i in ts_inverters)
        ts_avg_cf = sum(i.avg_capacity_factor_pct for i in ts_inverters if i.days_active > 0)
        ts_active = sum(1 for i in ts_inverters if i.days_active > 0)
        ts_avg_cf = (ts_avg_cf / ts_active) if ts_active else 0

        rows_html = ""
        for inv in ts_inverters:
            cf = inv.avg_capacity_factor_pct
            cf_class = "good" if cf >= 15 else ("bad" if cf < 5 else "")
            inactive = ' class="inactive-row"' if inv.days_active == 0 else ''
            rows_html += (
                f'<tr{inactive}>'
                f'<td>{inv.name}</td>'
                f'<td class="num">{inv.total_energy_kwh:,.0f}</td>'
                f'<td class="num">{inv.max_power_kw:.1f}</td>'
                f'<td class="num">{inv.rated_kw:.0f}</td>'
                f'<td class="num cf-{cf_class}">{cf:.1f}%</td>'
                f'<td class="num">{inv.days_active}</td>'
                f'<td class="rank-cell">#{inv.rank}</td>'
                f'</tr>'
            ).replace(",", " ")

        transformer_html += f'''
        <div class="transformer-group">
            <div class="ts-header">
                <strong>{ts}</strong> ({len(ts_inverters)} inverters)
                — Total: {ts_total:,.0f} kWh, Avg CF: {ts_avg_cf:.1f}%
            </div>
            <table class="inverter-table">
                <thead><tr>
                    <th>Inverter</th><th>kWh</th><th>Max kW</th>
                    <th>Rated</th><th>CF%</th><th>Days</th><th>Rank</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
        '''.replace(",", " ")

    html = f'''<div class="section" id="{_section_id(14)}">
    <h2 class="section-title">14. Inverter Yield</h2>
    <div class="kpi-row" style="grid-template-columns: repeat(3, 1fr);">
        <div class="kpi-card"><div class="kpi-value">{len(inverters)}</div><div class="kpi-label">Total Inverters</div></div>
        <div class="kpi-card"><div class="kpi-value">{total_energy:,.0f}</div><div class="kpi-label">Total Energy (kWh)</div></div>
        <div class="kpi-card"><div class="kpi-value">{avg_cf:.1f}%</div><div class="kpi-label">Avg Capacity Factor</div></div>
    </div>
    {data_quality_warning}
    {inactive_warning}
    <div class="side-by-side">
        <div class="card">
            <h3 style="color:{_C['green']}; margin-bottom:12px;">\U0001f3c6 Top 5 Best</h3>
            {top_table}
        </div>
        <div class="card">
            <h3 style="color:{_C['red']}; margin-bottom:12px;">\u26a0\ufe0f Bottom 5</h3>
            {bottom_table}
        </div>
    </div>
    <div class="card" style="margin-top:16px;">
        <h3 style="margin-bottom:12px;">Per Transformer Group</h3>
        {transformer_html}
    </div>
</div>'''.replace(",", " ")

    return html, ""


def _render_inverter_efficiency(report: MonthlyReport) -> tuple[str, str]:
    """Sektion 15: Inverter Efficiency — multi-line + heatmap."""
    if not report.has_inverter_data or not report.inverter_daily_lookup:
        return _render_placeholder(
            15, "Inverter Efficiency", "\u26a1",
            "Inverter-level data missing. Run 'python bazefield_download.py --inverters' to sync."
        ), ""

    inverters = sorted(report.inverters, key=lambda m: m.name)
    daily_lookup = report.inverter_daily_lookup

    # Datakvalitets-varning (samma logik som sektion 14)
    inverter_sum_mwh = sum(inv.total_energy_kwh for inv in report.inverters) / 1000.0
    gap_pct = 0.0
    if report.actual_energy_mwh > 0:
        gap_pct = (1 - inverter_sum_mwh / report.actual_energy_mwh) * 100
    efficiency_data_alert = ""
    if gap_pct > 10:
        efficiency_data_alert = (
            '<div class="data-quality-alert">'
            '<strong>\u2139\ufe0f Note:</strong> Red areas in the heatmap below '
            'do not mean the inverters are offline \u2014 they are data gaps due to '
            'non-communicating inverters. See the data quality notice in section 14.'
            '</div>'
        )

    # Bestäm antal dagar i månaden
    import calendar as _cal
    days_in_month = _cal.monthrange(report.year, report.month)[1]
    days = list(range(1, days_in_month + 1))

    # Bygg multi-line chart-data — en linje per inverter
    traces = []
    for inv in inverters:
        cf_per_day = []
        for d in days:
            day_data = daily_lookup.get(inv.name, {}).get(d)
            cf_per_day.append(day_data.capacity_factor_pct if day_data else None)
        traces.append({
            "x": days,
            "y": cf_per_day,
            "name": inv.name,
            "type": "scatter",
            "mode": "lines",
            "line": {"width": 1.5},
            "showlegend": False,  # För många för legend
            "hovertemplate": f"{inv.name}<br>Day %{{x}}: %{{y:.1f}}%<extra></extra>",
        })

    layout = {
        "paper_bgcolor": _C["card"],
        "plot_bgcolor": _C["card"],
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 11, "color": _C["text"]},
        "title": {"text": "Daily Capacity Factor per Inverter", "font": {"size": 14}},
        "xaxis": {"title": "Day", "dtick": 1, "gridcolor": "#e2e8f0"},
        "yaxis": {"title": "Capacity Factor (%)", "gridcolor": "#e2e8f0", "rangemode": "tozero"},
        "height": 420,
        "margin": {"l": 60, "r": 20, "t": 50, "b": 50},
    }

    chart_id = "chart-inverter-efficiency"
    chart_html = f'<div id="{chart_id}" class="chart-container"></div>'
    script = f"Plotly.newPlot('{chart_id}', {json.dumps(traces)}, {json.dumps(layout)}, {{responsive: true}});"

    # Heatmap-data: rows = invertrar, cols = dagar, values = CF%
    z_data = []
    y_labels = []
    for inv in inverters:
        row = []
        for d in days:
            day_data = daily_lookup.get(inv.name, {}).get(d)
            row.append(day_data.capacity_factor_pct if day_data else 0)
        z_data.append(row)
        y_labels.append(inv.name)

    heatmap_trace = {
        "z": z_data,
        "x": days,
        "y": y_labels,
        "type": "heatmap",
        "colorscale": [
            [0, "#ef4444"],     # Röd (0%)
            [0.3, "#f59e0b"],   # Amber (~5%)
            [0.6, "#fbbf24"],   # Gul (~10%)
            [1.0, "#10b981"],   # Grön (~20%+)
        ],
        "zmin": 0,
        "zmax": 25,
        "colorbar": {"title": "CF%"},
        "hovertemplate": "%{y}<br>Day %{x}: %{z:.1f}%<extra></extra>",
    }

    heatmap_layout = {
        "paper_bgcolor": _C["card"],
        "plot_bgcolor": _C["card"],
        "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 10, "color": _C["text"]},
        "title": {"text": "CF Heatmap (day \u00d7 inverter)", "font": {"size": 14}},
        "xaxis": {"title": "Day", "dtick": 1},
        "yaxis": {"title": "", "automargin": True},
        "height": max(300, 18 * len(inverters)),
        "margin": {"l": 130, "r": 20, "t": 50, "b": 50},
    }

    heatmap_id = "chart-inverter-efficiency-heatmap"
    heatmap_html = f'<div id="{heatmap_id}" class="chart-container"></div>'
    heatmap_script = f"Plotly.newPlot('{heatmap_id}', [{json.dumps(heatmap_trace)}], {json.dumps(heatmap_layout)}, {{responsive: true}});"

    html = f'''<div class="section" id="{_section_id(15)}">
    <h2 class="section-title">15. Inverter Efficiency</h2>
    {efficiency_data_alert}
    <div class="card">
        {chart_html}
    </div>
    <div class="card" style="margin-top:16px;">
        {heatmap_html}
    </div>
</div>'''

    full_script = script + "\n" + heatmap_script
    return html, full_script


def _render_alarm_summary(report: MonthlyReport) -> tuple[str, str]:
    """Sektion 18: Alarm & Fault Summary."""
    if not report.has_alarm_data or report.alarm_stats is None:
        return _render_placeholder(
            18, "Alarms &amp; Faults", "\U0001f514",
            "No alarm events for this month. Either run 'python bazefield_download.py --inverters' to sync, or the park was stable."
        ), ""

    stats = report.alarm_stats

    # KPI-rad
    kpi_html = f'''
    <div class="kpi-row" style="grid-template-columns: repeat(4, 1fr);">
        <div class="kpi-card"><div class="kpi-value">{stats.total_alarms}</div><div class="kpi-label">Total Alarms</div></div>
        <div class="kpi-card"><div class="kpi-value">{stats.unique_types}</div><div class="kpi-label">Unique Types</div></div>
        <div class="kpi-card"><div class="kpi-value">{stats.avg_mtba_hours:.1f}</div><div class="kpi-label">MTBA (hours)</div></div>
        <div class="kpi-card"><div class="kpi-value">{stats.active_at_period_end}</div><div class="kpi-label">Active (period end)</div></div>
    </div>
    '''

    # Daily timeline chart
    if stats.daily_count:
        sorted_dates = sorted(stats.daily_count.keys())
        days_x = [int(d.split("-")[2]) for d in sorted_dates]
        counts_y = [stats.daily_count[d] for d in sorted_dates]

        timeline_trace = {
            "x": days_x,
            "y": counts_y,
            "type": "bar",
            "marker": {"color": _C["red"]},
            "name": "Alarm Count",
        }
        timeline_layout = {
            "paper_bgcolor": _C["card"],
            "plot_bgcolor": _C["card"],
            "font": {"family": "'Segoe UI', system-ui, sans-serif", "size": 11, "color": _C["text"]},
            "title": {"text": "Daily Alarm Frequency", "font": {"size": 14}},
            "xaxis": {"title": "Day", "dtick": 1, "gridcolor": "#e2e8f0"},
            "yaxis": {"title": "Alarm Count", "gridcolor": "#e2e8f0"},
            "height": 280,
            "margin": {"l": 60, "r": 20, "t": 50, "b": 50},
        }

        timeline_id = "chart-alarm-timeline"
        timeline_html = f'<div id="{timeline_id}" class="chart-container"></div>'
        timeline_script = f"Plotly.newPlot('{timeline_id}', [{json.dumps(timeline_trace)}], {json.dumps(timeline_layout)}, {{responsive: true}});"
    else:
        timeline_html = ""
        timeline_script = ""

    # Top alarm types-tabell
    top_html = '<table class="alarm-table"><thead><tr><th>#</th><th>Alarm Type</th><th>Count</th><th>Total Duration (min)</th></tr></thead><tbody>'
    for idx, (name, count, dur) in enumerate(stats.top_alarms, 1):
        top_html += (
            f'<tr><td>{idx}</td>'
            f'<td>{name}</td>'
            f'<td class="num">{count}</td>'
            f'<td class="num">{dur:,.0f}</td>'
            f'</tr>'
        ).replace(",", " ")
    top_html += '</tbody></table>'

    # Per-inverter breakdown (top 10)
    sorted_invs = sorted(stats.by_inverter.items(), key=lambda x: x[1], reverse=True)[:10]
    inv_html = '<table class="alarm-table"><thead><tr><th>Inverter</th><th>Alarm Count</th></tr></thead><tbody>'
    for inv_name, count in sorted_invs:
        inv_html += f'<tr><td>{inv_name}</td><td class="num">{count}</td></tr>'
    inv_html += '</tbody></table>'

    # Senaste alarm-detaljer (top 15 för att inte överbelasta)
    detail_html = '<table class="alarm-detail-table"><thead><tr><th>Time</th><th>Inverter</th><th>Type</th><th>Description</th><th>Duration (min)</th></tr></thead><tbody>'
    for evt in report.recent_alarms[:15]:
        time_short = evt.time_start_utc[:16].replace("T", " ")
        dur_str = f'{evt.duration_min:.0f}' if evt.duration_min > 0 else '\u2014'
        detail_html += (
            f'<tr><td>{time_short}</td>'
            f'<td>{evt.inverter_name}</td>'
            f'<td>{evt.event_name}</td>'
            f'<td>{evt.description}</td>'
            f'<td class="num">{dur_str}</td>'
            f'</tr>'
        )
    detail_html += '</tbody></table>'

    html = f'''<div class="section" id="{_section_id(18)}">
    <h2 class="section-title">18. Alarms &amp; Faults</h2>
    {kpi_html}
    <div class="card">
        {timeline_html}
    </div>
    <div class="side-by-side" style="margin-top:16px;">
        <div class="card">
            <h3 style="margin-bottom:12px;">Top Alarm Types</h3>
            {top_html}
        </div>
        <div class="card">
            <h3 style="margin-bottom:12px;">Per Inverter (top 10)</h3>
            {inv_html}
        </div>
    </div>
    <div class="card" style="margin-top:16px;">
        <h3 style="margin-bottom:12px;">Recent Alarms (max 15)</h3>
        {detail_html}
    </div>
</div>'''

    return html, timeline_script


def _render_incidents_placeholder() -> str:
    """Sektion 17: Incident-platshållare (sektion 14, 15, 18 har egna funktioner nu)."""
    return _render_placeholder(
        17, "Incidents &amp; Work Orders", "\U0001f6e0\ufe0f",
        "Incident and work log integration with maintenance system (e.g. QBO, ServiceNow). Contact the O&M team to activate."
    )


# ---------------------------------------------------------------------------
# Section 16: PPM Schedule
# ---------------------------------------------------------------------------

def _render_ppm_schedule(report: MonthlyReport) -> str:
    """Rendera PPM Schedule-matrisen (sektion 16).

    Visar en kalendermatris med tasks som rader och månader som kolumner.
    Schemalagda månader visas med "📅" och nuvarande månad highlightas.
    """
    from .ppm_schedule import get_ppm_schedule

    tasks = get_ppm_schedule(report.park_key)
    current_month = report.month

    # Header: Task | Frekvens | Jan | Feb | ... | Dec
    header_cells = ['<th class="ppm-task-col">Maintenance Task</th>',
                    '<th class="ppm-freq-col">Frequency</th>']
    for m in range(1, 13):
        month_label = _MONTH_SV[m]
        current_class = ' ppm-current-month' if m == current_month else ''
        header_cells.append(f'<th class="ppm-month-col{current_class}">{month_label}</th>')

    header_row = '<tr>' + ''.join(header_cells) + '</tr>'

    # Rows: one per task
    body_rows = []
    freq_label = {"biannual": "Bi-annual", "annual": "Annual", "monthly": "Monthly"}
    for task in tasks:
        cells = [f'<td class="ppm-task-cell">{task["task"]}</td>']
        cells.append(f'<td class="ppm-freq-cell">{freq_label.get(task["frequency"], task["frequency"])}</td>')
        for m in range(1, 13):
            scheduled = m in task.get("months", [])
            current = m == current_month
            classes = "ppm-cell"
            if scheduled:
                classes += " ppm-scheduled"
            if current:
                classes += " ppm-current-month"
            content = "\U0001f4c5" if scheduled else ""
            cells.append(f'<td class="{classes}">{content}</td>')
        body_rows.append('<tr>' + ''.join(cells) + '</tr>')

    table = f'''<table class="ppm-table">
    <thead>{header_row}</thead>
    <tbody>{"".join(body_rows)}</tbody>
</table>'''

    note = (
        '<div class="insight-box">'
        f'The schedule shows standardised preventive maintenance for solar parks. '
        f'Marked months (<span style="color:#2563eb">\U0001f4c5</span>) '
        f'indicate scheduled activity. Current month ({_MONTH_SV[current_month]}) is highlighted.'
        '</div>'
    )

    return f'''<div class="section" id="{_section_id(16)}">
    <h2 class="section-title">16. PPM Schedule</h2>
    <div class="card">
        {table}
        {note}
    </div>
</div>'''


# ---------------------------------------------------------------------------
# Section 19: Executive Summary
# ---------------------------------------------------------------------------

def _render_executive_summary(report: MonthlyReport) -> str:
    r = report
    month_full = _MONTH_FULL_SV[r.month]

    # Energy vs budget
    energy_delta_pct = ((r.actual_energy_mwh / r.budget_energy_mwh - 1) * 100) if r.budget_energy_mwh > 0 else 0
    energy_word = "below" if energy_delta_pct < 0 else "above"

    # Irradiation
    irr_text = ""
    if r.actual_irradiation_kwh_m2 is not None and r.budget_irradiation_kwh_m2 > 0:
        irr_delta = ((r.actual_irradiation_kwh_m2 / r.budget_irradiation_kwh_m2 - 1) * 100)
        irr_word = "lower" if irr_delta < 0 else "higher"
        irr_text = (
            f"Irradiation during {month_full} reached "
            f"{_fmt(r.actual_irradiation_kwh_m2)} kWh/m\u00b2, "
            f"which is {abs(irr_delta):.1f}% {irr_word} than the budgeted "
            f"irradiation ({_fmt(r.budget_irradiation_kwh_m2)} kWh/m\u00b2). "
        )

    # PR
    pr_text = ""
    if r.performance_ratio_pct is not None:
        pr_delta = r.performance_ratio_pct - r.budget_pr_pct
        pr_word = "below" if pr_delta < 0 else "above"
        pr_text = (
            f"Performance Ratio reached {_fmt(r.performance_ratio_pct)}%, "
            f"compared to the budgeted {_fmt(r.budget_pr_pct)}% "
            f"({abs(pr_delta):.1f} percentage points {pr_word})."
        )

    # Losses
    lc = r.losses
    loss_items = []
    if lc.curtailment_loss_mwh > 0.1:
        loss_items.append(f"Curtailment: {_fmt(lc.curtailment_loss_mwh)} MWh")
    if lc.irradiance_shortfall_loss_mwh > 0.1:
        loss_items.append(f"Irradiance Shortfall: {_fmt(lc.irradiance_shortfall_loss_mwh)} MWh")
    if lc.availability_loss_mwh > 0.1:
        loss_items.append(f"Availability: {_fmt(lc.availability_loss_mwh)} MWh")
    if abs(lc.temperature_loss_mwh) > 0.1:
        loss_items.append(f"Temperature: {_fmt(lc.temperature_loss_mwh)} MWh")

    losses_html = ""
    if loss_items:
        losses_html = "<li>Main losses: " + ", ".join(loss_items) + "</li>"

    # YTD summary
    ytd_text = ""
    if r.ytd:
        ytd_actual = sum(m.actual_energy_mwh for m in r.ytd)
        ytd_budget = sum(m.budget_energy_mwh for m in r.ytd)
        ytd_delta_pct = ((ytd_actual / ytd_budget - 1) * 100) if ytd_budget > 0 else 0
        ytd_word = "below the annual budget" if ytd_delta_pct < 0 else "above the annual budget"
        ytd_text = (
            f"Year-to-date the park has produced "
            f"{_fmt(ytd_actual)} MWh, {abs(ytd_delta_pct):.1f}% {ytd_word} "
            f"({_fmt(ytd_budget)} MWh through {month_full})."
        )

    overview = (
        f"{r.park_display_name} produced during {month_full} {r.year} a total of "
        f"<strong>{_fmt(r.actual_energy_mwh)} MWh</strong>, "
        f"which is <strong>{abs(energy_delta_pct):.1f}% {energy_word}</strong> "
        f"the budgeted generation of {_fmt(r.budget_energy_mwh)} MWh. "
        f"{irr_text}{pr_text}"
    )

    html = f"""<div class="section" id="{_section_id(19)}">
    <h2 class="section-title">19. Executive Summary</h2>
    <div class="card">
        <h3 style="color:{_C['primary']}; margin-bottom:12px;">Overview</h3>
        <p style="margin-bottom:16px;">{overview}</p>

        <h3 style="color:{_C['primary']}; margin-bottom:12px;">Key Observations</h3>
        <ul style="margin-bottom:16px; padding-left:20px; line-height:2;">
            <li>Total generation: {_fmt(r.actual_energy_mwh)} MWh ({_fmt_delta(energy_delta_pct)} vs budget)</li>
            <li>Specific Yield: {_fmt(r.yield_kwh_kwp)} kWh/kWp</li>
            {"<li>PR: " + _fmt(r.performance_ratio_pct) + "% (budget: " + _fmt(r.budget_pr_pct) + "%)</li>" if r.performance_ratio_pct is not None else ""}
            {losses_html}
        </ul>

        <h3 style="color:{_C['primary']}; margin-bottom:12px;">Summary Assessment</h3>
        <p>{ytd_text}</p>
    </div>
</div>"""

    return html


# ---------------------------------------------------------------------------
# Huvudfunktion
# ---------------------------------------------------------------------------

def render_html(report: MonthlyReport) -> str:
    """Rendera komplett HTML-rapport fr\u00e5n MonthlyReport.

    Args:
        report: Komplett m\u00e5nadsrapportdata fr\u00e5n generate_report().

    Returns:
        Fullst\u00e4ndig HTML-str\u00e4ng redo att skrivas till fil.
    """
    all_scripts: list[str] = []

    # Sections that return (html, script)
    sec1_html, sec1_script = _render_monthly_summary(report)
    all_scripts.append(sec1_script)

    sec2_html, sec2_script = _render_ytd(report)
    all_scripts.append(sec2_script)

    sec3_html, sec3_script = _render_daily_generation(report)
    all_scripts.append(sec3_script)

    sec4_html, sec4_script = _render_pr_temp(report)
    all_scripts.append(sec4_script)

    sec5_html, sec5_script = _render_expected_vs_actual(report)
    all_scripts.append(sec5_script)

    sec6_html, sec6_script = _render_performance_index(report)
    all_scripts.append(sec6_script)

    sec7_html, sec7_script = _render_efficiency(report)
    all_scripts.append(sec7_script)

    sec8_html, sec8_script = _render_power_irr_trend(report)
    all_scripts.append(sec8_script)

    sec9_html, sec9_script = _render_loss_cascade_mwh(report)
    all_scripts.append(sec9_script)

    sec10_html, sec10_script = _render_loss_cascade_pct(report)
    all_scripts.append(sec10_script)

    sec11_html, sec11_script = _render_curtailment_irr_trend(report)
    all_scripts.append(sec11_script)

    sec12_html, sec12_script = _render_best_worst_day(report)
    all_scripts.append(sec12_script)

    sec13_html, sec13_script = _render_top5(report)
    all_scripts.append(sec13_script)

    sec14_html, sec14_script = _render_inverter_yield(report)
    all_scripts.append(sec14_script)

    sec15_html, sec15_script = _render_inverter_efficiency(report)
    all_scripts.append(sec15_script)

    ppm_schedule_html = _render_ppm_schedule(report)
    incidents_html = _render_incidents_placeholder()

    sec18_html, sec18_script = _render_alarm_summary(report)
    all_scripts.append(sec18_script)

    exec_summary_html = _render_executive_summary(report)

    # Combine scripts
    combined_scripts = "\n".join(s for s in all_scripts if s)

    month_full = _MONTH_FULL_SV[report.month]
    title = f"{report.park_display_name} \u2013 Performance Report \u2013 {month_full} {report.year}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="{PLOTLY_CDN}"></script>
    {_render_css()}
</head>
<body>
    {_render_header(report)}
    {_render_toc()}
    <div class="content">
        {sec1_html}
        {sec2_html}
        {sec3_html}
        {sec4_html}
        {sec5_html}
        {sec6_html}
        {sec7_html}
        {sec8_html}
        {sec9_html}
        {sec10_html}
        {sec11_html}
        {sec12_html}
        {sec13_html}
        {sec14_html}
        {sec15_html}
        {ppm_schedule_html}
        {incidents_html}
        {sec18_html}
        {exec_summary_html}
    </div>
    <footer style="text-align:center; padding:20px; color:{_C['muted']}; font-size:12px;">
        Generated by Svea Solar Performance Reporting &middot; {report.park_display_name} &middot; {month_full} {report.year}
    </footer>
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            {combined_scripts}
        }});
    </script>
</body>
</html>"""

    return html
