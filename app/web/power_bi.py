"""Read-only CSV feeds for Power BI's Web connector."""
import csv
import io
import secrets
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func

from app.core.config import settings
from app.core.summary_marker import is_summary_name
from app.db.database import SessionLocal
from app.db.models import (
    KoboCompetitorMetric, KoboProductMetric, KoboRingPullMetric, KoboSubmission, SyncLog,
)

router = APIRouter()

# Explicit allowlists prevent accidental disclosure of new database columns.
OUTLET_FIELDS = (
    "id", "submission_id", "report_date", "submission_time", "region", "dealer",
    "group_no", "member_no", "total_outlet_visit_target", "outlet_name",
    "outlet_type", "report_type", "is_new_outlet", "submitter_name",
    "phone_number", "location_text", "gps_latitude", "gps_longitude", "key_issue_text",
    "suggestion_text", "updated_at",
)
METRICS = {
    "products": (KoboProductMetric, (
        "product_name", "status", "available", "movement_score", "stock_status",
        "bbe_date", "buy_in_price", "sell_out_price", "ring_pull_value",
        "new_outlet_purchase", "volume_ctn",
    )),
    "competitors": (KoboCompetitorMetric, (
        "product_name", "status", "movement_score", "stock_status", "buy_in_price",
        "sell_out_price",
    )),
    "ring_pulls": (KoboRingPullMetric, ("product_name", "qty_ctn")),
}


def _line(values):
    buffer = io.StringIO()
    csv.writer(buffer).writerow(values)
    return buffer.getvalue().encode("utf-8")


@router.get("/api/power-bi/{table}")
def power_bi_csv(
    table: Literal["outlets", "products", "competitors", "ring_pulls", "dealers", "sync_status", "dashboard"],
    api_key: str = Query(default=""),
    start_date: date | None = None,
):
    # ApiKeyName in Web.Contents lets Power BI store this key as a Web API credential.
    expected = settings.power_bi_api_key
    if not expected or not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid Power BI API key")

    if table == "dashboard":
        return _dashboard_csv(start_date)

    if table in {"dealers", "sync_status"}:
        def metadata_stream():
            if table == "dealers":
                from app.data.dealers import REGION_DEALERS
                yield _line(("dealer", "region"))
                for region, dealers in REGION_DEALERS.items():
                    for dealer in dealers:
                        yield _line((dealer, region))
            else:
                yield _line(("database_rows", "first_report_date", "last_report_date",
                             "last_submission_time", "last_full_sync_utc", "sync_status",
                             "kobo_rows_at_sync", "synced_rows", "skipped_rows", "details"))
                with SessionLocal() as db:
                    counts = db.execute(select(func.count(KoboSubmission.id),
                        func.min(KoboSubmission.report_date), func.max(KoboSubmission.report_date),
                        func.max(KoboSubmission.submission_time))).one()
                    log = db.scalar(select(SyncLog).where(SyncLog.source == "kobo_bi_full")
                                    .order_by(SyncLog.id.desc()).limit(1))
                    yield _line((*counts, log.created_at if log else None,
                                 log.status if log else "never_synced",
                                 log.fetched if log else None, log.synced if log else None,
                                 log.skipped if log else None, log.message if log else None))
        return StreamingResponse(metadata_stream(), media_type="text/csv; charset=utf-8",
                                 headers={"Cache-Control": "private, no-store"})

    parent = KoboSubmission
    if table == "outlets":
        headers = (*OUTLET_FIELDS, "is_summary")
        stmt = select(*(getattr(parent, field) for field in OUTLET_FIELDS))
        stmt = stmt.order_by(parent.id)
    else:
        model, fields = METRICS[table]
        headers = ("submission_db_id", "report_date", "region", "dealer", "outlet_name",
                   "report_type", "is_summary", "metric_id", *fields)
        stmt = select(
            parent.id, parent.report_date, parent.region, parent.dealer,
            parent.outlet_name, parent.report_type, model.id,
            *(getattr(model, field) for field in fields),
        ).join(model, model.submission_id == parent.id).order_by(parent.id, model.id)
    if start_date:
        stmt = stmt.where(parent.report_date >= start_date)

    def stream():
        yield _line(headers)
        with SessionLocal() as session:
            for row in session.execute(stmt).yield_per(1000):
                values = list(row)
                if table == "outlets":
                    values.append(is_summary_name(values[OUTLET_FIELDS.index("outlet_name")]))
                else:
                    values.insert(6, is_summary_name(values[4]))
                yield _line(values)

    return StreamingResponse(
        stream(), media_type="text/csv; charset=utf-8",
        headers={"Cache-Control": "private, no-store", "Content-Disposition": f'attachment; filename="market_survey_{table}.csv"'},
    )


