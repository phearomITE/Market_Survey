ALTER TABLE IF EXISTS kobo_submissions
ADD COLUMN IF NOT EXISTS source_hash VARCHAR(64);

CREATE INDEX IF NOT EXISTS ix_kobo_submissions_source_hash
ON kobo_submissions (source_hash);
