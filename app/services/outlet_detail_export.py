"""One row per genuine outlet visit, with GPS-derived administrative names."""
import json
import math
import os
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from app.core.summary_marker import is_summary_name

HEADERS = ['Date', 'Region', 'Dealer', 'Outlet Name', 'Outlet Type',
           'Phone Number Outlet', 'Latitude', 'Longitude', 'Province', 'District', 'Commune']


def coordinates(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        if lat == 0 and lon == 0:
            return None
        return lat, lon
    except (TypeError, ValueError):
        return None


def administrative_names(payload):
    # Use explicit administrative levels, never nearby POIs as communes.
    levels = {int(x['adminLevel']): x.get('name', '')
              for x in payload.get('localityInfo', {}).get('administrative', [])
              if str(x.get('adminLevel', '')).isdigit()}
    return [levels.get(4) or payload.get('principalSubdivision', ''),
            levels.get(6, ''), levels.get(8, '')]


def resolve_location(lat, lon):
    key = os.getenv('BIGDATACLOUD_API_KEY', '').strip()
    if not key:
        raise ValueError('Set BIGDATACLOUD_API_KEY on Railway for GPS location lookup.')
    query = urlencode({'latitude':lat, 'longitude':lon, 'localityLanguage':'en', 'key':key})
    base = 'https://api-bdc.net/data/reverse-geocode'
    req = Request(base + '?' + query, headers={'Accept':'application/json'})
    with urlopen(req, timeout=10) as response:
        return administrative_names(json.load(response))


def create_detail_export(rows, day, output_dir, resolver=resolve_location):
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / 'outlet_detail_geocode_cache.json'
    try:
        cache = json.loads(cache_path.read_text(encoding='utf8'))
    except (OSError, ValueError):
        cache = {}
    wb = Workbook(); ws = wb.active; ws.title = 'Outlet Detail'; ws.append(HEADERS)
    count = unresolved = 0
    attempted = {}
    for row in rows:
        if is_summary_name(getattr(row, 'outlet_name', None)):
            continue
        pin = coordinates(getattr(row, 'gps_latitude', None), getattr(row, 'gps_longitude', None))
        names = ['', '', '']
        if pin:
            key = f'{pin[0]:.6f},{pin[1]:.6f}'
            names = cache.get(key) or attempted.get(key)
            if names is None:
                try:
                    names = list(resolver(*pin))
                except Exception:
                    names = ['', '', '']
                attempted[key] = names
                if all(names):
                    cache[key] = names
                if resolver is resolve_location:
                    time.sleep(1)
        unresolved += int(not all(names))
        values = [day, getattr(row,'region',None), getattr(row,'dealer',None),
                  getattr(row,'outlet_name',None), getattr(row,'outlet_type',None),
                  str(getattr(row,'phone_number',None) or ''),
                  pin[0] if pin else None, pin[1] if pin else None, *names]
        ws.append(values); count += 1
        for cell in ws[ws.max_row]:
            if isinstance(cell.value,str):
                cell.data_type = 's'  # Keep phone numbers and untrusted text literal.
        ws.cell(ws.max_row,1).number_format = 'yyyy-mm-dd'
        ws.cell(ws.max_row,6).number_format = '@'
    for c in ws[1]:
        c.font=Font(bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='174A73')
    from openpyxl.utils import get_column_letter
    for i,width in enumerate([14,12,12,32,22,24,16,16,24,24,24],1):
        ws.column_dimensions[get_column_letter(i)].width=width
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    path=output_dir / f'Export_detail_{day}.xlsx'
    wb.save(path)
    temp=cache_path.with_suffix('.tmp');temp.write_text(json.dumps(cache,ensure_ascii=False),encoding='utf8');temp.replace(cache_path)
    return path,count,unresolved


def generate_outlet_detail_export(day):
    if not os.getenv('BIGDATACLOUD_API_KEY', '').strip():
        raise ValueError('Set BIGDATACLOUD_API_KEY on Railway for Province/District/Commune lookup.')
    from app.core.config import settings
    from app.kobo.sync import fetch_report_submissions_fast
    rows=fetch_report_submissions_fast(None,day,metadata_only=True)
    if not rows:
        raise ValueError(f'No submissions found for {day}')
    return create_detail_export(rows,day,settings.export_path)
