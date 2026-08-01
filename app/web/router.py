from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import KoboSubmission
from app.db.models import KoboCompetitorMetric, KoboProductMetric
from app.reports.aggregator import OFFTAKE_COMPARE_GROUPS, OWN_PRODUCTS


router = APIRouter()
WEB_DIR = Path(__file__).resolve().parent
OWN_PRODUCT_SET = set(OWN_PRODUCTS)
APPROVED_REPORT_DATES = (
    date(2026, 7, 4),
    date(2026, 7, 18),
    date(2026, 7, 25),
)


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

# Competitor products inherit the category of the own product at the start of
# their comparison group. This prevents beer competitors appearing under the
# generic "Competitor" category.
for comparison_group in OFFTAKE_COMPARE_GROUPS:
    own_product = comparison_group[0]
    category = PRODUCT_CATEGORIES.get(own_product, "Other")
    for compared_product in comparison_group:
        PRODUCT_CATEGORIES.setdefault(compared_product, category)


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _authorize(access: str = Query(default="")) -> str:
    if not settings.map_public_view_enabled:
        raise HTTPException(status_code=404, detail="Map viewer is disabled")
    valid_tokens = {token for token in (settings.map_viewer_token.strip(), settings.map_editor_token.strip()) if token}
    if valid_tokens and access not in valid_tokens:
        raise HTTPException(status_code=401, detail="Invalid map access token")
    return access


