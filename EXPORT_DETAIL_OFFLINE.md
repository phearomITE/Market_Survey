# Outlet-detail export: offline Cambodia boundaries

Fixes the missing BIGDATACLOUD_API_KEY error for `/export_detail YYYY-MM-DD`.
The existing command registration stays unchanged. No additional dependency or API key is required.

## Output
`Export_detail_YYYY-MM-DD.xlsx`: Date, Region, Dealer, Outlet Name, Outlet Type,
Phone Number Outlet, Latitude, Longitude, Province, District, Commune, Product, Movement Rate.
One row per outlet visit and own product; summary-marker submissions are excluded as before.
Product lists follow GT/HORECA form parsing. Movement Rate uses the per-outlet
movement_score, not the dealer-level normalized comparison score. Unavailable
products have rate 0. Available products with missing scores stay blank. Outlets
without product metrics retain one row with blank Product/Movement Rate.
Repeated outlet details are expected; the completion count remains outlet visits.
Region and Dealer remain Kobo values; location mapping does not reassign dealers.

## Boundary data
Bundled `app/data/boundaries/cambodia_communes.json.gz` is generated from:
- `Map_KML(3).kml`: 1,652 commune geometries, primary coverage.
- `Location_All(3).xlsx`: 1,652 distinct commune codes, all KML codes matched;
  English Province/District/Commune names joined by commune code, not spelling.
- `CambodiaCommuneBoundaries(1).geojson`: 1,633 fallback geometries, used only
  where no primary polygon matches. Its metadata includes validOn 2018/10/04;
  this is supplied boundary coverage, not a guarantee of current legal borders.
  Exact code matches use workbook names, otherwise GeoJSON names.

Point-in-polygon checks use longitude first in geometry and latitude/longitude
from Kobo. Includes polygon holes, multipart polygons, a spatial grid, and
in-memory reuse for repeated GPS coordinates. No coordinates leave the server.
Conflicting overlaps/shared edges, invalid GPS, and outside-coverage coordinates
remain blank and contribute to the unresolved count. No nearest-commune guess.
Old API-generated disk cache is ignored, so stale names cannot override maps.
Boundary data is bundled in the Docker build; restart to load a changed map.

## Apply from Git Bash
Extract this update ZIP into D:/Bot/Market_Survey_Git. It updates only named files;
it does not delete templates, nested folders, or other project changes.

    PYTHONPATH=. python -X utf8 -m unittest discover -s tests -p test_offline_detail_export.py -v
    PYTHONPATH=. python -X utf8 tests/test_sport_and_detail_update.py
    python -m compileall -q app

Commit the eight files in this ZIP and push. Wait for Railway deployment success
for that commit, then send `/export_detail 2026-01-03` to Telegram.
If Kobo has no submissions for that exact report date, the bot reports that fact.
Use a date with collected data; no artificial records are created.

## Rebuild after changing source files (optional)
    python -X utf8 scripts/build_detail_boundaries.py Location_All.xlsx Map_KML.kml CambodiaCommuneBoundaries.geojson app/data/boundaries/cambodia_communes.json.gz

## Validation
Five offline tests passed, existing Sport/detail checks passed, app compilation
passed. Includes export without API key, real boundary points, invalid/reversed
GPS, polygon holes/edges, ambiguous matches, source priority, no-data date,
phone leading zero and literal cell text. Live Kobo/Telegram/Railway execution
has not been tested here.
