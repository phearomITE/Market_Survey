from pathlib import Path
from types import ModuleType
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
