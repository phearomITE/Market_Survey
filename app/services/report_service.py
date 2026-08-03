from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.database import SessionLocal, init_db
from app.db.models import KoboSubmission
from app.kobo.sync import fetch_report_submissions_fast, sync_kobo
from app.reports.aggregator import aggregate_submissions
from app.reports.excel_report import create_single_report, create_all_dealer_report, create_selected_dealer_report
from app.data.dealers import ALL_DEALERS
from app.reports.summary_report import build_summary_rows, create_summary_report
from app.reports.movement_exports import (
    create_daily_export,
    create_movement_export,
    create_raw_movement_long_export,
)

ReportType = Literal["GT", "HORECA"]

CHANNEL_SPECIALIST_OUTLET_TYPES = {
    "Local Eat",
    "Coffee,Bakery",
    "Canteen",
    "Sport Club",
    "Motor Shop",
    "Local Drink",
}


def normalize_report_type(value: str | None) -> ReportType:
    normalized = str(value or "GT").strip().upper().replace("_", " ")
    if normalized in {"GT", "GENERAL", "GENERAL TRADE"}:
        return "GT"
    if normalized in {"HORECA", "CHANNEL", "CHANNEL SPECIALIST", "SPECIALIST", "CS"}:
        return "HORECA"
    raise ValueError("Report type must be GT or HORECA.")


def parse_report_date(value: str | None) -> date:
    if not value:
        return datetime.now().date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_report_command_args(args: list[str] | tuple[str, ...]) -> tuple[str, str, ReportType]:
    """Parse /report command arguments.

    Supported:
      /report PVH3 GT 2026-07-07
      /report CA3 HORECA 2026-07-18

    The date is always the last token. This prevents trying to parse
    'CHANNEL' as a YYYY-MM-DD date.
    """
    parts = [str(x).strip() for x in args if str(x).strip()]
    if len(parts) < 2:
        raise ValueError("Usage: /report CA3 GT 2026-07-18 or /report CA3 HORECA 2026-07-18")

    dealer = parts[0].upper()
    date_str = parts[-1]

    # Validate date early so the user gets a clean message.
    parse_report_date(date_str)

    middle = " ".join(parts[1:-1]).strip().upper()
    if not middle:
        report_type: ReportType = "GT"
    else:
        report_type = normalize_report_type(middle)

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
    report_type = normalize_report_type(report_type)
    def effective_type(s: KoboSubmission) -> ReportType:
        explicit = (getattr(s, "report_type", None) or "").strip()
        if explicit:
            try:
                return normalize_report_type(explicit)
            except ValueError:
                pass
        return "HORECA" if _is_channel_specialist_submission(s) else "GT"
    return [s for s in submissions if effective_type(s) == report_type]


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


def generate_dealer_report(dealer: str, report_date_str: str, report_type: ReportType = "GT"):
    report_type = normalize_report_type(report_type)
    d = parse_report_date(report_date_str)
    dealer = dealer.upper().strip()
    all_rows = fetch_report_submissions_fast(dealer, d)
    submissions = _filter_by_report_type(all_rows, report_type)
    if not submissions:
        label = report_type
        outlet_types = sorted({(row.outlet_type or "blank") for row in all_rows})
        detail = f" Kobo rows for dealer/date: {len(all_rows)}; outlet types: {', '.join(outlet_types) or 'none'}."
        return None, (
            f"No {label} submissions found for {dealer} on {d}." + detail +
            " Check the command date and Report Type selected in Kobo."
        )

    agg = aggregate_submissions(submissions, wide_map={})
    agg["report_type"] = report_type
    agg["channel"] = report_type

    path = create_single_report(agg)
    label = report_type
    return path, f"Generated {label} {dealer} report for {d}: {len(submissions)} outlet submissions"


def generate_today_all_dealers(report_date_str: str | None = None):
    d = parse_report_date(report_date_str)
    submissions = _filter_by_report_type(
        fetch_report_submissions_fast(None, d), "GT"
    )
    grouped = {}
    for s in submissions:
        grouped.setdefault(s.dealer, []).append(s)
    aggs = {
        dealer: aggregate_submissions(rows, wide_map={})
        for dealer, rows in grouped.items()
        if dealer
    }
    for agg in aggs.values():
        agg["report_type"] = "GT"
        agg["channel"] = "GT"
    path = create_all_dealer_report(aggs, d)
    return path, f"Generated all dealer report for {d}: {len(submissions)} outlet submissions, {len(aggs)} dealers with data"



