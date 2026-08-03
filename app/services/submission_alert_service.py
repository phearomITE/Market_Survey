from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.data.dealers import ALL_DEALERS, DEALER_REGION
from app.kobo.sync import fetch_report_submissions_fast
from app.reports.submission_status_export import create_submission_status_export
from app.services.summary_marker import is_final_summary_outlet_name


def _clean(value) -> str:
    return " ".join(str(value or "").replace("\u200b", "").split()).strip()


def local_today() -> date:
    try:
        from app.core.config import settings
        return datetime.now(ZoneInfo(settings.app_timezone)).date()
    except Exception:
        return datetime.now(ZoneInfo("Asia/Phnom_Penh")).date()


def dealer_submission_counts(report_date: date) -> dict[str, int]:
    counts: Counter[str] = Counter()
    official = set(ALL_DEALERS)
    submissions = fetch_report_submissions_fast(
        None, report_date, metadata_only=True
    )
    for submission in submissions:
        dealer = _clean(getattr(submission, "dealer", None)).upper()
        if dealer in official and not is_final_summary_outlet_name(
            getattr(submission, "outlet_name", None)
        ):
            counts[dealer] += 1
    return {dealer: int(counts.get(dealer, 0)) for dealer in ALL_DEALERS}


def format_submission_alert(
    report_date: date,
    threshold: int,
    counts: dict[str, int] | None = None,
) -> str:
    if threshold not in {10, 20}:
        raise ValueError("Threshold must be 10 or 20.")
    values = counts if counts is not None else dealer_submission_counts(report_date)
    order = {dealer: index for index, dealer in enumerate(ALL_DEALERS)}
    rows = sorted(
        [
            (dealer, int(values.get(dealer, 0)))
            for dealer in ALL_DEALERS
            if int(values.get(dealer, 0)) < threshold
        ],
        key=lambda item: (-item[1], order[item[0]]),
    )
    lines = [
        f"📊 Dealer ដែល Submit Report តិចជាង {threshold}",
        f"📅 {report_date:%d/%m/%Y}",
        "",
    ]
    lines.extend(
        f"{index}. {dealer} = {count} Report"
        for index, (dealer, count) in enumerate(rows, 1)
    )
    lines.extend(["", f"សរុប Dealer: {len(rows)}"])
    return "\n".join(lines)


def generate_submission_status_export(report_date_value: str):
    """Export summary-submission status using live, date-filtered Kobo rows."""
    try:
        report_date = datetime.strptime(report_date_value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError("Date must use YYYY-MM-DD, for example 2026-08-01.") from exc

    submissions = fetch_report_submissions_fast(
        None, report_date, metadata_only=True
    )
    submitted = {
        _clean(getattr(row, "dealer", None)).upper()
        for row in submissions
        if is_final_summary_outlet_name(getattr(row, "outlet_name", None))
    }
    rows = [
        {
            "date": report_date,
            "region": DEALER_REGION[dealer],
            "dealer": dealer,
            "status": (
                "Summary Submitted" if dealer in submitted else "Missing Summary"
            ),
        }
        for dealer in ALL_DEALERS
    ]
    path = create_submission_status_export(rows, report_date)
    return path, (
        f"Summary status for {report_date}: "
        f"{len(submitted & set(ALL_DEALERS))}/{len(ALL_DEALERS)} dealers submitted"
    )
