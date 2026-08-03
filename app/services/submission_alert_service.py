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


def parse_alert_submit_args(
    args: list[str] | tuple[str, ...],
    *,
    today: date | None = None,
) -> tuple[int, date]:
    """Parse /alert_submit THRESHOLD [YYYY-MM-DD].

    The date remains optional for backward compatibility. When omitted, the
    command checks the current Cambodia date.
    """
    parts = [str(value).strip() for value in args if str(value).strip()]
    if len(parts) not in {1, 2}:
        raise ValueError(
            "Usage:\n"
            "/alert_submit 10\n"
            "/alert_submit 20\n"
            "/alert_submit 10 2026-08-01\n"
            "/alert_submit 20 2026-08-01"
        )

    try:
        threshold = int(parts[0])
    except (TypeError, ValueError) as exc:
        raise ValueError("Threshold must be 10 or 20.") from exc
    if threshold not in {10, 20}:
        raise ValueError("Threshold must be 10 or 20.")

    if len(parts) == 1:
        return threshold, today or local_today()

    try:
        report_date = date.fromisoformat(parts[1])
    except ValueError as exc:
        raise ValueError(
            "Invalid date. Use YYYY-MM-DD, for example 2026-08-01."
        ) from exc
    return threshold, report_date


def dealer_submission_counts(report_date: date) -> dict[str, int]:
    counts: Counter[str] = Counter()
    official = set(ALL_DEALERS)
    summary_names = {value.replace(" ", "") for value in SUMMARY_NAMES}
    submissions = fetch_report_submissions_fast(
        None, report_date, metadata_only=True
    )
    for submission in submissions:
        dealer = _clean(getattr(submission, "dealer", None)).upper()
        outlet_name = _clean(
            getattr(submission, "outlet_name", None)
        ).replace(" ", "")
        if dealer in official and outlet_name not in summary_names:
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
