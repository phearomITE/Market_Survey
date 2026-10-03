BI record reconciliation update

Automatic sync resumes on deployment and saves changed records in batches of 250. Product metric inserts now use bulk execution. All pages must be fetched completely; empty, failed or filtered snapshots cannot trigger reconciliation. Missing IDs prevent reconciliation. After successful processing, records absent from Kobo are backed up with their normalized child metrics in kobo_reconciliation_archive before removal from active reporting tables. Raw wide-table historical data is retained. Edited source records are updated by submission ID.

Use market_survey_submissions.csv / docs/power_bi/all_submissions.pq to compare one row per Kobo submission, including summary and incomplete records. The product dashboard excludes summaries and expands products, so its row count is not the Kobo submission count. While the first sync runs, both CSVs expose partial saved data. Refresh after completion. Do not change source dates to force counts. Compare exact submission IDs if a discrepancy remains: live edits/deletions during pagination can require another automatic cycle.

Tests cover interrupted batch recovery, complete pagination, edited dates, archived removed records, missing-ID safety, empty-snapshot safety, and filtered-snapshot safety. Local tests do not verify live Railway connectivity or production completion.
