from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import KoboSubmission
from app.reports.aggregator import OWN_PRODUCTS


router = APIRouter()
WEB_DIR = Path(__file__).resolve().parent
OWN_PRODUCT_SET = set(OWN_PRODUCTS)


PRODUCT_CATEGORIES = {
    "CB LITE ORD": "Beer",
    "CBC 4.4 NCP": "Beer",
    "CB Original NCP": "Beer",
    "CB LITE NCP": "Beer",
    "CB BLACK NCP": "Beer",
    "CAMBODIA COLA": "Beverage",
    "WURKZ": "Energy Drink",
    "CAMBODIA ED": "Energy Drink",
    "DAZZ": "Energy Drink",
    "DAZZ Zero Sugar": "Energy Drink",
    "EXPREZ Can 330ml": "Beverage",
    "IZE PET 300ml Flavour": "Beverage",
    "IZE COLA PET 1.5L All SKUs": "Beverage",
    "EXPREZ Melon": "Beverage",
    "Wurkz Ice": "Energy Drink",
    "CAMBODIA Sport 300mL": "Sport Drink",
    "CAMBODIA Sport 500mL": "Sport Drink",
    "CAMBODIA WATER 500mL": "Water",
    "CAMBODIA WATER 1500mL": "Water",
}


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _authorize(access: str = Query(default="")) -> str:
    if not settings.map_public_view_enabled:
        raise HTTPException(status_code=404, detail="Map viewer is disabled")
    configured = settings.map_viewer_token.strip()
    if configured and access != configured:
        raise HTTPException(status_code=401, detail="Invalid map access token")
    return access


@router.get("/map", dependencies=[Depends(_authorize)])
def map_page():
    return FileResponse(WEB_DIR / "map.html")


@router.get("/dashboard", dependencies=[Depends(_authorize)])
def dashboard_page():
    return FileResponse(WEB_DIR / "map.html")


@router.get("/web/map.css")
def map_css():
    return FileResponse(WEB_DIR / "map.css", media_type="text/css")


@router.get("/web/map.js")
def map_js():
    return FileResponse(WEB_DIR / "map.js", media_type="application/javascript")


def _score_band(score: int) -> str:
    if score <= 4:
        return "very-low"
    if score <= 8:
        return "medium"
    return "very-strong"


def _metric_row(submission: KoboSubmission, metric: Any, product_type: str) -> dict[str, Any] | None:
    if metric.movement_score is None:
        return None
    score = max(0, min(10, int(metric.movement_score)))
    product = metric.product_name
    return {
        "id": f"{submission.id}-{product_type}-{metric.id}",
        "submission_id": submission.id,
        "submission_uid": submission.submission_id,
        "outlet_name": submission.outlet_name or "Unnamed outlet",
        "outlet_type": submission.outlet_type or "",
        "phone": submission.phone_number or "",
        "submitter": submission.submitter_name or "",
        "region": submission.region or "",
        "dealer": submission.dealer or "",
        "report_date": submission.report_date.isoformat() if submission.report_date else "",
        "submitted_at": submission.submission_time.isoformat() if submission.submission_time else "",
        "latitude": submission.gps_latitude,
        "longitude": submission.gps_longitude,
        "location": submission.location_text or "",
        "product": product,
        "product_type": product_type,
        "category": PRODUCT_CATEGORIES.get(product, "Competitor" if product_type == "Competitor" else "Other"),
        "movement": score,
        "band": _score_band(score),
        "stock_status": metric.stock_status or "",
        "sales_status": metric.status or "",
        "key_issue": submission.key_issue_text or "",
    }


@router.get("/api/map/data")
def map_data(
    access: str = Depends(_authorize),
    region: str = "",
    dealer: str = "",
    report_date: str = "",
    category: str = "",
    product: str = "",
    movement: str = "",
    db: Session = Depends(_db),
):
    stmt = (
        select(KoboSubmission)
        .options(
            selectinload(KoboSubmission.product_metrics),
            selectinload(KoboSubmission.competitor_metrics),
        )
        .where(
            KoboSubmission.gps_latitude.is_not(None),
            KoboSubmission.gps_longitude.is_not(None),
        )
        .order_by(KoboSubmission.report_date.desc(), KoboSubmission.id.desc())
    )
    if region:
        stmt = stmt.where(KoboSubmission.region == region)
    if dealer:
        stmt = stmt.where(KoboSubmission.dealer == dealer)
    if report_date:
        try:
            stmt = stmt.where(KoboSubmission.report_date == date.fromisoformat(report_date))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid report date")

    submissions = db.execute(stmt).scalars().unique().all()
    all_rows: list[dict[str, Any]] = []
    for submission in submissions:
        for metric in submission.product_metrics:
            row = _metric_row(submission, metric, "Own")
            if row:
                all_rows.append(row)
        for metric in submission.competitor_metrics:
            row = _metric_row(submission, metric, "Competitor")
            if row:
                all_rows.append(row)

    options = {
        "regions": sorted({row["region"] for row in all_rows if row["region"]}),
        "dealers": sorted({row["dealer"] for row in all_rows if row["dealer"]}),
        "dates": sorted({row["report_date"] for row in all_rows if row["report_date"]}, reverse=True),
        "categories": sorted({row["category"] for row in all_rows if row["category"]}),
        "products": sorted({row["product"] for row in all_rows if row["product"]}),
    }

    rows = all_rows
    if category:
        rows = [row for row in rows if row["category"] == category]
    if product:
        rows = [row for row in rows if row["product"] == product]
    if movement:
        try:
            low, high = [int(value) for value in movement.split("-", 1)]
            rows = [row for row in rows if low <= row["movement"] <= high]
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid movement range")

    outlet_count = len({row["submission_id"] for row in rows})
    own_scores = [row for row in rows if row["product_type"] == "Own"]
    competitor_scores = [row for row in rows if row["product_type"] == "Competitor"]
    by_region = Counter(row["region"] or "Unknown" for row in rows)
    by_dealer = Counter(row["dealer"] or "Unknown" for row in rows)
    by_product = Counter(row["product"] for row in rows)

    return {
        "rows": rows,
        "options": options,
        "summary": {
            "outlets": outlet_count,
            "ratings": len(rows),
            "own_products": len(own_scores),
            "competitor_products": len(competitor_scores),
            "own_wins": sum(1 for row in own_scores if row["movement"] == 10),
            "very_low": sum(1 for row in rows if row["movement"] <= 4),
            "medium": sum(1 for row in rows if 5 <= row["movement"] <= 8),
            "very_strong": sum(1 for row in rows if row["movement"] >= 9),
            "key_issues": len({row["submission_id"] for row in rows if row["key_issue"].strip()}),
        },
        "charts": {
            "regions": by_region.most_common(8),
            "dealers": by_dealer.most_common(8),
            "products": by_product.most_common(10),
        },
    }
