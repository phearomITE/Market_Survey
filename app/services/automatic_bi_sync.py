"""Start the existing BI worker within the web application's lifecycle."""
import logging
import os
from threading import Event, Thread

log = logging.getLogger(__name__)


class AutomaticBISync:
    def __init__(self, run_cycle=None, interval_seconds=None):
        if run_cycle is None:
            from scripts.power_bi_worker import run_once
            run_cycle = run_once
        self.run_cycle = run_cycle
        self.interval = max(60, int(
            interval_seconds if interval_seconds is not None
            else os.getenv("POWER_BI_SYNC_INTERVAL_SECONDS", "300")
        ))
        self.stop_event = Event()
        self.thread = None

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = Thread(target=self._loop, name="automatic-bi-sync", daemon=True)
        self.thread.start()
        log.info("Automatic BI sync started; retry interval %s seconds.", self.interval)

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                self.run_cycle()
            except Exception as exc:
                log.error("Automatic BI cycle failed (%s); will retry.", type(exc).__name__)
            self.stop_event.wait(self.interval)

    def stop(self):
        self.stop_event.set()
        # Do not hold up server shutdown for a long network/database operation.
        # Committed batches are retained; the next startup resumes by source hash.
        if self.thread is not None:
            self.thread.join(timeout=2)
