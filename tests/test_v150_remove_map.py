from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_map_command_and_help_are_removed():
    handlers = read("app/bot/handlers.py")
    runner = read("app/bot/run_bot.py")
    assert "map_cmd" not in handlers
    assert "map_cmd" not in runner
    assert 'CommandHandler("map"' not in runner
    assert "/map" not in handlers


def test_map_router_and_settings_are_removed():
    main = read("app/main.py")
    config = read("app/core/config.py")
    env_example = read(".env.example")
    assert "app.web" not in main
    assert "include_router" not in main
    assert "map_viewer_token" not in config
    assert "map_editor_token" not in config
    assert "MAP_VIEWER_TOKEN" not in env_example


def test_map_assets_are_removed():
    assert not (ROOT / "app/web").exists()
