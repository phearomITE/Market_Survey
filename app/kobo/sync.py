from __future__ import annotations

from threading import Lock

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.db.database import SessionLocal, init_db
from app.db.models import (
    KoboCompetitorMetric,
    KoboProductMetric,
    KoboRingPullMetric,
    KoboSubmission,
    SyncLog,
)
from app.kobo.client import KoboClient
from app.kobo.parser import normalize_submission, to_float, to_int, yes_value
from app.db.kobo_wide import upsert_wide_submission
_SYNC_LOCK = Lock()

from app.reports.aggregator import (
    COMPETITOR_PRODUCTS,
    OWN_PRODUCTS,
    RING_PRODUCTS,
    STATUS_AVAILABLE,
    competitor_field,
    first_value,
    product_field,
)


def _status_to_mov(value) -> int | None:
    if value in (None, ""):
        return None
    s = str(value).strip()
    mapping = {
        "no_sale": 0,
        "sale": 5,
        "fast_sale": 10,
        "អត់មានលក់": 0,
        "មានលក់": 5,
        "លក់ដាច់": 10,
    }
    return mapping.get(s) if s in mapping else mapping.get(s.lower())


def _has_any_product_detail(flat: dict, product: str) -> bool:
    for field in ("mov", "bbe", "stock", "buy_in", "sell_out", "ring_pull", "volume", "new_purchase"):
        if first_value(flat, product_field(product, field)) not in (None, ""):
            return True
    return False


def _product_metrics_from_flat(flat: dict) -> list[dict]:
    rows: list[dict] = []
    for product in OWN_PRODUCTS:
        status = first_value(flat, product_field(product, "status"))
        score = first_value(flat, product_field(product, "mov"))
        movement = to_int(score)
        if movement is None:
            movement = _status_to_mov(status)
        available = False
        if status not in (None, ""):
            available = str(status).strip().lower() in STATUS_AVAILABLE or str(status).strip() in STATUS_AVAILABLE
        else:
            available = _has_any_product_detail(flat, product)

        values = {
            "product_name": product,
            "status": str(status).strip() if status not in (None, "") else None,
            "available": bool(available),
            "movement_score": movement,
            "stock_status": first_value(flat, product_field(product, "stock")),
            "bbe_date": first_value(flat, product_field(product, "bbe")),
            "buy_in_price": to_float(first_value(flat, product_field(product, "buy_in"))),
            "sell_out_price": to_float(first_value(flat, product_field(product, "sell_out"))),
            "ring_pull_value": to_float(first_value(flat, product_field(product, "ring_pull"))),
            "new_outlet_purchase": yes_value(first_value(flat, product_field(product, "new_purchase"))),
            "volume_ctn": to_float(first_value(flat, product_field(product, "volume"))),
        }

        # Store every product row so reporting has fixed rows, even if blank.
        rows.append(values)
    return rows


def _competitor_metrics_from_flat(flat: dict) -> list[dict]:
    rows: list[dict] = []
    for product in COMPETITOR_PRODUCTS:
        status = first_value(flat, competitor_field(product, "status"))
        score = first_value(flat, competitor_field(product, "mov"))
        movement = to_int(score)
        if movement is None:
            movement = _status_to_mov(status)
        rows.append(
            {
                "product_name": product,
                "status": str(status).strip() if status not in (None, "") else None,
                "movement_score": movement,
                "buy_in_price": to_float(first_value(flat, competitor_field(product, "buy_in"))),
                "sell_out_price": to_float(first_value(flat, competitor_field(product, "sell_out"))),
            }
        )
    return rows


