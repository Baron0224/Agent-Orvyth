"""Small, conservative conversational reminder setup; no model-generated actions."""
import re

import voice
from datetime import datetime, timedelta


def number(value):
    digits = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    if value.isdigit():
        return int(value)
    if value == '十':
        return 10
    if '十' in value:
        a, b = value.split('十', 1)
        return (digits.get(a, 1) * 10) + digits.get(b, 0)
    return digits.get(value)


def read_time(text):
    match = re.search(r'(凌晨|早上|上午|中午|下午|晚上)?\s*([0-9]{1,2}|[零一二两三四五六七八九十]{1,3})\s*(?:[:：]([0-9]{2})|[点时](?:([0-9]{1,2})分?|([零一二两三四五六七八九十]{1,3})分|半)?)', text)
    if not match:
        return None
    hour = number(match.group(2))
    minute = int(match.group(3) or match.group(4) or 0) if not match.group(5) else number(match.group(5))
    if match.group(0).endswith('半'):
        minute = 30
    period = match.group(1)
    if hour is None or minute is None or minute > 59 or hour > 23:
        return None
    if period in ('下午', '晚上') and 1 <= hour <= 11:
        hour += 12
    if period == '中午' and 1 <= hour <= 11:
        hour += 12
    if period == '凌晨' and hour == 12:
        hour = 0
    return f'{hour:02d}:{minute:02d}'


def read_duration(text):
    if re.search(r'不限|一直|长期|每天|每日', text):
        duration = 0
    elif re.search(r'一次|一天|只.*今天|只.*明天', text):
        duration = 1
    else:
        duration = None
    match = re.search(r'(?:连续|坚持|共|接下来)?\s*([0-9]{1,3}|[一二两三四五六七八九十]{1,3})\s*天', text)
    if match:
        duration = number(match.group(1))
        if duration is None or duration < 1 or duration > 365:
            return None
    return duration


def read_relative(text):
    match = re.search(r'([0-9]{1,4}|[一二两三四五六七八九十]{1,3})\s*(分钟|小时|秒钟|秒)后', text)
    if not match:
        return None
    value = number(match.group(1))
    factor = {'分钟': 60, '小时': 3600, '秒钟': 1, '秒': 1}[match.group(2)]
    seconds = value * factor if value is not None else 0
    return seconds if 0 < seconds <= 86400 else 0


REMIND = re.compile(r'提醒我|提醒一下|叫我|(?:设置|设个|定个|加个).{0,6}提醒')
RECORD = re.compile(r'帮我记[一下录]?|记录一下|记录|记一下|记下来|记着')
# “你会提醒我吗”“你能提醒我吗”这类问能力的句子只回答，不建事项。
CAPABILITY = re.compile(r'(?:你|这个页面|它).{0,6}(?:会|能|可以|可不可以|能不能).{0,4}提醒我|(?:会|能)提醒我吗|能提醒我吗')

CONDITION = voice.condition()


def capability_answer(text):
    """Answer capability questions truthfully; return None when the text is not one."""
    if not CAPABILITY.search(text.strip()):
        return None
    return voice.capability()


def _title_of(text):
    match = re.search(r'提醒我\s*(.+)', text)
    if match:
        title = match.group(1)
    else:
        match = re.search(r'(?:帮我记[一下录]?|记录一下|记录|记一下|记下来|记着)[，,:：\s]*(.+)', text)
        title = match.group(1) if match else ('打卡' if '打卡' in text else '')
    title = re.sub(r'[0-9一二两三四五六七八九十]+\s*(?:分钟|小时|秒钟|秒)后', '', title)
    title = re.sub(r'(?:每天|每日|每晚|天天|明天|今天|从明天开始|从今天开始|连续[0-9一二两三四五六七八九十]+天|[0-9一二两三四五六七八九十]+天)', '', title)
    title = re.sub(r'(?:凌晨|早上|上午|中午|下午|晚上)?\s*(?:[0-9]{1,2}|[零一二两三四五六七八九十]{1,3})\s*(?:[:：][0-9]{2}|[点时](?:[0-9]{1,2}分?|[零一二两三四五六七八九十]+分|半)?)', '', title)
    title = re.sub(r'^[，,。：:\s]+|[，,。：:\s]+$', '', title)
    return title[:160] or ('打卡' if '打卡' in text else None)


