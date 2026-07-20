from __future__ import annotations

from collections import defaultdict
from copy import copy
from datetime import date
from pathlib import Path
import re
from typing import Any, Iterable

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.core.config import BASE_DIR, settings
from app.reports.aggregator import OFFTAKE_COMPARE_GROUPS, aggregate_submissions


SUMMARY_MARKERS = {
    "បូកសរុបរួម",
    "បូកសរុបរូម",
    "សរុបរួម",
    "បួកសរុបរួម",
}

SUMMARY_SHEET = "Summary_Data"
LOCATION_SHEET = "Location_Outlet"
DATA_EXPORT_TEMPLATE = BASE_DIR / "templates" / "Template_Data_Survey.xlsx"

SUMMARY_HEADERS = [
    "Region",
    "Dealer",
    "Location_Visit",
    "Member",
    "Group",
    "Total_Outlets",
    "Wholesale",
    "Drink_Shop",
    "Wet_Market",
    "Trolley",
    "Product",
    "WS",
    "DS",
    "WM",
    "TL",
    "Mov",
]

LOCATION_HEADERS = [
    "Date",
    "Region",
    "Dealer",
    "Latitude",
    "Longitude",
    "Outlet Name",
    "Outlet Type",
    "Phone Number Outlet",
]

# The comparison groups define the exact 57-product report order.
EXPORT_PRODUCTS: tuple[str, ...] = tuple(
    product
    for group in OFFTAKE_COMPARE_GROUPS
    for product in group
)

PRODUCT_DISPLAY_ALIASES = {
    "CAMBODIA Sport 300ml": "CAMBODIA Sport 300mL",
}

PRODUCT_LOOKUP_ALIASES = {
    "CAMBODIA Sport 300ml": (
        "CAMBODIA Sport 300mL",
        "CAMBODIA Sport 300ml",
    ),
    "EXPREZ Can 330ml": (
        "EXPREZ Can 330ml",
    ),
}

OUTLET_TYPE_KEYS = {
    "Wholesale": "wholesale",
    "Drink_Shop": "drinkshop",
    "Wet_Market": "wetmarket",
    "Trolley": "trolley",
}

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_THIN = Side(style="thin", color="D9E2F3")
_DATA_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _is_summary_submission(submission: Any) -> bool:
    return _clean(getattr(submission, "outlet_name", None)) in SUMMARY_MARKERS


def _region_sort(value: Any) -> tuple[int, str]:
    text = _clean(value).upper()
    match = re.fullmatch(r"R(\d+)", text)
    return (int(match.group(1)), text) if match else (999, text)


def _numeric_text_sort(value: Any) -> tuple[int, Any]:
    if value in (None, ""):
        return (2, "")
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, _clean(value).lower())


def _group_sort_key(item: tuple[tuple[str, str], list[Any]]):
    (region, dealer), _rows = item
    return (_region_sort(region), _clean(dealer).upper())


def _location_sort_key(submission: Any):
    return (
        _region_sort(getattr(submission, "region", None)),
        _clean(getattr(submission, "dealer", None)).upper(),
        _numeric_text_sort(getattr(submission, "member_no", None)),
        _clean(getattr(submission, "outlet_name", None)).lower(),
    )


def _normalize_outlet_type(value: Any) -> str:
    text = _clean(value).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _count_type(counter: Any, target_key: str) -> int:
    if not counter:
        return 0
    items = counter.items() if hasattr(counter, "items") else []
    return sum(
        int(count or 0)
        for label, count in items
        if _normalize_outlet_type(label) == target_key
    )


def _joined_unique(rows: Iterable[Any], attribute: str) -> str:
    values = {
        getattr(row, attribute, None)
        for row in rows
        if getattr(row, attribute, None) not in (None, "")
    }
    return ", ".join(_clean(value) for value in sorted(values, key=_numeric_text_sort))


def _joined_locations(rows: Iterable[Any]) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for row in rows:
        value = _clean(getattr(row, "location_text", None))
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return " | ".join(values)