def _ring_pull_metrics_from_flat(flat: dict) -> list[dict]:
    ring_key_map = {
        "CBL NCP 6 Can": [
            "ring_pull_qty_cbl_ncp_6_can",
            "cbl_ncp_6_can_ring_pull_qty_can",
            "cbl_ncp_6_can_ring_pull_qty_ctn",
            "1_cbl_ncp_6_can_ring_pull_qty_can",
            "1_cbl_ncp_6_can_ring_pull_qty_ctn",
            "1. CBL NCP 6 Can - Ring Pull Qty (Can)",
            "1. CBL NCP 6 Can - Ring Pull Qty (ctn)",
            "CBL NCP 6 Can - Ring Pull Qty (Can)",
            "CBL NCP 6 Can - Ring Pull Qty (ctn)",
            "ring_pull_cbl_ncp_6_can",
            "ring_pull_cbl_ncp_6_can_can",
            "ring_pull_cbl_ncp_6_can_ctn",
            "ringpull_cbl_ncp_6_can",
            "ringpull_cbl_ncp_6_can_can",
            "ringpull_cbl_ncp_6_can_ctn",
            "cbl_ncp_6_can_qty",
            "ring_pull_group/ring_pull_qty_cbl_ncp_6_can",
            "ring_pull_group/cbl_ncp_6_can_ring_pull_qty_can",
            "ring_pull_group/cbl_ncp_6_can_ring_pull_qty_ctn",
            "ring_pull_outlets/ring_pull_qty_cbl_ncp_6_can",
            "ring_pull_outlets/cbl_ncp_6_can_ring_pull_qty_can",
            "ring_pull_outlets/cbl_ncp_6_can_ring_pull_qty_ctn",
            "Ring Pull In Outlets/CBL NCP 6 Can",
            "1_cbc_cbl_can_and_cbb_can_ring_pull_qty_ctn",
            "1. CBC, CBL Can and CBB Can - Ring Pull Qty (ctn)",
            "ring_pull_cbc_cbl_cbb_can_ctn",
            "ringpull_cbc_cbl_cbb_can_ctn",
            "ringpull_cbc_cbl_cbb_can_qty",
            "cbc_cbl_cbb_can_qty",
            "ring_pull_group/ring_pull_cbc_cbl_cbb_can_ctn",
            "ring_pull_outlets/ring_pull_cbc_cbl_cbb_can_ctn",
        ],
        "CBL NCP 5 USD": [
            "ring_pull_qty_cbl_ncp_5_usd",
            "cbl_ncp_5_usd_ring_pull_qty_can",
            "cbl_ncp_5_usd_ring_pull_qty_ctn",
            "2_cbl_ncp_5_usd_ring_pull_qty_can",
            "2_cbl_ncp_5_usd_ring_pull_qty_ctn",
            "2. CBL NCP 5 USD - Ring Pull Qty (Can)",
            "2. CBL NCP 5 USD - Ring Pull Qty (ctn)",
            "CBL NCP 5 USD - Ring Pull Qty (Can)",
            "CBL NCP 5 USD - Ring Pull Qty (ctn)",
            "ring_pull_cbl_ncp_5_usd",
            "ring_pull_cbl_ncp_5_usd_can",
            "ring_pull_cbl_ncp_5_usd_ctn",
            "ringpull_cbl_ncp_5_usd",
            "ringpull_cbl_ncp_5_usd_can",
            "ringpull_cbl_ncp_5_usd_ctn",
            "cbl_ncp_5_usd_qty",
            "ring_pull_group/ring_pull_qty_cbl_ncp_5_usd",
            "ring_pull_group/cbl_ncp_5_usd_ring_pull_qty_can",
            "ring_pull_group/cbl_ncp_5_usd_ring_pull_qty_ctn",
            "ring_pull_outlets/ring_pull_qty_cbl_ncp_5_usd",
            "ring_pull_outlets/cbl_ncp_5_usd_ring_pull_qty_can",
            "ring_pull_outlets/cbl_ncp_5_usd_ring_pull_qty_ctn",
            "Ring Pull In Outlets/CBL NCP 5 USD",
            "2_wurkz_ncp_5_usd_ring_pull_qty_ctn",
            "2. Wurkz NCP 5 USD - Ring Pull Qty (ctn)",
            "ring_pull_wurkz_ncp_5usd_ctn",
            "ringpull_wurkz_ncp_5usd_ctn",
            "ringpull_wurkz_ncp_5_usd_qty",
            "wurkz_ncp_5usd_qty",
            "ring_pull_group/ring_pull_wurkz_ncp_5usd_ctn",
            "ring_pull_outlets/ring_pull_wurkz_ncp_5usd_ctn",
        ],
    }
    out: list[dict] = []
    for product in RING_PRODUCTS:
        out.append({"product_name": product, "qty_ctn": to_int(first_value(flat, ring_key_map[product])) or 0})
    return out


