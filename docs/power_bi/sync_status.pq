let
    Source = Csv.Document(Web.Contents("https://marketsurvey-production.up.railway.app",
        [RelativePath = "api/power-bi/sync_status", ApiKeyName = "api_key", Timeout = #duration(0, 0, 10, 0)]),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Nulls, {{"database_rows", Int64.Type}, {"kobo_rows_at_sync", Int64.Type}, {"synced_rows", Int64.Type}, {"skipped_rows", Int64.Type}, {"first_report_date", type date}, {"last_report_date", type date}, {"last_submission_time", type datetime}, {"last_full_sync_utc", type datetime}}, "en-US")
in
    Typed