def process_reminder(text, draft, now):
    text = text.strip()
    # 新请求优先：带“提醒我 + 新事项”的句子不能拿时间去补旧槽位。
    new_title = _title_of(text) if REMIND.search(text) else None
    if draft is not None and new_title:
        previous = (draft.get('title') or '').strip()
        if not previous or new_title != previous:
            draft = None
    relative = read_relative(text)
    wants = bool(REMIND.search(text) or RECORD.search(text) or re.search(r'(?:帮我|我要|我想|我需要).{0,12}打卡', text))
    if relative is not None and (draft is not None or re.search(r'提醒我|(?:帮我|我要|我想|我需要).{0,12}打卡', text)):
        if relative == 0:
            return voice.need_time(), draft, None
        if re.search(r'每天|每日|每隔|连续', text):
            return voice.relative_once(), draft, None
    if re.search(r'每隔|隔[一二两三四五六七八九十0-9]+天|[一二两三四五六七八九十0-9]+天后', text):
        if draft is not None or re.search(r'提醒我|(?:帮我|我要|我想|我需要).{0,12}打卡', text):
            return voice.interval_unsupported(), draft, None
    if draft is None:
        if not wants:
            return None
        # Questions about reminders should remain ordinary conversation.
        if re.match(r'^(?:怎么|如何|为什么|能不能|可以不可以|可不可以)', text):
            return None
        if CAPABILITY.search(text):
            return None
        # “记录/记一下”只有在带时间或明确说“提醒”时才算提醒请求。
        if not REMIND.search(text) and not read_time(text) and read_duration(text) is None and relative is None and '打卡' not in text:
            return None
        draft = {'title': None, 'time': None, 'days': None, 'start': None}
        draft['title'] = new_title or _title_of(text)
    else:
        draft = dict(draft)
        if re.fullmatch(r'取消|算了|不设置了|不用了', text):
            return voice.cancelled(), None, None
        if not draft.get('title') and not read_time(text) and read_duration(text) is None and relative is None:
            draft['title'] = text[:160]
    if relative and draft.get('days') not in (None, 1):
        return voice.series_relative_conflict(), draft, None
    if relative:
        target = datetime.fromtimestamp(now.timestamp() + relative, now.tzinfo)
        draft['due_at'] = target.timestamp()
        draft['time'] = target.strftime('%H:%M')
        draft['start'] = target.date().isoformat()
        draft['days'] = 1
    elif (t := read_time(text)) is not None:
        draft['time'] = t
    if not relative and (days := read_duration(text)) is not None:
        draft['days'] = days
    if not relative and '明天' in text:
        draft['start'] = (now.date() + timedelta(days=1)).isoformat()
    elif not relative and '今天' in text:
        draft['start'] = now.date().isoformat()
    if not draft.get('title'):
        return voice.ask_title(), draft, None
    if not draft.get('time'):
        return voice.ask_time(draft['title']), draft, None
    if draft.get('days') is None:
        return voice.ask_days(), draft, None
    start = draft.get('start') or now.date().isoformat()
    end = (now.date().fromisoformat(start) + timedelta(days=draft['days'] - 1)).isoformat() if draft['days'] else None
    task = {'title': draft['title'], 'time': draft['time'], 'start': start, 'end': end, 'due_at': draft.get('due_at')}
    duration = '每天' if not draft['days'] else ('一次' if draft['days'] == 1 else f'连续{draft["days"]}天')
    if task['due_at']:
        target = datetime.fromtimestamp(task['due_at'], now.tzinfo)
        reply = voice.created_once(f'{target:%Y-%m-%d %H:%M:%S}', draft['title'])
    else:
        reply = voice.created_series(start, duration, draft['time'], draft['title'], daily=not draft['days'])
    return reply, None, task