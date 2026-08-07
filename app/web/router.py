from __future__ import annotations

from datetime import date
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from sqlalchemy import case, func, literal, select, union_all
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import KoboSubmission
from app.db.models import KoboCompetitorMetric, KoboProductMetric
from app.reports.aggregator import OFFTAKE_COMPARE_GROUPS


router = APIRouter()
WEB_DIR = Path(__file__).resolve().parent
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
_OPTIONS_CACHE: tuple[float, dict[str, Any]] | None = None
_OPTIONS_LOCK = Lock()
CAMBODIA_LAT_MIN = 9.20
CAMBODIA_LAT_MAX = 15.70
CAMBODIA_LON_MIN = 101.00
CAMBODIA_LON_MAX = 108.50

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


@router.get("/web/map.css")
def map_css():
    return FileResponse(WEB_DIR / "map.css", media_type="text/css", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/web/map.js")
def map_js():
    return FileResponse(WEB_DIR / "map.js", media_type="application/javascript", headers={"Cache-Control": "public, max-age=3600"})


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


def _category_expression(product_column, type_column):
    clauses = [
        (product_column == name, category)
        for name, category in PRODUCT_CATEGORIES.items()
    ]
    return case(
        *clauses,
        else_=case((type_column == "Competitor", "Competitor"), else_="Other"),
    )


def _map_options(db: Session) -> dict[str, Any]:
    """Return compact filter metadata without loading child ORM collections."""
    global _OPTIONS_CACHE
    now = monotonic()
    with _OPTIONS_LOCK:
        if _OPTIONS_CACHE and now - _OPTIONS_CACHE[0] < 120:
            return _OPTIONS_CACHE[1]

    submission_values = db.execute(
        select(
            KoboSubmission.region,
            KoboSubmission.dealer,
            KoboSubmission.report_date,
            KoboSubmission.province,
            KoboSubmission.district,
            KoboSubmission.commune,
        )
        .where(
            KoboSubmission.gps_latitude.between(CAMBODIA_LAT_MIN, CAMBODIA_LAT_MAX),
            KoboSubmission.gps_longitude.between(CAMBODIA_LON_MIN, CAMBODIA_LON_MAX),
        )
        .distinct()
    ).all()
    product_names = set(
        db.scalars(
            select(KoboProductMetric.product_name)
            .where(KoboProductMetric.movement_score.between(1, 10))
            .distinct()
        ).all()
    )
    product_names.update(
        db.scalars(
            select(KoboCompetitorMetric.product_name)
            .where(KoboCompetitorMetric.movement_score.between(1, 10))
            .distinct()
        ).all()
    )
    products = sorted(name for name in product_names if name)
    products_by_category: dict[str, list[str]] = {}
    for name in products:
        category = PRODUCT_CATEGORIES.get(name, "Other")
        products_by_category.setdefault(category, []).append(name)
    options = {
        "regions": sorted({row.region for row in submission_values if row.region}),
        "dealers": sorted({row.dealer for row in submission_values if row.dealer}),
        "dates": sorted(
            {row.report_date.isoformat() for row in submission_values if row.report_date},
            reverse=True,
        ),
        "provinces": sorted({row.province for row in submission_values if row.province}),
        "districts": sorted({row.district for row in submission_values if row.district}),
        "communes": sorted({row.commune for row in submission_values if row.commune}),
        "products": products,
        "categories": sorted(products_by_category),
        "products_by_category": products_by_category,
    }
    with _OPTIONS_LOCK:
        _OPTIONS_CACHE = (now, options)
    return options


@router.get("/api/map/data")
def map_data(
    response: Response,
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
    response.headers["Cache-Control"] = "private, max-age=30, stale-while-revalidate=120"
    metrics = union_all(
        select(
            KoboProductMetric.submission_id.label("submission_id"),
            KoboProductMetric.id.label("metric_id"),
            KoboProductMetric.product_name.label("product"),
            KoboProductMetric.movement_score.label("movement"),
            KoboProductMetric.stock_status.label("stock_status"),
            KoboProductMetric.status.label("sales_status"),
            literal("Own").label("product_type"),
        ),
        select(
            KoboCompetitorMetric.submission_id.label("submission_id"),
            KoboCompetitorMetric.id.label("metric_id"),
            KoboCompetitorMetric.product_name.label("product"),
            KoboCompetitorMetric.movement_score.label("movement"),
            KoboCompetitorMetric.stock_status.label("stock_status"),
            KoboCompetitorMetric.status.label("sales_status"),
            literal("Competitor").label("product_type"),
        ),
    ).subquery("map_metrics")
    category_expr = _category_expression(metrics.c.product, metrics.c.product_type)
    stmt = select(
        KoboSubmission.id.label("submission_id"),
        KoboSubmission.submission_id.label("submission_uid"),
        KoboSubmission.outlet_name,
        KoboSubmission.outlet_type,
        KoboSubmission.phone_number.label("phone"),
        KoboSubmission.submitter_name.label("submitter"),
        KoboSubmission.region,
        KoboSubmission.dealer,
        KoboSubmission.report_date,
        KoboSubmission.submission_time.label("submitted_at"),
        KoboSubmission.gps_latitude.label("latitude"),
        KoboSubmission.gps_longitude.label("longitude"),
        KoboSubmission.location_text.label("location"),
        KoboSubmission.province,
        KoboSubmission.district,
        KoboSubmission.commune,
        KoboSubmission.village,
        KoboSubmission.key_issue_text.label("key_issue"),
        metrics.c.metric_id,
        metrics.c.product,
        metrics.c.product_type,
        metrics.c.movement,
        metrics.c.stock_status,
        metrics.c.sales_status,
        category_expr.label("category"),
    ).join(metrics, metrics.c.submission_id == KoboSubmission.id).where(
        KoboSubmission.gps_latitude.between(CAMBODIA_LAT_MIN, CAMBODIA_LAT_MAX),
        KoboSubmission.gps_longitude.between(CAMBODIA_LON_MIN, CAMBODIA_LON_MAX),
        metrics.c.movement.between(1, 10),
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

    if category:
        stmt = stmt.where(category_expr.in_(category))
    if product:
        stmt = stmt.where(metrics.c.product.in_(product))
    if movement:
        try:
            ranges = [
                tuple(int(value) for value in selected_range.split("-", 1))
                for selected_range in movement
            ]
            stmt = stmt.where(
                *[
                    metrics.c.movement.between(low, high)
                    for low, high in ranges
                ]
            ) if len(ranges) == 1 else stmt.where(
                metrics.c.movement.in_(
                    [score for low, high in ranges for score in range(low, high + 1)]
                )
            )
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid movement range")
    filtered = stmt.subquery("filtered_map_rows")
    summary_row = db.execute(
        select(
            func.count(func.distinct(filtered.c.submission_id)).label("outlets"),
            func.count().label("ratings"),
            func.count(func.distinct(filtered.c.region)).label("regions"),
            func.count(func.distinct(filtered.c.dealer)).label("dealers"),
            func.count(func.distinct(filtered.c.province)).label("provinces"),
            func.sum(case((filtered.c.movement <= 4, 1), else_=0)).label("very_low"),
            func.sum(case((filtered.c.movement.between(5, 8), 1), else_=0)).label("medium"),
            func.sum(case((filtered.c.movement >= 9, 1), else_=0)).label("very_strong"),
        )
    ).mappings().one()
    ranked = select(
        *filtered.c,
        func.row_number().over(
            partition_by=filtered.c.submission_id,
            order_by=(filtered.c.movement.asc(), filtered.c.metric_id.asc()),
        ).label("marker_rank"),
    ).subquery("ranked_map_rows")
    # Keep the phone response deliberately small while allowing a useful
    # desktop overview. These limits are also part of the map performance
    # contract covered by the existing regression suite.
    marker_limit = 250 if mobile else 1200
    marker_rows = db.execute(
        select(ranked)
        .where(ranked.c.marker_rank == 1)
        .order_by(ranked.c.report_date.desc(), ranked.c.submission_id.desc())
        .limit(marker_limit)
    ).mappings().all()
    markers = []
    for result in marker_rows:
        row = dict(result)
        row.pop("marker_rank", None)
        row["id"] = f'{row["submission_id"]}-{row["product_type"]}-{row["metric_id"]}'
        row["outlet_name"] = row.get("outlet_name") or "Unnamed outlet"
        row["report_date"] = row["report_date"].isoformat() if row.get("report_date") else ""
        row["submitted_at"] = row["submitted_at"].isoformat() if row.get("submitted_at") else ""
        row["band"] = _score_band(int(row["movement"]))
        for key in ("outlet_type", "phone", "submitter", "region", "dealer", "location", "province", "district", "commune", "village", "stock_status", "sales_status", "key_issue"):
            row[key] = row.get(key) or ""
        markers.append(row)
    outlet_count = int(summary_row["outlets"] or 0)
    return {
        # The table was removed. Product details are fetched only after a user
        # taps a marker, keeping the first mobile response small.
        "rows": [],
        "markers": markers,
        "total_ratings": int(summary_row["ratings"] or 0),
        "rows_truncated": False,
        "markers_truncated": outlet_count > len(markers),
        "can_edit": bool(settings.map_editor_token.strip() and access == settings.map_editor_token.strip()),
        "options": _map_options(db),
        "summary": {
            "outlets": outlet_count,
            "ratings": int(summary_row["ratings"] or 0),
            "regions": int(summary_row["regions"] or 0),
            "dealers": int(summary_row["dealers"] or 0),
            "provinces": int(summary_row["provinces"] or 0),
            "very_low": int(summary_row["very_low"] or 0),
            "medium": int(summary_row["medium"] or 0),
            "very_strong": int(summary_row["very_strong"] or 0),
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
