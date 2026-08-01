from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from telegram.ext import Application, CommandHandler

from app.bot.handlers import (
    alert_submit_cmd,
    debug_kobo_cmd,
    help_cmd,
    export_cmd,
    report_cmd,
    report_multi_cmd,
    report_today_cmd,
    raw_movement_cmd,
    start,
    status_cmd,
    summary_cmd,
    sync_kobo_cmd,
)
from app.core.config import settings
from app.db.database import init_db


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
        .concurrent_updates(4)
        .build()
    )

    # Let handlers read the latest Kobo synchronization status.
    app.bot_data["get_last_auto_sync"] = lambda: None

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
    app.add_handler(CommandHandler("raw_movement", raw_movement_cmd))
    app.add_handler(CommandHandler("alert_submit", alert_submit_cmd))
    app.add_handler(CommandHandler("export", export_cmd))

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

