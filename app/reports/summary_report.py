
# app/reports/summary_report.py


from __future__ import annotations

from collections import defaultdict
from copy import copy
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.core.config import settings
from app.data.dealers import REGION_DEALERS
from app.reports.aggregator import aggregate_submissions, is_final_summary_outlet_name


HEADER_FILL = "1F4E78"
REGION_FILL = "D9EAF7"
ZERO_FILL = "FCE4D6"
PARTIAL_FILL = "FFF2CC"
OK_FILL = "E2F0D9"
BORDER_COLOR = "D9E2F3"
TARGET_PRODUCT = "CB LITE NCP"
COMPARE_PRODUCTS = (
    "GB SNOW NCP",
    "Hanuman LITE NCP",
    "Krud LITE NCP",
    "Greet LITE NCP",
)
KPI_COMPETITORS = ("GB SNOW NCP", "Hanuman LITE NCP", "Greet LITE NCP")


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


def _score(value) -> int | None:
    value = _safe_int(value)
    return max(0, min(10, value)) if value is not None else None


def _find_metric(submission, product_name: str):
    wanted = " ".join(product_name.upper().split())
    aliases = {wanted}
    if wanted == TARGET_PRODUCT:
        aliases.update({"CB LITE", "CBC LITE", "CBC LITE NCP"})
    metrics = list(getattr(submission, "product_metrics", []) or [])
    metrics += list(getattr(submission, "competitor_metrics", []) or [])
    for metric in metrics:
        name = " ".join(_clean(getattr(metric, "product_name", "")).upper().split())
        if name in aliases:
            return metric
    return None


