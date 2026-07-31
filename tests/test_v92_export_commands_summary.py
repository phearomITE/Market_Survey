from datetime import date
from types import SimpleNamespace

from openpyxl import load_workbook

from app.reports.movement_exports import (
    RAW_MOVEMENT_HEADERS,
    create_raw_movement_export,
)
from app.reports.summary_report import create_summary_report


def _metric(name: str, score: int | None):
    return SimpleNamespace(product_name=name, movement_score=score)


def test_raw_movement_export_writes_product_rows_and_preserves_zero(tmp_path):
    row = SimpleNamespace(
        report_date=date(2026, 7, 25),
        region="R1",
        dealer="CA1",
        gps_latitude=11.55,
        gps_longitude=104.91,
        outlet_name="Test Outlet",
        outlet_type="Drink Shop",
        phone_number="012345678",
        product_metrics=[
            _metric("CB LITE NCP", 10),
            _metric("CBC 4.4 NCP", 0),
        ],
        competitor_metrics=[_metric("GB SNOW NCP", 8)],
    )
    output = create_raw_movement_export(
        [row],
        date(2026, 7, 25),
        output_path=tmp_path / "raw.xlsx",
    )
    ws = load_workbook(output, data_only=True).active
    headers = [cell.value for cell in ws[1]]
    assert headers == RAW_MOVEMENT_HEADERS
    values = {row[3]: row[4] for row in ws.iter_rows(min_row=2, values_only=True)}
    assert values["CB LITE NCP"] == 10
    assert values["CBC 4.4 NCP"] == 0
    assert values["GB SNOW NCP"] == 8


def test_gt_summary_is_simple_one_sheet_submission_layout(tmp_path):
    rows = [
        {
            "region": "R1",
            "dealer": "CA1",
            "total_submissions": 25,
            "total_outlets": 25,
            "target": None,
            "status": "✅",
        },
        {
            "region": "R1",
            "dealer": "CA8",
            "total_submissions": 0,
            "total_outlets": 0,
            "target": None,
            "status": "❌ No Submit",
        },
    ]
    output = create_summary_report(
        rows,
        date(2026, 7, 25),
        output_path=tmp_path / "summary.xlsx",
        report_type="GT",
    )
    workbook = load_workbook(output, data_only=True)
    assert workbook.sheetnames == ["Summary"]
    ws = workbook["Summary"]
    assert ws["A1"].value == "KB Market Survey - GT Region & Dealer Submission Summary"
    assert [ws.cell(8, column).value for column in range(1, 6)] == [
        "Region",
        "Dealer",
        "Total Submissions",
        "Total Outlets",
        "Status",
    ]
    assert ws["A4"].value == "Total Regions"
    assert ws["G4"].value == "Completion"