def _product_metric(aggregate: dict[str, Any], product: str) -> dict[str, Any] | None:
    display_name = PRODUCT_DISPLAY_ALIASES.get(product, product)
    candidates: list[str] = [product, display_name]
    candidates.extend(PRODUCT_LOOKUP_ALIASES.get(product, ()))

    # Own-product values take priority for cross-over products such as
    # CB Original NCP, CAMBODIA Sport 300mL and EXPREZ Can 330ml.
    for bucket_name in ("products", "competitors"):
        bucket = aggregate.get(bucket_name) or {}
        for candidate in dict.fromkeys(candidates):
            metric = bucket.get(candidate)
            if isinstance(metric, dict):
                return metric
    return None


def _movement_for_product(aggregate: dict[str, Any], product: str):
    metric = _product_metric(aggregate, product)
    return metric.get("mov") if metric else None


def _availability_for_product(aggregate: dict[str, Any], product: str):
    metric = _product_metric(aggregate, product)
    return (metric.get("availability") or {}) if metric else {}


def _coordinates(submission: Any) -> tuple[float | None, float | None]:
    lat = getattr(submission, "gps_latitude", None)
    lon = getattr(submission, "gps_longitude", None)
    if lat is not None or lon is not None:
        return lat, lon

    gps_text = _clean(getattr(submission, "gps_text", None))
    if not gps_text:
        return None, None

    numbers = re.findall(r"-?\d+(?:\.\d+)?", gps_text)
    if len(numbers) < 2:
        return None, None
    try:
        return float(numbers[0]), float(numbers[1])
    except ValueError:
        return None, None


def _clear_data_rows(ws) -> None:
    if ws.max_row > 1:
        ws.delete_rows(2, ws.max_row - 1)


def _write_headers(ws, headers: list[str]) -> None:
    for column, header in enumerate(headers, start=1):
        ws.cell(1, column).value = header


def _style_header(ws, last_column: int) -> None:
    for cell in ws[1][:last_column]:
        cell.fill = copy(_HEADER_FILL)
        cell.font = copy(_HEADER_FONT)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = copy(_DATA_BORDER)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{ws.cell(1, last_column).column_letter}1"


def _style_data_rows(ws, start_row: int, end_row: int, last_column: int) -> None:
    if end_row < start_row:
        return
    for row in ws.iter_rows(
        min_row=start_row,
        max_row=end_row,
        min_col=1,
        max_col=last_column,
    ):
        for cell in row:
            cell.border = copy(_DATA_BORDER)
            cell.alignment = Alignment(vertical="center", wrap_text=False)


def _write_summary_data(ws, submissions: Iterable[Any]) -> tuple[int, int]:
    """Write one row per Dealer + Product, without scattering by member.

    Dealer-level values repeat for every product row:
    Location_Visit, combined Members, combined Groups, Total_Outlets and total
    outlet-type counts. Product-level WS/DS/WM/TL count only outlets where that
    product is sold, while Mov uses the same final normalized movement used by
    the dealer report.
    """
    groups: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for submission in submissions:
        if _is_summary_submission(submission):
            continue
        key = (
            _clean(getattr(submission, "region", None)).upper(),
            _clean(getattr(submission, "dealer", None)).upper(),
        )
        groups[key].append(submission)

    output_rows: list[list[Any]] = []
    for (region, dealer), rows in sorted(groups.items(), key=_group_sort_key):
        aggregate = aggregate_submissions(rows)
        outlet_counts = aggregate.get("outlet_types") or {}

        common_values = [
            region,
            dealer,
            _joined_locations(rows) or _clean(aggregate.get("location_text")),
            _joined_unique(rows, "member_no"),
            _joined_unique(rows, "group_no"),
            len(rows),
            _count_type(outlet_counts, OUTLET_TYPE_KEYS["Wholesale"]),
            _count_type(outlet_counts, OUTLET_TYPE_KEYS["Drink_Shop"]),
            _count_type(outlet_counts, OUTLET_TYPE_KEYS["Wet_Market"]),
            _count_type(outlet_counts, OUTLET_TYPE_KEYS["Trolley"]),
        ]

        for product in EXPORT_PRODUCTS:
            availability = _availability_for_product(aggregate, product)
            output_rows.append(
                common_values
                + [
                    PRODUCT_DISPLAY_ALIASES.get(product, product),
                    _count_type(availability, OUTLET_TYPE_KEYS["Wholesale"]),
                    _count_type(availability, OUTLET_TYPE_KEYS["Drink_Shop"]),
                    _count_type(availability, OUTLET_TYPE_KEYS["Wet_Market"]),
                    _count_type(availability, OUTLET_TYPE_KEYS["Trolley"]),
                    _movement_for_product(aggregate, product),
                ]
            )

    for row_number, values in enumerate(output_rows, start=2):
        for column_number, value in enumerate(values, start=1):
            ws.cell(row_number, column_number).value = value

    last_row = len(output_rows) + 1
    _style_data_rows(ws, 2, last_row, len(SUMMARY_HEADERS))

    widths = {
        "A": 10,
        "B": 12,
        "C": 30,
        "D": 18,
        "E": 12,
        "F": 14,
        "G": 12,
        "H": 14,
        "I": 14,
        "J": 12,
        "K": 30,
        "L": 9,
        "M": 9,
        "N": 9,
        "O": 9,
        "P": 10,
    }
    for column, width in widths.items():
        ws.column_dimensions[column].width = width

    for column in ("F", "G", "H", "I", "J", "L", "M", "N", "O", "P"):
        for cell in ws[column][1:]:
            cell.number_format = "0"

    return len(groups), len(output_rows)


