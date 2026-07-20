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

## Daily BI Data Export

Telegram command:

```text
/export 2026-07-18
```

The bot synchronizes the complete requested Kobo date and sends
`Market_Survey_Data_YYYY-MM-DD.xlsx` with two sheets.

### Summary_Data

One row represents one Dealer + Product. Dealers are not split by Member.

Columns:

```text
Region, Dealer, Location_Visit, Member, Group, Total_Outlets,
Wholesale, Drink_Shop, Wet_Market, Trolley,
Product, WS, DS, WM, TL, Mov
```

- `Member` and `Group` combine unique values for the dealer.
- `Total_Outlets` equals all real outlet submissions for the dealer.
- `Wholesale` through `Trolley` are dealer-level outlet counts.
- `WS`, `DS`, `WM`, `TL` are product-specific selling-outlet counts.
- `Mov` uses the same final normalized comparison movement as the dealer report.
- Final-summary marker submissions are excluded.

### Location_Outlet

One row per real outlet with date, GPS, outlet name/type, and phone number.
