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
from app.reports.excel_report import create_single_report, create_all_dealer_report, create_selected_dealer_report
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



def parse_multi_report_command_args(args: list[str] | tuple[str, ...]) -> tuple[list[str], str]:
    """Parse a selected-dealer report command.

    Supported examples:
      /report_multi CPH2 CA2 KDL1 CA1 CA7 2026-07-14
      /report_multi CPH2,CA2,KDL1,CA1,CA7 2026-07-14

    The last token must be the report date. Dealer codes may be separated by
    spaces and/or commas. Duplicate dealer codes are removed while preserving
    the requested order.
    """
    parts = [str(x).strip() for x in args if str(x).strip()]
    if len(parts) < 2:
        raise ValueError(
            "Usage: /report_multi CPH2 CA2 KDL1 CA1 CA7 2026-07-14"
        )

    date_str = parts[-1]
    parse_report_date(date_str)

    dealer_tokens: list[str] = []
    for token in parts[:-1]:
        dealer_tokens.extend(piece.strip() for piece in token.split(",") if piece.strip())

    dealers: list[str] = []
    seen: set[str] = set()
    for token in dealer_tokens:
        dealer = token.upper()
        if dealer not in seen:
            seen.add(dealer)
            dealers.append(dealer)

    if not dealers:
        raise ValueError("Enter at least one dealer before the date.")
    if len(dealers) > 10:
        raise ValueError("Maximum 10 dealers per command. For all dealers, use /report_today.")

    invalid = [dealer for dealer in dealers if dealer not in ALL_DEALERS]
    if invalid:
        raise ValueError(
            "Unknown dealer code(s): " + ", ".join(invalid) + ". Check the dealer list and retry."
        )

    return dealers, date_str


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
    """Target the requested dealer/date and wait for any active background sync."""
    if submissions:
        return submissions
    try:
        result = sync_kobo(
            dealer=dealer,
            report_date=d,
            wait_if_running=True,
            timeout_seconds=settings.report_sync_wait_seconds,
        )
        print(f"ℹ️ Report sync result: {result}")
    except Exception as e:
        print(f"⚠️ Auto sync before retry failed: {e}")
        return submissions

    rows = get_submissions(dealer, d, report_type=report_type)
    if rows:
        return rows

    # If we only waited for another sync and it did not import this dealer/date,
    # run one targeted pass now that the lock is free.
    if result.get("waited_for_existing_sync"):
        try:
            sync_kobo(
                dealer=dealer,
                report_date=d,
                wait_if_running=True,
                timeout_seconds=settings.report_sync_wait_seconds,
            )
        except Exception as e:
            print(f"⚠️ Targeted retry failed: {e}")
    return get_submissions(dealer, d, report_type=report_type)