def _replace_metric_rows(db, submission_db_id: int, flat: dict) -> None:
    db.execute(delete(KoboProductMetric).where(KoboProductMetric.submission_id == submission_db_id))
    db.execute(delete(KoboCompetitorMetric).where(KoboCompetitorMetric.submission_id == submission_db_id))
    db.execute(delete(KoboRingPullMetric).where(KoboRingPullMetric.submission_id == submission_db_id))

    for row in _product_metrics_from_flat(flat):
        db.add(KoboProductMetric(submission_id=submission_db_id, **row))
    for row in _competitor_metrics_from_flat(flat):
        db.add(KoboCompetitorMetric(submission_id=submission_db_id, **row))
    for row in _ring_pull_metrics_from_flat(flat):
        db.add(KoboRingPullMetric(submission_id=submission_db_id, **row))


def _sync_kobo_unlocked() -> dict:
    """Pull Kobo submissions and upsert into normalized PostgreSQL tables.

    Each Kobo submission is one outlet visit.
    No raw JSONB payload is stored in the production database.
    """
    init_db()
    rows = KoboClient().fetch_submissions()
    synced = 0
    skipped = 0
    skipped_reasons: list[str] = []

    with SessionLocal() as db:
        for raw in rows:
            data = normalize_submission(raw)
            flat = data.pop("_flat", {}) or {}

            missing = [k for k in ("submission_id", "dealer", "report_date") if not data.get(k)]
            if missing:
                skipped += 1
                if len(skipped_reasons) < 5:
                    skipped_reasons.append(f"missing {','.join(missing)} from keys={list(raw.keys())[:12]}")
                continue

            # Store every Kobo question/answer into kobo_submissions_wide as real SQL columns.
            # This is not JSONB; each Kobo field gets a safe dynamic column and the
            # kobo_field_map table keeps the original question label.
            upsert_wide_submission(flat, data)

            stmt = insert(KoboSubmission).values(**data).on_conflict_do_update(
                index_elements=["submission_id"],
                set_={k: v for k, v in data.items() if k != "submission_id"},
            )
            db.execute(stmt)
            db.flush()

            sub = db.scalar(select(KoboSubmission).where(KoboSubmission.submission_id == data["submission_id"]))
            if sub is None:
                skipped += 1
                skipped_reasons.append(f"could not re-read submission_id={data['submission_id']}")
                continue

            _replace_metric_rows(db, sub.id, flat)
            synced += 1

        message = f"fetched {len(rows)}, synced {synced}, skipped {skipped}"
        if skipped_reasons:
            message += " | " + " || ".join(skipped_reasons[:5])
        db.add(SyncLog(status="success", message=message, fetched=len(rows), synced=synced, skipped=skipped))
        db.commit()

    print(f"✅ Kobo sync: fetched={len(rows)} synced={synced} skipped={skipped}")
    if skipped_reasons:
        print("⚠️ Skipped examples:")
        for reason in skipped_reasons:
            print(" -", reason)
    return {"fetched": len(rows), "synced": synced, "skipped": skipped, "skipped_reasons": skipped_reasons}


def sync_kobo() -> dict:
    """Thread-safe Kobo sync used by manual command, auto polling and report retry."""
    if not _SYNC_LOCK.acquire(blocking=False):
        print("ℹ️ Kobo sync already running; skipping overlapping sync.")
        return {"fetched": 0, "synced": 0, "skipped": 0, "skipped_reasons": ["sync already running"]}
    try:
        return _sync_kobo_unlocked()
    finally:
        _SYNC_LOCK.release()


if __name__ == "__main__":
    print(sync_kobo())
