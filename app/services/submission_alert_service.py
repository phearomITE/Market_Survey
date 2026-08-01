from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.data.dealers import ALL_DEALERS

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
    from sqlalchemy import select
    from app.db.database import SessionLocal
    from app.db.models import KoboSubmission

    counts: Counter[str] = Counter()
    official = set(ALL_DEALERS)
    summary_names = {value.replace(" ", "") for value in SUMMARY_NAMES}
    with SessionLocal() as database:
        statement = select(KoboSubmission.dealer, KoboSubmission.outlet_name).where(
            KoboSubmission.report_date == report_date
        )
        for dealer, outlet_name in database.execute(statement):
            code = _clean(dealer).upper()
            if code in official and _clean(outlet_name).replace(" ", "") not in summary_names:
                counts[code] += 1
    return {dealer: int(counts.get(dealer, 0)) for dealer in ALL_DEALERS}


def dealers_below_threshold(counts: dict[str, int], threshold: int) -> list[tuple[str, int]]:
    order = {dealer: index for index, dealer in enumerate(ALL_DEALERS)}
    rows = [(dealer, int(counts.get(dealer, 0))) for dealer in ALL_DEALERS if int(counts.get(dealer, 0)) < threshold]
    return sorted(rows, key=lambda item: (-item[1], order[item[0]]))


def format_submission_alert(report_date: date, threshold: int, counts: dict[str, int] | None = None) -> str:
    if threshold not in {10, 20}:
        raise ValueError("Threshold must be 10 or 20.")
    rows = dealers_below_threshold(counts or dealer_submission_counts(report_date), threshold)
    lines = [f"📊 Dealer ដែល Submit Report តិចជាង {threshold}", f"📅 {report_date:%d/%m/%Y}", ""]
    if rows:
        lines.extend(f"{index}. {dealer} = {count} Report" for index, (dealer, count) in enumerate(rows, 1))
        lines.extend(["", f"សរុប Dealer: {len(rows)}"])
    else:
        lines.append(f"✅ Dealer ទាំងអស់បាន Submit ចាប់ពី {threshold} Report ឡើងទៅ។")
    return "\n".join(lines)
