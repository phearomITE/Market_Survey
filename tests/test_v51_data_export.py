from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook

from app.reports.data_export import EXPORT_PRODUCTS, SUMMARY_HEADERS, create_data_export


def _submission(
    sid: str,
    outlet_name: str,
    outlet_type: str,
    lat: float,
    lon: float,
    product_mov: int,
    competitor_mov: int,
    member_no: int = 6,
    group_no: int = 2,
    location_text: str = "Area A",
):
    return SimpleNamespace(
        submission_id=sid,
        report_date=date(2026, 7, 18),
        region="R1",
        dealer="CA1",
        group_no=group_no,
        member_no=member_no,
        total_outlet_visit_target=20,
        outlet_name=outlet_name,
        outlet_type=outlet_type,
        is_new_outlet=False,
        submitter_name="Tester",
        phone_number="+588886631198",
        location_text=location_text,
        gps_text=f"{lat} {lon}",
        gps_latitude=lat,
        gps_longitude=lon,
        key_issue_text="",
        suggestion_text="",
        product_metrics=[
            SimpleNamespace(
                product_name="CB LITE ORD",
                status="sale",
                available=True,
                movement_score=product_mov,
                stock_status=None,
                bbe_date=None,
                buy_in_price=None,
                sell_out_price=None,
                ring_pull_value=None,
                new_outlet_purchase=False,
                volume_ctn=None,
            )
        ],
        competitor_metrics=[
            SimpleNamespace(
                product_name="GB SNOW ORD",
                status="sale",
                movement_score=competitor_mov,
                stock_status=None,
                buy_in_price=None,
                sell_out_price=None,
            )
        ],
        ring_pull_metrics=[],
    )


def _find_product_row(ws, product: str) -> int:
    for row in range(2, ws.max_row + 1):
        if ws.cell(row, 11).value == product:
            return row
    raise AssertionError(f"Product row not found: {product}")


def test_data_export_matches_dealer_product_layout(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    template = project_root / "templates" / "Template_Data_Survey.xlsx"
    output = tmp_path / "export.xlsx"

    rows = [
        _submission(
            "1", "Outlet One", "Wholesale", 12.085292, 106.422036,
            4, 8, member_no=1, group_no=2, location_text="Area A",
        ),
        _submission(
            "2", "Outlet Two", "Drink Shop", 11.568123, 102.9957213,
            6, 10, member_no=6, group_no=3, location_text="Area B",
        ),
        # Control row must not be exported or counted as an outlet.
        _submission(
            "3", "បូកសរុបរួម", "Wholesale", 0, 0,
            10, 10, member_no=9, group_no=9, location_text="Summary",
        ),
    ]

    path, stats = create_data_export(
        rows,
        date(2026, 7, 18),
        template_path=template,
        output_path=output,
    )

    assert path == output
    assert stats["dealer_groups"] == 1
    assert stats["summary_rows"] == len(EXPORT_PRODUCTS)
    assert stats["location_rows"] == 2

    workbook = load_workbook(output, data_only=True)
    summary = workbook["Summary_Data"]
    location = workbook["Location_Outlet"]

    assert [summary.cell(1, col).value for col in range(1, 17)] == SUMMARY_HEADERS
    assert summary.max_row == len(EXPORT_PRODUCTS) + 1

    # Dealer-level values repeat for every product row and are not split by Member.
    assert summary["A2"].value == "R1"
    assert summary["B2"].value == "CA1"
    assert summary["C2"].value == "Area A | Area B"
    assert summary["D2"].value == "1, 6"
    assert summary["E2"].value == "2, 3"
    assert summary["F2"].value == 2
    assert summary["G2"].value == 1
    assert summary["H2"].value == 1
    assert summary["I2"].value == 0
    assert summary["J2"].value == 0
    assert summary[f"F{len(EXPORT_PRODUCTS) + 1}"].value == 2

    # Product-specific outlet counts use only outlets where that product is sold.
    own_row = _find_product_row(summary, "CB LITE ORD")
    assert summary.cell(own_row, 12).value == 1  # WS
    assert summary.cell(own_row, 13).value == 1  # DS
    assert summary.cell(own_row, 14).value == 0  # WM
    assert summary.cell(own_row, 15).value == 0  # TL
    assert summary.cell(own_row, 16).value is not None

    competitor_row = _find_product_row(summary, "GB SNOW ORD")
    assert summary.cell(competitor_row, 12).value == 1
    assert summary.cell(competitor_row, 13).value == 1
    assert summary.cell(competitor_row, 16).value is not None

    assert location.max_row == 3
    assert location["F2"].value == "Outlet One"
    assert location["H2"].value == "+588886631198"
