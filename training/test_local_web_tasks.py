"""Isolated regression; fixtures are not real account records or live acceptance."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import local_web_tasks as tasks
from browser_store import Store, MissingRecord


class LocalTasksTests(unittest.TestCase):
    def test_create_slots_exact_content_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(tasks, 'desktop_folder', return_value=Path(directory)), patch('file_write.desktop_folder', return_value=Path(directory)):
                first = tasks.route('在桌面建一个测试文件，名字叫 orvyth测试.txt，里面写核心路径实测')
                self.assertEqual(first['local_text_write']['content'], '核心路径实测')
                steps = []
                tasks.create_text(first['local_text_write'], lambda *step: steps.append(step))
                target = Path(directory) / 'orvyth测试.txt'
                self.assertEqual(target.read_bytes(), '核心路径实测'.encode())
                with self.assertRaises(FileExistsError):
                    tasks.create_text(first['local_text_write'], lambda *step: None)
                self.assertEqual(target.read_bytes(), '核心路径实测'.encode())
                pending = tasks.route('在桌面新建一个文件，文件名是“补充.txt”')
                self.assertNotIn('文件名、', pending['reply'])
                complete = tasks.route('内容是“第二轮内容”', pending['file_lookup'])
                self.assertEqual(complete['local_text_write']['name'], '补充.txt')
                self.assertEqual(complete['local_text_write']['content'], '第二轮内容')
                self.assertIsNone(tasks.route('今天天气怎么样', pending['file_lookup']))
                self.assertIn('文件名不能', tasks.route('在桌面建一个文件，名字叫 ../越界.txt，里面写x')['reply'])
                self.assertNotIn('local_text_write', tasks.route('不要在桌面创建文件，名字叫x，内容是y'))

    def test_create_with_bare_jian_and_bare_filename(self):
        plan = tasks.route('在桌面建 x测试.txt，里面写内容', None)
        self.assertIn('local_text_write', plan)
        self.assertEqual(plan['local_text_write']['name'], 'x测试.txt')
        self.assertEqual(plan['local_text_write']['content'], '内容')
        self.assertEqual(plan['local_text_write']['path'], str((tasks.desktop_folder() / 'x测试.txt').resolve()))

    def test_candidates_short_fragment_selection_restart_and_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('简历甲.png', '简历乙.png'):
                (root / name).write_bytes(b'fixture, not a real image')
            result = tasks.route(f'在 "{root}" 找简历文件')
            state = result['file_lookup']
            self.assertEqual(len(state['paths']), 2)
            selected = tasks.route('第二个', state)['file_lookup']
            self.assertEqual(selected['selected_index'], 1)
            expected = state['paths'][1]
            self.assertIn(expected, tasks.route('继续', selected)['reply'])
            self.assertIn('列表内', tasks.route('第9个', state)['reply'])
            returned = tasks.route('返回候选列表', selected)['file_lookup']
            self.assertIsNone(returned['selected_index'])
            cancelled = tasks.route('取消', selected)['file_lookup']
            self.assertIn('没有可接续', tasks.route('继续', cancelled)['reply'])
            db = root / 'test.sqlite3'
            store = Store(db)
            _, owner = store.owner(create=True)
            chat = store.state(owner)['active_chat']
            store.save_pair(owner, chat, '找文件', result['reply'], search_evidence=selected)
            store.save_pair(owner, chat, '普通聊天', '普通回答')
            recovered = Store(db).latest_local_task(owner, chat)
            self.assertEqual(recovered['paths'][1], expected)
            self.assertEqual(recovered['selected_index'], 1)
            _, other = store.owner(create=True)
            with self.assertRaises(MissingRecord):
                store.latest_local_task(other, chat)
            self.assertIsNone(store.latest_local_task(other, store.state(other)['active_chat']))

    def test_send_is_clarification_and_unknown_facts_are_not_invented(self):
        reply = tasks.route('把那个文件发给龙哥')['reply']
        for text in ('哪个文件', '渠道', '收件人', '没有发送工具'):
            self.assertIn(text, reply)
        class Archive:
            is_command = staticmethod(lambda q: False)
            entries = staticmethod(lambda owner: [])
        for text in ('我叫什么、在哪上学', '我的高中班主任叫什么', '我的银行卡密码是什么'):
            self.assertIn('没有', tasks.personal_reply(Archive(), 'isolated', text))
        self.assertIsNone(tasks.personal_reply(Archive(), 'isolated', '我的文件是什么'))

    def test_cloud_other_ports_terminal_keep_original_route(self):
        self.assertTrue(tasks.enabled('ollama', 8775))
        self.assertTrue(tasks.enabled('deepseek', 8775))
        for provider, port in [('deepseek', 8776), ('ollama', 8776), ('ollama', 8765)]:
            self.assertFalse(tasks.enabled(provider, port))
        from file_write import write_request
        self.assertIn('请把文件名和内容', write_request('在桌面建一个测试文件，名字叫 orvyth测试.txt，里面写核心路径实测')['reply'])
        import chat_local
        self.assertNotIn('local_web_tasks', chat_local.__dict__)
        self.assertIsNone(tasks.route('帮我找 three feet under 项目里的图纸 demo，先只查找和预览，不修改任何文件'))

    def test_cloud_http_does_not_call_local_task_router(self):
        from functools import partial
        from chat_web import ChatServer
        import test_chat_web
        with patch('test_chat_web.ChatServer', partial(ChatServer, model='deepseek-cloud:deepseek-flash')):
            web = test_chat_web.WebChatTest()
            web.setUp()
        try:
            with patch('chat_web.local_web_tasks.route', side_effect=AssertionError('local route reached cloud')):
                events = web.request('POST', '/api/chat', {'chat_id': web.chat, 'message': '在桌面建一个测试文件，名字叫a.txt，里面写x'})[2]
            self.assertIn('请把文件名和内容', ''.join(e.get('content', '') for e in events))
        finally:
            web.tearDown()


if __name__ == '__main__':
    unittest.main()
