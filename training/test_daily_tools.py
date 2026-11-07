import unittest
from unittest.mock import patch
from weather_tool import weather_city,current_weather
from web_lookup import search_query,guarded_followup
import test_chat_web
class DailyToolsTest(unittest.TestCase):
 def test_city_context_without_account_location(self):
  self.assertIn('哪座城市',weather_city('今天的天气怎么样',[])['answer'])
  self.assertEqual(weather_city('截图大连天气怎么样',[])['city'],'大连')
  self.assertEqual(weather_city('天气怎么样',[{'role':'user','content':'我在大连'}])['city'],'大连')
  with patch('weather_tool.request_json',side_effect=OSError('offline')):self.assertEqual(current_weather('大连')['kind'],'weather_failure')
 def test_flow_food_weather_and_registration(self):
  from live_news import evidence_answer
  self.assertIn('同名站点',evidence_answer({'kind':'web','query':'steam official website','verified_page':{'title':'Oferty pracy i rekrutacja dla firm | Steam','url':'https://steam.jobs/pl/'}},'给我steam网站'))
  self.assertEqual(search_query('我怎么注册steam账号'),'steam create account official support')
  self.assertIsNone(search_query('不要联网，我怎么注册steam账号'))
  web=test_chat_web.WebChatTest();web.setUp()
  try:
   with patch('chat_web.lookup',side_effect=AssertionError('not generic search')),patch('chat_web.LocalChat.reply',side_effect=AssertionError('no invented shops')):
    for q in ('我想去吃饭','我不知道吃啥'):
     answer=''.join(e.get('content','') for e in web.request('POST','/api/chat',{'chat_id':web.chat,'message':q})[2]);self.assertIn('口味',answer) if q=='我不知道吃啥' else self.assertIn('面',answer);self.assertNotIn('大连',answer)
    events=web.request('POST','/api/chat',{'chat_id':web.chat,'message':'今天的天气怎么样'})[2];self.assertIn('哪座城市',''.join(e.get('content','') for e in events))
   with patch('chat_web.current_weather',side_effect=AssertionError('must not network')):
    events=web.request('POST','/api/chat',{'chat_id':web.chat,'message':'不要联网，查大连天气'})[2];self.assertIn('不联网',''.join(e.get('content','') for e in events))
  finally:web.tearDown()
 def test_continuous_pending_intents_and_owner_isolation(self):
  web=test_chat_web.WebChatTest();web.setUp()
  def send(q,chat=None,extra=None):
   events=web.request('POST','/api/chat',{'chat_id':chat or web.chat,'message':q},extra=extra)[2]
   self.assertEqual(events[-1]['type'],'done')
   answer=''.join(e.get('content','') for e in events)
   if not extra:self.assertEqual(web.state()['messages'][-1]['content'],answer)
   return answer
  def weather(city,**kw):return {'kind':'weather','query_city':city,'district':kw.get('district',''),'answer':city+' 城市坐标数据；区内天气未核实；'+str(kw.get('correction',False)),'current':{'time':'test'}}
  try:
   with patch('chat_web.LocalChat.reply',side_effect=AssertionError('must not invent facts')),patch('chat_web.lookup',side_effect=AssertionError('no generic search')),patch('chat_web.current_weather',side_effect=weather) as tool:
    self.assertIn('哪座城市',send('我今天天气怎么样'))
    self.assertIn('城市坐标',send('大连市甘井子区'));self.assertEqual(tool.call_args.args,('大连市',));self.assertEqual(tool.call_args.kwargs['district'],'甘井子区')
    send('沙河口区');self.assertEqual(tool.call_args.kwargs['district'],'沙河口区')
    self.assertIn('True',send('但手机说下雨'));self.assertTrue(tool.call_args.kwargs['correction'])
    self.assertEqual(tool.call_count,3)
    self.assertIn('面',send('我想吃饭'));self.assertIn('口味',send('我不知道吃啥'))
    self.assertIn('饺子',send('饺子？'));self.assertIn('食材',web.state()['messages'][-1]['content'])
    self.assertIn('预算',send('帮我找几家餐厅'))
    self.assertIn('模式',send('我在打三角洲推荐什么图'))
    correction=send('哪有这些图呢');self.assertIn('地图',correction);self.assertIn('模式',correction);self.assertNotIn('来源记录',correction)
    other=web.request('GET','/api/session',extra={'Cookie':''})
    cookie=other[1]['Set-Cookie'].split(';')[0];other_chat=other[2]['active_chat']
    self.assertIn('哪座城市',send('沙河口区天气',other_chat,{'Cookie':cookie}))
    self.assertNotIn('大连',web.server.store.latest_search_evidence(web.server.store.key(cookie.split('=',1)[1]),other_chat).get('query_city',''))
   source={'kind':'web','items':[{'title':'测试资料','snippet':'地图原文只包含测试信息','url':'https://example.org/maps'}]}
   with patch('chat_web.lookup',return_value=source) as lookup,patch('chat_web.LocalChat.reply',side_effect=AssertionError('do not invent maps')):
    self.assertIn('原文只包含测试信息',send('烽火地带'));self.assertIn('三角洲',lookup.call_args.args[0]);self.assertIn('烽火地带',lookup.call_args.args[0])
   evidence=web.server.store.latest_search_evidence(web.server.store.key(web.cookie.split('=',1)[1]),web.chat)
   self.assertIn('三角洲',evidence['game_topic']);self.assertEqual(evidence['items'][0]['url'],'https://example.org/maps')
   with patch('chat_web.lookup',return_value=None),patch('chat_web.LocalChat.reply',side_effect=AssertionError('search failure must not invent maps')):
    self.assertIn('没拿到资料',send('哪有这些图呢'))
   evidence=web.server.store.latest_search_evidence(web.server.store.key(web.cookie.split('=',1)[1]),web.chat)
   self.assertIn('三角洲',evidence['game_topic']);self.assertEqual(evidence['kind'],'failure')
  finally:web.tearDown()
 def test_weather_scope_and_correction_data(self):
  place={'name':'大连市','country':'中国','admin1':'辽宁','latitude':38.9,'longitude':121.6,'feature_code':'PPL'}
  data={'current':{'time':'2026-11-07T15:00','temperature_2m':6,'precipitation':0.1},'current_units':{'temperature_2m':'°C','precipitation':'mm'},'timezone':'Asia/Shanghai','utc_offset_seconds':28800}
  with patch('weather_tool.request_json',side_effect=[{'results':[place]},data]):
   result=current_weather('大连市','沙河口区',True)
  self.assertIn('尚未核实',result['answer']);self.assertIn('城市坐标',result['answer']);self.assertIn('0.1mm',result['answer']);self.assertNotIn('晴',result['answer']);self.assertIn('2026-11-07T15:00',result['answer'])
  self.assertIsNone(weather_city('我今天很累',[],result))
if __name__=='__main__':unittest.main()
