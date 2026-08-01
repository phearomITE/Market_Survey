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
        if dealer or report_date:
            # Current Kobo form stores these questions inside outlet_info;
            # older/newer assets may expose them at the top level. Query both.
            # Dealer choice names are uppercase, so never lowercase the code.
            conditions: list[dict] = []
            if dealer:
                code = str(dealer).strip().upper()
                dealer_values = {"$in": [code, code.lower()]}
                conditions.append({"$or": [
                    {"outlet_info/dealer": dealer_values},
                    {"dealer": dealer_values},
                ]})
            if report_date:
                day = report_date.isoformat()
                conditions.append({"$or": [
                    {"outlet_info/report_date": day},
                    {"report_date": day},
                ]})
            query = conditions[0] if len(conditions) == 1 else {"$and": conditions}
            params = {"query": json.dumps(query, separators=(",", ":"))}
        rows: list[dict] = []
        started = monotonic()
        page_count = 0
        while url:
            if page_count >= 5 or monotonic() - started > 18:
                raise TimeoutError("Targeted Kobo fetch exceeded the 18-second report limit")
            data = self._get_json(url, timeout=10, params=params)
            rows.extend(data.get("results", []))
            url = data.get("next")
            params = None
            page_count += 1
        return rows
