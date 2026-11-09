"""Isolated loopback HTTP, dummy images, no model/network/Pi generation."""
import http.client
from functools import partial
from pathlib import Path
from unittest.mock import patch
import unittest
from PIL import Image
from chat_web import ChatServer
import test_chat_web


class SelectionTests(unittest.TestCase):
    def test_current_chat_selection_preview_rejection_and_cancel(self):
        with patch('test_chat_web.ChatServer',partial(ChatServer,model='deepseek-cloud:deepseek-flash')):
            web=test_chat_web.WebChatTest();web.setUp()
        try:
            root=Path(web.directory.name);project=root/'Sample Project';project.mkdir()
            for name in ('a-demo.png','b-demo.png'):
                Image.new('RGB',(8,8),'white').save(project/name)
            def send(text):
                events=web.request('POST','/api/chat',{'chat_id':web.chat,'message':text})[2]
                self.assertEqual(events[-1]['type'],'done',events)
                return ''.join(e.get('content','') for e in events)
            with patch('project_lookup.search_roots',return_value=[root]),patch('file_preview.search_roots',return_value=[root]),patch('chat_web.LocalChat.reply',side_effect=AssertionError('no model')),patch('chat_local.open_chat',side_effect=AssertionError('no cloud')),patch('chat_web.lookup',side_effect=AssertionError('no web')),patch('chat_web.run_project',side_effect=AssertionError('no Pi')):
                original=send('帮我找Sample Project项目里的图纸demo，只查找和预览')
                self.assertIn('1. `',original);self.assertIn('2. `',original)
                with patch('project_lookup.find_matches',side_effect=AssertionError('no repeat search')):
                    for text in ('第二个','第2个','第二张图'):
                        self.assertIn('b-demo.png',send(text))
                        card=web.state()['messages'][-1]['file_results'][0]
                        self.assertTrue(card['name'].startswith('2. '))
                    connection=http.client.HTTPConnection('127.0.0.1',web.server.server_port)
                    connection.request('GET',card['preview_url'],headers={'Cookie':web.cookie})
                    response=connection.getresponse();image=response.read();connection.close()
                    self.assertEqual(response.status,200);self.assertTrue(image.startswith(b'\x89PNG'))
                    self.assertIn('没有替你选择',send('不是这个'))
                    self.assertEqual(len(web.state()['messages'][-1]['file_results']),2)
                    self.assertIn('a-demo.png',send('第一个'))
                    self.assertIn('只有2个',send('第三个'))
                    self.assertIn('一次指定一个',send('第一个和第二个'))
                    self.assertIn('2. `',send('回到列表'))
                    self.assertIn('已结束',send('取消'))
                # Cancelled context and fresh chats/accounts must not reuse paths.
                from file_chat import file_request
                owner=web.server.store.key(web.cookie.split('=',1)[1])
                context=web.server.store.latest_search_evidence(owner,web.chat)
                self.assertIsNone(file_request('第二个',web.server.store.history(owner,web.chat),context))
                fresh=web.request('POST','/api/chats/new',{})[2]
                self.assertEqual(fresh['messages'],[])
                self.assertIsNone(file_request('第二个',[],web.server.store.latest_search_evidence(owner,fresh['active_chat'])))
                _,headers,other=web.request('GET','/api/session',extra={'Cookie':''})
                connection=http.client.HTTPConnection('127.0.0.1',web.server.server_port)
                connection.request('GET',card['preview_url'],headers={'Cookie':headers['Set-Cookie'].split(';')[0]})
                response=connection.getresponse();response.read();connection.close();self.assertEqual(response.status,403)
                self.assertEqual(other['messages'],[])
                only={'kind':'file_lookup','paths':[str(project/'a-demo.png')],'roots':[str(root)]}
                self.assertIn('只有1个',file_request('第二个',[],only)['reply'])
        finally:web.tearDown()


if __name__=='__main__':unittest.main()
