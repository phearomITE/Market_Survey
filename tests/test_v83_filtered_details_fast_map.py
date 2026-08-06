from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_map_supports_real_report_date_filtering():
    router = read("app/web/router.py")
    assert "date.fromisoformat(value)" in router
    assert "KoboSubmission.report_date.in_(parsed_dates)" in router


def test_outlet_product_details_obey_active_filters():
    router = read("app/web/router.py")
    javascript = read("app/web/map.js")
    assert "category: list[str] = Query(default=[])" in router
    assert 'row["category"] in category' in router
    assert "ratings?${requestParams()}" in javascript


def test_phone_map_uses_small_payload_and_low_cost_animation():
    router = read("app/web/router.py")
    javascript = read("app/web/map.js")
    assert "marker_limit = 250 if mobile else 1200" in router
    assert "zoomAnimation:!isPhone" in javascript
    assert "updateWhenZooming:false" in javascript
    assert "preferCanvas:true" in javascript
    assert "L.circleMarker" in javascript


def test_map_is_map_only_without_outlet_table_or_dashboard():
    html = read("app/web/map.html")
    javascript = read("app/web/map.js")
    assert "OUTLET LIST" not in html
    assert "OUTLET & PRODUCT LIST" not in html
    assert "dashboard" not in html.lower()
    assert "renderDashboard" not in javascript
