"""Read-only CSV feeds for Power BI's Web connector."""
import csv
import io
import secrets
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.config import settings
from app.core.summary_marker import is_summary_name
from app.db.database import SessionLocal
from app.db.models import (
    KoboCompetitorMetric, KoboProductMetric, KoboRingPullMetric, KoboSubmission,
)

router = APIRouter()

# Explicit allowlists prevent accidental disclosure of new database columns.
OUTLET_FIELDS = (
    "id", "submission_id", "report_date", "submission_time", "region", "dealer",
    "group_no", "member_no", "total_outlet_visit_target", "outlet_name",
    "outlet_type", "report_type", "is_new_outlet", "submitter_name",
    "location_text", "gps_latitude", "gps_longitude", "key_issue_text",
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
    table: Literal["outlets", "products", "competitors", "ring_pulls"],
    api_key: str = Query(default=""),
    start_date: date | None = None,
):
    # ApiKeyName in Web.Contents lets Power BI store this key as a Web API credential.
    expected = settings.power_bi_api_key
    if not expected or not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid Power BI API key")

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
