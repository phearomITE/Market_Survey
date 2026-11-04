"""Offline regression checks: real report code with infrastructure imports omitted.
Requires only existing openpyxl/Pillow; no network, Telegram or DB credentials.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from datetime import date
from decimal import Decimal
import tempfile
import zipfile
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parent

def load(relative, initial=None):
    path=ROOT/relative
    tree=ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    tree.body=[n for n in tree.body if not(isinstance(n,ast.ImportFrom) and (n.module or '').startswith(('app.','sqlalchemy')))]
    ns={'__name__':'offline_check','__file__':str(path),**(initial or {})}
    exec(compile(tree,str(path),'exec'),ns)
    return ns

settings=SimpleNamespace(template_file=ROOT/'templates/template_general.xlsx',
    export_path=ROOT/'exports',app_timezone='Asia/Phnom_Penh')
markers=load('app/core/summary_marker.py')
dealers=load('app/data/dealers.py')
aggregator=load('app/reports/aggregator.py',markers)
branding=load('app/reports/branding.py',{'settings':settings})
volume=load('app/reports/volume_summary.py',{**aggregator,**markers,**dealers,**branding,'settings':settings})
PRODUCTS=volume['VOLUME_PRODUCTS']; day=date(2026,11,4)
def visit(dealer, values, *, name='Synthetic Outlet', scope='GT', phone='012345678', lat=11.5, lon=104.9):
    metrics=[SimpleNamespace(product_name=p,volume_ctn=v,status='sale') for p,v in zip(PRODUCTS, values)]
    return SimpleNamespace(dealer=dealer,region='R1' if dealer=='CA1' else 'R2',report_date=day,
        outlet_name=name,report_type=scope,phone_number=phone,gps_latitude=lat,gps_longitude=lon,
        gps_text=None,product_metrics=metrics)
rows=[visit('CA1',[10,2.5,0,None,1]),visit('CA1',[3,0.25,4,5,6],scope='HORECA'),
      visit('KDL1',[1,None,2,0,3],name='=Literal outlet'),
      visit('CA1',[999]*5,name='បូកសរុបរួម')]
# Stale hidden quantity must not count when not sold.
rows[2].product_metrics[0].status='no_sale'
rows[2].gps_latitude=None;rows[2].gps_longitude=None
zero=visit('CA1',[0]*5,name='Zero coordinate',lat=0,lon=0)
rows.append(zero)
expected=[Decimal('13'),Decimal('2.75'),Decimal('6'),Decimal('5'),Decimal('10')]
records=volume['build_volume_rows'](rows,day)
assert len(records)==4
assert [sum((r[i] or Decimal(0) for r in records),Decimal(0)) for i in range(8,13)]==expected
assert volume['_coordinates'](zero)==(0,0)
assert volume['parse_volume_args'](['2026-11-04'])==('ALL',day)
assert volume['parse_volume_args'](['gt','2026-11-04'])==('GT',day)
for args in [[],['bad'],['GT','2026-02-30'],['BAD','2026-11-04']]:
    try:volume['parse_volume_args'](args)
    except ValueError:pass
    else:raise AssertionError(args)
# Service date/type selection runs the actual function; external I/O is stubbed.
service_tree=ast.parse((ROOT/'app/services/report_service.py').read_text())
fn=next(n for n in service_tree.body if isinstance(n,ast.FunctionDef) and n.name=='generate_summary_volume_date')
fn.body=[n for n in fn.body if not isinstance(n,ast.ImportFrom)]
captured=[]
def fake_create(records, day, scope):
    captured.append((list(records),day,scope));return Path('test.xlsx'),len(records)
ns={'parse_volume_args':volume['parse_volume_args'],'create_volume_summary':fake_create,
    'fetch_report_submissions_fast':lambda *args:rows,
    '_filter_by_report_type':lambda records,scope:[s for s in records if s.report_type==scope]}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'service','exec'),ns)
ns['generate_summary_volume_date']('2026-11-04','GT');assert all(r.report_type=='GT' for r in captured[-1][0])
ns['generate_summary_volume_date']('2026-11-04','ALL');assert len(captured[-1][0])==5

with tempfile.TemporaryDirectory() as temp:
    path,count=volume['create_volume_summary'](rows,day,Path(temp)/'volume.xlsx')
    assert count==4
    w=load_workbook(path);assert w.sheetnames==['Summary_Volume','Detail_Volume']
    s,d=w.worksheets;assert len(s._images)==len(d._images)==1
    grand=next(r for r in s.values if r[1]=='Grand Total')
    assert list(map(str,grand[3:8]))==list(map(str,[13,2.75,6,5,10]))
    assert grand[8]==36.75
    official=[r for r in list(s.values)[7:] if r[1] not in ('Region Total','Grand Total')]
    assert len(official)==65
    detail=list(d.values)[7:];assert len(detail)==4
    literal=next(r for r in d.iter_rows(min_row=8) if r[3].value=='=Literal outlet')
    assert literal[3].data_type=='s' and literal[4].value=='012345678'
    assert literal[7].hyperlink is None
    coords=next(r for r in d.iter_rows(min_row=8) if r[3].value=='Zero coordinate')
    assert coords[7].hyperlink.target.endswith('0.0,0.0')
    assert [sum(float(r[i] or 0) for r in detail) for i in range(8,13)]==[float(v) for v in expected]
    if '--sample' in __import__('sys').argv:
        import shutil
        dest=ROOT/'exports/V161_SYNTHETIC_VOLUME.xlsx';dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(path,dest);print('Synthetic QA example:',dest)
    # Empty report still has both sheets, all 65 dealers and a zero grand total.
    empty,_=volume['create_volume_summary']([],day,Path(temp)/'empty.xlsx')
    ew=load_workbook(empty);assert len(ew.sheetnames)==2
    assert next(r for r in ew.worksheets[0].values if r[1]=='Grand Total')[8]==0
# Exercise raw nested Kobo payloads through the real fast parser for both types.
parser=load('app/kobo/parser.py')
sync_tree=ast.parse((ROOT/'app/kobo/sync.py').read_text())
wanted={'_status_to_mov','_product_metrics_from_flat','_competitor_metrics_from_flat','_build_report_submissions'}
sync_nodes=[n for n in sync_tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
class FakeClient:
    def fetch_submissions(self, **kwargs):
        return raw_records
settings.kobo_fetch_deadline_seconds=30;settings.kobo_request_timeout_seconds=12
sync_ns={**aggregator,**parser,'settings':settings,'SimpleNamespace':SimpleNamespace,
         'KoboClient':FakeClient,'KoboSubmission':SimpleNamespace,
         '_ring_pull_metrics_from_flat':lambda f:[]}
exec(compile(ast.Module(body=sync_nodes,type_ignores=[]),'sync parser regression','exec'),sync_ns)
raw_records=[]
for report_type in ['gt','horeca']:
    raw_records.append({'_id':report_type,'outlet_info':{'report_date':day.isoformat(),
        'region':'r1','dealer':'ca1','outlet_name':'Parser test','final_summary_report_type':report_type,
        'phone_number':'012345678','gps_latitude':'11.5','gps_longitude':'104.9'},
        'product_check_by_type':{'fresh_cb_lite_ncp_group':{
            'fresh_status_cb_lite_ncp':'sale','fresh_volume_cb_lite_ncp':'12.75'}}})
parsed=sync_ns['_build_report_submissions'](dealer=None,report_date=day,wanted=set(),summary_only=False,metadata_only=False)
parsed_details=volume['build_volume_rows'](parsed,day)
assert len(parsed_details)==2 and all(r[8]==Decimal('12.75') for r in parsed_details)
# Existing /summary workbook gets a logo without overlaying its detail rows.
summarymod=load('app/reports/summary_report.py',{**aggregator,**dealers,**branding,'settings':settings})
# Boundaries are an independent service, unused for this empty-report layout test.
class StripInfrastructure(ast.NodeTransformer):
    def visit_ImportFrom(self,node):
        return None if (node.module or '').startswith(('app.','sqlalchemy')) else node
summary_tree=StripInfrastructure().visit(ast.parse((ROOT/'app/reports/summary_report.py').read_text()))
summarymod['get_boundary_index']=lambda:None
exec(compile(summary_tree,'summary layout regression','exec'),summarymod)
with tempfile.TemporaryDirectory() as tmp:
    out=summarymod['create_summary_report']([],day,Path(tmp)/'summary.xlsx',submissions=[])
    summarybook=load_workbook(out)
    assert len(summarybook['Summary_beer']._images)==1
    assert 'CMFB' in summarybook['Summary_beer']['A1'].value
    assert len(summarybook['Location_no_CB_LITE']._images)==0
    assert summarybook['Location_no_CB_LITE']['A1'].value=='Date'
    if '--sample' in __import__('sys').argv:
        import shutil
        shutil.copyfile(out,ROOT/'exports/V161_SYNTHETIC_SUMMARY.xlsx')

# Registration and async handler: parse/import wiring validated independently.
handlers=(ROOT/'app/bot/handlers.py').read_text();run=(ROOT/'app/bot/run_bot.py').read_text()
assert 'async def summary_volume_date_cmd(' in handlers
assert 'CommandHandler("summary_volume_date", summary_volume_date_cmd)' in run
for p in (ROOT/'app').rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
# Branded XLSForms preserve identity, question names, required/relevance logic.
for p in ROOT.glob('templates/*XLSForm*.xlsx'):
    form=load_workbook(p);assert 'CMFB' in str(form['settings'].cell(2,1).value)
    data=list(form['survey'].values)
    for key in ['cb_lite_ncp','wurkz_ncp','dazz_ncp','exprez_can_330_ncp','ize_cola_500_ncp']:
        for prefix in ['fresh_status_','fresh_volume_']:
            r=next(r for r in data if r[1]==prefix+key);assert r[3]=='yes'
print('V161 OK: command routing/date filters, 65 dealers, subtotal reconciliation, 5 volumes, detail/map/phone fields, blank/zero/hidden/summary exclusion, 2 logos, CMFB forms.')
