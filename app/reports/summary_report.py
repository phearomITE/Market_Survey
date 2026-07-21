
# app/reports/summary_report.py


from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.core.config import settings
from app.data.dealers import REGION_DEALERS
from app.reports.aggregator import is_final_summary_outlet_name


HEADER_FILL = "1F4E78"
REGION_FILL = "D9EAF7"
ZERO_FILL = "FCE4D6"
PARTIAL_FILL = "FFF2CC"
OK_FILL = "E2F0D9"
BORDER_COLOR = "D9E2F3"


def _clean(value) -> str:
    return str(value or "").strip()


def _status(total_submissions: int, total_outlets: int, target: int | None) -> str:
    if total_submissions <= 0:
        return "❌ No Submit"
    if target and total_outlets < target:
        return "⚠ Partial"
    return "✅"


def _safe_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except Exception:
        return None


def build_summary_rows(submissions: Iterable) -> list[dict]:
    """Return one row for every configured dealer, including zero-submit dealers.

    Total Submissions = number of real outlet rows (summary-marker rows excluded).
    Total Outlets = distinct outlet_name count when available, otherwise row count.
    Status = No Submit / Partial / OK.
    """
    grouped: dict[str, list] = defaultdict(list)
    for s in submissions:
        dealer = _clean(getattr(s, "dealer", "")).upper()
        if dealer:
            grouped[dealer].append(s)

    rows: list[dict] = []
    for region, dealers in REGION_DEALERS.items():
        for dealer in dealers:
            dealer_rows = grouped.get(dealer, [])
            outlet_rows = [
                s for s in dealer_rows
                if not is_final_summary_outlet_name(getattr(s, "outlet_name", None))
            ]
            total_submissions = len(outlet_rows)

            outlet_names = {
                _clean(getattr(s, "outlet_name", "")).lower()
                for s in outlet_rows
                if _clean(getattr(s, "outlet_name", ""))
            }
            total_outlets = len(outlet_names) if outlet_names else total_submissions

            targets = [_safe_int(getattr(s, "total_outlet_visit_target", None)) for s in outlet_rows]
            targets = [x for x in targets if x is not None]
            target = max(targets) if targets else None

            rows.append(
                {
                    "region": region,
                    "dealer": dealer,
                    "total_submissions": total_submissions,
                    "total_outlets": total_outlets,
                    "target": target,
                    "status": _status(total_submissions, total_outlets, target),
                }
            )
    return rows


def _style_summary_sheet(ws) -> None:
    thin = Side(style="thin", color=BORDER_COLOR)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for row in ws.iter_rows():
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="center", horizontal="center")
            cell.font = Font(name="Calibri", size=11)

    # Title rows
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=HEADER_FILL)
    ws["A2"].font = Font(name="Calibri", size=11, italic=True, color="666666")

    # KPI block
    for row in range(4, 7):
        for col in range(1, 9):
            c = ws.cell(row, col)
            c.fill = PatternFill("solid", fgColor="F8FBFD")
            c.font = Font(name="Calibri", size=11, bold=(row == 4))

    # Header
    header_row = 8
    for col in range(1, 6):
        c = ws.cell(header_row, col)
        c.fill = PatternFill("solid", fgColor=HEADER_FILL)
        c.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        c.alignment = Alignment(horizontal="center", vertical="center")

    # Data rows
    for row in range(9, ws.max_row + 1):
        status = str(ws.cell(row, 5).value or "")
        fill = None
        if "No Submit" in status:
            fill = PatternFill("solid", fgColor=ZERO_FILL)
        elif "Partial" in status:
            fill = PatternFill("solid", fgColor=PARTIAL_FILL)
        elif "✅" in status:
            fill = PatternFill("solid", fgColor=OK_FILL)
        if fill:
            for col in range(1, 6):
                ws.cell(row, col).fill = fill

        ws.cell(row, 1).font = Font(bold=True)
        ws.cell(row, 2).font = Font(bold=True)

    ws.freeze_panes = "A9"
    widths = {"A": 12, "B": 14, "C": 20, "D": 16, "E": 18, "G": 22, "H": 14}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    for row in range(1, ws.max_row + 1):
        ws.row_dimensions[row].height = 22


def create_summary_report(rows: list[dict], report_date: date, output_path: Path | None = None) -> Path:
    settings.export_path.mkdir(parents=True, exist_ok=True)
    output_path = output_path or settings.export_path / f"Market_Survey_Summary_{report_date}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"

    total_dealers = len(rows)
    submitted_dealers = sum(1 for r in rows if r["total_submissions"] > 0)
    no_submit = total_dealers - submitted_dealers
    total_submissions = sum(r["total_submissions"] for r in rows)
    total_outlets = sum(r["total_outlets"] for r in rows)
    completion = submitted_dealers / total_dealers if total_dealers else 0

    ws.merge_cells("A1:H1")
    ws["A1"] = "KB Market Survey - Region & Dealer Submission Summary"
    ws.merge_cells("A2:H2")
    ws["A2"] = f"Report Date: {report_date} | Generated: {datetime.now():%d/%m/%Y %H:%M:%S}"

    kpis = [
        ("Total Regions", len(set(r["region"] for r in rows))),
        ("Total Dealers", total_dealers),
        ("Submitted Dealers", submitted_dealers),
        ("No Submit Dealers", no_submit),
        ("Total Submissions", total_submissions),
        ("Total Outlets", total_outlets),
        ("Completion", f"{completion:.1%}"),
    ]
    for idx, (label, value) in enumerate(kpis, start=1):
        ws.cell(4, idx).value = label
        ws.cell(5, idx).value = value

    header = ["Region", "Dealer", "Total Submissions", "Total Outlets", "Status"]
    for col, value in enumerate(header, start=1):
        ws.cell(8, col).value = value

    current_row = 9
    for region, dealers in REGION_DEALERS.items():
        region_rows = [r for r in rows if r["region"] == region]
        for r in region_rows:
            ws.cell(current_row, 1).value = r["region"]
            ws.cell(current_row, 2).value = r["dealer"]
            ws.cell(current_row, 3).value = r["total_submissions"]
            ws.cell(current_row, 4).value = r["total_outlets"]
            ws.cell(current_row, 5).value = r["status"]
            current_row += 1

        # Region subtotal row
        ws.cell(current_row, 1).value = region
        ws.cell(current_row, 2).value = "Region Total"
        ws.cell(current_row, 3).value = sum(r["total_submissions"] for r in region_rows)
        ws.cell(current_row, 4).value = sum(r["total_outlets"] for r in region_rows)
        submitted = sum(1 for r in region_rows if r["total_submissions"] > 0)
        ws.cell(current_row, 5).value = f"{submitted}/{len(region_rows)} dealers submitted"
        for col in range(1, 6):
            ws.cell(current_row, col).fill = PatternFill("solid", fgColor=REGION_FILL)
            ws.cell(current_row, col).font = Font(bold=True)
        current_row += 1

    _style_summary_sheet(ws)
    wb.save(output_path)
    return output_path
