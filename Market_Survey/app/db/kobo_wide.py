from __future__ import annotations

"""Dynamic wide-table storage for Kobo form fields.

Why this exists:
- The production tables (kobo_submissions, kobo_product_metrics, etc.) are used
  by the report engine.
- Users also want to see every Kobo question as a database column, without a
  JSONB payload. Kobo forms can change over time, so this module creates and
  updates a separate wide table dynamically.

Tables created:
- kobo_submissions_wide: one row per Kobo submission, one TEXT column per Kobo field.
- kobo_field_map: maps safe SQL column names back to original Kobo question keys.

This avoids JSONB while preserving every field submitted by Kobo.
"""

from datetime import datetime
import hashlib
import re
from typing import Any

from sqlalchemy import text

from app.db.database import engine

SYSTEM_COLUMNS = {
    "submission_id",
    "dealer",
    "region",
    "report_date",
    "submission_time",
    "created_at",
    "updated_at",
}


def _quote_ident(name: str) -> str:
    # Safe PostgreSQL identifier quoting.
    return '"' + name.replace('"', '""') + '"'


def _ascii_slug(value: str, max_len: int = 35) -> str:
    # Keep SQL column names readable for English field names. Khmer text will be
    # represented by a stable hash and mapped in kobo_field_map.
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:max_len].strip("_") or "field"


def field_column_name(kobo_key: str) -> str:
    """Return a stable safe column name for any Kobo key/question label."""
    key = str(kobo_key or "field")
    last = key.split("/")[-1]
    slug = _ascii_slug(last)
    digest = hashlib.sha1(key.encode("utf-8", errors="ignore")).hexdigest()[:10]
    # PostgreSQL identifier length limit is 63 bytes. Keep comfortably shorter.
    name = f"k_{digest}_{slug}"
    return name[:60].rstrip("_")


def _value_to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple)):
        return str(value)
    text_value = str(value)
    return text_value if text_value != "" else None


def ensure_wide_tables() -> None:
    """Create wide table and field map table if missing."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS kobo_submissions_wide (
                submission_id VARCHAR(120) PRIMARY KEY,
                dealer VARCHAR(30),
                region VARCHAR(30),
                report_date DATE,
                submission_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS kobo_field_map (
                column_name VARCHAR(80) PRIMARY KEY,
                kobo_key TEXT UNIQUE NOT NULL,
                question_label TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))


def ensure_wide_columns(flat: dict[str, Any]) -> dict[str, str]:
    """Ensure all flat Kobo keys exist as TEXT columns.

    Returns mapping: original Kobo key -> safe SQL column name.
    """
    ensure_wide_tables()
    mapping: dict[str, str] = {}
    with engine.begin() as conn:
        for kobo_key in sorted(flat.keys(), key=str.lower):
            if not kobo_key:
                continue
            column_name = field_column_name(kobo_key)
            if column_name in SYSTEM_COLUMNS:
                column_name = f"k_{column_name}"
            mapping[kobo_key] = column_name
            conn.execute(text(
                f"ALTER TABLE kobo_submissions_wide ADD COLUMN IF NOT EXISTS {_quote_ident(column_name)} TEXT"
            ))
            conn.execute(
                text("""
                    INSERT INTO kobo_field_map (column_name, kobo_key, question_label)
                    VALUES (:column_name, :kobo_key, :question_label)
                    ON CONFLICT (column_name) DO UPDATE SET
                        kobo_key = EXCLUDED.kobo_key,
                        question_label = EXCLUDED.question_label
                """),
                {
                    "column_name": column_name,
                    "kobo_key": str(kobo_key),
                    "question_label": str(kobo_key).split("/")[-1],
                },
            )
    return mapping


def upsert_wide_submission(flat: dict[str, Any], normalized: dict[str, Any]) -> None:
    """Upsert one Kobo submission into the dynamic wide table.

    This stores every Kobo field as a separate SQL column, not JSONB.
    """
    if not normalized.get("submission_id"):
        return

    mapping = ensure_wide_columns(flat)
    base_values: dict[str, Any] = {
        "submission_id": str(normalized.get("submission_id")),
        "dealer": normalized.get("dealer"),
        "region": normalized.get("region"),
        "report_date": normalized.get("report_date"),
        "submission_time": normalized.get("submission_time"),
        "updated_at": datetime.utcnow(),
    }

    field_values: dict[str, Any] = {}
    for kobo_key, column_name in mapping.items():
        field_values[column_name] = _value_to_text(flat.get(kobo_key))

    values = {**base_values, **field_values}
    columns = list(values.keys())
    quoted_columns = ", ".join(_quote_ident(c) for c in columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    update_cols = [c for c in columns if c != "submission_id"]
    updates = ", ".join(f"{_quote_ident(c)} = EXCLUDED.{_quote_ident(c)}" for c in update_cols)

    sql = f"""
        INSERT INTO kobo_submissions_wide ({quoted_columns})
        VALUES ({placeholders})
        ON CONFLICT (submission_id) DO UPDATE SET {updates}
    """

    with engine.begin() as conn:
        conn.execute(text(sql), values)
