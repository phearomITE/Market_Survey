"""Regression: template ml/mL spelling must retain calculated Sport metrics."""
import ast
from pathlib import Path
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]

def test_sport_template_resolves_calculated_metrics():
    tree = ast.parse((ROOT / 'app/reports/excel_report.py').read_text(encoding='utf8'))
    nodes = [n for n in tree.body if
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PRODUCT_NAME_MAP' for t in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name == '_product_key')]
    scope = {'_clean': lambda value: ' '.join(str(value or '').split())}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<report lookup>', 'exec'), scope)
    key = scope['_product_key']
    # Fixture values are deliberately distinct; these are not CA2's live results.
    metrics = {'CAMBODIA Sport 500mL ORD': {'mov': 8, 'availability': {'Drink Shop': 12}}}
    for label in ['CAMBODIA Sport 500ml ORD', 'CAMBODIA Sport 500mL ORD',
                  'CAMBODIA SPORT 500ML ORD', 'CAMBODIA Sport 500ml']:
        assert metrics[key(label)]['mov'] == 8
        assert metrics[key(label)]['availability']['Drink Shop'] == 12
    workbook = load_workbook(ROOT / 'templates/template_general.xlsx')
    try:
        for address in ['B22', 'B40']:
            assert metrics[key(workbook.active[address].value)]['mov'] == 8
    finally:
        workbook.close()
    assert key('CAMBODIA WATER 500mL') != 'CAMBODIA Sport 500mL ORD'
