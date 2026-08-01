from pathlib import Path
import unittest


class V125FastReportsNoWebTests(unittest.TestCase):
    def test_no_background_full_sync(self):
        source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
        self.assertNotIn("_auto_sync_loop", source)
        self.assertNotIn("post_init(_post_init)", source)

    def test_map_and_dashboard_commands_removed(self):
        run_bot = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
        handlers = Path("app/bot/handlers.py").read_text(encoding="utf-8")
        self.assertNotIn('CommandHandler("map"', run_bot)
        self.assertNotIn('CommandHandler("dashboard"', run_bot)
        self.assertNotIn("async def map_cmd", handlers)
        self.assertNotIn("async def dashboard_cmd", handlers)

    def test_targeted_fetch_has_hard_deadline(self):
        client = Path("app/kobo/client.py").read_text(encoding="utf-8")
        self.assertIn("deadline_seconds = 18 if dealer else 120", client)
        self.assertIn('"limit": 500', client)
        self.assertIn("page_limit = 5 if dealer else 20", client)
        self.assertIn("request_timeout = 10 if dealer else 60", client)

    def test_railway_starts_telegram_bot_only(self):
        railway = Path("railway.json").read_text(encoding="utf-8")
        docker = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn("python -m app.bot.run_bot", railway)
        self.assertIn('CMD ["python", "-m", "app.bot.run_bot"]', docker)


if __name__ == "__main__":
    unittest.main()
