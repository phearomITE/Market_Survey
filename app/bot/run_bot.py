from __future__ import annotations

import asyncio
import signal
from datetime import datetime
import os
import threading
from urllib.parse import urlsplit

import uvicorn
from telegram.ext import Application, CommandHandler

from app.bot.handlers import (
    debug_kobo_cmd,
    dashboard_cmd,
    help_cmd,
    map_cmd,
    report_cmd,
    report_multi_cmd,
    report_today_cmd,
    summary_cmd,
    start,
    status_cmd,
    sync_kobo_cmd,
)
from app.core.config import settings
from app.db.database import init_db
from app.kobo.sync import sync_kobo


_auto_sync_task: asyncio.Task | None = None
_last_auto_sync: dict | None = None
_web_thread: threading.Thread | None = None


def _run_web_server() -> None:
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")


def _start_web_server() -> None:
    global _web_thread
    if _web_thread and _web_thread.is_alive():
        return
    _web_thread = threading.Thread(target=_run_web_server, name="movement-map-web", daemon=True)
    _web_thread.start()
    print(f"🌐 Movement map web server starting on PORT={os.getenv('PORT', '8000')}")


async def _auto_sync_loop() -> None:
    """Polling option for local testing: pull Kobo every N minutes.

    This makes new Kobo submissions insert into PostgreSQL automatically
    without manually running: python -m app.kobo.sync
    """
    global _last_auto_sync

    # Local polling: check Kobo frequently without overlapping sync jobs.
    # Prefer AUTO_SYNC_INTERVAL_SECONDS=60. Falls back to minutes for old .env files.
    interval_seconds = int(getattr(settings, "auto_sync_interval_seconds", 0) or 0)
    if interval_seconds <= 0:
        interval_seconds = int(settings.auto_sync_interval_minutes or 1) * 60
    interval_seconds = max(60, interval_seconds)
    print(f"🔄 Auto Kobo sync enabled: every {interval_seconds} seconds")

    # Run once shortly after startup, then every interval.
    await asyncio.sleep(3)
    while True:
        try:
            started = datetime.now()
            result = await asyncio.to_thread(sync_kobo)
            _last_auto_sync = {"time": started, "result": result, "error": None}
            print(
                f"✅ Auto sync done at {started:%Y-%m-%d %H:%M:%S}: "
                f"fetched={result.get('fetched')} synced={result.get('synced')} skipped={result.get('skipped')}"
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _last_auto_sync = {"time": datetime.now(), "result": None, "error": str(exc)}
            print(f"⚠️ Auto sync failed: {exc}")

        await asyncio.sleep(interval_seconds)


async def _post_init(app: Application) -> None:
    global _auto_sync_task
    if settings.auto_sync_enabled:
        _auto_sync_task = asyncio.create_task(_auto_sync_loop())


async def _post_shutdown(app: Application) -> None:
    global _auto_sync_task
    if _auto_sync_task:
        _auto_sync_task.cancel()
        try:
            await _auto_sync_task
        except asyncio.CancelledError:
            pass


def _safe_database_target() -> str:
    try:
        parsed = urlsplit(settings.db_url.replace("postgresql+psycopg://", "postgresql://", 1))
        return f"{parsed.hostname or 'unknown'}:{parsed.port or 5432}/{(parsed.path or '/').lstrip('/')}"
    except Exception:
        return "configured database"




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


def main():
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    if not settings.kobo_token or not settings.kobo_asset_uid:
        raise RuntimeError("KOBO_TOKEN or KOBO_ASSET_UID is missing")

    print(f"🚀 Environment: {settings.app_env}")
    print(f"🗄️ Database target: {_safe_database_target()}")
    print(f"📄 Template: {settings.template_file}")
    print(f"📁 Export directory: {settings.export_path}")

    init_db()
    _start_web_server()

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    # Expose sync status to handlers without import cycle.
    app.bot_data["get_last_auto_sync"] = lambda: _last_auto_sync

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("sync_kobo", sync_kobo_cmd))
    app.add_handler(CommandHandler("debug_kobo", debug_kobo_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("report_multi", report_multi_cmd))
    app.add_handler(CommandHandler("report5", report_multi_cmd))
    app.add_handler(CommandHandler("report_today", report_today_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("map", map_cmd))
    app.add_handler(CommandHandler("dashboard", dashboard_cmd))

    print("✅ KB Market Survey Bot running...")
    asyncio.run(_run_application(app))
if __name__ == "__main__":
    main()
