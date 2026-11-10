import unittest
from functools import partial
from unittest.mock import patch
from chat_web import ChatServer
import test_chat_web


class PersonalFactsTests(unittest.TestCase):
 def test_real_saved_records_new_chat_read_and_facts(self):
  with patch('test_chat_web.ChatServer',partial(ChatServer,model='deepseek-cloud:deepseek-flash')):
   web=test_chat_web.WebChatTest();web.setUp()
  try:
   owner=web.server.store.key(web.cookie.split('=',1)[1])
   web.server.store.save_profile(owner,{**web.state()['profile'],'user_address':'Boss'})
   def send(text):
    events=web.request('POST','/api/chat',{'chat_id':web.chat,'message':text})[2]
    self.assertEqual(events[-1]['type'],'done',events)
    return ''.join(e.get('content','') for e in events)
   with patch('chat_web.LocalChat.reply',side_effect=AssertionError('no model')),patch('chat_web.lookup',side_effect=AssertionError('no web')),patch('chat_web.run_project',side_effect=AssertionError('no Pi')):
    send('记住：姓名：林舟；学校：海岚信息学院；生日：2002.07.16')
    web.chat=web.request('POST','/api/chats/new',{})[2]['active_chat']
    send('你是怎么记忆的');self.assertIn('海岚',send('帮我读取他'))
    for text in ('就是上面这个文件','那你调取出来'):self.assertIn('海岚',send(text))
    path=web.server.memory.file_path(owner)
    self.assertIn('海岚',send('读取 "'+str(path)+'"'))
    self.assertIn('海岚信息学院',send('我在哪上学'))
    self.assertIn('2002年',send('我是几几年生日'))
    for text in ('我真实的名字','我叫什么','我的姓名是什么'):
     answer=send(text);self.assertIn('林舟',answer);self.assertIn('Boss',answer);self.assertNotIn('没读成功',answer)
    before=path.read_bytes();self.assertIn('没有保存',send('我叫苏禾'));self.assertEqual(path.read_bytes(),before)
    web.server.memory.mutate(owner,'clear',confirmed=True)
    compound='我的名字是顾遥星港信息学院大三生2003.08.19'
    web.server.memory.mutate(owner,'add',content=compound,category='other')
    self.assertIn(compound,send('我在哪上学'))
    self.assertIn('没有标明用途',send('我的出生年份是什么'))
    self.assertIn(compound,send('我真实的名字'))
    web.server.memory.mutate(owner,'clear',confirmed=True)
    with web.server.memory.store(owner) as store:store.add('user','学校：南湾大学')
    self.assertIn('南湾大学',send('我在哪就读'))
    self.assertIn('没有找到能确认',send('我叫什么'))
    web.server.memory.mutate(owner,'add',content='真实姓名：许澄',category='personal')
    self.assertIn('许澄',send('我叫啥'))
    _,headers,other=web.request('GET','/api/session',extra={'Cookie':''})
    events=web.request('POST','/api/chat',{'chat_id':other['active_chat'],'message':'我在哪上学'},extra={'Cookie':headers['Set-Cookie'].split(';')[0]})[2]
    self.assertNotIn('南湾',str(events));self.assertIn('没有找到能确认',str(events))
  finally:web.tearDown()


if __name__=='__main__':unittest.main()
