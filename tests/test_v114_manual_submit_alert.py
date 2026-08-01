from datetime import date
from pathlib import Path
import unittest

from app.data.dealers import ALL_DEALERS
from app.services.submission_alert_service import (
    dealers_below_threshold,
    format_submission_alert,
)


def _counts() -> dict[str, int]:
    counts = {dealer: 25 for dealer in ALL_DEALERS}
    counts.update({"CA1": 8, "CA5": 5, "PTM6": 16, "KKG3": 14})
    return counts


class V114ManualSubmitAlertTests(unittest.TestCase):
    def test_manual_threshold_10(self):
        self.assertEqual(
            dealers_below_threshold(_counts(), 10),
            [("CA1", 8), ("CA5", 5)],
        )

    def test_manual_threshold_20(self):
        self.assertEqual(
            dealers_below_threshold(_counts(), 20)[:4],
            [
                ("PTM6", 16),
                ("KKG3", 14),
                ("CA1", 8),
                ("CA5", 5),
            ],
        )

    def test_alert_text_and_command_registration(self):
        text = format_submission_alert(date(2026, 7, 25), 10, _counts())
        self.assertIn("Dealer ដែល Submit Report តិចជាង 10", text)
        self.assertIn("1. CA1 = 8 Report", text)
        self.assertIn("2. CA5 = 5 Report", text)

        source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
        self.assertIn('CommandHandler("alert_submit", alert_submit_cmd)', source)
        self.assertNotIn("submit_alert_job", source)


if __name__ == "__main__":
    unittest.main()
