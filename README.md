# KB Market Survey Bot V39

Railway-ready Telegram bot for:

- KoboToolbox synchronization
- PostgreSQL storage
- Dealer Excel reports
- LibreOffice PDF/PNG rendering
- Single-dealer and selected multi-dealer Telegram reports
- Manual final summary selected by the four Outlet Name markers

## Commands

```text
/start
/status
/sync_kobo
/debug_kobo
/report CPH2 2026-07-14
/report_multi CPH2 CA2 KDL1 CA1 CA7 2026-07-14
/report5 CPH2 CA2 KDL1 CA1 CA7 2026-07-14
/report_today 2026-07-14
/summary 2026-07-14
```

## Local Windows run

1. Copy `.env.example` to `.env`.
2. Set local PostgreSQL and secret values.
3. Start PostgreSQL:

```powershell
docker compose up -d postgres
```

4. Install and run:

```powershell
python -m pip install -r requirements.txt
python -m app.bot.run_bot
```

For Windows, set:

```env
LIBREOFFICE_PATH=C:/Program Files/LibreOffice/program/soffice.exe
```

## Railway deployment

See `RAILWAY_DEPLOYMENT.md`.

The Dockerfile installs LibreOffice and Noto fonts for Linux report rendering. Railway's normal `postgresql://` database URL is automatically converted to SQLAlchemy's psycopg v3 URL.

## Security

Never commit `.env`. Store Kobo, Telegram and PostgreSQL credentials only in Railway Variables or a local ignored `.env`.
