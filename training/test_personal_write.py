"""Personal facts stated or asked to remember go to the current account archive."""
import tempfile
import unittest
from pathlib import Path

from hermes_memory import HermesMemory
from local_web_tasks import personal_reply, personal_write

OWNER = 'owner-a'
STATEMENT = '我叫穆柏润，在大连东软信息学院上学，记住'
STORE_REQUEST = '帮我存进长期记忆：我叫穆柏润，在大连东软信息学院上学'


class PersonalWriteTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.memory = HermesMemory(Path(self.folder.name))
        self.addCleanup(self.folder.cleanup)

    def contents(self):
        return [item['content'] for item in self.memory.entries(OWNER)]

    def test_statement_with_tail_command_writes_verbatim_facts(self):
        reply = personal_write(self.memory, OWNER, STATEMENT)
        self.assertIsNotNone(reply)
        self.assertIn('已存入', reply)
        self.assertIn('我叫穆柏润', reply)
        self.assertIn('在大连东软信息学院上学', reply)
        entries = self.memory.entries(OWNER)
        self.assertEqual({item['content'] for item in entries},
                         {'我叫穆柏润', '在大连东软信息学院上学'})
        self.assertEqual({item['category'] for item in entries}, {'name', 'school'})
        self.assertEqual({item['source'] for item in entries}, {'explicit_chat'})
        self.assertIn('共 2 条', reply)

    def test_memory_store_phrasing_writes_then_answers(self):
        reply = personal_write(self.memory, OWNER, STORE_REQUEST)
        self.assertIn('已存入', reply)
        self.assertIn('姓名', personal_reply(self.memory, OWNER, '我叫什么'))
        self.assertIn('穆柏润', personal_reply(self.memory, OWNER, '我叫什么'))
        school = personal_reply(self.memory, OWNER, '我在哪上学')
        self.assertIn('大连东软信息学院', school)
        combined = personal_reply(self.memory, OWNER, '我叫什么，在哪上学')
        self.assertIn('穆柏润', combined)
        self.assertIn('大连东软信息学院', combined)

    def test_questions_do_not_write(self):
        self.assertIsNone(personal_write(self.memory, OWNER, '我叫什么'))
        self.assertIsNone(personal_write(self.memory, OWNER, '我在哪上学'))
        self.assertEqual(self.contents(), [])

    def test_repeat_is_not_duplicated(self):
        personal_write(self.memory, OWNER, STATEMENT)
        reply = personal_write(self.memory, OWNER, STATEMENT)
        self.assertIn('没有重复写入', reply)
        self.assertEqual(len(self.contents()), 2)

    def test_unknown_fact_is_reported_missing(self):
        personal_write(self.memory, OWNER, STATEMENT)
        answer = personal_reply(self.memory, OWNER, '我的银行卡密码是什么')
        self.assertIn('没有可用于回答的密码记录', answer)
        self.assertNotIn('穆柏润', answer)
        self.assertEqual(len(self.contents()), 2)

    def test_credential_statement_is_not_stored(self):
        reply = personal_write(self.memory, OWNER, '记住：我的银行卡密码是123456789012')
        self.assertIsNotNone(reply)
        self.assertIn('没有写入', reply)
        self.assertEqual(self.contents(), [])

    def test_unrelated_memory_command_is_left_to_existing_path(self):
        self.assertIsNone(personal_write(self.memory, OWNER, '记住：明天下午三点提醒我开会'))


if __name__ == '__main__':
    unittest.main()