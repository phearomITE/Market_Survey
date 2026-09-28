import ast
from pathlib import Path

def test_zero_availability_cannot_win_comparison():
    source = Path(__file__).resolve().parents[1] / 'app/reports/aggregator.py'
    tree = ast.parse(source.read_text(encoding='utf8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_apply_offtake_comparison_goal')
    scope = {'Any':object, 'OFFTAKE_COMPARE_GROUPS':[['Absent','Present']],
             'to_float':lambda v: float(v) if v is not None else None,
             'to_int':lambda v: int(v or 0), 'round_half_up':lambda v:int(v+0.5),
             '_get_movement_bucket':lambda r,p:('products',r['products'][p])}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual normalization>','exec'),scope)
    def data(count,score):
        return {'availability':{'Drink Shop':count},'_mov_effective':score,'_mov_avg':score,'_movement_count':30}
    result={'products':{'Absent':data(0,10),'Present':data(3,4),'Ungrouped':data(0,9)}}
    scope['_apply_offtake_comparison_goal'](result)
    assert result['products']['Absent']['mov']==0
    assert result['products']['Ungrouped']['mov']==0
    assert result['products']['Present']['mov']==10
    result['products']['Present']['availability']={}
    scope['_apply_offtake_comparison_goal'](result)
    assert all(d['mov']==0 for d in result['products'].values())
