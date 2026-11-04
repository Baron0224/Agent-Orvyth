import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from chat_web import ChatServer

class TraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'README.md').write_text('hello',encoding='utf-8')
        self.server=ChatServer(port=0,db_path=self.root/'browser.sqlite3')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        state,headers=self.request('GET','/api/session');self.chat=state['active_chat'];self.cookie=headers['Set-Cookie'].split(';')[0]
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,method,path,data=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        headers={'Origin':self.server.origin,'Cookie':getattr(self,'cookie','')}
        body=None
        if data is not None:body=json.dumps(data).encode();headers['Content-Type']='application/json'
        try:
            connection.request(method,path,body,headers);response=connection.getresponse();raw=response.read().decode()
            self.assertEqual(response.status,200,raw)
            return ([json.loads(l) for l in raw.splitlines()] if 'ndjson' in response.getheader('Content-Type') else json.loads(raw)),dict(response.getheaders())
        finally:connection.close()
    def run_task(self,events):
        plan={'folder':str(self.root),'task':'读取README.md','only_file':'README.md'}
        with patch('chat_web.file_request',return_value=plan),patch('chat_web.run_project',return_value=(e for e in events)):
            return self.request('POST','/api/chat',{'chat_id':self.chat,'message':'读取README.md'})[0]
    def test_trace_survives_restart_and_has_real_path(self):
        result=self.run_task([{'type':'tool','name':'read_project','path':'README.md'},{'type':'delta','content':'hello'},{'type':'done'}])
        self.assertEqual(result[-1]['type'],'done')
        state=self.request('GET','/api/session')[0];trace=state['messages'][-1]['task_trace']
        self.assertEqual(trace['state'],'completed');self.assertEqual(trace['steps'][2]['path'],str(self.root/'README.md'))
        from browser_store import Store
        _,owner=self.server.store.owner(self.cookie.split('=',1)[1])
        self.assertEqual(Store(self.root/'browser.sqlite3').state(owner)['messages'][-1]['task_trace'],trace)
    def test_model_claim_before_error_is_not_saved_as_success(self):
        result=self.run_task([{'type':'delta','content':'我已经完成了所有修改'},{'type':'error','message':'文件不存在'}])
        answer=''.join(e['content'] for e in result if e['type']=='delta')
        self.assertNotIn('完成了所有修改',answer);self.assertIn('文件不存在',answer)
        self.assertEqual(self.request('GET','/api/session')[0]['messages'][-1]['task_trace']['state'],'failed')
    def test_missing_done_and_missing_artifact_fail_verification(self):
        for events in ([{'type':'delta','content':'done'}], [{'type':'tool','name':'replace_word_text','path':'missing.docx'},{'type':'delta','content':'done'},{'type':'done'}]):
            result=self.run_task(events)
            trace=[e['task'] for e in result if e['type']=='task'][-1]
            self.assertEqual(trace['state'],'failed')
    def test_existing_text_file_is_preserved_and_failure_recorded(self):
        target=self.root/'hello.txt';target.write_text('original',encoding='utf-8')
        with patch('chat_web.file_request',return_value={'write':{'name':'hello.txt','content':'new'}}),patch('file_write.desktop_folder',return_value=self.root):
            result=self.request('POST','/api/chat',{'chat_id':self.chat,'message':'新建文本'})[0]
        self.assertEqual(target.read_text(encoding='utf-8'),'original')
        self.assertEqual([e['task'] for e in result if e['type']=='task'][-1]['state'],'failed')
        self.assertIn('没有覆盖',self.request('GET','/api/session')[0]['messages'][-1]['content'])

if __name__=='__main__':unittest.main()
