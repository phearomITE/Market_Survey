# Market Survey BI update
This package contains the full project and the BIGINT fix.

Changed full sync:
- Commit every 250 changed submissions. Parent, metrics, and raw wide fields share the transaction.
- Store running checkpoints. Retry skips successfully saved unchanged submissions.
- Full success is recorded only after the Kobo/database ID audit.
- The CSV returns 503 during an incomplete/failed full sync rather than presenting partial data as complete.
- Records absent from Kobo are retained and counted as database_only_ids; this update does not delete them.
- A source row without an ID blocks a successful completeness audit.
- No fixed submission row limit is applied by either CSV.

Power BI:
Dashboard: https://marketsurvey-production.up.railway.app/powerbi/market_survey_dashboard.csv
One row per own-brand product per outlet visit. Summary markers excluded.
All submissions: https://marketsurvey-production.up.railway.app/powerbi/market_survey_submissions.csv
One row per stored submission, including summary and incomplete records; use this to reconcile counts.
These are not interchangeable row counts. Count distinct Submission ID for dashboard visits.

Set POWER_BI_PUBLIC_CSV_ENABLED=true in Market_Survey. Anyone with the URL can then read this data.
In Power BI choose Anonymous. Existing protected API routes still require their Web API key.

For continuous sync create one separate Railway service named BI_Sync from the same repository:
- Same DATABASE_URL, KOBO_BASE_URL, KOBO_TOKEN, KOBO_ASSET_UID.
- POWER_BI_WORKER_ONLY=true
- POWER_BI_SYNC_INTERVAL_SECONDS=300
- Start command: python -u -m scripts.power_bi_worker
- One replica, no web health check or public domain.
The existing app.bot.run_bot entrypoint also honors POWER_BI_WORKER_ONLY.
Do not set POWER_BI_WORKER_ONLY=true on the main Market_Survey service.
Do not run a manual sync alongside the worker.
Worker retries failed cycles and runs again 300 seconds after each cycle.
A managed worker is independent of your browser console connection.

After deploying, either use BI_Sync or run once in Market_Survey Console:
cd /app
python -u -m scripts.sync_power_bi
Wait for the completed audit before refreshing Power BI.
Do not keep the old manual sync running while starting the worker.

Verification: local mocked data, SQLite transaction/resume tests and PostgreSQL SQL compilation.
Live PostgreSQL migration and Railway end-to-end sync require verification after deployment.
