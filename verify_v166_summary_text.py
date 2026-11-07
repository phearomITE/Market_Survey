"""Verify submitted Khmer issue/solution text reaches the actual report cells."""
import runpy,tempfile
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone,date
from openpyxl import load_workbook
ROOT=Path(__file__).resolve().parent
base=runpy.run_path(str(ROOT/'verify_v161_volume_summary.py'))
parser=base['parser'];agg=base['aggregator'];day=date(2026,10,31)
issue='ម៉ូយខ្វះស្តុកផលិតផល'
solution='ត្រូវបន្ថែមស្តុកជូនម៉ូយ'
html_group='<span style="color:red">3. FINAL KEY ISSUES & INITIATIVE IDEA / SUGGESTION</span>'
raw={'_id':'control','_submission_time':'2026-10-31T12:00:00Z','outlet_info':{'report_date':'2026-10-31','region':'r8','dealer':'smr5','outlet_name':'សរុបរួម,','final_summary_report_type':'gt'},
    html_group+' / Key Issues Detail':issue,
    html_group+' / Initiative Idea / Suggestion':solution}
parsed=parser['normalize_submission'](raw)
assert parsed['key_issue_text']==issue and parsed['suggestion_text']==solution,parsed
# Actual nested machine keys and Khmer-labelled exports work too.
for fields in [
    {'key_issues_suggestion_group':{'key_issues_detail':issue,'initiative_idea_suggestion':solution}},
    {'បញ្ហាទីផ្សារ':issue,'បញ្ហាត្រូវដោះស្រាយ':solution},
    {html_group+' / Key Issues Detail':issue,'legacy/key_issues_detail':' ',html_group+' / Initiative Idea / Suggestion':solution,'legacy/suggestion':' '},
]:
    row={**raw};row.pop(html_group+' / Key Issues Detail');row.pop(html_group+' / Initiative Idea / Suggestion');row.update(fields)
    value=parser['normalize_submission'](row);assert value['key_issue_text']==issue and value['suggestion_text']==solution
# A note or group heading is never accepted as an answer.
blank=parser['normalize_submission']({'_id':'note','key_issues_suggestion_group':{'final_key_issues_note':'INSTRUCTION TEXT ONLY'}})
assert blank['key_issue_text'] is None and blank['suggestion_text'] is None
control=SimpleNamespace(**{k:v for k,v in parsed.items() if k!='_flat'})
control.product_metrics=[];control.competitor_metrics=[];control.ring_pull_metrics=[]
visit=SimpleNamespace(dealer='SMR5',region='R8',report_date=day,outlet_name='Test outlet',outlet_type='Drink Shop',
    submission_time=datetime(2026,10,31,13),key_issue_text='Newer outlet note',suggestion_text='Newer outlet action',
    product_metrics=[],competitor_metrics=[],ring_pull_metrics=[],location_text='Test',group_no=2,member_no=6)
new_blank=SimpleNamespace(outlet_name='សរុបរួម,',submission_time=datetime(2026,10,31,14,tzinfo=timezone.utc),key_issue_text=' ',suggestion_text=None,
    product_metrics=[],competitor_metrics=[],ring_pull_metrics=[],outlet_type='Drink Shop')
result=agg['aggregate_submissions']([visit,control,new_blank],wide_map={})
assert result['total_outlets']==1 and result['summary_control_count']==2
assert result['key_issues'][0]==issue and result['suggestions'][0]==solution
# Without a written control answer, real outlet text still appears.
a,b=agg['_latest_manual_summary']([visit,new_blank]);assert a==['Newer outlet note'] and b==['Newer outlet action']
# Independent latest non-empty fields: a later solution-only answer is retained.
new_solution=SimpleNamespace(outlet_name='សរុបរួម',submission_time=datetime(2026,10,31,15),key_issue_text=None,suggestion_text='Updated solution')
a,b=agg['_latest_manual_summary']([visit,control,new_blank,new_solution]);assert a==[issue] and b==['Updated solution']
guidance=base['load']('app/reports/guidance.py')
settings=SimpleNamespace(template_file=ROOT/'templates/template_general.xlsx',horeca_template_file=ROOT/'templates/template_horeca_products.xlsx')
writer=base['load']('app/reports/excel_report.py',{**agg,**guidance,'settings':settings,'ALL_DEALERS':['SMR5']})
result['report_type']='GT'
with tempfile.TemporaryDirectory() as temp:
    path=writer['create_report_workbook']([result],Path(temp)/'summary.xlsx')
    sheet=load_workbook(path).active
    assert sheet['I50'].value=='1. '+issue,sheet['I50'].value
    assert sheet['S50'].value=='1. '+solution,sheet['S50'].value
    assert sheet['W4'].value=='Total outlet Visit : 1'
    if '--sample' in __import__('sys').argv:
        import shutil
        dest=ROOT/'exports/V166_SYNTHETIC_SUMMARY_TEXT.xlsx';dest.parent.mkdir(exist_ok=True);shutil.copyfile(path,dest)
print('V166 OK: HTML/nested/Khmer fields, blank duplicates, non-empty final-summary priority, outlet fallback, independent fields and actual I50/S50 report text.')
