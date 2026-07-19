from datetime import date
from types import SimpleNamespace

from app.kobo.parser import normalize_submission, normalize_dealer
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


def test_historical_kd1_choice_normalizes_to_kdl1():
    assert normalize_dealer("kd1") == "KDL1"
    raw = {
        "_id": 2001,
        "_submission_time": "2026-07-18T08:00:00",
        "outlet_info": {
            "region": "r2",
            "dealer": "kd1",
            "report_date": "2026-07-18",
            "outlet_name": "Outlet A",
        },
    }
    assert normalize_submission(raw)["dealer"] == "KDL1"


def test_summary_template_field_parses():
    raw = {
        "_id": 2002,
        "_submission_time": "2026-07-18T17:00:00",
        "outlet_info": {
            "region": "r2",
            "dealer": "kdl1",
            "report_date": "2026-07-18",
            "outlet_name": "បូកសរុបរួម",
        },
        "key_issues_suggestion_group": {
            "final_summary_report_type": "channel_specialist",
        },
    }
    data = normalize_submission(raw)
    assert data["dealer"] == "KDL1"
    assert data["summary_report_type"] == "CHANNEL_SPECIALIST"


def test_report_type_filter_routes_summary_marker_by_selector():
    rows = [
        SimpleNamespace(outlet_name="Outlet A", outlet_type="Wholesale", summary_report_type=None),
        SimpleNamespace(outlet_name="Outlet B", outlet_type="Local Eat", summary_report_type=None),
        SimpleNamespace(outlet_name="បូកសរុបរួម", outlet_type=None, summary_report_type=None),
        SimpleNamespace(
            outlet_name="បូកសរុបរួម",
            outlet_type=None,
            summary_report_type="CHANNEL_SPECIALIST",
        ),
    ]
    general = _filter_by_report_type(rows, "GENERAL")
    channel = _filter_by_report_type(rows, "CHANNEL_SPECIALIST")
    assert len(general) == 2
    assert len(channel) == 2
    assert any(getattr(row, "summary_report_type", None) is None and row.outlet_name == "បូកសរុបរួម" for row in general)
    assert any(getattr(row, "summary_report_type", None) == "CHANNEL_SPECIALIST" for row in channel)
