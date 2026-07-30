from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_map_is_map_only_and_mobile_summary_is_hidden():
    html = text("app/web/map.html")
    css = text("app/web/map.css")
    assert "OUTLET &amp; PRODUCT LIST" not in html
    assert ".stats{display:none}" in css


def test_api_supports_multi_filters_and_small_mobile_payload():
    router = text("app/web/router.py")
    assert "list[str] = Query(default=[])" in router
    assert "products_by_category" in router
    assert "marker_limit = 180 if mobile else 900" in router
    assert '"rows": []' in router


def test_map_uses_numbered_markers_and_movement_colored_areas():
    javascript = text("app/web/map.js")
    assert "score-marker" in javascript
    assert "L.circle(" in javascript
    assert '"#e5232e"' in javascript
    assert '"#f5b400"' in javascript
    assert '"#118a45"' in javascript
    assert "refreshProducts" in javascript
