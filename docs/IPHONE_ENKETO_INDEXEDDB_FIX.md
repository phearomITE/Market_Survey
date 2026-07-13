# iPhone KoBo/Enketo IndexedDB Error

Error message:

`Failed to execute 'transaction' on 'IDBDatabase': The database connection is closing.`

This is a browser-side KoBo/Enketo IndexedDB problem. It happens before the data reaches KoBo and before this Python bot can sync it.

## What this project update does

- Adds Channel Specialist outlet types to the Kobo XLSForm.
- Supports Channel Specialist report headers in Excel/PNG output.
- Keeps General Trade report headers for normal outlets.
- Keeps auto-sync and report generation stable after the form is successfully submitted to KoBo.

## What bot code cannot fix

Bot code cannot stop the iPhone browser from closing IndexedDB while the form is open. The bot only sees submissions after KoBo accepts them.

## Operational fixes for iPhone users

1. Use a stable connection before tapping Submit.
2. Do not switch apps while filling the form.
3. Close old KoBo tabs before opening a new submission.
4. Clear website data for `ee.kobotoolbox.org` if one device repeatedly fails.
5. Submit immediately after completing the form; do not leave drafts open for a long time.
6. For large daily operations, use Android + KoBoCollect or a custom Flutter app for iPhone/Android.

## Production recommendation

For 70 daily sales representatives, use this backend as the reporting system and plan a native mobile app or Power Apps if iPhone browser reliability remains a problem.
