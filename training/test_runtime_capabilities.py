import unittest
from unittest.mock import patch
from runtime_capabilities import is_self_assessment
from web_lookup import search_query
import test_chat_web
class CapabilityTest(unittest.TestCase):
 def test_routing_and_boundaries(self):
  for q in ['我要给你加什么功能吗你查查你自己有没有什么优化的','你还需要补充什么','Orvyth有什么限制']:
   self.assertTrue(is_self_assessment(q));self.assertIsNone(search_query(q))
  for q in ['帮你查一下GitHub最新插件优化方案','联网搜索适合你的外部工具方案','你帮我查一下Python性能优化方案']:
   self.assertFalse(is_self_assessment(q));self.assertIsNotNone(search_query(q))
  self.assertIsNone(search_query('不要联网，查一下最新插件'))
  self.assertFalse(is_self_assessment('你觉得你牛逼吗'))
 def test_http_live_configuration_and_failure(self):
  web=test_chat_web.WebChatTest();web.setUp()
  try:
   web.request('POST','/api/profile',{**web.state()['profile'],'user_address':'BOOS'})
   for failure in [False,True]:
    with patch.object(web.server,'installed_models',side_effect=OSError('offline') if failure else None,return_value=[{'name':'qwen3:8b'}]),patch('chat_web.pi_available',return_value=not failure),patch('chat_web.lookup',side_effect=AssertionError('not web')),patch('chat_web.LocalChat.reply',side_effect=AssertionError('must not invent execution')):
     events=web.request('POST','/api/chat',{'chat_id':web.chat,'message':'我要给你加什么功能吗你查查你自己有没有什么优化的'})[2]
     answer=''.join(e.get('content','') for e in events)
     self.assertEqual(events[-1]['type'],'done');self.assertTrue(answer.startswith('BOOS，'));self.assertIn('建议',answer);self.assertIn('还没有执行',answer);self.assertNotIn('我已经调整',answer)
     if failure:self.assertIn('工具模型未就绪',answer);self.assertIn('服务未就绪',answer)
     else:self.assertIn('依赖和工具模型已安装',answer)
     self.assertEqual(web.state()['messages'][-1]['content'],answer)
  finally:web.tearDown()
if __name__=='__main__':unittest.main()
