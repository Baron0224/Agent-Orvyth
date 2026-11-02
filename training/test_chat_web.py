"""本机持久记录、会话隔离、聊天与任务接口、流式失败的回归验证。"""
import base64
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from chat_web import ChatServer, WEB_PRIVACY, WEB_PROMPT
from chat_local import LocalChat, PRIVACY_NOTICE

PNG = 'data:image/png;base64,' + 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII='
def fake_reply(chat, question):
    yield '测试回答'
    if question == '模拟失败':
        raise RuntimeError('模型连接中断')

class WebChatTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'browser.sqlite3'
        self.start()
        _, headers, data = self.request('GET','/api/session')
        self.cookie = headers['Set-Cookie'].split(';')[0]
        self.chat = data['active_chat']
        self.assertEqual(data['messages'],[])
        self.assertIn('HttpOnly',headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',headers['Set-Cookie'])
    def start(self):
        self.server = ChatServer(port=0,db_path=self.path)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
    def tearDown(self):
        self.stop(); self.directory.cleanup()
    def request(self,method,path,payload=None,extra=None):
        headers={'Origin':self.server.origin}
        if hasattr(self,'cookie'): headers['Cookie']=self.cookie
        body=None
        if payload is not None:
            body=json.dumps(payload,ensure_ascii=False).encode('utf8'); headers['Content-Type']='application/json'
        headers.update(extra or {})
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            conn.request(method,path,body=body,headers=headers); response=conn.getresponse(); raw=response.read().decode()
            content=response.getheader('Content-Type','')
            data=[json.loads(line) for line in raw.splitlines()] if 'ndjson' in content else json.loads(raw) if 'json' in content else raw
            return response.status,dict(response.getheaders()),data
        finally: conn.close()
    def send(self,message='你好',chat=None):
        with patch('chat_web.LocalChat.reply',fake_reply):
            return self.request('POST','/api/chat',{'chat_id':chat or self.chat,'message':message})
    def state(self): return self.request('GET','/api/session')[2]
    def test_assets_host_origin_and_input_boundaries(self):
        self.assertEqual(self.request('GET','/')[0],200)
        self.assertEqual(self.request('GET','/../chat_local.py')[0],404)
        self.assertEqual(self.request('GET','/',extra={'Host':'untrusted.example'})[0],403)
        self.assertEqual(self.request('POST','/api/clear',{'chat_id':self.chat},{'Origin':'http://untrusted.example'})[0],403)
        for value in ['', ' ', None, 2, '字'*2001]:
            self.assertEqual(self.request('POST','/api/chat',{'chat_id':self.chat,'message':value})[0],400)
        self.assertEqual(self.request('POST','/api/chat',[])[0],400)
        self.assertEqual(self.request('POST','/api/chat',{}, {'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('POST','/api/chat',{'chat_id':[],'message':'hi'})[0],400)
        self.assertEqual(self.request('POST','/api/chats/new',{}, {'Cookie':''})[0],410)
    def test_particle_start_page_is_stateless_and_links_to_chat(self):
        status, headers, html = self.request('GET','/start')
        self.assertEqual(status,200)
        self.assertIn('Hi Boss',html)
        self.assertIn('href="/"',html)
        self.assertNotIn('<button',html)
        self.assertNotIn('Set-Cookie',headers)
        for path in ('/start.css','/start.js','/particle-field.js'):
            self.assertEqual(self.request('GET',path)[0],200)
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        try:
            conn.request('GET','/assets/particle-ribbon.png')
            response=conn.getresponse()
            self.assertEqual(response.status,200)
            self.assertEqual(response.getheader('Content-Type'),'image/png')
            self.assertTrue(response.read().startswith(b'\x89PNG\r\n\x1a\n'))
        finally:
            conn.close()
    def test_new_open_rename_clear_delete(self):
        _,_,events=self.send()
        self.assertEqual(events[-1]['type'],'done')
        old=self.chat
        self.assertEqual(len(self.state()['messages']),2)
        other=self.request('POST','/api/chats/new',{})[2]['active_chat']
        self.assertNotEqual(old,other)
        self.assertEqual(self.state()['messages'],[])
        opened=self.request('POST','/api/chats/open',{'chat_id':old})[2]
        self.assertEqual(len(opened['messages']),2)
        self.request('POST','/api/chats/rename',{'chat_id':old,'title':'我的项目'})
        self.send('第二个问题',old)
        self.assertEqual(next(c['title'] for c in self.state()['chats'] if c['id']==old),'我的项目')
        self.request('POST','/api/clear',{'chat_id':old})
        self.assertEqual(self.state()['messages'],[])
        self.request('POST','/api/chats/delete',{'chat_id':old})
        self.assertEqual(self.state()['active_chat'],other)
        self.request('POST','/api/chats/delete',{'chat_id':other})
        self.assertEqual(len(self.state()['chats']),1)
    def test_browser_owner_isolation(self):
        _, headers, other=self.request('GET','/api/session',extra={'Cookie':''})
        other_cookie=headers['Set-Cookie'].split(';')[0]
        self.send()
        self.assertEqual(self.request('GET','/api/session',extra={'Cookie':other_cookie})[2]['messages'],[])
        self.assertEqual(self.request('POST','/api/chats/open',{'chat_id':other['active_chat']})[0],404)
        task=self.request('POST','/api/tasks/add',{'title':'测试任务'})[2]['tasks'][0]
        self.assertEqual(self.request('POST','/api/tasks/delete',{'id':task['id']},{'Cookie':other_cookie})[0],404)
    def test_tasks_and_profile_survive_restart(self):
        data=self.request('POST','/api/tasks/add',{'title':'整理项目思路'})[2]
        task=data['tasks'][0]
        self.request('POST','/api/tasks/toggle',{'id':task['id'],'done':True})
        profile={'name':'测试空间','pet_name':'小团','pet_motion':False,'avatar':PNG}
        self.assertEqual(self.request('POST','/api/profile',profile)[0],200)
        self.send('重启之后还要在')
        self.stop(); self.start()
        data=self.state()
        self.assertEqual(data['profile'],profile)
        self.assertEqual(data['tasks'][0]['done'],1)
        self.assertEqual(data['messages'][0]['content'],'重启之后还要在')
        self.request('POST','/api/tasks/toggle',{'id':task['id'],'done':False})
        self.assertEqual(self.state()['tasks'][0]['done'],0)
        self.request('POST','/api/tasks/delete',{'id':task['id']})
        self.assertEqual(self.state()['tasks'],[])
    def test_invalid_profile_and_tasks_do_not_overwrite(self):
        profile=self.state()['profile']
        for data in [{**profile,'name':''},{**profile,'pet_motion':'yes'},{**profile,'avatar':'data:image/svg+xml;base64,PHN2Zz4='},{**profile,'avatar':PNG+'!'}]:
            self.assertEqual(self.request('POST','/api/profile',data)[0],400)
        self.assertEqual(self.state()['profile'],profile)
        self.assertEqual(self.request('POST','/api/tasks/add',{'title':'x'*161})[0],400)
        self.assertEqual(self.request('POST','/api/tasks/toggle',{'id':[]})[0],400)
    def test_busy_chat_does_not_block_tasks(self):
        with self.server.chat_lock(self.chat):
            self.assertEqual(self.request('POST','/api/clear',{'chat_id':self.chat})[0],409)
        with self.server.generation_lock:
            self.assertEqual(self.request('POST','/api/chat',{'chat_id':self.chat,'message':'hi'})[0],503)
            self.assertEqual(self.request('POST','/api/tasks/add',{'title':'仍能记任务'})[0],200)
    def test_failed_stream_not_saved(self):
        _,_,events=self.send('模拟失败')
        self.assertEqual(events[-1]['type'],'error')
        self.assertEqual(self.state()['messages'],[])
        self.assertFalse(self.server.generation_lock.locked())
    def test_archive_is_full_but_model_context_bounded(self):
        for i in range(10): self.send(str(i))
        self.assertEqual(len(self.state()['messages']),20)
        _,owner=self.server.store.owner(self.cookie.split('=',1)[1])
        self.assertEqual(len(self.server.store.history(owner,self.chat)),16)
    def test_web_privacy_is_persistent_and_cli_is_still_temporary(self):
        with patch('chat_local.urllib.request.build_opener',side_effect=AssertionError('should not call model')):
            web=LocalChat(system_prompt=WEB_PROMPT,privacy_notice=WEB_PRIVACY)
            self.assertEqual(''.join(web.reply('/privacy')),WEB_PRIVACY)
            self.assertEqual(''.join(LocalChat().reply('/privacy')),PRIVACY_NOTICE)
        self.assertNotIn('退出本聊天程序会丢失',WEB_PROMPT)
        self.assertIn('数据库',self.state()['privacy'])
    def test_legacy_cookie_keeps_existing_profile_after_rename(self):
        self.send('旧版本保存的消息')
        legacy_cookie = 'openagent_session=' + self.cookie.split('=',1)[1]
        status, headers, data = self.request('GET','/api/session',extra={'Cookie':legacy_cookie})
        self.assertEqual(status,200)
        self.assertEqual(data['active_chat'],self.chat)
        self.assertEqual(data['messages'][0]['content'],'旧版本保存的消息')
        self.assertTrue(headers['Set-Cookie'].startswith('orvyth_session='))
    def test_default_data_path_keeps_legacy_database(self):
        from chat_web import default_database_path
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ',{'LOCALAPPDATA':folder}):
            root=Path(folder)
            self.assertEqual(default_database_path(),root/'Orvyth'/'browser.sqlite3')
            legacy=root/'OpenAgent'/'browser.sqlite3'
            legacy.parent.mkdir(); legacy.touch()
            self.assertEqual(default_database_path(),legacy)
if __name__=='__main__': unittest.main()
