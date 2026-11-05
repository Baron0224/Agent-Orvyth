"""Route explicit local-file requests from normal chat to Pi."""
from pathlib import Path
import re
from file_lookup import find_matches, query_name
from file_write import write_request
from word_write import word_request

ASK_PATH = '我在本机常用文档和项目目录里暂时没定位到对应文件。告诉我更具体的文件名，或者把文件所在文件夹发给我，我再接着找。'

def local_intent(question):
    return bool(re.search(r'调取|读取|读一下', question) or
                (re.search(r'打开|查看|看一下|找一下|找到|帮我找|找找|总结|分析|修改|编辑|替换|改成|改为', question) and
                 re.search(r'文档|文件|目录|项目|[\w-]+\.[a-zA-Z0-9]{1,8}\b|[A-Za-z]:[\\/]|我.{1,80}(?:中|里)的', question)))

def natural_location(question):
    match=re.fullmatch(r'\s*(?:在|放在|就在|它在)?\s*([a-zA-Z])\s*盘\s*(.+?)\s*',question)
    if not match: return None
    rest=re.sub(r'(里面|里边|里|中)[。！!]*$', '', match[2]).strip()
    rest=re.sub(r'[/\\]|下面的|下的|的', lambda _: '\\', rest).strip(' \\"“”')
    return match[1].upper()+':\\'+rest if rest else None

def file_request(question, history):
    word = word_request(question)
    if word: return word
    creation=write_request(question)
    if creation: return creation
    original_question = question
    source_question = None
    location=natural_location(question)
    if location:
        for entry in reversed(history[-8:]):
            if entry.get('role')=='user' and local_intent(entry.get('content','')):
                source_question=entry['content'];break
        if source_question: question='"'+location+'"'
    pending = bool(history and history[-1].get('role') == 'assistant' and
                   (history[-1].get('content') == ASK_PATH or history[-1].get('content','').startswith('我没找到这个文件或文件夹。')))
    choices = history[-1].get('content','') if history and history[-1].get('role')=='assistant' else ''
    choosing = choices.startswith('找到几个可能的文件或项目')
    pending = pending or bool(source_question)
    if choosing:
        selection = re.fullmatch(r'(?:第)?([1-8一二三四五六七八])(?:个|项)?',question.strip())
        candidates = re.findall(r'`([^`]+)`',choices)
        if selection:
            n=selection[1];index=int(n)-1 if n.isdigit() else '一二三四五六七八'.index(n)
            if index<len(candidates):
                question='"'+candidates[index]+'"'; pending=True
    # Explicit read/retrieve requests also refer to named projects or their
    # contents without using the literal word “file”. Ask for a path rather
    # than sending such requests to knowledge search or unconstrained chat.
    intent = local_intent(question)
    if not intent and not pending:
        return None
    if pending and not intent and re.search(r'先不|不看了|算了|聊聊天',question):
        return None
    # Quoting disambiguates file paths with spaces and trailing instructions.
    quoted = re.findall(r'["“`「]([^"”`」\r\n]+)["”`」]', question)
    paths = [s for s in quoted if re.match(r'^[A-Za-z]:[\\/]|^/', s)]
    if not paths:
        match = re.search(r'[A-Za-z]:[\\/][^\r\n"“”`，。！？]*?\.[a-zA-Z0-9]{1,8}(?=$|[\s，。！？,;；]|并|然后|的内容)', question)
        if match:
            paths = [match.group().strip()]
        else:
            match = re.search(r'[A-Za-z]:[\\/][^\s"“”`，。！？]+', question)
            if match: paths = [match.group().rstrip('，。！？,;；')]
    if not paths:
        if not intent and not pending: return None
        name=query_name(question)
        candidates=find_matches(name)
        if len(candidates)==1:
            paths=[str(candidates[0])]
        elif candidates:
            return {'reply':'找到几个可能的文件或项目，请回复序号，我再读取：\n'+ '\n'.join(f'{i+1}. `{p}`' for i,p in enumerate(candidates))}
        else:
            return {'reply':ASK_PATH}
    if len(paths) != 1:
        return {'reply': '先发一个文件或文件夹路径给我，我们逐个查看。'}
    target = Path(paths[0])
    original = source_question or (history[-2]['content'] if pending and len(history)>1 and history[-2].get('role')=='user' else question)
    try:
        target = target.resolve(strict=True)
        if target.is_dir():
            hints=re.findall(r'(?:里的|中的|的)([\u4e00-\u9fffA-Za-z0-9_-]{2,32}?)(?=大概|主要|讲了|是什么|什么意思|内容|[，。？?]|$)',original)
            if hints:
                documents=[p for p in find_matches(hints[-1].rsplit('的',1)[-1],roots=[target]) if p.is_file()]
                if len(documents)==1: target=documents[0].resolve(strict=True)
        if target.is_file():
            folder, only_file = target.parent, target.name
        elif target.is_dir():
            folder, only_file = target, None
        else:
            return {'reply': '这个路径不是普通文件或文件夹，请重新确认。'}
    except (OSError, ValueError):
        return {'reply': '我没找到这个文件或文件夹。请检查路径，再把完整路径发给我。'}
    task = f'用户要求：{original}\n本轮补充：{original_question}\n已定位来源：{target}\n'
    task += f'请先调用 read_project 读取 {only_file!r}，再根据实际内容回答。' if only_file else '请先调用 list_project 查看目录，再按要求读取相关文本。'
    return {'folder':str(folder), 'task':task, 'only_file':only_file}
