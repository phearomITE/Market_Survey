"""Stage the reviewed update only; never stage unrelated deleted files or exports."""
import json, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
paths=json.loads((root/'V164_CHANGED_FILES.json').read_text(encoding='utf-8'))
missing=[p for p in paths if not (root/p).is_file()]
if missing:raise SystemExit('Missing update files: '+', '.join(missing))
subprocess.run(['git','add','--',*paths],cwd=root,check=True)
print('V164 files staged. Review: git diff --cached --stat')
