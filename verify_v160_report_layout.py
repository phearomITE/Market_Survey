"""Offline regression checks using production report functions (no DB/network).
Only infrastructure imports are omitted; aggregation and writer code run intact.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from datetime import date
import tempfile
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent

def load_offline(relative, initial=None):
    path = ROOT / relative
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.ImportFrom) and
        (node.module or '').startswith(('app.', 'sqlalchemy'))
    )]
    namespace = {'__name__': 'offline_check', '__file__': str(path), **(initial or {})}
    exec(compile(tree, str(path), 'exec'), namespace)
    return namespace

markers = load_offline('app/core/summary_marker.py')
aggmod = load_offline('app/reports/aggregator.py', markers)
guidance = load_offline('app/reports/guidance.py')
settings = SimpleNamespace(template_file=ROOT/'templates/template_general.xlsx',
    horeca_template_file=ROOT/'templates/template_horeca_products.xlsx')
writer = load_offline('app/reports/excel_report.py', {**aggmod, **guidance,
    'settings': settings, 'ALL_DEALERS': ['CA1']})

sheet = load_workbook(settings.template_file).active
layout = writer['_layout_rows'](sheet, {})
assert layout['freshness_end'] == 29, layout
assert layout['movement_header'] == 31, layout
assert layout['movement_start'] == 32 and layout['movement_end'] == 47, layout
assert layout['summary_header'] == 49 and layout['issue_start'] == 50, layout
# English and translated summary headings resolve to the same row.
for heading in ['Key Issues', 'បញ្ហាទីផ្សារ']:
    sheet['I49'] = heading
    assert writer['_find_summary_header_row'](sheet) == 49
# Older HORECA templates retain their own dynamic layout.
horeca = load_workbook(settings.horeca_template_file).active
hl = writer['_layout_rows'](horeca, {'report_type':'HORECA'})
assert hl['movement_header'] == writer['_find_movement_header_row'](horeca)

keys = ['cb_lite_ncp','wurkz_ncp','dazz_ncp','exprez_can_330_ncp','ize_cola_500_ncp']
labels = ['CB LITE NCP','WURKZ NCP','DAZZ NCP','EXPREZ Can 500ml NCP','IZE COLA 500ml NCP']
payload = {f'product_check_by_type/fresh_{key}_group/fresh_volume_{key}': i+2 for i,key in enumerate(keys)}
payload.update({f'product_check_by_type/fresh_{key}_group/fresh_status_{key}': 'sale' for key in keys})
payload.update({'fresh_status_cb_lite_ord':'sale','fresh_movement_score_cb_lite_ord':8,
    'fresh_bbe_cb_lite_ord':'05.2027'})
def submission(name, raw):
    return SimpleNamespace(dealer='CA1',region='R1',report_date=date(2026,10,31),
        outlet_name=name,outlet_type='Wholesale',group_no=2,member_no=3,
        location_text='Test location',product_metrics=[],competitor_metrics=[],
        ring_pull_metrics=[],raw_payload=raw)
visit = submission('TEST OUTLET (synthetic)', payload)
summary = submission('បូកសរុបរួម', {})
agg = aggmod['aggregate_submissions']([visit,summary], wide_map={})
assert agg['total_outlets']==1 and agg['summary_control_count']==1
for i,label in enumerate(labels):assert agg['products'][label]['volume']==i+2, (label,agg['products'][label])
agg['report_type']='GT';agg['key_issues']=['Synthetic issue'];agg['suggestions']=['Synthetic action']
# The generator reads the unchanged supplied template and writes only report data.
with tempfile.TemporaryDirectory() as temporary:
    output=Path(temporary)/'report.xlsx'
    writer['create_report_workbook']([agg],output)
    result=load_workbook(output).active
    for row,label in enumerate(labels,25):
        assert result.cell(row,2).value==label
        assert result.cell(row,26).value==row-23
    assert result['B26'].value=='WURKZ NCP'
    assert result['C31'].value=='Mov'
    assert result['B47'].value=='CAMBODIA WATER 1500mL'
    assert result['A49'].value=="Don't"
    assert result['I50'].value=='1. Synthetic issue'
    assert result['S50'].value=='1. Synthetic action'
    assert result['W4'].value=='Total outlet Visit : 1'
    assert result['C32'].value is not None
    if '--sample' in __import__('sys').argv:
        import shutil
        dest=ROOT/'exports/V160_SYNTHETIC_CA1.xlsx'
        shutil.copyfile(output,dest)
        print('Synthetic QA example:',dest)
# Run the actual service function with isolated I/O seams.
service_tree=ast.parse((ROOT/'app/services/report_service.py').read_text(encoding='utf-8'))
function=next(n for n in service_tree.body if isinstance(n,ast.FunctionDef) and n.name=='generate_dealer_report')
ns={'ReportType':str,'normalize_report_type':str.upper,'parse_report_date':date.fromisoformat,
    'fetch_report_submissions_fast':lambda *a:[summary], '_filter_by_report_type':lambda rows,t:rows,
    'aggregate_submissions':aggmod['aggregate_submissions'],
    'create_single_report':lambda a: (_ for _ in ()).throw(AssertionError('must not write empty report'))}
exec(compile(ast.Module(body=[function],type_ignores=[]),'<service regression>','exec'),ns)
path,message=ns['generate_dealer_report']('CA1','2026-10-31','GT')
assert path is None and 'final-summary' in message
print('V160 OK: bilingual layout, 23 freshness rows, 16 movement rows, summary isolation, five NCP volume mappings, summary-only guard.')
