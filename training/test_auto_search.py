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
  self.assertEqual(search_query('那现在价格呢',[{'role':'user','content':'查一下RTX 4060价格'}]),'RTX 4060价格')
  self.assertIsNone(search_query('那现在价格呢',[{'role':'user','content':'我的账号123'}]))
 def test_followup_and_news_do_not_expand(self):
  from live_news import evidence_answer
  self.assertEqual(search_query('帮我查一下“Blender”'),'Blender')
  self.assertEqual(search_query('它的官网呢？',[{'role':'user','content':'帮我查一下 Blender'}]),'Blender')
  self.assertIsNone(search_query('不要联网，它的官网呢？',[{'role':'user','content':'帮我查一下 Blender'}]))
  title='Two dead after bus crashes in France, officials say'
  source={'kind':'news','items':[{'title':title,'published':'2026-11-06','url':'https://bbc.co.uk/a','description':'One child and one young adult were killed.'}]}
  answer=evidence_answer(source,'今天新闻')
  self.assertIn(title,answer);self.assertNotIn('乘客',answer);self.assertNotIn('https://',answer)
  self.assertIn('https://',evidence_answer(source,'今天新闻来源'))
 def test_news_scope_follows_owner_evidence_without_search(self):
  from live_news import lookup_news, FEED
  source={'kind':'news','title':'BBC World 2026-11-07','url':FEED,'items':[{'title':'Original headline','published':'2026-11-07','url':'https://www.bbc.co.uk/a'}]}
  web=test_chat_web.WebChatTest();web.setUp()
  try:
   with patch('chat_web.lookup',return_value=source):web.send('今天新闻')
   with patch('chat_web.lookup',side_effect=AssertionError('clarification must not search')),patch('chat_web.LocalChat.reply',side_effect=AssertionError('do not guess scope')):
    for q in ('这是中国的新闻吗','这些是国内新闻吗','这是哪的新闻','刚才是什么来源','刚才查的是什么来源','这几条都是中国的吗'):
     events=web.request('POST','/api/chat',{'chat_id':web.chat,'message':q})[2]
     answer=''.join(e.get('content','') for e in events)
     self.assertIn('国际新闻列表',answer);self.assertNotIn('Original headline',answer)
   self.assertEqual(lookup_news('帮我查今天中国新闻')['reason'],'unsupported_region')
   with patch('chat_web.lookup',wraps=lookup_news):
    answer=''.join(e.get('content','') for e in web.send('帮我查今天中国新闻')[2])
   self.assertIn('不能拿 BBC 国际新闻列表代替',answer)
   fresh=web.request('POST','/api/chats/new',{})[2]['active_chat']
   with patch('chat_web.lookup',side_effect=AssertionError('new chat has no evidence')):
    events=web.request('POST','/api/chat',{'chat_id':fresh,'message':'这些是国内新闻吗'})[2]
   self.assertIn('没有可核对的来源',''.join(e.get('content','') for e in events))
   _,headers,data=web.request('GET','/api/session',extra={'Cookie':''})
   cookie=headers['Set-Cookie'].split(';')[0]
   status,_,_=web.request('POST','/api/chat',{'chat_id':web.chat,'message':'这是中国新闻吗'},extra={'Cookie':cookie})
   self.assertNotEqual(status,200)
   with patch('chat_web.lookup',side_effect=AssertionError('must not search')):
    events=web.request('POST','/api/chat',{'chat_id':data['active_chat'],'message':'这是中国新闻吗'},extra={'Cookie':cookie})[2]
   self.assertIn('没有可核对的来源', ''.join(e.get('content','') for e in events))
  finally:web.tearDown()
 def test_brand_and_short_confirmation_guards(self):
  from web_lookup import brand_matches, guarded_followup
  history=[{'role':'user','content':'deepseek的官网链接'},{'role':'assistant','content':'已读取网站页面'}]
  self.assertEqual(search_query('那chatgpt的呢',history),'chatgpt official website')
  self.assertEqual(search_query('那给我chatgpt的网址',history),'chatgpt official website')
  self.assertFalse(brand_matches('chatgpt official website','https://chatbotarena.com/','Chatbot Arena'))
  self.assertFalse(brand_matches('chatgpt official website','https://bad.example/chatgpt-alternative','ChatGPT alternative'))
  self.assertFalse(brand_matches('chatgpt official website','https://example.org/chatgpt','ChatGPT'))
  self.assertTrue(brand_matches('chatgpt official website','https://chatgpt.com/','ChatGPT'))
  dining=[{'role':'user','content':'中餐推荐呢大连'},{'role':'assistant','content':'要不要我帮你找几家靠谱的店？'}]
  self.assertIn('预算',guarded_followup('要',dining,None))
  self.assertIsNone(guarded_followup('要',[],None))
  self.assertIsNone(guarded_followup('要',[{'role':'assistant','content':'要不要休息？'}],None))
  web=test_chat_web.WebChatTest();web.setUp()
  try:
   source={'kind':'news','items':[{'title':'Original title only','published':'2026-11-07','url':'https://bbc.co.uk/a'}]}
   with patch('chat_web.lookup',return_value=source):web.send('今天新闻')
   with patch('chat_web.lookup',side_effect=AssertionError('must not search')),patch('chat_web.LocalChat.reply',return_value=iter(['["仅标题译文"]'])):
    answer=''.join(e.get('content','') for e in web.request('POST','/api/chat',{'chat_id':web.chat,'message':'能给我翻译成中文吗'})[2])
    self.assertIn('原文：Original title only',answer)
    answer=''.join(e.get('content','') for e in web.request('POST','/api/chat',{'chat_id':web.chat,'message':'不要联网，给我ChatGPT的网址'})[2])
    self.assertIn('没有联网',answer)
  finally:web.tearDown()
 def test_keyless_headers_and_rate_limit(self):
  import json,urllib.error
  response=json.dumps({'results':[{'title':'Example topic','url':'https://example.org','content':'Example topic evidence'}]}).encode()
  _cache.clear()
  with patch.dict('os.environ',{'TAVILY_API_KEY':''}),patch('web_lookup._request',return_value=response) as request,patch('web_lookup.read_result_pages',return_value=[]):
   self.assertEqual(lookup('Example topic')['provider'],'Tavily keyless')
   self.assertEqual(request.call_args.args[2]['X-Tavily-Access-Mode'],'keyless')
  _cache.clear()
  with patch.dict('os.environ',{'TAVILY_API_KEY':'test-value'}),patch('web_lookup._request',return_value=response) as request,patch('web_lookup.read_result_pages',return_value=[]):
   lookup('Example topic')
   self.assertNotIn('X-Tavily-Access-Mode',request.call_args.args[2])
   self.assertIn('Authorization',request.call_args.args[2])
  _cache.clear()
  with patch('web_lookup._request',side_effect=urllib.error.HTTPError('https://api.tavily.com',429,'rate limit',None,None)) as request:
   self.assertEqual(lookup('Example topic')['reason'],'rate_limited');self.assertEqual(request.call_count,1)
 def test_source_data_has_no_automatic_links(self):
  _cache.clear()
  with patch('web_lookup._request',side_effect=OSError('offline')), patch('web_lookup.discover_site',side_effect=AssertionError('no fixed-site bypass')):
   self.assertEqual(lookup('Blender')['kind'],'failure')
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
    self.assertEqual(events[0]['type'],'status');self.assertIn('检索服务暂时不可用',events[1]['content'])
   for reason,expected in (('unavailable','检索服务暂时不可用'),('no_related','没有找到与这个主题'),('no_news_date','没有收录指定发布日期')):
    with patch('chat_web.lookup',return_value={'kind':'failure','reason':reason}):
     failed=web.send('联网查找某个主题')[2]
    self.assertIn(expected,''.join(e.get('content','') for e in failed))
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
