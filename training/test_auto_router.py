"""Smart routing v1: pure rules, no model call, explainable reasons."""
import unittest

import auto_router
from chat_web import ENGINES, ChatServer
from browser_store import Store
import tempfile
from pathlib import Path


class RuleTest(unittest.TestCase):
    def assertLocal(self, question):
        result = auto_router.choose(question)
        self.assertEqual(result['engine'], 'local', (question, result))
        self.assertTrue(result['reason'])

    def assertCloud(self, question, rule=None):
        result = auto_router.choose(question)
        self.assertEqual(result['engine'], 'deepseek', (question, result))
        if rule:
            self.assertEqual(result['rule'], rule, result)
        return result

    def test_small_talk_and_short_questions_stay_local(self):
        for question in ('你好呀', '今天过得怎么样', '谢谢', '几点了', '早安'):
            self.assertLocal(question)

    def test_facts_and_file_tasks_stay_local(self):
        for question in ('我叫什么、在哪上学', '在桌面建 orvyth测试.txt，里面写核心路径实测', '找一下我的简历文件'):
            self.assertLocal(question)

    def test_long_input_goes_cloud(self):
        question = '今天想和你慢慢说一件事。' * 30
        self.assertGreaterEqual(len(question), auto_router.LONG_INPUT)
        self.assertCloud(question, 'long')

    def test_code_goes_cloud(self):
        self.assertCloud('帮我看看这段 Python 为什么报错', 'code')
        self.assertCloud('这段代码怎么改 bug', 'code')

    def test_generation_goes_cloud(self):
        self.assertCloud('帮我写一篇关于春天的作文', 'generate')
        self.assertCloud('替我写一份活动方案', 'generate')

    def test_reasoning_goes_cloud(self):
        self.assertCloud('比较一下这两个方案，为什么一个更好', 'reason')
        self.assertCloud('给我规划一下学习步骤', 'reason')

    def test_explicit_request_wins(self):
        result = self.assertCloud('认真想想这个问题', 'explicit')
        self.assertIn('认真', result['reason'])

    def test_threshold_is_documented(self):
        self.assertEqual(auto_router.LONG_INPUT, 200)


class RouteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.tmp.name) / 'browser.sqlite3'))
        _, self.owner = self.store.owner(create=True)
        self.srv = object.__new__(ChatServer)
        self.srv.model = 'qwen3:8b'
        self.srv.store = self.store
        self.srv.server_port = 8775

    def tearDown(self):
        self.tmp.cleanup()

    def test_auto_route_is_per_message(self):
        self.srv.cloud_key_ready = lambda: True
        hard = self.srv.route_for(self.owner, '帮我分析一下这个方案的优缺点')
        easy = self.srv.route_for(self.owner, '你好')
        self.assertEqual(hard['model'], ENGINES['deepseek'])
        self.assertTrue(hard['auto'])
        self.assertEqual(easy['model'], ENGINES['local'])
        self.assertIn('简单', easy['reason'])

    def test_manual_local_ignores_hard_question(self):
        self.store.save_profile(self.owner, {'name': 'x', 'pet_name': 'y', 'chat_engine': 'local'})
        self.srv.cloud_key_ready = lambda: True
        route = self.srv.route_for(self.owner, '帮我分析一下这个方案的优缺点')
        self.assertEqual(route['model'], ENGINES['local'])
        self.assertFalse(route['auto'])


if __name__ == '__main__':
    unittest.main()