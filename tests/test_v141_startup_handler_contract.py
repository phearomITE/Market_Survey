from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V141StartupHandlerContractTests(unittest.TestCase):
    def test_every_run_bot_handler_import_exists(self):
        run_tree = ast.parse(
            (ROOT / "app" / "bot" / "run_bot.py").read_text(encoding="utf-8")
        )
        handler_tree = ast.parse(
            (ROOT / "app" / "bot" / "handlers.py").read_text(encoding="utf-8")
        )

        imported = {
            alias.name
            for node in run_tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "app.bot.handlers"
            for alias in node.names
        }
        defined = {
            node.name
            for node in handler_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(imported - defined, set())

    def test_alert_submit_is_defined_imported_and_registered(self):
        handlers = (ROOT / "app" / "bot" / "handlers.py").read_text(encoding="utf-8")
        runner = (ROOT / "app" / "bot" / "run_bot.py").read_text(encoding="utf-8")
        service = ROOT / "app" / "services" / "submission_alert_service.py"

        self.assertIn("async def alert_submit_cmd", handlers)
        self.assertIn("alert_submit_cmd,", runner)
        self.assertIn('CommandHandler("alert_submit", alert_submit_cmd)', runner)
        self.assertTrue(service.is_file())

    def test_alert_is_manual_only(self):
        runner = (ROOT / "app" / "bot" / "run_bot.py").read_text(encoding="utf-8")
        self.assertEqual(runner.count('CommandHandler("alert_submit"'), 1)
        self.assertNotIn("alert_submit_job", runner)


if __name__ == "__main__":
    unittest.main()
