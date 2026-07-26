from datetime import date

from app.data.dealers import ALL_DEALERS
from app.services.submission_alert_service import (
    dealers_below_threshold,
    format_submission_alert,
)


def _counts():
    counts = {dealer: 25 for dealer in ALL_DEALERS}
    counts.update({"CA1": 8, "CA5": 5, "PTM6": 16, "KKG3": 14})
    return counts


def test_manual_threshold_10():
    assert dealers_below_threshold(_counts(), 10) == [("CA1", 8), ("CA5", 5)]


def test_manual_threshold_20():
    assert dealers_below_threshold(_counts(), 20)[:4] == [
        ("PTM6", 16),
        ("KKG3", 14),
        ("CA1", 8),
        ("CA5", 5),
    ]


def test_alert_text():
    text = format_submission_alert(date(2026, 7, 25), 10, _counts())
    assert "Dealer ដែល Submit Report តិចជាង 10" in text
    assert "1. CA1 = 8 Report" in text
    assert "2. CA5 = 5 Report" in text
