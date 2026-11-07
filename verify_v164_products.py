"""Offline tests for product corrections, date defaults, comparisons and PDF route."""
from pathlib import Path
from types import SimpleNamespace
from datetime import date
import ast, asyncio, runpy, tempfile, re, zipfile
from openpyxl import load_workbook
ROOT=Path(__file__).resolve().parent
base=runpy.run_path(str(ROOT/'verify_v161_volume_summary.py'))
agg=base['aggregator'];parser=base['parser'];sync=base['sync_ns'];day=date(2026,11,7)
renames={'CBC 4.4 NCP':'CBC 4.4 ORD','CB Original NCP':'CB Original ORD','GB Original NCP':'GB Original ORD','CB BLACK NCP':'CB BLACK ORD','Hanuman Black NCP':'Hanuman Black ORD'}
removed={'comp_krud_ncp_group','comp_gb_snow_ncp_group','comp_hanuman_lite_ncp_group','comp_krud_lite_ncp_group','comp_greet_lite_ncp_group'}
for old,new in renames.items():
    assert agg['_canonical_product_name'](old)==new
    metric=SimpleNamespace(product_name=old,movement_score=7)
    assert agg['_metric_by_product']([metric])[new] is metric
assert ['IZE COLA 500ml ORD','Coca 650ml'] in agg['OFFTAKE_COMPARE_GROUPS']
assert agg['COMPETITOR_CODES']['Coca 650ml'][0]=='coca_650'
for path in (ROOT/'templates').glob('*XLSForm*.xlsx'):
    w=load_workbook(path);s=w['survey'];header=[c.value for c in s[1]]
    rows=[dict(zip(header,r)) for r in list(s.values)[1:]]
    names=[r['name'] for r in rows if r['name']]
    assert len(names)==len(set(names)) and not set(names)&removed
    stack=[];choices={r[0] for r in list(w['choices'].values)[1:]}
    for r in rows:
        kind=r['type']
        if kind in {'begin_group','begin_repeat'}:stack.append(kind)
        elif kind in {'end_group','end_repeat'}:assert stack.pop()==kind.replace('end','begin')
        if str(kind).startswith(('select_one ','select_multiple ')):assert kind.split()[1] in choices
        for column in ['relevant','constraint','calculation']:
            for ref in re.findall(r'\$\{([^}]+)\}',str(r.get(column) or '')):assert ref in names,(path,ref)
        assert not any(old in str(r.get('label') or '') for old in renames)
        assert not any(retired in str(r.get('label') or '') for retired in ['Krud NCP','GB SNOW NCP','Hanuman LITE NCP','Krud LITE NCP','Greet LITE NCP'])
    assert not stack
    dt=next(r for r in rows if r['name']=='report_date');assert dt['default']=='today()' and dt['required']=='yes'
    cocoa=next(r for r in rows if r['name']=='comp_status_coca_650');assert cocoa['required']=='yes'
    movement=next(r for r in rows if r['name']=='comp_movement_score_coca_650');assert movement['required']=='yes'
    assert "'sale'" in movement['relevant'] and "'fast_sale'" in movement['relevant']
    for code in ['cb_lite_ncp','wurkz_ncp','dazz_ncp','exprez_can_330_ncp','ize_cola_500_ncp']:
        for prefix in ['fresh_status_','fresh_volume_']:
            assert next(r for r in rows if r['name']==prefix+code)['required']=='yes'

def parse_visit(own_score,comp_score,own_status='sale',comp_status='sale'):
    raw={'_id':'synthetic','outlet_info':{'report_date':day.isoformat(),'region':'r5','dealer':'krg7','outlet_name':'SYNTHETIC TEST OUTLET','outlet_type':'drink_shop','final_summary_report_type':'gt','group_no':2,'member_no':6},
        'product_check_by_type':{'fresh_ize_cola_500_ord_group':{'fresh_status_ize_cola_500_ord':own_status,'fresh_movement_score_ize_cola_500_ord':own_score},
        'comp_coca_650_group':{'comp_status_coca_650':comp_status,'comp_movement_score_coca_650':comp_score},
        'fresh_cbc44_ncp_group':{'fresh_status_cbc44_ncp':'sale','fresh_movement_score_cbc44_ncp':7}}}
    data=parser['normalize_submission'](raw);flat=data.pop('_flat')
    submission=SimpleNamespace(**data)
    submission.product_metrics=[SimpleNamespace(**v) for v in sync['_product_metrics_from_flat'](flat,agg['OWN_PRODUCTS'])]
    submission.competitor_metrics=[SimpleNamespace(**v) for v in sync['_competitor_metrics_from_flat'](flat,agg['COMPETITOR_PRODUCTS'])]
    submission.ring_pull_metrics=[]
    return submission
