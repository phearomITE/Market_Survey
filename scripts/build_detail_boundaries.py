"""Build offline export data from the three user-supplied location files."""
import argparse
import gzip
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from openpyxl import load_workbook


def build(location, kml, geojson, output):
    workbook = load_workbook(location, read_only=True, data_only=True)
    names = {}
    for row in list(workbook.active.values)[1:]:
        if row[0] is None:
            continue
        code = str(int(row[0]))
        value = [str(row[i] or '').strip() for i in (2, 5, 8)]
        if code in names and names[code] != value:
            raise ValueError(f'Conflicting administrative names: {code}')
        if not all(value):
            raise ValueError(f'Incomplete administrative names: {code}')
        names[code] = value
    workbook.close()
    ns = {'k': 'http://www.opengis.net/kml/2.2'}
    records = []
    def ring(text):
        return [[float(v) for v in point.split(',')[:2]] for point in text.split()]
    for place in ET.parse(kml).findall('.//k:Placemark', ns):
        fields = {e.get('name'): e.text for e in place.findall('.//k:SimpleData', ns)}
        code = str(int(float(fields['COM_CODE'])))
        if code not in names:
            raise ValueError(f'KML commune missing from location workbook: {code}')
        polygons = []
        for polygon in place.findall('.//k:Polygon', ns):
            outer = polygon.find('k:outerBoundaryIs/k:LinearRing/k:coordinates', ns)
            holes = polygon.findall('k:innerBoundaryIs/k:LinearRing/k:coordinates', ns)
            polygons.append([ring(outer.text)] + [ring(h.text) for h in holes])
        if not polygons:
            raise ValueError(f'No polygon: {code}')
        records.append({'code': code, 'names': names[code], 'polygons': polygons, 'priority': 0})
    primary = len(records)
    source = json.loads(Path(geojson).read_text(encoding='utf-8'))
    for feature in source['features']:
        p, g = feature['properties'], feature['geometry']
        code = str(int(p['ADM3_PCODE'].removeprefix('KH')))
        polygons = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
        if g['type'] not in ('Polygon', 'MultiPolygon'):
            raise ValueError('Unsupported boundary geometry')
        records.append({'code': code, 'names': names.get(code) or [p['ADM1_EN'], p['ADM2_EN'], p['ADM3_EN']],
                        'polygons': polygons, 'priority': 1})
    result = {'version': 1, 'sources': [Path(p).name for p in (location, kml, geojson)],
              'primary_count': primary, 'fallback_count': len(records)-primary, 'records': records}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output, 'wt', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, separators=(',', ':'))
    print(f'Built {primary} KML communes with workbook names; {len(records)-primary} fallback GeoJSON communes.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('location'); parser.add_argument('kml'); parser.add_argument('geojson'); parser.add_argument('output')
    args = parser.parse_args()
    build(args.location, args.kml, args.geojson, args.output)
