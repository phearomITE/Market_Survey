"""Separate Railway service: python -u -m scripts.power_bi_worker"""
import logging
import os
import signal
from threading import Event
from sqlalchemy import text
from app.db.database import engine, SessionLocal
from app.db.models import SyncLog
from app.kobo.sync import sync_kobo

log = logging.getLogger('power_bi_worker')
stop = Event()


def run_once():
    # Prevent duplicate BI worker replicas from running simultaneously.
    with engine.connect() as lock:
        acquired = lock.scalar(text('SELECT pg_try_advisory_lock(742019031)'))
        lock.commit()
        if not acquired:
            log.info('Another BI worker owns the sync lock; skipping this cycle.')
            return
        try:
            result = sync_kobo(full_history=True, force=False, wait_if_running=False)
            if not result.get('audit'):
                log.warning('Sync did not start: another sync is running.')
            elif result.get('skipped') or result['audit']['missing_source_ids']:
                log.warning('BI sync incomplete; inspect sync_status.')
            else:
                log.info('BI sync complete: fetched=%s changed=%s unchanged=%s',
                         result['fetched'],result['synced'],result['unchanged'])
        except Exception as exc:
            log.error('BI sync failed (%s). Retrying next cycle.', type(exc).__name__)
            try:
                with SessionLocal() as db:
                    db.add(SyncLog(source='kobo_bi_full', status='failed',
                                   message=f'Automatic BI sync failed: {type(exc).__name__}. See worker logs.'))
                    db.commit()
            except Exception:
                log.error('Could not store sync failure status.')
        finally:
            lock.execute(text('SELECT pg_advisory_unlock(742019031)'))
            lock.commit()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
    interval = max(60, int(os.getenv('POWER_BI_SYNC_INTERVAL_SECONDS','300')))
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            run_once()
        except Exception as exc:
            log.error('Worker cycle failed (%s); retrying.', type(exc).__name__)
        stop.wait(interval)


if __name__ == '__main__':
    main()
