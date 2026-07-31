from pathlib import Path


def test_launcher_uses_asyncio_run_in_telegram_thread():
    source = Path("app/launcher.py").read_text(encoding="utf-8")
    assert "asyncio.run(run_bot_async())" in source
    assert 'name="telegram-bot"' in source
    assert 'uvicorn.run(' in source


def test_bot_uses_explicit_async_lifecycle_not_run_polling():
    source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
    assert "await app.initialize()" in source
    assert "await app.start()" in source
    assert "await updater.start_polling()" in source
    assert ".run_polling(" not in source


def test_railway_starts_combined_launcher():
    assert "python -m app.launcher" in Path("railway.json").read_text(encoding="utf-8")
    assert '"app.launcher"' in Path("Dockerfile").read_text(encoding="utf-8")
