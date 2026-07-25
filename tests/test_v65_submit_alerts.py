from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services.submission_alert_service import (
    current_manual_threshold,
    dealers_below_threshold,
    format_submission_alert,
)


def test_dealers_below_threshold_includes_zero_and_excludes_equal():
    counts = {"CA1": 8, "CA8": 10, "CA3": 0}
    result = dict(dealers_below_threshold(counts, 10))
    assert result["CA1"] == 8
    assert result["CA3"] == 0
    assert "CA8" not in result


def test_alert_text_matches_requested_format():
    from app.data.dealers import ALL_DEALERS
    counts = {dealer: 25 for dealer in ALL_DEALERS}
    counts["CA1"] = 8
    text = format_submission_alert(date(2026, 7, 25), 10, counts, "09:30 AM")
    assert "Dealer ដែល Submit Report តិចជាង 10" in text
    assert "1. CA1 = 8 Report" in text
    assert "25/07/2026" in text


def test_manual_threshold_changes_at_second_schedule(monkeypatch):
    from app.services import submission_alert_service as service

    monkeypatch.setattr(service.settings, "submit_alert_first_threshold", 10)
    monkeypatch.setattr(service.settings, "submit_alert_second_threshold", 20)
    monkeypatch.setattr(service.settings, "submit_alert_second_time", "10:30")
    tz = ZoneInfo("Asia/Phnom_Penh")
    assert current_manual_threshold(datetime(2026, 7, 25, 10, 29, tzinfo=tz)) == 10
    assert current_manual_threshold(datetime(2026, 7, 25, 10, 30, tzinfo=tz)) == 20
