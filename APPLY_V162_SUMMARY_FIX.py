"""Repair only the extra /summary argument and Windows verifier encoding."""
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def repair(path):
    source=path.read_text(encoding='utf-8')
    tree=ast.parse(source)
    summary=next((n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='summary_cmd'),None)
    if summary is None:
        raise SystemExit(f'Cannot find summary_cmd in {path}; no change made.')
    bad_lines=[]
    for node in ast.walk(summary):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='_run_fast':
            if node.args and isinstance(node.args[0],ast.Name) and node.args[0].id=='generate_region_dealer_summary':
                for arg in node.args[1:]:
                    if isinstance(arg,ast.Name) and arg.id=='generate_summary_volume_date':
                        if arg.lineno != arg.end_lineno:
                            raise SystemExit('Unexpected call layout; no change made.')
                        bad_lines.append(arg.lineno-1)
    if bad_lines:
        lines=source.splitlines(keepends=True)
        for index in sorted(set(bad_lines),reverse=True):
            if lines[index].strip()!='generate_summary_volume_date,':
                raise SystemExit('Unexpected call line; no change made.')
            del lines[index]
        updated=''.join(lines);ast.parse(updated)
        backup=path.with_suffix('.py.pre_v162.bak')
        if not backup.exists():backup.write_text(source,encoding='utf-8')
        path.write_text(updated,encoding='utf-8')
        print('Fixed:',path.relative_to(ROOT))
    else:
        print('Already correct:',path.relative_to(ROOT))

for base in [ROOT,ROOT/'Market_Survey_Ready',ROOT/'Market_Survey_Ready/Market_Survey']:
    handler=base/'app/bot/handlers.py'
    if handler.is_file():repair(handler)
    verifier=base/'verify_v161_volume_summary.py'
    if verifier.is_file():
        source=verifier.read_text(encoding='utf-8')
        updated=source.replace('.read_text()',".read_text(encoding='utf-8')")
        if updated!=source:
            ast.parse(updated);verifier.write_text(updated,encoding='utf-8')
            print('Fixed UTF-8:',verifier.relative_to(ROOT))
print('Run: python -X utf8 verify_v162_summary_handler.py')
