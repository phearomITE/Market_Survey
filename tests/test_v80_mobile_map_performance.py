from pathlib import Path


def test_large_json_responses_are_compressed():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert "GZipMiddleware" in source
    assert "minimum_size=1000" in source


def test_mobile_payload_has_safe_limits():
    source = Path("app/web/router.py").read_text(encoding="utf-8")
    assert "marker_limit = 500 if mobile else 1200" in source
    assert "row_limit = 100 if mobile else 300" in source
    assert 'mobile: bool = False' in source


def test_marker_product_details_are_loaded_on_demand():
    router = Path("app/web/router.py").read_text(encoding="utf-8")
    js = Path("app/web/map.js").read_text(encoding="utf-8")
    assert '@router.get("/api/map/outlets/{submission_id}/ratings")' in router
    assert "loadOutletRatings(row)" in js
    assert "requestAnimationFrame(renderBatch)" in js


def test_blank_admin_locations_are_reverse_geocoded():
    source = Path("app/web/geocode.py").read_text(encoding="utf-8")
    assert 'KoboSubmission.province == ""' in source
    assert 'KoboSubmission.district == ""' in source


def test_mobile_filter_drawer_supports_touch_scrolling():
    css = Path("app/web/map.css").read_text(encoding="utf-8")
    assert "-webkit-overflow-scrolling:touch" in css
    assert "touch-action:pan-y" in css
