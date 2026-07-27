from __future__ import annotations
import time
import requests
from sqlalchemy import select
from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import KoboSubmission

def _pick(a: dict, *names: str) -> str:
    for name in names:
        if a.get(name):
            return str(a[name]).strip()
    return ""

def enrich_missing_administrative_locations() -> int:
    """Cache a throttled batch of GPS reverse-geocoding results."""
    if not settings.reverse_geocoding_enabled:
        return 0
    with SessionLocal() as db:
        rows = db.execute(
            select(KoboSubmission).where(
                KoboSubmission.gps_latitude.is_not(None),
                KoboSubmission.gps_longitude.is_not(None),
                KoboSubmission.province.is_(None),
            ).limit(max(1, min(settings.reverse_geocoding_batch_size, 100)))
        ).scalars().all()
        done = 0
        app_url = settings.public_url or "https://marketsurvey-production.up.railway.app"
        user_agent = f"KBMarketSurvey/1.0 (+{app_url})"
        for row in rows:
            try:
                response = requests.get(
                    settings.reverse_geocoding_url,
                    params={"lat": row.gps_latitude, "lon": row.gps_longitude, "format": "jsonv2", "addressdetails": 1, "accept-language": "en"},
                    headers={"User-Agent": user_agent},
                    timeout=12,
                )
                response.raise_for_status()
                address = response.json().get("address") or {}
                row.province = _pick(address, "state", "province", "city")
                row.district = _pick(address, "county", "city_district", "district")
                row.commune = _pick(address, "municipality", "town", "suburb", "quarter")
                row.village = _pick(address, "village", "hamlet", "neighbourhood")
                done += 1
                db.commit()
            except Exception as exc:
                db.rollback()
                print(f"⚠️ Reverse geocoding skipped submission {row.id}: {exc}")
            time.sleep(1.05)
        return done
