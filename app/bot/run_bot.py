from __future__ import annotations

import asyncio
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
    start,
    status_cmd,
    summary_cmd,
    sync_kobo_cmd,
)
from app.core.config import settings
from app.db.database import init_db
from app.kobo.sync import sync_kobo


_auto_sync_task: asyncio.Task | None = None
_last_auto_sync: dict | None = None


async def _auto_sync_loop() -> None:
    """Pull Kobo submissions automatically at the configured interval."""
    global _last_auto_sync

    interval_seconds = int(
        getattr(settings, "auto_sync_interval_seconds", 0) or 0
    )

    if interval_seconds <= 0:
        interval_minutes = int(
            getattr(settings, "auto_sync_interval_minutes", 1) or 1
        )
        interval_seconds = interval_minutes * 60

    interval_seconds = max(60, interval_seconds)

    print(
        f"🔄 Auto Kobo sync enabled: every {interval_seconds} seconds"
    )

    # Allow the application to complete startup before the first sync.
    await asyncio.sleep(3)

    while True:
        try:
            started = datetime.now()
            result = await asyncio.to_thread(sync_kobo)
            if getattr(settings, "reverse_geocoding_enabled", False):
                from app.web.geocode import enrich_missing_administrative_locations
                enriched = await asyncio.to_thread(enrich_missing_administrative_locations)
                if enriched:
                    print(f"📍 GPS administration enriched: {enriched} outlets")

            _last_auto_sync = {
                "time": started,
                "result": result,
                "error": None,
            }

            print(
                f"✅ Auto sync done at {started:%Y-%m-%d %H:%M:%S}: "
                f"fetched={result.get('fetched')} "
                f"synced={result.get('synced')} "
                f"skipped={result.get('skipped')}"
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            _last_auto_sync = {
                "time": datetime.now(),
                "result": None,
                "error": str(exc),
            }

            print(f"⚠️ Auto sync failed: {exc}")

        await asyncio.sleep(interval_seconds)


async def _post_init(app: Application) -> None:
    """Start background tasks after Telegram initializes."""
    global _auto_sync_task

    if getattr(settings, "auto_sync_enabled", False):
        _auto_sync_task = asyncio.create_task(_auto_sync_loop())


async def _post_shutdown(app: Application) -> None:
    """Stop background tasks cleanly during shutdown."""
    global _auto_sync_task

    if _auto_sync_task is not None:
        _auto_sync_task.cancel()

        try:
            await _auto_sync_task
        except asyncio.CancelledError:
            pass

        _auto_sync_task = None


def _safe_database_target() -> str:
    """Return a safe database target without exposing credentials."""
    try:
        raw_url = str(settings.db_url)
        normalized_url = raw_url.replace(
            "postgresql+psycopg://",
            "postgresql://",
            1,
        )
        parsed = urlsplit(normalized_url)

        hostname = parsed.hostname or "unknown"
        port = parsed.port or 5432
        database = (parsed.path or "/").lstrip("/")

        return f"{hostname}:{port}/{database}"

    except Exception:
        return "configured database"


def _build_application() -> Application:
    """Build the Telegram application and register commands."""
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    # Let handlers read the latest Kobo synchronization status.
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

    return app


def main() -> None:
    """Initialize the database, web server, and Telegram bot."""
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    if not settings.kobo_token or not settings.kobo_asset_uid:
        raise RuntimeError("KOBO_TOKEN or KOBO_ASSET_UID is missing")

    print(f"🚀 Environment: {settings.app_env}")
    print(f"🗄️ Database target: {_safe_database_target()}")
    print(f"📄 Template: {settings.template_file}")
    print(f"📁 Export directory: {settings.export_path}")

    init_db()

    port = int(os.getenv("PORT", "8080"))
    web_thread = threading.Thread(
        target=lambda: uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=port,
            loop="asyncio",
            log_level="info",
        ),
        name="movement-map-web",
        daemon=True,
    )
    web_thread.start()
    print(f"🌐 Movement map web server starting on PORT={port}")

    app = _build_application()

    print("✅ KB Market Survey Bot running...")

    # Python 3.12 with uvloop does not automatically create an event loop.
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)

    try:
        app.run_polling(close_loop=False)
    finally:
        if not event_loop.is_closed():
            event_loop.close()


if __name__ == "__main__":
    main()
