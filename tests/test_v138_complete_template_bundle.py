import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class V138CompleteTemplateBundleTests(unittest.TestCase):
    def test_default_gt_template_is_current_general_template(self):
        config_source = (ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
        self.assertIn(
            'template_path: str = "templates/template_general.xlsx"',
            config_source,
        )
        self.assertTrue((TEMPLATES / "template_general.xlsx").exists())

    def test_both_kobo_form_filenames_are_the_current_form(self):
        self.assertEqual(
            _sha256(TEMPLATES / "KB_Market_Improvement_XLSForm.xlsx"),
            _sha256(TEMPLATES / "KB_Market_Improvement_XLSForm_GT_HORECA.xlsx"),
        )

    def test_legacy_report_template_names_are_synchronized(self):
        self.assertEqual(
            _sha256(TEMPLATES / "template_by_dealer.xlsx"),
            _sha256(TEMPLATES / "template_general.xlsx"),
        )
        self.assertEqual(
            _sha256(TEMPLATES / "template_horeca.xlsx"),
            _sha256(TEMPLATES / "template_horeca_products.xlsx"),
        )

    def test_every_required_template_is_present(self):
        required = {
            "KB_Market_Improvement_XLSForm.xlsx",
            "KB_Market_Improvement_XLSForm_GT_HORECA.xlsx",
            "template_by_dealer.xlsx",
            "template_general.xlsx",
            "template_gt_summary.xlsx",
            "template_horeca.xlsx",
            "template_horeca_products.xlsx",
        }
        self.assertEqual(set(path.name for path in TEMPLATES.glob("*.xlsx")), required)


if __name__ == "__main__":
    unittest.main()
