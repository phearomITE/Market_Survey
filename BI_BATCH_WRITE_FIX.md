# BI batch write fix

Observed production log: unchanged=6888, changed=111 at processed=7000, several minutes
into new records. This demonstrates a progressing but slow import, not a date dropdown bug.
Full-history imports now queue up to 250 changed submissions, execute a single parent
upsert with RETURNING, execute the wide upsert as a prepared batch, delete old metrics
by a batch of parent IDs and bulk-insert replacement metrics. All these writes and the
checkpoint share one transaction. A failed batch rolls back; previously committed batches
remain and are skipped on the next automatic cycle. Final partial batch is also saved.
Normal date-filtered command sync retains its existing single-row path.
All previous exact report-date audits and dashboard submit_time/id columns remain.
No automatic pruning occurs until a complete import is reconciled.

13 local tests passed, including batch insert request counts, failed-batch rollback/resume,
wide null clearing, all report dates, CSV trace columns, startup and worker tests.
These tests use SQLite and mocks for the wide PostgreSQL table. Live Railway PostgreSQL
performance and completed 19989-record import have not been verified here.

Deploy once and monitor BI sync SAVED. Do not launch a parallel manual sync.
Use /powerbi/market_survey_sync_status.csv to inspect saved rows and latest report date.
Fetch completion alone does not mean database completion. Refresh the existing dashboard
query after final sync success. No Power Query or endpoint change is required.
