# app/reports/summary_report.py

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.core.config import settings
from app.data.dealers import REGION_DEALERS
from app.reports.aggregator import (
    build_bulk_dealer_aggregates,
    is_final_summary_outlet_name,
)


HEADER_FILL = "1F4E78"
REGION_FILL = "D9EAF7"
ZERO_FILL = "FCE4D6"
PARTIAL_FILL = "FFF2CC"
OK_FILL = "E2F0D9"
BORDER_COLOR = "D9E2F3"

MOVEMENT_RED = "C00000"
MOVEMENT_YELLOW = "FFC000"
MOVEMENT_GREEN = "00B050"
MOVEMENT_TITLE_RED = "FF0000"

CHANNEL_SPECIALIST_OUTLET_TYPES = {
    "Local Eat",
    "Coffee,Bakery",
    "Canteen",
    "Sport Club",
    "Motor Shop",
}

CB_LITE_NCP = "CB LITE NCP"
CB_LITE_NCP_COMPETITORS = (
    "GB SNOW NCP",
    "Hanuman LITE NCP",
    "Krud LITE NCP",
    "Greet LITE NCP",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _status(total_submissions: int, total_outlets: int, target: int | None) -> str:
    if total_submissions <= 0:
        return "❌ No Submit"
    if target and total_outlets < target:
        return "⚠ Partial"
    return "✅"


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except Exception:
        return None


def _member_value(value: Any) -> str:
    """Normalize Member values so 7, 7.0 and '7' are counted together."""
    parsed = _safe_int(value)
    if parsed is not None:
        return str(parsed)
    return _clean(value)


def most_frequent_member(submissions: Iterable[Any]) -> str:
    """Return only the Member value occurring most often.

    When counts tie, keep the value that appeared first in the dealer's rows.
    Blank values are ignored.
    """
    values = [
        value
        for submission in submissions
        if (value := _member_value(getattr(submission, "member_no", None)))
    ]
    if not values:
        return ""

    counts = Counter(values)
    highest_count = max(counts.values())
    return next(value for value in values if counts[value] == highest_count)


def _movement_from_bucket(bucket: dict[str, Any] | None, product: str) -> int | None:
    if not isinstance(bucket, dict):
        return None
    metrics = bucket.get(product)
    if not isinstance(metrics, dict):
        return None
    value = _safe_int(metrics.get("mov"))
    if value is None:
        return None
    return max(0, min(10, value))


def movement_comparison_from_aggregate(aggregate: dict[str, Any] | None) -> dict[str, Any]:
    """Build the five summary columns from final report movement values.

    CB LITE NCP is written into exactly one movement band:
      * <5
      * 5 to 8
      * 9 to 10

    Product Competitor and Movement Lead are shown only when a competitor in
    the CB LITE NCP comparison group has the final normalized movement 10.
    This is the same final value used by the dealer Market Improvement Report.
    """
    aggregate = aggregate or {}
    own_movement = _movement_from_bucket(aggregate.get("products"), CB_LITE_NCP)

    result: dict[str, Any] = {
        "movement_under_5": None,
        "movement_5_to_8": None,
        "movement_9_to_10": None,
        "competitor_product": "",
        "competitor_movement_lead": None,
    }

    if own_movement is not None:
        if own_movement < 5:
            result["movement_under_5"] = own_movement
        elif own_movement <= 8:
            result["movement_5_to_8"] = own_movement
        else:
            result["movement_9_to_10"] = own_movement

    competitors = aggregate.get("competitors") or {}
    for product in CB_LITE_NCP_COMPETITORS:
        movement = _movement_from_bucket(competitors, product)
        if movement == 10:
            result["competitor_product"] = product
            result["competitor_movement_lead"] = 10
            break

    return result


def build_summary_rows(
    submissions: Iterable[Any],
    *,
    dealer_aggregates: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return one row for every configured dealer, including zero-submit dealers.

    Bulk movement is supplied by the fast dealer analytics cache. It uses the
    same final normalization rules as the GENERAL dealer report without loading
    tens of thousands of ORM metric objects or recalculating unused fields.
    """
    submission_list = list(submissions or [])
    if dealer_aggregates is None:
        dealer_aggregates, _cache_hit = build_bulk_dealer_aggregates(submission_list)

    grouped: dict[str, list[Any]] = defaultdict(list)
    for submission in submission_list:
        dealer = _clean(getattr(submission, "dealer", "")).upper()
        if dealer:
            grouped[dealer].append(submission)

    rows: list[dict[str, Any]] = []
    for region, dealers in REGION_DEALERS.items():
        for dealer in dealers:
            dealer_rows = grouped.get(dealer, [])
            outlet_rows = [
                submission
                for submission in dealer_rows
                if not is_final_summary_outlet_name(
                    getattr(submission, "outlet_name", None)
                )
            ]
            total_submissions = len(outlet_rows)

            outlet_names = {
                _clean(getattr(submission, "outlet_name", "")).lower()
                for submission in outlet_rows
                if _clean(getattr(submission, "outlet_name", ""))
            }
            total_outlets = len(outlet_names) if outlet_names else total_submissions

            targets = [
                _safe_int(getattr(submission, "total_outlet_visit_target", None))
                for submission in outlet_rows
            ]
            targets = [target for target in targets if target is not None]
            target = max(targets) if targets else None

            movement_summary = movement_comparison_from_aggregate(
                (dealer_aggregates or {}).get(dealer)
            )

            rows.append(
                {
                    "region": region,
                    "dealer": dealer,
                    "member": most_frequent_member(outlet_rows),
                    "total_submissions": total_submissions,
                    "total_outlets": total_outlets,
                    "target": target,
                    "status": _status(total_submissions, total_outlets, target),
                    **movement_summary,
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

    # Main title rows.
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=HEADER_FILL)
    ws["A2"].font = Font(name="Calibri", size=11, italic=True, color="666666")

    # KPI block.
    for row in range(4, 7):
        for col in range(1, 8):
            cell = ws.cell(row, col)
            cell.fill = PatternFill("solid", fgColor="F8FBFD")
            cell.font = Font(name="Calibri", size=11, bold=(row == 4))

    # Movement section title.
    ws["G7"].font = Font(
        name="Calibri", size=13, bold=False, color=MOVEMENT_TITLE_RED
    )
    ws["G7"].alignment = Alignment(horizontal="center", vertical="center")

    # Main headers A:F.
    for col in range(1, 7):
        cell = ws.cell(8, col)
        cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    # Movement band headers G:I.
    band_headers = {
        7: MOVEMENT_RED,
        8: MOVEMENT_YELLOW,
        9: MOVEMENT_GREEN,
    }
    for col, color in band_headers.items():
        cell = ws.cell(8, col)
        cell.fill = PatternFill("solid", fgColor=color)
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    # Competitor headers J:K.
    for col in range(10, 12):
        cell = ws.cell(8, col)
        cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    # Dealer data rows.
    for row in range(9, ws.max_row + 1):
        status = str(ws.cell(row, 6).value or "")
        fill = None
        if "No Submit" in status:
            fill = PatternFill("solid", fgColor=ZERO_FILL)
        elif "Partial" in status:
            fill = PatternFill("solid", fgColor=PARTIAL_FILL)
        elif "✅" in status:
            fill = PatternFill("solid", fgColor=OK_FILL)
        if fill:
            for col in range(1, 12):
                ws.cell(row, col).fill = fill

        ws.cell(row, 1).font = Font(bold=True)
        ws.cell(row, 2).font = Font(bold=True)

        # Keep the status-row background, but make the movement values follow
        # the requested red / yellow / green color convention.
        ws.cell(row, 7).font = Font(bold=True, color=MOVEMENT_RED)
        ws.cell(row, 8).font = Font(bold=True, color="F4A000")
        ws.cell(row, 9).font = Font(bold=True, color=MOVEMENT_GREEN)
        ws.cell(row, 10).font = Font(bold=True, color="1F1F1F")
        ws.cell(row, 11).font = Font(bold=True, color=MOVEMENT_GREEN)

    ws.freeze_panes = "A9"
    widths = {
        "A": 12,
        "B": 14,
        "C": 14,
        "D": 20,
        "E": 16,
        "F": 20,
        "G": 14,
        "H": 14,
        "I": 14,
        "J": 24,
        "K": 16,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    for row in range(1, ws.max_row + 1):
        ws.row_dimensions[row].height = 22
    ws.row_dimensions[7].height = 28
    ws.row_dimensions[8].height = 26


def create_summary_report(
    rows: list[dict[str, Any]],
    report_date: date,
    output_path: Path | None = None,
) -> Path:
    settings.export_path.mkdir(parents=True, exist_ok=True)
    output_path = output_path or settings.export_path / (
        f"Market_Survey_Summary_{report_date}.xlsx"
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"

    total_dealers = len(rows)
    submitted_dealers = sum(1 for row in rows if row["total_submissions"] > 0)
    no_submit = total_dealers - submitted_dealers
    total_submissions = sum(row["total_submissions"] for row in rows)
    total_outlets = sum(row["total_outlets"] for row in rows)
    completion = submitted_dealers / total_dealers if total_dealers else 0

    ws.merge_cells("A1:K1")
    ws["A1"] = "KB Market Survey - Region & Dealer Submission Summary"
    ws.merge_cells("A2:K2")
    ws["A2"] = (
        f"Report Date: {report_date} | Generated: "
        f"{datetime.now():%d/%m/%Y %H:%M:%S}"
    )

    kpis = [
        ("Total Regions", len(set(row["region"] for row in rows))),
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

    ws.merge_cells("G7:K7")
    ws["G7"] = "Movement CB LITE NCP compare to Competitors"

    headers = [
        "Region",
        "Dealer",
        "Member",
        "Total Submissions",
        "Total Outlets",
        "Status",
        "<5",
        "5 to 8",
        "9 to 10",
        "Product Competitor",
        "Movement Lead",
    ]
    for col, value in enumerate(headers, start=1):
        ws.cell(8, col).value = value

    current_row = 9
    for region in REGION_DEALERS:
        region_rows = [row for row in rows if row["region"] == region]
        for row_data in region_rows:
            values = [
                row_data["region"],
                row_data["dealer"],
                row_data.get("member", ""),
                row_data["total_submissions"],
                row_data["total_outlets"],
                row_data["status"],
                row_data.get("movement_under_5"),
                row_data.get("movement_5_to_8"),
                row_data.get("movement_9_to_10"),
                row_data.get("competitor_product", ""),
                row_data.get("competitor_movement_lead"),
            ]
            for col, value in enumerate(values, start=1):
                ws.cell(current_row, col).value = value
            current_row += 1

        # Region subtotal row.
        ws.cell(current_row, 1).value = region
        ws.cell(current_row, 2).value = "Region Total"
        ws.cell(current_row, 3).value = ""
        ws.cell(current_row, 4).value = sum(
            row["total_submissions"] for row in region_rows
        )
        ws.cell(current_row, 5).value = sum(row["total_outlets"] for row in region_rows)
        submitted = sum(1 for row in region_rows if row["total_submissions"] > 0)
        ws.cell(current_row, 6).value = (
            f"{submitted}/{len(region_rows)} dealers submitted"
        )
        for col in range(1, 12):
            ws.cell(current_row, col).fill = PatternFill(
                "solid", fgColor=REGION_FILL
            )
            ws.cell(current_row, col).font = Font(bold=True)
        current_row += 1

    _style_summary_sheet(ws)
    wb.save(output_path)
    return output_path
