import unittest
from chat_quality import without_emoji, wrong_addressee, trusted_history
from chat_preferences import addressed
class QualityTest(unittest.TestCase):
    def test_prose_emoji_removed_but_code_and_links_untouched(self):
        text = '开心😊。\n```python\nprint("😊")\n```\nhttps://example.org/😊'
        self.assertEqual(without_emoji(text),'开心。\n```python\nprint("😊")\n```\nhttps://example.org/😊')
        self.assertEqual(addressed('爸爸，你好😊','爸爸'),'爸爸，你好')
    def test_only_proven_wrong_assistant_vocative_is_quarantined(self):
        history = [{'role':'user','content':'我上了一天课'}, {'role':'assistant','content':'爸爸，小白你好呀！'}, {'role':'assistant','content':'我叫小白，先运行print(1)。'}]
        clean = trusted_history(history,'小白','爸爸')
        self.assertEqual(clean[0],history[0]);self.assertEqual(clean[2],history[2])
        self.assertNotIn('小白你好',clean[1]['content'])
        self.assertEqual(history[1]['content'],'爸爸，小白你好呀！')
        self.assertFalse(wrong_addressee('我叫小白','小白','爸爸'))
        self.assertFalse(wrong_addressee('小白你好','小白','小白'))
if __name__ == '__main__':unittest.main()
