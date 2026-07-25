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
/alert_submit
/alert_submit 10
/alert_submit 2026-07-25 20
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

Yes, the updated code is now correctly inside the real Git repository.

This confirms it:

```text
modified: app/reports/excel_report.py
```

The diff also shows the new spacing values:

```python
SUMMARY_MIN_ROW_HEIGHT = 32
SUMMARY_LINE_HEIGHT = 22
SUMMARY_MAX_ROW_HEIGHT = 140
```

You are currently inside the `git diff` viewer. Press:

```text
q
```

Then commit and push:

```bash
git add app/reports/excel_report.py
git commit -m "Improve four-line Khmer summary spacing"
git push origin main
```

Verify the latest commit:

```bash
git log -1 --oneline
```

You should see a new commit such as:

```text
xxxxxxx Improve four-line Khmer summary spacing
```

Railway should then automatically build and deploy the new GitHub commit. After the deployment becomes active, test:

```text
/report CPH2 2026-07-14
```

## Dealer submission alerts

The bot sends daily alerts using `APP_TIMEZONE` (default `Asia/Phnom_Penh`):

- `09:30` — dealers with fewer than 10 real outlet submissions
- `10:30` — dealers with fewer than 20 real outlet submissions

Final summary rows such as `បូកសរុបរួម` are excluded from the counts.
Dealers with zero submissions are included.

Run `/alert_submit` once inside the Telegram **General** group to save that
group as the automatic alert target. The command can also be used manually:

```text
/alert_submit
/alert_submit 10
/alert_submit 20
/alert_submit 2026-07-25 10
```

`/alert_submit` uses the `<10` threshold before 10:30 AM and `<20` at or
after 10:30 AM. Railway variables can override the saved group with
`SUBMIT_ALERT_CHAT_ID`. Leave `SUBMIT_ALERT_THREAD_ID` empty to post in General.
