from pathlib import Path
import unittest

from openpyxl import Workbook
from openpyxl.styles import Font

from app.reports.excel_report import SUMMARY_FONT_NAME, _normalize_khmer_cells


class KhmerPngRegressionTests(unittest.TestCase):
    def test_khmer_cluster_is_normalized_and_theme_override_removed(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet["A1"] = "គ្\u200bរប់"
        sheet["A1"].font = Font(name="Calibri", scheme="minor")

        _normalize_khmer_cells(sheet)

        self.assertEqual(sheet["A1"].value, "គ្រប់")
        self.assertEqual(sheet["A1"].font.name, SUMMARY_FONT_NAME)
        self.assertIsNone(sheet["A1"].font.scheme)
        self.assertIsNone(sheet["A1"].font.charset)
        self.assertIsNone(sheet["A1"].font.family)

    def test_png_renderer_uses_private_profile_and_true_headless_backend(self):
        source = Path("app/services/render_service.py").read_text(encoding="utf-8")
        self.assertIn("UserInstallation", source)
        self.assertIn("SAL_USE_VCLPLUGIN", source)
        self.assertIn('environment.pop("DISPLAY", None)', source)
        self.assertIn("Noto Sans Khmer:lang=km", source)
        self.assertIn("pdf:calc_pdf_Export", source)


if __name__ == "__main__":
    unittest.main()
