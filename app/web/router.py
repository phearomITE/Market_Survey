from __future__ import annotations

from datetime import date
import hmac
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.data.dealers import REGION_DEALERS
from app.db.database import SessionLocal
from app.db.models import KoboCompetitorMetric, KoboProductMetric, KoboSubmission


router = APIRouter(tags=["movement-map"])
WEB_DIR = Path(__file__).resolve().parent


def _authorize(access: str | None, header_token: str | None) -> None:
    if not settings.map_public_view_enabled:
        raise HTTPException(status_code=403, detail="Movement map is disabled")
    expected = settings.map_viewer_token.strip()
    if expected and not hmac.compare_digest((access or header_token or "").strip(), expected):
        raise HTTPException(status_code=401, detail="Invalid or missing map access token")


def _category(name: str) -> str:
    lowered = name.lower()
    if any(value in lowered for value in ("water", "vital", "provida", "ganzberg", "hitech")):
        return "Water"
    if any(value in lowered for value in (" ord", " ncp", "hanuman", "krud lite", "gb snow")):
        return "Beer"
    return "Beverage"


def _level(score: int) -> tuple[str, str]:
    if score <= 4:
        return "Very Low", "#dc2626"
    if score <= 8:
        return "Medium", "#f4b400"
    return "Very Strong", "#15803d"


@router.get("/map", include_in_schema=False)
def map_page():
    return FileResponse(WEB_DIR / "map.html")


@router.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(WEB_DIR / "map.html")


@router.get("/api/map/filters")
def map_filters(
    access: str | None = None,
    x_map_viewer_token: str | None = Header(default=None, alias="X-Map-Viewer-Token"),
):
    _authorize(access, x_map_viewer_token)
    with SessionLocal() as db:
        dates = db.execute(
            select(KoboSubmission.report_date)
            .where(KoboSubmission.report_date.is_not(None))
            .distinct()
            .order_by(KoboSubmission.report_date.desc())
        ).scalars().all()
        own_products = db.execute(
            select(KoboProductMetric.product_name).distinct()
        ).scalars().all()
        competitor_products = db.execute(
            select(KoboCompetitorMetric.product_name).distinct()
        ).scalars().all()
    products = sorted({
        name for name in [*own_products, *competitor_products] if name
    })
    return {
        "regions": REGION_DEALERS,
        "report_dates": [value.isoformat() for value in dates],
        "products": products,
        "categories": ["Beer", "Beverage", "Water"],
    }


@router.get("/api/map/data")
def map_data(
    access: str | None = None,
    region: str | None = Query(default=None, max_length=30),
    dealer: str | None = Query(default=None, max_length=30),
    report_date: date | None = None,
    category: str | None = Query(default=None, max_length=30),
    product: str | None = Query(default=None, max_length=255),
    movement_min: int = Query(default=0, ge=0, le=10),
    movement_max: int = Query(default=10, ge=0, le=10),
    x_map_viewer_token: str | None = Header(default=None, alias="X-Map-Viewer-Token"),
):
    _authorize(access, x_map_viewer_token)
    if movement_min > movement_max:
        raise HTTPException(status_code=422, detail="Invalid movement range")
    query = (
        select(KoboSubmission)
        .options(
            selectinload(KoboSubmission.product_metrics),
            selectinload(KoboSubmission.competitor_metrics),
        )
        .where(
            KoboSubmission.gps_latitude.is_not(None),
            KoboSubmission.gps_longitude.is_not(None),
        )
        .order_by(KoboSubmission.submission_time.desc(), KoboSubmission.id.desc())
    )
    if region:
        query = query.where(KoboSubmission.region == region)
    if dealer:
        query = query.where(KoboSubmission.dealer == dealer)
    if report_date:
        query = query.where(KoboSubmission.report_date == report_date)

    with SessionLocal() as db:
        submissions = db.execute(query).scalars().all()

    rows: list[dict[str, Any]] = []
    outlet_ids: set[int] = set()
    for submission in submissions:
        if not (-90 <= submission.gps_latitude <= 90 and -180 <= submission.gps_longitude <= 180):
            continue
        metrics = [
            *((item, "own") for item in submission.product_metrics),
            *((item, "competitor") for item in submission.competitor_metrics),
        ]
        for metric, source in metrics:
            score = metric.movement_score
            if score is None or not 0 <= score <= 10 or not movement_min <= score <= movement_max:
                continue
            product_category = _category(metric.product_name)
            if category and category != product_category:
                continue
            if product and product != metric.product_name:
                continue
            level, color = _level(score)
            outlet_ids.add(submission.id)
            rows.append({
                "id": f"{submission.submission_id}:{source}:{metric.id}",
                "outlet_name": submission.outlet_name or "Unnamed outlet",
                "outlet_type": submission.outlet_type or "—",
                "phone_number": submission.phone_number or "—",
                "region": submission.region or "—",
                "dealer": submission.dealer or "—",
                "location": submission.location_text or "—",
                "product": metric.product_name,
                "product_source": source,
                "category": product_category,
                "stock_status": metric.stock_status or "—",
                "status": metric.status or "—",
                "movement_score": score,
                "movement_level": level,
                "movement_color": color,
                "key_issue": submission.key_issue_text or "—",
                "report_date": submission.report_date.isoformat() if submission.report_date else None,
                "submitted_at": submission.submission_time.isoformat() if submission.submission_time else None,
                "latitude": submission.gps_latitude,
                "longitude": submission.gps_longitude,
            })
    by_score = {str(score): sum(1 for row in rows if row["movement_score"] == score) for score in range(11)}
    return {
        "rows": rows,
        "summary": {
            "total_outlets": len(outlet_ids),
            "total_ratings": len(rows),
            "own_wins_10": sum(1 for row in rows if row["product_source"] == "own" and row["movement_score"] == 10),
            "competitor_wins_10": sum(1 for row in rows if row["product_source"] == "competitor" and row["movement_score"] == 10),
            "very_low": sum(1 for row in rows if row["movement_score"] <= 4),
            "medium": sum(1 for row in rows if 5 <= row["movement_score"] <= 8),
            "very_strong": sum(1 for row in rows if row["movement_score"] >= 9),
            "with_issue": len({row["outlet_name"] for row in rows if row["key_issue"] != "—"}),
            "by_score": by_score,
        },
    }
