"""普通聊天边界检查；不生成闲聊台词，不修改原始历史。"""
import re
PROTECTED = re.compile(r'(```[\s\S]*?(?:```|$)|`[^`]*`|https?://\S+)')
EMOJI = re.compile(r'[\U0001F1E6-\U0001FAFF\u2600-\u27BF](?:[\uFE0F\u200D\U0001F1E6-\U0001FAFF\u2600-\u27BF])*')
def without_emoji(text):
    parts = PROTECTED.split(text)
    return ''.join(part if i % 2 else EMOJI.sub('', part) for i,part in enumerate(parts))
def wrong_addressee(text, assistant_name, user_address):
    if not assistant_name or assistant_name == user_address:
        return False
    prose = text.strip()
    if user_address:
        prose = re.sub(r'^' + re.escape(user_address) + r'[，,:：]\s*', '', prose)
    return bool(re.match(r'^' + re.escape(assistant_name) + r'[，,:：\s]*(?:你好|您好|嗨|hi\b|hello\b)', prose, re.I))
def trusted_history(history, assistant_name, user_address):
    return [{**item, 'content': '[这条历史助手回复叫错了人，不作为事实或表达示范；用户原话保留。]'} if item['role']=='assistant' and wrong_addressee(item['content'], assistant_name, user_address) else dict(item) for item in history]
