from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.summary_marker import is_final_summary_outlet_name
from app.services.submission_alert_service import generate_submission_status_export


def test_summary_name_accepts_hidden_kobo_unicode():
    assert is_final_summary_outlet_name("\u200bបូក\u00a0សរុបរួម\ufeff")
    assert is_final_summary_outlet_name("បូកសរុបរូម")
    assert not is_final_summary_outlet_name("Outlet បូកសរុបរួម Shop")


def test_bti6_summary_is_submitted(tmp_path):
    rows = [SimpleNamespace(dealer="BTI6", outlet_name="\u200bបូក សរុបរួម")]
    captured = {}

    def fake_create(status_rows, report_date):
        captured["rows"] = status_rows
        return Path(tmp_path) / "status.xlsx"

    with patch(
        "app.services.submission_alert_service.fetch_report_submissions_fast",
        return_value=rows,
    ), patch(
        "app.services.submission_alert_service.create_submission_status_export",
        side_effect=fake_create,
    ):
        generate_submission_status_export("2026-08-01")

    bti6 = next(row for row in captured["rows"] if row["dealer"] == "BTI6")
    assert bti6["region"] == "R2"
    assert bti6["status"] == "Summary Submitted"
