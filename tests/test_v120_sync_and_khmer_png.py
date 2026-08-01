from pathlib import Path
import unittest


class V120SyncAndKhmerPngTests(unittest.TestCase):
    def test_kobo_fetch_uses_exact_xlsform_dealer_and_date(self):
        client = Path("app/kobo/client.py").read_text(encoding="utf-8")
        sync = Path("app/kobo/sync.py").read_text(encoding="utf-8")
        self.assertIn('query["outlet_info/dealer"] = str(dealer).strip().lower()', client)
        self.assertIn('query["outlet_info/report_date"] = report_date.isoformat()', client)
        self.assertNotIn('dealer_values = {"$in"', client)
        self.assertNotIn('conditions.append({"$or"', client)
        self.assertIn('"query": json.dumps(query', client)
        self.assertIn("fetch_submissions(dealer=dealer, report_date=report_date)", sync)

    def test_report_runs_only_one_targeted_sync(self):
        source = Path("app/services/report_service.py").read_text(encoding="utf-8")
        helper = source[source.index("def _sync_and_retry_if_empty"):source.index(
            "def generate_dealer_report"
        )]
        self.assertEqual(helper.count("sync_kobo("), 1)
        self.assertIn("return get_submissions", helper)
        self.assertNotIn("if submissions:\n        return submissions", helper)

    def test_report_always_refreshes_stale_nonempty_rows(self):
        source = Path("app/services/report_service.py").read_text(encoding="utf-8")
        block = source[source.index("def generate_dealer_report"):source.index(
            "def generate_today_all_dealers"
        )]
        self.assertIn(
            "submissions = _sync_and_retry_if_empty(dealer, d, submissions, report_type=report_type)",
            block,
        )
        self.assertNotIn("if settings.auto_sync_before_report or not submissions", block)

    def test_khmer_font_and_headless_environment(self):
        source = Path("app/services/render_service.py").read_text(encoding="utf-8")
        docker = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn('font.name = "Noto Sans Khmer"', source)
        self.assertIn('"SAL_USE_VCLPLUGIN": "svp"', source)
        self.assertIn("fonts-noto-extra", docker)
        self.assertNotIn("fonts-khmeros-core", docker)

    def test_manual_sync_defaults_to_today(self):
        handlers = Path("app/bot/handlers.py").read_text(encoding="utf-8")
        block = handlers[handlers.index("async def sync_kobo_cmd"):handlers.index(
            "async def _maybe_sync_before_report"
        )]
        self.assertIn("sync_date = local_today()", block)
        self.assertIn("report_date=sync_date", block)

    def test_alert_command_is_registered(self):
        run_bot = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
        handlers = Path("app/bot/handlers.py").read_text(encoding="utf-8")
        self.assertIn('CommandHandler("alert_submit", alert_submit_cmd)', run_bot)
        self.assertIn("async def alert_submit_cmd", handlers)


if __name__ == "__main__":
    unittest.main()