cases=[(8,4,'sale','sale',10,5),(4,8,'sale','sale',5,10),(8,None,'sale','no_sale',10,0),(None,None,'no_sale','no_sale',0,0),(5,5,'sale','sale',10,9)]
for a,b,sa,sb,expect_own,expect_comp in cases:
    result=agg['aggregate_submissions']([parse_visit(a,b,sa,sb)],wide_map={})
    assert result['products']['IZE COLA 500ml ORD']['mov']==expect_own,result['products']['IZE COLA 500ml ORD']
    assert result['competitors']['Coca 650ml']['mov']==expect_comp,result['competitors']['Coca 650ml']
# Use the actual workbook writer to verify the printed comparison row.
guidance=base['load']('app/reports/guidance.py')
settings=SimpleNamespace(template_file=ROOT/'templates/template_general.xlsx',horeca_template_file=ROOT/'templates/template_horeca_products.xlsx')
writer=base['load']('app/reports/excel_report.py',{**agg,**guidance,'settings':settings,'ALL_DEALERS':['KRG7']})
result=agg['aggregate_submissions']([parse_visit(8,4)],wide_map={});result['report_type']='GT'
with tempfile.TemporaryDirectory() as temp:
    out=writer['create_report_workbook']([result],Path(temp)/'report.xlsx')
    ws=load_workbook(out).active
    ownrow=next(r for r in range(32,48) if ws.cell(r,2).value=='IZE COLA 500ml ORD')
    assert ws.cell(ownrow,3).value==10 and ws.cell(ownrow,8).value=='Coca 650ml' and ws.cell(ownrow,9).value==5
    assert not any('EXPREZ Can 330ml' in str(c.value) for row in ws for c in row)
    if '--sample' in __import__('sys').argv:
        import shutil
        dest=ROOT/'exports/V164_SYNTHETIC_REPORT.xlsx';dest.parent.mkdir(exist_ok=True);shutil.copyfile(out,dest)
# PDF handler runs through the actual service signature and upload path.
tree=ast.parse((ROOT/'app/bot/handlers.py').read_text(encoding='utf-8'))
fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='report_pdf_cmd')
async def test_pdf():
    with tempfile.TemporaryDirectory() as temp:
        pdf=Path(temp)/'test.pdf';pdf.write_bytes(b'%PDF-1.4\n')
        messages=[];uploads=[];calls=[]
        class Message:
            async def reply_text(self,text):messages.append(text);return self
            async def edit_text(self,text):messages.append(text)
            async def reply_document(self,**kw):uploads.append(kw)
        def generate(dealer,day,scope):calls.append((dealer,day,scope));return Path(temp)/'test.xlsx','Generated'
        async def fast(function,*args,**kwargs):return function(*args)
        ns={'Update':object,'ContextTypes':SimpleNamespace(DEFAULT_TYPE=object),'parse_report_command_args':lambda args:('KRG7','2026-11-07','GT'),
            '_run_fast':fast,'generate_dealer_report':generate,'excel_to_pdf':lambda path:pdf,'InputFile':lambda f,filename:filename}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'PDF handler','exec'),ns)
        await ns['report_pdf_cmd'](SimpleNamespace(effective_message=Message()),SimpleNamespace(args=['KRG7','GT','2026-11-07']))
        assert calls==[('KRG7','2026-11-07','GT')] and len(uploads)==1
        ns['excel_to_pdf']=lambda path:None;uploads.clear()
        await ns['report_pdf_cmd'](SimpleNamespace(effective_message=Message()),SimpleNamespace(args=['KRG7','GT','2026-11-07']))
        assert not uploads and 'conversion unavailable' in messages[-1]
asyncio.run(test_pdf())
for p in (ROOT/'app').rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('V164 OK: 5 ORD renames, 5 groups removed, today() defaults, legacy data, IZE/Coca comparisons (5 scenarios), generated cells and PDF handler.')
