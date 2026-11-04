"""Route explicit local-file requests from normal chat to Pi."""
from pathlib import Path
import re
from file_lookup import find_matches, query_name

ASK_PATH = '我在本机常用文档和项目目录里暂时没定位到对应文件。告诉我更具体的文件名，或者把文件所在文件夹发给我，我再接着找。'

def file_request(question, history):
    pending = bool(history and history[-1].get('role') == 'assistant' and
                   (history[-1].get('content') == ASK_PATH or history[-1].get('content','').startswith('我没找到这个文件或文件夹。')))
    choices = history[-1].get('content','') if history and history[-1].get('role')=='assistant' else ''
    choosing = choices.startswith('找到几个可能的文件或项目')
    original_question = question
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
    intent = bool(re.search(r'调取|读取|读一下', question) or
                  (re.search(r'打开|查看|看一下|找一下|总结|分析', question) and
                   re.search(r'文件|目录|项目|[\w-]+\.[a-zA-Z0-9]{1,8}\b|[A-Za-z]:[\\/]|我.{1,80}(?:中|里)的', question)))
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
    try:
        target = target.resolve(strict=True)
        if target.is_file():
            folder, only_file = target.parent, target.name
        elif target.is_dir():
            folder, only_file = target, None
        else:
            return {'reply': '这个路径不是普通文件或文件夹，请重新确认。'}
    except (OSError, ValueError):
        return {'reply': '我没找到这个文件或文件夹。请检查路径，再把完整路径发给我。'}
    original = history[-2]['content'] if pending and len(history)>1 and history[-2].get('role')=='user' else question
    task = f'用户要求：{original}\n本轮补充：{original_question}\n已定位来源：{target}\n'
    task += f'请先调用 read_project 读取 {only_file!r}，再根据实际内容回答。' if only_file else '请先调用 list_project 查看目录，再按要求读取相关文本。'
    return {'folder':str(folder), 'task':task, 'only_file':only_file}
