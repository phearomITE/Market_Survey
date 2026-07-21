from datetime import datetime
from types import SimpleNamespace

from app.reports.aggregator import _latest_manual_summary, normalize_summary_report_type
from app.services.report_service import _filter_by_report_type


def _row(**kwargs):
    defaults = {
        "outlet_name": "Outlet",
        "outlet_type": "Drink Shop",
        "summary_report_type": None,
        "key_issue_text": None,
        "suggestion_text": None,
        "submission_time": datetime(2026, 7, 18, 8, 0, 0),
        "id": 1,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_blank_selector_routes_to_general_only():
    general_summary = _row(
        outlet_name="បូកសរុបរួម",
        outlet_type=None,
        summary_report_type=None,
        key_issue_text="General issue",
        suggestion_text="General action",
    )
    channel_summary = _row(
        outlet_name="បូកសរុបរួម",
        outlet_type=None,
        summary_report_type="channel_specialist",
        key_issue_text="Channel issue",
        suggestion_text="Channel action",
        submission_time=datetime(2026, 7, 18, 9, 0, 0),
        id=2,
    )

    rows = [general_summary, channel_summary]
    assert _latest_manual_summary(rows, "GENERAL", {}) == (
        ["General issue"], ["General action"]
    )
    assert _latest_manual_summary(rows, "CHANNEL_SPECIALIST", {}) == (
        ["Channel issue"], ["Channel action"]
    )


def test_filter_keeps_matching_summary_control_row():
    general_outlet = _row(outlet_name="GT Outlet", outlet_type="Drink Shop")
    channel_outlet = _row(outlet_name="CS Outlet", outlet_type="Local Eat")
    general_summary = _row(outlet_name="បូកសរុបរួម", outlet_type=None)
    channel_summary = _row(
        outlet_name="បូកសរុបរួម",
        outlet_type=None,
        summary_report_type="CHANNEL_SPECIALIST",
    )
    rows = [general_outlet, channel_outlet, general_summary, channel_summary]

    general = _filter_by_report_type(rows, "GENERAL")
    channel = _filter_by_report_type(rows, "CHANNEL_SPECIALIST")

    assert general_outlet in general
    assert general_summary in general
    assert channel_outlet not in general
    assert channel_summary not in general

    assert channel_outlet in channel
    assert channel_summary in channel
    assert general_outlet not in channel
    assert general_summary not in channel


def test_summary_type_normalization():
    assert normalize_summary_report_type(None) == "GENERAL"
    assert normalize_summary_report_type("") == "GENERAL"
    assert normalize_summary_report_type("channel_specialist") == "CHANNEL_SPECIALIST"
    assert normalize_summary_report_type("CHANNEL SPECIALIST") == "CHANNEL_SPECIALIST"
