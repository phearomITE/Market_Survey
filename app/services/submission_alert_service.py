from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.data.dealers import ALL_DEALERS
from app.kobo.sync import fetch_report_submissions_fast


SUMMARY_NAMES = {"បូកសរុបរួម", "បូកសរុបរូម", "សរុបរួម", "បួកសរុបរួម"}


def _clean(value) -> str:
    return " ".join(str(value or "").replace("\u200b", "").split()).strip()


def local_today() -> date:
    try:
        from app.core.config import settings
        return datetime.now(ZoneInfo(settings.app_timezone)).date()
    except Exception:
        return datetime.now(ZoneInfo("Asia/Phnom_Penh")).date()


def dealer_submission_counts(report_date: date) -> dict[str, int]:
    """Count all current Kobo rows by dealer, excluding summary controls."""
    counts: Counter[str] = Counter()
    official = set(ALL_DEALERS)
    summary_names = {value.replace(" ", "") for value in SUMMARY_NAMES}
    submissions = fetch_report_submissions_fast(
        None, report_date, metadata_only=True
    )
    for submission in submissions:
        dealer = _clean(getattr(submission, "dealer", None)).upper()
        outlet_name = _clean(getattr(submission, "outlet_name", None)).replace(" ", "")
        if dealer in official and outlet_name not in summary_names:
            counts[dealer] += 1
    return {dealer: int(counts.get(dealer, 0)) for dealer in ALL_DEALERS}


def dealers_below_threshold(
    counts: dict[str, int], threshold: int
) -> list[tuple[str, int]]:
    order = {dealer: index for index, dealer in enumerate(ALL_DEALERS)}
    rows = [
        (dealer, int(counts.get(dealer, 0)))
        for dealer in ALL_DEALERS
        if int(counts.get(dealer, 0)) < threshold
    ]
    return sorted(rows, key=lambda item: (-item[1], order[item[0]]))


def format_submission_alert(
    report_date: date,
    threshold: int,
    counts: dict[str, int] | None = None,
) -> str:
    if threshold not in {10, 20}:
        raise ValueError("Threshold must be 10 or 20.")
    rows = dealers_below_threshold(
        counts if counts is not None else dealer_submission_counts(report_date),
        threshold,
    )
    lines = [
        f"📊 Dealer ដែល Submit Report តិចជាង {threshold}",
        f"📅 {report_date:%d/%m/%Y}",
        "",
    ]
    if rows:
        lines.extend(
            f"{index}. {dealer} = {count} Report"
            for index, (dealer, count) in enumerate(rows, 1)
        )
        lines.extend(["", f"សរុប Dealer: {len(rows)}"])
    else:
        lines.append(
            f"✅ Dealer ទាំងអស់បាន Submit ចាប់ពី {threshold} Report ឡើងទៅ។"
        )
    return "\n".join(lines)

