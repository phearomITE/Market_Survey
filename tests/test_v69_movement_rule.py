"""Targeted checks for submitted-score-only movement calculation."""

from app.reports.aggregator import (
    _apply_offtake_comparison_goal,
    _movement_from_payload,
    final_offtake_movement,
    movement_average,
)


def test_cb_lite_example_uses_8_entered_scores_not_19_outlets():
    values = [10, 10, 10, 10, 10, 10, 9, 10]
    assert len(values) == 8
    assert movement_average(values) == 79 / 8
    assert final_offtake_movement(values) == 10


def test_blank_or_no_sale_is_not_a_movement_zero():
    assert _movement_from_payload(
        {"fresh_status_cb_lite_ncp": "no_sale", "fresh_movement_score_cb_lite_ncp": 0},
        "CB LITE NCP",
        False,
    ) is None
    assert _movement_from_payload(
        {"fresh_status_cb_lite_ncp": "sale", "fresh_movement_score_cb_lite_ncp": 0},
        "CB LITE NCP",
        False,
    ) == 0


def test_cb_lite_wins_example_and_only_one_product_is_10():
    result = {
        "products": {
            "CB LITE NCP": {"mov": 10, "_mov_avg": 79 / 8},
        },
        "competitors": {
            "GB SNOW NCP": {"mov": 8, "_mov_avg": 62 / 8},
            "Hanuman LITE NCP": {"mov": 7, "_mov_avg": 7.1},
            "Krud LITE NCP": {"mov": 6, "_mov_avg": 6.2},
            "Greet LITE NCP": {"mov": 5, "_mov_avg": 5.2},
        },
    }
    _apply_offtake_comparison_goal(result)
    scores = [
        result["products"]["CB LITE NCP"]["mov"],
        result["competitors"]["GB SNOW NCP"]["mov"],
        result["competitors"]["Hanuman LITE NCP"]["mov"],
        result["competitors"]["Krud LITE NCP"]["mov"],
        result["competitors"]["Greet LITE NCP"]["mov"],
    ]
    assert scores[0] == 10
    assert scores[1] == 8
    assert scores.count(10) == 1
    assert len(scores) == len(set(scores))
