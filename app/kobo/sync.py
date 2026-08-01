from __future__ import annotations

from threading import Event, Lock
import hashlib
import json
from datetime import date
from types import SimpleNamespace
from time import monotonic

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
from app.kobo.parser import (
    ALIASES,
    FlatFieldMap,
    flatten_dict,
    normalize_dealer,
    normalize_submission,
    to_float,
    to_int,
    yes_value,
)
from app.db.kobo_wide import upsert_wide_submission
from app.core.config import settings
_SYNC_LOCK = Lock()
_SYNC_FINISHED = Event()
_SYNC_FINISHED.set()

from app.reports.aggregator import (
    ALL_COMPETITOR_PRODUCTS,
    ALL_OWN_PRODUCTS,
    COMPETITOR_PRODUCTS,
    HORECA_COMPETITOR_PRODUCTS,
    HORECA_OWN_PRODUCTS,
    OWN_PRODUCTS,
    RING_PRODUCTS,
    STATUS_AVAILABLE,
    competitor_field,
    first_value,
    product_field,
)


_REPORT_CACHE: dict[tuple[str, str, str], tuple[float, list]] = {}
_REPORT_CACHE_LOCK = Lock()
_REPORT_FLIGHT_LOCKS: dict[tuple[str, str, str], Lock] = {}


def _report_flight_lock(cache_key: tuple[str, str, str]) -> Lock:
    with _REPORT_CACHE_LOCK:
        return _REPORT_FLIGHT_LOCKS.setdefault(cache_key, Lock())


def clear_report_submission_cache() -> None:
    """Invalidate normalized rows after a manual database/Kobo sync."""
    with _REPORT_CACHE_LOCK:
        _REPORT_CACHE.clear()


def _cached_report_rows(cache_key: tuple[str, str, str]) -> list | None:
    with _REPORT_CACHE_LOCK:
        cached = _REPORT_CACHE.get(cache_key)
    if not cached:
        return None
    if monotonic() - cached[0] > max(
        0, int(settings.kobo_normalized_cache_ttl_seconds)
    ):
        with _REPORT_CACHE_LOCK:
            _REPORT_CACHE.pop(cache_key, None)
        return None
    return list(cached[1])


def _store_report_rows(cache_key: tuple[str, str, str], rows: list) -> None:
    with _REPORT_CACHE_LOCK:
        _REPORT_CACHE[cache_key] = (monotonic(), list(rows))


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


