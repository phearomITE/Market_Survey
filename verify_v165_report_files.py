"""Run the real /report handler: two files, no PNG, clear partial failures."""
import ast,asyncio,tempfile
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent
node=next(n for n in ast.parse((ROOT/'app/bot/handlers.py').read_text(encoding='utf-8')).body if isinstance(n,ast.AsyncFunctionDef) and n.name=='report_cmd')
async def test():
    with tempfile.TemporaryDirectory() as temp:
        xlsx=Path(temp)/'report.xlsx';xlsx.write_bytes(b'xlsx')
        pdf=Path(temp)/'report.pdf';pdf.write_bytes(b'%PDF-1.4\n')
        calls=[]
        def generate(dealer,day,scope):calls.append(('generate',dealer,day,scope));return xlsx,'Generated'
        async def fast(fn,*args,**kwargs):return fn(*args)
        async def sync(message):pass
        class Message:
            def __init__(self):self.files=[];self.messages=[]
            async def reply_text(self,text):self.messages.append(text);return self
            async def edit_text(self,text):self.messages.append(text)
            async def reply_document(self,document,**kwargs):self.files.append(document)
        def render(path):calls.append(('pdf',path));return pdf
        env={'Update':object,'ContextTypes':SimpleNamespace(DEFAULT_TYPE=object),
            'parse_report_command_args':lambda args:('KRG7','2026-11-07','GT'),
            '_maybe_sync_before_report':sync,'_run_fast':fast,'generate_dealer_report':generate,
            'excel_to_pdf':render,'InputFile':lambda f,filename:filename,'monotonic':lambda:0,
            'settings':SimpleNamespace(png_render_timeout_seconds=18)}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'actual report handler','exec'),env)
        message=Message();context=SimpleNamespace(args=['KRG7','GT','2026-11-07'])
        await env['report_cmd'](SimpleNamespace(effective_message=message),context)
        assert message.files==['report.xlsx','report.pdf'],message.files
        assert calls==[('generate','KRG7','2026-11-07','GT'),('pdf',xlsx)]
        assert 'Excel + PDF sent' in message.messages[-1]
        env['excel_to_pdf']=lambda p:None
        message=Message();await env['report_cmd'](SimpleNamespace(effective_message=message),context)
        assert message.files==['report.xlsx'] and 'PDF conversion failed' in message.messages[-1]
        def timeout(p):raise TimeoutError()
        env['excel_to_pdf']=timeout
        message=Message();await env['report_cmd'](SimpleNamespace(effective_message=message),context)
        assert message.files==['report.xlsx'] and 'PDF conversion failed' in message.messages[-1]
        env['generate_dealer_report']=lambda *a:(None,'No matching submissions')
        message=Message();await env['report_cmd'](SimpleNamespace(effective_message=message),context)
        assert not message.files and 'No matching submissions' in message.messages[-1]
asyncio.run(test())
print('V165 OK: /report sends Excel + PDF in order; never renders PNG; converter failure/timeout and missing-data cases handled.')
