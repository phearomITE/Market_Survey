from pathlib import Path

from app.db.models import KoboSubmission


def test_summary_report_type_is_available_to_sync_code():
    assert hasattr(KoboSubmission, "summary_report_type")
    assert KoboSubmission.__table__.c.summary_report_type.nullable is True


def test_existing_database_migration_adds_summary_report_type():
    source = Path("app/db/database.py").read_text(encoding="utf-8")
    assert '("summary_report_type", "VARCHAR(80)")' in source
