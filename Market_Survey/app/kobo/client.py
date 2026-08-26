from __future__ import annotations

from datetime import date
import json
from threading import Lock
from time import monotonic

import requests

from app.core.config import settings


_DATE_CACHE: dict[tuple[str, str], tuple[float, list[dict]]] = {}
_DATE_CACHE_LOCK = Lock()
_DATE_FLIGHT_LOCKS: dict[tuple[str, str], Lock] = {}


def _flight_lock(cache_key: tuple[str, str]) -> Lock:
    """Single-flight one date without blocking different report dates."""
    with _DATE_CACHE_LOCK:
        return _DATE_FLIGHT_LOCKS.setdefault(cache_key, Lock())


class KoboClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or settings.kobo_base_url).rstrip("/")
        self.token = token or settings.kobo_token
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"Authorization": f"Token {self.token}"})

    def _get_json(
        self,
        url: str,
        timeout: int = 12,
        params: dict | None = None,
    ) -> dict:
        response = self.session.get(url, timeout=timeout, params=params)
        if response.status_code in (401, 403):
            raise RuntimeError("Kobo authentication failed. Check KOBO_TOKEN.")
        if response.status_code == 404:
            raise RuntimeError(
                "Kobo asset not found. Check KOBO_BASE_URL and KOBO_ASSET_UID."
            )
        response.raise_for_status()
        return response.json()

    def list_assets(self) -> list[dict]:
        url = f"{self.base_url}/api/v2/assets/"
        data = self._get_json(
            url, timeout=max(3, int(settings.kobo_request_timeout_seconds))
        )
        return data.get("results", data if isinstance(data, list) else [])

    def _asset_uid(self, asset_uid: str | None) -> str:
        uid = asset_uid or settings.kobo_asset_uid
        if uid:
            return uid
        assets = self.list_assets()
        if len(assets) == 1 and assets[0].get("uid"):
            return str(assets[0]["uid"])
        raise RuntimeError("KOBO_ASSET_UID is missing.")

    def _fetch_pages(
        self,
        uid: str,
        *,
        params: dict | None,
        deadline_seconds: int,
        request_timeout: int,
        page_limit: int,
    ) -> list[dict]:
        url = f"{self.base_url}/api/v2/assets/{uid}/data.json"
        rows: list[dict] = []
        started = monotonic()
        pages = 0
        while url:
            remaining = deadline_seconds - (monotonic() - started)
            if pages >= page_limit or remaining <= 0:
                raise TimeoutError(
                    f"Kobo fetch exceeded {deadline_seconds}s after "
                    f"{pages} pages and {len(rows)} rows"
                )
            data = self._get_json(
                url,
                timeout=max(1, min(request_timeout, int(remaining))),
                params=params,
            )
            rows.extend(data.get("results", []))
            url = data.get("next")
            params = None
            pages += 1
        print(f"✅ Kobo date fetch: rows={len(rows)} pages={pages}")
        return rows

    def fetch_submissions(
        self,
        asset_uid: str | None = None,
        *,
        dealer: str | None = None,
        report_date: date | None = None,
        deadline_seconds: int | None = None,
        request_timeout: int | None = None,
        page_limit: int = 20,
        use_cache: bool = True,
    ) -> list[dict]:
        uid = self._asset_uid(asset_uid)
        deadline = max(
            5, int(deadline_seconds or settings.kobo_fetch_deadline_seconds)
        )
        timeout = max(
            3, int(request_timeout or settings.kobo_request_timeout_seconds)
        )
        cache_key = (
            (str(uid), report_date.isoformat()) if report_date else None
        )
        lock = _flight_lock(cache_key) if cache_key and use_cache else _NullLock()
        with lock:
            if cache_key and use_cache:
                with _DATE_CACHE_LOCK:
                    cached = _DATE_CACHE.get(cache_key)
                if (
                    cached
                    and monotonic() - cached[0]
                    <= max(0, int(settings.kobo_cache_ttl_seconds))
                ):
                    print(
                        f"⚡ Kobo date cache hit: date={report_date} "
                        f"rows={len(cached[1])}"
                    )
                    return list(cached[1])

            if report_date:
                # Current XLSForm internal name. Kobo performs this query before
                # pagination, so a command reads one business date, not history.
                params = {
                    "query": json.dumps(
                        {"outlet_info/report_date": report_date.isoformat()},
                        separators=(",", ":"),
                    ),
                    "limit": 1000,
                }
                print(
                    f"🔎 Kobo date fetch: date={report_date} "
                    f"dealer-filter={dealer or 'ALL'}"
                )
                rows = self._fetch_pages(
                    uid,
                    params=params,
                    deadline_seconds=deadline,
                    request_timeout=timeout,
                    page_limit=page_limit,
                )
                # Some older deployed form versions stored the same field at
                # root level. Try that path only when the current path returns 0.
                if not rows:
                    fallback_params = {
                        "query": json.dumps(
                            {"report_date": report_date.isoformat()},
                            separators=(",", ":"),
                        ),
                        "limit": 1000,
                    }
                    rows = self._fetch_pages(
                        uid,
                        params=fallback_params,
                        deadline_seconds=deadline,
                        request_timeout=timeout,
                        page_limit=page_limit,
                    )
            else:
                rows = self._fetch_pages(
                    uid,
                    params={"limit": 1000},
                    deadline_seconds=deadline,
                    request_timeout=timeout,
                    page_limit=page_limit,
                )

            if cache_key and use_cache:
                with _DATE_CACHE_LOCK:
                    _DATE_CACHE[cache_key] = (monotonic(), list(rows))
            return rows


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False
