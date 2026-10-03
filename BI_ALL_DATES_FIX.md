# All report dates

Preserve exact Kobo report dates, including off-cycle and future entered dates.
Repairs an incorrect stored report_date even if source_hash is unchanged.
Full sync records report_date_counts and report_date_mismatches in SyncLog.message.
Success requires zero missing submission IDs and zero report-date count mismatches.
Avoids repeated ALTER TABLE calls for existing wide columns and field map rewrites.
Parent upsert returns its ID directly, eliminating a separate query per changed row.
Committed batches resume automatically after deployment. Later dates remain unavailable
until their submissions are saved; this patch does not claim a completed live import.

Dashboard: /powerbi/market_survey_dashboard.csv
Progress: /powerbi/market_survey_sync_status.csv (anonymous when public CSV enabled)
Status fields: Saved Submissions, First Report Date, Last Report Date, Sync Status,
Fetched Submissions, Changed Submissions, Skipped Submissions.
Running means import has not completed. Success is a completed snapshot, not a guarantee
that a new submission has already appeared. The next automatic cycle imports new changes.
The dashboard excludes summary-marker records and has one row per own product per visit.
Use all-submissions CSV for exact Kobo record reconciliation.

Validated: 11 local tests, including all dates July-October, unchanged-hash date repair,
CSV access, pagination, interruption/resume, automatic startup and worker locking.
Real Railway PostgreSQL schema optimization and full live completion have not been tested here.
