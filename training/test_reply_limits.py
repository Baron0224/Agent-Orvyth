"""回答预算、错误结束和个人资料查找的回归。"""
import io,json,unittest,urllib.error,tempfile,os
from unittest.mock import patch
from chat_local import LocalChat,INPUT_BYTE_BUDGET
from web_lookup import source_context,search_query,conversation_followup
from file_chat import file_request,PROJECT_LOCATION
import test_chat_web

class ReplyLimitsTest(unittest.TestCase):
 def test_evidence_and_old_history_are_bounded_without_deleting_storage(self):
  source={'kind':'web','extract':'重复'*9000,'items':[{'title':'真实标题','url':'https://example.org','snippet':'证据'*6000}],'pages':[{'title':'正文','text':'正文'*9000}]}
  context=source_context(source,True,byte_budget=1500)
  self.assertLessEqual(len(context.encode()),1500);self.assertIn('https://example.org',context)
  chat=LocalChat('deepseek-r1:7b',system_prompt='身份约束'+context)
  chat.history=[{'role':r,'content':'历史'*400} for r in ('user','assistant','user','assistant')]
  response=io.BytesIO(json.dumps({'message':{'content':'完整答案'},'done':True}).encode()+b'\n')
  with patch('chat_local.urllib.request.build_opener') as build:
   build.return_value.open.return_value=response
   self.assertEqual(''.join(chat.reply('本轮问题')),'完整答案')
   messages=json.loads(build.return_value.open.call_args.args[0].data)['messages']
  self.assertLessEqual(sum(len(m['content'].encode())+64 for m in messages),INPUT_BYTE_BUDGET)
  self.assertEqual(messages[-1]['content'],'本轮问题');self.assertIn('身份约束',messages[0]['content'])
  self.assertEqual(len(chat.history),6)
 def test_context_400_is_understandable_and_does_not_echo_prompt(self):
  error=urllib.error.HTTPError('http://localhost',400,'bad',{},io.BytesIO(b'{"error":"request (9322 tokens) exceeds the available context size (8192 tokens)"}'))
  chat=LocalChat('deepseek-r1:7b')
  with patch('chat_local.urllib.request.build_opener') as build:
   build.return_value.open.side_effect=error
   with self.assertRaisesRegex(RuntimeError,'超过模型一次能读'):list(chat.reply('test'))
  self.assertEqual(chat.history,[])
 def test_private_project_ranking_and_self_assessment(self):
  with patch('file_chat.find_matches',side_effect=AssertionError('do not scan without location')):
   plan=file_request('帮我查一下我three feet under的图纸demo帮我找一下',[])
   self.assertIn('本地文件夹还是网站',plan['reply'])
   history=[{'role':'user','content':'我的图纸demo'},{'role':'assistant','content':'BOOS，'+plan['reply']}]
   with patch('project_lookup.find_matches',side_effect=AssertionError('generic demo must not search projects')):
    self.assertIn('还缺项目或文件夹的名字',file_request('本地',history)['reply'])
   plan=file_request('网站',history);self.assertIn('链接',plan['reply'])
   self.assertIsNone(file_request('https://example.org/demo',[{'role':'assistant','content':'BOOS，'+plan['reply']}]))
  rank=conversation_followup('给我在deepseekharness chatgpt muse Claude grokbot里排行榜',[],None)
  self.assertIn('deepseekharness',rank['answer']);self.assertIn('维度',rank['answer']);self.assertNotIn('query',rank)
  self.assertIsNone(search_query('你查一下自己觉得你还需要补充什么'))
 def test_http_errors_and_addressed_location_clarification(self):
  web=test_chat_web.WebChatTest();web.setUp()
  try:
   profile=web.state()['profile'];web.request('POST','/api/profile',{**profile,'user_address':'BOOS'})
   with patch('chat_web.lookup',side_effect=AssertionError('not public search')),patch.dict(os.environ,{'ORVYTH_FILE_ROOTS':web.directory.name}):
    for q,expected in [('帮我查一下我three feet under的图纸demo','本地文件夹还是网站'),('本地','允许的目录')]:
     events=web.request('POST','/api/chat',{'chat_id':web.chat,'message':q})[2]
     answer=''.join(e.get('content','') for e in events);self.assertIn(expected,answer);self.assertTrue(answer.startswith('BOOS'));self.assertEqual(events[-1]['type'],'done')
   web.chat=web.request('POST','/api/chats/new',{})[2]['active_chat']
   with patch('chat_web.lookup',side_effect=ValueError('private internal detail')):
    events=web.send('联网查找Python文档')[2]
   self.assertEqual(events[-1]['type'],'error');self.assertNotIn('private internal',str(events));self.assertEqual(web.state()['messages'],[])
  finally:web.tearDown()
if __name__=='__main__':unittest.main()
