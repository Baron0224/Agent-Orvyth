import io,json,unittest
from unittest.mock import patch
from reply_format import plan_for,arrange
from chat_local import LocalChat
class FormatTest(unittest.TestCase):
 def test_scope_and_unambiguous_blocks(self):
  entries=[{'category':'preference','content':'我学习编程要先给例子再解释'}]
  self.assertEqual(plan_for(entries,'请教我编程中的变量'),('示例','解释'))
  for q in ['我今天很累','请解释法国历史','你好','这次请先解释编程再举例']:self.assertIsNone(plan_for(entries,q))
  raw='## 解释\n说明原文。\n\n## 示例\n```python\nprint(1)\n```'
  out,status=arrange(raw,('示例','解释'));self.assertEqual(status,'reordered');self.assertTrue(out.startswith('## 示例'));self.assertIn('print(1)\n```',out);self.assertTrue(out.endswith('说明原文。'))
  for raw in ['概念在前但没有分段。','前言含实质内容\n## 解释\n内容\n## 示例\n内容','## 示例\nA\n## 解释\nB\n## 示例\nC','## 示例\nA\n## 解释\nB\n## 其他\nC']:
   self.assertEqual(arrange(raw,('示例','解释')),(raw,'unverified'))
 def test_model_once_and_history_matches(self):
  chat=LocalChat('deepseek-r1:7b');chat.memory_context=json.dumps([{'category':'preference','content':'我学习编程要先例子再解释'}])
  raw='## 解释\n原解释。\n## 示例\n原示例。'
  with patch('chat_local.urllib.request.build_opener') as build:
   build.return_value.open.return_value=io.BytesIO((json.dumps({'message':{'content':raw},'done':True})+'\n').encode())
   answer=''.join(chat.reply('请教我编程变量'));self.assertEqual(build.return_value.open.call_count,1)
  self.assertTrue(answer.startswith('## 示例'));self.assertEqual(chat.history[-1]['content'],answer);self.assertEqual(chat.format_check,'reordered')
if __name__=='__main__':unittest.main()
