import ast
from datetime import date
from pathlib import Path
import unittest

from openpyxl import Workbook, load_workbook

from app.reports.guidance import guidance_for_date, write_guidance


ROOT = Path(__file__).resolve().parents[1]


class OrdGuidanceTests(unittest.TestCase):
    def test_weekly_cycle_uses_requested_report_date(self):
        self.assertEqual(guidance_for_date(date(2026, 9, 12))[0], 'No Compromise')
        self.assertEqual(guidance_for_date('2026-09-19')[0], "Don't")
        self.assertEqual(guidance_for_date('26/09/2026')[0], 'No Compromise')
        self.assertEqual(guidance_for_date(date(2026, 10, 3))[0], "Don't")

    def test_guidance_is_visible_in_printable_sheet(self):
        sheet = Workbook().active
        end = write_guidance(sheet, date(2026, 9, 19), 50)
        self.assertEqual(sheet['A50'].value, "Don't")
        self.assertEqual(end, 57)
        self.assertTrue(sheet['A57'].value.startswith('7. '))
        source = (ROOT / 'app/reports/excel_report.py').read_text(encoding='utf8')
        self.assertIn('write_guidance(ws, rdate, layout["print_end"] + 2)', source)
        self.assertIn('ws.print_area = f"A1:AA{guidance_end}"', source)

    def test_form_and_product_lists_have_both_ord_names(self):
        form = load_workbook(ROOT / 'templates/KB_Market_Improvement_XLSForm_GT_HORECA.xlsx', read_only=True)
        labels = [cell.value for sheet in form for row in sheet for cell in row if isinstance(cell.value, str)]
        for name in ('WURKZ ORD', 'Dragon ORD'):
            self.assertIn(name, labels)
        source = (ROOT / 'app/reports/aggregator.py').read_text(encoding='utf8')
        tree = ast.parse(source)
        lists = {node.targets[0].id: ast.literal_eval(node.value)
                 for node in tree.body if isinstance(node, ast.Assign)
                 and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id in {'OWN_PRODUCTS', 'COMPETITOR_PRODUCTS'}}
        self.assertIn('WURKZ ORD', lists['OWN_PRODUCTS'])
        self.assertIn('Dragon ORD', lists['COMPETITOR_PRODUCTS'])
        self.assertNotIn('WURKZ', lists['OWN_PRODUCTS'])
        self.assertNotIn('Dragon', lists['COMPETITOR_PRODUCTS'])
        for template_path in (ROOT / 'templates').glob('template*.xlsx'):
            sheet = load_workbook(template_path, read_only=True).active
            labels = [cell.value for row in sheet for cell in row if isinstance(cell.value, str)]
            self.assertNotIn('WURKZ', labels, template_path.name)
            self.assertNotIn('Dragon', labels, template_path.name)

    def test_database_migration_never_deletes_canonical_names(self):
        source = (ROOT / 'app/db/database.py').read_text(encoding='utf8')
        self.assertIn('if old_name == new_name:', source)
        self.assertIn('"WURKZ": "WURKZ ORD"', source)
        self.assertIn('"Dragon": "Dragon ORD"', source)
        self.assertNotIn('"DAZZ ORD": "DAZZ ORD"', source)


if __name__ == '__main__':
    unittest.main()
