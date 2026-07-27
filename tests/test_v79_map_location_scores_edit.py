from pathlib import Path


def test_map_list_contains_administrative_columns_and_action():
    html = Path("app/web/map.html").read_text(encoding="utf-8")
    assert "<th>Province</th><th>District</th>" in html
    assert "<th>Action</th>" in html


def test_map_markers_show_numeric_movement_score():
    js = Path("app/web/map.js").read_text(encoding="utf-8")
    assert 'class="score-marker ${row.band}">${row.movement}</span>' in js
    assert "L.divIcon" in js


def test_summary_replaces_ratings_with_location_counts():
    js = Path("app/web/map.js").read_text(encoding="utf-8")
    router = Path("app/web/router.py").read_text(encoding="utf-8")
    assert 's.regions,"Region"' in js
    assert 's.dealers,"Dealer"' in js
    assert 's.provinces,"Province"' in js
    assert 's.ratings,"Ratings"' not in js
    assert '"regions": len(' in router
    assert '"dealers": len(' in router
    assert '"provinces": len(' in router


def test_editor_link_enables_product_row_edit():
    js = Path("app/web/map.js").read_text(encoding="utf-8")
    assert "state.data.can_edit" in js
    assert 'data-edit-id="${esc(row.id)}"' in js
    assert "stock_status" in js
    assert "key_issue" in js
    assert "movement" in js


def test_reverse_geocoder_converts_gps_to_admin_fields():
    source = Path("app/web/geocode.py").read_text(encoding="utf-8")
    assert "row.province =" in source
    assert "row.district =" in source
    assert "row.commune =" in source
    assert "row.village =" in source
