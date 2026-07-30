from pathlib import Path


def test_run_bot_starts_map_web_server():
    source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
    assert "def _start_web_server()" in source
    assert 'uvicorn.run(' in source
    assert "_start_web_server()" in source


def test_map_dashboard_assets_exist():
    assert Path("app/web/map.html").is_file()
    assert Path("app/web/map.css").is_file()
    assert Path("app/web/map.js").is_file()


def test_fastapi_mounts_web_router():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert "app.include_router(web_router)" in source


def test_horeca_report_header_has_no_channel_specialist_label():
    source = Path("app/reports/excel_report.py").read_text(encoding="utf-8")
    assert 'ws["A3"]' in source
    assert "CHANNEL SPECIALIST" not in source
