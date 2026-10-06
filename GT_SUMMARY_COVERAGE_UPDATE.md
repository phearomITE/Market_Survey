# GT coverage summary update

GT Summary_beer now matches the supplied 13-column layout. Total Submissions counts ordinary outlet visit records only. Final-summary Khmer markers, including added names/numbers/spaces, are excluded from visit, availability, area and movement counts. A dealer with only final-summary records is No Submit for this report.

CB LITE ORD Outlet counts ordinary visit records with CB LITE ORD availability, using the existing report aggregator. This is a visit count, not distinct physical outlet deduplication.

Total District and Total Commune count distinct administrative areas from visit GPS using the same offline boundaries as the BI feed. Codes identify areas; hierarchical names are fallback keys. Blank/unresolved locations are excluded. Regional and global counts use set unions, so do not sum dealer area counts when areas overlap. Boundary data and resolver are bundled.

The summary retains the previous ORD calculation and parser fixes. No screenshot values are hardcoded. HORECA layout remains unchanged; shared build_summary_rows now excludes summary markers from Total Submissions.

Validation: 28 targeted tests passed; app compilation passed. Existing deprecation warnings remain. Live Railway/Kobo values were not verified.
