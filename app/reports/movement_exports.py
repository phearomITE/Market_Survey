from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.config import settings
from app.reports.aggregator import ALL_COMPETITOR_PRODUCTS, ALL_OWN_PRODUCTS


BEER_PRODUCTS = [
    "CB LITE ORD",
    "GB SNOW ORD",
    "HANUMAN LITE ORD",
    "Krud LITE ORD",
    "CBC 4.4 NCP",
    "CB Original NCP",
    "GB Original NCP",
    "Krud NCP",
    "CB LITE NCP",
    "GB SNOW NCP",
    "Hanuman LITE NCP",
    "Krud LITE NCP",
    "Greet LITE NCP",
    "CB BLACK NCP",
    "Hanuman Black NCP",
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


def _metric_scores(submission) -> dict[str, int]:
    scores: dict[str, int] = {}
    for metric in list(getattr(submission, "product_metrics", None) or []):
        value = getattr(metric, "movement_score", None)
        if value is not None:
            scores[_clean(getattr(metric, "product_name", None))] = int(value)
    for metric in list(getattr(submission, "competitor_metrics", None) or []):
        value = getattr(metric, "movement_score", None)
        if value is not None:
            scores[_clean(getattr(metric, "product_name", None))] = int(value)
    return scores


def _ordered_products(submissions: Iterable, beer_only: bool) -> list[str]:
    rows = list(submissions)
    present = {
        product
        for submission in rows
        for product in _metric_scores(submission)
        if product
    }
    preferred = BEER_PRODUCTS if beer_only else list(dict.fromkeys(ALL_OWN_PRODUCTS + ALL_COMPETITOR_PRODUCTS))
    ordered = [product for product in preferred if product in present]
    ordered.extend(sorted(present.difference(ordered), key=str.casefold))
    return ordered


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


def create_movement_export(
    submissions: Iterable,
    report_dates: list[date],
    *,
    beer_only: bool,
    output_path: Path | None = None,
) -> Path:
    """Create a safe, table-free movement workbook.

    One row represents one outlet submission and each product has its own
    movement column. Blank movement remains blank; a genuine zero remains 0.
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
    products = _ordered_products(rows, beer_only=beer_only)
    headers = BASE_HEADERS + products

    wb = Workbook()
    ws = wb.active
    ws.title = "Movement"
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
                *[scores.get(product) for product in products],
            ]
        )

    for cell in ws["A"][1:]:
        cell.number_format = "yyyy-mm-dd"
    _style_sheet(ws, len(headers))

    settings.export_path.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        joined_dates = "_".join(str(item) for item in report_dates)
        prefix = "Detail_Movement_Beer" if beer_only else "Raw_Movement_GENERAL"
        output_path = settings.export_path / f"{prefix}_{joined_dates}.xlsx"
    wb.save(output_path)
    return output_path

