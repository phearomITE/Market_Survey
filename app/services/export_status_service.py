"""Completion status for each dealer's final combined Kobo summary row."""
from datetime import date

from app.core.summary_marker import is_summary_name
from app.data.dealers import REGION_DEALERS


def format_export_status(report_date: date, submissions=None) -> str:
    """A dealer is complete when any row names a final combined summary."""
    if submissions is None:
        from app.kobo.sync import fetch_report_submissions_fast
        submissions = fetch_report_submissions_fast(
            None, report_date, metadata_only=True
        )

    official = {dealer for dealers in REGION_DEALERS.values() for dealer in dealers}
    completed = {
        str(getattr(row, "dealer", "") or "").strip().upper()
        for row in submissions
        if is_summary_name(getattr(row, "outlet_name", None))
    } & official
    lines = [
        "📊 Final combined summary status",
        f"📅 {report_date:%d/%m/%Y}",
        f"✅ Completed: {len(completed)}/{len(official)} dealers",
        "",
    ]
    for region, dealers in REGION_DEALERS.items():
        missing = [dealer for dealer in dealers if dealer not in completed]
        lines.append(f"{region}: {len(dealers) - len(missing)}/{len(dealers)} completed")
        lines.append("Missing: " + (", ".join(missing) if missing else "None"))
    return "\n".join(lines)
