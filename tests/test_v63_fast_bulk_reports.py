from datetime import date, datetime
from types import SimpleNamespace as NS

from app.reports.aggregator import (
    IndexedPayload,
    aggregate_bulk_submissions,
    aggregate_submissions,
    first_value,
)


def _own(name, movement, available=True):
    return NS(
        product_name=name,
        movement_score=movement,
        available=available,
        status="sale" if available else "no_sale",
        stock_status=None,
        bbe_date=None,
        buy_in_price=None,
        sell_out_price=None,
        ring_pull_value=None,
        new_outlet_purchase=False,
        volume_ctn=None,
    )


def _competitor(name, movement):
    return NS(
        product_name=name,
        movement_score=movement,
        status="sale",
        stock_status=None,
        buy_in_price=None,
        sell_out_price=None,
    )


def _row(index, own, gb, hanuman, krud, greet):
    return NS(
        id=index,
        submission_id=str(index),
        submission_time=datetime(2026, 7, 18, 8, index),
        updated_at=datetime(2026, 7, 18, 8, index),
        report_date=date(2026, 7, 18),
        region="R1",
        dealer="CA1",
        group_no=1,
        member_no=7,
        total_outlet_visit_target=3,
        outlet_name=f"Outlet {index}",
        outlet_type="Drink Shop",
        phone_number="0",
        location_text="Phnom Penh",
        gps_text="",
        gps_latitude=11.5,
        gps_longitude=104.9,
        key_issue_text="",
        suggestion_text="",
        summary_report_type="GENERAL",
        product_metrics=[_own("CB LITE NCP", own)],
        competitor_metrics=[
            _competitor("GB SNOW NCP", gb),
            _competitor("Hanuman LITE NCP", hanuman),
            _competitor("Krud LITE NCP", krud),
            _competitor("Greet LITE NCP", greet),
        ],
        ring_pull_metrics=[],
    )


def test_indexed_payload_matches_alias_without_rebuilding_indexes():
    payload = IndexedPayload({
        "fresh_movement_score_cb_lite_ncp": "7",
        "CB LITE NCP - Movement Score 0-10": "7",
    })
    assert first_value(payload, ["fresh_movement_score_cb_lite_ncp"]) == "7"
    assert first_value(payload, ["CB LITE NCP - Movement Score 0-10"]) == "7"


def test_fast_bulk_movement_matches_final_dealer_report_rule():
    rows = [
        _row(1, 7, 5, 4, 3, 2),
        _row(2, 8, 6, 7, 5, 4),
        _row(3, 9, 7, 8, 6, 5),
    ]
    normal = aggregate_submissions(rows, wide_map={}, report_type="GENERAL")
    fast = aggregate_bulk_submissions(rows, wide_map={})

    assert fast["products"]["CB LITE NCP"]["mov"] == normal["products"]["CB LITE NCP"]["mov"]
    for product in (
        "GB SNOW NCP",
        "Hanuman LITE NCP",
        "Krud LITE NCP",
        "Greet LITE NCP",
    ):
        assert fast["competitors"][product]["mov"] == normal["competitors"][product]["mov"]
