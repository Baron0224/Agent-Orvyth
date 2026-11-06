import unittest
from unittest.mock import patch
from web_lookup import search_query, source_context, lookup, _cache, relevant
import test_chat_web

class AutoSearchTest(unittest.TestCase):
 def test_decisions_and_private_followup(self):
  for q in ('今天很开心','我想找个人聊天','17乘以23','什么是变量','不要联网，查一下最新版本','查一下我的API key abc','查一下我的邮箱'):
   self.assertIsNone(search_query(q),q)
  for q in ('查找Python官方文档','北京今天天气','现在黄金价格多少','核实这条消息','Python最新版本','找一篇论文介绍量子计算'):
   self.assertIsNotNone(search_query(q),q)
  self.assertEqual(search_query('那现在价格呢',[{'role':'user','content':'查一下RTX 4060价格'}]),'查一下RTX 4060价格；那现在价格呢')
  self.assertIsNone(search_query('那现在价格呢',[{'role':'user','content':'我的账号123'}]))
 def test_source_data_has_no_automatic_links(self):
  self.assertFalse(relevant('搜索 Python 官方下载',{'title':'Steam游戏','snippet':'武林游戏','url':'https://steam.com'}))
  self.assertTrue(relevant('搜索 Python 官方下载',{'title':'Python downloads','snippet':'Python','url':'https://python.org'}))
  source={'url':'https://example.org','extract':'证据','items':[{'url':'https://example.org','published':None,'snippet':'片段'}]}
  self.assertNotIn('https://',source_context(source))
  self.assertIn('https://',source_context(source,True))
 def test_routing_failure_stream_and_evidence(self):
  web=test_chat_web.WebChatTest();web.setUp()
  try:
   with patch('chat_web.lookup',side_effect=AssertionError('must not search')):
    self.assertEqual(web.send('不要联网，查一下Python最新版本')[0],200)
    self.assertEqual(web.send('今天很开心')[0],200)
   with patch('chat_web.lookup',return_value=None):
    events=web.send('联网查找Python最新版本')[2]
    self.assertEqual(events[0]['type'],'status');self.assertIn('没能取得',events[1]['content'])
   source={'kind':'web','extract':'Python官方文档','items':[{'title':'Python','url':'https://docs.python.org','snippet':'官方文档','published':None}],'fetched_at':'2026-11-06'}
   with patch('chat_web.lookup',return_value=source):
    events=web.send('查找Python官方文档')[2]
   self.assertEqual([e['type'] for e in events],['status','delta','done'])
   with web.server.store.connect() as db:
    saved=db.execute('SELECT search_evidence FROM messages ORDER BY id DESC LIMIT 1').fetchone()[0]
   self.assertIn('docs.python.org',saved)
   self.assertEqual(web.state()['messages'][-1]['content'],'测试回答')
   with patch('chat_web.lookup',return_value=source), patch('chat_web.LocalChat.reply',side_effect=AssertionError('undated summaries must not establish latest facts')):
    guarded=web.request('POST','/api/chat',{'chat_id':web.chat,'message':'Python最新版本'})[2]
   self.assertIn('不足以确认', ''.join(e.get('content','') for e in guarded))
  finally:web.tearDown()

if __name__=='__main__':unittest.main()
