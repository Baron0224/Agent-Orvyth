"""本机持久记录、会话隔离、聊天与任务接口、流式失败的回归验证。"""
import base64
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from chat_web import ChatServer, WEB_PRIVACY, WEB_PROMPT
from chat_local import LocalChat, PRIVACY_NOTICE
from chat_preferences import DEFAULTS

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
    def test_pi_run_uses_configured_tool_model_and_validates_input(self):
        def results():
            yield {'type': 'delta', 'content': '测试文件结果'}
            yield {'type': 'done'}
        folder = str(Path(self.directory.name).resolve())
        for tool_model in ('qwen3:8b', 'qwen3:4b-instruct'):
            self.server.model = 'deepseek-r1:7b'
            self.server.tool_model = tool_model
            self.assertEqual(self.request('GET', '/api/pi/status')[2]['model'], tool_model)
            with patch('chat_web.run_project', return_value=results()) as run:
                status, _, events = self.request('POST', '/api/pi/run', {
                    'folder': folder, 'task': '  读取测试文件  ', 'model': 'deepseek-r1:7b',
                })
            self.assertEqual(status, 200)
            self.assertEqual(events[-1]['type'], 'done')
            run.assert_called_once_with(folder, '读取测试文件', tool_model)
        for payload in (
            {'folder': [], 'task': '读取文件'},
            {'folder': folder, 'task': None},
            {'folder': folder, 'task': ' '},
            {'folder': folder, 'task': '字' * 2001},
        ):
            with patch('chat_web.run_project') as run:
                self.assertEqual(self.request('POST', '/api/pi/run', payload)[0], 400)
                run.assert_not_called()
    def test_address_only_and_retired_preferences_ignored(self):
        profile = self.state()['profile']
        status, _, saved = self.request('POST', '/api/profile', {**profile, 'chat_model': 'qwen3:8b', 'closeness': 'friendly', 'reply_length': 'long', 'user_address': 'BOOS'})
        self.assertEqual(status, 200)
        self.assertNotIn('chat_model', saved['profile'])
        observed=[]
        def reply(chat, question):
            observed.append(chat.model)
            yield '第一段'
            yield '第二段'
        with patch('chat_web.LocalChat.reply',reply):
            _, _, events=self.request('POST','/api/chat',{'chat_id':self.chat,'message':'陪我聊两句'})
        self.assertEqual(observed,[self.server.model])
        self.assertEqual(events[-1]['type'],'done')
        full=''.join(e.get('content','') for e in events)
        self.assertEqual(full.count('BOOS'),1)
        self.assertEqual(full,self.state()['messages'][-1]['content'])
        for question in ('你现在用什么模型','今天几号','2029.1.1新闻','记住：我喜欢简短回答','提醒我'):
            _,_,events=self.request('POST','/api/chat',{'chat_id':self.chat,'message':question})
            self.assertIn('BOOS',''.join(e.get('content','') for e in events))
        self.stop();self.start()
        self.assertEqual(self.state()['profile']['user_address'],'BOOS')
        _,other=self.server.store.owner(create=True)
        self.assertEqual(self.server.store.state(other)['profile']['user_address'],'')

    def test_address_covers_file_success_and_failure_without_touching_task_events(self):
        profile=self.state()['profile']
        self.request('POST','/api/profile',{**profile,'user_address':'BOOS'})
        for failure in (False, True):
            with patch('chat_web.file_request',return_value={'word_write':{}}), patch('chat_web.create_word_file', side_effect=RuntimeError('写入失败') if failure else None, return_value='已保存：[下载](https://example.org/file.docx)'):
                _,_,events=self.request('POST','/api/chat',{'chat_id':self.chat,'message':'新建文件'})
            answer=''.join(e.get('content','') for e in events)
            self.assertEqual(answer.count('BOOS'),1)
            self.assertEqual(answer,self.state()['messages'][-1]['content'])
            self.assertTrue(any(e['type']=='task' for e in events))
            if not failure:self.assertIn('[下载](https://example.org/file.docx)',answer)

    def test_address_validation_and_code_url_preservation(self):
        from chat_preferences import addressed
        profile=self.state()['profile']
        for value in ('x'*25,'a\nB','a\x7f','a\u200bB',None):
            self.assertEqual(self.request('POST','/api/profile',{**profile,'user_address':value})[0],400)
        text='```python\nprint("boss")\n```\nhttps://example.org/boss'
        self.assertEqual(addressed(text,'boss'),'boss，\n'+text)
        self.assertEqual(addressed('boss，已经好了','boss'),'boss，已经好了')
        self.assertEqual(addressed(text,''),text)
        self.assertEqual(addressed('BOOS，\n\n你好。','BOOS'),'BOOS，你好。')

    def test_both_names_come_from_separate_profile_fields(self):
        profile=self.state()['profile']
        self.request('POST','/api/profile',{**profile,'pet_name':'小白','user_address':'BOOS'})
        with patch('chat_web.lookup',side_effect=AssertionError('names must not search')), patch('chat_web.LocalChat.reply',side_effect=AssertionError('names must not be guessed')):
            _,_,events=self.request('POST','/api/chat',{'chat_id':self.chat,'message':'你叫什么，我叫什么'})
        self.assertEqual(events[0]['content'],'我叫小白，你希望我叫你BOOS。')

    def test_identity_intents_are_separate_account_facts_without_generation(self):
        profile = self.state()['profile']
        self.request('POST','/api/profile',{**profile,'pet_name':'小白','user_address':'BOOS'})
        with patch('chat_web.lookup',side_effect=AssertionError('must not search')), patch('chat_web.LocalChat.reply',side_effect=AssertionError('must not guess identity')):
            for question in ('我是谁','我叫什么','你知道我是谁吗'):
                _,_,events=self.request('POST','/api/chat',{'chat_id':self.chat,'message':question})
                answer=events[0]['content']
                self.assertIn('BOOS',answer)
                self.assertIn('不能把它当作你的真实姓名',answer)
                self.assertNotIn('我叫小白',answer)
            for question in ('你是谁','你叫什么'):
                _,_,events=self.request('POST','/api/chat',{'chat_id':self.chat,'message':question})
                self.assertIn('我叫小白',events[0]['content'])
                self.assertIn('BOOS',events[0]['content'])
            _,_,events=self.request('POST','/api/chat',{'chat_id':self.chat,'message':'你是什么模型'})
            self.assertIn(self.server.model,events[0]['content'])
        old_cookie=self.cookie
        del self.cookie
        _,headers,state=self.request('GET','/api/session')
        self.cookie=headers['Set-Cookie'].split(';')[0]
        _,_,events=self.request('POST','/api/chat',{'chat_id':state['active_chat'],'message':'我是谁'})
        self.assertIn('还没设置',events[0]['content'])
        self.assertNotIn('BOOS',events[0]['content'])
        self.cookie=old_cookie

    def test_identity_router_does_not_hijack_quotes_negation_or_other_tasks(self):
        from chat_local import role_info, model_info
        for question in ('不要回答我是谁','我不是问你是谁','“我是谁”是什么意思','解释电影《我是谁》','你是谁以及怎么写代码','你叫什么我叫什么，然后帮我写代码','你不是什么模型','你是什么模型，怎么部署'):
            self.assertIsNone(role_info(question,'小白','BOOS'))
            self.assertIsNone(model_info(question,'deepseek-r1:7b','小白'))

    def test_lookup_does_not_append_citation_footer(self):
        source = {'title': '测试百科', 'url': 'https://example.org/source', 'extract': '供测试的事实。'}
        with patch('chat_web.lookup', return_value=source):
            status, _, events = self.send('恐龙是什么')
        self.assertEqual(status, 200)
        answer = ''.join(event.get('content', '') for event in events)
        self.assertEqual(answer, '测试回答')
        self.assertEqual(self.state()['messages'][-1]['content'], answer)
    def test_identity_uses_current_pet_name(self):
        profile = self.state()['profile']
        for name in ('小团', '星星'):
            self.assertEqual(self.request('POST', '/api/profile', {**profile, 'pet_name': name})[0], 200)
            status, _, events = self.send('你知道你叫什么名字吗')
            self.assertEqual(status, 200)
            self.assertIn(name, events[0]['content'])
            self.assertIn('Orvyth', events[0]['content'])
            self.assertIn('AI', events[0]['content'])
            _, _, repeated = self.send('你知道你叫什么名字吗')
            self.assertEqual(events[0]['content'], repeated[0]['content'])
            self.assertIn(name, repeated[0]['content'])
    def test_identity_questions_do_not_search(self):
        with patch('chat_web.lookup', side_effect=AssertionError('identity must not search')):
            for question in ('你是谁', '你是谁呀', '你是什么人'):
                status, _, events = self.send(question)
                self.assertEqual(status, 200)
                self.assertNotIn('资料来源', events[0]['content'])
    def test_model_identity_keeps_custom_name_without_search_or_generation(self):
        profile = self.state()['profile']
        self.request('POST', '/api/profile', {**profile, 'pet_name': '小团'})
        with patch('chat_web.lookup', side_effect=AssertionError('must not search')), patch('chat_web.LocalChat.reply', side_effect=AssertionError('runtime fact must not be guessed')):
            _, _, events = self.request('POST', '/api/chat', {'chat_id': self.chat, 'message': '你现在用什么模型'})
        self.assertIn('小团', events[0]['content'])
        self.assertIn('Orvyth', events[0]['content'])
        self.assertIn(self.server.model, events[0]['content'])
    def test_assets_host_origin_and_input_boundaries(self):
        self.assertEqual(self.request('GET','/')[0],200)
        for asset in ('/reminder-notifications.js', '/pet3d.js', '/companion3d/model.js', '/companion3d/vendor/three.module.js', '/companion3d/vendor/three.core.js'):
            status, headers, body = self.request('GET', asset)
            self.assertEqual(status, 200)
            self.assertTrue(headers['Content-Type'].startswith('text/javascript'))
            self.assertTrue(body)
        self.assertEqual(self.request('GET', '/companion3d/../../chat_local.py')[0], 404)
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
        profile={'name':'测试空间','pet_name':'小团','pet_motion':False,'pet_kind':'cat','avatar':PNG}
        self.assertEqual(self.request('POST','/api/profile',profile)[0],200)
        self.send('重启之后还要在')
        self.stop(); self.start()
        data=self.state()
        self.assertEqual(data['profile'],{**DEFAULTS, **profile, 'chat_engine':'local'})
        self.assertEqual(data['tasks'][0]['done'],1)
        self.assertEqual(data['messages'][0]['content'],'重启之后还要在')
        self.request('POST','/api/tasks/toggle',{'id':task['id'],'done':False})
        self.assertEqual(self.state()['tasks'][0]['done'],0)
        self.request('POST','/api/tasks/delete',{'id':task['id']})
        self.assertEqual(self.state()['tasks'],[])
    def test_pet_selection_legacy_payload_preserves_saved_cat(self):
        profile = {**self.state()['profile'], 'pet_kind': 'cat'}
        self.assertEqual(self.request('POST', '/api/profile', profile)[0], 200)
        profile.pop('pet_kind')
        self.assertEqual(self.request('POST', '/api/profile', profile)[0], 200)
        self.assertEqual(self.state()['profile']['pet_kind'], 'cat')

    def test_invalid_profile_and_tasks_do_not_overwrite(self):
        profile=self.state()['profile']
        for data in [{**profile,'pet_kind':'dragon'},{**profile,'name':''},{**profile,'pet_motion':'yes'},{**profile,'avatar':'data:image/svg+xml;base64,PHN2Zz4='},{**profile,'avatar':PNG+'!'}]:
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

    def test_news_uses_retrieved_source_without_api_key(self):
        source={'title':'BBC World','url':'https://feeds.bbci.co.uk/news/world/rss.xml','extract':'真实新闻标题及时间','kind':'news'}
        with patch.dict('os.environ',{'TAVILY_API_KEY':''}),patch('chat_web.lookup',return_value=source) as lookup:
            status,_,events=self.send('说出2026.11.4的新闻')
        self.assertEqual(status,200);lookup.assert_called_once()
        self.assertIn('BBC World 原始标题',''.join(event.get('content','') for event in events))

    def test_repeated_login_request_asks_for_missing_evidence(self):
        question='我现在不想休息，想解决登录报错，先检查什么'
        first=self.send(question)[2][0]['content']
        second=self.send(question)[2][0]['content']
        self.assertIn('错误原文',first);self.assertIn('还缺',second)
        self.assertNotEqual(first,second)
    def test_failed_stream_not_saved(self):
        _,_,events=self.send('模拟失败')
        self.assertEqual(events[-1]['type'],'error')
        self.assertEqual(self.state()['messages'],[])
        self.assertFalse(self.server.generation_lock.locked())

    def test_named_project_read_asks_for_path_without_search_or_model(self):
        from file_chat import ASK_PATH
        with patch('chat_web.lookup', side_effect=AssertionError('must not search')), \
             patch('file_chat.find_matches',return_value=[]), \
             patch('chat_web.LocalChat.reply', side_effect=AssertionError('must not invent an answer')):
            status, _, events = self.send('读取我three feet under中的故事背景大概讲了什么')
        self.assertEqual(status, 200)
        self.assertEqual(events[0], {'type':'delta','content':ASK_PATH})
        self.assertEqual(events[-1]['type'], 'done')
        self.assertEqual(self.state()['messages'][-1]['content'], ASK_PATH)
    def test_archive_is_full_but_model_context_bounded(self):
        for i in range(10): self.send(str(i))
        self.assertEqual(len(self.state()['messages']),20)
        _,owner=self.server.store.owner(self.cookie.split('=',1)[1])
        self.assertEqual(len(self.server.store.history(owner,self.chat)),16)
    def test_r1_http_saves_only_final_answer_and_no_failed_pair(self):
        chunks = [
            {'message': {'thinking': 'internal reasoning'}},
            {'message': {'content': '<thi'}},
            {'message': {'content': 'nk>legacy reasoning</think>391'}, 'done': True},
        ]
        raw = b''.join(json.dumps(chunk).encode() + b'\n' for chunk in chunks)
        self.server.model = 'deepseek-r1:7b'
        with patch('chat_local.urllib.request.build_opener') as build:
            build.return_value.open.return_value = io.BytesIO(raw)
            status, _, events = self.request('POST', '/api/chat', {'chat_id': self.chat, 'message': '计算17乘23'})
        self.assertEqual(status, 200)
        self.assertEqual([e for e in events if e['type']!='status'], [{'type': 'delta', 'content': '391'}, {'type': 'done', 'chat_id': self.chat}])
        self.assertEqual(self.state()['messages'][-1]['content'], '391')
        with patch('chat_local.urllib.request.build_opener') as build:
            build.return_value.open.return_value = io.BytesIO(b'{"message":{"thinking":"unfinished"},"done":true,"done_reason":"length"}\n')
            _, _, events = self.request('POST', '/api/chat', {'chat_id': self.chat, 'message': '计算18乘23'})
        self.assertEqual(events[-1]['type'], 'error')
        self.assertEqual(len(self.state()['messages']), 2)
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
