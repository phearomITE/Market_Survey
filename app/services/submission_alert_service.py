from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.data.dealers import ALL_DEALERS


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", "").split()).strip()



FINAL_SUMMARY_KEYWORDS = {
    "បូកសរុបរួម",
    "បូកសរុបរូម",
    "សរុបរួម",
    "បួកសរុបរួម",
}


def _is_final_summary_outlet_name(value: Any) -> bool:
    normalized = _clean(value).replace(" ", "")
    return normalized in {item.replace(" ", "") for item in FINAL_SUMMARY_KEYWORDS}

def local_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(settings.app_timezone))
    except Exception:
        return datetime.now(ZoneInfo("Asia/Phnom_Penh"))


def parse_hhmm(value: str, fallback: str) -> time:
    raw = _clean(value) or fallback
    try:
        return datetime.strptime(raw, "%H:%M").time()
    except ValueError:
        return datetime.strptime(fallback, "%H:%M").time()


def current_manual_threshold(now: datetime | None = None) -> int:
    """Choose the manual alert threshold from the configured schedule.

    Before the second alert time, /alert_submit uses the first threshold.
    At or after the second alert time, it uses the second threshold.
    """
    current = now or local_now()
    second_time = parse_hhmm(settings.submit_alert_second_time, "10:30")
    if current.timetz().replace(tzinfo=None) >= second_time:
        return int(settings.submit_alert_second_threshold)
    return int(settings.submit_alert_first_threshold)


def dealer_submission_counts(report_date: date) -> dict[str, int]:
    """Count real outlet submissions for all official dealers on one date.

    Final control rows whose Outlet Name is a summary marker are excluded.
    Dealers with no submissions are returned with count 0.
    """
    from sqlalchemy import select
    from app.db.database import SessionLocal, init_db
    from app.db.models import KoboSubmission

    init_db()
    counts: Counter[str] = Counter()
    official = set(ALL_DEALERS)

    with SessionLocal() as db:
        stmt = (
            select(KoboSubmission.dealer, KoboSubmission.outlet_name)
            .where(KoboSubmission.report_date == report_date)
        )
        for dealer, outlet_name in db.execute(stmt):
            dealer_code = _clean(dealer).upper()
            if dealer_code not in official:
                continue
            if _is_final_summary_outlet_name(outlet_name):
                continue
            counts[dealer_code] += 1

    return {dealer: int(counts.get(dealer, 0)) for dealer in ALL_DEALERS}


def dealers_below_threshold(
    counts: dict[str, int],
    threshold: int,
) -> list[tuple[str, int]]:
    """Return dealers below threshold in the official Region/Dealer order."""
    return [
        (dealer, int(counts.get(dealer, 0)))
        for dealer in ALL_DEALERS
        if int(counts.get(dealer, 0)) < int(threshold)
    ]


def format_submission_alert(
    report_date: date,
    threshold: int,
    counts: dict[str, int] | None = None,
    scheduled_time: str | None = None,
) -> str:
    counts = counts or dealer_submission_counts(report_date)
    low_dealers = dealers_below_threshold(counts, threshold)

    lines = [
        f"📊 Dealer ដែល Submit Report តិចជាង {threshold}",
        f"📅 {report_date:%d/%m/%Y}" + (f" | ⏰ {scheduled_time}" if scheduled_time else ""),
        "",
    ]

    if low_dealers:
        lines.extend(
            f"{index}. {dealer} = {count} Report"
            for index, (dealer, count) in enumerate(low_dealers, start=1)
        )
        lines.extend(["", f"សរុប Dealer: {len(low_dealers)}"])
    else:
        lines.append(f"✅ Dealer ទាំងអស់បាន Submit ចាប់ពី {threshold} Report ឡើងទៅ។")

    return "\n".join(lines)


