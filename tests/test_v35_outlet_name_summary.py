from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime
from types import SimpleNamespace

from app.reports.aggregator import (
    OWN_PRODUCTS,
    COMPETITOR_PRODUCTS,
    _latest_manual_summary,
    aggregate_submissions,
    is_final_summary_outlet_name,
    competitor_field,
    product_field,
)
from app.reports.excel_report import (
    FRESHNESS_START_ROW,
    FRESHNESS_END_ROW,
    MOVEMENT_HEADER_ROW,
    MOVEMENT_START_ROW,
    MOVEMENT_END_ROW,
    RING_PULL_START_ROW,
    ISSUE_START_ROW,
)


def test_exact_report_rows():
    assert len(OWN_PRODUCTS) == 18
    assert OWN_PRODUCTS[0] == "CB LITE ORD"
    assert OWN_PRODUCTS[-1] == "CAMBODIA WATER 1500mL"
    assert "King Kong Ice" in COMPETITOR_PRODUCTS
    assert "Poweram" not in COMPETITOR_PRODUCTS
    assert (FRESHNESS_START_ROW, FRESHNESS_END_ROW) == (7, 24)
    assert (MOVEMENT_HEADER_ROW, MOVEMENT_START_ROW, MOVEMENT_END_ROW) == (26, 27, 42)
    assert (RING_PULL_START_ROW, ISSUE_START_ROW) == (45, 45)


def test_new_kobo_field_names():
    assert "fresh_movement_score_cb_lite_ord" in product_field("CB LITE ORD", "mov")
    assert "comp_stock_status_king_kong_ice" in competitor_field("King Kong Ice", "stock")
    # Cross-over product uses its own-product question in the competitor report block.
    assert "fresh_movement_score_cb_original_ncp" in competitor_field("CB Original NCP", "mov")


def _submission(idx, outlet_name, issue="", suggestion="", hour=8):
    return SimpleNamespace(
        id=idx, submission_id="", submission_time=datetime(2026, 7, 14, hour, 0),
        dealer="CA1", region="R1", report_date=datetime(2026, 7, 14).date(),
        group_no=2, member_no=4, location_text="Phnom Penh", outlet_name=outlet_name,
        outlet_type="Wholesale", total_outlet_visit_target=19,
        key_issue_text=issue, suggestion_text=suggestion,
        product_metrics=[], competitor_metrics=[], ring_pull_metrics=[],
    )


def test_latest_summary_selected_by_outlet_name_only():
    submissions = [
        _submission(1, "Outlet A", "Old outlet issue", "Old action", 8),
        _submission(2, "សរុបរួម", "1. Low stock\n2. Slow movement",
                    "1. Refill stock\n2. Visit outlet", 17),
    ]
    issues, suggestions = _latest_manual_summary(submissions)
    assert issues == ["Low stock", "Slow movement"]
    assert suggestions == ["Refill stock", "Visit outlet"]
    assert is_final_summary_outlet_name(" បូកសរុបរួម ")
    assert not is_final_summary_outlet_name("Outlet បូកសរុបរួម Shop")


def test_summary_control_row_is_not_counted_as_outlet():
    submissions = [
        _submission(1, "Outlet A", hour=8),
        _submission(2, "Outlet B", hour=9),
        _submission(3, "បូកសរុបរួម", "Issue summary", "Action summary", 17),
    ]
    result = aggregate_submissions(submissions)
    assert result["total_outlets"] == 2
    assert result["outlet_types"]["Wholesale"] == 2
    assert result["key_issues"][0] == "Issue summary"
    assert result["suggestions"][0] == "Action summary"


def test_normal_outlet_comments_are_not_used_for_final_report_summary():
    submissions = [
        _submission(1, "Je mey", "Normal outlet issue", "Normal outlet action", 8),
        _submission(2, "Outlet B", "Another regular issue", "Another regular action", 9),
        _submission(
            3,
            "បូកសរុបរួម",
            "1. Final issue one\n2. Final issue two",
            "1. Final action one\n2. Final action two",
            17,
        ),
    ]
    result = aggregate_submissions(submissions)
    assert result["total_outlets"] == 2
    assert result["key_issues"][:2] == ["Final issue one", "Final issue two"]
    assert result["suggestions"][:2] == ["Final action one", "Final action two"]
    assert "Normal outlet issue" not in result["key_issues"]
    assert "Normal outlet action" not in result["suggestions"]
