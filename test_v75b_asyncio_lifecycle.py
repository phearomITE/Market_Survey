from __future__ import annotations

import ast
import re
from pathlib import Path


def test_railway_uses_managed_asyncio_lifecycle():
    source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
    ast.parse(source)

    assert "async def _run_application(" in source
    assert "asyncio.run(_run_application(app))" in source
    assert not re.search(
        r"(?m)^[ \t]*app\.run_polling\(",
        source,
    )

    for required in (
        "await app.initialize()",
        "await app.updater.start_polling()",
        "await app.start()",
        "await app.updater.stop()",
        "await app.stop()",
        "await app.shutdown()",
    ):
        assert required in source
