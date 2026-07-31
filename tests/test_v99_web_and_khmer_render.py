from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_railway_entrypoint_starts_uvicorn_on_port():
    source = (ROOT / "app" / "bot" / "run_bot.py").read_text(encoding="utf-8")
    assert 'os.getenv("PORT", "8080")' in source
    assert '"app.main:app"' in source
    assert "uvicorn.run(" in source
    assert "threading.Thread(" in source


def test_khmer_render_copy_is_used_without_changing_source_workbook():
    source = (ROOT / "app" / "services" / "render_service.py").read_text(encoding="utf-8")
    assert "_create_khmer_safe_render_copy" in source
    assert 'PNG_KHMER_FONT_NAME", "Khmer OS"' in source
    assert 'prefix="kb-khmer-render-"' in source


def test_container_installs_khmer_shaping_fonts_and_locale():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "fonts-khmeros" in dockerfile
    assert "libreoffice-l10n-km" in dockerfile
    assert "km_KH.UTF-8" in dockerfile
