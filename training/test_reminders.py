import tempfile
import sqlite3
from contextlib import closing
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from browser_store import Store
from reminders import process_reminder, read_time


def moment(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc)


class ReminderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'test.sqlite3')
        _, self.owner = self.store.owner(create=True)
        self.chat = self.store.state(self.owner)['active_chat']
        self.now = patch('browser_store.local_now', return_value=moment(2, 12))
        self.now.start()
        self.addCleanup(self.now.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_dialog_and_daily_due_time(self):
        self.assertIn('几点', self.store.reminder_chat(self.owner, self.chat, '我想打卡'))
        self.assertIn('几天', self.store.reminder_chat(self.owner, self.chat, '下午一点'))
        self.assertIn('右侧待办', self.store.reminder_chat(self.owner, self.chat, '每天'))
        task = self.store.state(self.owner)['tasks'][0]
        self.assertEqual((task['title'], task['remind_time'], task['done']), ('打卡', '13:00', 0))
        self.store.task_action(self.owner, 'toggle', {'id': task['id'], 'done': True})
        self.assertEqual(self.store.state(self.owner)['tasks'][0]['done'], 1)
        with patch('browser_store.local_now', return_value=moment(3, 12, 59)):
            self.assertTrue(self.store.state(self.owner)['tasks'][0]['waiting'])
        with patch('browser_store.local_now', return_value=moment(3, 13)):
            self.assertEqual(self.store.state(self.owner)['tasks'][0]['done'], 0)
        self.assertEqual(len(self.store.state(self.owner)['tasks']), 1)

    def test_finite_cancel_and_no_unrelated_interception(self):
        self.assertIsNone(self.store.reminder_chat(self.owner, self.chat, '如何设置打卡提醒？'))
        self.assertIn('右侧待办', self.store.reminder_chat(self.owner, self.chat, '每天13:00提醒我打卡连续3天'))
        task = self.store.state(self.owner)['tasks'][0]
        self.assertEqual(task['end_date'], '2026-11-04')
        with patch('browser_store.local_now', return_value=moment(5, 13)):
            self.assertTrue(self.store.state(self.owner)['tasks'][0]['expired'])
        self.store.reminder_chat(self.owner, self.chat, '提醒我喝水')
        self.assertIn('不设置', self.store.reminder_chat(self.owner, self.chat, '取消'))
        self.assertEqual(len(self.store.state(self.owner)['tasks']), 1)

    def test_draft_survives_reopen_and_is_isolated(self):
        self.store.reminder_chat(self.owner, self.chat, '提醒我打卡')
        self.store = Store(self.store.path)
        _, other = self.store.owner(create=True)
        other_chat = self.store.state(other)['active_chat']
        self.assertIsNone(self.store.reminder_chat(other, other_chat, '13:00'))
        self.assertIn('几天', self.store.reminder_chat(self.owner, self.chat, '13:00'))
        self.store.reminder_chat(self.owner, self.chat, '一天')
        self.assertEqual(self.store.state(other)['tasks'], [])
        self.assertEqual(self.store.state(self.owner)['tasks'][0]['end_date'], '2026-11-02')

    def test_existing_tasks_survive_migration(self):
        path = Path(self.tmp.name) / 'old.sqlite3'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL)")
            db.execute("INSERT INTO tasks VALUES ('t', 'owner', '原有任务', 1, 1)")
        Store(path)
        with closing(sqlite3.connect(path)) as db, db:
            self.assertEqual(db.execute("SELECT title,done,remind_time FROM tasks WHERE id='t'").fetchone(), ('原有任务', 1, None))

    def test_unsupported_interval_never_creates_task(self):
        self.assertIn('只能设置', self.store.reminder_chat(self.owner, self.chat, '每隔两天13:00提醒我打卡'))
        self.assertEqual(self.store.state(self.owner)['tasks'], [])

    def test_relative_reminder_appears_only_when_due_and_stays_completed(self):
        self.assertIn('只提醒一次', self.store.reminder_chat(self.owner, self.chat, '2分钟后提醒我喝水'))
        task = self.store.state(self.owner)['tasks'][0]
        self.assertEqual(task['title'], '喝水')
        self.assertTrue(task['waiting'])
        self.assertFalse(task['done'])
        with patch('browser_store.local_now', return_value=moment(2, 12) + timedelta(seconds=119)):
            self.assertTrue(self.store.state(self.owner)['tasks'][0]['waiting'])
            with self.assertRaises(ValueError):
                self.store.task_action(self.owner, 'toggle', {'id': task['id'], 'done': True})
        with patch('browser_store.local_now', return_value=moment(2, 12, 2)):
            self.assertFalse(self.store.state(self.owner)['tasks'][0]['waiting'])
            self.store.task_action(self.owner, 'toggle', {'id': task['id'], 'done': True})
        with patch('browser_store.local_now', return_value=moment(3, 13)):
            self.assertTrue(self.store.state(self.owner)['tasks'][0]['done'])
            self.assertFalse(self.store.state(self.owner)['tasks'][0]['expired'])

    def test_relative_followup_and_midnight(self):
        self.assertIn('几点', self.store.reminder_chat(self.owner, self.chat, '提醒我喝水'))
        with patch('browser_store.local_now', return_value=moment(2, 23, 59)):
            self.assertIn('只提醒一次', self.store.reminder_chat(self.owner, self.chat, '2分钟后'))
            self.assertEqual(self.store.state(self.owner)['tasks'][0]['start_date'], '2026-11-03')
        with patch('browser_store.local_now', return_value=moment(3, 0, 1)):
            self.assertFalse(self.store.state(self.owner)['tasks'][0]['waiting'])

    def test_relative_is_not_allowed_to_override_daily_intent(self):
        self.assertIn('几点', self.store.reminder_chat(self.owner, self.chat, '每天提醒我喝水'))
        self.assertIn('只能设置一次', self.store.reminder_chat(self.owner, self.chat, '2分钟后'))
        self.assertEqual(self.store.state(self.owner)['tasks'], [])

    def test_overdue_relative_survives_until_done(self):
        self.store.reminder_chat(self.owner, self.chat, '2分钟后提醒我喝水')
        with patch('browser_store.local_now', return_value=moment(3, 15)):
            task = self.store.state(self.owner)['tasks'][0]
            self.assertFalse(task['waiting'])
            self.assertFalse(task['done'])
            self.store.task_action(self.owner, 'toggle', {'id': task['id'], 'done': True})
            self.assertTrue(self.store.state(self.owner)['tasks'][0]['done'])

    def test_daily_notification_only_due_after_scheduled_time(self):
        self.store.reminder_chat(self.owner, self.chat, '每天13:00提醒我打卡')
        self.assertFalse(self.store.state(self.owner)['tasks'][0]['remind_due'])
        with patch('browser_store.local_now', return_value=moment(2, 13)):
            task = self.store.state(self.owner)['tasks'][0]
            self.assertTrue(task['remind_due'])
            self.assertEqual(task['occurrence_date'], '2026-11-02')
            self.store.task_action(self.owner, 'toggle', {'id': task['id'], 'done': True})
            self.assertFalse(self.store.state(self.owner)['tasks'][0]['remind_due'])

    def test_time_parser(self):
        self.assertEqual(read_time('下午一点半'), '13:30')
        self.assertEqual(read_time('13:00'), '13:00')
        self.assertIsNone(read_time('25:00'))

if __name__ == '__main__':
    unittest.main()
