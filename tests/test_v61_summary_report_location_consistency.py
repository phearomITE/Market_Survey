from app.reports.aggregator import combine_location_visit
from app.reports.summary_report import movement_comparison_from_aggregate


def test_summary_competitor_leader_matches_final_report_values():
    aggregate = {
        "products": {"CB LITE NCP": {"mov": 7}},
        "competitors": {
            "GB SNOW NCP": {"mov": 9},
            "Hanuman LITE NCP": {"mov": 10},
            "Krud LITE NCP": {"mov": 6},
            "Greet LITE NCP": {"mov": 8},
        },
    }

    result = movement_comparison_from_aggregate(aggregate)

    assert result["movement_5_to_8"] == 7
    assert result["competitor_product"] == "Hanuman LITE NCP"
    assert result["competitor_movement_lead"] == 10


def test_location_visit_merges_case_language_and_spelling_variants():
    result = combine_location_visit(
        [
            "Location of Visit: Phnom Penh, Psar prek pnov, psar prek pov, "
            "Saroang, Samroang, Praek Pnov, ព្រែកព្នៅ, ដំបូកខ្ពស់, Pnov"
        ]
    )

    assert result == "Phnom Penh, Prek Pnov, Samroang, ដំបូកខ្ពស់"
