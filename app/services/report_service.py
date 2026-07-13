from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.database import SessionLocal, init_db
from app.db.models import KoboSubmission
from app.kobo.sync import sync_kobo
from app.reports.aggregator import aggregate_submissions
from app.reports.excel_report import create_single_report, create_all_dealer_report
from app.services.render_service import excel_workbook_to_png_zip
from app.data.dealers import ALL_DEALERS
from app.reports.summary_report import build_summary_rows, create_summary_report

ReportType = Literal["GENERAL", "CHANNEL_SPECIALIST"]

CHANNEL_SPECIALIST_OUTLET_TYPES = {
    "Local Eat",
    "Coffee,Bakery",
    "Canteen",
    "Sport Club",
    "Motor Shop",
}


def parse_report_date(value: str | None) -> date:
    if not value:
        return datetime.now().date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_report_command_args(args: list[str] | tuple[str, ...]) -> tuple[str, str, ReportType]:
    """Parse /report command arguments.

    Supported:
      /report PVH3 2026-07-07
      /report PVH3 CHANNEL SPECIALIST 2026-07-07

    The date is always the last token. This prevents trying to parse
    'CHANNEL' as a YYYY-MM-DD date.
    """
    parts = [str(x).strip() for x in args if str(x).strip()]
    if len(parts) < 2:
        raise ValueError("Usage: /report PVH3 2026-07-07 or /report PVH3 CHANNEL SPECIALIST 2026-07-07")

    dealer = parts[0].upper()
    date_str = parts[-1]

    # Validate date early so the user gets a clean message.
    parse_report_date(date_str)

    middle = " ".join(parts[1:-1]).strip().upper()
    if not middle:
        report_type: ReportType = "GENERAL"
    elif middle in {"CHANNEL", "CHANNEL SPECIALIST", "SPECIALIST", "CS"}:
        report_type = "CHANNEL_SPECIALIST"
    else:
        raise ValueError(
            "Unknown report type. Use /report PVH3 2026-07-07 or "
            "/report PVH3 CHANNEL SPECIALIST 2026-07-07"
        )

    return dealer, date_str, report_type


def _is_channel_specialist_submission(s: KoboSubmission) -> bool:
    return (s.outlet_type or "").strip() in CHANNEL_SPECIALIST_OUTLET_TYPES


def _filter_by_report_type(submissions: list[KoboSubmission], report_type: ReportType) -> list[KoboSubmission]:
    if report_type == "CHANNEL_SPECIALIST":
        return [s for s in submissions if _is_channel_specialist_submission(s)]
    # General report excludes Channel Specialist outlet types.
    return [s for s in submissions if not _is_channel_specialist_submission(s)]


def get_submissions(dealer: str | None, report_date: date, report_type: ReportType | None = None):
    init_db()
    with SessionLocal() as db:
        stmt = (
            select(KoboSubmission)
            .options(
                selectinload(KoboSubmission.product_metrics),
                selectinload(KoboSubmission.competitor_metrics),
                selectinload(KoboSubmission.ring_pull_metrics),
            )
            .where(KoboSubmission.report_date == report_date)
        )
        if dealer:
            stmt = stmt.where(KoboSubmission.dealer == dealer.upper())

        rows = list(db.scalars(stmt).all())

    if report_type:
        rows = _filter_by_report_type(rows, report_type)
    return rows


def _sync_and_retry_if_empty(dealer: str | None, d: date, submissions: list, report_type: ReportType | None = None) -> list:
    # Real project behavior: if DB has no matching rows, pull Kobo once and retry.
    # This prevents the common mistake of generating before /sync_kobo was run.
    if submissions:
        return submissions
    try:
        sync_kobo()
    except Exception as e:
        print(f"⚠️ Auto sync before retry failed: {e}")
        return submissions
    return get_submissions(dealer, d, report_type=report_type)


def generate_dealer_report(dealer: str, report_date_str: str, report_type: ReportType = "GENERAL"):
    d = parse_report_date(report_date_str)
    dealer = dealer.upper().strip()
    submissions = get_submissions(dealer, d, report_type=report_type)
    if settings.auto_sync_before_report or not submissions:
        submissions = _sync_and_retry_if_empty(dealer, d, submissions, report_type=report_type)
    if not submissions:
        label = "CHANNEL SPECIALIST" if report_type == "CHANNEL_SPECIALIST" else "GENERAL"
        return None, (
            f"No {label} submissions found for {dealer} on {d}. "
            "Run /sync_kobo and check the dealer/date/outlet type in PostgreSQL."
        )

    agg = aggregate_submissions(submissions)
    agg["report_type"] = report_type
    agg["channel"] = "CHANNEL SPECIALIST" if report_type == "CHANNEL_SPECIALIST" else "GENERAL"

    path = create_single_report(agg)
    label = "Channel Specialist" if report_type == "CHANNEL_SPECIALIST" else "General"
    return path, f"Generated {label} {dealer} report for {d}: {len(submissions)} outlet submissions"


def generate_today_all_dealers(report_date_str: str | None = None):
    d = parse_report_date(report_date_str)
    submissions = get_submissions(None, d, report_type="GENERAL")
    if settings.auto_sync_before_report or not submissions:
        submissions = _sync_and_retry_if_empty(None, d, submissions, report_type="GENERAL")
    grouped = {}
    for s in submissions:
        grouped.setdefault(s.dealer, []).append(s)
    aggs = {dealer: aggregate_submissions(rows) for dealer, rows in grouped.items() if dealer}
    for agg in aggs.values():
        agg["report_type"] = "GENERAL"
        agg["channel"] = "GENERAL"
    path = create_all_dealer_report(aggs, d)
    return path, f"Generated all dealer report for {d}: {len(submissions)} outlet submissions, {len(aggs)} dealers with data"



def generate_today_all_dealers_with_pngs(report_date_str: str | None = None):
    """Generate /report_today output: one 65-dealer Excel workbook + PNG ZIP.

    The workbook contains one sheet per dealer in ALL_DEALERS order, including
    dealers with zero submissions. The PNG ZIP contains one PNG preview per
    worksheet/page when LibreOffice + PyMuPDF are available.
    """
    path, text = generate_today_all_dealers(report_date_str)
    png_zip = excel_workbook_to_png_zip(path, sheet_names=list(ALL_DEALERS))
    if png_zip:
        text = f"{text}; PNG previews: {len(ALL_DEALERS)} dealer pages"
    else:
        text = f"{text}; PNG ZIP not created. Install LibreOffice/PyMuPDF or check LIBREOFFICE_PATH."
    return path, png_zip, text


def generate_region_dealer_summary(report_date_str: str | None = None):
    d = parse_report_date(report_date_str)
    submissions = get_submissions(None, d)
    if settings.auto_sync_before_report or not submissions:
        submissions = _sync_and_retry_if_empty(None, d, submissions)
    rows = build_summary_rows(submissions)
    path = create_summary_report(rows, d)
    submitted_dealers = sum(1 for r in rows if r.get("total_submissions", 0) > 0)
    total_submissions = sum(r.get("total_submissions", 0) for r in rows)
    total_outlets = sum(r.get("total_outlets", 0) for r in rows)
    return (
        path,
        f"Generated summary for {d}: {submitted_dealers}/65 dealers submitted, "
        f"{total_submissions} submissions, {total_outlets} outlets"
    )
