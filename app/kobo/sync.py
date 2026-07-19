from __future__ import annotations

from threading import Event, Lock
import hashlib
import json
from datetime import date

from sqlalchemy import delete, select, update
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
_SYNC_FINISHED = Event()
_SYNC_FINISHED.set()

from app.reports.aggregator import (
    COMPETITOR_PRODUCTS,
    OWN_PRODUCTS,
    RING_PRODUCTS,
    STATUS_AVAILABLE,
    competitor_field,
    first_value,
    own_product_field_allowed,
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
        if own_product_field_allowed(product, field) and first_value(flat, product_field(product, field)) not in (None, ""):
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
            "stock_status": (
                first_value(flat, product_field(product, "stock"))
                if own_product_field_allowed(product, "stock") else None
            ),
            "bbe_date": (
                first_value(flat, product_field(product, "bbe"))
                if own_product_field_allowed(product, "bbe") else None
            ),
            "buy_in_price": (
                to_float(first_value(flat, product_field(product, "buy_in")))
                if own_product_field_allowed(product, "buy_in") else None
            ),
            "sell_out_price": (
                to_float(first_value(flat, product_field(product, "sell_out")))
                if own_product_field_allowed(product, "sell_out") else None
            ),
            "ring_pull_value": (
                to_float(first_value(flat, product_field(product, "ring_pull")))
                if own_product_field_allowed(product, "ring_pull") else None
            ),
            "new_outlet_purchase": (
                yes_value(first_value(flat, product_field(product, "new_purchase")))
                if own_product_field_allowed(product, "new_purchase") else False
            ),
            "volume_ctn": (
                to_float(first_value(flat, product_field(product, "volume")))
                if own_product_field_allowed(product, "volume") else None
            ),
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
                # V46 competitor form fields are Sale Status + Movement only.
                "stock_status": None,
                "buy_in_price": None,
                "sell_out_price": None,
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


def _source_hash(raw: dict) -> str:
    payload = json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _core_value(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return " ".join(value.strip().split()) or None
    return value


def _core_record_matches(existing: dict, normalized: dict) -> bool:
    """Check fields that must be repaired even when the raw Kobo hash is unchanged.

    This protects against parser fixes such as historical KD1 -> KDL1. The raw
    Kobo submission did not change, but the normalized database value must.
    """
    fields = (
        "dealer",
        "report_date",
        "region",
        "outlet_name",
        "group_no",
        "member_no",
        "summary_report_type",
    )
    return all(
        _core_value(existing.get(field)) == _core_value(normalized.get(field))
        for field in fields
    )


def _sync_kobo_unlocked(dealer: str | None = None, report_date: date | None = None) -> dict:
    """Fetch Kobo rows and upsert only new or changed submissions.

    When dealer/report_date are supplied, only matching rows are processed. This
    makes an on-demand /report sync fast even when the Kobo asset contains many rows.
    """
    init_db()
    rows = KoboClient().fetch_submissions()
    synced = 0
    unchanged = 0
    hash_backfilled = 0
    repaired = 0
    skipped = 0
    matched = 0
    skipped_reasons: list[str] = []

    with SessionLocal() as db:
        existing_records = {
            row.submission_id: {
                "source_hash": row.source_hash,
                "dealer": row.dealer,
                "report_date": row.report_date,
                "region": row.region,
                "outlet_name": row.outlet_name,
                "group_no": row.group_no,
                "member_no": row.member_no,
                "summary_report_type": row.summary_report_type,
            }
            for row in db.execute(
                select(
                    KoboSubmission.submission_id,
                    KoboSubmission.source_hash,
                    KoboSubmission.dealer,
                    KoboSubmission.report_date,
                    KoboSubmission.region,
                    KoboSubmission.outlet_name,
                    KoboSubmission.group_no,
                    KoboSubmission.member_no,
                    KoboSubmission.summary_report_type,
                )
            ).all()
        }

        for raw in rows:
            data = normalize_submission(raw)
            flat = data.pop("_flat", {}) or {}

            if dealer and (data.get("dealer") or "").upper() != dealer.upper():
                continue
            if report_date and data.get("report_date") != report_date:
                continue
            matched += 1

            missing = [k for k in ("submission_id", "dealer", "report_date") if not data.get(k)]
            if missing:
                skipped += 1
                if len(skipped_reasons) < 5:
                    skipped_reasons.append(f"missing {','.join(missing)} from keys={list(raw.keys())[:12]}")
                continue

            source_hash = _source_hash(raw)
            data["source_hash"] = source_hash
            existing = existing_records.get(data["submission_id"])
            existing_hash = existing.get("source_hash") if existing else None
            core_matches = bool(existing and _core_record_matches(existing, data))

            if existing and existing_hash == source_hash and core_matches:
                unchanged += 1
                continue

            # Safe first-run optimization: only backfill the hash when all core
            # normalized values already match. If a parser fix changes Dealer,
            # Date, Member or Summary Template, fully re-upsert the row.
            if existing and existing_hash in (None, "") and core_matches:
                db.execute(
                    update(KoboSubmission)
                    .where(KoboSubmission.submission_id == data["submission_id"])
                    .values(source_hash=source_hash)
                )
                existing["source_hash"] = source_hash
                hash_backfilled += 1
                continue

            if existing and not core_matches:
                repaired += 1

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
            existing_records[data["submission_id"]] = {
                "source_hash": source_hash,
                "dealer": data.get("dealer"),
                "report_date": data.get("report_date"),
                "region": data.get("region"),
                "outlet_name": data.get("outlet_name"),
                "group_no": data.get("group_no"),
                "member_no": data.get("member_no"),
                "summary_report_type": data.get("summary_report_type"),
            }
            synced += 1

        message = (
            f"fetched {len(rows)}, matched {matched}, synced {synced}, "
            f"hash_backfilled {hash_backfilled}, repaired {repaired}, unchanged {unchanged}, skipped {skipped}"
        )
        if skipped_reasons:
            message += " | " + " || ".join(skipped_reasons[:5])
        db.add(SyncLog(status="success", message=message, fetched=len(rows), synced=synced, skipped=skipped))
        db.commit()

    print(
        f"✅ Kobo sync: fetched={len(rows)} matched={matched} synced={synced} "
        f"hash_backfilled={hash_backfilled} repaired={repaired} unchanged={unchanged} skipped={skipped}"
    )
    return {
        "fetched": len(rows), "matched": matched, "synced": synced,
        "hash_backfilled": hash_backfilled, "repaired": repaired,
        "unchanged": unchanged, "skipped": skipped, "skipped_reasons": skipped_reasons,
    }


def sync_kobo(
    dealer: str | None = None,
    report_date: date | None = None,
    *,
    wait_if_running: bool = True,
    timeout_seconds: int = 180,
) -> dict:
    """Thread-safe sync. Reports wait for an active sync instead of failing early."""
    acquired = _SYNC_LOCK.acquire(blocking=False)
    if not acquired:
        if not wait_if_running:
            return {
                "fetched": 0, "matched": 0, "synced": 0, "unchanged": 0, "skipped": 0,
                "waited_for_existing_sync": False, "skipped_reasons": ["sync already running"],
            }
        print("ℹ️ Kobo sync already running; waiting for it to finish...")
        finished = _SYNC_FINISHED.wait(timeout=max(1, int(timeout_seconds)))
        return {
            "fetched": 0, "matched": 0, "synced": 0, "unchanged": 0, "skipped": 0,
            "waited_for_existing_sync": True, "sync_finished": finished,
            "skipped_reasons": [] if finished else ["timed out waiting for active sync"],
        }

    _SYNC_FINISHED.clear()
    try:
        return _sync_kobo_unlocked(dealer=dealer, report_date=report_date)
    finally:
        _SYNC_FINISHED.set()
        _SYNC_LOCK.release()


if __name__ == "__main__":
    print(sync_kobo())
