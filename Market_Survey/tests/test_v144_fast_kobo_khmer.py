from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json

from openpyxl import Workbook

from app.kobo.client import KoboClient, _DATE_CACHE
from app.kobo.parser import normalize_submission
from app.reports.excel_report import (
    SUMMARY_FONT_NAME,
    _normalize_khmer_cells,
)


def test_kobo_fetch_filters_one_date_and_reuses_cache(monkeypatch):
    _DATE_CACHE.clear()
    calls = []

    def fake_get(url, timeout, params=None):
        calls.append((url, params))
        return {
            "results": [
                {
                    "_id": 1,
                    "outlet_info": {
                        "report_date": "2026-08-01",
                        "dealer": "CA7",
                    },
                }
            ],
            "next": None,
        }

    client = KoboClient(base_url="https://example.test", token="token")
    monkeypatch.setattr(client, "_get_json", fake_get)
    first = client.fetch_submissions(
        asset_uid="asset", report_date=date(2026, 8, 1)
    )
    second = client.fetch_submissions(
        asset_uid="asset", report_date=date(2026, 8, 1)
    )
    assert first == second
    assert len(calls) == 1
    query = json.loads(calls[0][1]["query"])
    assert query == {"outlet_info/report_date": "2026-08-01"}
    assert calls[0][1]["limit"] == 1000


def test_current_grouped_gt_and_horeca_fields_parse():
    for raw_value, expected in (("gt", "GT"), ("horeca", "HORECA")):
        normalized = normalize_submission(
            {
                "_id": raw_value,
                "outlet_info": {
                    "report_date": "2026-08-01",
                    "region": "r7",
                    "dealer": "mdk2",
                    "final_summary_report_type": raw_value,
                },
            }
        )
        assert normalized["dealer"] == "MDK2"
        assert normalized["region"] == "R7"
        assert normalized["report_type"] == expected


def test_khmer_hidden_separator_removed_and_noto_font_applied():
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "គ្\u200bរប់"
    _normalize_khmer_cells(sheet)
    assert sheet["A1"].value == "គ្រប់"
    assert sheet["A1"].font.name == SUMMARY_FONT_NAME


def test_render_uses_private_headless_profile():
    source = Path("app/services/render_service.py").read_text(encoding="utf-8")
    assert "SAL_USE_VCLPLUGIN" in source
    assert "UserInstallation" in source
    assert 'environment.pop("DISPLAY", None)' in source


def test_full_history_auto_sync_is_not_started():
    source = Path("app/bot/run_bot.py").read_text(encoding="utf-8")
    post_init = source.split("async def _post_init", 1)[1].split(
        "async def _post_shutdown", 1
    )[0]
    assert "create_task" not in post_init
