"""Daily five-product NCP stock-volume export: summary and outlet details."""
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import math
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from app.core.config import settings
from app.core.summary_marker import is_summary_name
from app.data.dealers import REGION_DEALERS
from app.reports.aggregator import (
    _metric_by_product, _product_lookup_key, _metric_or_payload_value,
    _payload_of_submission, first_value, product_field,
)
from app.reports.branding import add_summary_logo

VOLUME_PRODUCTS = ('CB LITE NCP', 'WURKZ NCP', 'DAZZ NCP',
                   'EXPREZ Can 500ml NCP', 'IZE COLA 500ml NCP')
NOT_SOLD = {'no_sale', 'not_sale', 'not_sold', 'none', 'អត់មានលក់'}
BLUE, PALE, GREEN = '1F4E78', 'D9EAF7', 'E2F0D9'


def _generated_at():
    try:
        zone = ZoneInfo(settings.app_timezone)
    except ZoneInfoNotFoundError:
        # Windows may not have an IANA timezone database. Cambodia uses UTC+7.
        zone = timezone(timedelta(hours=7))
    return datetime.now(zone)


def parse_volume_args(args):
    parts = [str(p).strip() for p in args]
    if len(parts) == 1:
        scope, day = 'ALL', parts[0]
    elif len(parts) == 2:
        scope, day = parts[0].upper(), parts[1]
    else:
        raise ValueError('Usage: /summary_volume_date [GT|HORECA|ALL] YYYY-MM-DD')
    if scope not in {'GT', 'HORECA', 'ALL'}:
        raise ValueError('Report type must be GT, HORECA or ALL.')
    try:
        parsed = datetime.strptime(day, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError('Date must use YYYY-MM-DD.') from None
    return scope, parsed


def _volume(submission, metrics, product):
    metric = metrics.get(product) or metrics.get(_product_lookup_key(product))
    status = first_value(_payload_of_submission(submission), product_field(product, 'status'))
    if status in (None, ''):
        status = getattr(metric, 'status', None)
    if str(status or '').strip().lower() in NOT_SOLD:
        return None
    raw = _metric_or_payload_value(submission, metric, product, 'volume_ctn', False)
    if raw in (None, ''):
        return None
    try:
        value = Decimal(str(raw).replace(',', '').strip())
    except InvalidOperation:
        raise ValueError(f'Invalid {product} volume for {getattr(submission, "outlet_name", "")}.') from None
    if not value.is_finite() or value < 0:
        raise ValueError(f'{product} volume must be a finite non-negative number.')
    return value


def _coordinates(submission):
    def numeric(value):
        try:
            n = float(value)
            return n if math.isfinite(n) else None
        except (ValueError, TypeError):
            return None
    lat = numeric(getattr(submission, 'gps_latitude', None))
    lon = numeric(getattr(submission, 'gps_longitude', None))
    if lat is None or lon is None:
        parts = str(getattr(submission, 'gps_text', '') or '').split()
        if len(parts) >= 2:
            lat, lon = numeric(parts[0]), numeric(parts[1])
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None
    return lat, lon


def build_volume_rows(submissions, report_date):
    official = {dealer: region for region, dealers in REGION_DEALERS.items() for dealer in dealers}
    details = []
    for submission in submissions:
        if is_summary_name(getattr(submission, 'outlet_name', None)):
            continue
        submitted_day = getattr(submission, 'report_date', None)
        if isinstance(submitted_day, datetime):
            submitted_day = submitted_day.date()
        if str(submitted_day) != report_date.isoformat():
            continue
        dealer = str(getattr(submission, 'dealer', '') or '').strip().upper()
        region = official.get(dealer) or str(getattr(submission, 'region', '') or '').strip().upper()
        metrics = _metric_by_product(list(getattr(submission, 'product_metrics', []) or []))
        quantities = [_volume(submission, metrics, p) for p in VOLUME_PRODUCTS]
        lat, lon = _coordinates(submission)
        link = f'https://www.google.com/maps?q={lat},{lon}' if lat is not None else None
        details.append([report_date, region, dealer, getattr(submission, 'outlet_name', None),
                        str(getattr(submission, 'phone_number', '') or ''), lat, lon, link,
                        *quantities, sum((v for v in quantities if v is not None), Decimal(0))])
    details.sort(key=lambda row: (row[1], row[2], str(row[3] or '')))
    return details


def _text(cell, value):
    # Names and phone numbers are literal data even when beginning with = or +.
    cell.value = value
    if isinstance(value, str):
        cell.data_type = 's'


def _put(sheet, row, values, fill=None, bold=False, color='000000'):
    thin = Side(style='thin', color='D9E2F3')
    for col, value in enumerate(values, 1):
        cell = sheet.cell(row, col)
        if isinstance(value, Decimal):
            value = int(value) if value == value.to_integral_value() else float(value)
        _text(cell, value)
        cell.font = Font(name='Calibri', size=11, bold=bold, color=color)
        cell.alignment = Alignment(vertical='center', horizontal='center' if col != 4 else 'left', wrap_text=True)
        cell.border = Border(bottom=thin)
        if fill:
            cell.fill = PatternFill('solid', fgColor=fill)
    sheet.row_dimensions[row].height = 26


def _base(sheet, title, report_date, scope, widths, note):
    last = get_column_letter(len(widths))
    sheet.merge_cells(f'A1:{last}1')
    _text(sheet['A1'], title)
    sheet['A1'].font = Font(name='Calibri', size=17, bold=True, color='FFFFFF')
    sheet['A1'].fill = PatternFill('solid', fgColor=BLUE)
    sheet['A1'].alignment = Alignment(horizontal='center', vertical='center')
    sheet.row_dimensions[1].height = 32
    sheet.merge_cells(f'C2:{last}2')
    _text(sheet['C2'], f'Report Date: {report_date} | Type: {scope} | Generated: {_generated_at():%d/%m/%Y %H:%M:%S}')
    sheet['C2'].alignment = Alignment(horizontal='center', vertical='center')
    sheet.merge_cells(f'A6:{last}6')
    _text(sheet['A6'], note)
    sheet['A6'].font = Font(name='Calibri', size=10, italic=True, color='666666')
    sheet['A6'].alignment = Alignment(wrap_text=True, vertical='center')
    sheet.row_dimensions[6].height = 30
    for col, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(col)].width = width
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = 'D8'
    sheet.print_title_rows = '1:7'
    sheet.page_setup.orientation = 'landscape'
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    add_summary_logo(sheet)


