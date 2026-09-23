"""Upload and redeploy the existing Kobo XLSForm from the local checkout."""
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
FORM = ROOT / 'templates' / 'KB_Market_Improvement_XLSForm_GT_HORECA.xlsx'


def config():
    # A local .env is never uploaded to Git. Shell variables take precedence.
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    base = os.getenv('KOBO_BASE_URL', 'https://kf.kobotoolbox.org').rstrip('/')
    token = os.getenv('KOBO_TOKEN', '').strip()
    uid = os.getenv('KOBO_ASSET_UID', '').strip()
    if not token or not uid or token.startswith('replace_') or uid.startswith('replace_'):
        raise ValueError('Set KOBO_TOKEN and KOBO_ASSET_UID in local .env or environment.')
    if not base.startswith('https://') or '/' in base[8:] or not uid.replace('-', '').isalnum():
        raise ValueError('Invalid KOBO_BASE_URL or KOBO_ASSET_UID.')
    return base, token, uid


def checked(response):
    response.raise_for_status()
    return response.json()


def deploy(session, base, uid, form=FORM, timeout=150, pause=time.sleep):
    if not form.is_file():
        raise FileNotFoundError(form)
    asset_url = f'{base}/api/v2/assets/{uid}/'
    original = checked(session.get(asset_url, timeout=30))
    old_version = original.get('version_id')
    if original.get('uid') != uid or not old_version:
        raise RuntimeError('Could not verify the existing Kobo asset and its version.')
    with form.open('rb') as handle:
        imported = checked(session.post(
            f'{base}/api/v2/imports/',
            data={'destination': asset_url},
            files={'file': (form.name, handle,
                            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
            timeout=60,
        ))
    job_url = imported.get('url')
    if not job_url or not job_url.startswith(f'{base}/api/v2/imports/'):
        raise RuntimeError('Kobo did not return a valid import job; deployment was skipped.')
    deadline = time.monotonic() + timeout
    version = None
    while time.monotonic() < deadline:
        job = checked(session.get(job_url, timeout=30))
        status = str(job.get('status', '')).lower()
        messages = job.get('messages') or {}
        if status in ('error', 'failed', 'failure') or (isinstance(messages, dict) and messages.get('error')):
            raise RuntimeError(f'Kobo import failed: {job.get("messages", status)}')
        asset = checked(session.get(asset_url, timeout=30))
        if asset.get('version_id') != old_version and asset.get('uid') == uid:
            version = asset['version_id']
            break
        pause(2)
    if not version:
        raise TimeoutError('Kobo import did not create a new asset version; deployment was skipped.')
    checked(session.patch(f'{asset_url}deployment/',
                          data={'active': 'true', 'version_id': version}, timeout=60))
    while time.monotonic() < deadline:
        asset = checked(session.get(asset_url, timeout=30))
        if asset.get('deployed_version_id') == version and asset.get('deployment__active') is True:
            return version
        pause(2)
    raise TimeoutError('Kobo did not confirm the new deployed version; check the Kobo project.')


def main():
    try:
        base, token, uid = config()
        import requests
        session = requests.Session()
        session.headers.update({'Authorization': f'Token {token}'})
        version = deploy(session, base, uid)
        print(f'Kobo form uploaded and redeployed: asset {uid}, version {version}')
    except Exception as error:
        print(f'Kobo update failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
