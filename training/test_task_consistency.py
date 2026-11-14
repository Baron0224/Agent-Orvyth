"""Completion state must follow the tool record, never the model's claim."""
import tempfile
import json
import shutil
import subprocess
import unittest
from functools import partial
from pathlib import Path
from unittest.mock import patch

from chat_web import ChatServer
from task_trace import TaskTrace
import test_chat_web


@unittest.skipUnless(shutil.which('node'), '需要 Node.js')
class PiBridgeFinalTests(unittest.TestCase):
    def run_bridge(self, content, first, second):
        bridge = Path(__file__).with_name('pi') / 'bridge.mjs'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'orvyth测试.txt'
            target.write_text(content, encoding='utf8')
            source = bridge.read_text(encoding='utf8')
            for name in ('project-path.mjs', 'docx-tools.mjs'):
                source = source.replace(f"'./{name}'", repr((bridge.parent / name).as_uri()))
            source = source.replace('import.meta.url', json.dumps(bridge.as_uri()))
            source = source.replace("'@earendil-works/pi-coding-agent'", "'./sdk.mjs'")
            script = root / 'bridge.mjs'
            script.write_text(source, encoding='utf8')
            (root / 'sdk.mjs').write_text(f"""
export const createExtensionRuntime = () => null;
export const ModelRuntime = {{create: async () => ({{getModel() {{}}}})}};
export const SessionManager = {{inMemory() {{}}}};
export const SettingsManager = SessionManager;
export const loadSkillsFromDir = () => [];
export async function createAgentSession({{customTools}}) {{
 let calls = 0;
 return {{session: {{
  messages: [], subscribe() {{}}, dispose() {{}},
  async prompt(prompt) {{
   if (++calls === 1) {{
    const reader = customTools.find(tool => tool.name === 'read_project');
    await reader.execute('read', {{path: {json.dumps(target.name)}}});
   }} else {{
    if (calls !== 2 || !prompt.includes({json.dumps(content)})) throw new Error('未按原文追问一次');
   }}
   this.messages.push({{role:'assistant',stopReason:'stop',content:[{{type:'text',
    text: calls === 1 ? {json.dumps(first)} : {json.dumps(second)}}}]}});
  }}
 }}}};
}}
""", encoding='utf8')
            question = f'读取 "{target}"，只告诉我这份文本写了什么'
            request = dict(folder=directory, task=f'用户要求：{question}', model='qwen3:8b',
                           onlyFile=target.name, verifyFinal=True)
            result = subprocess.run(['node', str(script)], input=json.dumps(request).encode(),
                                    capture_output=True, timeout=20)
            return [json.loads(line) for line in result.stdout.decode('utf8').splitlines()]

    def test_short_text_retry_contains_actual_tool_content(self):
        events = self.run_bridge('核心路径实测', '无法读取', '核心路径实测')
        self.assertEqual(events[-1], {'type': 'done', 'content': '核心路径实测'})

    def test_long_text_keeps_model_answer(self):
        events = self.run_bridge('长' * 121, '模型总结', '')
        self.assertEqual(events[-1], {'type': 'done', 'content': '模型总结'})


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

    def test_local_final_result_controls_saved_answer_and_task_state(self):
        self.web.server.verify_pi_final = True
        read = {'type': 'tool', 'name': 'read_project', 'path': self.file.name}
        old_delta = {'type': 'delta', 'content': '我无法读取这个文件。'}
        for events, expected_state, expected_text in (
            ([read, {'type': 'done', 'content': '文件路径或文件名可能存在错误。'}],
             'failed', '工具已成功读取文件，但最终回答没有用上读取结果'),
            ([read, {'type': 'done', 'content': '我没读到这个文件。'}],
             'failed', '工具已成功读取文件，但最终回答没有用上读取结果'),
            ([read, old_delta, {'type': 'done', 'content': '文件里写的是核心路径实测。'}],
             'completed', '文件里写的是核心路径实测。'),
            ([old_delta, {'type': 'error', 'message': '本次没有成功读取文件'}],
             'failed', '本次没有成功读取文件'),
        ):
            with self.subTest(state=expected_state, events=events):
                with patch('chat_web.run_project', return_value=(event for event in events)) as run:
                    response = self.send(f'读取"{self.file}"')
                self.assertTrue(run.call_args.kwargs['verify_final'])
                text = ''.join(event.get('content', '') for event in response)
                self.assertIn(expected_text, text)
                self.assertNotIn(old_delta['content'], text)
                self.assertEqual(self.last_task(response)['state'], expected_state)
                saved = self.web.state()['messages'][-1]
                self.assertEqual(saved['content'], text)
                self.assertEqual(saved['task_trace']['state'], expected_state)
                if expected_state == 'failed':
                    self.assertNotIn('核心路径实测', text)
                    self.assertTrue(all(event['task']['state'] != 'completed'
                                        for event in response if event['type'] == 'task'))


if __name__ == '__main__':
    unittest.main()
