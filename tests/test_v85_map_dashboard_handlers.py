from pathlib import Path

from app.bot import handlers
from app.bot.run_bot import _build_application


def test_run_bot_imports_existing_map_handler():
    assert callable(handlers.map_cmd)


def test_application_registers_map_only_command(monkeypatch):
    monkeypatch.setattr(handlers.settings, "telegram_bot_token", "123456:TEST_TOKEN")
    app = _build_application()
    commands = {
        command
        for group in app.handlers.values()
        for handler in group
        for command in getattr(handler, "commands", set())
    }
    assert "map" in commands
    assert "dashboard" not in commands


def test_all_run_bot_handler_imports_exist():
    source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
    assert "map_cmd" in source


def test_fastapi_mounts_map_router():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert "from app.web.router import router as web_router" in source
    assert "app.include_router(web_router)" in source
