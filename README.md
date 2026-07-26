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

## Manual dealer submission alert

Dealer submission alerts run only when a user sends a command. There is no 9:30 AM or 10:30 AM background schedule.

```text
/alert_submit                    # today: show both <10 and <20
/alert_submit 10                 # today: only <10
/alert_submit 20                 # today: only <20
/alert_submit 2026-07-25         # selected date: both sections
/alert_submit 2026-07-25 10      # selected date: only <10
```

## V71: Fast export and unified final movement

- `/export YYYY-MM-DD` is registered in Telegram and generates `Summary_Data` and `Location_Outlet`.
- `/report`, `/summary`, and `/export` use the same shared final movement values.
- Movement average uses only explicitly submitted positive scores from 1 to 10. Blank and zero values are excluded.
- The product with the highest raw average in each comparison group is raised to 10.
- The same increase is added to every other scored product in that group.
- Duplicate positive final ratings are resolved by raw-average ranking, so each comparison group has one Movement 10.
- Bulk summary/export analytics use batched Kobo-wide queries and an in-memory snapshot cache.
- Dealer submission alerts are manual only with `/alert_submit`; no 09:30 or 10:30 scheduler runs.
