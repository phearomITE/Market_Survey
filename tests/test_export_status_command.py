from datetime import date
from types import SimpleNamespace
from unittest import TestCase

from app.services.export_status_service import format_export_status


class ExportStatusTests(TestCase):
    def test_summary_variants_complete_dealers_once(self):
        rows = [
            SimpleNamespace(dealer=" ca1 ", outlet_name="បូកសរុបរួម10"),
            SimpleNamespace(dealer="CA1", outlet_name="សរុបចុងក្រោយ"),
            SimpleNamespace(dealer="CA3", outlet_name="ចែ ម៉ៅ"),
            SimpleNamespace(dealer="CA6", outlet_name="ចែ ម៉ៅ, បូកសរុបរួម"),
            SimpleNamespace(dealer="UNKNOWN", outlet_name="សរុបរួម"),
        ]
        result = format_export_status(date(2026, 9, 19), rows)
        self.assertIn("Completed: 2/65 dealers", result)
        self.assertIn("R1: 2/10 completed", result)
        self.assertIn("CA3", result)
        self.assertNotIn("UNKNOWN", result)

    def test_no_rows_lists_every_dealer_missing(self):
        result = format_export_status(date(2026, 9, 19), [])
        self.assertIn("Completed: 0/65 dealers", result)
        self.assertIn("R8: 0/4 completed", result)
