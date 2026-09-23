"""Run inside the Railway app container: python -m scripts.sync_power_bi --rebuild."""
import argparse
import json
from app.kobo.sync import sync_kobo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rebuild', action='store_true', help='Rebuild unchanged rows and product mappings on first run after an update.')
    args = parser.parse_args()
    try:
        result = sync_kobo(full_history=True, force=args.rebuild, wait_if_running=False)
    except Exception as exc:
        from app.db.database import SessionLocal
        from app.db.models import SyncLog
        try:
            with SessionLocal() as db:
                db.add(SyncLog(source="kobo_bi_full", status="failed",
                               message=f"Full sync failed: {type(exc).__name__}. Check worker logs."))
                db.commit()
        except Exception:
            pass
        raise

    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    audit = result.get('audit')
    if not audit:
        raise SystemExit('Sync did not run; another sync may be active. Retry after it finishes.')
    if result['skipped'] or audit['missing_source_ids']:
        raise SystemExit('Sync has missing/rejected records. Review output before refreshing BI.')
    if audit['database_only_ids']:
        print('Database contains IDs absent from this Kobo response. No records were deleted; investigate deleted submissions or a changed asset.')


if __name__ == '__main__':
    main()
