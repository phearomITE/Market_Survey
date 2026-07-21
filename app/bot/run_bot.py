from __future__ import annotations

import asyncio
from datetime import datetime
from urllib.parse import urlsplit

from telegram.ext import Application, CommandHandler

from app.bot.handlers import (
    debug_kobo_cmd,
    export_cmd,
    help_cmd,
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
    app.add_handler(CommandHandler("export", export_cmd))

    print("✅ KB Market Survey Bot running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
