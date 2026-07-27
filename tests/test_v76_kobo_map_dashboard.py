from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_map_dashboard_assets_exist():
    for relative in (
        "app/web/__init__.py",
        "app/web/router.py",
        "app/web/map.html",
        "app/web/map.css",
        "app/web/map.js",
    ):
        assert (ROOT / relative).is_file()


def test_bot_registers_viewer_commands():
    run_bot = (ROOT / "app/bot/run_bot.py").read_text(encoding="utf-8")
    assert 'CommandHandler("map", map_cmd)' in run_bot
    assert 'CommandHandler("dashboard", dashboard_cmd)' in run_bot
    assert 'loop="asyncio"' in run_bot


def test_main_mounts_web_router():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "app.include_router(web_router)" in main


def test_map_uses_raw_product_ratings():
    router = (ROOT / "app/web/router.py").read_text(encoding="utf-8")
    assert '"movement": score' in router
    assert '"product_type": product_type' in router
    assert '"own_wins"' in router
