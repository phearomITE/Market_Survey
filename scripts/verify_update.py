"""Run the repaired workflows in separate processes to isolate legacy test stubs."""
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
TESTS = [
 'test_project_integration.py', 'test_export_status_command.py',
 'test_product_ord_update.py', 'test_summary_outlet_variants.py',
 'test_ord_guidance_rotation.py', 'test_kobo_direct_deploy.py',
 'test_v158_khmer_png_shaping.py', 'test_v84_gt_horeca_commands.py',
 'test_v38_multi_dealer_report.py', 'test_v39_railway_config.py',
 'test_v92_export_commands_summary.py', 'test_v104_daily_exports.py',
 'test_v150_export_status_map_runtime.py',
]
def main():
    import compileall
    import os
    import tempfile
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='Run every test module, including historical tests')
    args = parser.parse_args()
    if not all(compileall.compile_dir(str(ROOT / folder), quiet=1) for folder in ('app', 'scripts')):
        return 1
    tests = sorted(p.name for p in (ROOT / 'tests').glob('test_*.py')) if args.all else TESTS
    # exports is already excluded from Docker and contains generated files only.
    temp_parent = ROOT / 'exports' / 'verification'
    temp_parent.mkdir(parents=True, exist_ok=True)
    failed = []
    with tempfile.TemporaryDirectory(prefix='run-', dir=temp_parent) as run_dir:
        run_path = Path(run_dir).resolve()
        env = os.environ.copy()
        for key in ('TEMP', 'TMP', 'TMPDIR'):
            env[key] = str(run_path)
        env['PYTHONUTF8'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        for index, name in enumerate(tests):
            # A unique empty path is safe for pytest's basetemp cleanup.
            base = run_path / f'pytest-{index}'
            command = [sys.executable, '-m', 'pytest', '-q',
                       '--basetemp', str(base), str(ROOT / 'tests' / name)]
            try:
                result = subprocess.run(command, cwd=ROOT, env=env)
            except OSError as exc:
                print(f'Cannot launch Python: {sys.executable}: {exc}')
                return 1
            if result.returncode:
                failed.append(name)
    if failed:
        print('Failed checks: ' + ', '.join(failed))
    else:
        scope = 'All test modules' if args.all else 'All focused update checks'
        print(scope + ' passed. Live deployment still requires verification.')
    return int(bool(failed))


if __name__ == '__main__':
    sys.exit(main())
