from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook

from app.reports.data_export import EXPORT_PRODUCTS, create_data_export


def _submission(
    sid: str,
    outlet_name: str,
    outlet_type: str,
    lat: float,
    lon: float,
    product_mov: int,
    competitor_mov: int,
    member_no: int = 6,
):
    return SimpleNamespace(
        submission_id=sid,
        report_date=date(2026, 7, 18),
        region="R1",
        dealer="CA1",
        group_no=2,
        member_no=member_no,
        total_outlet_visit_target=2,
        outlet_name=outlet_name,
        outlet_type=outlet_type,
        is_new_outlet=False,
        submitter_name="Tester",
        phone_number="+588886631198",
        location_text="",
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


def test_data_export_uses_template_and_writes_two_sheets(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    template = project_root / "templates" / "Template_Data_Survey.xlsx"
    output = tmp_path / "export.xlsx"

    rows = [
        _submission("1", "Outlet One", "Wholesale", 12.085292, 106.422036, 4, 8, member_no=1),
        _submission("2", "Outlet Two", "Drink Shop", 11.568123, 102.9957213, 6, 10, member_no=6),
        # Control row must not be exported as an outlet.
        _submission("3", "បូកសរុបរួម", "Wholesale", 0, 0, 10, 10),
    ]

    path, stats = create_data_export(
        rows,
        date(2026, 7, 18),
        template_path=template,
        output_path=output,
    )

    assert path == output
    assert stats["dealer_groups"] == 1
    assert stats["member_groups"] == 1
    assert stats["summary_rows"] == len(EXPORT_PRODUCTS)
    assert stats["location_rows"] == 2

    workbook = load_workbook(output, data_only=True)
    summary = workbook["Summary_Data"]
    location = workbook["Location_Outlet"]

    assert summary["A2"].value == "R1"
    assert summary["B2"].value == "CA1"
    assert summary["C2"].value == "1, 6"
    assert summary["D2"].value == 2
    assert summary[f"D{len(EXPORT_PRODUCTS) + 1}"].value == 2
    assert summary["E2"].value == 1
    assert summary["F2"].value == 1
    assert summary["N2"].value == "CB LITE ORD"
    assert summary.max_row == len(EXPORT_PRODUCTS) + 1

    assert location.max_row == 3
    assert location["F2"].value == "Outlet One"
    assert location["H2"].value == "+588886631198"
