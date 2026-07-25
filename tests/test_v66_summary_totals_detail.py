from datetime import date
from types import SimpleNamespace

from app.reports.summary_report import (
    build_detail_rows,
    build_summary_rows,
    movement_summary_from_aggregate,
)


def _aggregate(cb_movement: int, leader: str = "GB SNOW NCP") -> dict:
    competitors = {
        "GB SNOW NCP": {"mov": 8},
        "Hanuman LITE NCP": {"mov": 7},
        "Krud LITE NCP": {"mov": 6},
        "Greet LITE NCP": {"mov": 5},
    }
    competitors[leader]["mov"] = 10
    return {
        "products": {"CB LITE NCP": {"mov": cb_movement}},
        "competitors": competitors,
    }


def test_movement_summary_uses_final_report_values():
    result = movement_summary_from_aggregate(_aggregate(3))
    assert result["movement_lt5"] == 3
    assert result["movement_5_8"] is None
    assert result["product_competitor"] == "GB SNOW NCP"
    assert result["movement_lead"] == 10


def test_detail_contains_explicit_low_outlet_and_map_link(monkeypatch):
    metric = SimpleNamespace(
        product_name="CB LITE NCP",
        movement_score=4,
        stock_status="គ្រប់",
        bbe_date="06.2027",
    )
    submission = SimpleNamespace(
        dealer="KPS7",
        region="R3",
        member_no=9,
        outlet_name="Test Outlet",
        outlet_type="Drink Shop",
        total_outlet_visit_target=None,
        report_date=date(2026, 7, 25),
        phone_number="+85512345678",
        gps_latitude=11.215704,
        gps_longitude=104.580909,
        gps_text=None,
        product_metrics=[metric],
    )

    details = build_detail_rows([submission], {"KPS7": _aggregate(3)})
    assert len(details) == 1
    assert details[0]["movement_lt5"] == 4
    assert details[0]["product_competitor"] == "GB SNOW NCP"
    assert details[0]["movement_lead"] == 10
    assert details[0]["link_map"].endswith("11.2157040,104.5809090")
