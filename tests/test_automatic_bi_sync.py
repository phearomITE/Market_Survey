from threading import Event
from app.services.automatic_bi_sync import AutomaticBISync


def test_starts_immediately_and_retries_without_overlap():
    done = Event()
    calls = []
    def cycle():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("temporary failure")
        done.set()
    service = AutomaticBISync(run_cycle=cycle, interval_seconds=60)
    service.interval = 0.01
    service.start()
    original_thread = service.thread
    service.start()
    assert service.thread is original_thread
    assert done.wait(2)
    service.stop()
    assert not service.thread.is_alive()
    assert len(calls) >= 2


def test_web_startup_and_shutdown_manage_sync(monkeypatch):
    from unittest.mock import MagicMock, patch
    from app import main
    monkeypatch.delenv("POWER_BI_AUTO_SYNC_ENABLED", raising=False)
    service = MagicMock()
    with patch.object(main, "init_db"), patch(
        "app.services.automatic_bi_sync.AutomaticBISync", return_value=service
    ):
        main.startup()
        service.start.assert_called_once()
        main.shutdown()
        service.stop.assert_called_once()
    del main.app.state.bi_sync
    monkeypatch.setenv("POWER_BI_AUTO_SYNC_ENABLED", "false")
    with patch.object(main, "init_db"), patch(
        "app.services.automatic_bi_sync.AutomaticBISync"
    ) as constructor:
        main.startup()
        constructor.assert_not_called()