def _dashboard_csv(start_date=None):
    from app.services.dashboard_feed import HEADERS, dashboard_values
    from app.services.offline_locations import get_boundary_index
    get_boundary_index()  # Fail before sending a CSV header if map is missing.
    fields = ("report_date", "region", "dealer", "outlet_name", "outlet_type",
              "phone_number", "gps_latitude", "gps_longitude", "key_issue_text",
              "suggestion_text", "submission_id", "report_type", "submission_time")
    stmt = select(*(getattr(KoboSubmission, name) for name in fields),
                  KoboProductMetric.product_name, KoboProductMetric.available,
                  KoboProductMetric.movement_score).join(
                      KoboProductMetric, KoboProductMetric.submission_id == KoboSubmission.id
                  ).order_by(KoboSubmission.id, KoboProductMetric.id)
    if start_date:
        stmt = stmt.where(KoboSubmission.report_date >= start_date)
    with SessionLocal() as session:
        latest = session.scalar(select(SyncLog).where(SyncLog.source == "kobo_bi_full", SyncLog.status == "success")
                                .order_by(SyncLog.id.desc()).limit(1))
        synced_at = str(latest.created_at) if latest else ""
        sync_state = "ready" if latest else "initial-sync-in-progress"
    def dashboard_stream():
        yield _line(HEADERS)
        with SessionLocal() as session:
            rows = session.execute(stmt).mappings().yield_per(1000)
            for values in dashboard_values(rows):
                yield _line(values)
    return StreamingResponse(dashboard_stream(), media_type="text/csv; charset=utf-8",
        headers={"Cache-Control": "private, no-store", "X-BI-Last-Sync-UTC": synced_at, "X-BI-Sync-State": sync_state,
                 "Content-Disposition": 'attachment; filename="market_survey_dashboard.csv"'})



@router.get("/powerbi/market_survey_dashboard.csv")
def public_dashboard_csv(start_date: date | None = None):
    """Optional anonymous CSV, matching the user's older BI project."""
    if not settings.power_bi_public_csv_enabled:
        raise HTTPException(status_code=404, detail="Public CSV is disabled")
    return _dashboard_csv(start_date)


@router.get("/powerbi/market_survey_submissions.csv")
def public_submissions_csv():
    """One row per stored Kobo submission, including summary/incomplete rows."""
    if not settings.power_bi_public_csv_enabled:
        raise HTTPException(404, detail="Public CSV is disabled")
    with SessionLocal() as db:
        latest = db.scalar(select(SyncLog).where(SyncLog.source == "kobo_bi_full", SyncLog.status == "success")
                           .order_by(SyncLog.id.desc()).limit(1))
        sync_state = "ready" if latest else "initial-sync-in-progress"
    def stream():
        yield _line((*OUTLET_FIELDS, "is_summary"))
        with SessionLocal() as db:
            rows = db.execute(select(*(getattr(KoboSubmission, f) for f in OUTLET_FIELDS))
                              .order_by(KoboSubmission.id)).yield_per(1000)
            name_index = OUTLET_FIELDS.index("outlet_name")
            for row in rows:
                yield _line((*row, is_summary_name(row[name_index])))
    return StreamingResponse(stream(), media_type="text/csv; charset=utf-8",
                             headers={"Cache-Control": "no-store", "X-BI-Sync-State": sync_state})


@router.get("/powerbi/market_survey_sync_status.csv")
def public_sync_status_csv():
    """Public aggregate progress only; no credentials or outlet details."""
    if not settings.power_bi_public_csv_enabled:
        raise HTTPException(404, detail="Public CSV is disabled")
    with SessionLocal() as db:
        count, first, last = db.execute(select(func.count(KoboSubmission.id),
            func.min(KoboSubmission.report_date), func.max(KoboSubmission.report_date))).one()
        log = db.scalar(select(SyncLog).where(SyncLog.source == "kobo_bi_full")
                        .order_by(SyncLog.id.desc()).limit(1))
        content = _line(("Saved Submissions", "First Report Date", "Last Report Date",
                         "Sync Status", "Fetched Submissions", "Changed Submissions", "Skipped Submissions"))
        content += _line((count, first, last, log.status if log else "not_started",
                         log.fetched if log else None, log.synced if log else None,
                         log.skipped if log else None))
    return StreamingResponse(iter([content]), media_type="text/csv; charset=utf-8",
                             headers={"Cache-Control": "no-store"})
