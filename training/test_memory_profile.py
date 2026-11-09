import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from hermes_memory import HermesMemory
from chat_local import LocalChat,INPUT_BYTE_BUDGET
import test_chat_web
class ProfileTest(unittest.TestCase):
 def test_actual_storage_legacy_crud_budget(self):
  with tempfile.TemporaryDirectory() as d:
   memory=HermesMemory(d)
   with memory.store('a') as store:store.add('user','旧记忆原文保持不变')
   raw=next(Path(d).rglob('USER.md')).read_text(encoding='utf8');old=memory.entries('a')[0]
   self.assertEqual(old['source'],'legacy');self.assertIsNone(old['updated_at'])
   memory.command('a','记住我学习编程要先结论后步骤');items=memory.entries('a');new=items[-1];self.assertEqual(new['category'],'preference');self.assertIn('旧记忆原文保持不变',next(Path(d).rglob('USER.md')).read_text(encoding='utf8'))
   memory.mutate('a','edit',new['id'],'学习编程先例子再解释','preference');self.assertEqual(memory.entries('a')[-1]['id'],new['id']);self.assertNotIn('先结论',memory.prompt('a','编程'))
   for n in range(20):memory.mutate('a','add',content=f'项目{n}的背景'+('背景'*140),category='other')
   self.assertLessEqual(len(memory.prompt('a','编程').encode()),900);self.assertEqual(len(memory.entries('a')),22)
   chat=LocalChat('deepseek-r1:7b',system_prompt='固定规则'*390);chat.memory_context=memory.prompt('a','编程')
   with patch('chat_local.urllib.request.build_opener') as build:
    build.return_value.open.return_value=io.BytesIO((json.dumps({'message':{'content':'完整答案'},'done':True})+'\n').encode())
    list(chat.reply('教我编程'));messages=json.loads(build.return_value.open.call_args.args[0].data)['messages']
   self.assertLessEqual(sum(len(x['content'].encode())+64 for x in messages),INPUT_BYTE_BUDGET);self.assertIn('先例子',messages[0]['content'])
   self.assertEqual(memory.entries('b'),[])
   with self.assertRaises(ValueError):memory.mutate('b','delete',new['id'])
   with self.assertRaises(ValueError):memory.mutate('a','add',content='密码是123456',category='personal')
   self.assertIsNone(memory.command('a','今天很累'));self.assertEqual(len(memory.entries('a')),22)
   memory.command('a','记住：我叫测试小明');self.assertIn('我叫测试小明',memory.personal_answer('a','我的名字是什么'))
   self.assertIn('先例子',memory.personal_answer('a','我的回答偏好是什么'))
   memory.mutate('a','delete',new['id']);self.assertNotIn('先例子',memory.prompt('a','编程'))
   memory.mutate('a','clear',confirmed=True);self.assertEqual(HermesMemory(d).entries('a'),[])
 def test_http_permissions_and_new_chats(self):
  web=test_chat_web.WebChatTest();web.setUp()
  try:
   web.send('记住我学习编程要先结论后步骤')
   items=web.request('GET','/api/memory')[2]['entries'];entry=items[0]
   web.chat=web.request('POST','/api/chats/new',{})[2]['active_chat'];seen=[]
   def reply(chat,q):seen.append(chat.memory_context);yield '测试正文'
   with patch('chat_web.LocalChat.reply',reply):web.request('POST','/api/chat',{'chat_id':web.chat,'message':'教我编程'})
   self.assertIn('先结论后步骤',seen[-1])
   status,_,_=web.request('POST','/api/memory',{'action':'edit','id':entry['id'],'content':'学习编程先例子再解释','category':'preference'});self.assertEqual(status,200)
   _,headers,other=web.request('GET','/api/session',extra={'Cookie':''});cookie=headers['Set-Cookie'].split(';')[0]
   self.assertEqual(web.request('GET','/api/memory',extra={'Cookie':cookie})[2]['entries'],[])
   self.assertEqual(web.request('POST','/api/memory',{'action':'delete','id':entry['id']},extra={'Cookie':cookie})[0],400)
   self.assertEqual(web.request('POST','/api/memory',{'action':'clear'})[0],400)
   web.chat=web.request('POST','/api/chats/new',{})[2]['active_chat']
   with patch('chat_web.LocalChat.reply',reply):web.request('POST','/api/chat',{'chat_id':web.chat,'message':'教我编程'})
   self.assertIn('先例子再解释',seen[-1]);self.assertNotIn('先结论',seen[-1])
   web.request('POST','/api/memory',{'action':'delete','id':entry['id']});web.chat=web.request('POST','/api/chats/new',{})[2]['active_chat']
   with patch('chat_web.LocalChat.reply',reply):web.request('POST','/api/chat',{'chat_id':web.chat,'message':'教我编程'})
   self.assertEqual(seen[-1],'')
  finally:web.tearDown()
if __name__=='__main__':unittest.main()