def _authorize_edit(access: str = Query(default="")) -> str:
    editor = settings.map_editor_token.strip()
    if not editor or access != editor:
        raise HTTPException(status_code=403, detail="Editor access required")
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
    if metric.movement_score is None or int(metric.movement_score) <= 0:
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
        "province": submission.province or "",
        "district": submission.district or "",
        "commune": submission.commune or "",
        "village": submission.village or "",
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
    region: list[str] = Query(default=[]),
    dealer: list[str] = Query(default=[]),
    report_date: list[str] = Query(default=[]),
    category: list[str] = Query(default=[]),
    product: list[str] = Query(default=[]),
    movement: list[str] = Query(default=[]),
    province: list[str] = Query(default=[]),
    district: list[str] = Query(default=[]),
    commune: list[str] = Query(default=[]),
    mobile: bool = False,
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
            KoboSubmission.report_date.in_(APPROVED_REPORT_DATES),
        )
        .order_by(KoboSubmission.report_date.desc(), KoboSubmission.id.desc())
    )
    if region:
        stmt = stmt.where(KoboSubmission.region.in_(region))
    if dealer:
        stmt = stmt.where(KoboSubmission.dealer.in_(dealer))
    if report_date:
        try:
            parsed_dates = [date.fromisoformat(value) for value in report_date]
            stmt = stmt.where(KoboSubmission.report_date.in_(parsed_dates))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid report date")
    if province:
        stmt = stmt.where(KoboSubmission.province.in_(province))
    if district:
        stmt = stmt.where(KoboSubmission.district.in_(district))
    if commune:
        stmt = stmt.where(KoboSubmission.commune.in_(commune))

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
        "products_by_category": {
            category_name: sorted({
                row["product"] for row in all_rows
                if row["category"] == category_name and row["product"]
            })
            for category_name in sorted({row["category"] for row in all_rows if row["category"]})
        },
        "provinces": sorted({row["province"] for row in all_rows if row["province"]}),
        "districts": sorted({row["district"] for row in all_rows if row["district"]}),
        "communes": sorted({row["commune"] for row in all_rows if row["commune"]}),
    }
    rows = all_rows
    if category:
        rows = [row for row in rows if row["category"] in category]
    if product:
        rows = [row for row in rows if row["product"] in product]
    if movement:
        try:
            ranges = [
                tuple(int(value) for value in selected_range.split("-", 1))
                for selected_range in movement
            ]
            rows = [
                row for row in rows
                if any(low <= row["movement"] <= high for low, high in ranges)
            ]
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid movement range")

    outlet_count = len({row["submission_id"] for row in rows})
    own_scores = [row for row in rows if row["product_type"] == "Own"]
    competitor_scores = [row for row in rows if row["product_type"] == "Competitor"]
    by_region = Counter(row["region"] or "Unknown" for row in rows)
    by_dealer = Counter(row["dealer"] or "Unknown" for row in rows)
    by_product = Counter(row["product"] for row in rows)

    # Never send every product row and a marker for every product to the
    # browser. A large Kobo dataset can contain hundreds of thousands of
    # ratings and will freeze Chrome/Telegram WebView. Keep all calculations
    # above exact, but return a bounded table page and one representative
    # marker per outlet. The marker uses the lowest score at that outlet so
    # operational problems remain visible without calculating an average.
    marker_by_submission: dict[int, dict[str, Any]] = {}
    for row in rows:
        current = marker_by_submission.get(row["submission_id"])
        if current is None or row["movement"] < current["movement"]:
            marker_by_submission[row["submission_id"]] = row

    markers = []
    marker_limit = 60 if mobile else 700
    for submission_id, representative in marker_by_submission.items():
        marker = dict(representative)
        markers.append(marker)
        if len(markers) >= marker_limit:
            break
    return {
        # The table was removed. Product details are fetched only after a user
        # taps a marker, keeping the first mobile response small.
        "rows": [],
        "markers": markers,
        "total_ratings": len(rows),
        "rows_truncated": False,
        "markers_truncated": outlet_count > len(markers),
        "can_edit": bool(settings.map_editor_token.strip() and access == settings.map_editor_token.strip()),
        "options": options,
        "summary": {
            "outlets": outlet_count,
            "ratings": len(rows),
            "regions": len({row["region"] for row in rows if row["region"]}),
            "dealers": len({row["dealer"] for row in rows if row["dealer"]}),
            "provinces": len({row["province"] for row in rows if row["province"]}),
            "own_products": len(own_scores),
            "competitor_products": len(competitor_scores),
            "own_wins": sum(1 for row in own_scores if row["movement"] == 10),
            "competitor_wins": sum(1 for row in competitor_scores if row["movement"] == 10),
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


@router.get("/api/map/outlets/{submission_id}/ratings")
def outlet_product_ratings(
    submission_id: int,
    access: str = Depends(_authorize),
    category: list[str] = Query(default=[]),
    product: list[str] = Query(default=[]),
    movement: list[str] = Query(default=[]),
    db: Session = Depends(_db),
):
    submission = db.execute(
        select(KoboSubmission)
        .options(
            selectinload(KoboSubmission.product_metrics),
            selectinload(KoboSubmission.competitor_metrics),
        )
        .where(KoboSubmission.id == submission_id)
    ).scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Outlet submission not found")
    rows: list[dict[str, Any]] = []
    for metric in submission.product_metrics:
        row = _metric_row(submission, metric, "Own")
        if row:
            rows.append(row)
    for metric in submission.competitor_metrics:
        row = _metric_row(submission, metric, "Competitor")
        if row:
            rows.append(row)
    if category:
        rows = [row for row in rows if row["category"] in category]
    if product:
        rows = [row for row in rows if row["product"] in product]
    if movement:
        try:
            ranges = [
                tuple(int(value) for value in selected_range.split("-", 1))
                for selected_range in movement
            ]
            rows = [
                row for row in rows
                if any(low <= row["movement"] <= high for low, high in ranges)
            ]
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid movement range")
    return {"rows": rows}


class RatingEdit(BaseModel):
    movement: int = Field(ge=0, le=10)
    stock_status: str = Field(default="", max_length=80)
    key_issue: str = Field(default="", max_length=5000)


@router.put("/api/map/ratings/{row_id}")
def edit_rating(row_id: str, payload: RatingEdit, access: str = Depends(_authorize_edit), db: Session = Depends(_db)):
    try:
        submission_id, product_type, metric_id = row_id.rsplit("-", 2)
        submission_pk, metric_pk = int(submission_id), int(metric_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid rating identifier")
    model = KoboProductMetric if product_type == "Own" else KoboCompetitorMetric
    metric = db.get(model, metric_pk)
    submission = db.get(KoboSubmission, submission_pk)
    if not metric or not submission or metric.submission_id != submission.id:
        raise HTTPException(status_code=404, detail="Rating not found")
    metric.movement_score = payload.movement
    metric.stock_status = payload.stock_status.strip() or None
    submission.key_issue_text = payload.key_issue.strip() or None
    db.commit()
    return {"status": "updated"}
