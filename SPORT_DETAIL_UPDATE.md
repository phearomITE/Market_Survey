# Sport comparison and outlet-detail update

Use `/export_detail 2026-01-03` in Telegram (date format YYYY-MM-DD).
Output: Export_detail_2026-01-03.xlsx.
Columns: Date, Region, Dealer, Outlet Name, Outlet Type, Phone Number Outlet,
Latitude, Longitude, Province, District, Commune.
One row per genuine outlet submission; summary/control rows excluded.

Railway Market_Survey service: add BIGDATACLOUD_API_KEY from a BigDataCloud
server-side Reverse Geocoding API account. The key stays in Railway variables.
The free client-side endpoint is not used for stored GPS coordinates.
Administrative levels 4/6/8 are used for province/district/commune. Missing
levels, invalid GPS and provider failures remain blank and are counted in the
completion message. Review incomplete locations rather than assuming a match.
Coordinates are sent to the configured provider. Successful locations are cached
in exports/outlet_detail_geocode_cache.json (ephemeral unless exports is on a volume).
Only one detail export runs at a time per bot process. It runs in the background;
a redeploy interrupts it, so rerun the command after deployment if needed.

Sport/Pocari/V-Active were absent from OFFTAKE_COMPARE_GROUPS. They now participate
in the same normalization as other groups, excluding zero-availability products.
Raw rounded 7/6/2 alone need not yield 10/9/3: normalization uses the underlying
unrounded effective scores. Exactly one eligible product wins 10.

Also removed an accidental extra function argument from /export movement_multi.
Existing earlier font, product mapping and zero-availability changes are retained
from the supplied project.

Validation:
PYTHONPATH=. python tests/test_sport_and_detail_update.py
python -m compileall -q app

Apply this full project ZIP over the existing Git root (no enclosing folder).
It excludes Git history, virtual environments, generated exports and credentials.
Back up your checkout before extracting. Review git diff before committing.
Changed files:
app/reports/aggregator.py
app/services/outlet_detail_export.py
app/bot/handlers.py
app/bot/run_bot.py
tests/test_sport_and_detail_update.py
SPORT_DETAIL_UPDATE.md

Live Kobo, Telegram, Railway and paid/API-key geocoding were not exercised here.
