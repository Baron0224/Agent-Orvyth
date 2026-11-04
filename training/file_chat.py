"""Route explicit local-file requests from normal chat to Pi."""
from pathlib import Path
import re

ASK_PATH = '可以，把文件或文件夹的完整路径发给我，例如 D:\\Projects\\MyApp\\README.md。路径有空格时，用双引号括起来。我会直接在这里读取并回答。'

def file_request(question, history):
    pending = bool(history and history[-1].get('role') == 'assistant' and
                   (history[-1].get('content') == ASK_PATH or history[-1].get('content','').startswith('我没找到这个文件或文件夹。')))
    intent = bool(re.search(r'调取|读取|打开|查看|读一下|看一下|找一下|总结|分析', question) and
                  re.search(r'文件|目录|项目|[\w-]+\.[a-zA-Z0-9]{1,8}\b|[A-Za-z]:[\\/]', question))
    if not intent and not pending:
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
        # A new unrelated reply must not keep forcing file requests.
        return {'reply': ASK_PATH} if intent or re.search(r'路径|文件|目录', question) else None
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
    task = f'用户要求：{original}\n本轮补充：{question}\n'
    task += f'请先调用 read_project 读取 {only_file!r}，再根据实际内容回答。' if only_file else '请先调用 list_project 查看目录，再按要求读取相关文本。'
    return {'folder':str(folder), 'task':task, 'only_file':only_file}
