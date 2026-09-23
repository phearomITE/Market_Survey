# Market Survey BI data update

Apply this overlay ONLY to D:\Bot\Market_Survey_Git (the repository used by Railway).

## What was found

Your screenshot shows Kobo has 16,839 results. It does not show the total BI row count or the final date in the dropdown, so an exact deficit cannot be calculated from it.
The inspected code serves BI from PostgreSQL. Date-filtered Telegram reports fetch Kobo into memory without saving it. Full-history automatic sync is disabled. The normal fetch has a 30-second default deadline and 20-page limit. Old sync also skipped records without dealer/date and marked some old records unchanged without rebuilding them. These are concrete paths to stale/incomplete BI data. The CSV outlets feed itself has no row limit; an optional start_date filter can reduce its scope.

## Changes

- Dedicated full-history command: 900-second fetch budget and 10,000-page safety cap; incomplete pagination raises an error before writes.
- --rebuild refreshes normalized fields, product mappings, and wide fields even when the source hash is unchanged.
- Missing dealer/date no longer causes a submission with a valid ID to be dropped.
- Wide schema creation runs once per sync instead of once per row.
- Existing outlet IDs remain stable; child metric IDs may change after rebuilding. Join on parent IDs, never on metric IDs.
- Final sync audit counts source IDs missing from PostgreSQL and database IDs absent from the source. This does NOT delete old records.
- Authenticated dealers and sync_status CSV feeds added; existing four CSV paths preserved.

The wide table and normalized tables use separate transactions in the existing project. BI uses the normalized tables, which commit at the end of the run. If a run fails, rerun it; a partial wide-table update is possible. Run only one full sync at a time and avoid /sync_kobo while it runs. Large historical rebuilds can take several minutes and use database resources.

## Install and deploy (Git Bash)

```bash
cd /d/Bot/Market_Survey_Git
unzip -o /c/Users/User/Downloads/Market_Survey_BI_Data_Update.zip -d .
.venv/Scripts/python.exe -m compileall -q app scripts/sync_power_bi.py
.venv/Scripts/python.exe -m pytest tests/test_power_bi_backfill.py -q --basetemp=exports/pytest-bi-backfill
```

Use a standard Python virtual environment with requirements.txt and pytest installed. The test folder given to --basetemp is disposable.
After tests pass:

```bash
git add app/kobo/client.py app/kobo/sync.py app/db/kobo_wide.py app/web/power_bi.py scripts/sync_power_bi.py tests/test_power_bi_backfill.py docs/power_bi BI_DATA_UPDATE.md
git diff --cached --stat
git commit -m "Backfill Kobo history and expose BI sync audit"
git push origin main
```

Wait for that exact commit to be active in Railway Market_Survey. This is a data-pipeline overlay and assumes the existing working Power BI startup update is already deployed.

## Run the backfill INSIDE Railway

In Railway, right-click Market_Survey and use Copy SSH Command. Run the copied command in Git Bash (Railway CLI must be installed/authenticated). This opens a shell inside the deployed app container, with its database/Kobo variables available. Then run:

```bash
python -u -m scripts.sync_power_bi --rebuild
```

Keep the session open until the final audit prints. Do not use the Postgres service shell. Do not replace the app's startup command with the one-time backfill command.

For later data updates, inside the same app environment:

```bash
python -u -m scripts.sync_power_bi
```

Without --rebuild this still fetches all pages to detect old edits, but only rewrites changed/new records. It does not start Telegram. To automate later, run this command in a separate scheduled Railway service using the same code and DATABASE_URL/KOBO_* variables, before the Power BI refresh. This ZIP does not create a schedule or change your live infrastructure.

## Reconcile before building charts

1. Sync must exit successfully. Read skipped and audit.missing_source_ids: both should be zero.
2. audit.database_only_ids > 0 means old/deleted source records or a different historical asset need investigation; this update preserves them.
3. Load sync_status: compare kobo_rows_at_sync with Kobo's count for the same asset, permissions and time, with no UI filters. New submissions can change Kobo's count during/after sync.
4. Load outlets without start_date or Power Query filters. Compare row count and DISTINCTCOUNT(submission_id) to database_rows. Distinct IDs should equal row count.
5. Do not compare product row count to Kobo submission count. One submission has many product rows.
6. For visits, exclude is_summary=true. For reconciliation to Kobo, include summary records. Submission count is not unique physical outlet count.

