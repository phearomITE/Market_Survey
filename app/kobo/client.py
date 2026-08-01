from __future__ import annotations

from datetime import date
import json
from threading import Lock
from time import monotonic

import requests
from app.core.config import settings


_DATE_CACHE: dict[tuple[str, str], tuple[float, list[dict]]] = {}
_DATE_CACHE_LOCK = Lock()


class KoboClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or settings.kobo_base_url).rstrip("/")
        self.token = token or settings.kobo_token
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"Authorization": f"Token {self.token}"})

    def _get_json(self, url: str, timeout: int = 15, params: dict | None = None) -> dict:
        resp = self.session.get(url, timeout=timeout, params=params)
        if resp.status_code in (401, 403):
            raise RuntimeError("Kobo authentication failed. Check KOBO_TOKEN in .env.")
        if resp.status_code == 404:
            raise RuntimeError("Kobo asset not found. Check KOBO_BASE_URL and KOBO_ASSET_UID.")
        resp.raise_for_status()
        return resp.json()

    def list_assets(self) -> list[dict]:
        url = f"{self.base_url}/api/v2/assets/"
        data = self._get_json(
            url,
            timeout=max(3, int(settings.kobo_request_timeout_seconds)),
        )
        return data.get("results", data if isinstance(data, list) else [])

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
        uid = asset_uid or settings.kobo_asset_uid
        if not uid:
            assets = self.list_assets()
            if len(assets) == 1:
                uid = assets[0].get("uid")
            else:
                raise RuntimeError("KOBO_ASSET_UID is missing. Set it in .env. Enketo URL is not enough for API sync.")

        url = f"{self.base_url}/api/v2/assets/{uid}/data.json"
        params = None
        cache_key: tuple[str, str] | None = None
        if report_date:
            # Kobo stores Dealer values with different letter case across form
            # versions. Filter by date on the server and Dealer locally.
            params = {
                "query": json.dumps(
                    {"outlet_info/report_date": report_date.isoformat()},
                    separators=(",", ":"),
                ),
                "limit": 500,
            }
            cache_key = (str(uid), report_date.isoformat())

        deadline_seconds = max(
            5,
            int(deadline_seconds or settings.kobo_fetch_deadline_seconds),
        )
        request_timeout = max(
            3,
            int(request_timeout or settings.kobo_request_timeout_seconds),
        )
        cache_ttl = max(0, int(settings.kobo_cache_ttl_seconds))

        # The lock provides single-flight behavior: summary/report/export calls
        # for the same date share one Kobo response instead of downloading the
        # same 1,650 rows concurrently.
        lock = _DATE_CACHE_LOCK if cache_key and use_cache else _NullLock()
        with lock:
            if cache_key and use_cache:
                cached = _DATE_CACHE.get(cache_key)
                if cached and monotonic() - cached[0] <= cache_ttl:
                    print(
                        f"⚡ Kobo date cache hit: date={report_date} "
                        f"rows={len(cached[1])}"
                    )
                    return list(cached[1])

            rows: list[dict] = []
            started = monotonic()
            pages = 0
            print(
                f"🔎 Kobo fast fetch: dealer-filter={dealer or 'ALL'} "
                f"date={report_date or 'ALL'}"
            )
            while url:
                elapsed = monotonic() - started
                remaining = deadline_seconds - elapsed
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

            if cache_key and use_cache:
                _DATE_CACHE[cache_key] = (monotonic(), list(rows))
            print(f"✅ Kobo fast fetch ready: rows={len(rows)} pages={pages}")
            return rows


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False
