"""Exercise the real Telegram handlers without Telegram/network/DB dependencies."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import tempfile

ROOT=Path(__file__).resolve().parent
source=(ROOT/'app/bot/handlers.py').read_text(encoding='utf-8')
tree=ast.parse(source)
handlers=[n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name in {'summary_cmd','summary_volume_date_cmd'}]
# Remove only the runtime infrastructure import in the volume handler.
for fn in handlers:
    fn.body=[n for n in fn.body if not isinstance(n,ast.ImportFrom)]
class Message:
    def __init__(self):self.messages=[];self.documents=[]
    async def reply_text(self,text):self.messages.append(text);return self
    async def edit_text(self,text):self.messages.append(text)
    async def reply_document(self,**kwargs):self.documents.append(kwargs)
async def exercise():
    with tempfile.TemporaryDirectory() as temp:
        report=Path(temp)/'summary.xlsx';report.write_bytes(b'offline-upload-fixture')
        calls=[]
        def generate_region_dealer_summary(report_type='GT',report_date_str=None):
            calls.append(('summary',report_type,report_date_str));return report,'Generated summary'
        def generate_summary_volume_date(report_date_str,report_type='ALL'):
            calls.append(('volume',report_type,report_date_str));return report,'Generated volume'
        async def run_fast(function,*args,**kwargs):
            assert kwargs=={'timeout_seconds':50}
            return function(*args)  # exercises the service signature, not just syntax
        async def maybe_sync(message):pass
        volume_tree=ast.parse((ROOT/'app/reports/volume_summary.py').read_text(encoding='utf-8'))
        parse=next(n for n in volume_tree.body if isinstance(n,ast.FunctionDef) and n.name=='parse_volume_args')
        from datetime import datetime
        env={'datetime':datetime};exec(compile(ast.Module(body=[parse],type_ignores=[]),'parse','exec'),env)
        env.update({'Update':object,'ContextTypes':SimpleNamespace(DEFAULT_TYPE=object),
            'InputFile':lambda f,filename:(filename,f.read()),'_run_fast':run_fast,
            '_maybe_sync_before_report':maybe_sync,
            'generate_region_dealer_summary':generate_region_dealer_summary,
            'generate_summary_volume_date':generate_summary_volume_date})
        exec(compile(ast.Module(body=handlers,type_ignores=[]),'production handlers','exec'),env)
        for scope in ['GT','HORECA']:
            message=Message()
            await env['summary_cmd'](SimpleNamespace(effective_message=message),SimpleNamespace(args=[scope,'2026-10-03']))
            assert calls[-1]==('summary',scope,'2026-10-03')
            assert len(message.documents)==1 and not any('failed' in s for s in message.messages),message.messages
        for args in [['2026-11-04'],['GT','2026-11-04']]:
            message=Message()
            await env['summary_volume_date_cmd'](SimpleNamespace(effective_message=message),SimpleNamespace(args=args))
            assert calls[-1]==('volume','ALL' if len(args)==1 else 'GT','2026-11-04')
            assert len(message.documents)==1
        message=Message();before=len(calls)
        await env['summary_cmd'](SimpleNamespace(effective_message=message),SimpleNamespace(args=['BAD','2026-10-03']))
        assert len(calls)==before and not message.documents
asyncio.run(exercise())
print('V162 OK: actual GT/HORECA summary and volume handlers invoke correct two-argument services and upload results; invalid type rejected.')
