from pathlib import Path


def test_summary_uses_original_full_aggregation_path():
    source = Path("app/reports/summary_report.py").read_text(encoding="utf-8")
    assert "load_wide_payloads" not in source
    assert "aggregate_submissions(movement_rows)" in source
    assert "wide_map=wide_map" not in source


def test_export_uses_original_full_aggregation_path():
    source = Path("app/reports/data_export.py").read_text(encoding="utf-8")
    assert "load_wide_payloads" not in source
    assert "aggregate_submissions(rows)" in source
    assert "wide_map=wide_map" not in source
