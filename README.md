# KB Market Survey Bot — GT + HORECA

Railway-ready Telegram bot for one Kobo asset with two report routes:

- **GT** uses the existing General Trade template and product flow.
- **HORECA** uses `templates/template_horeca.xlsx` and the new HORECA product flow.
- Kobo submissions are stored in PostgreSQL with `report_type = GT` or `HORECA`.
- `/report` and `/summary` filter by the selected report type before calculating results.

## Telegram commands

```text
/start
/status
/sync_kobo
/debug_kobo

/report CA3 GT 2026-07-18
/report CA3 HORECA 2026-07-18

/summary GT 2026-07-25
/summary HORECA 2026-07-25

/report_multi CPH2 CA2 KDL1 CA1 CA7 2026-07-14
/report_today 2026-07-14
```

Backward-compatible commands remain valid:

```text
/report CA3 2026-07-18       # defaults to GT
/summary 2026-07-25          # defaults to GT
```

## Report routing

The Kobo question `final_summary_report_type` is normalized to:

```text
gt      -> GT
horeca  -> HORECA
```

Old records without the selector fall back to their outlet type. HORECA outlet types are Local Eat, Coffee/Bakery, Canteen, Sport Club, Motor Shop and Local Drink.

## Templates

```text
templates/template_general.xlsx   # GT
templates/template_horeca.xlsx    # HORECA
templates/KB_Market_Improvement_XLSForm.xlsx
```

The HORECA report generator uses the uploaded HORECA template without changing its worksheet dimensions, merged layout, widths or row positions.

## First synchronization after

changes the stored metric schema. Run this once after Railway becomes active:

```text
/sync_kobo
```

The first sync may take longer because product and competitor metric rows are rebuilt once for the GT/HORECA form. Later syncs return to normal hash-based incremental updates.

## Local validation

```bash
python -m py_compile \
  app/bot/handlers.py \
  app/db/database.py \
  app/db/models.py \
  app/kobo/parser.py \
  app/kobo/sync.py \
  app/reports/aggregator.py \
  app/reports/excel_report.py \
  app/reports/summary_report.py \
  app/services/report_service.py

py -3.12 -m pytest -q
```

## Security

Never commit `.env`. Keep Kobo, Telegram, PostgreSQL and map tokens only in Railway Variables or a local ignored `.env` file.
