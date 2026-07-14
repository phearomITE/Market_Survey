from pathlib import Path
import shutil

from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine


def main() -> None:
    errors: list[str] = []

    if not settings.telegram_bot_token:
        errors.append("TELEGRAM_BOT_TOKEN is missing")
    if not settings.kobo_token:
        errors.append("KOBO_TOKEN is missing")
    if not settings.kobo_asset_uid:
        errors.append("KOBO_ASSET_UID is missing")
    if not settings.template_file.exists():
        errors.append(f"Template missing: {settings.template_file}")

    soffice = settings.libreoffice_path or shutil.which("libreoffice") or shutil.which("soffice")
    if not soffice or not Path(soffice).exists():
        errors.append("LibreOffice was not found")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        errors.append(f"PostgreSQL connection failed: {exc}")

    if errors:
        print("Railway preflight failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Railway preflight passed")
    print(f"Template: {settings.template_file}")
    print(f"LibreOffice: {soffice}")


if __name__ == "__main__":
    main()
