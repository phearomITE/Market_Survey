"""Backfill Province/District/Commune from existing Kobo GPS pins.

Run repeatedly in a Railway shell until it reports zero updated rows:
    python -m scripts.backfill_map_locations --limit 250
"""
from __future__ import annotations

import argparse

from sqlalchemy import or_, select

from app.db.database import SessionLocal, init_db
from app.db.models import KoboSubmission
from app.web.geocode import enrich_admin_location


def backfill(limit: int) -> tuple[int, int]:
    init_db()
    updated = failed = 0
    with SessionLocal() as db:
        rows = db.scalars(
            select(KoboSubmission)
            .where(
                KoboSubmission.gps_latitude.is_not(None),
                KoboSubmission.gps_longitude.is_not(None),
                or_(
                    KoboSubmission.province.is_(None),
                    KoboSubmission.district.is_(None),
                    KoboSubmission.commune.is_(None),
                ),
            )
            .order_by(KoboSubmission.id.desc())
            .limit(max(1, limit))
        ).all()
        for row in rows:
            values = {
                "gps_latitude": row.gps_latitude,
                "gps_longitude": row.gps_longitude,
                "province": row.province,
                "district": row.district,
                "commune": row.commune,
                "village": row.village,
            }
            enrich_admin_location(values)
            if not values.get("province"):
                failed += 1
                continue
            row.province = values.get("province")
            row.district = values.get("district")
            row.commune = values.get("commune")
            row.village = values.get("village")
            updated += 1
            if updated % 25 == 0:
                db.commit()
        db.commit()
    return updated, failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=250)
    args = parser.parse_args()
    updated, failed = backfill(args.limit)
    print(f"Map location backfill complete: updated={updated}, unresolved={failed}")
