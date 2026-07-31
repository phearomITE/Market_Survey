from pathlib import Path
import unittest

from app.kobo.parser import normalize_submission


class V101RegressionTests(unittest.TestCase):
    def test_location_fields_are_normalized_for_map(self):
        data = normalize_submission({
            "_id": "v101-test",
            "report_date": "2026-07-31",
            "province": "Phnom Penh",
            "district": "Dangkao",
            "commune": "Prey Sa",
            "village": "Test Village",
            "gps_latitude": "11.50",
            "gps_longitude": "104.90",
        })
        self.assertEqual(data["province"], "Phnom Penh")
        self.assertEqual(data["district"], "Dangkao")
        self.assertEqual(data["commune"], "Prey Sa")
        self.assertEqual(data["village"], "Test Village")
        self.assertEqual(data["gps_latitude"], 11.5)
        self.assertEqual(data["gps_longitude"], 104.9)

    def test_zero_movement_and_khmer_status_are_exposed(self):
        router_source = Path("app/web/router.py").read_text(encoding="utf-8")
        map_source = Path("app/web/map.js").read_text(encoding="utf-8")
        self.assertIn('if metric.movement_score is None:', router_source)
        self.assertIn('"sales_status": metric.status or ""', router_source)
        for status in ("អត់មានលក់", "មានលក់", "លក់ដាច់"):
            self.assertIn(status, map_source)

    def test_combined_railway_launcher(self):
        launcher = Path("app/launcher.py").read_text(encoding="utf-8")
        self.assertIn("await telegram.updater.start_polling", launcher)
        self.assertIn("uvicorn.Server", launcher)


if __name__ == "__main__":
    unittest.main()
