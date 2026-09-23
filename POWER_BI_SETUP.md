# Power BI connection for Market Survey

Use `Market_Survey_Git(1).zip` as your current source archive. The other uploaded ZIP has nested older copies. Apply `Market_Survey_Power_BI_Web_Update.zip` to the root of your existing Git working directory. The full ZIP is for backup/review only: never unzip it on top of a current Git checkout unless you intend to replace the project.

## Deploy

1. In Railway, choose the **Market_Survey app** service, then Variables. Add `POWER_BI_API_KEY` with a freshly generated long random value. Do not add it to the Postgres service, Git, or Power Query code.
2. Apply the code and push it; Railway must deploy the new commit. Keep `DATABASE_URL` pointing to the private PostgreSQL service as it does now.
3. In Power BI Desktop choose Get data > Blank query > Advanced Editor and paste:

```powerquery
let
    Source = Csv.Document(
        Web.Contents(
            "https://marketsurvey-production.up.railway.app",
            [RelativePath = "api/power-bi/outlets", ApiKeyName = "api_key"]
        ),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"id", Int64.Type}, {"report_date", type date}, {"is_summary", type logical}})
in
    Typed
```

When asked for credentials, choose **Web API** and paste the `POWER_BI_API_KEY` value. If Power BI has stored incorrect credentials, use File > Options and settings > Data source settings > clear permissions for the app URL, then refresh. Duplicate this query for `products`, `competitors`, and `ring_pulls`, changing only `RelativePath`; remove/adjust the `Typed` step for those feeds: the key is `submission_db_id`, not `id`. Relate `outlets[id]` to each detail table's `submission_db_id` (1 to many). Use `is_summary = false` to count real outlets. The export is raw submitted data, not the bot's final calculated movement score.

Publishing a report also requires configuring **Web API** credentials under the semantic model's Data source credentials in Power BI Service, then enabling Scheduled refresh. Browser URLs without an API key return 401 by design. Do not place the API key in a URL or screenshot.

## Run in Git Bash

```bash
cd /d/Bot/Market_Survey_Git
unzip -o /c/Users/User/Downloads/Market_Survey_Power_BI_Web_Update.zip -d .
python -m compileall -q app
python -m unittest discover -s tests -v
git status
git add app/main.py app/core/config.py app/web/power_bi.py app/bot/run_bot.py POWER_BI_SETUP.md
git commit -m "Add protected Power BI CSV exports"
git push origin main
```

Check tests finish successfully before `git add`. Check `git status` to ensure no `.env` or secrets are staged. The Railway start command runs the bot; this update also starts the FastAPI server on Railway PORT. This code was syntax checked here but could not be tested against your live database. Existing full-suite test failures from old product names, templates, and form deploy are separate from the BI endpoint; the full test suite must not be described as passing.
