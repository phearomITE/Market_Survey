from __future__ import annotations

import ast
from pathlib import Path


def _top_level_function_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_map_dashboard_handlers_exist():
    source = Path("app/bot/handlers.py").read_text(encoding="utf-8")
    names = _top_level_function_names(source)

    assert "map_cmd" in names
    assert "dashboard_cmd" in names
    assert "InlineKeyboardButton" in source
    assert "InlineKeyboardMarkup" in source
    assert '"/map"' in source
    assert '"/dashboard"' in source


def test_handler_and_run_bot_syntax():
    handlers_source = Path("app/bot/handlers.py").read_text(encoding="utf-8")
    run_source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")

    ast.parse(handlers_source)
    ast.parse(run_source)
