let
    Source = Csv.Document(Web.Contents("https://marketsurvey-production.up.railway.app/powerbi/market_survey_submissions.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {{"submission_id", type text}, {"report_date", type date}}, "en-US")
in
    Types
