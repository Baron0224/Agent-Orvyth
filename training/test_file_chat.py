import tempfile
from pathlib import Path
import unittest
from file_chat import ASK_PATH, file_request

class FileChatTests(unittest.TestCase):
    def test_normal_chat_does_not_call_pi(self):
        self.assertIsNone(file_request('今天有点累', []))
        self.assertIsNone(file_request('Python文件是什么？', []))

    def test_missing_path_and_unrelated_followup(self):
        self.assertEqual(file_request('帮我读取README.md', [])['reply'], ASK_PATH)
        history=[{'role':'user','content':'帮我读取README.md'}, {'role':'assistant','content':ASK_PATH}]
        self.assertIsNone(file_request('先不看了，聊聊天', history))

    def test_quoted_spaces_and_followup(self):
        with tempfile.TemporaryDirectory() as base:
            target=Path(base)/'my notes.txt';target.write_text('hello',encoding='utf-8')
            plan=file_request(f'帮我读取 "{target}" 并总结', [])
            self.assertEqual(plan['only_file'], target.name)
            history=[{'role':'user','content':'帮我读取文件，概括用途'}, {'role':'assistant','content':ASK_PATH}]
            plan=file_request(f'"{target}"',history)
            self.assertIn('概括用途',plan['task'])
            self.assertEqual(plan['folder'],str(target.parent.resolve()))

    def test_missing_file_has_clear_reply(self):
        plan=file_request('帮我读取 Z:\\missing-orvyth-test\\file.txt',[])
        self.assertIn('没找到',plan['reply'])

    def test_named_project_content_requires_source_not_world_knowledge(self):
        for question in ('读取我three feet under中的故事背景大概讲了什么',
                         '帮我调取 Three Feet Under 的故事背景',
                         '看一下我three feet under中的故事背景'):
            with self.subTest(question=question):
                self.assertEqual(file_request(question, [])['reply'], ASK_PATH)

if __name__=='__main__': unittest.main()
