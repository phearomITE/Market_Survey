# Deploy KB Market Survey Bot to Railway from GitHub

## Architecture

Use two services in the same Railway project and production environment:

1. `Postgres` — Railway PostgreSQL service.
2. `Market-Survey-Bot` — this GitHub repository, running as one always-on worker.

The bot uses Telegram long polling, so it does not need a public domain and must not be configured as a cron job.

## Railway variables for the bot service

Paste these in the bot service **Variables → Raw Editor**. Replace only the placeholder secret values.

```env
APP_NAME=KB Market Survey
APP_ENV=production
APP_TIMEZONE=Asia/Phnom_Penh

DATABASE_URL=${{Postgres.DATABASE_URL}}

KOBO_BASE_URL=https://kf.kobotoolbox.org
KOBO_TOKEN=REPLACE_WITH_NEW_KOBO_TOKEN
KOBO_ASSET_UID=REPLACE_WITH_KOBO_ASSET_UID

TELEGRAM_BOT_TOKEN=REPLACE_WITH_NEW_TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=

TEMPLATE_PATH=templates/template_by_dealer.xlsx
EXPORT_DIR=exports

AUTO_SYNC_BEFORE_REPORT=false
AUTO_SYNC_ENABLED=true
AUTO_SYNC_INTERVAL_SECONDS=60
REPORT_SYNC_WAIT_SECONDS=240

LIBREOFFICE_PATH=/usr/bin/libreoffice
PNG_RENDER_SCALE=4.0
PNG_MAX_WIDTH=6000
```

Do not add local variables such as `DB_HOST=localhost`, `DB_PORT=5438`, or a Windows LibreOffice path to Railway.

## Railway service settings

- Source: GitHub repository root.
- Branch: `main`.
- Builder: Dockerfile (auto-detected).
- Start command: supplied by `railway.json`.
- Replicas: exactly `1`.
- Serverless/sleep: disabled; the bot must stay running.
- Cron schedule: empty.
- Public domain: not required.
- Postgres and bot must be in the same Railway project and same environment.

## Expected deployment logs

```text
Environment: production
Database target: postgres.railway.internal:5432/railway
Database tables are ready
KB Market Survey Bot running
Auto Kobo sync enabled: every 60 seconds
```

## Telegram smoke test

```text
/status
/sync_kobo
/report CPH2 2026-07-14
/report_multi CPH2 CA2 KDL1 CA1 CA7 2026-07-14
```

## Important

Generated Excel/PDF/PNG files are temporary container files. They are sent to Telegram immediately and may disappear after a redeploy. PostgreSQL data remains persistent in the Railway Postgres volume.
