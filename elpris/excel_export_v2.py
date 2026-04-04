"""Excel export for Dashboard v2 data.

Generates a companion .xlsx file with yearly and monthly capture prices
per zone, matching the dashboard v2 data format.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "Maj", "Jun",
    "Jul", "Aug", "Sep", "Okt", "Nov", "Dec",
]

HEADER_FONT = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")
SUBHEADER_FONT = Font(name="Calibri", bold=True, size=10, color="E0E0E0")
SUBHEADER_FILL = PatternFill(start_color="16213e", end_color="16213e", fill_type="solid")
BODY_FONT = Font(name="Calibri", size=10)
ZONE_FONT = Font(name="Calibri", bold=True, size=11, color="4A9EFF")
NUM_FMT_PRICE = '#,##0.00'
NUM_FMT_RATIO = '0.000'


def generate_dashboard_excel(data: dict, output_path: Path) -> None:
    """Generate Excel report from dashboard v2 data."""
    wb = Workbook()
    wb.remove(wb.active)

    profiles = data.get("profiles", {})
    profile_keys = [k for k in profiles if k != "baseload"]

    for zone in data.get("zones", []):
        zone_data = data["data"].get(zone, {})
        if not zone_data:
            continue

        ws = wb.create_sheet(title=zone)
        ws.sheet_properties.tabColor = _zone_tab_color(zone)

        row = 1

        # --- Yearly section ---
        ws.cell(row=row, column=1, value=f"{zone} — Årlig sammanställning (EUR/MWh)")
        ws.cell(row=row, column=1).font = ZONE_FONT
        row += 1

        # Header row
        headers = ["År", "Baseload"]
        available_keys = []
        for k in profile_keys:
            if k in zone_data:
                available_keys.append(k)
                headers.append(profiles[k])
                headers.append(f"Ratio")
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=h)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center")
        row += 1

        # Data rows
        baseload_yearly = zone_data.get("baseload", {}).get("yearly", [])
        for yr in baseload_yearly:
            col = 1
            ws.cell(row=row, column=col, value=yr["year"]).font = BODY_FONT
            col += 1
            _write_price(ws, row, col, yr["baseload"])
            col += 1

            for k in available_keys:
                yr_data = zone_data[k].get("yearly", [])
                match = next((d for d in yr_data if d["year"] == yr["year"]), None)
                _write_price(ws, row, col, match["capture"] if match else None)
                col += 1
                _write_ratio(ws, row, col, match["ratio"] if match else None)
                col += 1
            row += 1

        row += 2

        # --- Monthly section ---
        ws.cell(row=row, column=1, value=f"{zone} — Månadsvis (EUR/MWh)")
        ws.cell(row=row, column=1).font = ZONE_FONT
        row += 1

        years = sorted(set(d["year"] for d in baseload_yearly))
        for year in years:
            ws.cell(row=row, column=1, value=str(year))
            ws.cell(row=row, column=1).font = Font(bold=True, size=10)
            row += 1

            m_headers = ["Månad", "Baseload"]
            for k in available_keys:
                m_headers.append(profiles[k])
                m_headers.append("Ratio")
            for col, h in enumerate(m_headers, 1):
                cell = ws.cell(row=row, column=col, value=h)
                cell.font = SUBHEADER_FONT
                cell.fill = SUBHEADER_FILL
                cell.alignment = Alignment(horizontal="center")
            row += 1

            for month in range(1, 13):
                col = 1
                ws.cell(row=row, column=col, value=MONTH_NAMES[month - 1]).font = BODY_FONT
                col += 1

                bl_monthly = zone_data.get("baseload", {}).get("monthly", [])
                bl = next((d for d in bl_monthly if d["year"] == year and d["month"] == month), None)
                _write_price(ws, row, col, bl["baseload"] if bl else None)
                col += 1

                for k in available_keys:
                    m_data = zone_data[k].get("monthly", [])
                    match = next((d for d in m_data if d["year"] == year and d["month"] == month), None)
                    _write_price(ws, row, col, match["capture"] if match else None)
                    col += 1
                    _write_ratio(ws, row, col, match["ratio"] if match else None)
                    col += 1
                row += 1

            row += 1

        # Auto-width columns
        for col in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col)].width = 14

        ws.freeze_panes = "A3"

    wb.save(output_path)


def _write_price(ws, row: int, col: int, value: float | None) -> None:
    cell = ws.cell(row=row, column=col)
    if value is not None:
        cell.value = value
        cell.number_format = NUM_FMT_PRICE
    else:
        cell.value = "–"
    cell.font = BODY_FONT
    cell.alignment = Alignment(horizontal="right")


def _write_ratio(ws, row: int, col: int, value: float | None) -> None:
    cell = ws.cell(row=row, column=col)
    if value is not None:
        cell.value = value
        cell.number_format = NUM_FMT_RATIO
        if value >= 0.9:
            cell.font = Font(name="Calibri", size=10, color="059669")
        elif value >= 0.7:
            cell.font = Font(name="Calibri", size=10, color="D97706")
        else:
            cell.font = Font(name="Calibri", size=10, color="DC2626")
    else:
        cell.value = "–"
        cell.font = BODY_FONT
    cell.alignment = Alignment(horizontal="right")


def _zone_tab_color(zone: str) -> str:
    return {
        "SE1": "3B82F6",
        "SE2": "10B981",
        "SE3": "F59E0B",
        "SE4": "EF4444",
    }.get(zone, "888888")
