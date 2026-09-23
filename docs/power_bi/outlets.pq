let
    Source = Csv.Document(
        Web.Contents("https://marketsurvey-production.up.railway.app", [
            RelativePath = "api/power-bi/outlets",
            ApiKeyName = "api_key",
            Timeout = #duration(0, 0, 10, 0)
        ]),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Nulls, {
        {"id", Int64.Type}, {"submission_id", type text},
        {"report_date", type date}, {"submission_time", type datetime},
        {"updated_at", type datetime}, {"is_summary", type logical},
        {"is_new_outlet", type logical}, {"gps_latitude", type number},
        {"gps_longitude", type number}
    }, "en-US")
in
    Typed
