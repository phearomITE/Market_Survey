from app.core.config import Settings


def test_railway_postgresql_url_uses_psycopg_v3():
    s = Settings(
        _env_file=None,
        database_url="postgresql://postgres:secret@postgres.railway.internal:5432/railway",
    )
    assert s.db_url == (
        "postgresql+psycopg://postgres:secret@postgres.railway.internal:5432/railway"
    )


def test_legacy_postgres_scheme_is_normalized():
    s = Settings(
        _env_file=None,
        database_url="postgres://postgres:secret@host:5432/db",
    )
    assert s.db_url.startswith("postgresql+psycopg://")
