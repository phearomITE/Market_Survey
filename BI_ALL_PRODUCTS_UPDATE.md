Dashboard now reads both own and competitor metric tables, using UNION ALL.
Adds Product Type (Own Product/Competitor) and Report Type (GT/HORECA).
Existing dashboard columns and location codes remain intact. Unavailable own products have Movement Rate zero. Competitors retain recorded movement score; no invented availability flag.
Channel product mappings remain enforced to avoid blank HORECA placeholders on GT visits and vice versa. Summary marker submissions remain excluded from this product feed.
Covers all products in the current code mappings; newly added Kobo fields require mapping updates. This does not generate missing metric records; background sync must have saved them.
After deploy refresh the existing public CSV. Remove fixed Columns=16/18/21; use QuoteStyle.Csv. Use docs/power_bi/dashboard_web.pq if replacing the query.
Product rows are not visit counts: count distinct Submission ID for visits, not CSV rows. Products may appear in both product types; use Product Type alongside Product in comparisons.
The screenshot shows Sport 300mL; current local mappings use Sport 500mL. This patch does not change historical labels or rewrite the aggregator mapping. Check deployed mapping if that obsolete label remains.
Validation: 5 tests passed; compilation passed. No live Railway deployment performed here.
