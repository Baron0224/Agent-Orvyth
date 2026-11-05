from datetime import datetime,timezone
import io
import unittest
from unittest.mock import patch
from live_news import requested_day,lookup_news,login_next_step
from web_lookup import should_search

class FixedDate(datetime):
    @classmethod
    def now(cls,tz=None):return cls(2026,11,4,22,0,tzinfo=timezone.utc)

class NewsTests(unittest.TestCase):
    def test_news_intent_preserves_sensitive_input_filter(self):
        self.assertTrue(should_search('我想知道今天新闻'))
        self.assertFalse(should_search('我的密码是123，今天新闻'))

    def test_exact_date_and_invalid_date(self):
        self.assertEqual(str(requested_day('说出2026.11.4的新闻')),'2026-11-04')
        with self.assertRaises(ValueError):requested_day('2026.13.4新闻')

    def test_filters_publication_day_and_keeps_real_source(self):
        feed=b'''<rss><channel><item><title>Current headline</title><pubDate>Wed, 04 Nov 2026 12:00:00 GMT</pubDate><link>https://www.bbc.com/news/a</link></item><item><title>Old headline</title><pubDate>Tue, 03 Nov 2026 12:00:00 GMT</pubDate><link>https://www.bbc.com/news/old</link></item></channel></rss>'''
        with patch('live_news.datetime',FixedDate),patch('live_news.urllib.request.urlopen',return_value=io.BytesIO(feed)):
            data=lookup_news('2026.11.4新闻')
        self.assertEqual(len(data['items']),1)
        self.assertIn('Current headline',data['extract']);self.assertNotIn('Old headline',data['extract'])

    def test_unavailable_or_empty_feed_never_fabricates(self):
        for content in (b'<rss><channel/></rss>',b'invalid'):
            with patch('live_news.urllib.request.urlopen',return_value=io.BytesIO(content)):
                self.assertIsNone(lookup_news('2026.11.4新闻'))

    def test_login_repeat_even_with_intervening_news(self):
        question='我现在不想休息，想解决登录报错，先检查什么'
        first=login_next_step(question,[])
        history=[{'role':'user','content':question},{'role':'assistant','content':first},{'role':'user','content':'今天新闻'}]
        second=login_next_step(question,history)
        self.assertIn('错误原文',first);self.assertNotEqual(first,second)
        self.assertNotIn('ping',second)
        self.assertIsNone(login_next_step('今天好累',[]))

if __name__=='__main__':unittest.main()
