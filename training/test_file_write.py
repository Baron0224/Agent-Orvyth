from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from file_write import write_request,create_text_file
from file_chat import file_request
import json
import threading
import urllib.request

class FileWriteTests(unittest.TestCase):
    def test_screenshot_request_creates_exact_content(self):
        question='你能在桌面上创建一个文档名字叫你好的文档文档里面写入我爱你吗'
        plan=file_request(question,[])
        self.assertEqual(plan,{'write':{'name':'你好的文档.txt','content':'我爱你'}})
        with tempfile.TemporaryDirectory() as base,patch('file_write.desktop_folder',return_value=Path(base)):
            reply=create_text_file(plan['write'])
            self.assertIn('已经在桌面创建',reply)
            self.assertEqual((Path(base)/'你好的文档.txt').read_text(encoding='utf-8'),'我爱你')
            self.assertIn('没有覆盖',create_text_file({'name':'你好的文档.txt','content':'changed'}))
            self.assertEqual((Path(base)/'你好的文档.txt').read_text(encoding='utf-8'),'我爱你')

    def test_quoted_literal_question_mark_is_preserved(self):
        self.assertEqual(write_request('在桌面新建文档，名字叫“问候”，内容是“你好吗？”')['write']['content'],'你好吗？')

    def test_unsafe_names_and_missing_fields_do_not_write(self):
        for name in ('../escape','CON','run.ps1'):
            self.assertIn('reply',write_request(f'在桌面新建文档，名字叫“{name}”，内容是“hello”'))
        self.assertIn('reply',write_request('在桌面创建文档'))
        self.assertIsNone(write_request('给我写一封情书'))
        self.assertIn('先不',write_request('不要在桌面创建文件')['reply'])

    def test_http_chat_creates_file_and_persists_truthful_reply(self):
        from chat_web import ChatServer
        with tempfile.TemporaryDirectory() as base:
            desktop=Path(base)/'Desktop';desktop.mkdir()
            server=ChatServer(port=0,db_path=Path(base)/'browser.sqlite3')
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            try:
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(server.origin+'/api/session') as response:
                    cookie=response.headers['Set-Cookie'].split(';')[0];state=json.load(response)
                payload={'chat_id':state['active_chat'],'message':'你能在桌面上创建一个文档名字叫你好的文档文档里面写入我爱你吗'}
                request=urllib.request.Request(server.origin+'/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Origin':server.origin,'Cookie':cookie})
                with patch('file_write.desktop_folder',return_value=desktop),patch('chat_web.LocalChat.reply',side_effect=AssertionError('must use file creation tool')):
                    with opener.open(request) as response:
                        events=[json.loads(line) for line in response]
                self.assertEqual(events[-1]['type'],'done')
                answer=next(e['content'] for e in events if e['type']=='delta')
                self.assertIn('已经在桌面创建',answer)
                self.assertEqual((desktop/'你好的文档.txt').read_text(encoding='utf-8'),'我爱你')
                with opener.open(urllib.request.Request(server.origin+'/api/session',headers={'Cookie':cookie})) as response:
                    saved=json.load(response)['messages'][-1]
                    self.assertEqual(saved['content'],answer)
                    self.assertEqual(saved['task_trace']['state'],'completed')
            finally:
                server.shutdown();server.server_close();worker.join()

if __name__=='__main__': unittest.main()
