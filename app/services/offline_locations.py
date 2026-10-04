"""GPS-to-administrative names using bundled WGS84 commune polygons.

No network calls. KML/workbook wins; GeoJSON fills coverage gaps only.
Ambiguous shared boundaries and conflicting overlaps stay unresolved.
"""
import gzip
import json
import math
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / 'data' / 'boundaries' / 'cambodia_communes.json.gz'


def ring_contains(x, y, ring):
    """Return 0 outside, 1 inside, 2 on the ring (longitude, latitude)."""
    inside = False
    ax, ay = ring[-1][:2]
    for point in ring:
        bx, by = point[:2]
        cross = (x-ax)*(by-ay) - (y-ay)*(bx-ax)
        if abs(cross) <= 1e-12 and min(ax,bx)-1e-12 <= x <= max(ax,bx)+1e-12 and min(ay,by)-1e-12 <= y <= max(ay,by)+1e-12:
            return 2
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
        ax, ay = bx, by
    return int(inside)


def polygon_contains(x, y, rings):
    outer = ring_contains(x, y, rings[0])
    if not outer:
        return False
    for hole in rings[1:]:
        hit = ring_contains(x, y, hole)
        if hit == 1:
            return False
    return True


class BoundaryIndex:
    def __init__(self, records):
        self.cells = {}
        for record in records:
            for polygon in record['polygons']:
                xs, ys = zip(*[p[:2] for p in polygon[0]])
                box = min(xs), min(ys), max(xs), max(ys)
                item = (record['priority'], record['code'], record['names'], box, polygon)
                for ix in range(math.floor(box[0]*4), math.floor(box[2]*4)+1):
                    for iy in range(math.floor(box[1]*4), math.floor(box[3]*4)+1):
                        self.cells.setdefault((ix, iy), []).append(item)

    def resolve_admin(self, latitude, longitude):
        try:
            y, x = float(latitude), float(longitude)
        except (TypeError, ValueError):
            return ['', '', '', '', '', '']
        if not math.isfinite(x) or not math.isfinite(y) or not (-180 <= x <= 180 and -90 <= y <= 90):
            return ['', '', '', '', '', '']
        candidates = self.cells.get((math.floor(x*4), math.floor(y*4)), [])
        for priority in (0, 1):
            matches = {}
            for rank, code, names, (left,bottom,right,top), polygon in candidates:
                if rank == priority and left <= x <= right and bottom <= y <= top and polygon_contains(x, y, polygon):
                    matches[code] = names
            if matches:
                if len(matches) != 1:
                    return ['', '', '', '', '', '']
                code, names = next(iter(matches.items()))
                code = str(code).strip()
                if code.isdigit() and len(code) in (5, 6):
                    code = code.zfill(6)
                    return [*names, code[:2], code[:4], code]
                return [*names, '', '', '']
        return ['', '', '', '', '', '']


    def resolve(self, latitude, longitude):
        """Compatibility API for existing exports: names only."""
        return self.resolve_admin(latitude, longitude)[:3]


@lru_cache(maxsize=1)
def get_boundary_index():
    if not DATA_PATH.is_file():
        raise RuntimeError('Offline boundary file missing. Deploy app/data/boundaries/cambodia_communes.json.gz.')
    with gzip.open(DATA_PATH, 'rt', encoding='utf-8') as stream:
        data = json.load(stream)
    return BoundaryIndex(data['records'])


def resolve_location(latitude, longitude):
    return get_boundary_index().resolve(latitude, longitude)
