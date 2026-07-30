from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_only_approved_production_dates_are_queried():
    router = read("app/web/router.py")
    assert "APPROVED_REPORT_DATES" in router
    assert "date(2026, 7, 4)" in router
    assert "date(2026, 7, 18)" in router
    assert "date(2026, 7, 25)" in router
    assert "KoboSubmission.report_date.in_(APPROVED_REPORT_DATES)" in router


def test_outlet_product_details_obey_active_filters():
    router = read("app/web/router.py")
    javascript = read("app/web/map.js")
    assert "category: list[str] = Query(default=[])" in router
    assert 'row["category"] in category' in router
    assert "ratings?${params()}" in javascript


def test_phone_map_uses_small_payload_and_low_cost_animation():
    router = read("app/web/router.py")
    javascript = read("app/web/map.js")
    assert "marker_limit = 60 if mobile else 700" in router
    assert "zoomAnimation: !isPhone" in javascript
    assert "updateWhenZooming: false" in javascript
    assert "radius: isPhone ? 18000 : 8000" in javascript
