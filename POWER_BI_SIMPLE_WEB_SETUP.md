# Simple CSV connection, matching the older Kobo QA project

The supplied old project exposes /powerbi/market_issue_daily_report.csv with no
API-key requirement. Its separate auto_kobo_loop updates the database. This
Market Survey version follows the same database -> CSV -> Power BI pattern.

New URL:
https://marketsurvey-production.up.railway.app/powerbi/market_survey_dashboard.csv

1. Deploy app/core/config.py and app/web/power_bi.py from this update.
2. In Railway Market_Survey variables set POWER_BI_PUBLIC_CSV_ENABLED=true.
   Deploy that variable change. Anyone with the URL can now download all feed
   data, including phone numbers, coordinates, issues and suggestions.
   Setting false disables this public route. The existing API-key route stays protected.
3. Keep BI_Sync worker running, as described in POWER_BI_DASHBOARD_SETUP.md.
   Wait for its first successful full sync. Without a successful sync, CSV returns
   HTTP 503. A refresh does not itself fetch Kobo: new data appears after the worker
   completes its next cycle (five-minute wait between completed runs by default).
4. Power BI -> Get Data -> Blank Query -> Advanced Editor.
   Paste docs/power_bi/dashboard_web.pq. Use Anonymous credentials for this URL.
   If Power BI has saved Web API credentials for the base domain, use Data source
   settings to edit the permissions for this connection. Existing protected queries
   still need their Web API credentials; do not switch them to Anonymous.
5. Close & Apply. Refresh loads the current database CSV. This query uses Date,
   not the old project's submission_time/issue_date/solve_date/created_at columns.

Same dashboard fields and definitions as POWER_BI_DASHBOARD_SETUP.md, including
Submission ID for distinct visit counts. All own-brand GT/HORECA products;
/export_detail stays beer-only. No endpoint truncation limit is imposed.

Validation: anonymous route disabled by default, public route works when enabled,
protected route still requires its key, dashboard fields and new saved rows,
backfill and worker tests. Live deployment and Power BI Desktop not tested here.
