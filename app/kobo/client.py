from __future__ import annotations

from datetime import date
import json
from time import monotonic

import requests
from app.core.config import settings


class KoboClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or settings.kobo_base_url).rstrip("/")
        self.token = token or settings.kobo_token
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"Authorization": f"Token {self.token}"})

    def _get_json(self, url: str, timeout: int = 120, params: dict | None = None) -> dict:
        resp = self.session.get(url, timeout=timeout, params=params)
        if resp.status_code in (401, 403):
            raise RuntimeError("Kobo authentication failed. Check KOBO_TOKEN in .env.")
        if resp.status_code == 404:
            raise RuntimeError("Kobo asset not found. Check KOBO_BASE_URL and KOBO_ASSET_UID.")
        resp.raise_for_status()
        return resp.json()

    def list_assets(self) -> list[dict]:
        url = f"{self.base_url}/api/v2/assets/"
        data = self._get_json(url, timeout=60)
        return data.get("results", data if isinstance(data, list) else [])

    def fetch_submissions(
        self,
        asset_uid: str | None = None,
        *,
        dealer: str | None = None,
        report_date: date | None = None,
        deadline_seconds: int | None = None,
        request_timeout: int | None = None,
        page_limit: int | None = None,
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
        if report_date:
            # Filter by date on Kobo, then filter Dealer after normalization.
            # Dealer choice values vary between old/new form versions (for
            # example CA7 vs ca7), so server-side dealer matching can return 0
            # even when Kobo visibly contains that dealer.
            query = {"outlet_info/report_date": report_date.isoformat()}
            params = {
                "query": json.dumps(query, separators=(",", ":")),
                "limit": 500,
            }

        if deadline_seconds is None:
            deadline_seconds = 120
        if request_timeout is None:
            request_timeout = 60
        if page_limit is None:
            page_limit = 20

        rows: list[dict] = []
        started = monotonic()
        page_count = 0
        print(
            f"🔎 Kobo date fetch starting: dealer-filter={dealer or 'ALL'} "
            f"date={report_date or 'ALL'}"
        )
        while url:
            if page_count >= page_limit or monotonic() - started > deadline_seconds:
                raise TimeoutError(
                    f"Kobo fetch exceeded {deadline_seconds} seconds after "
                    f"{page_count} pages and {len(rows)} rows"
                )
            data = self._get_json(url, timeout=request_timeout, params=params)
            rows.extend(data.get("results", []))
            url = data.get("next")
            params = None
            page_count += 1
        print(f"✅ Kobo date fetch finished: rows={len(rows)} pages={page_count}")
        return rows

