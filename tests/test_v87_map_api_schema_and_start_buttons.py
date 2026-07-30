from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_map_schema_columns_are_present_and_migrated():
    models = (ROOT / "app/db/models.py").read_text(encoding="utf-8")
    database = (ROOT / "app/db/database.py").read_text(encoding="utf-8")

    for column in ("province", "district", "commune", "village"):
        assert f"{column}:" in models
        assert f'("{column}",' in database


def test_start_contains_real_map_and_dashboard_buttons():
    handlers = (ROOT / "app/bot/handlers.py").read_text(encoding="utf-8")

    assert "Open Movement Map" in handlers
    assert "Open Movement Dashboard" in handlers
    assert '_viewer_url("map")' in handlers
    assert '_viewer_url("dashboard")' in handlers


def test_movement_filter_values_match_api_ranges():
    html = (ROOT / "app/web/map.html").read_text(encoding="utf-8")

    assert 'value="1-4"' in html
    assert 'value="5-8"' in html
    assert 'value="9-10"' in html
    assert 'value="very-low"' not in html
