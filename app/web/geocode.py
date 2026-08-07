from __future__ import annotations

import json
from functools import lru_cache
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings


def _clean(value) -> str | None:
    text = str(value or "").strip()
    return text or None


@lru_cache(maxsize=4096)
def _reverse_cached(latitude: float, longitude: float) -> tuple[str | None, ...]:
    """Resolve a Kobo GPS pin without adding work to map page requests."""
    params = urlencode(
        {
            "latitude": f"{latitude:.6f}",
            "longitude": f"{longitude:.6f}",
            "localityLanguage": "en",
        }
    )
    request = Request(
        f"{settings.reverse_geocoding_url}?{params}",
        headers={"Accept": "application/json"},
    )
    with urlopen(request, timeout=settings.reverse_geocoding_timeout_seconds) as response:
        payload = json.load(response)

    province = _clean(payload.get("principalSubdivision"))
    district = _clean(payload.get("locality") or payload.get("city"))
    informative = payload.get("localityInfo", {}).get("informative", []) or []
    commune = _clean(informative[0].get("name")) if informative else None
    village = _clean(informative[-1].get("name")) if informative else None

    # The provider may expose better administrative levels in this ordered list.
    administrative = payload.get("localityInfo", {}).get("administrative", []) or []
    names = [_clean(item.get("name")) for item in administrative]
    names = [name for name in names if name and name.lower() != "cambodia"]
    if names:
        province = province or names[0]
        district = district or (names[1] if len(names) > 1 else None)
        commune = commune or (names[2] if len(names) > 2 else None)
        village = village or (names[3] if len(names) > 3 else None)
    return province, district, commune, village


def enrich_admin_location(data: dict) -> dict:
    """Fill missing administrative fields from a submitted GPS pin.

    Failures are intentionally non-fatal: Kobo synchronization and reports must
    continue when the external geocoder is temporarily unavailable.
    """
    if not settings.reverse_geocoding_enabled:
        return data
    if data.get("province") and data.get("district") and data.get("commune"):
        return data
    latitude, longitude = data.get("gps_latitude"), data.get("gps_longitude")
    if latitude is None or longitude is None:
        return data
    try:
        province, district, commune, village = _reverse_cached(
            round(float(latitude), 5), round(float(longitude), 5)
        )
        for key, value in zip(
            ("province", "district", "commune", "village"),
            (province, district, commune, village),
        ):
            if not data.get(key) and value:
                data[key] = value
    except Exception as exc:
        print(f"⚠️ GPS administrative lookup skipped: {exc}")
    return data
