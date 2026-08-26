from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_map_query_aggregates_in_database_and_never_returns_table_rows():
    router = read("app/web/router.py")
    map_part = router.split('@router.get("/api/map/data")', 1)[1].split('@router.get("/api/map/outlets', 1)[0]
    assert "union_all(" in map_part
    assert "row_number().over(" in map_part
    assert '"rows": []' in map_part
    assert "selectinload(KoboSubmission.product_metrics)" not in map_part


def test_admin_location_is_stored_and_has_a_backfill_command():
    models = read("app/db/models.py")
    sync = read("app/kobo/sync.py")
    config = read("app/core/config.py")
    for field in ("province", "district", "commune", "village"):
        assert f"{field}: Mapped" in models
    assert "enrich_admin_location(data)" in sync
    assert "reverse_geocoding_user_agent" not in config.lower()
    assert (ROOT / "scripts/backfill_map_locations.py").exists()


def test_telegram_bad_gateway_is_handled_without_crashing():
    runner = read("app/bot/run_bot.py")
    assert "NetworkError" in runner
    assert "app.add_error_handler(_telegram_error_handler)" in runner
    assert "polling will retry" in runner


def test_map_assets_are_compressed_and_mobile_marker_count_is_bounded():
    assert "GZipMiddleware" in read("app/main.py")
    assert "marker_limit = 220 if mobile else 900" in read("app/web/router.py")
    javascript = read("app/web/map.js")
    assert "sessionStorage" in javascript
    assert "L.canvas" in javascript
