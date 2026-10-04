import csv
import io
from datetime import date, datetime
from unittest.mock import patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, KoboSubmission, KoboProductMetric, SyncLog
from app.core.config import settings
from app.web import power_bi
from app.services.dashboard_feed import HEADERS


def test_dashboard_auth_location_products_and_new_data(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path/'dashboard.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    app = FastAPI(); app.include_router(power_bi.router)
    with patch.object(power_bi, 'SessionLocal', factory), patch.object(settings, 'power_bi_api_key', 'test-key'):
        client = TestClient(app)
        url='/api/power-bi/dashboard'
        assert client.get(url).status_code == 401
        initial = client.get(url, params={'api_key':'test-key'})
        assert initial.status_code == 200
        assert initial.headers['X-BI-Sync-State'] == 'initial-sync-in-progress'
        with factory() as db:
            sub=KoboSubmission(submission_id='100',report_date=date(2026,10,3),region='R1',dealer='CA2',
                submission_time=datetime(2026, 10, 3, 12, 28), outlet_name='Shop, Khmer',outlet_type='Drink Shop',report_type='GT',phone_number='012345678',
                gps_latitude=11.55,gps_longitude=104.93,key_issue_text='Issue, one\nIssue two',suggestion_text='Suggestion')
            db.add(sub);db.flush()
            db.add_all([KoboProductMetric(submission_id=sub.id,product_name='CB LITE ORD',available=True,movement_score=7),
                KoboProductMetric(submission_id=sub.id,product_name='WURKZ ORD',available=False,movement_score=9),
                KoboProductMetric(submission_id=sub.id,product_name='CBL Pint',available=True,movement_score=8)])
            db.commit()
        with patch.object(settings, 'power_bi_public_csv_enabled', True):
            partial = client.get('/powerbi/market_survey_dashboard.csv')
            assert partial.status_code == 200
            assert 'Shop, Khmer' in partial.text
            assert partial.headers['X-BI-Sync-State'] == 'initial-sync-in-progress'
            assert client.get('/powerbi/market_survey_submissions.csv').status_code == 200
        with factory() as db:
            db.add(SyncLog(source='kobo_bi_full',status='success',fetched=1,synced=1,skipped=0));db.commit()
        public_url='/powerbi/market_survey_dashboard.csv'
        with patch.object(settings, 'power_bi_public_csv_enabled', False):
            assert client.get(public_url).status_code == 404
        with patch.object(settings, 'power_bi_public_csv_enabled', True):
            public_response=client.get(public_url)
            assert public_response.status_code == 200
            submissions = client.get("/powerbi/market_survey_submissions.csv")
            assert submissions.status_code == 200
            records = list(csv.DictReader(io.StringIO(submissions.text)))
            assert any(r["submission_id"] == "100" for r in records)
            assert "phone_number" in records[0]
            assert len(list(csv.DictReader(io.StringIO(public_response.text)))) == 2
            assert client.get(url).status_code == 401  # Protected route remains protected.
        response=client.get(url,params={'api_key':'test-key'})
        assert response.status_code==200
        data=list(csv.DictReader(io.StringIO(response.text)))
        assert list(data[0])==list(HEADERS)
        assert len(data)==2  # GT excludes HORECA placeholders, includes non-beer.
        assert data[0]['Province']=='Phnom Penh' and data[0]['Commune']=='Tonle Basak'
        assert data[0]['Code_Province']=='12'
        assert data[0]['Code_District']=='1201'
        assert data[0]['Code_Commune']=='120101'
        assert data[0]['Phone Number Outlet']=='012345678'
        assert data[0]['Key Issues Detail']=='Issue, one\nIssue two'
        assert data[1]['Movement Rate']=='0'
        assert data[0]['Submission ID']=='100'
        assert data[0]['id']=='100'
        assert data[0]['submit_time']=='2026-10-03 12:28:00'
        with factory() as db:
            sub=KoboSubmission(submission_id='101',report_date=date(2026,10,4),outlet_name='New visit',report_type='HORECA')
            db.add(sub);db.flush();db.add(KoboProductMetric(submission_id=sub.id,product_name='CBL Pint',available=True,movement_score=10));db.commit()
        data=list(csv.DictReader(io.StringIO(client.get(url,params={'api_key':'test-key'}).text)))
        assert len(data)==3 and data[-1]['Submission ID']=='101'
        assert data[-1]['Commune']==''
        assert all(data[-1][k]=='' for k in ('Code_Province','Code_District','Code_Commune'))
        data=list(csv.DictReader(io.StringIO(client.get(url,params={'api_key':'test-key','start_date':'2026-10-04'}).text)))
        assert len(data)==1
        with factory() as db:
            db.add(SyncLog(source='kobo_bi_full',status='failed'));db.commit()
        assert client.get(url,params={'api_key':'test-key'}).status_code==200  # Prior successful backfill remains readable.
    engine.dispose()
