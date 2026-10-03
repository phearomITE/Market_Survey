# Market Survey Power BI dashboard feed

Endpoint: https://marketsurvey-production.up.railway.app/api/power-bi/dashboard
Use docs/power_bi/dashboard.pq in Power BI Advanced Editor, not a browser with no key.

## Data contract
One row = one outlet visit × own-brand product, across all dates in PostgreSQL.
Includes GT and HORECA products (not only beer); /export_detail remains beer-only.
Fields: Date, Region, Dealer, Outlet Name, Outlet Type, Phone Number Outlet,
Latitude, Longitude, Province, District, Commune, Product, Movement Rate,
Key Issues Detail, Suggestion, Submission ID.
Phone and Submission ID stay text. Summary-marker visits are excluded.
Movement Rate is the per-outlet Kobo score, not dealer-level normalized movement.
Unavailable product = 0. Available product with no score = blank.
Issue and suggestion repeat on each product row of the same visit.
Submission ID is included so DISTINCTCOUNT can count visits correctly.
Province/District/Commune use the bundled offline boundary lookup. Missing,
invalid, outside, or ambiguous GPS stays blank. No online geocoder key required.
Region/Dealer remain the values submitted in Kobo.
Optional ?start_date=2026-01-01 restricts report dates without changing sync scope.

## One-time Railway setup
1. Deploy the updated GitHub code to your existing Market_Survey app service.
2. Retain/set POWER_BI_API_KEY in Market_Survey. Use a private random key, not your
   database password or Telegram token. Generate locally if needed:
   python -c "import secrets; print(secrets.token_urlsafe(32))"
3. Create a second service from the SAME repository/main branch, name BI_Sync.
   Use root / and the existing Dockerfile. Its start command can remain
   python -m app.bot.run_bot, which now selects worker mode from the variable below.
   Alternatively set python -u -m scripts.power_bi_worker as its start command.
4. Set these variables on BI_Sync:
   POWER_BI_WORKER_ONLY=true
   POWER_BI_SYNC_INTERVAL_SECONDS=300
   DATABASE_URL=<reference to the same Postgres DATABASE_URL used by Market_Survey>
   KOBO_BASE_URL=<same value as Market_Survey>
   KOBO_TOKEN=<same value as Market_Survey>
   KOBO_ASSET_UID=<same value as Market_Survey>
   If Market_Survey has other Kobo settings, copy those too.
5. Keep BI_Sync at one replica, continuously running, with no HTTP healthcheck,
   no public domain, and no sleep/serverless mode. Do not enable worker-only mode
   on Market_Survey. Worker mode does not start Telegram polling or the web app.
6. Wait for BI_Sync logs: BI sync complete. First backfill may take longer because
   all changed records need writing. Further cycles hash-check and skip unchanged
   submissions. The five-minute wait starts AFTER the previous sync completes.

Data flow: Kobo -> automatic worker -> PostgreSQL -> authenticated CSV -> Power BI.
You do not need to run a sync command for each new submission. Refresh gets the
latest committed data. If a submission arrived after the last cycle, wait for
another completed cycle and refresh again. This is polling, not instant push.
A failed or incomplete latest sync makes dashboard return HTTP 503 rather than
silently treating an incomplete sync as successful. Check /api/power-bi/sync_status
using its existing PQ file for last sync time, counts, status, and details.
If the worker is stopped, PostgreSQL retains old data: always monitor that timestamp.
The worker fetches full history each cycle to also detect edits to older records;
set a larger interval for a growing dataset or Kobo usage limits. It does not
remove database submissions deleted in Kobo; sync_status reports database-only IDs.
Avoid running manual full sync concurrently with the worker. BI workers coordinate
with a PostgreSQL advisory lock, but the legacy manual sync uses a process lock.

## Power BI Desktop
Get data -> Blank query -> Advanced Editor -> paste docs/power_bi/dashboard.pq.
Rename query MarketSurvey. Click Edit Credentials -> Web API and enter the exact
POWER_BI_API_KEY value. Select the marketsurvey-production.up.railway.app base URL.
Do not paste the key into M code. Close & Apply, then Home -> Refresh as needed.
The query sets text types for phone/ID, date for Date, numeric coordinates and rate.
If publishing to Power BI Service, configure this source's Web API credentials
there too and schedule refresh if you want the dashboard updated without clicking.

Suggested measures (MarketSurvey query):
Visits = DISTINCTCOUNT(MarketSurvey[Submission ID])
Average Movement = AVERAGE(MarketSurvey[Movement Rate])
Visits With Issues = CALCULATE(DISTINCTCOUNT(MarketSurvey[Submission ID]), FILTER(MarketSurvey, LEN(TRIM(MarketSurvey[Key Issues Detail] & "")) > 0))
Use Date/Region/Dealer/Outlet Type/Product slicers; location map; issue-detail table.
Average Movement above includes zero unavailable products. Do not use SUM of
Movement Rate as sales volume, or COUNTROWS as outlet visits.

## Validation and deployment scope
Endpoint integration tests cover authentication, no-sync guard, geographic fields,
all-product GT/HORECA filtering, CSV commas/newlines, phone leading zero, new rows,
date filtering, failed-sync guard. Backfill tests cover idempotency and pagination.
Validation completed: 3 endpoint/backfill tests and 2 worker tests passed; Python compilation passed.
Live Railway/Kobo/Power BI refresh must be verified after deployment.
This full ZIP is based on Market_Survey_Git(6) plus the prior updates in this chat.
Unzip into the existing checkout; do not replace your checkout or delete templates.
For this update, stage only files listed in APPLY_BI_DASHBOARD.txt.