def generate_today_all_dealers_with_pngs(report_date_str: str | None = None):
    """Generate the urgent 65-dealer Excel workbook without a slow PNG ZIP."""
    path, text = generate_today_all_dealers(report_date_str)
    return path, None, text



def generate_multi_dealer_reports(
    dealers: list[str] | tuple[str, ...],
    report_date_str: str,
    report_type: ReportType = "GT",
):
    """Generate one workbook and one PNG ZIP for selected dealers.

    The Kobo API is synchronized at most once for the requested date when any
    selected dealer is missing from PostgreSQL. The output workbook always has
    one sheet per requested dealer, in the same order as the command. Dealers
    with no matching submissions receive a blank sheet and are listed in the
    returned status message.
    """
    report_type = normalize_report_type(report_type)
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

    requested_rows = _filter_by_report_type(
        fetch_report_submissions_fast(None, d, dealers=seen), report_type
    )

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
        agg = aggregate_submissions(rows, wide_map={})
        agg["report_type"] = report_type
        agg["channel"] = report_type
        aggs[dealer] = agg

    path = create_selected_dealer_report(aggs, normalized, d)
    png_zip = None

    missing = [dealer for dealer in normalized if not grouped[dealer]]
    total_rows = sum(len(rows) for rows in grouped.values())
    status = (
        f"Generated {len(normalized)} dealer sheets for {d}: "
        f"{len(normalized) - len(missing)} with data, {total_rows} outlet submissions"
    )
    if missing:
        status += "; no data: " + ", ".join(missing)
    return path, png_zip, status


def generate_region_dealer_summary(report_type: ReportType | str = "GT", report_date_str: str | None = None):
    report_type = normalize_report_type(report_type)
    d = parse_report_date(report_date_str)
    submissions = _filter_by_report_type(
        fetch_report_submissions_fast(None, d, summary_only=True), report_type
    )
    if not submissions:
        raise ValueError(f"Kobo returned no {report_type} submissions for {d}.")
    rows = build_summary_rows(submissions)
    path = create_summary_report(
        rows,
        d,
        report_type=report_type,
        submissions=submissions,
    )
    submitted_dealers = sum(1 for r in rows if r.get("total_submissions", 0) > 0)
    total_submissions = sum(r.get("total_submissions", 0) for r in rows)
    total_outlets = sum(r.get("total_outlets", 0) for r in rows)
    return (
        path,
        f"Generated {report_type} summary for {d}: {submitted_dealers}/65 dealers submitted, "
        f"{total_submissions} submissions, {total_outlets} outlets"
    )


def generate_raw_movement_export(report_date_str: str):
    """Export combined GT and HORECA raw movement for one report date."""
    d = parse_report_date(report_date_str)
    submissions = fetch_report_submissions_fast(None, d)
    if not submissions:
        raise ValueError(f"No submissions found for {d}.")
    output_path = settings.export_path / f"Raw_Movement_{d}.xlsx"
    path = create_raw_movement_long_export(submissions, d, output_path)
    return (
        path,
        f"Generated combined GT/HORECA raw movement for {d}: "
        f"{len(submissions)} outlet submissions",
    )


def generate_daily_data_export(report_date_str: str):
    """Create the requested Summary_Data + Location_Outlet workbook."""
    d = parse_report_date(report_date_str)
    submissions = fetch_report_submissions_fast(None, d)
    if not submissions:
        raise ValueError(f"No submissions found for {d}.")
    path = create_daily_export(submissions, d)
    return path, f"Generated three-sheet market survey export for {d}: {len(submissions)} submissions"


def generate_movement_multi_export(report_date_values: list[str] | tuple[str, ...]):
    """Export Beer movement for multiple requested dates in one workbook."""
    dates = list(dict.fromkeys(parse_report_date(value) for value in report_date_values))
    if not dates:
        raise ValueError(
            "Usage: /export movement_multi 2026-07-04 2026-07-18 2026-07-25"
        )
    # Different dates are independent Kobo queries. Fetch them concurrently so
    # a three-date movement export stays inside the Telegram command deadline.
    workers = min(4, len(dates))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        chunks = list(
            executor.map(
                lambda report_date: fetch_report_submissions_fast(None, report_date),
                dates,
            )
        )
    submissions = [row for chunk in chunks for row in chunk]
    if not submissions:
        raise ValueError("No submissions found for the requested report dates.")
    path = create_movement_export(submissions, dates, beer_only=True)
    return (
        path,
        f"Generated Beer movement export for {len(dates)} date(s): "
        f"{len(submissions)} outlet submissions",
    )