def _target_from_settings() -> tuple[str | int | None, int | None]:
    raw_chat_id = _clean(settings.submit_alert_chat_id) or _clean(settings.telegram_chat_id)
    if not raw_chat_id:
        return None, None

    chat_id: str | int
    if raw_chat_id.lstrip("-").isdigit():
        chat_id = int(raw_chat_id)
    else:
        chat_id = raw_chat_id

    raw_thread = settings.submit_alert_thread_id
    thread_id = int(raw_thread) if raw_thread not in (None, "", 0, "0") else None
    return chat_id, thread_id


def save_group_alert_target(chat_id: int | str) -> None:
    """Persist the group used by /alert_submit as the automatic General target."""
    from app.db.database import SessionLocal, init_db
    from app.db.models import SubmissionAlertTarget

    init_db()
    value = str(chat_id)
    with SessionLocal() as db:
        target = db.get(SubmissionAlertTarget, 1)
        if target is None:
            target = SubmissionAlertTarget(id=1, chat_id=value, thread_id=None)
            db.add(target)
        else:
            target.chat_id = value
            # Automatic alerts must go to the General topic, so no topic ID.
            target.thread_id = None
            target.updated_at = datetime.utcnow()
        db.commit()


def resolve_alert_target() -> tuple[str | int | None, int | None]:
    """Resolve env-configured target first, then the group saved by /alert_submit."""
    configured = _target_from_settings()
    if configured[0] is not None:
        return configured

    from app.db.database import SessionLocal, init_db
    from app.db.models import SubmissionAlertTarget

    init_db()
    with SessionLocal() as db:
        target = db.get(SubmissionAlertTarget, 1)
        if target is None or not _clean(target.chat_id):
            return None, None
        raw_chat_id = _clean(target.chat_id)
        chat_id: str | int = int(raw_chat_id) if raw_chat_id.lstrip("-").isdigit() else raw_chat_id
        return chat_id, target.thread_id


def alert_was_sent(
    report_date: date,
    threshold: int,
    scheduled_time: str,
    chat_id: str | int,
) -> bool:
    from sqlalchemy import select
    from app.db.database import SessionLocal, init_db
    from app.db.models import SubmissionAlertHistory

    init_db()
    with SessionLocal() as db:
        stmt = select(SubmissionAlertHistory.id).where(
            SubmissionAlertHistory.alert_date == report_date,
            SubmissionAlertHistory.threshold == int(threshold),
            SubmissionAlertHistory.scheduled_time == scheduled_time,
            SubmissionAlertHistory.chat_id == str(chat_id),
        )
        return db.scalar(stmt) is not None


def mark_alert_sent(
    report_date: date,
    threshold: int,
    scheduled_time: str,
    chat_id: str | int,
) -> bool:
    """Reserve one scheduled alert before Telegram sending.

    Returns False when another process already reserved or sent the same alert.
    """
    from sqlalchemy.exc import IntegrityError
    from app.db.database import SessionLocal, init_db
    from app.db.models import SubmissionAlertHistory

    init_db()
    with SessionLocal() as db:
        db.add(
            SubmissionAlertHistory(
                alert_date=report_date,
                threshold=int(threshold),
                scheduled_time=scheduled_time,
                chat_id=str(chat_id),
            )
        )
        try:
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            return False


def release_alert_claim(
    report_date: date,
    threshold: int,
    scheduled_time: str,
    chat_id: str | int,
) -> None:
    """Remove a reserved history row when Telegram sending fails."""
    from sqlalchemy import select
    from app.db.database import SessionLocal, init_db
    from app.db.models import SubmissionAlertHistory

    init_db()
    with SessionLocal() as db:
        stmt = select(SubmissionAlertHistory).where(
            SubmissionAlertHistory.alert_date == report_date,
            SubmissionAlertHistory.threshold == int(threshold),
            SubmissionAlertHistory.scheduled_time == scheduled_time,
            SubmissionAlertHistory.chat_id == str(chat_id),
        )
        row = db.scalar(stmt)
        if row is not None:
            db.delete(row)
            db.commit()