def create_volume_summary(submissions, report_date, output_path=None, scope='ALL'):
    details = build_volume_rows(submissions, report_date)
    workbook = Workbook()
    summary = workbook.active
    summary.title = 'Summary_Volume'
    detail = workbook.create_sheet('Detail_Volume')
    _base(summary, 'CMFB Market Survey - NCP Volume by Region & Dealer', report_date, scope,
          [12, 17, 17, 22, 22, 22, 29, 27, 22],
          'Unit: cartons (ctn). One detail row = one outlet visit. Regional and grand totals sum detail volumes; final-summary control rows excluded.')
    totals = defaultdict(lambda: [0, *[Decimal(0) for _ in VOLUME_PRODUCTS]])
    for row in details:
        key = (row[1], row[2])
        totals[key][0] += 1
        for i, value in enumerate(row[8:13], 1):
            totals[key][i] += value or Decimal(0)
    headers = ['Region', 'Dealer', 'Outlet Visits', *VOLUME_PRODUCTS, 'Total Volume (ctn)']
    _put(summary, 4, ['Regions', 'Dealers', 'Dealers Visited', 'Outlet Visits', 'Total Volume (ctn)'], bold=True)
    _put(summary, 5, [len({r for r,d in totals}), len({d for ds in REGION_DEALERS.values() for d in ds}),
                       len({d for r,d in totals}), len(details), sum((r[13] for r in details), Decimal(0))])
    _put(summary, 7, headers, BLUE, True, 'FFFFFF')
    rownum = 8
    region_order = list(REGION_DEALERS) + sorted({r for r,d in totals} - set(REGION_DEALERS))
    for region in region_order:
        dealers = list(REGION_DEALERS.get(region, []))
        dealers += sorted(d for r,d in totals if r == region and d not in dealers)
        regional = [0, *[Decimal(0) for _ in VOLUME_PRODUCTS]]
        for dealer in dealers:
            values = totals[(region, dealer)]
            _put(summary, rownum, [region, dealer, *values, sum(values[1:], Decimal(0))], GREEN if values[0] else 'F8FBFD')
            for i, value in enumerate(values):
                regional[i] += value
            rownum += 1
        _put(summary, rownum, [region, 'Region Total', *regional, sum(regional[1:], Decimal(0))], PALE, True, 'FF0000')
        rownum += 1
    grand = [len(details), *[sum((row[i] or Decimal(0) for row in details), Decimal(0)) for i in range(8,13)]]
    _put(summary, rownum, ['ALL', 'Grand Total', *grand, sum(grand[1:], Decimal(0))], BLUE, True, 'FFFFFF')
    for row in summary.iter_rows(min_row=8, min_col=4, max_col=9):
        for cell in row:
            cell.number_format = '#,##0' if isinstance(cell.value, int) else '#,##0.###'
    summary.print_area = f'A1:I{rownum}'
    _base(detail, 'CMFB Market Survey - NCP Volume Outlet Detail', report_date, scope,
          [15, 12, 14, 34, 22, 17, 17, 18, 22, 22, 22, 29, 27, 22],
          'Unit: cartons (ctn). Blank volume = no recorded applicable volume; 0 = an explicit zero. Open Map uses the submitted GPS coordinates.')
    _put(detail, 4, ['Outlet Visits', 'Total Volume (ctn)'], bold=True)
    _put(detail, 5, [len(details), sum((row[13] for row in details), Decimal(0))])
    _put(detail, 7, ['Date', 'Region', 'Dealer', 'Outlet Name', 'Phone Number', 'Lat', 'Lon', 'Open Map',
                   *VOLUME_PRODUCTS, 'Total Volume (ctn)'], BLUE, True, 'FFFFFF')
    detail.row_dimensions[7].height = summary.row_dimensions[7].height = 44
    for index, values in enumerate(details, 8):
        _put(detail, index, values, 'F0F6FB' if index % 2 == 0 else None)
        detail.cell(index, 1).number_format = 'yyyy-mm-dd'
        detail.cell(index, 5).number_format = '@'
        for col in (6, 7):
            detail.cell(index, col).number_format = '0.000000'
        if values[7]:
            detail.cell(index, 8).value = 'Open Map'
            detail.cell(index, 8).hyperlink = values[7]
            detail.cell(index, 8).font = Font(name='Calibri', color='0563C1', underline='single')
        for col in range(9,15):
            cell = detail.cell(index, col)
            cell.number_format = '#,##0' if isinstance(cell.value, int) else '#,##0.###'
    detail.auto_filter.ref = f'A7:N{max(7, detail.max_row)}'
    detail.print_area = f'A1:N{max(8, detail.max_row)}'
    destination = Path(output_path) if output_path else settings.export_path / f'CMFB_Summary_Volume_{scope}_{report_date}.xlsx'
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    return destination, len(details)
