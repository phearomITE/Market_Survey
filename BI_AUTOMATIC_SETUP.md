# Automatic Market Survey BI
Deploy the full update to the existing Market_Survey service.
The web startup automatically starts a single background loop per app process.
PostgreSQL advisory locking prevents duplicate automatic sync cycles across replicas.
The loop immediately performs a full fetch, commits changed submissions every 250 rows,
and repeats 300 seconds after completion. Failed runs retry; saved batches resume by hash.
No console sync command or separate BI_Sync service is required.
If a separate BI_Sync service was previously created, stop it when using this setup.

Market_Survey variables:
POWER_BI_PUBLIC_CSV_ENABLED=true (existing opt-in for the public data)
POWER_BI_AUTO_SYNC_ENABLED=true (default true)
POWER_BI_SYNC_INTERVAL_SECONDS=300 (default 300)
POWER_BI_WORKER_ONLY must be absent or false in the main service.
Existing DATABASE_URL, KOBO_BASE_URL, KOBO_TOKEN, KOBO_ASSET_UID remain required.
Do not manually launch a concurrent full sync.

Dashboard:
https://marketsurvey-production.up.railway.app/powerbi/market_survey_dashboard.csv
Choose Anonymous in Power BI Web credentials.
All submissions:
https://marketsurvey-production.up.railway.app/powerbi/market_survey_submissions.csv

On the first deployment, CSV returns 503 until the first successful full backfill.
After that, CSV reads the live database during later cycles.
Rows updated during a batch cycle can reflect different sync times until it finishes.
If a later cycle fails, existing data remains readable and may be stale.
X-BI-Last-Sync-UTC identifies the last completed successful full sync.
Use the protected sync_status feed/logs to check freshness.
Public endpoints expose outlet phone and GPS to anyone with the URL.

Dashboard is one visit x own-brand product, excludes summary markers.
All-submissions CSV includes summary and incomplete records for Kobo reconciliation.
Deleted Kobo records are retained; audit reports database-only IDs.
GPS boundary names are generated offline; invalid/ambiguous coordinates remain blank.
A Power BI refresh reads the database; it does not force a Kobo sync.

Validation uses temporary SQLite/mocked Kobo and PostgreSQL SQL compilation.
Railway live sync completion and PostgreSQL migration remain to be verified after deployment.
