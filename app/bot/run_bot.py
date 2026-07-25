from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from telegram.ext import Application, CommandHandler

from app.bot.handlers import (
    alert_submit_cmd,
    debug_kobo_cmd,
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
from app.services.submission_alert_service import (
    alert_was_sent,
    format_submission_alert,
    local_now,
    mark_alert_sent,
    parse_hhmm,
    release_alert_claim,
    resolve_alert_target,
)


_auto_sync_task: asyncio.Task | None = None
_submit_alert_task: asyncio.Task | None = None
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



def _submit_alert_schedules() -> list[tuple[str, int]]:
    return [
        (settings.submit_alert_first_time, int(settings.submit_alert_first_threshold)),
        (settings.submit_alert_second_time, int(settings.submit_alert_second_threshold)),
    ]


async def _send_scheduled_submit_alert(
    app: Application,
    report_date,
    threshold: int,
    schedule_value: str,
) -> bool:
    chat_id, thread_id = await asyncio.to_thread(resolve_alert_target)
    if chat_id is None:
        print(
            "⚠️ Submit alert target is not configured. Run /alert_submit once in "
            "the Telegram General group or set SUBMIT_ALERT_CHAT_ID."
        )
        return True

    scheduled = parse_hhmm(schedule_value, "09:30")
    display_time = scheduled.strftime("%I:%M %p").lstrip("0")

    if await asyncio.to_thread(
        alert_was_sent,
        report_date,
        threshold,
        schedule_value,
        chat_id,
    ):
        return True

    # Reserve the unique history row before sending so overlapping Railway
    # containers cannot both post the same scheduled alert.
    claimed = await asyncio.to_thread(
        mark_alert_sent,
        report_date,
        threshold,
        schedule_value,
        chat_id,
    )
    if not claimed:
        return True

    try:
        text = await asyncio.to_thread(
            format_submission_alert,
            report_date,
            threshold,
            None,
            display_time,
        )
        kwargs = {"chat_id": chat_id, "text": text}
        if thread_id:
            kwargs["message_thread_id"] = thread_id
        await app.bot.send_message(**kwargs)
        print(
            f"✅ Submit alert sent: date={report_date} threshold=<{threshold} "
            f"time={display_time} chat={chat_id}"
        )
        return True
    except Exception as exc:
        await asyncio.to_thread(
            release_alert_claim,
            report_date,
            threshold,
            schedule_value,
            chat_id,
        )
        print(f"⚠️ Scheduled submit alert failed: {exc}")
        return False


async def _submit_alert_loop(app: Application) -> None:
    """Send daily dealer submission alerts in Asia/Phnom_Penh time."""
    grace_minutes = max(1, int(settings.submit_alert_grace_minutes or 30))
    schedule_text = ", ".join(
        f"{value} (<{threshold})" for value, threshold in _submit_alert_schedules()
    )
    print(f"⏰ Submit alerts enabled: {schedule_text} [{settings.app_timezone}]")

    while True:
        try:
            now = local_now()
            attempted = False
            failed = False

            for schedule_value, threshold in _submit_alert_schedules():
                scheduled_time = parse_hhmm(schedule_value, "09:30")
                scheduled_at = now.replace(
                    hour=scheduled_time.hour,
                    minute=scheduled_time.minute,
                    second=0,
                    microsecond=0,
                )
                grace_end = scheduled_at + timedelta(minutes=grace_minutes)

                if scheduled_at <= now < grace_end:
                    attempted = True
                    ok = await _send_scheduled_submit_alert(
                        app,
                        now.date(),
                        threshold,
                        schedule_value,
                    )
                    failed = failed or not ok

            if failed:
                await asyncio.sleep(60)
                continue

            # Check once per minute. This also catches a Railway restart inside
            # the configured grace window without sending stale alerts hours late.
            await asyncio.sleep(60 if attempted else 30)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"⚠️ Submit alert scheduler error: {exc}")
            await asyncio.sleep(60)


async def _post_init(app: Application) -> None:
    global _auto_sync_task, _submit_alert_task
    if settings.auto_sync_enabled:
        _auto_sync_task = asyncio.create_task(_auto_sync_loop())
    if settings.submit_alert_enabled:
        _submit_alert_task = asyncio.create_task(_submit_alert_loop(app))


async def _post_shutdown(app: Application) -> None:
    global _auto_sync_task, _submit_alert_task
    for task in (_auto_sync_task, _submit_alert_task):
        if task:
            task.cancel()
            try:
                await task
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
    app.add_handler(CommandHandler("alert_submit", alert_submit_cmd))

    print("✅ KB Market Survey Bot running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
