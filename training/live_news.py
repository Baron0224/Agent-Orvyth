"""Public RSS headlines; exact requested publication day, no fabricated history."""
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import re
import urllib.request
import xml.etree.ElementTree as ET

FEED='https://feeds.bbci.co.uk/news/world/rss.xml'

def is_news_request(text):
    return bool(re.search(r'新闻|头条|时事',text)) and not re.search(r'新闻学|什么是新闻|新闻是什么',text)

def requested_day(text, now=None):
    now=now or datetime.now().astimezone()
    match=re.search(r'(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})',text)
    if match:
        try: return datetime(*map(int,match.groups())).date()
        except ValueError: raise ValueError('这个日期好像写错了一点。换成“2026-11-04”这样的格式发给我，我再帮你查。')
    return (now-timedelta(days=1 if '昨天' in text else 0)).date()

def lookup_news(text):
    now=datetime.now().astimezone();day=requested_day(text,now)
    if day>now.date():return None
    req=urllib.request.Request(FEED,headers={'User-Agent':'Orvyth/0.1 RSS reader'})
    try:
        with urllib.request.urlopen(req,timeout=8) as response:raw=response.read(2_000_000)
        root=ET.fromstring(raw);items=[]
        for item in root.findall('./channel/item'):
            title=item.findtext('title','').strip();url=item.findtext('link','').strip()
            try:published=parsedate_to_datetime(item.findtext('pubDate','')).astimezone(now.tzinfo)
            except (TypeError,ValueError,OverflowError):continue
            if published.date()!=day or not title or not url.startswith('https://www.bbc.'):continue
            if title not in [x['title'] for x in items]:items.append({'title':title,'url':url,'published':published.isoformat()})
            if len(items)>=5:break
        if not items:return None
        extract=f'来源：BBC World公开RSS。筛选的是{day.isoformat()}的发布日，不保证事件发生日相同。这只是该新闻源的部分国际新闻，不是当天完整新闻。只有标题和时间，不能编造正文细节。请将标题准确译成中文，逐条列出，开头交代来源与日期。\n'
        extract+='\n'.join(f'{i+1}. {x["title"]}；发布时间{x["published"]}'+ ('；链接'+x['url'] if re.search(r'来源|出处|链接',text) else '') for i,x in enumerate(items))
        return {'title':f'BBC World {day.isoformat()}发布的新闻标题','url':FEED,'extract':extract,'kind':'news','items':items}
    except (OSError,ValueError,ET.ParseError):return None

def login_next_step(question,history):
    if not ('登录' in question and '报错' in question and re.search(r'先.{0,8}(检查|看|做)',question)):
        return None
    normalize=lambda s:re.sub(r'[\s，。？！,.?!]','',s)
    if any(normalize(x['content'])==normalize(question) for x in history[-8:] if x['role']=='user'):
        return '我记着呢，你想先解决登录。现在还缺报错原文或截图，把它发给我看看，我们再一起判断是账号验证、权限还是服务端的问题，不用来回试一堆不相关的办法。'
    return '那我们就先把登录这件事弄清楚。第一步看错误原文或错误码，把报错截图连同应用名字发给我看看，我跟你一起往下查。'
