"""Stage only the reviewed V161 files, never exports, databases or secrets."""
from pathlib import Path
import json
import subprocess
ROOT = Path(__file__).resolve().parents[1]
paths = json.loads((ROOT/'V161_CHANGED_FILES.json').read_text(encoding='utf-8'))
missing=[p for p in paths if not (ROOT/p).is_file()]
if missing:
    raise SystemExit('Missing update files: '+', '.join(missing))
subprocess.run(['git','add','--',*paths],cwd=ROOT,check=True)
print(f'Staged {len(paths)} V161 files. Review with git diff --cached --stat.')
