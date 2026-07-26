from datetime import date
from types import SimpleNamespace

from app.reports.raw_movement_export import RAW_MOVEMENT_PRODUCTS, build_raw_movement_data


def metric(product: str, score: int | None):
    return SimpleNamespace(product_name=product, movement_score=score)


def submission(dealer: str, own=None, competitors=None, outlet_name="Outlet"):
    return SimpleNamespace(
        submission_id=f"{dealer}-{outlet_name}",
        report_date=date(2026, 7, 25),
        region="R1",
        dealer=dealer,
        outlet_name=outlet_name,
        product_metrics=list(own or []),
        competitor_metrics=list(competitors or []),
    )


def test_raw_movement_has_long_and_all_product_wide_outputs():
    rows = [
        submission(
            "CA1",
            own=[metric("CB LITE NCP", 10)],
            competitors=[metric("GB SNOW NCP", 8)],
            outlet_name="A",
        ),
        submission(
            "CA1",
            own=[metric("CB LITE NCP", 9)],
            competitors=[metric("GB SNOW NCP", 0)],
            outlet_name="B",
        ),
        submission(
            "CA1",
            own=[metric("CB LITE NCP", None)],
            competitors=[],
            outlet_name="C",
        ),
        # Final summary control row must never appear.
        submission(
            "CA1",
            own=[metric("CB LITE NCP", 7)],
            outlet_name="បូកសរុបរួម",
        ),
    ]

    long_rows, wide_rows = build_raw_movement_data(rows, wide_map={})

    assert [row[-1] for row in long_rows if row[3] == "CB LITE NCP"] == [9, 10]
    assert [row[-1] for row in long_rows if row[3] == "GB SNOW NCP"] == [8]
    assert len(wide_rows) == 1

    cb_index = 3 + RAW_MOVEMENT_PRODUCTS.index("CB LITE NCP")
    gb_index = 3 + RAW_MOVEMENT_PRODUCTS.index("GB SNOW NCP")
    assert wide_rows[0][cb_index] == 9.5
    assert wide_rows[0][gb_index] == 8.0
    assert len(RAW_MOVEMENT_PRODUCTS) == 57
