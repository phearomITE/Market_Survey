# KB Market Survey Bot — New Short Kobo Form Ready

This project is updated for the new Kobo XLSForm:

- `templates/KB_Market_Improvement_XLSForm_New.xlsx`
- 1 Kobo submission = 1 outlet visit
- Group by `dealer + report_date` = 1 dealer report
- Output keeps the same `templates/template_by_dealer.xlsx` report layout

## Run locally

```powershell
cd D:\Bot\kb_market_surveys
python -m pip install -r requirements.txt
docker compose up -d postgres
python -m app.bot.run_bot
```

## Telegram commands

```text
/start
/sync_kobo
/debug_kobo
/report CA2 2026-06-29
/report_today 2026-06-29

Then verify it's installed:

ollama list

Expected:

NAME
qwen2.5:7b
deepseek-r1:8b

Then test it:

ollama run qwen2.5:7b

Type:

Hello

It should reply immediately (without the long reasoning process that DeepSeek-R1 produces).

Exit:

/bye

Then check:

ollama ps
```

## New form field support

The bot now maps these new short form fields:

- Own product status: `fresh_status_*`
- Own product movement: `fresh_movement_score_*`
- Own product stock: `fresh_stock_status_*`
- BBE: `fresh_bbe_*`
- Buy in: `fresh_buy_in_price_*`
- Sell out: `fresh_sell_out_price_*`
- Ring pull price: `fresh_ring_pull_*`
- Competitor status: `comp_status_*`
- Competitor movement: `comp_movement_score_*`
- Ring Pull in Outlets: `ring_pull_qty_cbl_ncp_6_can`, `ring_pull_qty_cbl_ncp_5_usd`
- Key Issues: `key_issues_detail`
- Initiative/Suggestion: `initiative_idea_suggestion`

## Important production note

Do not run `python -m scripts.seed_test_data` in production because it inserts fake test rows. Use `/sync_kobo` or `python -m app.kobo.sync` for real Kobo data.

If PNG preview does not work on Windows, set this in `.env`:

```env
LIBREOFFICE_PATH=C:\Program Files\LibreOffice\program\soffice.exe
```

## Local AI summary with Ollama

Recommended model for report summarization:

```powershell
ollama pull qwen2.5:7b
```

`.env`:

```env
AI_SUMMARY_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
AI_SUMMARY_TIMEOUT=600
AI_SUMMARY_TEMPERATURE=0.1
AI_SUMMARY_NUM_CTX=4096
```

The bot uses Ollama directly for Key Issues and Initiative/Suggestion summaries. Python still handles numeric aggregation such as Movement average, BBE mode, Stock threshold, availability counts, competitor averages, and Ring Pull totals. If the configured Ollama model is not installed, the bot will try an installed supported model and will fall back to clean raw comments if AI is unavailable, so report generation will not crash.

## Database storage update: all Kobo questions as SQL columns

This version keeps the production normalized report tables and also creates a dynamic wide table for all Kobo form questions:

- `kobo_submissions` — core outlet-visit fields used by report filters.
- `kobo_product_metrics` — one row per own product per submission.
- `kobo_competitor_metrics` — one row per competitor product per submission.
- `kobo_ring_pull_metrics` — one row per ring-pull product per submission.
- `kobo_submissions_wide` — one row per submission, with one TEXT column per Kobo question/field.
- `kobo_field_map` — maps each generated SQL column in `kobo_submissions_wide` back to the original Kobo question/key.

No `payload JSONB` column is used. During every sync, the bot automatically adds any new Kobo question as a new SQL column in `kobo_submissions_wide`.

Useful SQL checks:

TRUNCATE TABLE
    public.kobo_competitor_metrics,
    public.kobo_product_metrics,
    public.kobo_ring_pull_metrics,
    public.kobo_submissions_wide,
    public.kobo_submissions,
    public.sync_logs
RESTART IDENTITY CASCADE;

```sql
SELECT * FROM kobo_submissions_wide ORDER BY submission_time DESC LIMIT 5;
SELECT column_name, kobo_key FROM kobo_field_map ORDER BY kobo_key;
SELECT dealer, report_date, COUNT(*) FROM kobo_submissions GROUP BY dealer, report_date;
```

## iPhone KoBo/Enketo IndexedDB Error

If iPhone users see `Failed to execute 'transaction' on 'IDBDatabase'`, read:

`docs/IPHONE_ENKETO_INDEXEDDB_FIX.md`

This is a KoBo/Enketo browser storage issue, not a PostgreSQL or Telegram bot issue.
