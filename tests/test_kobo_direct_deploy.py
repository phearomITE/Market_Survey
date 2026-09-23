import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock

from scripts.deploy_kobo_form import deploy

BASE = 'https://kf.kobotoolbox.org'
ASSET = f'{BASE}/api/v2/assets/abc123/'
JOB = f'{BASE}/api/v2/imports/job1/'


def reply(data):
    response = Mock()
    response.json.return_value = data
    return response


class KoboDirectDeployTests(TestCase):
    def test_uploads_to_existing_asset_and_verifies_redeployment(self):
        session = Mock()
        session.get.side_effect = [
            reply({'uid': 'abc123', 'version_id': 'old'}),
            reply({'status': 'processing'}),
            reply({'uid': 'abc123', 'version_id': 'new'}),
            reply({'uid': 'abc123', 'version_id': 'new',
                   'deployed_version_id': 'new', 'deployment__active': True}),
        ]
        session.post.return_value = reply({'url': JOB})
        session.patch.return_value = reply({'active': True})
        with tempfile.TemporaryDirectory() as directory:
            form = Path(directory) / 'form.xlsx'
            form.write_bytes(b'form')
            self.assertEqual(deploy(session, BASE, 'abc123', form, pause=lambda _: None), 'new')
        self.assertEqual(session.post.call_args.kwargs['data']['destination'], ASSET)
        self.assertEqual(session.patch.call_args.kwargs['data']['version_id'], 'new')
        self.assertEqual(session.patch.call_args.args[0], ASSET + 'deployment/')

    def test_does_not_deploy_when_import_fails(self):
        session = Mock()
        session.get.side_effect = [reply({'uid': 'abc123', 'version_id': 'old'}),
                                   reply({'status': 'error', 'messages': {'error': 'bad XLSForm'}})]
        session.post.return_value = reply({'url': JOB})
        with tempfile.TemporaryDirectory() as directory:
            form = Path(directory) / 'form.xlsx'
            form.write_bytes(b'form')
            with self.assertRaisesRegex(RuntimeError, 'bad XLSForm'):
                deploy(session, BASE, 'abc123', form, pause=lambda _: None)
        session.patch.assert_not_called()
