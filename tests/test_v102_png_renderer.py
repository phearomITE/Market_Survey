from pathlib import Path
import unittest


class V102PngRendererTests(unittest.TestCase):
    def test_docker_installs_and_checks_renderer(self):
        source = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn("libreoffice-calc", source)
        self.assertIn("fonts-khmeros", source)
        self.assertIn("test -x /usr/bin/soffice", source)

    def test_renderer_uses_isolated_profile_and_calc_export(self):
        source = Path("app/services/render_service.py").read_text(encoding="utf-8")
        self.assertIn("UserInstallation=", source)
        self.assertIn("pdf:calc_pdf_Export", source)
        self.assertIn("TemporaryDirectory", source)
        self.assertIn("get_last_render_error", source)


if __name__ == "__main__":
    unittest.main()
