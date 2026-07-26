from __future__ import annotations

from collections import Counter, defaultdict
from copy import copy
from datetime import date, datetime
from pathlib import Path
import re
from typing import Iterable, Any

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.core.config import settings
from app.data.dealers import REGION_DEALERS
from app.reports.aggregator import is_final_summary_outlet_name


HEADER_FILL = "1F4E78"
REGION_FILL = "D9EAF7"
ZERO_FILL = "FCE4D6"
PARTIAL_FILL = "FFF2CC"
OK_FILL = "E2F0D9"
BORDER_COLOR = "D9E2F3"
RED_FILL = "D00000"
YELLOW_FILL = "FFC000"
GREEN_FILL = "00B050"

CB_LITE_PRODUCT = "CB LITE NCP"
CB_LITE_ALIASES = {
    "cblitencp",
    "cbclitencp",
    "cblite",
    "cbclite",
}
CB_LITE_COMPETITORS = [
    "GB SNOW NCP",
    "Hanuman LITE NCP",
    "Greet LITE NCP",
]
# The user-approved top KPI block contains exactly these three lead columns.
LEAD_TOTAL_PRODUCTS = [
    "GB SNOW NCP",
    "Hanuman LITE NCP",
    "Greet LITE NCP",
]

SUMMARY_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "templates"
    / "Market_Survey_Summary_Template.xlsx"
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


def _member_key(value: Any) -> str:
    parsed = _safe_int(value)
    if parsed is not None:
        return str(parsed)
    return _clean(value)


def most_frequent_member(submissions: Iterable) -> str:
    """Return the most common nonblank Member value.

    Equal counts are resolved by first appearance so results stay stable.
    """
    ordered: list[str] = []
    counts: Counter[str] = Counter()
    for submission in submissions:
        value = _member_key(getattr(submission, "member_no", None))
        if not value:
            continue
        if value not in counts:
            ordered.append(value)
        counts[value] += 1
    if not counts:
        return ""
    highest = max(counts.values())
    return next(value for value in ordered if counts[value] == highest)


def _lookup_product_data(aggregate: dict, product: str) -> dict:
    for bucket_name in ("products", "competitors"):
        bucket = aggregate.get(bucket_name) or {}
        value = bucket.get(product)
        if isinstance(value, dict):
            return value
        loose = "".join(ch for ch in product.lower() if ch.isalnum())
        value = bucket.get(loose)
        if isinstance(value, dict):
            return value
    return {}


def movement_summary_from_aggregate(aggregate: dict | None) -> dict[str, Any]:
    """Return CB LITE NCP band and the final competitor leader.

    All values come from aggregate_submissions(), which already applies the
    same final comparison normalization used by the dealer Excel/PNG report.
    """
    aggregate = aggregate or {}
    cb_mov = _safe_int(_lookup_product_data(aggregate, CB_LITE_PRODUCT).get("mov"))

    band_lt5 = cb_mov if cb_mov is not None and cb_mov < 5 else None
    band_5_8 = cb_mov if cb_mov is not None and 5 <= cb_mov <= 8 else None
    band_9_10 = cb_mov if cb_mov is not None and 9 <= cb_mov <= 10 else None

    lead_product = ""
    lead_movement: int | None = None
    for product in CB_LITE_COMPETITORS:
        movement = _safe_int(_lookup_product_data(aggregate, product).get("mov"))
        if movement == 10:
            lead_product = product
            lead_movement = 10
            break

    return {
        "cb_lite_movement": cb_mov,
        "movement_lt5": band_lt5,
        "movement_5_8": band_5_8,
        "movement_9_10": band_9_10,
        "product_competitor": lead_product,
        "movement_lead": lead_movement,
    }


def build_summary_rows(
    submissions: Iterable,
    dealer_aggregates: dict[str, dict] | None = None,
) -> list[dict]:
    """Return one row for every configured dealer, including zero-submit dealers.

    Submission totals use every real outlet row. Movement values are injected
    from dealer_aggregates created from GENERAL rows so /summary matches the
    final General dealer report exactly.
    """
    dealer_aggregates = dealer_aggregates or {}
    grouped: dict[str, list] = defaultdict(list)
    for submission in submissions:
        dealer = _clean(getattr(submission, "dealer", "")).upper()
        if dealer:
            grouped[dealer].append(submission)

    rows: list[dict] = []
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
                _clean(getattr(submission, "outlet_name", "")).casefold()
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

            row = {
                "region": region,
                "dealer": dealer,
                "member": most_frequent_member(outlet_rows),
                "total_submissions": total_submissions,
                "total_outlets": total_outlets,
                "target": target,
                "status": _status(total_submissions, total_outlets, target),
            }
            row.update(
                movement_summary_from_aggregate(dealer_aggregates.get(dealer))
            )
            rows.append(row)
    return rows


