from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

# The production image installs pydantic-settings from requirements.txt. Keep
# this renderer unit test runnable in lightweight developer environments too.
try:
    import pydantic_settings  # noqa: F401
except ModuleNotFoundError:
    config_stub = types.ModuleType("app.core.config")
    config_stub.settings = types.SimpleNamespace(libreoffice_path="")
    sys.modules["app.core.config"] = config_stub

from app.services import render_service


VALID_PDF = b"%PDF-1.4\n" + (b"0" * 100)


class V140RailwayPngRendererTests(unittest.TestCase):
    @staticmethod
    def _write_fake_pdf(command: list[str]) -> None:
        output_dir = Path(command[command.index("--outdir") + 1])
        xlsx_path = Path(command[-1])
        (output_dir / f"{xlsx_path.stem}.pdf").write_bytes(VALID_PDF)

    def test_primary_conversion_uses_private_profile_and_svp(self):
        calls: list[tuple[list[str], dict[str, str]]] = []

        def fake_run(command, **kwargs):
            calls.append((list(command), dict(kwargs["env"])))
            self._write_fake_pdf(list(command))
            return subprocess.CompletedProcess(command, 0, "converted", "")

        with tempfile.TemporaryDirectory() as temporary:
            xlsx = Path(temporary) / "Market_Improvement_CA7_2026-08-01.xlsx"
            xlsx.write_bytes(b"xlsx")
            with patch.object(render_service, "_find_soffice", return_value="/usr/bin/libreoffice"), patch.object(
                render_service.subprocess, "run", side_effect=fake_run
            ):
                pdf, error = render_service.excel_to_pdf_with_diagnostics(xlsx)

        self.assertIsNone(error)
        self.assertIsNotNone(pdf)
        self.assertTrue(any(arg.startswith("-env:UserInstallation=file:") for arg in calls[0][0]))
        self.assertEqual(calls[0][1].get("SAL_USE_VCLPLUGIN"), "svp")
        self.assertNotIn("DISPLAY", calls[0][1])

    def test_xvfb_fallback_runs_when_primary_creates_no_pdf(self):
        call_count = 0
        commands: list[list[str]] = []

        def fake_run(command, **kwargs):
            nonlocal call_count
            call_count += 1
            commands.append(list(command))
            if call_count == 1:
                return subprocess.CompletedProcess(command, 1, "", "X11 error: Can't open display")
            self._write_fake_pdf(list(command))
            return subprocess.CompletedProcess(command, 0, "converted", "")

        def fake_which(program: str):
            return "/usr/bin/xvfb-run" if program == "xvfb-run" else None

        with tempfile.TemporaryDirectory() as temporary:
            xlsx = Path(temporary) / "Market_Improvement_CA7_2026-08-01.xlsx"
            xlsx.write_bytes(b"xlsx")
            with patch.object(render_service, "_find_soffice", return_value="/usr/bin/libreoffice"), patch.object(
                render_service.shutil, "which", side_effect=fake_which
            ), patch.object(render_service.subprocess, "run", side_effect=fake_run):
                pdf, error = render_service.excel_to_pdf_with_diagnostics(xlsx)

        self.assertIsNone(error)
        self.assertIsNotNone(pdf)
        self.assertEqual(call_count, 2)
        self.assertEqual(commands[1][0], "/usr/bin/xvfb-run")

    def test_real_pdf_first_page_renders_to_png(self):
        try:
            import fitz
        except Exception as exc:  # pragma: no cover - requirements install PyMuPDF
            self.skipTest(str(exc))

        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "sample.pdf"
            png = Path(temporary) / "sample.png"
            document = fitz.open()
            page = document.new_page(width=400, height=200)
            page.insert_text((40, 80), "KB Market Improvement")
            document.save(str(pdf))
            document.close()

            result, error = render_service.pdf_first_page_to_png_with_diagnostics(pdf, png)

            self.assertIsNone(error)
            self.assertEqual(result, png)
            self.assertTrue(png.is_file())
            self.assertGreater(png.stat().st_size, 0)

    def test_railway_image_contains_both_headless_paths(self):
        root = Path(__file__).resolve().parents[1]
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("SAL_USE_VCLPLUGIN=svp", dockerfile)
        self.assertIn("xvfb", dockerfile)
        self.assertIn("xauth", dockerfile)
        self.assertIn("poppler-utils", dockerfile)

    def test_report_sends_excel_before_png_conversion(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "app" / "bot" / "handlers.py").read_text(encoding="utf-8")
        report_start = source.index("async def report_cmd")
        report_end = source.index("async def report_multi_cmd")
        report_source = source[report_start:report_end]
        first_upload = report_source.index("reply_document")
        png_conversion = report_source.index("excel_to_png_with_diagnostics")
        self.assertLess(first_upload, png_conversion)

    def test_example_environment_contains_no_live_tokens(self):
        root = Path(__file__).resolve().parents[1]
        example = (root / ".env.example").read_text(encoding="utf-8")
        self.assertIn("KOBO_TOKEN=replace_with_your_kobo_token", example)
        self.assertIn("TELEGRAM_BOT_TOKEN=replace_with_your_telegram_bot_token", example)


if __name__ == "__main__":
    unittest.main()
