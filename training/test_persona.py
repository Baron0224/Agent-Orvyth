import io,json,unittest
from pathlib import Path
from unittest.mock import patch
from chat_local import LocalChat,CONVERSATION_STYLE,role_info,model_info
from chat_preferences import addressed
from runtime_capabilities import assessment
class PersonaTest(unittest.TestCase):
 def test_shared_source_identity_and_old_context(self):
  self.assertEqual(CONVERSATION_STYLE,Path(__file__).with_name('PERSONA.md').read_text(encoding='utf-8-sig').strip())
  for history in ([],[{'role':'user','content':'过去的话'},{'role':'assistant','content':'我是客服机器人，没有任何感情。'}]):
   chat=LocalChat('deepseek-r1:7b');chat.display_name='小白';chat.user_address='BOOS';chat.history=history
   with patch('chat_local.urllib.request.build_opener') as build:
    build.return_value.open.return_value=io.BytesIO((json.dumps({'message':{'content':'先把今天这件小事交给我。'},'done':True})+'\n').encode())
    answer=''.join(chat.reply('今天想被你宠一下'));messages=json.loads(build.return_value.open.call_args.args[0].data)['messages']
   self.assertIn(CONVERSATION_STYLE,messages[0]['content']);self.assertIn('私人AI秘书',messages[0]['content']);self.assertNotIn('Orvyth AI陪伴者',messages[0]['content']);self.assertTrue(addressed(answer,'BOOS').startswith('BOOS，'))
  self.assertIn('私人 AI 秘书',role_info('你是谁','小白','BOOS'));self.assertIn('deepseek-r1:7b',model_info('你是什么模型','deepseek-r1:7b','小白'))
 def test_self_report_honest_not_derogatory(self):
  answer=assessment({'status':{'model':'test','ready':False},'registered':[],'pi_ready':False})
  self.assertIn('私人AI秘书',answer);self.assertIn('未就绪',answer);self.assertIn('还没有执行',answer);self.assertNotIn('我不行',answer);self.assertNotIn('我已经',answer)
if __name__=='__main__':unittest.main()
