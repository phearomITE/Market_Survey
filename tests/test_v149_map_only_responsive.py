from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_map_assets_exist_and_outlet_list_is_removed():
    html = read("app/web/map.html")
    assert 'id="map"' in html
    assert 'id="filterPanel"' in html
    assert "OUTLET LIST" not in html
    assert "OUTLET & PRODUCT LIST" not in html
    assert "dashboard" not in html.lower()


def test_map_uses_fast_mobile_rendering():
    javascript = read("app/web/map.js")
    router = read("app/web/router.py")
    assert "preferCanvas:true" in javascript
    assert "L.circleMarker" in javascript
    assert "updateWhenZooming:false" in javascript
    assert "zoomAnimation:!isPhone" in javascript
    assert "marker_limit = 220 if mobile else 900" in router


def test_map_has_responsive_controls_and_score_details():
    html = read("app/web/map.html")
    css = read("app/web/map.css")
    javascript = read("app/web/map.js")
    for field in ("region", "dealer", "reportDate", "province", "district", "commune", "category", "product", "movement"):
        assert f'id="{field}"' in html
    assert "@media(max-width:900px)" in css
    assert "Movement Rating" in javascript
    assert "google.com/maps/dir" in javascript


def test_only_map_command_is_registered():
    handlers = read("app/bot/handlers.py")
    runner = read("app/bot/run_bot.py")
    assert 'CommandHandler("map", map_cmd)' in runner
    assert 'CommandHandler("dashboard"' not in runner
    assert "/dashboard" not in handlers
