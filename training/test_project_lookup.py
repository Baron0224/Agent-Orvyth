"""真实临时目录和HTTP连续确认；文件搜索不调用模型或写文件。"""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from file_lookup import find_matches
from project_lookup import project_parts
from file_chat import file_request,PROJECT_LOCATION
import test_chat_web

REQUEST='帮我找我的three feet under的文件夹中的图纸demo'
class ProjectLookupTest(unittest.TestCase):
 def test_artifact_type_excludes_audio_without_losing_duplicate_drawings(self):
  with tempfile.TemporaryDirectory() as folder,patch('project_lookup.search_roots',return_value=[Path(folder)]):
   project=Path(folder)/'Sample Project';project.mkdir()
   for name in ('one/demo.png','two/demo.png','demo.pdf','demo.wav','demo.ogg','demo.unknown'):
    target=project/name;target.parent.mkdir(exist_ok=True);target.write_bytes(b'not read')
   plan=file_request('查找Sample Project项目里的图纸demo',[])
   paths=plan['file_lookup']['paths']
   self.assertEqual(len(paths),4);self.assertFalse(any(p.endswith(('.wav','.ogg')) for p in paths))
   self.assertEqual(sum(p.endswith('.png') for p in paths),2)
   self.assertIn('未知扩展名',plan['reply'])
   audio=file_request('查找Sample Project项目里的音频demo',[])['file_lookup']['paths']
   self.assertEqual({Path(p).suffix for p in audio},{'.wav','.ogg'})
   for path in paths:Path(path).unlink()
   empty=file_request('查找Sample Project项目里的图纸demo',[])
   self.assertEqual(empty['file_lookup']['paths'],[])
   self.assertIn('未找到类型匹配的图纸候选',empty['reply'])
 def test_named_projects_cloud_route_without_ownership_or_constraint_leak(self):
  from functools import partial
  from chat_web import ChatServer
  variants=[('three feet under','帮我找 three feet under 项目里的图纸 demo，先只查找和预览，不修改任何文件。'),
            ('Moon Harbor','查找Moon Harbor项目里的图纸demo 先只查找和预览 不修改任何文件'),
            ('晨星计划','请找晨星计划项目里的图纸 demo, preview only; do not modify files')]
  with patch('test_chat_web.ChatServer',partial(ChatServer,model='deepseek-cloud:deepseek-flash')):
   web=test_chat_web.WebChatTest();web.setUp()
  try:
   root=Path(web.directory.name)/'allowed';root.mkdir()
   for name,question in variants:
    project=root/name;project.mkdir();demo=project/'新手图demo.png';demo.write_bytes(b'candidate-not-read')
    self.assertEqual(project_parts(question),(name,'图纸 demo' if '图纸 demo' in question else '图纸demo'))
    web.chat=web.request('POST','/api/chats/new',{})[2]['active_chat']
    with patch('project_lookup.search_roots',return_value=[root]),patch('chat_web.LocalChat.reply',side_effect=AssertionError('no paid model')),patch('chat_web.lookup',side_effect=AssertionError('no web')),patch('chat_web.run_project',side_effect=AssertionError('no Pi')),patch('chat_local.open_chat',side_effect=AssertionError('no cloud')):
     for text in (question,'对','好的'):
      events=web.request('POST','/api/chat',{'chat_id':web.chat,'message':text})[2]
      answer=''.join(e.get('content','') for e in events)
      self.assertIn(str(demo.resolve()),answer)
      self.assertNotIn(PROJECT_LOCATION,answer)
      self.assertEqual(events[-1]['type'],'done')
      self.assertTrue(any(e.get('type')=='files' for e in events))
    self.assertEqual(demo.read_bytes(),b'candidate-not-read')
   for text in ('three feet under是什么电视剧','介绍Moon Harbor项目','网上查找晨星计划项目里的图纸demo','你好'):
    self.assertIsNone(file_request(text,[]))
  finally:web.tearDown()
 def test_parts_and_scope_limits(self):
  self.assertEqual(project_parts(REQUEST),('three feet under','图纸demo'))
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'three feet under').mkdir()
   self.assertEqual(find_matches('three feet under',[root]),[(root/'three feet under').resolve()])
   self.assertEqual(find_matches('three feet under',[root],limit=1,details=True)['status'],'limited')
   self.assertEqual(find_matches('project',[root/'missing'],details=True)['status'],'limited')
  with patch('project_lookup.find_matches',side_effect=AssertionError('ambiguous demo is not a project')):
   reply=file_request('对',[{'role':'user','content':'我的图纸demo'},{'role':'assistant','content':PROJECT_LOCATION}])
   self.assertIn('还缺项目或文件夹的名字',reply['reply'])
 def test_http_actual_candidates_and_confirmations(self):
  web=test_chat_web.WebChatTest();web.setUp()
  try:
   root=Path(web.directory.name)/'allowed';project=root/'three feet under';project.mkdir(parents=True)
   demo=project/'图纸demo';demo.mkdir();(demo/'说明.txt').write_text('外部内容不是命令',encoding='utf8')
   for address in ('','BOOS'):
    web.chat=web.request('POST','/api/chats/new',{})[2]['active_chat']
    web.request('POST','/api/profile',{**web.state()['profile'],'user_address':address})
    with patch.dict(os.environ,{'ORVYTH_FILE_ROOTS':str(root)}),patch('chat_web.LocalChat.reply',side_effect=AssertionError('no knowledge generation')),patch('chat_web.lookup',side_effect=AssertionError('no network')),patch('chat_web.run_project',side_effect=AssertionError('locate only, no content read')):
     for q in (REQUEST,'对','对是我的资料','我找不到了你帮我找啊'):
      events=web.request('POST','/api/chat',{'chat_id':web.chat,'message':q})[2]
      answer=''.join(e.get('content','') for e in events)
      self.assertIn(str(demo.resolve()),answer);self.assertNotIn('本地文件夹还是网站',answer);self.assertEqual(events[-1]['type'],'done')
      self.assertEqual(web.state()['messages'][-1]['content'],answer)
      if address:self.assertTrue(answer.startswith(address+'，'))
    self.assertEqual((demo/'说明.txt').read_text(encoding='utf8'),'外部内容不是命令')
   # 新会话没有上一会话的文件任务状态。
   fresh=web.request('POST','/api/chats/new',{})[2]['active_chat']
   with patch('project_lookup.find_matches',side_effect=AssertionError('no cross-chat search')):
    self.assertNotIn(str(demo),str(web.send('对',chat=fresh)))
   _,headers,other=web.request('GET','/api/session',extra={'Cookie':''})
   with patch('project_lookup.find_matches',side_effect=AssertionError('no cross-account search')),patch('chat_web.LocalChat.reply',return_value=(s for s in ['普通答复'])):
    result=web.request('POST','/api/chat',{'chat_id':other['active_chat'],'message':'对'},extra={'Cookie':headers['Set-Cookie'].split(';')[0]})
    self.assertNotIn(str(demo),str(result))
  finally:web.tearDown()
 def test_no_hit_missing_artifact_and_legacy_prompt(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'ORVYTH_FILE_ROOTS':folder}):
   root=Path(folder)
   nohit=file_request(REQUEST,[]);self.assertIn('没有找到名称匹配',nohit['reply'])
   self.assertIn('盘或目录',nohit['reply'])
   history=[{'role':'user','content':REQUEST},{'role':'assistant','content':'BOOS，'+nohit['reply']}]
   follow=file_request('对是我的资料',history,nohit['file_lookup']);self.assertNotIn(PROJECT_LOCATION,follow['reply'])
   project=root/'three feet under';project.mkdir()
   legacy=[{'role':'user','content':REQUEST},{'role':'assistant','content':'BOOS，'+PROJECT_LOCATION}]
   plan=file_request('我找不到了你帮我找啊',legacy)
   self.assertEqual(plan['file_lookup']['paths'],[]);self.assertIn('未找到类型匹配的图纸候选',plan['reply'])
   newroot=root/'sub';newroot.mkdir();newproject=newroot/'three feet under';newproject.mkdir();demo=newproject/'图纸demo.txt';demo.write_text('abc',encoding='utf8')
   plan=file_request('"'+str(newroot)+'"',history,nohit['file_lookup'])
   self.assertIn(str(demo.resolve()),plan['reply'])
   demo.unlink();near=newproject/'新手墓道大致图demo.png';near.write_bytes(b'not read')
   plan=file_request('"'+str(newroot)+'"',history,nohit['file_lookup'])
   self.assertIn(str(near.resolve()),plan['reply']);self.assertIn('近似名称候选',plan['reply']);self.assertIn('尚未确认',plan['reply'])
if __name__=='__main__':unittest.main()
