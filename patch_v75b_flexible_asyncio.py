#!/usr/bin/env python3
"""Flexible Railway asyncio patch for KB Market Survey.

Supports both:
    def main():
and:
    def main() -> None:

It preserves existing map/dashboard startup and all command registrations.
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
    fail(f"Run this script from the project root. Missing: {TARGET}")

source = TARGET.read_text(encoding="utf-8")
original = source

# Ensure signal is imported for graceful Railway shutdown.
if not re.search(r"^import signal\s*$", source, flags=re.MULTILINE):
    asyncio_import = re.search(
        r"^import asyncio\s*$",
        source,
        flags=re.MULTILINE,
    )
    if not asyncio_import:
        fail("Could not find 'import asyncio' in app/bot/run_bot.py")

    insert_at = asyncio_import.end()
    source = source[:insert_at] + "\nimport signal" + source[insert_at:]

runner = '''

async def _run_application(app: Application) -> None:
    """Run Telegram polling inside one active asyncio event loop."""
    if app.updater is None:
        raise RuntimeError("Telegram application has no updater")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_shutdown() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown)
        except (NotImplementedError, RuntimeError):
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
'''

# Insert before any top-level main declaration:
# def main():
# def main() -> None:
if "async def _run_application(" not in source:
    main_match = re.search(
        r"(?m)^def\s+main\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:",
        source,
    )
    if not main_match:
        fail(
            "Could not find a top-level main function. "
            "Search app/bot/run_bot.py for 'run_polling' and send that section."
        )

    source = source[:main_match.start()] + runner + "\n\n" + source[main_match.start():]

# Replace executable run_polling calls but do not alter comments/docstrings.
run_polling_pattern = re.compile(
    r"(?m)^(?P<indent>[ \t]*)app\.run_polling\((?P<args>[^\n]*)\)\s*$"
)

source, replacement_count = run_polling_pattern.subn(
    lambda match: f"{match.group('indent')}asyncio.run(_run_application(app))",
    source,
)

if replacement_count == 0:
    if "asyncio.run(_run_application(app))" in source:
        print("run_bot.py already uses asyncio.run lifecycle.")
    else:
        fail(
            "Could not find an executable app.run_polling(...) line "
            "in app/bot/run_bot.py."
        )

backup = TARGET.with_suffix(".py.v75b_backup")

if source != original:
    backup.write_text(original, encoding="utf-8")
    TARGET.write_text(source, encoding="utf-8")
    print(f"Patched: {TARGET}")
    print(f"Backup: {backup}")
else:
    print("No changes required; file already patched.")

py_compile.compile(str(TARGET), doraise=True)

updated = TARGET.read_text(encoding="utf-8")

if re.search(r"(?m)^[ \t]*app\.run_polling\(", updated):
    fail("An executable app.run_polling(...) line still remains.")

if "asyncio.run(_run_application(app))" not in updated:
    fail("asyncio.run lifecycle was not installed.")

print("Python syntax: OK")
print("Executable run_polling removed: OK")
print("asyncio.run lifecycle installed: OK")
