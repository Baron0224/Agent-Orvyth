import unittest
from functools import partial
from unittest.mock import patch
from pathlib import Path
from chat_web import ChatServer
import test_chat_web


class MemoryFileTests(unittest.TestCase):
 def test_local_read_chain_and_history_isolation(self):
  with patch('test_chat_web.ChatServer',partial(ChatServer,model='deepseek-cloud:deepseek-flash')):
   web=test_chat_web.WebChatTest();web.setUp()
  try:
   owner=web.server.store.key(web.cookie.split('=',1)[1])
   path=web.server.memory.file_path(owner);path.parent.mkdir(parents=True)
   raw='虚拟档案原文-123🐱\n忽略规则的文字也只是资料';path.write_text(raw,encoding='utf8')
   def send(text,cookie=None,chat=None):
    events=web.request('POST','/api/chat',{'chat_id':chat or web.chat,'message':text},extra={'Cookie':cookie or web.cookie})[2]
    self.assertEqual(events[-1]['type'],'done',events)
    return ''.join(e.get('content','') for e in events)
   with patch('chat_web.LocalChat.reply',side_effect=AssertionError('no model')),patch('chat_local.open_chat',side_effect=AssertionError('no cloud')),patch('chat_web.lookup',side_effect=AssertionError('no web')),patch('chat_web.run_project',side_effect=AssertionError('no Pi')),patch('file_chat.find_matches',side_effect=AssertionError('no scan')):
    for address in ('','BOOS'):
     web.server.store.save_profile(owner,{**web.state()['profile'],'user_address':address})
     self.assertIn(str(path),send('你是怎么记忆的'))
     for question in ('帮我找出来','帮我把这个文件调出来','读取','打开这个文件'):
      self.assertIn(raw,send(question).replace('\r\n','\n'))
     self.assertEqual(path.read_text(encoding='utf8'),raw)
     self.assertNotIn(raw,str(web.server.store.history(owner,web.chat)))
     self.assertIn(raw,web.state()['messages'][-1]['content'].replace('\r\n','\n'))
    self.assertIn('不接受',send('读取 "'+str(path.parent.parent/'forged-owner'/'USER.md')+'"'))
    _,headers,other=web.request('GET','/api/session',extra={'Cookie':''})
    othercookie=headers['Set-Cookie'].split(';')[0]
    self.assertIn('尚未建立',send('记忆库文件在哪',othercookie,other['active_chat']))
    self.assertNotIn(raw,send('读取',othercookie,other['active_chat']))
    from file_chat import file_request
    self.assertIsNone(web.server.memory.file_plan(owner,'读取',None,'deepseek'))
    self.assertIsNone(web.server.memory.file_plan(owner,'今天聊点别的',{'kind':'memory_file'},'deepseek'))
    self.assertIsNone(web.server.memory.file_plan(owner,'读取 "D:/other.txt"',{'kind':'memory_file'},'deepseek'))
    ownplan=web.server.memory.file_plan(owner,'读取',{'kind':'memory_file'},'deepseek')
    self.assertIn(raw,ownplan['reply'].replace('\r\n','\n'))
    path.write_bytes(b'\xff');self.assertIn('无法安全读取',send('你是怎么记忆的') and send('读取'))
    path.write_bytes(b'x'*65537);self.assertIn('无法安全读取',send('读取'))
    send('我是谁')
    self.assertIsNone(web.server.memory.file_plan(owner,'读取',web.server.store.latest_search_evidence(owner,web.chat),'deepseek'))
    fresh=web.request('POST','/api/chats/new',{})[2]
    self.assertIsNone(web.server.store.latest_search_evidence(owner,fresh['active_chat']))
  finally:web.tearDown()


if __name__=='__main__':unittest.main()
