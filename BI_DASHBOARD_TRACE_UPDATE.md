# Dashboard trace update

Adds submit_time (stored Kobo submission timestamp, without timezone conversion) and id
(Kobo _id, the same stable identifier as Submission ID; not the internal SQL row id).
Date remains the Kobo Report Date, not submission date.
Includes prior all-dates repairs and schema-check optimization.
Logs now identify schema preparation and scanned-row progress separately from saved batches.
A fetched count only verifies source retrieval; wait for final Kobo sync completion and zero
skipped/missing/date mismatch audit before confirming complete data.
Dashboard remains one own-product row per visit, excluding summary-marker rows.
Use docs/power_bi/dashboard_web.pq in Power Query Advanced Editor; no fixed Columns option.
11 local tests passed, including timestamp/id CSV values and all report dates.
Live Railway import completion is not verified here.
