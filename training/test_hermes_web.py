import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from chat_web import ChatServer

class HermesWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'browser.sqlite3'
        self.start()
        data,headers=self.request('GET','/api/session')
        self.cookie=headers['Set-Cookie'].split(';')[0];self.chat=data['active_chat']

    def start(self):
        self.server=ChatServer(port=0,db_path=self.path)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def tearDown(self):self.stop();self.tmp.cleanup()

    def request(self,method,path,data=None,cookie=None):
        headers={'Origin':self.server.origin,'Cookie':getattr(self,'cookie','') if cookie is None else cookie}
        body=None
        if data is not None:body=json.dumps(data).encode();headers['Content-Type']='application/json'
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            connection.request(method,path,body,headers);response=connection.getresponse()
            text=response.read().decode();self.assertEqual(response.status,200,text)
            parsed=[json.loads(l) for l in text.splitlines()] if 'ndjson' in response.getheader('Content-Type') else json.loads(text)
            return parsed,dict(response.getheaders())
        finally:connection.close()

    def send(self,text):return self.request('POST','/api/chat',{'chat_id':self.chat,'message':text})[0]

    def test_cross_chat_restart_prompt_isolation_and_deletion(self):
        with patch('chat_web.LocalChat.reply',side_effect=AssertionError('explicit memory must not use model')):
            events=self.send('记住：我的项目代号是青松42，回答尽量简短')
        self.assertEqual(events[-1]['type'],'done')
        self.assertIn('记住了',events[0]['content'])
        self.stop();self.start()
        self.chat=self.request('POST','/api/chats/new',{})[0]['active_chat']
        prompts=[]
        def fake(chat,question):prompts.append(chat.system_prompt);yield '测试回答'
        with patch('chat_web.LocalChat.reply',fake),patch('chat_web.lookup',side_effect=AssertionError('personal recall must stay local')):
            self.send('我的项目代号是什么')
        self.assertIn('青松42',prompts[-1])
        with patch('chat_web.LocalChat.reply',fake):self.send('忘记第1条')
        with patch('chat_web.LocalChat.reply',fake),patch('chat_web.should_search',return_value=False):self.send('再说句话')
        self.assertNotIn('青松42',prompts[-1])
        # Distinct browser owners never share memory, even on one database.
        self.send('记住：我的代号是海鸥77')
        other,headers=self.request('GET','/api/session',cookie='')
        self.cookie=headers['Set-Cookie'].split(';')[0];self.chat=other['active_chat']
        self.assertNotIn('海鸥77',self.send('查看记忆')[0]['content'])

if __name__=='__main__':unittest.main()
