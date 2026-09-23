let
    Source = Csv.Document(Web.Contents("https://marketsurvey-production.up.railway.app",
        [RelativePath = "api/power-bi/dealers", ApiKeyName = "api_key", Timeout = #duration(0, 0, 10, 0)]),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers))
in
    Nulls
