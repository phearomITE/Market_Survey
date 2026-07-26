from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
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


def local_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(settings.app_timezone))
    except Exception:
        return datetime.now(ZoneInfo("Asia/Phnom_Penh"))


def dealer_submission_counts(report_date: date) -> dict[str, int]:
    """Count real outlet submissions for all official dealers on one date."""
    from sqlalchemy import select
    from app.db.database import SessionLocal
    from app.db.models import KoboSubmission

    counts: Counter[str] = Counter()
    official = set(ALL_DEALERS)

    with SessionLocal() as db:
        stmt = select(KoboSubmission.dealer, KoboSubmission.outlet_name).where(
            KoboSubmission.report_date == report_date
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
    """List low-submit dealers, closest to the target first.

    Example: for <10, a dealer with 8 reports appears before a dealer with 5.
    Official dealer order is used to break equal-count ties.
    """
    order = {dealer: index for index, dealer in enumerate(ALL_DEALERS)}
    rows = [
        (dealer, int(counts.get(dealer, 0)))
        for dealer in ALL_DEALERS
        if int(counts.get(dealer, 0)) < int(threshold)
    ]
    return sorted(rows, key=lambda item: (-item[1], order[item[0]]))


def format_submission_alert(
    report_date: date,
    threshold: int,
    counts: dict[str, int] | None = None,
) -> str:
    counts = counts or dealer_submission_counts(report_date)
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
        lines.append(f"✅ Dealer ទាំងអស់បាន Submit ចាប់ពី {threshold} Report ឡើងទៅ។")

    return "\n".join(lines)
