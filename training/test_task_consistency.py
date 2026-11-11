"""Completion state must follow the tool record, never the model's claim."""
import tempfile
import unittest
from functools import partial
from pathlib import Path
from unittest.mock import patch

from chat_web import ChatServer
from task_trace import TaskTrace
import test_chat_web


class TaskTraceTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / 'orvyth测试.txt'
        self.file.write_text('核心路径实测', encoding='utf-8')
        self.trace = TaskTrace(self.events.append)

    def test_read_record_overrides_false_failure_claim(self):
        self.trace.tool({'name': 'read_project', 'path': self.file.name}, self.directory.name)
        answer = self.trace.reconcile('我无法读取这个文件。', self.file.name)
        self.assertIn('核心路径实测', answer)
        self.assertIn(str(self.file.resolve()), answer)
        self.assertNotIn('无法读取', answer)

    def test_consistent_answer_is_kept(self):
        self.trace.tool({'name': 'read_project', 'path': self.file.name}, self.directory.name)
        self.assertEqual(self.trace.reconcile('文件里写的是核心路径实测。', self.file.name), '文件里写的是核心路径实测。')

    def test_read_claim_without_read_record_fails(self):
        with self.assertRaises(RuntimeError):
            self.trace.reconcile('我已经读取了文件，里面写着核心路径实测。', self.file.name)

    def test_list_only_never_counts_as_reading(self):
        self.trace.tool({'name': 'list_project', 'path': '.'}, self.directory.name)
        with self.assertRaises(RuntimeError):
            self.trace.reconcile('文件内容是核心路径实测。', self.file.name)

    def test_failure_claim_without_readable_text_fails(self):
        broken = Path(self.directory.name) / 'broken.txt'
        broken.write_bytes(b'\xff\xfe')
        self.trace.tool({'name': 'read_project', 'path': broken.name}, self.directory.name)
        with self.assertRaises(RuntimeError):
            self.trace.reconcile('我无法读取这个文件。', broken.name)


class StreamConsistencyTests(unittest.TestCase):
    def setUp(self):
        with patch('test_chat_web.ChatServer', partial(ChatServer, model='qwen3:8b')):
            self.web = test_chat_web.WebChatTest()
            self.web.setUp()
        self.addCleanup(self.web.tearDown)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / 'orvyth测试.txt'
        self.file.write_text('核心路径实测', encoding='utf-8')

    def send(self, message):
        status, _, events = self.web.request('POST', '/api/chat', {'chat_id': self.web.chat, 'message': message})
        self.assertEqual(status, 200)
        return events

    def last_task(self, events):
        tasks = [event['task'] for event in events if event['type'] == 'task']
        self.assertTrue(tasks, events)
        return tasks[-1]

    def test_missing_file_is_reported_failed(self):
        events = self.send(f'读取"{Path(self.directory.name) / "没有这个文件.txt"}"')
        # 口吻定版（VOICE.md v1）：失败告知改为“这个路径我没找到…”，信息要素不变。
        self.assertIn('这个路径我没找到', ''.join(event.get('content', '') for event in events))
        self.assertEqual(self.last_task(events)['state'], 'failed')
        self.assertEqual(self.web.state()['messages'][-1]['task_trace']['state'], 'failed')

    def fake_stream(self, answer, tool=('read_project', 'orvyth测试.txt')):
        def results():
            if tool:
                yield {'type': 'tool', 'name': tool[0], 'path': tool[1]}
            yield {'type': 'delta', 'content': answer}
            yield {'type': 'done'}
        return results()

    def test_tool_read_contradicted_by_reply_still_shows_real_content(self):
        with patch('chat_web.run_project', return_value=self.fake_stream('我无法读取这个文件。')):
            events = self.send(f'读取"{self.file}"')
        text = ''.join(event.get('content', '') for event in events)
        self.assertIn('核心路径实测', text)
        self.assertEqual(self.last_task(events)['state'], 'completed')

    def test_reply_claiming_read_without_tool_fails(self):
        with patch('chat_web.run_project', return_value=self.fake_stream('我已经读取了文件，内容很深奥。', tool=('list_project', '.'))):
            events = self.send(f'读取"{self.file}"')
        text = ''.join(event.get('content', '') for event in events)
        self.assertIn('任务未完成', text)
        self.assertEqual(self.last_task(events)['state'], 'failed')

    def test_normal_read_completes(self):
        with patch('chat_web.run_project', return_value=self.fake_stream('文件里写的是核心路径实测。')):
            events = self.send(f'读取"{self.file}"')
        self.assertEqual(self.last_task(events)['state'], 'completed')
        self.assertEqual(self.web.state()['messages'][-1]['task_trace']['state'], 'completed')


if __name__ == '__main__':
    unittest.main()