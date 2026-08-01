from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V143DisableFullAutoSyncTests(unittest.TestCase):
    def test_post_init_never_starts_full_sync_loop(self):
        source = (ROOT / "app/bot/run_bot.py").read_text(encoding="utf-8")
        start = source.index("async def _post_init")
        end = source.index("async def _post_shutdown")
        block = source[start:end]
        self.assertNotIn("create_task", block)
        self.assertNotIn("auto_sync_enabled", block)
        self.assertIn("Automatic full Kobo sync disabled", block)

    def test_manual_sync_is_current_day_only(self):
        source = (ROOT / "app/bot/handlers.py").read_text(encoding="utf-8")
        start = source.index("async def sync_kobo_cmd")
        end = source.index("async def _maybe_sync_before_report")
        block = source[start:end]
        self.assertIn("report_date = local_today()", block)
        self.assertIn("report_date=report_date", block)
        self.assertIn("timeout_seconds=50", block)

    def test_reports_still_use_fast_date_filtered_path(self):
        source = (ROOT / "app/services/report_service.py").read_text(encoding="utf-8")
        self.assertIn("fetch_report_submissions_fast", source)
        self.assertIn("generate_dealer_report", source)


if __name__ == "__main__":
    unittest.main()
