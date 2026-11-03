from __future__ import annotations

from pathlib import Path
import ast
import zipfile

ROOT = Path(__file__).resolve().parent

PY_FILES = [
    ROOT / 'app/reports/aggregator.py',
    ROOT / 'app/reports/excel_report.py',
    ROOT / 'app/db/database.py',
    ROOT / 'app/kobo/sync.py',
    ROOT / 'app/web/router.py',
]

for path in PY_FILES:
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))

agg = (ROOT / 'app/reports/aggregator.py').read_text(encoding='utf-8')
for product in [
    'CB LITE NCP',
    'WURKZ NCP',
    'DAZZ NCP',
    'EXPREZ Can 330ml NCP',
    'IZE COLA 500ml NCP',
    'IZE COLA 500ml ORD',
]:
    assert product in agg, f'Missing aggregator mapping: {product}'

excel = (ROOT / 'app/reports/excel_report.py').read_text(encoding='utf-8')
for mapping in [
    '"CBC 4.4 ORD": "CBC 4.4 NCP"',
    '"CB Original ORD": "CB Original NCP"',
    '"CB BLACK ORD": "CB BLACK NCP"',
    '"IZE COLA 500ml": "IZE COLA 500ml ORD"',
]:
    assert mapping in excel, f'Missing report template alias: {mapping}'
assert 'REPORT_LOGO_WIDTH_PX = 190' in excel
assert 'REPORT_LOGO_HEIGHT_PX = 97' in excel

sync = (ROOT / 'app/kobo/sync.py').read_text(encoding='utf-8')
assert 'gt-ncp-volume-ize500-v2' in sync


def xlsx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        chunks = []
        for name in zf.namelist():
            if name.endswith('.xml'):
                chunks.append(zf.read(name).decode('utf-8', errors='ignore'))
        return '\n'.join(chunks)

form = xlsx_text(ROOT / 'templates/KB_Market_Improvement_XLSForm_GT_HORECA.xlsx')
for field in [
    'fresh_status_wurkz_ncp', 'fresh_volume_wurkz_ncp',
    'fresh_status_dazz_ncp', 'fresh_volume_dazz_ncp',
    'fresh_status_exprez_can_330_ncp', 'fresh_volume_exprez_can_330_ncp',
    'fresh_status_ize_cola_500_ncp', 'fresh_volume_ize_cola_500_ncp',
    'fresh_status_cb_lite_ncp', 'fresh_volume_cb_lite_ncp',
    'fresh_status_ize_cola_500_ord',
]:
    assert field in form, f'Missing Kobo field: {field}'

# The five NCP products must not ask for manual movement/stock/price fields.
for forbidden in [
    'fresh_movement_score_wurkz_ncp', 'fresh_stock_status_wurkz_ncp',
    'fresh_movement_score_dazz_ncp', 'fresh_stock_status_dazz_ncp',
    'fresh_movement_score_exprez_can_330_ncp', 'fresh_stock_status_exprez_can_330_ncp',
    'fresh_movement_score_ize_cola_500_ncp', 'fresh_stock_status_ize_cola_500_ncp',
    'fresh_movement_score_cb_lite_ncp', 'fresh_stock_status_cb_lite_ncp',
]:
    assert forbidden not in form, f'Unexpected Kobo field: {forbidden}'

report = xlsx_text(ROOT / 'templates/template_general.xlsx')
for label in [
    'CB LITE NCP', 'WURKZ NCP', 'DAZZ NCP',
    'EXPREZ Can 330ml NCP', 'IZE COLA 500ml NCP', 'IZE COLA 500ml ORD',
]:
    assert label in report, f'Missing report-template product: {label}'

logo = (ROOT / 'templates/kb_logo.png').read_bytes()
assert logo.startswith(b'\x89PNG\r\n\x1a\n'), 'templates/kb_logo.png is not a PNG'
assert len(logo) > 10_000, 'Logo file looks unexpectedly small'

print('V157 verification OK')
print('  - Python syntax: OK')
print('  - 5 NCP Status -> Volume fields: OK')
print('  - IZE COLA 500ml ORD: OK')
print('  - General report template mappings: OK')
print('  - Chip Mong FoodBev logo: OK')
