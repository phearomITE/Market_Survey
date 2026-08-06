from types import SimpleNamespace

from app.kobo.parser import normalize_submission
from app.services.report_service import (
    _filter_by_report_type,
    parse_report_command_args,
)


def test_report_command_supports_explicit_gt_and_horeca():
    assert parse_report_command_args(["CA3", "GT", "2026-07-18"]) == (
        "CA3",
        "2026-07-18",
        "GT",
    )
    assert parse_report_command_args(["CA3", "HORECA", "2026-07-18"]) == (
        "CA3",
        "2026-07-18",
        "HORECA",
    )


def test_new_form_report_type_is_normalized():
    row = {
        "_id": "1001",
        "_submission_time": "2026-07-25T10:00:00",
        "dealer": "ca3",
        "final_summary_report_type": "horeca",
    }
    assert normalize_submission(row)["report_type"] == "HORECA"


def test_explicit_report_type_wins_and_legacy_outlet_type_falls_back():
    rows = [
        SimpleNamespace(report_type="GT", outlet_type="Local Eat"),
        SimpleNamespace(report_type="HORECA", outlet_type="Drink Shop"),
        SimpleNamespace(report_type=None, outlet_type="Canteen"),
        SimpleNamespace(report_type=None, outlet_type="Wholesale"),
    ]
    assert _filter_by_report_type(rows, "GT") == [rows[0], rows[3]]
    assert _filter_by_report_type(rows, "HORECA") == [rows[1], rows[2]]
