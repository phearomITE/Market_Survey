from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from app.reports.excel_report import SUMMARY_FONT_NAME, _normalize_khmer_cells


def test_khmer_cluster_cleanup_and_libreoffice_font():
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "គ្\u200bរប់"
    _normalize_khmer_cells(sheet)
    assert sheet["A1"].value == "គ្រប់"
    assert sheet["A1"].font.name == "Khmer OS System"
    assert SUMMARY_FONT_NAME == "Khmer OS System"


def test_map_router_is_included_and_web_server_started():
    main_source = Path("app/main.py").read_text(encoding="utf-8")
    bot_source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
    router_source = Path("app/web/router.py").read_text(encoding="utf-8")
    assert "app.include_router(web_router)" in main_source
    assert '@router.get("/map"' in router_source
    assert "_start_web_server()" in bot_source
    assert '"app.main:app"' in bot_source


def test_region_subtotal_counts_dealers_by_band():
    source = Path("app/reports/summary_report.py").read_text(encoding="utf-8")
    assert 'sum(score < 5 for score in region_scores)' in source
    assert 'sum(5 <= score <= 8 for score in region_scores)' in source
    assert 'sum(score >= 9 for score in region_scores)' in source