def _write_location_data(ws, submissions: Iterable[Any], report_date: date) -> int:
    rows = [s for s in submissions if not _is_summary_submission(s)]
    rows.sort(key=_location_sort_key)

    for row_number, submission in enumerate(rows, start=2):
        lat, lon = _coordinates(submission)
        values = [
            getattr(submission, "report_date", None) or report_date,
            _clean(getattr(submission, "region", None)).upper(),
            _clean(getattr(submission, "dealer", None)).upper(),
            lat,
            lon,
            _clean(getattr(submission, "outlet_name", None)),
            _clean(getattr(submission, "outlet_type", None)),
            _clean(getattr(submission, "phone_number", None)),
        ]
        for column_number, value in enumerate(values, start=1):
            ws.cell(row_number, column_number).value = value

        ws.cell(row_number, 1).number_format = "dd/mm/yyyy"
        ws.cell(row_number, 4).number_format = "0.0000000"
        ws.cell(row_number, 5).number_format = "0.0000000"
        ws.cell(row_number, 8).number_format = "@"

    last_row = len(rows) + 1
    _style_data_rows(ws, 2, last_row, len(LOCATION_HEADERS))
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 15
    ws.column_dimensions["E"].width = 15
    ws.column_dimensions["F"].width = 28
    ws.column_dimensions["G"].width = 18
    ws.column_dimensions["H"].width = 24
    return len(rows)


def create_data_export(
    submissions: Iterable[Any],
    report_date: date,
    template_path: Path | str | None = None,
    output_path: Path | str | None = None,
) -> tuple[Path, dict[str, int]]:
    template = Path(template_path or DATA_EXPORT_TEMPLATE)
    if not template.exists():
        raise FileNotFoundError(f"Data export template not found: {template}")

    workbook = load_workbook(template)
    missing_sheets = [
        name for name in (SUMMARY_SHEET, LOCATION_SHEET)
        if name not in workbook.sheetnames
    ]
    if missing_sheets:
        raise ValueError(
            "Data export template is missing sheet(s): " + ", ".join(missing_sheets)
        )

    summary_ws = workbook[SUMMARY_SHEET]
    location_ws = workbook[LOCATION_SHEET]
    _clear_data_rows(summary_ws)
    _clear_data_rows(location_ws)
    _write_headers(summary_ws, SUMMARY_HEADERS)
    _write_headers(location_ws, LOCATION_HEADERS)
    _style_header(summary_ws, len(SUMMARY_HEADERS))
    _style_header(location_ws, len(LOCATION_HEADERS))

    submission_list = list(submissions or [])
    dealer_groups, summary_rows = _write_summary_data(summary_ws, submission_list)
    location_rows = _write_location_data(location_ws, submission_list, report_date)

    destination = Path(output_path) if output_path else (
        settings.export_path / f"Market_Survey_Data_{report_date:%Y-%m-%d}.xlsx"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)

    return destination, {
        "dealer_groups": dealer_groups,
        # Retained for compatibility with older callers.
        "member_groups": dealer_groups,
        "summary_rows": summary_rows,
        "location_rows": location_rows,
        "products": len(EXPORT_PRODUCTS),
    }
