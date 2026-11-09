"""Mock-only cloud protocol and real loopback HTTP integration; no paid requests."""
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch, Mock

import deepseek_cloud as cloud
from chat_local import LocalChat, CONVERSATION_STYLE
from chat_web import ChatServer
import cloud_launch


def sse(text='收到，我听你说。', finish='stop', done=True):
    events = [': keepalive', '', 'data: '+json.dumps({'choices':[{'delta':{'reasoning_content':'隐藏思考','content':text}}]},ensure_ascii=False), '',
              'data: '+json.dumps({'choices':[{'delta':{},'finish_reason':finish}]}), '',
              'data: '+json.dumps({'choices':[], 'usage':{'prompt_tokens':10,'completion_tokens':4,'total_tokens':14,'secret':'never'}}), '']
    if done: events += ['data: [DONE]', '']
    return io.BytesIO(('\n'.join(events)+'\n').encode('utf8'))


class CloudTests(unittest.TestCase):
    def test_payload_and_sse(self):
        opener=Mock();opener.open.return_value=sse()
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY':'test-not-a-real-key','ORVYTH_CLOUD_MAX_TOKENS':'512'}, clear=True), patch.object(cloud.urllib.request,'build_opener',return_value=opener):
            chat=LocalChat('deepseek-cloud:deepseek-flash')
            chat.display_name='小白';chat.user_address='BOOS'
            text=''.join(chat.reply('今天有点累，想被你宠一下。'))
        self.assertEqual(opener.open.call_count,1)
        request=opener.open.call_args.args[0];data=json.loads(request.data)
        self.assertEqual(request.full_url,cloud.ENDPOINT)
        self.assertEqual(request.get_header('Authorization'),'Bearer test-not-a-real-key')
        self.assertEqual(data['thinking'],{'type':'disabled'})
        self.assertEqual(data['model'],'deepseek-flash')
        self.assertNotIn('think',data);self.assertNotIn('options',data)
        self.assertIn(CONVERSATION_STYLE,data['messages'][0]['content'])
        self.assertIn('BOOS',data['messages'][0]['content'])
        self.assertNotIn('隐藏思考',text)
        self.assertEqual(chat.usage,{'prompt_tokens':10,'completion_tokens':4,'total_tokens':14})
        self.assertEqual(len(chat.history),2)

    def test_failure_statuses_and_missing_key(self):
        for code in (401,402,429):
            with self.subTest(code=code), patch.dict('os.environ',{'DEEPSEEK_API_KEY':'test-key'},clear=True), patch.object(cloud.urllib.request,'build_opener') as build:
                build.return_value.open.side_effect=urllib.error.HTTPError(cloud.ENDPOINT,code,'secret-body',{},io.BytesIO(b'secret-key'))
                with self.assertRaisesRegex(RuntimeError,str(code)) as caught: cloud.open_chat([],cloud.PREFIX+'deepseek-flash')
                self.assertNotIn('secret',str(caught.exception));self.assertEqual(build.return_value.open.call_count,1)
        with patch.dict('os.environ',{},clear=True), patch.object(cloud.urllib.request,'build_opener') as build:
            with self.assertRaisesRegex(RuntimeError,'未配置'):cloud.open_chat([],cloud.PREFIX+'deepseek-flash')
            build.assert_not_called()

    def test_incomplete_or_timeout_keeps_history(self):
        for finish,done in [('length',True),('stop',False)]:
            chat=LocalChat(cloud.PREFIX+'deepseek-flash')
            with self.subTest(finish=finish,done=done), patch('chat_local.open_chat',return_value=cloud.CloudResponse(sse(finish=finish,done=done))):
                with self.assertRaises(RuntimeError):list(chat.reply('随便聊聊'))
                self.assertEqual(chat.history,[])
        with patch('chat_local.open_chat',side_effect=TimeoutError), patch('chat_local.urllib.request.OpenerDirector.open') as local:
            with self.assertRaisesRegex(RuntimeError,'未切换'):list(LocalChat(cloud.PREFIX+'deepseek-flash').reply('随便聊聊'))
            local.assert_not_called()

    def test_sse_network_fragmentation_and_close(self):
        class Fragmented(io.RawIOBase):
            def __init__(self, data):self.data=io.BytesIO(data)
            def readable(self):return True
            def readinto(self, buffer):
                part=self.data.read(min(3,len(buffer)))
                buffer[:len(part)]=part
                return len(part)
        stream=io.BufferedReader(Fragmented(sse().getvalue()))
        with cloud.CloudResponse(stream) as response:
            chunks=[json.loads(line) for line in response]
        self.assertTrue(stream.closed)
        self.assertTrue(chunks[-1]['done'])
        self.assertEqual(chunks[0]['message']['content'],'收到，我听你说。')
        response=sse()
        with cloud.CloudResponse(response) as events:
            iterator=iter(events);next(iterator);iterator.close()
        self.assertTrue(response.closed)

    def test_default_paths_and_missing_key_status(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ',{'LOCALAPPDATA':directory,'USERPROFILE':directory},clear=True), patch.object(ChatServer,'installed_models',return_value=[]):
            remote=ChatServer(0,cloud.PREFIX+'deepseek-flash')
            local=ChatServer(0)
            try:
                self.assertEqual(remote.store.path,Path(directory)/'Orvyth'/'cloud'/'browser.sqlite3')
                self.assertNotEqual(remote.store.path,local.store.path)
                self.assertNotEqual(remote.memory,local.memory)
                self.assertFalse(remote.runtime_status()['configured'])
                self.assertFalse(remote.runtime_status()['verified'])
                self.assertFalse(remote.runtime_status()['ready'])
            finally:remote.server_close();local.server_close()

    def test_hidden_launcher_child_environment(self):
        with patch.dict('os.environ',{},clear=True), patch('cloud_launch.sys.stdin.isatty',return_value=True), patch('cloud_launch.load_key',return_value=''), patch('builtins.input',return_value=''), patch('cloud_launch.getpass.getpass',return_value='test-hidden-key'), patch('cloud_launch.subprocess.call',return_value=0) as call:
            self.assertEqual(cloud_launch.main([]),0)
            self.assertNotIn('test-hidden-key',str(call.call_args.args))
            self.assertEqual(call.call_args.kwargs['env']['DEEPSEEK_API_KEY'],'test-hidden-key')
            self.assertNotIn('DEEPSEEK_API_KEY',cloud_launch.os.environ)

    def test_loopback_save_isolation_status_and_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ',{'DEEPSEEK_API_KEY':'mock-only'},clear=True), patch.object(ChatServer,'installed_models',return_value=[{'name':'qwen3:8b'}]):
            server=ChatServer(0,cloud.PREFIX+'deepseek-flash',Path(directory)/'cloud.sqlite3')
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            local=ChatServer(0,'qwen3:8b',Path(directory)/'local.sqlite3')
            try:
                def request(method,path,payload=None,cookie=None):
                    conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
                    headers={'Origin':server.origin,'Content-Type':'application/json'}
                    if cookie:headers['Cookie']=cookie
                    conn.request(method,path,json.dumps(payload).encode() if payload else None,headers)
                    response=conn.getresponse();body=response.read();header=dict(response.getheaders());conn.close()
                    return header,body
                header,body=request('GET','/api/session');state=json.loads(body)
                cookie=header['Set-Cookie'].split(';')[0];chat=state['active_chat']
                self.assertTrue(cookie.startswith('orvyth_cloud_session='))
                self.assertNotEqual(local.cookie_name,server.cookie_name)
                self.assertIn('DeepSeek',state['privacy']);self.assertNotIn('mock-only',body.decode())
                status=server.runtime_status();self.assertTrue(status['configured']);self.assertFalse(status['verified'])
                self.assertEqual(server.tool_model,'qwen3:8b')
                with patch('chat_local.open_chat',side_effect=lambda *a:cloud.CloudResponse(sse())), patch('chat_web.lookup',return_value=None), patch('chat_web.search_query',return_value=None):
                    _,body=request('POST','/api/chat',{'chat_id':chat,'message':'今天有点累，想被你宠一下。'},cookie)
                events=[json.loads(line) for line in body.splitlines()]
                self.assertEqual(events[-1]['type'],'done',events)
                _,body=request('GET','/api/session',cookie=cookie);messages=json.loads(body)['messages']
                self.assertEqual(len(messages),2);self.assertEqual(messages[-1]['usage']['total_tokens'],14)
                self.assertTrue(server.runtime_status()['verified'])
                with patch('chat_local.open_chat',side_effect=lambda *a:cloud.CloudResponse(sse(finish='length'))), patch('chat_web.lookup',return_value=None), patch('chat_web.search_query',return_value=None):
                    _,body=request('POST','/api/chat',{'chat_id':chat,'message':'再聊一句'},cookie)
                self.assertEqual(json.loads(body.splitlines()[-1])['type'],'error')
                _,body=request('GET','/api/session',cookie=cookie);self.assertEqual(len(json.loads(body)['messages']),2)
                for code in (401,402,429):
                    with patch('chat_local.open_chat',side_effect=RuntimeError(cloud.error_message(code))) as call, patch('chat_web.lookup',return_value=None), patch('chat_web.search_query',return_value=None):
                        _,body=request('POST','/api/chat',{'chat_id':chat,'message':'随便再聊一句'},cookie)
                    self.assertIn(str(code),body.decode());self.assertEqual(call.call_count,1)
                    _,body=request('GET','/api/session',cookie=cookie);self.assertEqual(len(json.loads(body)['messages']),2)
                _,body=request('GET','/api/session',cookie='orvyth_session='+cookie.split('=',1)[1]);self.assertEqual(json.loads(body)['messages'],[])
                self.assertIn('云端', ''.join(LocalChat(cloud.PREFIX+'deepseek-flash').reply('你用的什么模型')))
            finally:
                server.shutdown();server.server_close();thread.join();local.server_close()


if __name__=='__main__':unittest.main()
