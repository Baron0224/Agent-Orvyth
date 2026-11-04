import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from file_chat import ASK_PATH, file_request, natural_location

class FileChatTests(unittest.TestCase):
    def setUp(self):
        patcher=patch('file_chat.find_matches',return_value=[])
        self.lookup=patcher.start();self.addCleanup(patcher.stop)

    def test_normal_chat_does_not_call_pi(self):
        self.assertIsNone(file_request('今天有点累', []))
        self.assertIsNone(file_request('Python文件是什么？', []))

    def test_screenshot_find_wording_and_colloquial_location(self):
        question='帮我找到我three feet under 的文档里的故事背景大概什么意思'
        self.assertEqual(file_request(question,[])['reply'],ASK_PATH)
        self.lookup.assert_called_with('three feet under')
        self.assertEqual(natural_location('在d盘codex的three feet under里'),r'D:\codex\three feet under')
        history=[{'role':'user','content':question},{'role':'assistant','content':'我暂时无法直接读取你电脑上的文件。'}]
        with tempfile.TemporaryDirectory() as base:
            with patch('file_chat.natural_location',return_value=base):
                plan=file_request('在d盘codex的three feet under里',history)
        self.assertEqual(plan['folder'],str(Path(base).resolve()))
        self.assertIn('故事背景',plan['task'])

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

    def test_unique_named_project_is_opened_without_asking_for_path(self):
        with tempfile.TemporaryDirectory() as base:
            project=Path(base)/'Three Feet Under';project.mkdir()
            self.lookup.return_value=[project]
            plan=file_request('读取我文档里three feet under中的故事背景大概讲了什么',[])
            self.assertEqual(plan['folder'],str(project.resolve()))
            self.assertIn('故事背景',plan['task'])
            self.lookup.assert_any_call('three feet under')

    def test_ambiguous_candidates_can_be_chosen_by_number(self):
        with tempfile.TemporaryDirectory() as base:
            a=Path(base)/'draft';b=Path(base)/'final';a.mkdir();b.mkdir()
            self.lookup.return_value=[a,b]
            question='读取three feet under故事背景'
            reply=file_request(question,[])['reply']
            history=[{'role':'user','content':question},{'role':'assistant','content':reply}]
            plan=file_request('第二个',history)
            self.assertEqual(plan['folder'],str(b.resolve()))
            self.assertIn('故事背景',plan['task'])

    def test_named_document_is_resolved_inside_project(self):
        with tempfile.TemporaryDirectory() as base:
            project=Path(base)/'three feet under';project.mkdir()
            document=project/'故事背景.md';document.write_text('古代墓葬探索',encoding='utf-8')
            self.lookup.side_effect=[[project],[document]]
            plan=file_request('帮我找到我three feet under 的文档里的故事背景大概什么意思',[])
            self.assertEqual(plan['only_file'],'故事背景.md')
            self.assertIn(str(document),plan['task'])

if __name__=='__main__': unittest.main()