def _product_metrics_from_flat(
    flat: dict,
    products: list[str] | tuple[str, ...] | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for product in products or ALL_OWN_PRODUCTS:
        status = first_value(flat, product_field(product, "status"))
        score = first_value(flat, product_field(product, "mov"))
        stock_status = first_value(flat, product_field(product, "stock"))
        bbe_date = first_value(flat, product_field(product, "bbe"))
        buy_in_price = first_value(flat, product_field(product, "buy_in"))
        sell_out_price = first_value(flat, product_field(product, "sell_out"))
        ring_pull_value = first_value(flat, product_field(product, "ring_pull"))
        new_outlet_purchase = first_value(
            flat, product_field(product, "new_purchase")
        )
        volume_ctn = first_value(flat, product_field(product, "volume"))
        movement = to_int(score)
        if movement is None:
            movement = _status_to_mov(status)
        available = False
        if status not in (None, ""):
            available = str(status).strip().lower() in STATUS_AVAILABLE or str(status).strip() in STATUS_AVAILABLE
        else:
            available = any(
                value not in (None, "")
                for value in (
                    score,
                    stock_status,
                    bbe_date,
                    buy_in_price,
                    sell_out_price,
                    ring_pull_value,
                    new_outlet_purchase,
                    volume_ctn,
                )
            )

        values = {
            "product_name": product,
            "status": str(status).strip() if status not in (None, "") else None,
            "available": bool(available),
            "movement_score": movement,
            "stock_status": stock_status,
            "bbe_date": bbe_date,
            "buy_in_price": to_float(buy_in_price),
            "sell_out_price": to_float(sell_out_price),
            "ring_pull_value": to_float(ring_pull_value),
            "new_outlet_purchase": yes_value(new_outlet_purchase),
            "volume_ctn": to_float(volume_ctn),
        }

        # Store every product row so reporting has fixed rows, even if blank.
        rows.append(values)
    return rows


def _competitor_metrics_from_flat(
    flat: dict,
    products: list[str] | tuple[str, ...] | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for product in products or ALL_COMPETITOR_PRODUCTS:
        status = first_value(flat, competitor_field(product, "status"))
        score = first_value(flat, competitor_field(product, "mov"))
        stock_status = first_value(flat, competitor_field(product, "stock"))
        buy_in_price = first_value(flat, competitor_field(product, "buy_in"))
        sell_out_price = first_value(flat, competitor_field(product, "sell_out"))
        movement = to_int(score)
        if movement is None:
            movement = _status_to_mov(status)
        rows.append(
            {
                "product_name": product,
                "status": str(status).strip() if status not in (None, "") else None,
                "movement_score": movement,
                "stock_status": stock_status,
                "buy_in_price": to_float(buy_in_price),
                "sell_out_price": to_float(sell_out_price),
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


def fetch_report_submissions_fast(
    dealer: str | None,
    report_date: date,
    *,
    dealers: set[str] | None = None,
    summary_only: bool = False,
    metadata_only: bool = False,
) -> list[KoboSubmission]:
    """Normalize one date directly from Kobo without PostgreSQL writes.

    Rows are indexed once, report/dealer filtered before product parsing and
    cached by date+mode.  This is shared by every export command, so a second
    command for the same date avoids repeating 1,600 product parses.
    """
    mode = "metadata" if metadata_only else "summary" if summary_only else "full"
    wanted = {
        str(value).strip().upper()
        for value in (dealers or set())
        if str(value).strip()
    }
    if dealer:
        wanted.add(str(dealer).strip().upper())
    scope = ",".join(sorted(wanted)) if wanted else "ALL"
    cache_key = (report_date.isoformat(), mode, scope)

    # A full-date cache is a safe superset for all other modes/scopes.
    full_all_key = (report_date.isoformat(), "full", "ALL")
    full_rows = _cached_report_rows(full_all_key)
    if full_rows is not None:
        selected = [
            row for row in full_rows
            if not wanted or str(getattr(row, "dealer", "")).upper() in wanted
        ]
        print(
            f"⚡ Normalized Kobo cache hit: date={report_date} "
            f"mode=full scope={scope} rows={len(selected)}"
        )
        return selected

    cached = _cached_report_rows(cache_key)
    if cached is not None:
        print(
            f"⚡ Normalized Kobo cache hit: date={report_date} "
            f"mode={mode} scope={scope} rows={len(cached)}"
        )
        return cached

    with _report_flight_lock(cache_key):
        cached = _cached_report_rows(cache_key)
        if cached is not None:
            return cached

        submissions = _build_report_submissions(
            dealer=dealer,
            report_date=report_date,
            wanted=wanted,
            summary_only=summary_only,
            metadata_only=metadata_only,
        )
        _store_report_rows(cache_key, submissions)
        return list(submissions)


def _build_report_submissions(
    *,
    dealer: str | None,
    report_date: date,
    wanted: set[str],
    summary_only: bool,
    metadata_only: bool,
) -> list[KoboSubmission]:
    rows = KoboClient().fetch_submissions(
        report_date=report_date,
        dealer=dealer,
        deadline_seconds=settings.kobo_fetch_deadline_seconds,
        request_timeout=settings.kobo_request_timeout_seconds,
    )
    submissions: list[KoboSubmission] = []
    for raw in rows:
        flat: FlatFieldMap = flatten_dict(raw)
        # Dealer commands should parse product fields only for the requested
        # dealer, not for all 1,600 submissions returned for the date.
        if wanted:
            raw_dealer = normalize_dealer(
                flat.parser_value(ALIASES["dealer"], "")
            )
            if raw_dealer not in wanted:
                continue

        data = normalize_submission(raw, flat=flat)
        flat = data.pop("_flat", {}) or {}
        normalized_dealer = str(data.get("dealer") or "").strip().upper()
        if wanted and normalized_dealer not in wanted:
            continue
        if data.get("report_date") != report_date or not data.get("submission_id"):
            continue

        submission = SimpleNamespace(**data)
        if metadata_only:
            submission.product_metrics = []
            submission.competitor_metrics = []
            submission.ring_pull_metrics = []
            submissions.append(submission)
            continue

        report_type = str(data.get("report_type") or "GT").strip().upper()
        if summary_only:
            own_products = ["CBL Pint"] if report_type == "HORECA" else ["CB LITE NCP"]
            competitor_products = [
                "Tiger Crystal Pint",
                "HANUMAN LITE Pint",
                "Vathanac LITE Pint",
            ] if report_type == "HORECA" else [
                "GB SNOW NCP",
                "Hanuman LITE NCP",
                "Greet LITE NCP",
            ]
        elif report_type == "HORECA":
            own_products = HORECA_OWN_PRODUCTS
            competitor_products = HORECA_COMPETITOR_PRODUCTS
        else:
            own_products = OWN_PRODUCTS
            competitor_products = COMPETITOR_PRODUCTS

        product_rows = _product_metrics_from_flat(flat, own_products)
        competitor_rows = _competitor_metrics_from_flat(
            flat, competitor_products
        )

        submission.product_metrics = [
            SimpleNamespace(**item) for item in product_rows
        ]
        submission.competitor_metrics = [
            SimpleNamespace(**item) for item in competitor_rows
        ]
        submission.ring_pull_metrics = (
            []
            if summary_only or report_type == "HORECA"
            else [
                SimpleNamespace(**item)
                for item in _ring_pull_metrics_from_flat(flat)
            ]
        )
        submissions.append(submission)

    print(
        f"✅ Fast Kobo rows: date={report_date} "
        f"dealer={dealer or 'ALL'} rows={len(submissions)}"
    )
    return submissions


def _sync_kobo_unlocked(dealer: str | None = None, report_date: date | None = None) -> dict:
    """Fetch Kobo rows and upsert only new or changed submissions.

    When dealer/report_date are supplied, only matching rows are processed. This
    makes an on-demand /report sync fast even when the Kobo asset contains many rows.
    """
    init_db()
    rows = KoboClient().fetch_submissions(
        report_date=report_date,
        dealer=dealer,
        deadline_seconds=settings.kobo_fetch_deadline_seconds,
        request_timeout=settings.kobo_request_timeout_seconds,
        use_cache=False,
    )
    synced = 0
    unchanged = 0
    hash_backfilled = 0
    skipped = 0
    matched = 0
    skipped_reasons: list[str] = []

    with SessionLocal() as db:
        existing_hashes = dict(db.execute(select(KoboSubmission.submission_id, KoboSubmission.source_hash)).all())

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
            existing_hash = existing_hashes.get(data["submission_id"])
            if existing_hash == source_hash:
                unchanged += 1
                continue

            # V37 first-run optimization: old DB rows have no source_hash yet.
            # Backfill their hash without deleting/recreating 57 child metric rows.
            # New rows are still imported fully, and future Kobo edits are detected.
            if data["submission_id"] in existing_hashes and existing_hash in (None, ""):
                db.execute(
                    update(KoboSubmission)
                    .where(KoboSubmission.submission_id == data["submission_id"])
                    .values(source_hash=source_hash, report_type=data.get("report_type"))
                )
                existing_hashes[data["submission_id"]] = source_hash
                hash_backfilled += 1
                continue

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
            existing_hashes[data["submission_id"]] = source_hash
            synced += 1

        message = (
            f"fetched {len(rows)}, matched {matched}, synced {synced}, "
            f"hash_backfilled {hash_backfilled}, unchanged {unchanged}, skipped {skipped}"
        )
        if skipped_reasons:
            message += " | " + " || ".join(skipped_reasons[:5])
        db.add(SyncLog(status="success", message=message, fetched=len(rows), synced=synced, skipped=skipped))
        db.commit()

    print(
        f"✅ Kobo sync: fetched={len(rows)} matched={matched} synced={synced} "
        f"hash_backfilled={hash_backfilled} unchanged={unchanged} skipped={skipped}"
    )
    return {
        "fetched": len(rows), "matched": matched, "synced": synced,
        "hash_backfilled": hash_backfilled, "unchanged": unchanged,
        "skipped": skipped, "skipped_reasons": skipped_reasons,
    }


def sync_kobo(
    dealer: str | None = None,
    report_date: date | None = None,
    *,
    wait_if_running: bool = True,
    timeout_seconds: int = 45,
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
        result = _sync_kobo_unlocked(dealer=dealer, report_date=report_date)
        clear_report_submission_cache()
        return result
    finally:
        _SYNC_FINISHED.set()
        _SYNC_LOCK.release()


if __name__ == "__main__":
    print(sync_kobo())
