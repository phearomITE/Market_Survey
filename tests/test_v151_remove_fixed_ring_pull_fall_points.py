from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

from openpyxl import load_workbook

from app.reports.aggregator import aggregate_submissions
from app.reports.excel_report import (
    NO_COMPROMISE_ITEMS,
    _layout_rows,
    fill_template_sheet,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FORM_PATH = PROJECT_ROOT / "templates" / "KB_Market_Improvement_XLSForm_GT_HORECA.xlsx"


def _submission(index: int, outlet_name: str, **overrides):
    values = {
        "id": index,
        "submission_time": datetime(2026, 8, 14, 8, index),
        "report_date": date(2026, 8, 14),
        "region": "R1",
        "dealer": "CA1",
        "group_no": 2,
        "member_no": 4,
        "location_text": "Phnom Penh",
        "outlet_name": outlet_name,
        "outlet_type": "Drink Shop",
        "submitter_name": None,
        "key_issue_text": None,
        "suggestion_text": None,
        "product_metrics": [],
        "competitor_metrics": [],
        "ring_pull_metrics": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class V152SummaryNoCompromiseTests(unittest.TestCase):
    def test_xlsform_removes_fall_point_and_uses_new_summary_labels(self):
        workbook = load_workbook(FORM_PATH, read_only=True, data_only=False)
        survey = workbook["survey"]
        headers = [cell.value for cell in next(survey.iter_rows(min_row=1, max_row=1))]
        name_col = headers.index("name")
        label_col = headers.index("label")
        relevant_col = headers.index("relevant")

        rows_by_name = {}
        labels = []
        for row in survey.iter_rows(min_row=2, values_only=True):
            name = row[name_col]
            if name:
                rows_by_name[name] = row
            if row[label_col]:
                labels.append(str(row[label_col]))

        self.assertNotIn("ring_pull_group", rows_by_name)
        self.assertNotIn("ring_pull_in_outlets", rows_by_name)
        self.assertNotIn("ring_pull_qty_cbl_ncp_6_can", rows_by_name)
        self.assertNotIn("ring_pull_qty_cbl_ncp_5_usd", rows_by_name)
        self.assertFalse(any("Ring Pull In Outlets" in label for label in labels))

        self.assertNotIn("submitter_name", rows_by_name)
        self.assertFalse(any("ចំណុចដួល" in label for label in labels))

        final_section = rows_by_name["key_issues_suggestion_group"]
        self.assertIn(">3. FINAL", str(final_section[label_col]))
        self.assertIn("បញ្ហាទីផ្សារ", str(final_section[label_col]))
        self.assertIn("បញ្ហាត្រូវដោះស្រាយ", str(final_section[label_col]))
        self.assertEqual(rows_by_name["key_issues_detail"][label_col], "បញ្ហាទីផ្សារ")
        self.assertEqual(
            rows_by_name["initiative_idea_suggestion"][label_col],
            "បញ្ហាត្រូវដោះស្រាយ",
        )
        required = str(rows_by_name["key_issues_detail"][headers.index("required")])
        self.assertIn("contains(", required)
        self.assertIn("សរុបរួម", required)
        self.assertIn("សរុបចុងក្រោយ", required)

        choices = workbook["choices"]
        choice_rows = list(choices.iter_rows(values_only=True))
        self.assertFalse(any(row and row[0] == "ring_pull_in_outlet_choices" for row in choice_rows))
        workbook.close()

    def test_summary_control_row_uses_only_market_issue_and_action(self):
        normal = _submission(
            1,
            "Outlet A",
            submitter_name="This normal-outlet value must not be used",
        )
        summary = _submission(
            2,
            "បូកសរុបរួម",
            submitter_name="Legacy value must be ignored",
            key_issue_text="1. Issue one",
            suggestion_text="1. Action one",
        )
        result = aggregate_submissions(
            [normal, summary],
            wide_map={},
            own_product_names=[],
            competitor_product_names=[],
            include_ring_pull=False,
        )
        self.assertEqual(result["total_outlets"], 1)
        self.assertNotIn("fall_points", result)
        self.assertEqual(result["key_issues"][0], "Issue one")
        self.assertEqual(result["suggestions"][0], "Action one")

    def test_gt_and_horeca_templates_generate_without_fixed_ring_pull(self):
        cases = [
            ("template_general.xlsx", "GT", {"Drink Shop": 1}),
            ("template_horeca_products.xlsx", "HORECA", {"Local Eat": 1}),
        ]
        for template_name, channel, outlet_types in cases:
            with self.subTest(template=template_name):
                workbook = load_workbook(PROJECT_ROOT / "templates" / template_name)
                sheet = workbook.active
                agg = {
                    "dealer": "CA1",
                    "report_date": date(2026, 8, 14),
                    "total_outlets": 1,
                    "outlet_types": outlet_types,
                    "location_text": "Phnom Penh",
                    "group_no": 2,
                    "member_no": 4,
                    "channel": channel,
                    "products": {},
                    "competitors": {},
                    "ring_pull": {
                        "CBL NCP 6 Can": {"total_outlets": 99, "qty": 99},
                        "CBL NCP 5 USD": {"total_outlets": 99, "qty": 99},
                    },
                    "key_issues": ["Issue one", "", "", ""],
                    "suggestions": ["Action one", "", "", ""],
                }
                fill_template_sheet(sheet, agg)
                layout = _layout_rows(sheet, agg)

                self.assertEqual(sheet.cell(layout["summary_header"], 1).value, "No Compromise")
                self.assertEqual(sheet.cell(layout["summary_header"], 9).value, "បញ្ហាទីផ្សារ")
                self.assertEqual(
                    sheet.cell(layout["summary_header"], 19).value,
                    "បញ្ហាត្រូវដោះស្រាយ",
                )
                self.assertEqual(
                    sheet.cell(layout["issue_start"], 1).value,
                    NO_COMPROMISE_ITEMS[0],
                )
                self.assertEqual(
                    sheet.cell(layout["issue_start"] + 3, 1).value,
                    NO_COMPROMISE_ITEMS[3],
                )
                self.assertEqual(sheet.cell(layout["issue_start"], 9).value, "1. Issue one")
                self.assertEqual(sheet.cell(layout["issue_start"], 19).value, "1. Action one")

                values = [
                    str(cell.value or "")
                    for row in sheet.iter_rows()
                    for cell in row
                ]
                self.assertNotIn("Ring Pull In Outlets", values)
                self.assertNotIn("CBL NCP 6 Can", values)
                self.assertNotIn("CBL NCP 5 USD", values)
                self.assertFalse(any("ចំណុចដួល" in value for value in values))
                workbook.close()


if __name__ == "__main__":
    unittest.main()
