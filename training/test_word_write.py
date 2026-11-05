from pathlib import Path
import os
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from unittest.mock import patch
from file_chat import file_request
from word_write import word_request, create_word_file

class WordWriteTests(unittest.TestCase):
    def test_screenshot_routes_to_word_creation(self):
        plan = file_request('帮我做一个word里面写你好', [])
        self.assertEqual(plan['word_write']['content'], '你好')
        self.assertTrue(plan['word_write']['name'].endswith('.docx'))

    def test_boundaries(self):
        self.assertIsNone(word_request('Word是什么'))
        self.assertIn('reply', word_request('不要生成word里面写你好'))
        self.assertIn('reply', word_request('创建word'))
        self.assertIn('reply', word_request('创建word名字叫../bad，里面写你好'))

    def test_real_docx_contains_exact_text_without_overwriting(self):
        exe = Path(os.environ.get('LOCALAPPDATA', ''))/'Orvyth/tools/docx-cli/v0.27.0/docx.exe'
        if not exe.is_file(): self.skipTest('docx-cli not installed')
        with tempfile.TemporaryDirectory() as base, patch('word_write.desktop_folder', return_value=Path(base)):
            request = {'name':'问候.docx','content':'你好'}
            self.assertIn('已经在桌面创建', create_word_file(request))
            file = Path(base)/request['name']
            before = file.read_bytes()
            with zipfile.ZipFile(file) as archive:
                xml = ET.fromstring(archive.read('word/document.xml'))
            self.assertEqual(''.join(xml.itertext()), '你好')
            with self.assertRaises(FileExistsError): create_word_file(request)
            self.assertEqual(file.read_bytes(), before)
