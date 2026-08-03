from datetime import date
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest


def _load_service():
    dealers = ModuleType("app.data.dealers")
    dealers.ALL_DEALERS = ["CA1", "CA8", "CA3", "CA6"]
    sync = ModuleType("app.kobo.sync")
    sync.fetch_report_submissions_fast = lambda *args, **kwargs: []
    sys.modules["app.data.dealers"] = dealers
    sys.modules["app.kobo.sync"] = sync
    path = Path("app/services/submission_alert_service.py")
    spec = importlib.util.spec_from_file_location("v150_alert_service", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class V150AlertSubmitDateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = _load_service()

    def test_threshold_10_with_historical_date(self):
        self.assertEqual(
            self.service.parse_alert_submit_args(["10", "2026-08-01"]),
            (10, date(2026, 8, 1)),
        )

    def test_threshold_20_with_historical_date(self):
        self.assertEqual(
            self.service.parse_alert_submit_args(["20", "2026-08-01"]),
            (20, date(2026, 8, 1)),
        )

    def test_date_is_optional_and_defaults_to_today(self):
        current = date(2026, 8, 3)
        self.assertEqual(
            self.service.parse_alert_submit_args(["10"], today=current),
            (10, current),
        )

    def test_invalid_threshold_and_date_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Threshold"):
            self.service.parse_alert_submit_args(["15", "2026-08-01"])
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            self.service.parse_alert_submit_args(["20", "01-08-2026"])

    def test_exact_threshold_boundaries_remain_correct(self):
        message_10 = self.service.format_submission_alert(
            date(2026, 8, 1),
            10,
            {"CA1": 9, "CA8": 10, "CA3": 19, "CA6": 20},
        )
        self.assertIn("CA1 = 9 Report", message_10)
        self.assertNotIn("CA8 = 10 Report", message_10)

        message_20 = self.service.format_submission_alert(
            date(2026, 8, 1),
            20,
            {"CA1": 9, "CA8": 10, "CA3": 19, "CA6": 20},
        )
        self.assertIn("CA1 = 9 Report", message_20)
        self.assertIn("CA8 = 10 Report", message_20)
        self.assertIn("CA3 = 19 Report", message_20)
        self.assertNotIn("CA6 = 20 Report", message_20)

    def test_handler_documents_and_uses_date_parser(self):
        handlers = Path("app/bot/handlers.py").read_text(encoding="utf-8")
        self.assertIn("parse_alert_submit_args(context.args)", handlers)
        self.assertIn("/alert_submit 10 [YYYY-MM-DD]", handlers)
        self.assertIn("/alert_submit 20 [YYYY-MM-DD]", handlers)


if __name__ == "__main__":
    unittest.main()
