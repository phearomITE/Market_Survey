from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_alert_handler_imports_datetime_and_supports_date():
    source = (ROOT / "app/bot/handlers.py").read_text(encoding="utf-8")
    assert "from datetime import datetime" in source
    assert "len(context.args) not in {1, 2}" in source
    assert 'datetime.strptime(context.args[1], "%Y-%m-%d")' in source


def test_status_export_does_not_create_excel_table():
    source = (
        ROOT / "app/reports/submission_status_export.py"
    ).read_text(encoding="utf-8")
    assert "sheet.auto_filter.ref = sheet.dimensions" in source
    assert "sheet.add_table" not in source
    assert "TableStyleInfo" not in source


def test_export_status_is_registered_cumulatively():
    handlers = (ROOT / "app/bot/handlers.py").read_text(encoding="utf-8")
    runner = (ROOT / "app/bot/run_bot.py").read_text(encoding="utf-8")
    assert "async def export_status_cmd" in handlers
    assert 'CommandHandler("export_status", export_status_cmd)' in runner
