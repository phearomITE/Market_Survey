from pathlib import Path
import unittest


class V120SyncAndKhmerPngTests(unittest.TestCase):
    def test_kobo_fetch_uses_dealer_and_date_query(self):
        client = Path("app/kobo/client.py").read_text(encoding="utf-8")
        sync = Path("app/kobo/sync.py").read_text(encoding="utf-8")
        self.assertIn('"outlet_info/dealer"', client)
        self.assertIn('"outlet_info/report_date"', client)
        self.assertIn('params = {"query": json.dumps', client)
        self.assertIn("fetch_submissions(dealer=dealer, report_date=report_date)", sync)

    def test_report_runs_only_one_targeted_sync(self):
        source = Path("app/services/report_service.py").read_text(encoding="utf-8")
        helper = source[source.index("def _sync_and_retry_if_empty"):source.index(
            "def generate_dealer_report"
        )]
        self.assertEqual(helper.count("sync_kobo("), 1)
        self.assertIn("return get_submissions", helper)

    def test_khmer_font_and_headless_environment(self):
        source = Path("app/services/render_service.py").read_text(encoding="utf-8")
        docker = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn('font.name = "Noto Sans Khmer"', source)
        self.assertIn('"SAL_USE_VCLPLUGIN": "svp"', source)
        self.assertIn("fonts-khmeros-core", docker)

    def test_alert_command_is_registered(self):
        run_bot = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
        handlers = Path("app/bot/handlers.py").read_text(encoding="utf-8")
        self.assertIn('CommandHandler("alert_submit", alert_submit_cmd)', run_bot)
        self.assertIn("async def alert_submit_cmd", handlers)


if __name__ == "__main__":
    unittest.main()
