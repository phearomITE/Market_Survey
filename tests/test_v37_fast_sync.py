from datetime import date
from types import SimpleNamespace

from app.kobo.parser import normalize_submission
from app.services.report_service import _filter_by_report_type
from app.kobo.sync import _source_hash


def test_cph2_new_form_fields_parse():
    raw = {
        "_id": 1001,
        "_submission_time": "2026-07-14T08:00:00",
        "outlet_info": {
            "region": "r2", "dealer": "cph2", "report_date": "2026-07-14",
            "outlet_name": "Je Mom", "outlet_type": "wholesale",
        },
    }
    data = normalize_submission(raw)
    assert data["dealer"] == "CPH2"
    assert data["report_date"] == date(2026, 7, 14)
    assert data["outlet_type"] == "Wholesale"


def test_general_report_includes_blank_and_wholesale_types():
    rows = [SimpleNamespace(outlet_type=None), SimpleNamespace(outlet_type="Wholesale")]
    assert len(_filter_by_report_type(rows, "GENERAL")) == 2


def test_source_hash_stable_and_detects_change():
    a = {"_id": 1, "dealer": "CPH2", "value": 5}
    b = {"value": 5, "dealer": "CPH2", "_id": 1}
    c = {"_id": 1, "dealer": "CPH2", "value": 6}
    assert _source_hash(a) == _source_hash(b)
    assert _source_hash(a) != _source_hash(c)
