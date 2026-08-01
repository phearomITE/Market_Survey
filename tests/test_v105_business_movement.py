from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
import importlib.util
import sys
import unittest


def _load_aggregator():
    sqlalchemy = ModuleType("sqlalchemy")
    sqlalchemy.text = lambda statement: statement
    database = ModuleType("app.db.database")
    database.SessionLocal = None
    sys.modules["sqlalchemy"] = sqlalchemy
    sys.modules["app.db.database"] = database

    path = Path("app/reports/aggregator.py")
    spec = importlib.util.spec_from_file_location("v105_aggregator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class V105BusinessMovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aggregator = _load_aggregator()

    def _score_group(self, values_by_product, total_outlets):
        result = {"products": {}, "competitors": {}}
        for product, values in values_by_product.items():
            bucket = "products" if product == "CAMBODIA ED" else "competitors"
            result[bucket][product] = self.aggregator.coverage_movement_stats(
                values, total_outlets
            )
        self.aggregator._apply_offtake_comparison_goal(result)
        return {
            product: result[
                "products" if product == "CAMBODIA ED" else "competitors"
            ][product]["mov"]
            for product in values_by_product
        }

    def test_ksa5_total_18_has_one_goal_10(self):
        scores = self._score_group(
            {
                "CAMBODIA ED": [4, 8] + ([9] * 7) + ([10] * 8),
                "King Kong": [3, 4, 4, 4, 7],
                "AIRA": [3, 3, 3, 3, 4, 4, 4, 6, 7, 7],
            },
            18,
        )
        self.assertEqual(
            scores,
            {"CAMBODIA ED": 10, "King Kong": 2, "AIRA": 3},
        )
        self.assertEqual(list(scores.values()).count(10), 1)

    def test_str3_total_32_has_one_goal_10(self):
        scores = self._score_group(
            {
                "CAMBODIA ED": (
                    [3, 3, 4, 4]
                    + ([5] * 8)
                    + ([6] * 8)
                    + [7, 7, 8]
                    + ([10] * 4)
                ),
                "Super Boostrong": [2] + ([3] * 4) + ([4] * 5) + [5, 5, 7],
                "King Kong": [2] + ([3] * 5) + ([4] * 5) + ([5] * 6) + [6, 6],
                "AIRA": [2, 2],
            },
            32,
        )
        self.assertEqual(
            scores,
            {
                "CAMBODIA ED": 10,
                "Super Boostrong": 4,
                "King Kong": 5,
                "AIRA": 2,
            },
        )
        self.assertEqual(list(scores.values()).count(10), 1)

    def test_blank_product_movement_defaults_to_one(self):
        stats = self.aggregator.coverage_movement_stats([], 20)
        self.assertEqual(stats["mov"], 1)
        self.assertEqual(stats["_mov_effective"], 1)
        self.assertEqual(stats["_movement_points"], 20)

    def test_zero_product_movement_defaults_to_one(self):
        stats = self.aggregator.coverage_movement_stats([0, 0, 5], 5)
        self.assertEqual(stats["_movement_points"], 9)
        self.assertEqual(stats["_mov_effective"], 1.8)
        self.assertEqual(stats["mov"], 2)

    def test_total_outlets_equals_submissions_minus_summary_rows(self):
        def submission(index, outlet_name):
            return SimpleNamespace(
                id=index,
                submission_id="",
                dealer="D1",
                region="R1",
                report_date=None,
                group_no=1,
                member_no=1,
                location_text="Phnom Penh",
                outlet_name=outlet_name,
                outlet_type="Drink Shop",
                product_metrics=[],
                competitor_metrics=[],
                ring_pull_metrics=[],
                key_issue_text="",
                suggestion_text="",
            )

        result = self.aggregator.aggregate_submissions(
            [
                submission(1, "Outlet A"),
                submission(2, "Outlet A"),
                submission(3, "Outlet B"),
                submission(4, "បូកសរុបរួម"),
            ],
            wide_map={},
        )
        self.assertEqual(result["total_submissions"], 4)
        self.assertEqual(result["summary_control_count"], 1)
        self.assertEqual(result["total_outlets"], 3)
        self.assertEqual(result["products"]["CAMBODIA ED"]["_movement_points"], 3)

    def test_combined_summary_outlet_marker_is_excluded(self):
        self.assertTrue(
            self.aggregator.is_final_summary_outlet_name(" បូកសរុបរួម ")
        )
        self.assertFalse(
            self.aggregator.is_final_summary_outlet_name(
                "Outlet បូកសរុបរួម Shop"
            )
        )

    def test_every_gt_and_horeca_comparison_product_is_registered(self):
        registered = set(self.aggregator.ALL_OWN_PRODUCTS)
        registered.update(self.aggregator.ALL_COMPETITOR_PRODUCTS)
        missing = {
            product
            for group in self.aggregator.OFFTAKE_COMPARE_GROUPS
            for product in group
            if product not in registered
        }
        self.assertEqual(missing, set())

    def test_exprez_can_is_available_in_freshness_and_comparison(self):
        self.assertIn("EXPREZ Can 330ml", self.aggregator.OWN_PRODUCTS)
        self.assertIn("EXPREZ Can 330ml", self.aggregator.COMPETITOR_PRODUCTS)
        self.assertIn("EXPREZ Can 330ml", self.aggregator.PRODUCT_CODES)
        self.assertIn("EXPREZ Can 330ml", self.aggregator.COMPETITOR_CODES)

    def test_summary_leader_requires_exact_final_ten(self):
        source = Path("app/reports/summary_report.py").read_text(encoding="utf-8")
        self.assertIn('.get("mov") == 10', source)

    def test_horeca_summary_uses_horeca_movement_group(self):
        source = Path("app/reports/summary_report.py").read_text(encoding="utf-8")
        self.assertIn('"own": "CBL Pint"', source)
        self.assertIn('"Tiger Crystal Pint"', source)
        self.assertIn('"HANUMAN LITE Pint"', source)
        self.assertIn('"Vathanac LITE Pint"', source)
        self.assertIn('report_type in {"GT", "HORECA"}', source)

    def test_combined_raw_command_is_registered(self):
        source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
        self.assertIn('CommandHandler("raw_movement",', source)
        self.assertNotIn('CommandHandler("raw_movement_gt"', source)
        self.assertNotIn('CommandHandler("raw_movement_horeca"', source)

    def test_all_horeca_template_products_use_movement_flow(self):
        expected = {
            "CB Pint",
            "Angkor Pint",
            "Tiger Pint",
            "CBL Pint",
            "CB SUPEEME Pint",
            "Tiger Crystal Pint",
            "HANUMAN LITE Pint",
            "Vathanac LITE Pint",
            "CB Black Pint",
            "ABC Pint",
            "HANUMAN Black Pint",
            "Dragon Pint",
            "CB LITE ORD",
            "GB SNOW ORD",
            "HANUMAN LITE ORD",
            "Krud LITE ORD",
            "CBC 4.4 NCP",
            "CB Original NCP",
            "GB Original NCP",
            "Krud NCP",
            "CB LITE NCP",
            "GB SNOW NCP",
            "Hanuman LITE NCP",
            "Krud LITE NCP",
            "Greet LITE NCP",
            "CB BLACK NCP",
            "Hanuman Black NCP",
            "CAMBODIA COLA",
            "Coca Cola 330ml",
            "V Cola 330ml",
            "WURKZ",
            "Boostrong",
            "Krud ED",
            "CAMBODIA ED",
            "Super Boostrong",
            "King Kong",
            "AIRA",
            "DAZZ",
            "BACCHUSE",
            "Dragon",
            "DAZZ Zero Sugar",
            "BACCHUSE Sugar Free",
            "EXPREZ Melon",
            "EXPREZ Can 330ml",
            "Sting Can 330ml",
            "Idol Can 330ml",
            "CAMBODIA Sport 300mL",
            "CAMBODIA Sport 500mL",
            "Pocari Sweat",
            "V-Active Sport",
            "CAMBODIA WATER 500mL",
            "Vital 500mL",
            "Provida 500mL",
            "Ganzberg 500ml",
            "Hitech 500mL",
        }
        registered = set(self.aggregator.HORECA_OWN_PRODUCTS)
        registered.update(self.aggregator.HORECA_COMPETITOR_PRODUCTS)
        self.assertEqual(registered, expected)
        for product in self.aggregator.HORECA_OWN_PRODUCTS:
            self.assertIn(product, self.aggregator.PRODUCT_CODES)
        for product in self.aggregator.HORECA_COMPETITOR_PRODUCTS:
            self.assertIn(product, self.aggregator.COMPETITOR_CODES)

    def test_wide_data_is_loaded_with_one_bulk_query(self):
        source = Path("app/reports/aggregator.py").read_text(encoding="utf-8")
        loader = source[source.index("def load_wide_payloads"):source.index(
            "def _wide_payload_for_submission"
        )]
        self.assertIn("ANY(:ids)", loader)
        self.assertEqual(loader.count("SELECT * FROM public.kobo_submissions_wide"), 1)


if __name__ == "__main__":
    unittest.main()
