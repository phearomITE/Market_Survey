#!/usr/bin/env python3
"""V75: replace python-telegram-bot run_polling with an asyncio.run lifecycle.

This patches only app/bot/run_bot.py and preserves existing imports,
commands, map/dashboard startup, alert logic, and background sync callbacks.
"""

from __future__ import annotations

from pathlib import Path
import py_compile
import re


ROOT = Path.cwd()
TARGET = ROOT / "app" / "bot" / "run_bot.py"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


if not TARGET.exists():
    fail(f"Run this script from the project root. Missing {TARGET}")

text = TARGET.read_text(encoding="utf-8")
original = text

# The new runner needs POSIX signal handling on Railway.
if not re.search(r"^import signal$", text, flags=re.MULTILINE):
    if re.search(r"^import asyncio$", text, flags=re.MULTILINE):
        text = re.sub(
            r"^import asyncio$",
            "import asyncio\nimport signal",
            text,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        fail("Could not find 'import asyncio' in run_bot.py")

runner = """

async def _run_application(app: Application) -> None:
    \"""Run Telegram polling inside the active asyncio loop.

    This avoids Application.run_polling(), which calls
    asyncio.get_event_loop() and can fail on Python 3.12 when another
    component such as Uvicorn/uvloop changes the global loop policy.
    \"""
    if app.updater is None:
        raise RuntimeError("Telegram application has no updater")

    stop_event = asyncio.Event()
    running_loop = asyncio.get_running_loop()

    def request_shutdown() -> None:
        stop_event.set()

    for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            running_loop.add_signal_handler(
                shutdown_signal,
                request_shutdown,
            )
        except (NotImplementedError, RuntimeError):
            # add_signal_handler is unavailable on some local platforms.
            pass

    initialized = False
    polling_started = False
    application_started = False

    try:
        await app.initialize()
        initialized = True

        if app.post_init is not None:
            await app.post_init(app)

        await app.updater.start_polling()
        polling_started = True

        await app.start()
        application_started = True

        print("✅ Telegram polling started")
        await stop_event.wait()

    finally:
        if polling_started and app.updater.running:
            await app.updater.stop()

        if application_started and app.running:
            await app.stop()

        if app.post_stop is not None:
            await app.post_stop(app)

        if initialized:
            await app.shutdown()

        if app.post_shutdown is not None:
            await app.post_shutdown(app)
"""

if "async def _run_application(app: Application)" not in text:
    marker = "\ndef main() -> None:"
    if marker not in text:
        fail("Could not find main() in app/bot/run_bot.py")
    text = text.replace(marker, runner + marker, 1)

# Replace the known Python 3.12 workaround block, if present.
old_block_pattern = re.compile(
    r"""
[ \t]*\#\s*Python\s+3\.12[^\n]*\n
[ \t]*event_loop\s*=\s*asyncio\.new_event_loop\(\)\s*\n
[ \t]*asyncio\.set_event_loop\(event_loop\)\s*\n
\s*
[ \t]*try:\s*\n
[ \t]*app\.run_polling\([^\n]*\)\s*\n
[ \t]*finally:\s*\n
[ \t]*if\s+not\s+event_loop\.is_closed\(\):\s*\n
[ \t]*event_loop\.close\(\)\s*
""",
    flags=re.VERBOSE,
)
text, count_old = old_block_pattern.subn(
    "\n    asyncio.run(_run_application(app))\n",
    text,
    count=1,
)

# Replace a plain run_polling call used by the map-enabled version.
if count_old == 0:
    plain_pattern = re.compile(
        r"^[ \t]*app\.run_polling\([^\n]*\)\s*$",
        flags=re.MULTILINE,
    )
    text, count_plain = plain_pattern.subn(
        "    asyncio.run(_run_application(app))",
        text,
        count=1,
    )
    if count_plain == 0 and "asyncio.run(_run_application(app))" not in text:
        fail("Could not find app.run_polling(...) to replace")

# Remove an obsolete event-loop creation immediately before the new runner.
text = re.sub(
    r"""
[ \t]*event_loop\s*=\s*asyncio\.new_event_loop\(\)\s*\n
[ \t]*asyncio\.set_event_loop\(event_loop\)\s*\n
(?=\s*asyncio\.run\(_run_application\(app\)\))
""",
    "",
    text,
    count=1,
    flags=re.VERBOSE,
)

if text == original:
    print("run_bot.py: already patched")
else:
    backup = TARGET.with_suffix(".py.v75_backup")
    backup.write_text(original, encoding="utf-8")
    TARGET.write_text(text, encoding="utf-8")
    print(f"Patched: {TARGET}")
    print(f"Backup: {backup}")

py_compile.compile(str(TARGET), doraise=True)

if "app.run_polling(" in text:
    fail("run_polling still exists after patch")
if "asyncio.run(_run_application(app))" not in text:
    fail("asyncio.run lifecycle was not installed")

print("Python syntax: OK")
print("run_polling removed: OK")
print("asyncio.run lifecycle installed: OK")
