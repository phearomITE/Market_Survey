from __future__ import annotations

from threading import Event, Lock
import hashlib
import json
from datetime import date, datetime
from types import SimpleNamespace
from time import monotonic

from sqlalchemy import delete, select, update, func
from sqlalchemy.dialects.postgresql import insert

from app.db.database import SessionLocal, init_db
from app.db.models import (
    KoboCompetitorMetric,
    KoboProductMetric,
    KoboRingPullMetric,
    KoboSubmission,
    KoboReconciliationArchive,
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
from app.db.kobo_wide import upsert_wide_submission, upsert_wide_submissions_batch, ensure_wide_columns
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

    for model, values in (
        (KoboProductMetric, _product_metrics_from_flat(flat)),
        (KoboCompetitorMetric, _competitor_metrics_from_flat(flat)),
        (KoboRingPullMetric, _ring_pull_metrics_from_flat(flat)),
    ):
        payloads = [dict(submission_id=submission_db_id, **row) for row in values]
        if payloads:
            db.execute(insert(model), payloads)


def _save_sync_batch(db, items, wide_mapping):
    """Replace parent and metric rows in one atomic checkpoint batch."""
    # Last source occurrence wins if an API snapshot repeats an ID.
    items = list({data["submission_id"]: (data, flat) for data, flat in items}.values())
    if not items:
        return
    upsert_wide_submissions_batch(items, mapping=wide_mapping, connection=db.connection())
    statement = insert(KoboSubmission).values([data for data, _ in items])
    statement = statement.on_conflict_do_update(index_elements=["submission_id"],
        set_={key: getattr(statement.excluded, key) for key in items[0][0] if key != "submission_id"})
    ids = dict(db.execute(statement.returning(KoboSubmission.submission_id, KoboSubmission.id)).all())
    if len(ids) != len(items):
        raise RuntimeError("Batch upsert did not return every submission ID")
    for model, resolver in ((KoboProductMetric, _product_metrics_from_flat),
                            (KoboCompetitorMetric, _competitor_metrics_from_flat),
                            (KoboRingPullMetric, _ring_pull_metrics_from_flat)):
        db.execute(delete(model).where(model.submission_id.in_(list(ids.values()))))
        payloads = [dict(submission_id=ids[data["submission_id"]], **metric)
                    for data, flat in items for metric in resolver(flat)]
        if payloads:
            db.execute(insert(model), payloads)


NORMALIZED_PRODUCT_MAPPING_VERSION = "gt-summary-ord-greet-v1"


def _source_hash(raw: dict) -> str:
    payload = json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(
        (NORMALIZED_PRODUCT_MAPPING_VERSION + "\n" + payload).encode("utf-8")
    ).hexdigest()


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
            own_products = ["CBL Pint"] if report_type == "HORECA" else ["CB LITE ORD"]
            competitor_products = [
                "Tiger Crystal Pint",
                "HANUMAN LITE Pint",
                "Vathanac LITE Pint",
            ] if report_type == "HORECA" else [
                "GB SNOW ORD",
                "Hanuman LITE ORD",
                "Greet LITE ORD",
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


def _sync_kobo_unlocked(dealer: str | None = None, report_date: date | None = None, *, force: bool = False, full_history: bool = False) -> dict:
    """Fetch Kobo rows and upsert only new or changed submissions.

    When dealer/report_date are supplied, only matching rows are processed. This
    makes an on-demand /report sync fast even when the Kobo asset contains many rows.
    """
    if full_history and (dealer is not None or report_date is not None):
        raise ValueError("Full-history reconciliation cannot use date/dealer filters")
    init_db()
    rows = KoboClient().fetch_submissions(
        report_date=report_date,
        dealer=dealer,
        deadline_seconds=900 if full_history else settings.kobo_fetch_deadline_seconds,
        request_timeout=settings.kobo_request_timeout_seconds,
        page_limit=10000 if full_history else 20,
        use_cache=False,
    )
    if full_history and not rows:
        raise RuntimeError("Empty Kobo snapshot: reconciliation refused; existing records retained")
    synced = 0
    unchanged = 0
    hash_backfilled = 0
    skipped = 0
    matched = 0
    source_ids = set()
    source_dates = {}
    skipped_reasons: list[str] = []

    # Prepare dynamic field columns once per run, not once per submission.
    if full_history:
        print("BI sync: preparing form-field columns", flush=True)
    wide_mapping = ensure_wide_columns({key: None for raw in rows for key in flatten_dict(raw)})
    if full_history:
        print("BI sync: columns ready; importing all report dates", flush=True)
    with SessionLocal() as db:
        existing_rows = db.execute(select(KoboSubmission.submission_id,
            KoboSubmission.source_hash, KoboSubmission.report_date)).all()
        existing_hashes = {sid: digest for sid, digest, _ in existing_rows}
        existing_dates = {sid: value for sid, _, value in existing_rows}

        if full_history:
            db.add(SyncLog(source="kobo_bi_full", status="running",
                           message="Full sync started; saving changes in batches of 250.",
                           fetched=len(rows), synced=0, skipped=0))
            db.commit()

        pending = []
        for processed, raw in enumerate(rows, 1):
            if full_history and processed % 250 == 0:
                print(f"BI sync processing {processed}/{len(rows)}; changed={synced}; unchanged={unchanged}", flush=True)
            data = normalize_submission(raw)
            flat = data.pop("_flat", {}) or {}

            if dealer and (data.get("dealer") or "").upper() != dealer.upper():
                continue
            if report_date and data.get("report_date") != report_date:
                continue
            matched += 1
            if data.get("submission_id"):
                source_ids.add(data["submission_id"])
                source_dates[data["submission_id"]] = str(data.get("report_date") or "")

            missing = [k for k in ("submission_id",) if not data.get(k)]
            if missing:
                skipped += 1
                if len(skipped_reasons) < 5:
                    skipped_reasons.append(f"missing {','.join(missing)} from keys={list(raw.keys())[:12]}")
                continue

            source_hash = _source_hash(raw)
            data["source_hash"] = source_hash
            existing_hash = existing_hashes.get(data["submission_id"])
            if (not force and existing_hash == source_hash
                    and existing_dates.get(data["submission_id"]) == data.get("report_date")):
                unchanged += 1
                continue

            data["updated_at"] = datetime.utcnow()
            if full_history:
                pending.append((data, flat))
            else:
                upsert_wide_submission(flat, data, mapping=wide_mapping, connection=db.connection())
                stmt = insert(KoboSubmission).values(**data).on_conflict_do_update(
                    index_elements=["submission_id"],
                    set_={k: v for k, v in data.items() if k != "submission_id"})
                sub_id = db.scalar(stmt.returning(KoboSubmission.id))
                if sub_id is None:
                    raise RuntimeError("Submission upsert returned no ID")
                _replace_metric_rows(db, sub_id, flat)
            existing_hashes[data["submission_id"]] = source_hash
            existing_dates[data["submission_id"]] = data.get("report_date")
            synced += 1
            if full_history and synced % 250 == 0:
                print(f"BI sync: saving batch of {len(pending)} submissions", flush=True)
                _save_sync_batch(db, pending, wide_mapping)
                pending.clear()
                db.add(SyncLog(source="kobo_bi_full", status="running",
                               message=f"Committed {synced} changed submissions; {unchanged} unchanged.",
                               fetched=len(rows), synced=synced, skipped=skipped))
                db.commit()
                print(f"BI sync SAVED {synced} changed submissions; {unchanged} unchanged", flush=True)

        if pending:
            print(f"BI sync: saving final batch of {len(pending)} submissions", flush=True)
            _save_sync_batch(db, pending, wide_mapping)
        message = (
            f"fetched {len(rows)}, matched {matched}, synced {synced}, "
            f"hash_backfilled {hash_backfilled}, unchanged {unchanged}, skipped {skipped}"
        )
        if skipped_reasons:
            message += " | " + " || ".join(skipped_reasons[:5])
        db.flush()
        stored_ids = set(db.scalars(select(KoboSubmission.submission_id)))
        archived = 0
        stale_ids = stored_ids - source_ids
        # Reconcile only after every fetched record has been processed successfully.
        if full_history and not skipped and not (source_ids - stored_ids):
            for source_id in sorted(stale_ids):
                sub = db.scalar(select(KoboSubmission).where(KoboSubmission.submission_id == source_id))
                payload = {"submission": {c.name: getattr(sub, c.name) for c in sub.__table__.columns}}
                for model in (KoboProductMetric, KoboCompetitorMetric, KoboRingPullMetric):
                    children = db.scalars(select(model).where(model.submission_id == sub.id)).all()
                    payload[model.__tablename__] = [{c.name: getattr(child, c.name) for c in model.__table__.columns} for child in children]
                db.add(KoboReconciliationArchive(submission_id=source_id,
                    payload=json.dumps(payload, ensure_ascii=False, default=str)))
                for model in (KoboProductMetric, KoboCompetitorMetric, KoboRingPullMetric):
                    db.execute(delete(model).where(model.submission_id == sub.id))
                db.execute(delete(KoboSubmission).where(KoboSubmission.id == sub.id))
                archived += 1
            stored_ids -= stale_ids
        audit_archived = archived
        audit = {
            "archived_database_only_records": audit_archived,
            "database_rows": len(stored_ids),
            "source_distinct_ids": len(source_ids),
            "missing_source_ids": len(source_ids - stored_ids),
            "database_only_ids": len(stored_ids - source_ids) if full_history else None,
        }
        if full_history:
            expected_dates = {}
            for value in source_dates.values():
                expected_dates[value] = expected_dates.get(value, 0) + 1
            actual_dates = {str(d or ""): n for d, n in db.execute(
                select(KoboSubmission.report_date, func.count(KoboSubmission.id))
                .group_by(KoboSubmission.report_date))}
            audit["report_date_counts"] = {
                key: {"kobo": expected_dates.get(key, 0), "database": actual_dates.get(key, 0)}
                for key in sorted(set(expected_dates) | set(actual_dates))
            }
            audit["report_date_mismatches"] = sum(
                item["kobo"] != item["database"] for item in audit["report_date_counts"].values())
        message += " | " + json.dumps(audit)
        db.add(SyncLog(source="kobo_bi_full" if full_history else "kobo",
                      status="warning" if skipped or audit["missing_source_ids"] or audit.get("report_date_mismatches", 0) else "success",
                      message=message, fetched=len(rows), synced=synced, skipped=skipped))
        db.commit()

    print(
        f"✅ Kobo sync: fetched={len(rows)} matched={matched} synced={synced} "
        f"hash_backfilled={hash_backfilled} unchanged={unchanged} skipped={skipped}"
    )
    return {
        "fetched": len(rows), "matched": matched, "synced": synced,
        "hash_backfilled": hash_backfilled, "unchanged": unchanged,
        "skipped": skipped, "skipped_reasons": skipped_reasons, "audit": audit,
    }


def sync_kobo(
    dealer: str | None = None,
    report_date: date | None = None,
    *,
    wait_if_running: bool = True,
    timeout_seconds: int = 45,
    force: bool = False,
    full_history: bool = False,
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
        result = _sync_kobo_unlocked(dealer=dealer, report_date=report_date, force=force, full_history=full_history)
        clear_report_submission_cache()
        return result
    finally:
        _SYNC_FINISHED.set()
        _SYNC_LOCK.release()


if __name__ == "__main__":
    print(sync_kobo())
