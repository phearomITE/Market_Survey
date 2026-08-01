from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class V142OneMinuteCommandTests(unittest.TestCase):
    def test_deadlines_are_below_one_minute(self):
        config = source("app/core/config.py")
        self.assertIn("command_timeout_seconds: int = 55", config)
        self.assertIn("kobo_fetch_deadline_seconds: int = 35", config)
        self.assertIn("png_render_timeout_seconds: int = 18", config)

    def test_kobo_uses_date_filter_cache_and_bounded_requests(self):
        client = source("app/kobo/client.py")
        self.assertIn('"outlet_info/report_date"', client)
        self.assertIn("_DATE_CACHE_LOCK", client)
        self.assertIn("remaining = deadline_seconds - elapsed", client)
        self.assertIn("timeout=max(1, min(request_timeout, int(remaining)))", client)

    def test_generators_use_fast_kobo_not_sync_fallback(self):
        report_service = source("app/services/report_service.py")
        for function_name in (
            "generate_dealer_report",
            "generate_today_all_dealers",
            "generate_multi_dealer_reports",
            "generate_region_dealer_summary",
            "generate_raw_movement_export",
            "generate_daily_data_export",
            "generate_movement_multi_export",
        ):
            start = report_service.index(f"def {function_name}")
            next_function = report_service.find("\ndef ", start + 5)
            block = report_service[start: next_function if next_function >= 0 else None]
            self.assertIn("fetch_report_submissions_fast", block, function_name)
            self.assertNotIn("_sync_and_retry_if_empty", block, function_name)

    def test_excel_is_sent_before_optional_png(self):
        handlers = source("app/bot/handlers.py")
        start = handlers.index("async def report_cmd")
        end = handlers.index("async def report_multi_cmd")
        report_block = handlers[start:end]
        excel_upload = report_block.index("reply_document")
        png_render = report_block.index("excel_to_png")
        self.assertLess(excel_upload, png_render)
        self.assertIn("_run_fast", report_block)

    def test_all_slow_commands_use_deadline_helper(self):
        handlers = source("app/bot/handlers.py")
        self.assertEqual(handlers.count("asyncio.to_thread"), 1)
        for name in (
            "sync_kobo_cmd",
            "report_cmd",
            "report_multi_cmd",
            "report_today_cmd",
            "debug_kobo_cmd",
            "summary_cmd",
            "raw_movement_cmd",
            "alert_submit_cmd",
            "export_cmd",
        ):
            start = handlers.index(f"async def {name}")
            next_function = handlers.find("\nasync def ", start + 6)
            block = handlers[start: next_function if next_function >= 0 else None]
            self.assertIn("_run_fast", block, name)

    def test_run_bot_imports_and_registers_every_handler(self):
        handlers_tree = ast.parse(source("app/bot/handlers.py"))
        handler_names = {
            node.name
            for node in handlers_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        run_bot_tree = ast.parse(source("app/bot/run_bot.py"))
        imported = set()
        for node in run_bot_tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "app.bot.handlers":
                imported.update(alias.name for alias in node.names)
        self.assertTrue(imported <= handler_names, imported - handler_names)
        run_bot = source("app/bot/run_bot.py")
        self.assertIn('CommandHandler("alert_submit", alert_submit_cmd)', run_bot)

    def test_bulk_reports_do_not_build_png_zip(self):
        report_service = source("app/services/report_service.py")
        self.assertNotIn("excel_workbook_to_png_zip", report_service)


if __name__ == "__main__":
    unittest.main()
