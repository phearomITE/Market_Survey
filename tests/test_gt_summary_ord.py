from datetime import date
from types import SimpleNamespace as NS
import pytest
from openpyxl import load_workbook
from app.reports.aggregator import COMPETITOR_PRODUCTS, competitor_field
from app.reports.summary_report import _dealer_movement, create_summary_report


def metric(name, score):
    return NS(product_name=name, movement_score=score, stock_status='full', available=True)


def submission(winner='CB LITE ORD'):
    competitors = ['GB SNOW ORD', 'Hanuman LITE ORD', 'Greet LITE ORD']
    return NS(id=1, submission_id=1, report_date=date(2026, 10, 3),
              region='R1', dealer='CA1', member_no=1, outlet_name='Shop',
              outlet_type='Wholesale', phone_number='012345678',
              gps_latitude=11.55, gps_longitude=104.91,
              product_metrics=[metric('CB LITE ORD', 10 if winner == 'CB LITE ORD' else 2),
                               metric('CB LITE NCP', 10)],
              competitor_metrics=[metric(n, 10 if n == winner else 2) for n in competitors]
                  + [metric('GB SNOW NCP', 10), metric('Hanuman LITE NCP', 10),
                     metric('Greet LITE NCP', 10)], ring_pull_metrics=[])


@pytest.mark.parametrize('winner', ['GB SNOW ORD', 'Hanuman LITE ORD', 'Greet LITE ORD'])
def test_summary_compares_ord_and_ignores_conflicting_ncp(winner):
    result = _dealer_movement([submission(winner)], wide_map={})
    assert result['competitor'] == winner
    assert result['competitor_display'] == 10
    assert result['own_display'] < 10


def test_own_ord_wins_and_summary_headers_are_ord(tmp_path):
    row = submission()
    result = _dealer_movement([row], wide_map={})
    assert result['own_display'] == 10
    assert result['competitor'] is None
    rows = [dict(region='R1', dealer='CA1', total_submissions=1,
                 total_outlets=1, target=None, status='✅')]
    output = create_summary_report(rows, row.report_date,
                                   output_path=tmp_path / 'summary.xlsx',
                                   submissions=[row], report_type='GT')
    ws = load_workbook(output, data_only=True).active
    assert [ws.cell(4, col).value for col in (8,9,10)] == [
        'GB SNOW ORD', 'Hanuman LITE ORD', 'Greet LITE ORD']
    assert 'CB LITE ORD' in ws['F6'].value
    assert ws['H8'].value == 10


def test_greet_ord_form_field_mapping_is_distinct_from_ncp():
    assert 'Greet LITE ORD' in COMPETITOR_PRODUCTS
    fields = competitor_field('Greet LITE ORD', 'mov')
    assert any('greet_lite_ord' in key for key in fields)
    assert not any('greet_lite_ncp' in key for key in fields)


def test_horeca_still_uses_pint():
    row = submission()
    row.product_metrics = [metric('CBL Pint', 2)]
    row.competitor_metrics = [metric('Tiger Crystal Pint', 10)]
    result = _dealer_movement([row], report_type='HORECA', wide_map={})
    assert result['competitor'] == 'Tiger Crystal Pint'


def test_mapping_revision_invalidates_old_cache_hashes():
    import hashlib
    import json
    from app.kobo.sync import _source_hash
    raw = {"_id": 123, "comp_movement_score_greet_lite_ord": 10}
    old = hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True,
        default=str, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert _source_hash(raw) != old
    assert _source_hash(raw) == _source_hash(dict(reversed(list(raw.items()))))


@pytest.mark.parametrize('winner', ['CB LITE ORD', 'GB SNOW ORD', 'Hanuman LITE ORD', 'Greet LITE ORD'])
def test_fast_summary_fetch_parses_ord_from_kobo(monkeypatch, winner):
    from app.kobo import sync
    from app.kobo.client import KoboClient
    codes = {'CB LITE ORD': 'cb_lite_ord', 'GB SNOW ORD': 'gb_snow_ord',
             'Hanuman LITE ORD': 'hanuman_lite_ord', 'Greet LITE ORD': 'greet_lite_ord'}
    raw = {'_id': 432, 'report_date': '2026-10-03', 'dealer': 'CA1',
           'region': 'R1', 'outlet_name': 'Test shop', 'outlet_type': 'Wholesale',
                      'fresh_movement_score_cb_lite_ord': 10 if winner == 'CB LITE ORD' else 2,
           'fresh_movement_score_cb_lite_ncp': 10}
    for product, code in codes.items():
        if product != 'CB LITE ORD':
            raw['comp_movement_score_' + code] = 10 if winner == product else 2
    monkeypatch.setattr(KoboClient, 'fetch_submissions', lambda *a, **kw: [raw])
    rows = sync._build_report_submissions(dealer=None, report_date=date(2026, 10, 3),
        wanted=set(), summary_only=True, metadata_only=False)
    assert len(rows) == 1
    assert 'CB LITE ORD' in [m.product_name for m in rows[0].product_metrics]
    assert {'GB SNOW ORD', 'HANUMAN LITE ORD', 'Greet LITE ORD'} <= set(m.product_name for m in rows[0].competitor_metrics)
    result = _dealer_movement(rows, wide_map={})
    if winner == 'CB LITE ORD':
        assert result['own_display'] == 10
        assert result['competitor'] is None
    else:
        assert result['competitor'] == winner
        assert result['competitor_display'] == 10
        assert 0 < result['own_display'] < 10


def test_summary_matches_full_dealer_aggregation():
    from app.reports.aggregator import aggregate_submissions
    row = submission()
    row.competitor_metrics.append(metric('Krud LITE ORD', 10))
    full = aggregate_submissions([row], wide_map={}, include_ring_pull=False,
                                include_manual_summary=False)
    assert _dealer_movement([row], wide_map={})['own_display'] == full['products']['CB LITE ORD']['mov']
