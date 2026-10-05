# GT summary ORD fast-fetch fix (v2)

GT summaries now compare CB LITE ORD with GB SNOW ORD, Hanuman LITE ORD and Greet LITE ORD. Applies to all GT report dates, including 2026-10-03. HORECA continues to compare Pint products.

The actual aggregation selects ORD metrics, not just ORD labels. Greet ORD has its own Kobo field aliases, separate from NCP, and participates in ORD comparison normalization. Existing availability and coverage-weighted final movement rules remain in use.

A product-mapping revision is included in source hashes: existing records are rebuilt by the automatic BI sync on its next pass, even if the Kobo source row is unchanged. Wait for background sync to finish after deployment before rerunning the summary. Greet ORD cannot be inferred from Greet NCP; it requires an actual ORD field in the source form.

Regression tests cover conflicting ORD/NCP values, each competitor winning, own-product winning, generated workbook headers, Greet field aliases, HORECA and cache invalidation. Three unrelated legacy assertions in test_v105_business_movement.py and test_v35_outlet_name_summary.py also fail in the original uploaded project (old product names and expected own-product count).

## Why the previous report showed zeros

The summary-only fast-fetch branch in app/kobo/sync.py still built CB LITE NCP and competitor NCP metrics. The summary then looked for ORD metrics, which were absent. This version also switches that fetch branch to ORD, with four regression cases passing raw Kobo rows through the actual summary parser and aggregation. 21 focused tests pass; app compilation passes. The patch does not copy the example screenshot values into the report.

## Git Bash

```bash
cd /d/Bot/Market_Survey_Git
unzip -o /c/Users/User/Downloads/Market_Survey_GT_Summary_ORD_Fast_Fetch_Fix.zip -d .

.venv/Scripts/python.exe -m pytest tests/test_gt_summary_ord.py tests/test_v92_export_commands_summary.py tests/test_power_bi_backfill.py -q --basetemp="exports/pytest-summary-ord-$(date +%Y%m%d_%H%M%S)" &&
.venv/Scripts/python.exe -m compileall -q app &&
git add app/reports/summary_report.py app/reports/aggregator.py app/kobo/sync.py tests/test_gt_summary_ord.py tests/test_v92_export_commands_summary.py GT_SUMMARY_ORD_UPDATE.md &&
git commit -m "Use ORD products in GT summary comparison" &&
git push origin main
```

After Railway deploys, the summary fetch reads and parses the requested date directly from Kobo. Run `/summary GT 2026-10-03` in Telegram. This patch has not been run against your production database.