def generate_dealer_report(dealer: str, report_date_str: str, report_type: ReportType = "GENERAL"):
    d = parse_report_date(report_date_str)
    dealer = dealer.upper().strip()
    submissions = get_submissions(dealer, d, report_type=report_type)
    if settings.auto_sync_before_report or not submissions:
        submissions = _sync_and_retry_if_empty(dealer, d, submissions, report_type=report_type)
    if not submissions:
        label = "CHANNEL SPECIALIST" if report_type == "CHANNEL_SPECIALIST" else "GENERAL"
        all_rows = get_submissions(dealer, d, report_type=None)
        outlet_types = sorted({(row.outlet_type or "blank") for row in all_rows})
        detail = f" DB rows for dealer/date: {len(all_rows)}; outlet types: {', '.join(outlet_types) or 'none'}."
        return None, (
            f"No {label} submissions found for {dealer} on {d}." + detail +
            " Run /sync_kobo once and retry."
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



def generate_multi_dealer_reports(
    dealers: list[str] | tuple[str, ...],
    report_date_str: str,
    report_type: ReportType = "GENERAL",
):
    """Generate one workbook and one PNG ZIP for selected dealers.

    The Kobo API is synchronized at most once for the requested date when any
    selected dealer is missing from PostgreSQL. The output workbook always has
    one sheet per requested dealer, in the same order as the command. Dealers
    with no matching submissions receive a blank sheet and are listed in the
    returned status message.
    """
    d = parse_report_date(report_date_str)
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in dealers:
        dealer = str(raw).strip().upper()
        if dealer and dealer not in seen:
            seen.add(dealer)
            normalized.append(dealer)

    if not normalized:
        raise ValueError("At least one dealer is required.")

    invalid = [dealer for dealer in normalized if dealer not in ALL_DEALERS]
    if invalid:
        raise ValueError("Unknown dealer code(s): " + ", ".join(invalid))

    submissions = get_submissions(None, d, report_type=report_type)
    requested_rows = [row for row in submissions if (row.dealer or "").upper() in seen]
    present = {(row.dealer or "").upper() for row in requested_rows}
    missing_before_sync = [dealer for dealer in normalized if dealer not in present]

    # One date-targeted sync is much faster and safer than running one full Kobo
    # fetch independently for every dealer.
    if settings.auto_sync_before_report or missing_before_sync:
        try:
            sync_kobo(
                dealer=None,
                report_date=d,
                wait_if_running=True,
                timeout_seconds=settings.report_sync_wait_seconds,
            )
        except Exception as exc:
            print(f"⚠️ Multi-dealer targeted sync failed: {exc}")

        submissions = get_submissions(None, d, report_type=report_type)
        requested_rows = [row for row in submissions if (row.dealer or "").upper() in seen]

    grouped: dict[str, list[KoboSubmission]] = {dealer: [] for dealer in normalized}
    for row in requested_rows:
        dealer = (row.dealer or "").upper()
        if dealer in grouped:
            grouped[dealer].append(row)

    aggs: dict[str, dict] = {}
    for dealer in normalized:
        rows = grouped[dealer]
        if not rows:
            continue
        agg = aggregate_submissions(rows)
        agg["report_type"] = report_type
        agg["channel"] = "CHANNEL SPECIALIST" if report_type == "CHANNEL_SPECIALIST" else "GENERAL"
        aggs[dealer] = agg

    path = create_selected_dealer_report(aggs, normalized, d)
    png_zip = excel_workbook_to_png_zip(
        path,
        sheet_names=normalized,
        zip_path=path.with_name(f"{path.stem}_PNG.zip"),
    )

    missing = [dealer for dealer in normalized if not grouped[dealer]]
    total_rows = sum(len(rows) for rows in grouped.values())
    status = (
        f"Generated {len(normalized)} dealer sheets for {d}: "
        f"{len(normalized) - len(missing)} with data, {total_rows} outlet submissions"
    )
    if missing:
        status += "; no data: " + ", ".join(missing)
    if png_zip:
        status += f"; PNG previews: {len(normalized)}"
    else:
        status += "; PNG ZIP not created"

    return path, png_zip, status


def generate_region_dealer_summary(report_date_str: str | None = None):
    """Generate a fresh all-dealer summary for one date.

    A summary may already find some dealers in PostgreSQL while newly submitted
    dealers are still missing. Always synchronize the full requested date before
    reading the database.
    """
    d = parse_report_date(report_date_str)
    sync_warning = ""

    try:
        sync_result = sync_kobo(
            dealer=None,
            report_date=d,
            wait_if_running=True,
            timeout_seconds=settings.report_sync_wait_seconds,
        )

        # The active sync may have targeted another dealer/date. Run one full
        # date pass after waiting so this summary includes every current dealer.
        if sync_result.get("waited_for_existing_sync"):
            sync_kobo(
                dealer=None,
                report_date=d,
                wait_if_running=True,
                timeout_seconds=settings.report_sync_wait_seconds,
            )
    except Exception as exc:
        sync_warning = f" Sync warning: {exc}"

    submissions = get_submissions(None, d)
    rows = build_summary_rows(submissions)
    path = create_summary_report(rows, d)
    submitted_dealers = sum(1 for r in rows if r.get("total_submissions", 0) > 0)
    total_dealers = len(rows)
    total_submissions = sum(r.get("total_submissions", 0) for r in rows)
    total_outlets = sum(r.get("total_outlets", 0) for r in rows)
    return (
        path,
        f"Generated summary for {d}: {submitted_dealers}/{total_dealers} dealers submitted, "
        f"{total_submissions} submissions, {total_outlets} outlets.{sync_warning}"
    )
