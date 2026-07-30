from __future__ import annotations

import ast
from pathlib import Path


def test_run_bot_uses_asyncio_run_lifecycle():
    path = Path("app/bot/run_bot.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "app.run_polling(" not in source
    assert "asyncio.run(_run_application(app))" in source

    async_functions = {
        node.name
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
    }
    assert "_run_application" in async_functions

    assert "await app.initialize()" in source
    assert "await app.updater.start_polling()" in source
    assert "await app.start()" in source
    assert "await app.updater.stop()" in source
    assert "await app.stop()" in source
    assert "await app.shutdown()" in source
