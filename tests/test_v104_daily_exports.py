from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace
import importlib.util
import sys
import tempfile
import unittest

from openpyxl import load_workbook


def _load_exports_module():
    config = ModuleType("app.core.config")
    config.settings = SimpleNamespace(export_path=Path(tempfile.gettempdir()))
    aggregator = ModuleType("app.reports.aggregator")
    aggregator.OWN_PRODUCTS = ["OWN"]
    aggregator.COMPETITOR_PRODUCTS = ["COMP"]
    aggregator.HORECA_OWN_PRODUCTS = ["HOWN"]
    aggregator.HORECA_COMPETITOR_PRODUCTS = ["HCOMP"]
    aggregator.ALL_OWN_PRODUCTS = ["OWN", "HOWN"]
    aggregator.ALL_COMPETITOR_PRODUCTS = ["COMP", "HCOMP"]
    aggregator.is_final_summary_outlet_name = (
        lambda value: str(value or "").replace(" ", "").strip() == "បូកសរុបរួម"
    )
    aggregator.load_wide_payloads = lambda rows: {}
    aggregator.aggregate_submissions = lambda rows, wide_map=None: {
        "region": "R1",
        "dealer": "D1",
        "location_text": "Phnom Penh",
        "total_outlets": len(rows),
        "outlet_types": {"Drink Shop": len(rows)},
        "products": {"OWN": {"availability": {"Drink Shop": len(rows)}, "mov": 10}},
        "competitors": {"COMP": {"mov": 8}},
    }
    sys.modules["app.core.config"] = config
    sys.modules["app.reports.aggregator"] = aggregator
    path = Path("app/reports/movement_exports.py")
    spec = importlib.util.spec_from_file_location("v104_movement_exports", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class V104DailyExportTests(unittest.TestCase):
    def setUp(self):
        self.exports = _load_exports_module()
        self.submission = SimpleNamespace(
            report_date=date(2026, 7, 25),
            region="R1",
            dealer="D1",
            member_no=1,
            location_text="Phnom Penh",
            gps_latitude=11.56,
            gps_longitude=104.92,
            outlet_name="Outlet 1",
            outlet_type="Drink Shop",
            phone_number="012345678",
            report_type="GT",
            product_metrics=[SimpleNamespace(product_name="OWN", movement_score=7)],
            competitor_metrics=[SimpleNamespace(product_name="COMP", movement_score=6)],
        )

    def test_export_has_exact_two_sheets_and_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "daily.xlsx"
            self.exports.create_daily_export([self.submission], date(2026, 7, 25), output)
            wb = load_workbook(output, read_only=True)
            self.assertEqual(wb.sheetnames, ["Summary_Data", "Location_Outlet"])
            self.assertEqual(
                [cell.value for cell in next(wb["Summary_Data"].iter_rows(max_row=1))],
                self.exports.SUMMARY_HEADERS,
            )
            self.assertEqual(
                [cell.value for cell in next(wb["Location_Outlet"].iter_rows(max_row=1))],
                self.exports.BASE_HEADERS,
            )
            summary = list(wb["Summary_Data"].iter_rows(min_row=2, max_row=2, values_only=True))[0]
            self.assertEqual(summary[-1], 10)
            wb.close()

    def test_raw_export_has_five_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "raw.xlsx"
            self.exports.create_raw_movement_long_export([self.submission], date(2026, 7, 25), output)
            wb = load_workbook(output, read_only=True)
            ws = wb["Raw_Movement"]
            first_row = [cell.value for cell in next(ws.iter_rows(max_row=1))]
            self.assertEqual(first_row, self.exports.RAW_HEADERS)
            self.assertEqual(len(first_row), 5)
            data_rows = list(ws.iter_rows(min_row=2, values_only=True))
            own_row = next(row for row in data_rows if row[3] == "OWN")
            self.assertEqual(own_row[4], 7)
            wb.close()

    def test_raw_export_preserves_zero_and_skips_summary(self):
        zero_submission = SimpleNamespace(**vars(self.submission))
        zero_submission.outlet_name = "Outlet Zero"
        zero_submission.product_metrics = [
            SimpleNamespace(product_name="OWN", movement_score=0)
        ]
        zero_submission.competitor_metrics = []

        summary_submission = SimpleNamespace(**vars(self.submission))
        summary_submission.outlet_name = "បូកសរុបរួម"
        summary_submission.product_metrics = [
            SimpleNamespace(product_name="OWN", movement_score=10)
        ]

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "raw_baseline.xlsx"
            self.exports.create_raw_movement_long_export(
                [zero_submission, summary_submission],
                date(2026, 7, 25),
                output,
            )
            wb = load_workbook(output, read_only=True)
            rows = list(
                wb["Raw_Movement"].iter_rows(min_row=2, values_only=True)
            )
            self.assertTrue(rows)
            self.assertTrue(all(row[4] == 0 for row in rows))
            self.assertTrue(all(row[4] != 10 for row in rows))
            wb.close()


if __name__ == "__main__":
    unittest.main()
