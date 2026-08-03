from pathlib import Path
import unittest


class V149ExportStatusCommandTests(unittest.TestCase):
    def test_command_is_registered_and_documented(self):
        run_bot = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
        handlers = Path("app/bot/handlers.py").read_text(encoding="utf-8")
        self.assertIn(
            'CommandHandler("export_status", export_status_cmd)', run_bot
        )
        self.assertIn("async def export_status_cmd", handlers)
        self.assertIn("/export_status 2026-08-01", handlers)


if __name__ == "__main__":
    unittest.main()
