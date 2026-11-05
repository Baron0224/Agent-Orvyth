"""推理模型协议与正文/历史隔离，不使用真实模型生成测试答案。"""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chat_local import AVAILABLE_MODELS, DEFAULT_MODEL, LocalChat
from chat_web import ChatServer


class LocalModelsTest(unittest.TestCase):
    def generate(self, model, chunks):
        chat = LocalChat(model)
        response = io.BytesIO(b''.join(json.dumps(chunk).encode() + b'\n' for chunk in chunks))
        with patch('chat_local.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            answer = ''.join(chat.reply('只回答二加二等于几'))
            payload = json.loads(build.return_value.open.call_args.args[0].data)
        return chat, answer, payload

    def test_native_thinking_is_never_output_or_saved(self):
        chat, answer, payload = self.generate('deepseek-r1:7b', [
            {'message': {'thinking': 'internal only'}},
            {'message': {'content': '4'}, 'done': True},
        ])
        self.assertEqual(answer, '4')
        self.assertEqual(chat.history[-1]['content'], '4')
        self.assertTrue(payload['think'])
        self.assertGreater(payload['options']['num_predict'], 512)
        systems = [message for message in payload['messages'] if message['role'] == 'system']
        self.assertEqual(len(systems), 1)
        self.assertIn('暧昧期', systems[0]['content'])
        self.assertIn('deepseek-r1:7b', systems[0]['content'])

    def test_single_system_preserves_memory_and_history_without_old_style_instruction(self):
        chat = LocalChat(system_prompt='当前人格\n账户记忆：偏好简短')
        chat.display_name = '小团'
        chat.history = [{'role': 'user', 'content': '我学物理'}, {'role': 'assistant', 'content': '如有需要可提供建议'}]
        with patch('chat_local.urllib.request.build_opener') as build:
            build.return_value.open.return_value = io.BytesIO(b'{"message":{"content":"ok"},"done":true}\n')
            list(chat.reply('继续聊'))
            messages = json.loads(build.return_value.open.call_args.args[0].data)['messages']
        self.assertEqual(sum(message['role'] == 'system' for message in messages), 1)
        self.assertIn('账户记忆', messages[0]['content'])
        self.assertIn('小团', messages[0]['content'])
        self.assertEqual(messages[1]['content'], '我学物理')

    def test_old_tagged_content_split_across_chunks(self):
        for parts in (['<thi', 'nk>internal', '</th', 'ink>4'], ['internal', '</think>', '4']):
            chat, answer, _ = self.generate('deepseek-r1:7b', [
                *[{'message': {'content': part}} for part in parts], {'done': True},
            ])
            self.assertEqual(answer, '4')
            self.assertEqual(chat.history[-1]['content'], '4')

    def test_no_final_answer_fails_without_history(self):
        for chunk in (
            {'message': {'content': '<think>unfinished'}, 'done': True},
            {'message': {'thinking': 'internal only'}, 'done': True},
            {'message': {'content': 'unfinished answer'}, 'done': True, 'done_reason': 'length'},
        ):
            chat = LocalChat('deepseek-r1:7b')
            raw = json.dumps(chunk).encode() + b'\n'
            with patch('chat_local.urllib.request.build_opener') as build:
                build.return_value.open.return_value = io.BytesIO(raw)
                output = []
                with self.assertRaises(RuntimeError):
                    for part in chat.reply('test'):
                        output.append(part)
            self.assertEqual(output, [])
            self.assertEqual(chat.history, [])

    def test_qwen_remains_available_with_thinking_disabled(self):
        self.assertEqual(DEFAULT_MODEL, 'deepseek-r1:7b')
        self.assertIn('qwen3:4b-instruct', AVAILABLE_MODELS)
        _, answer, payload = self.generate('qwen3:8b', [{'message': {'content': '4'}, 'done': True}])
        self.assertEqual(answer, '4')
        self.assertFalse(payload['think'])

    def test_pi_keeps_existing_qwen_tool_model(self):
        with tempfile.TemporaryDirectory() as folder:
            for model, expected in [('deepseek-r1:7b', 'qwen3:8b'), ('qwen3:4b-instruct', 'qwen3:4b-instruct')]:
                server = ChatServer(0, model, Path(folder) / 'test.sqlite3')
                try:
                    self.assertEqual(server.tool_model, expected)
                finally:
                    server.server_close()


if __name__ == '__main__':
    unittest.main()