## Connect Power BI

Get data -> Blank query -> Advanced Editor. Paste one matching file from docs/power_bi per query and name the query outlets, products, competitors, ring_pulls, dealers or sync_status.
Choose Web API credentials; enter the Market_Survey service's POWER_BI_API_KEY. Do not put passwords/tokens in the M code. If stale Anonymous credentials are saved, clear permissions for the app URL and reconnect using Web API.
All queries use https://marketsurvey-production.up.railway.app with RelativePath api/power-bi/<feed>. Then Refresh Preview and Close & Apply.
The queries convert report_date to Date (your screenshot shows it was Text), IDs to the appropriate types, and booleans/numbers for measures. Blank CSV fields become null. Invalid date/number text raises a visible error rather than being silently discarded.

## Recommended dashboard model

| Query | Grain | Main fields/use |
|---|---|---|
| outlets | One Kobo submission | submission_id, report_date, submission_time, region, dealer, outlet_name, outlet_type, report_type, is_new_outlet, is_summary, GPS, issues, suggestions |
| products | One submission/product | product_name, status, available, movement_score, stock_status, buy/sell prices, volume_ctn, new_outlet_purchase, BBE |
| competitors | One submission/competitor product | product_name, status, movement_score, stock_status, buy/sell prices |
| ring_pulls | One submission/ring-pull product | product_name, qty_ctn; confirm units with the current form because historic aliases include cans and cartons |
| dealers | One official dealer | All 65 dealers and regions, including dealers with no submissions |
| sync_status | One latest full-sync status row | Source count, database count, first/last report dates, last sync time, skipped rows and audit details |

Use one-to-many, single-direction relationships:
- dealers[dealer] -> outlets[dealer]
- outlets[id] -> products[submission_db_id]
- outlets[id] -> competitors[submission_db_id]
- outlets[id] -> ring_pulls[submission_db_id]
- Your calendar Date -> outlets[report_date]
Leave sync_status disconnected. Do not also link dealers/date directly to the detail tables; that introduces multiple filter paths.
Keep unknown/missing dealer submissions visible in a data-quality page. A 65-dealer dimension does not automatically classify unknown source dealer codes.

Useful initial measures (query names as above):

```dax
Kobo Submissions = DISTINCTCOUNT(outlets[submission_id])
Outlet Visits = CALCULATE([Kobo Submissions], outlets[is_summary] = FALSE())
New Outlet Visits = CALCULATE([Outlet Visits], outlets[is_new_outlet] = TRUE())
Dealers Visited = CALCULATE(DISTINCTCOUNT(outlets[dealer]), outlets[is_summary] = FALSE(), outlets[dealer] <> BLANK())
Summary Dealers = CALCULATE(DISTINCTCOUNT(outlets[dealer]), outlets[is_summary] = TRUE(), outlets[dealer] <> BLANK())
```

Dashboard pages:
1. Coverage: visits by report date, region/dealer, GT/HORECA; zero-submit official dealers.
2. Products: availability/status by product, observed prices and reported volume; filter out summary rows to avoid double counting. Never sum prices or interpret movement_score as sales volume.
3. Competitors: status and price comparisons by selected product/dealer/date; not market share without a defined denominator.
4. Issues: key_issue_text and suggestion_text with outlet/date/dealer detail.
5. Quality: sync_status, missing dealers/dates, latest report date and total IDs.

The normalized feeds deliberately expose selected dashboard columns. The database wide table stores other Kobo fields, but this update does not publish every raw field or phone number. Product rows can be placeholders for unanswered questions; confirm field eligibility before calculating availability percentages. Repeated dealer targets should not be summed across visits. Summary completion needs a single report date selected; a multi-date distinct dealer count is not daily completion.

## Validation and limitations

Local syntax checks passed. New tests exercised two-page fetches, incomplete pagination rejection, retention of a missing-dealer/date record, unchanged-row skipping, forced metric rebuilding, 65-dealer export and protected sync-status export. Existing focused checks also passed. DB behavior was tested with SQLite; live PostgreSQL migration/DDL and 16,839-record runtime have not been tested here. No live Kobo/Railway data was changed. Historical unrelated test failures noted in earlier review remain outside this update. Do not treat this as a guarantee that every bot feature is error-free.

References: https://docs.railway.com/cli/ssh and https://learn.microsoft.com/en-us/powerquery-m/web-contents
