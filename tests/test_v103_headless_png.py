from pathlib import Path
import unittest


class V103HeadlessPngTests(unittest.TestCase):
    def test_renderer_uses_virtual_headless_backend(self):
        source = Path("app/services/render_service.py").read_text(encoding="utf-8")
        self.assertIn('"SAL_USE_VCLPLUGIN": "svp"', source)
        self.assertNotIn('"SAL_USE_VCLPLUGIN": "gen"', source)

    def test_docker_checks_soffice_headless_backend(self):
        source = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn("test -x /usr/bin/soffice", source)
        self.assertIn("SAL_USE_VCLPLUGIN=svp", source)

    def test_combined_web_and_bot_launcher_is_preserved(self):
        self.assertTrue(Path("app/launcher.py").exists())
        self.assertIn("app.launcher", Path("railway.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
