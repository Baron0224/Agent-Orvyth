import unittest
from pathlib import Path
from functools import partial
from unittest.mock import patch
from chat_web import ChatServer
from file_chat import file_request,ASK_PATH,PROJECT_LOCATION
import test_chat_web


class PendingMemoryTests(unittest.TestCase):
 def test_authenticated_memory_identity_and_pending_release(self):
  with patch('test_chat_web.ChatServer',partial(ChatServer,model='deepseek-cloud:deepseek-flash')):
   web=test_chat_web.WebChatTest();web.setUp()
  try:
   owner=web.server.store.key(web.cookie.split('=',1)[1])
   web.server.store.save_pair(owner,web.chat,'找文件',ASK_PATH)
   with patch('file_chat.find_matches',side_effect=AssertionError('no scan')),patch('chat_web.lookup',side_effect=AssertionError('no web')),patch('chat_web.LocalChat.reply',side_effect=AssertionError('no model')),patch('chat_web.run_project',side_effect=AssertionError('no Pi')):
    answers=[]
    for question in ('我昨天不是给你弄了个文档来当你的记忆库吗我怎么没找到你是不是没用这个你如果用这个了把这个文件给我找出来','那我昨天怎么给你加的记忆你是怎么记忆的','我是谁','？'):
     events=web.request('POST','/api/chat',{'chat_id':web.chat,'message':question})[2]
     self.assertEqual(events[-1]['type'],'done');answer=''.join(e.get('content','') for e in events)
     self.assertNotIn(ASK_PATH,answer);answers.append(answer)
    self.assertIsNone(web.server.memory.storage_answer(owner,'记住：我的记忆库文件需要备份','deepseek'))
    from hermes_memory import HermesMemory
    local=HermesMemory(Path(web.directory.name)/'independent-local')
    self.assertIn('本地版',local.storage_answer(owner,'记忆库在哪里','ollama'))
    self.assertIn('尚未建立',answers[0]);self.assertIn('云端版',answers[0]);self.assertIn('称呼',answers[2])
    web.server.memory.mutate(owner,'add',content='测试回答偏好',category='preference')
    own=web.server.memory.storage_answer(owner,'记忆库文件在哪','deepseek');self.assertIn('已存在',own);self.assertNotIn('测试回答偏好',own)
    _,headers,other=web.request('GET','/api/session',extra={'Cookie':''})
    events=web.request('POST','/api/chat',{'chat_id':other['active_chat'],'message':'记忆库文件在哪'},extra={'Cookie':headers['Set-Cookie'].split(';')[0]})[2]
    other_answer=''.join(e.get('content','') for e in events)
    self.assertIn('尚未建立',other_answer);self.assertNotEqual(own,other_answer)
    import hashlib
    self.assertNotIn(hashlib.sha256(owner.encode()).hexdigest(),other_answer)
   for last in (ASK_PATH,PROJECT_LOCATION):
    history=[{'role':'user','content':'查找文件'},{'role':'assistant','content':last}]
    with patch('file_chat.find_matches',side_effect=AssertionError('no new-topic search')):
     self.assertIsNone(file_request('今天有点累',history))
     self.assertIsNone(file_request('我是谁',history))
     self.assertIsNone(file_request('？',history))
   target=Path(web.directory.name)/'example.txt';target.write_text('test')
   plan=file_request('"'+str(target)+'"',[{'role':'user','content':'读取文件'},{'role':'assistant','content':ASK_PATH}])
   self.assertEqual(plan['only_file'],'example.txt')
  finally:web.tearDown()


if __name__=='__main__':unittest.main()
