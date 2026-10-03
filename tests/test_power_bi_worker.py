from unittest.mock import MagicMock, patch
from scripts import power_bi_worker as worker


def test_worker_lock_and_success():
    lock=MagicMock(); lock.scalar.return_value=True
    with patch.object(worker.engine,'connect') as connect, patch.object(worker,'sync_kobo') as sync:
        connect.return_value.__enter__.return_value=lock
        sync.return_value={'audit':{'missing_source_ids':0},'skipped':0,'fetched':2,'synced':1,'unchanged':1}
        worker.run_once()
        sync.assert_called_once_with(full_history=True,force=False,wait_if_running=False)
        assert 'pg_advisory_unlock' in str(lock.execute.call_args.args[0])
        lock.scalar.return_value=False;sync.reset_mock()
        worker.run_once();sync.assert_not_called()


def test_worker_failure_records_status_and_unlocks():
    lock=MagicMock();lock.scalar.return_value=True
    with patch.object(worker.engine,'connect') as connect, patch.object(worker,'sync_kobo',side_effect=RuntimeError('failed')), patch.object(worker,'SessionLocal') as factory:
        connect.return_value.__enter__.return_value=lock
        worker.run_once()
        saved=factory.return_value.__enter__.return_value.add.call_args.args[0]
        assert saved.status=='failed' and saved.source=='kobo_bi_full'
        assert 'pg_advisory_unlock' in str(lock.execute.call_args.args[0])
