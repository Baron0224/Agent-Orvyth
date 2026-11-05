"""有限的自动百科查询；资料始终视为不可信内容。"""
import json
import os
import re
import urllib.parse
import urllib.request
from live_news import is_news_request, lookup_news


def should_search(text):
    normalized = re.sub(r'[\s？?，,。.!！]', '', text)
    if normalized in ('你是谁', '你是谁呀', '你是谁啊', '你是谁呢', '你到底是谁', '你是什么人', '介绍一下你自己', '你介绍一下自己'):
        return False
    if len(text) > 120 or re.search(r'密码|密钥|身份证|银行卡|住址|手机号|验证码', text):
        return False
    if is_news_request(text):
        return True
    if re.search(r'我(很|有点|觉得|感到|最近|今天|为什么|想|不想|累|难过|伤心|孤独)', text):
        return False
    return bool(re.search(r'什么是|是什么|是谁|何时|什么时候|多少|哪年|哪里|为什么|如何|怎么|最新|新闻|现在|目前', text))


def lookup(text):
    if is_news_request(text):
        return lookup_news(text)
    key = os.environ.get('TAVILY_API_KEY', '').strip()
    if key:
        req = urllib.request.Request('https://api.tavily.com/search',
            data=json.dumps({'query': text, 'search_depth': 'basic', 'max_results': 3}).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                     'User-Agent': 'OrvythLocalAssistant/0.1'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                results = json.load(response).get('results', [])
            results = [x for x in results if x.get('url', '').startswith(('https://', 'http://')) and x.get('content')]
            if results:
                first = results[0]
                return {'title': first.get('title', '网页'), 'url': first['url'],
                        'extract': str(first.get('title', '')) + ': ' + first['content'][:1800]}
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None
    params = urllib.parse.urlencode({'action': 'query', 'generator': 'search', 'gsrsearch': text,
                                    'gsrlimit': 1, 'prop': 'extracts|info', 'exintro': 1,
                                    'explaintext': 1, 'inprop': 'url', 'format': 'json'})
    req = urllib.request.Request('https://zh.wikipedia.org/w/api.php?' + params,
                                 headers={'User-Agent': 'OrvythLocalAssistant/0.1 (personal research)'})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.load(response)
        pages = data.get('query', {}).get('pages', {})
        page = next(iter(pages.values()), {})
        if not page.get('extract') or not page.get('fullurl'):
            return None
        return {'title': page['title'], 'url': page['fullurl'], 'extract': page['extract'][:2000]}
    except (OSError, ValueError, KeyError):
        return None
