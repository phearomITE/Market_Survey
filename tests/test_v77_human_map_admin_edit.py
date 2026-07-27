from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_zero_ratings_are_hidden_and_raw_ratings_remain():
    router = read("app/web/router.py")
    assert "int(metric.movement_score) <= 0" in router
    assert '"movement": score' in router

def test_administrative_fields_and_filters_exist():
    models = read("app/db/models.py")
    router = read("app/web/router.py")
    html = read("app/web/map.html")
    for name in ("province", "district", "commune", "village"):
        assert name in models
        assert name in router
    for element in ('id="province"', 'id="district"', 'id="commune"'):
        assert element in html

def test_editing_requires_separate_editor_token():
    router = read("app/web/router.py")
    assert "def _authorize_edit" in router
    assert "Depends(_authorize_edit)" in router
    assert "Field(ge=0, le=10)" in router

def test_reverse_geocoding_is_throttled_and_cached():
    geocode = read("app/web/geocode.py")
    assert "time.sleep(1.05)" in geocode
    assert "row.province =" in geocode
