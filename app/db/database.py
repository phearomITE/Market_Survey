from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.db_url,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"connect_timeout": 15},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _safe_exec(conn, sql: str) -> None:
    try:
        conn.execute(text(sql))
    except Exception as exc:
        # Keep startup safe; print migration warnings instead of crashing bot.
        print(f"⚠️ DB migration warning: {exc} | SQL={sql[:80]}")


def _ensure_light_migrations() -> None:
    """Small local migrations for evolving from the old JSONB demo table.

    The old project had kobo_submissions.payload JSONB NOT NULL.
    Production v12 stores form values in real columns + child metric tables,
    so the old payload column is dropped if present.
    """
    with engine.begin() as conn:
        # Core columns added after early demo versions.
        for col, ddl in [
            ("group_no", "INTEGER"),
            ("member_no", "INTEGER"),
            ("total_outlet_visit_target", "INTEGER"),
            ("is_new_outlet", "BOOLEAN"),
            ("submitter_name", "VARCHAR(255)"),
            ("phone_number", "VARCHAR(80)"),
            ("gps_text", "TEXT"),
            ("gps_latitude", "DOUBLE PRECISION"),
            ("gps_longitude", "DOUBLE PRECISION"),
            ("updated_at", "TIMESTAMP"),
            ("source_hash", "VARCHAR(64)"),
        ]:
            _safe_exec(conn, f"ALTER TABLE IF EXISTS kobo_submissions ADD COLUMN IF NOT EXISTS {col} {ddl}")


        # Ensure numeric columns stay numeric even when older versions created them as VARCHAR.
        _safe_exec(conn, """
            ALTER TABLE IF EXISTS kobo_submissions
            ALTER COLUMN group_no TYPE INTEGER
            USING NULLIF(regexp_replace(group_no::text, '[^0-9-]', '', 'g'), '')::integer
        """)
        _safe_exec(conn, """
            ALTER TABLE IF EXISTS kobo_submissions
            ALTER COLUMN member_no TYPE INTEGER
            USING NULLIF(regexp_replace(member_no::text, '[^0-9-]', '', 'g'), '')::integer
        """)
        _safe_exec(conn, """
            ALTER TABLE IF EXISTS kobo_submissions
            ALTER COLUMN total_outlet_visit_target TYPE INTEGER
            USING NULLIF(regexp_replace(total_outlet_visit_target::text, '[^0-9-]', '', 'g'), '')::integer
        """)

        # Remove old raw payload JSONB column per user's production requirement.
        _safe_exec(conn, "ALTER TABLE IF EXISTS kobo_submissions DROP COLUMN IF EXISTS payload")

        # SyncLog columns added after early versions.
        for col in ["fetched", "synced", "skipped"]:
            _safe_exec(conn, f"ALTER TABLE IF EXISTS sync_logs ADD COLUMN IF NOT EXISTS {col} INTEGER")

        for col, ddl in [
            ("stock_status", "VARCHAR(80)"),
        ]:
            _safe_exec(conn, f"ALTER TABLE IF EXISTS kobo_competitor_metrics ADD COLUMN IF NOT EXISTS {col} {ddl}")

        # Keep existing database rows compatible with the renamed product list.
        product_renames = {
            "CBC 4.4": "CBC 4.4 NCP",
            "CB Original": "CB Original NCP",
            "CB LITE": "CB LITE NCP",
            "CB BLACK": "CB BLACK NCP",
            "ភេសជ្ជៈប៉ូវកម្លាំង​កម្ពុជា": "CAMBODIA ED",
            "EXPREZ ត្រសក់ផ្អែម": "EXPREZ Melon",
        }
        competitor_renames = {
            "GB Original": "GB Original NCP",
            "GB  Original": "GB Original NCP",
            "GB SNOW": "GB SNOW NCP",
            "Hanuman Lite": "Hanuman LITE NCP",
            "Krud": "Krud NCP",
            "Krud Lite": "Krud LITE NCP",
            "Greet Lite": "Greet LITE NCP",
            "Great Lite": "Greet LITE NCP",
            "Hanuman Black": "Hanuman Black NCP",
        }
        for old_name, new_name in product_renames.items():
            _safe_exec(conn, f"""
                UPDATE kobo_product_metrics old_row
                SET product_name = '{new_name}'
                WHERE old_row.product_name = '{old_name}'
                  AND NOT EXISTS (
                      SELECT 1 FROM kobo_product_metrics new_row
                      WHERE new_row.submission_id = old_row.submission_id
                        AND new_row.product_name = '{new_name}'
                  )
            """)
            _safe_exec(conn, f"DELETE FROM kobo_product_metrics WHERE product_name = '{old_name}'")
        for old_name, new_name in competitor_renames.items():
            _safe_exec(conn, f"""
                UPDATE kobo_competitor_metrics old_row
                SET product_name = '{new_name}'
                WHERE old_row.product_name = '{old_name}'
                  AND NOT EXISTS (
                      SELECT 1 FROM kobo_competitor_metrics new_row
                      WHERE new_row.submission_id = old_row.submission_id
                        AND new_row.product_name = '{new_name}'
                  )
            """)
            _safe_exec(conn, f"DELETE FROM kobo_competitor_metrics WHERE product_name = '{old_name}'")


def init_db() -> None:
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_light_migrations()
    try:
        from app.db.kobo_wide import ensure_wide_tables
        ensure_wide_tables()
    except Exception as exc:
        print(f"⚠️ Wide table init warning: {exc}")


if __name__ == "__main__":
    init_db()
    print("✅ Database tables are ready")
