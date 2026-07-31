from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.config import settings
MOVEMENT_MULTI_PRODUCTS = [
    "CB LITE NCP",
    "GB SNOW NCP",
    "Hanuman LITE NCP",
    "Krud LITE NCP",
    "Greet LITE NCP",
]

BASE_HEADERS = [
    "Date",
    "Region",
    "Dealer",
    "Latitude",
    "Longitude",
    "Outlet Name",
    "Outlet Type",
    "Phone Number Outlet",
]


def _clean(value) -> str:
    return str(value or "").strip()


def _product_key(value) -> str:
    return " ".join(_clean(value).casefold().split())


def _all_metrics(submission):
    yield from list(getattr(submission, "product_metrics", None) or [])
    yield from list(getattr(submission, "competitor_metrics", None) or [])


def _metric_scores(submission) -> dict[str, int]:
    scores: dict[str, int] = {}
    for metric in _all_metrics(submission):
        value = getattr(metric, "movement_score", None)
        product = _product_key(getattr(metric, "product_name", None))
        if product and value is not None:
            scores[product] = int(value)
    return scores


def _style_sheet(ws, max_column: int) -> None:
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(max_column)}{max(ws.max_row, 1)}"
    widths = [13, 10, 12, 13, 13, 25, 18, 22]
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    for index in range(len(BASE_HEADERS) + 1, max_column + 1):
        ws.column_dimensions[get_column_letter(index)].width = 20
    ws.row_dimensions[1].height = 25


def create_movement_multi_export(
    submissions: Iterable,
    report_dates: list[date],
    *,
    output_path: Path | None = None,
) -> Path:
    """Create the fixed five-product Beer movement workbook.

    One row represents one outlet submission. The schema is intentionally
    fixed so Excel and downstream users always receive the same 13 columns.
    Blank movement remains blank; a genuine user-selected zero remains 0.
    """
    rows = sorted(
        list(submissions),
        key=lambda item: (
            getattr(item, "report_date", None) or date.min,
            _clean(getattr(item, "region", None)),
            _clean(getattr(item, "dealer", None)),
            _clean(getattr(item, "outlet_name", None)),
        ),
    )
    headers = BASE_HEADERS + MOVEMENT_MULTI_PRODUCTS

    wb = Workbook()
    ws = wb.active
    ws.title = "Detail_Movement"
    ws.append(headers)

    for submission in rows:
        scores = _metric_scores(submission)
        ws.append(
            [
                getattr(submission, "report_date", None),
                getattr(submission, "region", None),
                getattr(submission, "dealer", None),
                getattr(submission, "gps_latitude", None),
                getattr(submission, "gps_longitude", None),
                getattr(submission, "outlet_name", None),
                getattr(submission, "outlet_type", None),
                getattr(submission, "phone_number", None),
                *[scores.get(_product_key(product)) for product in MOVEMENT_MULTI_PRODUCTS],
            ]
        )

    for cell in ws["A"][1:]:
        cell.number_format = "yyyy-mm-dd"
    _style_sheet(ws, len(headers))

    settings.export_path.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        joined_dates = "_".join(str(item) for item in report_dates)
        output_path = settings.export_path / f"Detail_Movement_Beer_{joined_dates}.xlsx"
    wb.save(output_path)
    return output_path


RAW_MOVEMENT_HEADERS = [
    "Date",
    "Region",
    "Dealer",
    "Product",
    "Movement Rate",
]


def create_raw_movement_export(
    submissions: Iterable,
    report_date: date,
    *,
    output_path: Path | None = None,
) -> Path:
    """Create normalized product-level movement rows for one date.

    Blank/unanswered scores are excluded. Genuine user-selected zeroes are
    included, so the export remains a faithful raw movement dataset.
    """
    output_rows: list[list] = []
    for submission in submissions:
        for metric in _all_metrics(submission):
            product = _clean(getattr(metric, "product_name", None))
            score = getattr(metric, "movement_score", None)
            if not product or score is None:
                continue
            output_rows.append(
                [
                    getattr(submission, "report_date", None),
                    getattr(submission, "region", None),
                    getattr(submission, "dealer", None),
                    product,
                    int(score),
                ]
            )

    output_rows.sort(
        key=lambda row: (
            row[0] or date.min,
            _clean(row[1]).casefold(),
            _clean(row[2]).casefold(),
            _clean(row[3]).casefold(),
        )
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Raw_Movement"
    ws.append(RAW_MOVEMENT_HEADERS)
    for row in output_rows:
        ws.append(row)

    for cell in ws["A"][1:]:
        cell.number_format = "yyyy-mm-dd"
    _style_sheet(ws, len(RAW_MOVEMENT_HEADERS))
    ws.column_dimensions["D"].width = 28
    ws.column_dimensions["E"].width = 16

    settings.export_path.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = settings.export_path / f"Raw_Movement_GENERAL_{report_date}.xlsx"
    wb.save(output_path)
    return output_path


def create_movement_export(
    submissions: Iterable,
    report_dates: list[date],
    *,
    beer_only: bool,
    output_path: Path | None = None,
) -> Path:
    """Backward-compatible wrapper for older callers.

    New code should call one of the two explicit exporters above.
    """
    if beer_only:
        return create_movement_multi_export(
            submissions,
            report_dates,
            output_path=output_path,
        )
    if len(report_dates) != 1:
        raise ValueError("Raw movement export requires exactly one report date.")
    return create_raw_movement_export(
        submissions,
        report_dates[0],
        output_path=output_path,
    )