def _metric_product_key(value: Any) -> str:
    return "".join(ch for ch in _clean(value).casefold() if ch.isalnum())


def _cb_lite_metric(submission: Any):
    for metric in list(getattr(submission, "product_metrics", None) or []):
        if _metric_product_key(getattr(metric, "product_name", "")) in CB_LITE_ALIASES:
            return metric
    return None


def _coordinates(submission: Any) -> tuple[float | None, float | None]:
    lat = getattr(submission, "gps_latitude", None)
    lon = getattr(submission, "gps_longitude", None)
    try:
        if lat not in (None, "") and lon not in (None, ""):
            return float(lat), float(lon)
    except Exception:
        pass

    gps_text = _clean(getattr(submission, "gps_text", ""))
    numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", gps_text)
    if len(numbers) >= 2:
        try:
            return float(numbers[0]), float(numbers[1])
        except Exception:
            pass
    return None, None


def _map_url(submission: Any) -> str:
    lat, lon = _coordinates(submission)
    if lat is None or lon is None:
        return ""
    return f"https://www.google.com/maps?q={lat:.7f},{lon:.7f}"


def build_detail_rows(
    general_submissions: Iterable,
    dealer_aggregates: dict[str, dict],
) -> list[dict]:
    """Build outlet detail for explicit CB LITE NCP movement scores below 5.

    Blank/no-sale movement fields are not listed. A row is included only when
    the outlet has a real numeric score from 0 to 4 and the dealer's final
    normalized CB LITE NCP movement is also below 5.
    """
    rows: list[dict] = []
    for submission in general_submissions:
        if is_final_summary_outlet_name(getattr(submission, "outlet_name", None)):
            continue

        dealer = _clean(getattr(submission, "dealer", "")).upper()
        aggregate = dealer_aggregates.get(dealer) or {}
        movement_info = movement_summary_from_aggregate(aggregate)
        dealer_movement = movement_info.get("cb_lite_movement")
        if dealer_movement is None or dealer_movement >= 5:
            continue

        metric = _cb_lite_metric(submission)
        outlet_movement = _safe_int(getattr(metric, "movement_score", None))
        if outlet_movement is None or outlet_movement >= 5:
            continue

        rows.append(
            {
                "date": getattr(submission, "report_date", None),
                "region": _clean(getattr(submission, "region", "")),
                "dealer": dealer,
                "outlet_name": _clean(getattr(submission, "outlet_name", "")),
                "phone_number": _clean(getattr(submission, "phone_number", "")),
                "outlet_type": _clean(getattr(submission, "outlet_type", "")),
                "stock_status": _clean(getattr(metric, "stock_status", "")),
                "freshness_date": _clean(getattr(metric, "bbe_date", "")),
                "movement_lt5": outlet_movement,
                "product_competitor": movement_info.get("product_competitor", ""),
                "movement_lead": movement_info.get("movement_lead"),
                "link_map": _map_url(submission),
            }
        )

    region_order = {region: index for index, region in enumerate(REGION_DEALERS)}
    dealer_order = {
        dealer: index
        for index, dealer in enumerate(
            dealer for dealers in REGION_DEALERS.values() for dealer in dealers
        )
    }
    rows.sort(
        key=lambda row: (
            region_order.get(row["region"], 999),
            dealer_order.get(row["dealer"], 999),
            row["outlet_name"].casefold(),
        )
    )
    return rows


