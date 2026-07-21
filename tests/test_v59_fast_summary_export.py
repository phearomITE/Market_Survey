from types import SimpleNamespace

from app.reports.aggregator import (
    IndexedPayload,
    aggregate_movement_comparison,
    first_value,
    product_field,
)


def _submission(sid: str, own: int, gb: int, hanuman: int, krud: int, greet: int):
    return SimpleNamespace(
        submission_id=sid,
        outlet_name=f"Outlet {sid}",
        outlet_type="Drink Shop",
        product_metrics=[
            SimpleNamespace(product_name="CB LITE NCP", movement_score=own),
        ],
        competitor_metrics=[
            SimpleNamespace(product_name="GB SNOW NCP", movement_score=gb),
            SimpleNamespace(product_name="Hanuman LITE NCP", movement_score=hanuman),
            SimpleNamespace(product_name="Krud LITE NCP", movement_score=krud),
            SimpleNamespace(product_name="Greet LITE NCP", movement_score=greet),
        ],
        ring_pull_metrics=[],
    )


def test_indexed_payload_keeps_tolerant_lookup():
    payload = IndexedPayload({"Fresh Movement Score CB LITE NCP": "7"})
    assert first_value(payload, product_field("CB LITE NCP", "mov")) == "7"


def test_fast_movement_comparison_uses_same_final_rule():
    rows = [_submission("1", 7, 5, 4, 3, 2)]
    result = aggregate_movement_comparison(
        rows,
        (
            "CB LITE NCP",
            "GB SNOW NCP",
            "Hanuman LITE NCP",
            "Krud LITE NCP",
            "Greet LITE NCP",
        ),
        wide_map={},
    )
    assert result["products"]["CB LITE NCP"]["mov"] == 10
    assert result["competitors"]["GB SNOW NCP"]["mov"] == 8
    assert result["competitors"]["Hanuman LITE NCP"]["mov"] == 7
    assert result["competitors"]["Krud LITE NCP"]["mov"] == 6
    assert result["competitors"]["Greet LITE NCP"]["mov"] == 5
