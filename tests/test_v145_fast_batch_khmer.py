from datetime import date
from time import perf_counter
import unittest
from unittest.mock import patch

from openpyxl import Workbook

from app.kobo.parser import FlatFieldMap, flatten_dict, normalize_submission
from app.kobo.sync import (
    clear_report_submission_cache,
    fetch_report_submissions_fast,
)
from app.reports.aggregator import (
    ALL_COMPETITOR_PRODUCTS,
    ALL_OWN_PRODUCTS,
    competitor_field,
    product_field,
)
from app.reports.excel_report import SUMMARY_FONT_NAME, _normalize_khmer_cells


def _submission(index: int) -> dict:
    row = {
        "_id": str(index),
        "_submission_time": "2026-08-01T10:00:00",
        "outlet_info": {
            "report_date": "2026-08-01",
            "region": "R1",
            "dealer": f"CA{(index % 9) + 1}",
            "final_summary_report_type": "GT",
            "outlet_name": f"Outlet {index}",
            "outlet_type": "drink_shop",
        },
    }
    for product in ALL_OWN_PRODUCTS:
        row[product_field(product, "status")[0]] = "sale"
        row[product_field(product, "mov")[0]] = "5"
    for product in ALL_COMPETITOR_PRODUCTS:
        row[competitor_field(product, "mov")[0]] = "5"
    return row


class V145FastBatchKhmerTests(unittest.TestCase):
    def tearDown(self):
        clear_report_submission_cache()

    def test_flattened_submission_builds_reusable_field_indexes(self):
        flat = flatten_dict(
            {
                "outlet_info": {
                    "report_date": "2026-08-01",
                    "dealer": "ca2",
                    "final_summary_report_type": "gt",
                }
            }
        )
        self.assertIsInstance(flat, FlatFieldMap)
        normalized = normalize_submission({"_id": "1"}, flat=flat)
        self.assertEqual(normalized["dealer"], "CA2")
        self.assertEqual(normalized["report_type"], "GT")
        self.assertEqual(normalized["report_date"], date(2026, 8, 1))

    def test_normalized_cache_prevents_duplicate_full_product_parsing(self):
        rows = [_submission(index) for index in range(1, 41)]
        clear_report_submission_cache()
        with patch(
            "app.kobo.sync.KoboClient.fetch_submissions", return_value=rows
        ) as fetch:
            first = fetch_report_submissions_fast(None, date(2026, 8, 1))
            second = fetch_report_submissions_fast(None, date(2026, 8, 1))
        self.assertEqual(len(first), 40)
        self.assertEqual(len(second), 40)
        self.assertEqual(fetch.call_count, 1)

    def test_250_full_rows_normalize_well_below_command_timeout(self):
        rows = [_submission(index) for index in range(1, 251)]
        clear_report_submission_cache()
        with patch(
            "app.kobo.sync.KoboClient.fetch_submissions", return_value=rows
        ):
            started = perf_counter()
            submissions = fetch_report_submissions_fast(None, date(2026, 8, 1))
            elapsed = perf_counter() - started
        self.assertEqual(len(submissions), 250)
        self.assertLess(elapsed, 10)

    def test_khmer_font_has_no_excel_theme_override(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet["A1"] = "គ្\u200bរប់"
        _normalize_khmer_cells(sheet)
        self.assertEqual(sheet["A1"].value, "គ្រប់")
        self.assertEqual(sheet["A1"].font.name, SUMMARY_FONT_NAME)
        self.assertIsNone(sheet["A1"].font.scheme)
        self.assertIsNone(sheet["A1"].font.charset)


if __name__ == "__main__":
    unittest.main()