def _fallback_workbook() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["KB Market Survey - Region & Dealer Submission Summary"])
    ws.append([None])
    ws.append([None])
    ws.append(
        [
            "Total Regions",
            "Total Dealers",
            "Submitted Dealers",
            "No Submit Dealers",
            "Total Submissions",
            "<5",
            "5 to 8",
            "9 to 10",
            "GB SNOW NCP",
            "Hanuman LITE NCP",
            "Greet LITE NCP",
        ]
    )
    ws.append([None] * 11)
    ws.append([None] * 11)
    ws.append([None] * 6 + ["Movement CB LITE NCP compare to Competitors"])
    ws.append(
        [
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
    )
    detail = wb.create_sheet("Detail")
    detail.append(
        [
            "Date",
            "Region",
            "Dealer",
            "Outlet Name",
            "Phone Number Outlet",
            "Outlet Type",
            "Stock Status",
            "Freshness Date",
            "<5",
            "Product Competitor",
            "Movement Lead",
            "Link Map",
        ]
    )
    return wb


def _copy_row_style(ws, source_row: int, target_row: int, max_col: int) -> None:
    for col in range(1, max_col + 1):
        source = ws.cell(source_row, col)
        target = ws.cell(target_row, col)
        if source.has_style:
            target._style = copy(source._style)
        if source.number_format:
            target.number_format = source.number_format
        target.alignment = copy(source.alignment)
    ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height


def _apply_summary_styles(ws) -> None:
    thin = Side(style="thin", color=BORDER_COLOR)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.merge_cells("A1:K1")
    ws.merge_cells("A2:K2")
    # Keep the movement title centered over the five movement columns.
    for merged in list(ws.merged_cells.ranges):
        if str(merged) in {"G7:K7", "G7:H7", "G7:I7"}:
            ws.unmerge_cells(str(merged))
    ws.merge_cells("G7:K7")

    for row in ws.iter_rows(min_row=1, max_row=max(81, ws.max_row), min_col=1, max_col=11):
        for cell in row:
            if isinstance(cell, MergedCell):
                continue
            cell.border = border
            cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
            if not cell.font or not cell.font.name:
                cell.font = Font(name="Calibri", size=11)

    ws["A1"].fill = PatternFill("solid", fgColor=HEADER_FILL)
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    ws["A2"].font = Font(name="Calibri", size=11, italic=True, color="666666")

    for col in range(1, 12):
        ws.cell(4, col).font = Font(name="Calibri", size=11, bold=True)
        ws.cell(4, col).fill = PatternFill("solid", fgColor="F8FBFD")
        ws.cell(5, col).fill = PatternFill("solid", fgColor="F8FBFD")

    for col in range(1, 12):
        cell = ws.cell(8, col)
        cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    for row in (4, 8):
        ws.cell(row, 6).fill = PatternFill("solid", fgColor=RED_FILL)
        ws.cell(row, 7).fill = PatternFill("solid", fgColor=YELLOW_FILL)
        ws.cell(row, 8).fill = PatternFill("solid", fgColor=GREEN_FILL)
        for col in (6, 7, 8):
            ws.cell(row, col).font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    for row in range(9, ws.max_row + 1):
        status = _clean(ws.cell(row, 6).value)
        if ws.cell(row, 2).value == "Region Total":
            fill = PatternFill("solid", fgColor=REGION_FILL)
        elif "No Submit" in status:
            fill = PatternFill("solid", fgColor=ZERO_FILL)
        elif "Partial" in status:
            fill = PatternFill("solid", fgColor=PARTIAL_FILL)
        else:
            fill = PatternFill("solid", fgColor=OK_FILL)
        for col in range(1, 12):
            ws.cell(row, col).fill = fill
        ws.cell(row, 1).font = Font(bold=True)
        ws.cell(row, 2).font = Font(bold=True)
        if ws.cell(row, 7).value not in (None, ""):
            ws.cell(row, 7).font = Font(bold=True, color="D00000")
        if ws.cell(row, 8).value not in (None, ""):
            ws.cell(row, 8).font = Font(bold=True, color="C69200")
        if ws.cell(row, 9).value not in (None, ""):
            ws.cell(row, 9).font = Font(bold=True, color="00A651")
        if ws.cell(row, 11).value not in (None, ""):
            ws.cell(row, 11).font = Font(bold=True, color="00A651")

    widths = {
        "A": 12,
        "B": 14,
        "C": 14,
        "D": 20,
        "E": 16,
        "F": 22,
        "G": 14,
        "H": 14,
        "I": 14,
        "J": 22,
        "K": 16,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A9"


def _apply_detail_styles(ws, max_row: int) -> None:
    thin = Side(style="thin", color=BORDER_COLOR)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col in range(1, 13):
        cell = ws.cell(1, col)
        cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for row in range(2, max_row + 1):
        if row > 2:
            _copy_row_style(ws, 2, row, 12)
        for col in range(1, 13):
            cell = ws.cell(row, col)
            cell.border = border
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.cell(row, 9).font = Font(bold=True, color="D00000")
        ws.cell(row, 11).font = Font(bold=True, color="00A651")

    widths = {
        "A": 13,
        "B": 10,
        "C": 12,
        "D": 28,
        "E": 20,
        "F": 18,
        "G": 16,
        "H": 16,
        "I": 10,
        "J": 22,
        "K": 15,
        "L": 18,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:L{max(2, max_row)}"


def create_summary_report(
    rows: list[dict],
    report_date: date,
    detail_rows: list[dict] | None = None,
    output_path: Path | None = None,
) -> Path:
    settings.export_path.mkdir(parents=True, exist_ok=True)
    output_path = output_path or settings.export_path / f"Market_Survey_Summary_{report_date}.xlsx"
    detail_rows = detail_rows or []

    wb = load_workbook(SUMMARY_TEMPLATE) if SUMMARY_TEMPLATE.exists() else _fallback_workbook()
    ws = wb["Summary"]
    detail_ws = wb["Detail"] if "Detail" in wb.sheetnames else wb.create_sheet("Detail")

    # Clear all old values while preserving the approved workbook formatting.
    for row in ws.iter_rows(min_row=2, max_row=max(ws.max_row, 81), min_col=1, max_col=11):
        if row[0].row not in (4, 7, 8):
            for cell in row:
                if not isinstance(cell, MergedCell):
                    cell.value = None
    for row in detail_ws.iter_rows(min_row=2, max_row=max(detail_ws.max_row, len(detail_rows) + 2), min_col=1, max_col=12):
        for cell in row:
            cell.value = None
            cell.hyperlink = None

    total_dealers = len(rows)
    submitted_dealers = sum(1 for row in rows if row["total_submissions"] > 0)
    no_submit = total_dealers - submitted_dealers
    total_submissions = sum(row["total_submissions"] for row in rows)

    movement_lt5_total = sum(1 for row in rows if row.get("movement_lt5") is not None)
    movement_5_8_total = sum(1 for row in rows if row.get("movement_5_8") is not None)
    movement_9_10_total = sum(1 for row in rows if row.get("movement_9_10") is not None)
    lead_totals = Counter(
        row.get("product_competitor")
        for row in rows
        if row.get("product_competitor")
    )

    ws["A1"] = "KB Market Survey - Region & Dealer Submission Summary"
    ws["A2"] = f"Report Date: {report_date} | Generated: {datetime.now():%d/%m/%Y %H:%M:%S}"

    kpis = [
        len(set(row["region"] for row in rows)),
        total_dealers,
        submitted_dealers,
        no_submit,
        total_submissions,
        movement_lt5_total,
        movement_5_8_total,
        movement_9_10_total,
        lead_totals.get("GB SNOW NCP", 0),
        lead_totals.get("Hanuman LITE NCP", 0),
        lead_totals.get("Greet LITE NCP", 0),
    ]
    for col, value in enumerate(kpis, start=1):
        ws.cell(5, col).value = value

    current_row = 9
    for region in REGION_DEALERS:
        region_rows = [row for row in rows if row["region"] == region]
        for row in region_rows:
            values = [
                row["region"],
                row["dealer"],
                row.get("member", ""),
                row["total_submissions"],
                row["total_outlets"],
                row["status"],
                row.get("movement_lt5"),
                row.get("movement_5_8"),
                row.get("movement_9_10"),
                row.get("product_competitor", ""),
                row.get("movement_lead"),
            ]
            for col, value in enumerate(values, start=1):
                ws.cell(current_row, col).value = value
            current_row += 1

        subtotal_values = [
            region,
            "Region Total",
            "",
            sum(row["total_submissions"] for row in region_rows),
            sum(row["total_outlets"] for row in region_rows),
            f"{sum(1 for row in region_rows if row['total_submissions'] > 0)}/{len(region_rows)} dealers submitted",
            "",
            "",
            "",
            "",
            "",
        ]
        for col, value in enumerate(subtotal_values, start=1):
            ws.cell(current_row, col).value = value
        current_row += 1

    _apply_summary_styles(ws)

    headers = [
        "Date",
        "Region",
        "Dealer",
        "Outlet Name",
        "Phone Number Outlet",
        "Outlet Type",
        "Stock Status",
        "Freshness Date",
        "<5",
        "Product Competitor",
        "Movement Lead",
        "Link Map",
    ]
    for col, header in enumerate(headers, start=1):
        detail_ws.cell(1, col).value = header

    for row_index, row in enumerate(detail_rows, start=2):
        values = [
            row.get("date"),
            row.get("region"),
            row.get("dealer"),
            row.get("outlet_name"),
            row.get("phone_number"),
            row.get("outlet_type"),
            row.get("stock_status"),
            row.get("freshness_date"),
            row.get("movement_lt5"),
            row.get("product_competitor"),
            row.get("movement_lead"),
            "Open Map" if row.get("link_map") else "",
        ]
        for col, value in enumerate(values, start=1):
            detail_ws.cell(row_index, col).value = value
        if isinstance(row.get("date"), date):
            detail_ws.cell(row_index, 1).number_format = "dd/mm/yyyy"
        link = row.get("link_map")
        if link:
            detail_ws.cell(row_index, 12).hyperlink = link
            detail_ws.cell(row_index, 12).style = "Hyperlink"

    _apply_detail_styles(detail_ws, max(2, len(detail_rows) + 1))
    wb.save(output_path)
    return output_path
