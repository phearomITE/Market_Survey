import csv
import io
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, KoboSubmission, KoboProductMetric
from app.kobo import sync
from app.kobo.client import KoboClient
from app.web import power_bi
from app.core.config import settings
import pytest


def test_full_sync_keeps_incomplete_rows_and_rebuilds(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'test.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    rows = [{'_id': 1, 'report_date': '2026-09-19', 'dealer': 'CA1'}, {'_id': 2}]
    with patch.object(sync, 'SessionLocal', factory), patch.object(sync, 'init_db'), \
         patch.object(sync, 'ensure_wide_columns', return_value={}), \
         patch.object(sync, 'upsert_wide_submission'), \
         patch.object(KoboClient, 'fetch_submissions', return_value=rows) as fetch:
        result = sync.sync_kobo(full_history=True, force=True)
        assert result['synced'] == 2 and result['skipped'] == 0
        assert result['audit']['missing_source_ids'] == 0
        assert fetch.call_args.kwargs['page_limit'] == 10000
        assert sync.sync_kobo(full_history=True)['unchanged'] == 2
        with factory() as db:
            sub_id = db.scalar(select(KoboSubmission.id).where(KoboSubmission.submission_id == '1'))
            metric = db.scalar(select(KoboProductMetric).where(KoboProductMetric.submission_id == sub_id))
            metric.product_name = 'obsolete mapping'
            db.commit()
        assert sync.sync_kobo(full_history=True, force=True)['synced'] == 2
        with factory() as db:
            assert db.scalar(select(KoboProductMetric).where(KoboProductMetric.product_name == 'obsolete mapping')) is None
    app = FastAPI(); app.include_router(power_bi.router)
    with patch.object(power_bi, 'SessionLocal', factory), patch.object(settings, 'power_bi_api_key', 'test'):
        client = TestClient(app)
        for feed in ['dealers', 'sync_status']:
            assert client.get('/api/power-bi/' + feed).status_code == 401
        data = client.get('/api/power-bi/sync_status', params={'api_key': 'test'})
        record = list(csv.DictReader(io.StringIO(data.text)))[0]
        assert record['database_rows'] == '2' and record['kobo_rows_at_sync'] == '2'
        dealers = client.get('/api/power-bi/dealers', params={'api_key': 'test'})
        assert len(list(csv.DictReader(io.StringIO(dealers.text)))) == 65
    engine.dispose()


def test_pagination_follows_every_page_and_rejects_incomplete():
    client = KoboClient()
    with patch.object(client, '_get_json', side_effect=[
        {'count': 2, 'results': [{'_id': 1}], 'next': 'https://example.invalid/page2'},
        {'count': 2, 'results': [{'_id': 2}], 'next': None},
    ]):
        assert len(client._fetch_pages('asset', params={}, deadline_seconds=900, request_timeout=12, page_limit=10000)) == 2
    with patch.object(client, '_get_json', return_value={'count': 2, 'results': [{'_id': 1}], 'next': None}):
        with pytest.raises(RuntimeError, match='incomplete'):
            client._fetch_pages('asset', params={}, deadline_seconds=900, request_timeout=12, page_limit=10000)
