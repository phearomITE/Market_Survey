from datetime import date
from pathlib import Path
import unittest

from app.data.dealers import ALL_DEALERS
from app.services.submission_alert_service import (
    dealers_below_threshold,
    format_submission_alert,
)


class V119FastReportsAndAlertsTests(unittest.TestCase):
    def test_alert_thresholds_and_text(self):
        counts = {dealer: 25 for dealer in ALL_DEALERS}
        counts.update({"CA1": 8, "CA5": 5, "PTM6": 16, "KKG3": 14})
        self.assertEqual(dealers_below_threshold(counts, 10), [("CA1", 8), ("CA5", 5)])
        self.assertEqual(
            dealers_below_threshold(counts, 20)[:4],
            [("PTM6", 16), ("KKG3", 14), ("CA1", 8), ("CA5", 5)],
        )
        text = format_submission_alert(date(2026, 8, 1), 10, counts)
        self.assertIn("1. CA1 = 8 Report", text)
        self.assertIn("2. CA5 = 5 Report", text)

    def test_commands_are_registered_and_concurrent(self):
        source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
        self.assertIn('CommandHandler("alert_submit", alert_submit_cmd)', source)
        self.assertIn(".concurrent_updates(4)", source)

    def test_report_does_not_block_on_sync(self):
        source = Path("app/services/report_service.py").read_text(encoding="utf-8")
        helper = source[source.index("def _sync_and_retry_if_empty"):source.index(
            "def generate_dealer_report"
        )]
        self.assertNotIn("sync_kobo(", helper)

    def test_excel_precedes_png_with_deadline(self):
        source = Path("app/bot/handlers.py").read_text(encoding="utf-8")
        handler = source[source.index("async def report_cmd"):source.index(
            "async def report_multi_cmd"
        )]
        self.assertLess(handler.index("reply_document"), handler.index("excel_to_png"))
        self.assertIn("asyncio.wait_for", handler)


if __name__ == "__main__":
    unittest.main()