def _google_maps_link(submission) -> str:
    lat = getattr(submission, "gps_latitude", None)
    lon = getattr(submission, "gps_longitude", None)
    if lat is None or lon is None:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"


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
            aggregate = aggregate_submissions(outlet_rows) if outlet_rows else {}
            products = aggregate.get("products") or {}
            competitors = aggregate.get("competitors") or {}
            target_score = _score((products.get(TARGET_PRODUCT) or {}).get("mov"))

            ranked_competitors = []
            for product in COMPARE_PRODUCTS:
                competitor_score = _score((competitors.get(product) or {}).get("mov"))
                if competitor_score is not None:
                    ranked_competitors.append((competitor_score, product))
            ranked_competitors.sort(key=lambda item: (-item[0], COMPARE_PRODUCTS.index(item[1])))
            lead_score, lead_product = (ranked_competitors[0] if ranked_competitors else (None, ""))
            if lead_score is None or target_score is None or lead_score <= target_score:
                lead_product, lead_score = "", None

            detail_rows = []
            if lead_product:
                for submission in outlet_rows:
                    metric = _find_metric(submission, TARGET_PRODUCT)
                    movement = _score(getattr(metric, "movement_score", None)) if metric else None
                    if metric is None and movement is None:
                        continue
                    detail_rows.append(
                        {
                            "date": getattr(submission, "report_date", None),
                            "region": region,
                            "dealer": dealer,
                            "outlet_name": _clean(getattr(submission, "outlet_name", "")),
                            "phone": _clean(getattr(submission, "phone_number", "")),
                            "outlet_type": _clean(getattr(submission, "outlet_type", "")),
                            "stock": _clean(getattr(metric, "stock_status", "")),
                            "freshness": _clean(getattr(metric, "bbe_date", "")),
                            "movement": movement,
                            "lead_product": lead_product,
                            "lead_score": lead_score,
                            "map_link": _google_maps_link(submission),
                        }
                    )

            rows.append(
                {
                    "region": region,
                    "dealer": dealer,
                    "total_submissions": total_submissions,
                    "total_outlets": total_outlets,
                    "target": target,
                    "status": _status(total_submissions, total_outlets, target),
                    "member": aggregate.get("member_no"),
                    "movement": target_score,
                    "lead_product": lead_product,
                    "lead_score": lead_score,
                    "detail_rows": detail_rows,
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


def create_summary_report(
    rows: list[dict],
    report_date: date,
    output_path: Path | None = None,
    report_type: str = "GT",
) -> Path:
    settings.export_path.mkdir(parents=True, exist_ok=True)
    report_type = str(report_type or "GT").upper()
    output_path = output_path or settings.export_path / f"Market_Survey_Summary_{report_type}_{report_date}.xlsx"

    if report_type == "GT" and settings.gt_summary_template_file.exists():
        return _create_gt_template_report(rows, report_date, output_path)

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
    ws["A1"] = f"KB Market Survey - {report_type} Region & Dealer Submission Summary"
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


def _copy_row_style(ws, source_row: int, target_row: int, max_col: int) -> None:
    for col in range(1, max_col + 1):
        source = ws.cell(source_row, col)
        target = ws.cell(target_row, col)
        if source.has_style:
            target._style = copy(source._style)
        target.number_format = source.number_format
        target.alignment = copy(source.alignment)
        target.protection = copy(source.protection)
    ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height


def _set_summary_row(ws, row_number: int, values: list) -> None:
    for col, value in enumerate(values, start=1):
        ws.cell(row_number, col).value = value


def _create_gt_template_report(rows: list[dict], report_date: date, output_path: Path) -> Path:
    """Populate the approved two-sheet GT management-summary template."""
    wb = load_workbook(settings.gt_summary_template_file)
    ws = wb["Summary"]
    detail = wb["Detail"]

    submitted = [row for row in rows if row["total_submissions"] > 0]
    ws["A1"] = "KB Market Survey - Region & Dealer Submission Summary"
    ws["A2"] = f"Report Date: {report_date} | Generated: {datetime.now():%d/%m/%Y %H:%M:%S}"

    movement_scores = [row["movement"] for row in submitted if row.get("movement") is not None]
    kpi_values = [
        len({row["region"] for row in rows}),
        len(rows),
        len(submitted),
        len(rows) - len(submitted),
        sum(row["total_submissions"] for row in rows),
        sum(score < 5 for score in movement_scores),
        sum(5 <= score <= 8 for score in movement_scores),
        sum(score >= 9 for score in movement_scores),
        sum(row.get("lead_product") == KPI_COMPETITORS[0] for row in submitted),
        sum(row.get("lead_product") == KPI_COMPETITORS[1] for row in submitted),
        sum(row.get("lead_product") == KPI_COMPETITORS[2] for row in submitted),
    ]
    for col, value in enumerate(kpi_values, start=1):
        ws.cell(5, col).value = value

    for old_row in range(9, ws.max_row + 1):
        for col in range(1, 12):
            ws.cell(old_row, col).value = None

    current_row = 9
    for region, dealers in REGION_DEALERS.items():
        region_rows = [row for row in rows if row["region"] == region]
        for row in region_rows:
            _copy_row_style(ws, 9, current_row, 11)
            movement = row.get("movement")
            buckets = [
                movement if movement is not None and movement < 5 else None,
                movement if movement is not None and 5 <= movement <= 8 else None,
                movement if movement is not None and movement >= 9 else None,
            ]
            _set_summary_row(
                ws,
                current_row,
                [
                    row["region"], row["dealer"], row.get("member"),
                    row["total_submissions"], row["total_outlets"], row["status"],
                    *buckets, row.get("lead_product") or None, row.get("lead_score"),
                ],
            )
            current_row += 1

        # Row 19 in the approved template is the first blue Region Total row.
        _copy_row_style(ws, 19, current_row, 11)
        region_scores = [row["movement"] for row in region_rows if row.get("movement") is not None]
        _set_summary_row(
            ws,
            current_row,
            [
                region, "Region Total", None,
                sum(row["total_submissions"] for row in region_rows),
                sum(row["total_outlets"] for row in region_rows),
                f"{sum(row['total_submissions'] > 0 for row in region_rows)}/{len(region_rows)} dealers submitted",
                sum(score < 5 for score in region_scores),
                sum(5 <= score <= 8 for score in region_scores),
                sum(score >= 9 for score in region_scores),
                None, None,
            ],
        )
        current_row += 1

    detail_headers = [
        "Date", "Region", "Dealer", "Outlet Name", "Phone Number Outlet",
        "Outlet Type", "Stock Status", "Freshness Date", "0 to 8",
        "Product Competitor", "Movement Lead", "Link Map",
    ]
    for col, value in enumerate(detail_headers, start=1):
        detail.cell(1, col).value = value

    detail_items = [item for row in rows for item in row.get("detail_rows", [])]
    for old_row in range(2, detail.max_row + 1):
        for col in range(1, 13):
            cell = detail.cell(old_row, col)
            cell.value = None
            cell.hyperlink = None

    for row_number, item in enumerate(detail_items, start=2):
        _copy_row_style(detail, 2, row_number, 12)
        values = [
            item["date"], item["region"], item["dealer"], item["outlet_name"],
            item["phone"], item["outlet_type"], item["stock"], item["freshness"],
            item["movement"], item["lead_product"], item["lead_score"],
            "Open Map" if item["map_link"] else None,
        ]
        _set_summary_row(detail, row_number, values)
        if item["map_link"]:
            detail.cell(row_number, 12).hyperlink = item["map_link"]
            detail.cell(row_number, 12).style = "Hyperlink"

    last_detail_row = max(2, len(detail_items) + 1)
    table = detail.tables.get("DetailMovementTable")
    if table:
        table.ref = f"A1:L{last_detail_row}"
    detail.auto_filter.ref = f"A1:L{last_detail_row}"

    wb.save(output_path)
    return output_path
