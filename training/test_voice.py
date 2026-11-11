"""口吻定版：规格锁定、关键信息不丢、禁区不出现。"""
import unittest

import voice


class VoiceTests(unittest.TestCase):
    def test_spec_is_locked_and_versioned(self):
        text = voice.SPEC_PATH.read_text(encoding='utf-8-sig')
        self.assertTrue(voice.SPEC_PATH.is_file())
        self.assertIn('2026-11-11', text)
        self.assertIn('不得擅自修改', text)
        self.assertIn('暧昧期', text)
        self.assertIn('信息完整性优先', text)

    def test_capability_keeps_all_conditions(self):
        text = voice.capability()
        for word in ('会', '网页', '静音', '桌面通知', '弹窗', '已错过'):
            self.assertIn(word, text)

    def test_reminder_created_keeps_time_title_and_conditions(self):
        once = voice.created_once('2026-11-11 18:00:00', '喝水')
        for word in ('喝水', '只提醒一次', '网页', '静音', '桌面通知'):
            self.assertIn(word, once)
        series = voice.created_series('2026-11-12', '每天', '22:29', '熄灯', daily=True)
        for word in ('熄灯', '22:29', '右侧待办', '网页', '第二天'):
            self.assertIn(word, series)

    def test_facts_keep_values_and_counts(self):
        saved = voice.fact_saved([('姓名', '我叫穆柏润'), ('学校', '在大连东软信息学院上学')], 2)
        self.assertIn('已存入', saved)
        self.assertIn('共 2 条', saved)
        self.assertIn('姓名', saved)
        answer = voice.fact_answer('姓名', '穆柏润', 'BOOS')
        self.assertTrue(answer.startswith('BOOS，'))
        self.assertIn('姓名', answer)
        self.assertIn('穆柏润', answer)
        self.assertIn('没有可用于回答的密码记录', voice.no_password())

    def test_files_keep_path_and_content(self):
        text = voice.file_created(r'C:\Users\me\Desktop\你好.txt', '我爱你')
        self.assertIn(r'C:\Users\me\Desktop\你好.txt', text)
        self.assertIn('我爱你', text)
        missing = voice.no_file('简历', '文档、桌面')
        for word in ('简历', '文档、桌面', '别处'):
            self.assertIn(word, missing)

    def test_failure_keeps_reason_and_no_retry(self):
        text = voice.task_failed('工具报告的文件不存在')
        self.assertIn('工具报告的文件不存在', text)
        self.assertIn('没有重试', text)
        self.assertIn('没有覆盖', text)

    def test_forbidden_tone_is_absent(self):
        samples = [
            voice.capability(), voice.ask_time('喝水'), voice.ask_days(),
            voice.need_time(), voice.cancelled(), voice.created_once('18:00', '喝水'),
            voice.fact_saved([('姓名', 'x')], 1), voice.fact_duplicate(['x']),
            voice.fact_rejected([('x', '原因')]), voice.no_password(),
            voice.listing(['[姓名] x']), voice.remembered('x'),
            voice.file_created('p', 'c'), voice.file_exists('x'),
            voice.no_file('简历', '桌面'), voice.need_name(), voice.parse_miss(),
            voice.task_failed('原因'), voice.declaration_name('穆柏润'),
        ]
        joined = '\n'.join(samples)
        for banned in ('您好', '已为您', '请您', '如需', '感谢您的理解', '当前账户档案中', '任务未完成：', '根据您的需求'):
            self.assertNotIn(banned, joined)

    def test_no_emoji_or_decorative_symbols(self):
        text = voice.capability() + voice.created_once('18:00', '喝水') + voice.no_password()
        for mark in ('😀', '✨', '♪', '～'):
            self.assertNotIn(mark, text)


if __name__ == '__main__':
    unittest.main()