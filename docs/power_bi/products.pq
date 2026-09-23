let
    Source = Csv.Document(Web.Contents("https://marketsurvey-production.up.railway.app",
        [RelativePath = "api/power-bi/products", ApiKeyName = "api_key", Timeout = #duration(0, 0, 10, 0)]),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Nulls, {{"submission_db_id", Int64.Type}, {"metric_id", Int64.Type}, {"report_date", type date}, {"is_summary", type logical}, {"movement_score", type number}, {"buy_in_price", type number}, {"sell_out_price", type number}, {"ring_pull_value", type number}, {"volume_ctn", type number}, {"available", type logical}, {"new_outlet_purchase", type logical}}, "en-US")
in
    Typed
