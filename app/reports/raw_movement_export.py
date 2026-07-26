from __future__ import annotations

"""Raw movement exports for audit and movement-calculation review.

The workbook has two sheets:
- Raw_Movement: one row per explicitly submitted movement score.
- All_Products: one row per dealer and one column for every comparison product;
  cells contain the raw average before final comparison-group normalization.

Only explicit movement scores from 1 to 10 are used. Blank fields, status-only
answers, and zero placeholders are excluded, matching the final movement input
rule used by the report engine.
"""

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo

from app.core.config import settings
from app.reports.aggregator import (
    COMPETITOR_PRODUCTS,
    OFFTAKE_COMPARE_GROUPS,
    OWN_PRODUCTS,
    _loose_movement_value,
    _metric_by_product,
    _product_lookup_key,
    _value,
    _wide_payload_for_submission,
    _wide_payloads_by_submission,
    competitor_field,
    first_value,
    is_final_summary_outlet_name,
    product_field,
    to_int,
)


RAW_MOVEMENT_PRODUCTS: list[str] = []
for _group in OFFTAKE_COMPARE_GROUPS:
    for _product in _group:
        if _product not in RAW_MOVEMENT_PRODUCTS:
            RAW_MOVEMENT_PRODUCTS.append(_product)

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_TABLE_STYLE = "TableStyleMedium2"


def _explicit_movement_from_payload(payload: dict[str, Any], product: str, is_competitor: bool) -> int | None:
    """Read only the movement question; never convert Sale Status to movement."""
    keys = competitor_field(product, "mov") if is_competitor else product_field(product, "mov")
    value = first_value(payload, keys)
    movement = to_int(value)
    if movement is None:
        movement = _loose_movement_value(payload, product, is_competitor)
    if movement is None or not 1 <= movement <= 10:
        return None
    return movement


def _explicit_movement(
    submission: Any,
    metric: Any,
    product: str,
    is_competitor: bool,
    wide_map: dict[str, dict[str, Any]],
) -> int | None:
    """Read an explicitly entered 1-10 score, preferring the wide Kobo row."""
    payload = _wide_payload_for_submission(submission, wide_map)
    if payload:
        movement = _explicit_movement_from_payload(payload, product, is_competitor)
        if movement is not None:
            return movement

    movement = to_int(_value(metric, "movement_score"))
    if movement is None or not 1 <= movement <= 10:
        return None
    return movement


def build_raw_movement_data(
    submissions: list[Any],
    *,
    wide_map: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[list[Any]], list[list[Any]]]:
    """Return long raw-score rows and dealer-wide raw-average rows.

    Long rows:
      Date, Region, Dealer, Product, Movement Rate

    Wide rows:
      Date, Region, Dealer, <57 product columns>
    """
    outlet_rows = [
        submission
        for submission in list(submissions or [])
        if not is_final_summary_outlet_name(getattr(submission, "outlet_name", None))
    ]
    if wide_map is None:
        wide_map = _wide_payloads_by_submission(outlet_rows)

    product_order = {product: index for index, product in enumerate(RAW_MOVEMENT_PRODUCTS)}
    long_rows: list[list[Any]] = []
    scores_by_dealer: dict[tuple[str, str, str], dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for submission in outlet_rows:
        report_date = getattr(submission, "report_date", None)
        date_text = report_date.isoformat() if hasattr(report_date, "isoformat") else str(report_date or "")
        region = str(getattr(submission, "region", "") or "").strip().upper()
        dealer = str(getattr(submission, "dealer", "") or "").strip().upper()
        if not dealer:
            continue

        own_map = _metric_by_product(list(getattr(submission, "product_metrics", []) or []))
        competitor_map = _metric_by_product(list(getattr(submission, "competitor_metrics", []) or []))

        for product in RAW_MOVEMENT_PRODUCTS:
            # Cross-over own products must be read from their own-product fields.
            is_own = product in OWN_PRODUCTS
            is_competitor = not is_own
            metric_map = own_map if is_own else competitor_map
            metric = metric_map.get(product) or metric_map.get(_product_lookup_key(product))

            movement = _explicit_movement(
                submission,
                metric,
                product,
                is_competitor=is_competitor,
                wide_map=wide_map,
            )
            if movement is None:
                continue

            long_rows.append([date_text, region, dealer, product, movement])
            scores_by_dealer[(date_text, region, dealer)][product].append(movement)

    long_rows.sort(
        key=lambda row: (
            row[0],
            row[1],
            row[2],
            product_order.get(str(row[3]), 999),
            row[4],
        )
    )

    wide_rows: list[list[Any]] = []
    for (date_text, region, dealer), product_scores in sorted(scores_by_dealer.items()):
        values: list[Any] = [date_text, region, dealer]
        for product in RAW_MOVEMENT_PRODUCTS:
            scores = product_scores.get(product, [])
            values.append(round(sum(scores) / len(scores), 2) if scores else None)
        wide_rows.append(values)

    return long_rows, wide_rows


def _style_header(ws, columns: int) -> None:
    for cell in ws[1][:columns]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"


def _add_safe_table(ws, ref: str, name: str) -> None:
    table = Table(displayName=name, ref=ref)
    table.tableStyleInfo = TableStyleInfo(
        name=_TABLE_STYLE,
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(table)


def create_raw_movement_export(
    submissions: list[Any],
    report_date: date,
    *,
    report_type: str = "GENERAL",
) -> Path:
    long_rows, wide_rows = build_raw_movement_data(submissions)

    output_dir = settings.export_path
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "CHANNEL_SPECIALIST" if report_type == "CHANNEL_SPECIALIST" else "GENERAL"
    output_path = output_dir / f"Raw_Movement_{suffix}_{report_date.isoformat()}.xlsx"

    workbook = Workbook()
    raw_sheet = workbook.active
    raw_sheet.title = "Raw_Movement"
    raw_headers = ["Date", "Region", "Dealer", "Product", "Movement Rate"]
    raw_sheet.append(raw_headers)
    for row in long_rows:
        raw_sheet.append(row)

    _style_header(raw_sheet, len(raw_headers))
    raw_sheet.column_dimensions["A"].width = 14
    raw_sheet.column_dimensions["B"].width = 10
    raw_sheet.column_dimensions["C"].width = 12
    raw_sheet.column_dimensions["D"].width = 30
    raw_sheet.column_dimensions["E"].width = 16
    raw_sheet["A1"].alignment = Alignment(horizontal="center")
    if raw_sheet.max_row >= 2:
        _add_safe_table(raw_sheet, f"A1:E{raw_sheet.max_row}", "RawMovementTable")

    all_sheet = workbook.create_sheet("All_Products")
    wide_headers = ["Date", "Region", "Dealer", *RAW_MOVEMENT_PRODUCTS]
    all_sheet.append(wide_headers)
    for row in wide_rows:
        all_sheet.append(row)

    _style_header(all_sheet, len(wide_headers))
    all_sheet.column_dimensions["A"].width = 14
    all_sheet.column_dimensions["B"].width = 10
    all_sheet.column_dimensions["C"].width = 12
    for column in range(4, len(wide_headers) + 1):
        all_sheet.column_dimensions[all_sheet.cell(1, column).column_letter].width = 18
    if all_sheet.max_row >= 2:
        end_column = all_sheet.cell(1, len(wide_headers)).column_letter
        _add_safe_table(all_sheet, f"A1:{end_column}{all_sheet.max_row}", "AllProductsMovementTable")

    workbook.save(output_path)
    return output_path
