from pathlib import Path


def test_summary_uses_exact_dealer_report_aggregation_path():
    source = Path('app/reports/summary_report.py').read_text(encoding='utf-8')

    assert 'aggregate_submissions' in source
    assert 'aggregate_movement_comparison' not in source
    assert 'wide_map=wide_map' in source
