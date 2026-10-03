let
    Source = Csv.Document(
        Web.Contents("https://marketsurvey-production.up.railway.app/powerbi/market_survey_dashboard.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Types = Table.TransformColumnTypes(Headers, {
        {"Date", type date}, {"Region", type text}, {"Dealer", type text},
        {"Outlet Name", type text}, {"Outlet Type", type text},
        {"Phone Number Outlet", type text}, {"Latitude", type number},
        {"Longitude", type number}, {"Province", type text}, {"District", type text},
        {"Commune", type text}, {"Product", type text}, {"Movement Rate", type number},
        {"Key Issues Detail", type text}, {"Suggestion", type text}, {"Submission ID", type text}
    }, "en-US")
in
    Types
