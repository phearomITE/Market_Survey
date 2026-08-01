from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.data.dealers import ALL_DEALERS


FINAL_SUMMARY_KEYWORDS = {
    "បូកសរុបរួម",
    "បូកសរុបរូម",
    "សរុបរួម",
    "បួកសរុបរួម",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", "").split()).strip()


def _is_final_summary_outlet_name(value: Any) -> bool:
    normalized = _clean(value).replace(" ", "")
    return normalized in {item.replace(" ", "") for item in FINAL_SUMMARY_KEYWORDS}


def local_today() -> date:
    """Return the current report date in the configured Cambodia timezone."""
    try:
        from app.core.config import settings

        return datetime.now(ZoneInfo(settings.app_timezone)).date()
    except Exception:
        return datetime.now(ZoneInfo("Asia/Phnom_Penh")).date()


def dealer_submission_counts(report_date: date) -> dict[str, int]:
    """Count valid Kobo outlet submissions for every official dealer."""
    from sqlalchemy import select

    from app.db.database import SessionLocal
    from app.db.models import KoboSubmission

    counts: Counter[str] = Counter()
    official = set(ALL_DEALERS)

    with SessionLocal() as db:
        statement = select(KoboSubmission.dealer, KoboSubmission.outlet_name).where(
            KoboSubmission.report_date == report_date
        )
        for dealer, outlet_name in db.execute(statement):
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
    """Return dealers below target, highest submission count first."""
    official_order = {dealer: index for index, dealer in enumerate(ALL_DEALERS)}
    rows = [
        (dealer, int(counts.get(dealer, 0)))
        for dealer in ALL_DEALERS
        if int(counts.get(dealer, 0)) < threshold
    ]
    return sorted(rows, key=lambda item: (-item[1], official_order[item[0]]))


def format_submission_alert(
    report_date: date,
    threshold: int,
    counts: dict[str, int] | None = None,
) -> str:
    """Build the manual Telegram response for /alert_submit."""
    if threshold not in {10, 20}:
        raise ValueError("Threshold must be 10 or 20.")

    counts = counts if counts is not None else dealer_submission_counts(report_date)
    low_dealers = dealers_below_threshold(counts, threshold)
    lines = [
        f"📊 Dealer ដែល Submit Report តិចជាង {threshold}",
        f"📅 {report_date:%d/%m/%Y}",
        "",
    ]

    if low_dealers:
        lines.extend(
            f"{index}. {dealer} = {count} Report"
            for index, (dealer, count) in enumerate(low_dealers, start=1)
        )
        lines.extend(["", f"សរុប Dealer: {len(low_dealers)}"])
    else:
        lines.append(
            f"✅ Dealer ទាំងអស់បាន Submit ចាប់ពី {threshold} Report ឡើងទៅ។"
        )

    return "\n".join(lines)
