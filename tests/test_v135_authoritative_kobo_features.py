from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _function_source(relative: str, name: str) -> str:
    source = _source(relative)
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"Function not found: {name}")


class V135AuthoritativeKoboFeaturesTests(unittest.TestCase):
    def test_every_data_feature_reads_current_kobo_date(self):
        service = "app/services/report_service.py"
        functions = (
            "generate_dealer_report",
            "generate_today_all_dealers",
            "generate_multi_dealer_reports",
            "generate_region_dealer_summary",
            "generate_raw_movement_export",
            "generate_daily_data_export",
            "generate_movement_multi_export",
        )
        for name in functions:
            with self.subTest(name=name):
                body = _function_source(service, name)
                self.assertIn("fetch_report_submissions_fast", body)
                self.assertNotIn("get_submissions(", body)

    def test_dealer_is_filtered_locally_after_date_fetch(self):
        client = _source("app/kobo/client.py")
        sync = _source("app/kobo/sync.py")
        self.assertIn('query = {"outlet_info/report_date": report_date.isoformat()}', client)
        self.assertNotIn('query["outlet_info/dealer"]', client)
        self.assertIn("normalized_dealer not in wanted_dealers", sync)

    def test_full_date_modes_are_lightweight(self):
        sync = _source("app/kobo/sync.py")
        self.assertIn("submission = SimpleNamespace(**data)", sync)
        self.assertIn("metadata_only", sync)
        self.assertIn("summary_only", sync)

    def test_alert_uses_current_kobo_not_stale_database(self):
        alert = _source("app/services/submission_alert_service.py")
        run_bot = _source("app/bot/run_bot.py")
        self.assertIn("fetch_report_submissions_fast", alert)
        self.assertIn('CommandHandler("alert_submit", alert_submit_cmd)', run_bot)

    def test_excel_only_mode_removes_map_dashboard_and_png_wait(self):
        handlers = _source("app/bot/handlers.py")
        run_bot = _source("app/bot/run_bot.py")
        self.assertNotIn('CommandHandler("map"', run_bot)
        self.assertNotIn('CommandHandler("dashboard"', run_bot)
        self.assertNotIn("excel_to_png", handlers)
        self.assertNotIn("Creating PNG preview", handlers)

    def test_daily_export_does_not_reload_stale_wide_table(self):
        body = _function_source(
            "app/reports/movement_exports.py", "create_daily_export"
        )
        self.assertIn("wide_map = {}", body)
        self.assertNotIn("load_wide_payloads(rows)", body)


if __name__ == "__main__":
    unittest.main()
