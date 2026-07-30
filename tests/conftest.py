from __future__ import annotations

import os

# Allow offline unit tests to import the report modules without a PostgreSQL
# driver/server. Railway continues to use DATABASE_URL from its variables.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("KOBO_TOKEN", "test-kobo-token")
os.environ.setdefault("KOBO_ASSET_UID", "test-asset")
