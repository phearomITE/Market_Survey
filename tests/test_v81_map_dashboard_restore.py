from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_bot_registers_map_dashboard_and_export_commands():
    handlers = read("app/bot/handlers.py")
    runner = read("app/bot/run_bot.py")
    assert "async def map_cmd" in handlers
    assert "async def dashboard_cmd" in handlers
    assert "async def export_cmd" in handlers
    assert 'CommandHandler("map", map_cmd)' in runner
    assert 'CommandHandler("dashboard", dashboard_cmd)' in runner
    assert 'CommandHandler("export", export_cmd)' in runner


def test_web_routes_and_responsive_viewer_are_present():
    main = read("app/main.py")
    router = read("app/web/router.py")
    html = read("app/web/map.html")
    css = read("app/web/map.css")
    javascript = read("app/web/map.js")
    assert "app.include_router(web_router)" in main
    assert '@router.get("/map"' in router
    assert '@router.get("/dashboard"' in router
    assert '@router.get("/api/map/data")' in router
    assert "Open Map" in read("app/bot/handlers.py")
    assert "viewport-fit=cover" in html
    assert "@media(max-width:900px)" in css
    assert "score-marker" in javascript
    assert "dashboardFilters" in javascript


def test_schema_supports_administrative_location_fields():
    models = read("app/db/models.py")
    database = read("app/db/database.py")
    for field in ("province", "district", "commune", "village"):
        assert f"{field}:" in models
        assert f'("{field}"' in database
