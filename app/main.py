from fastapi import FastAPI
from app.db.database import init_db
from app.kobo.sync import sync_kobo
from app.services.report_service import generate_dealer_report, generate_today_all_dealers

app = FastAPI(title='KB Market Survey')

@app.on_event('startup')
def startup():
    init_db()

@app.get('/')
def root():
    return {'status': 'ok', 'app': 'KB Market Survey'}

@app.post('/sync_kobo')
def api_sync_kobo():
    return sync_kobo()

@app.post('/report/{dealer}/{report_date}')
def api_report(dealer: str, report_date: str):
    path, message = generate_dealer_report(dealer, report_date)
    return {'message': message, 'path': str(path) if path else None}

@app.post('/report_today/{report_date}')
def api_report_today(report_date: str):
    path, message = generate_today_all_dealers(report_date)
    return {'message': message, 'path': str(path)}
