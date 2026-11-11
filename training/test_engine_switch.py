"""Engine switching and shared local work path: 8775 only, model-independent."""
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

import file_lookup
import local_web_tasks as tasks
from browser_store import Store
from chat_web import ENGINES, ChatServer


class EnabledTest(unittest.TestCase):
    def test_8775_serves_both_engines(self):
        self.assertTrue(tasks.enabled('ollama', 8775))
        self.assertTrue(tasks.enabled('deepseek', 8775))
        self.assertFalse(tasks.enabled('ollama', 8776))

    def test_engine_mapping_is_stable(self):
        self.assertEqual(ENGINES, {'local': 'qwen3:8b', 'deepseek': 'deepseek-cloud:deepseek-flash'})


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.tmp.name) / 'browser.sqlite3'))
        _, self.owner = self.store.owner(create=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _save(self, **extra):
        payload = {'name': '穆柏润', 'pet_name': '小白', 'pet_motion': True, 'pet_kind': 'dog', 'avatar': ''}
        payload.update(extra)
        self.store.save_profile(self.owner, payload)

    def test_default_is_local_and_survives_restart(self):
        self._save()
        self.assertEqual(self.store.profile(self.owner)['chat_engine'], 'local')

    def test_deepseek_is_persisted(self):
        self._save(chat_engine='deepseek')
        self.assertEqual(self.store.profile(self.owner)['chat_engine'], 'deepseek')
        reopened = Store(str(Path(self.tmp.name) / 'browser.sqlite3'))
        self.assertEqual(reopened.profile(self.owner)['chat_engine'], 'deepseek')

    def test_unknown_engine_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self._save(chat_engine='gpt')
        self.assertIn('引擎', str(caught.exception))


class SelectedModelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.tmp.name) / 'browser.sqlite3'))
        self.srv = object.__new__(ChatServer)
        self.srv.model = 'qwen3:8b'
        self.srv.store = self.store
        self.srv.server_port = 8775
        _, self.owner = self.store.owner(create=True)
        self.store.save_profile(self.owner, {'name': 'x', 'pet_name': 'y'})

    def tearDown(self):
        self.tmp.cleanup()

    def test_local_engine_uses_local_model(self):
        self.assertEqual(self.srv.selected_model(self.owner), 'qwen3:8b')

    def test_deepseek_engine_uses_cloud_model(self):
        self.store.save_profile(self.owner, {'name': 'x', 'pet_name': 'y', 'chat_engine': 'deepseek'})
        self.srv.ensure_cloud_key = lambda: True
        self.assertEqual(self.srv.selected_model(self.owner), 'deepseek-cloud:deepseek-flash')

    def test_missing_key_falls_back_to_local(self):
        self.store.save_profile(self.owner, {'name': 'x', 'pet_name': 'y', 'chat_engine': 'deepseek'})
        self.srv.ensure_cloud_key = lambda: False
        self.assertEqual(self.srv.selected_model(self.owner), 'qwen3:8b')

    def test_terminal_port_ignores_engine(self):
        self.srv.server_port = 8776
        self.srv.model = 'deepseek-cloud:deepseek-flash'
        self.store.save_profile(self.owner, {'name': 'x', 'pet_name': 'y', 'chat_engine': 'local'})
        self.assertEqual(self.srv.selected_model(self.owner), 'deepseek-cloud:deepseek-flash')


class RootsTest(unittest.TestCase):
    def setUp(self):
        self.saved = os.environ.pop('ORVYTH_FILE_ROOTS', None)

    def tearDown(self):
        if self.saved is not None:
            os.environ['ORVYTH_FILE_ROOTS'] = self.saved

    def test_roots_are_real_directories_and_never_localized_guesses(self):
        roots = file_lookup.search_roots()
        self.assertTrue(roots)
        for root in roots:
            self.assertTrue(Path(root).is_dir(), root)
            label = file_lookup.display_path(root)
            self.assertNotIn('เอกสาร', label)
            self.assertFalse(re.search(r'[\u0e00-\u0e7f]', label), label)
        self.assertEqual(len({str(Path(r).resolve()) for r in roots}), len(roots))
        documents = file_lookup._shell_folder('Personal')
        if documents is not None and documents in roots:
            self.assertEqual(file_lookup.display_path(documents), '文档')

    def test_configured_override_still_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ['ORVYTH_FILE_ROOTS'] = tmp
            self.assertEqual(file_lookup.search_roots(), [Path(tmp)])


class SharedFactsTest(unittest.TestCase):
    def test_same_implementation_answers_both_topics(self):
        class Archive:
            is_command = staticmethod(lambda q: False)
            entries = staticmethod(lambda owner: [
                {'content': '我叫穆柏润', 'category': 'name'},
                {'content': '在大连东软信息学院上学', 'category': 'school'},
            ])
        reply = tasks.personal_reply(Archive(), 'isolated', '我叫什么、在哪上学')
        self.assertIn('穆柏润', reply)
        self.assertIn('大连东软信息学院', reply)
        self.assertIn('没有', tasks.personal_reply(Archive(), 'isolated', '我的银行卡密码是什么'))


if __name__ == '__main__':
    unittest.main()