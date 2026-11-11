"""Explicit desktop text-file creation; no overwrites or executable files."""
import os
from pathlib import Path
import re

import voice

def desktop_folder():
    if os.name=='nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                value=winreg.QueryValueEx(key,'Desktop')[0]
            folder=Path(os.path.expandvars(value))
            if folder.is_dir(): return folder.resolve()
        except OSError: pass
    for folder in (Path.home()/'Desktop',Path.home()/'OneDrive'/'桌面',Path.home()/'桌面'):
        if folder.is_dir(): return folder.resolve()
    raise OSError('没有找到系统桌面文件夹，请检查桌面位置。')

def clean_name(name):
    name=name.strip().strip('"“”「」`').strip()
    if not name or len(name)>100 or re.search(r'[<>:"/\\|?*\x00-\x1f]',name) or name.endswith(('.', ' ')):
        raise ValueError('文件名不能包含路径或特殊符号，请换一个简单的名字。')
    if re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',name):
        raise ValueError('这个名字被系统保留，请换一个文件名。')
    suffix=Path(name).suffix
    if suffix and suffix.lower()!='.txt':
        raise ValueError('目前桌面创建支持 .txt 文本文件，请使用 .txt 或省略扩展名。')
    return name if suffix else name+'.txt'

def write_request(question):
    if not ('桌面' in question and re.search(r'创建|新建|建立|建个|建一个',question) and re.search(r'文件|文档|文本',question)):
        return None
    if re.search(r'不要(?:在|创建|新建)|别(?:创建|新建)|先不(?:创建|新建)',question):
        return {'reply':'行，这次先不建了。'}
    name_match=re.search(r'(?:名字叫|命名为|名为|叫做|叫|文件名(?:为|是)?)[：:\s]*(.+?)(?=[，,；;\n]|(?:文档|文件)?(?:里面|里边|里)(?:写|面)|写入|写上|内容(?:是|为)|$)',question)
    content_match=re.search(r'(?:写入|写上|写下|内容(?:是|为))[：:\s]*(.+)',question,re.S)
    if not name_match or not content_match:
        return {'reply':'桌面文本文件可以建，请把文件名和内容一起告诉我，比如：在桌面新建文档，名字叫“你好”，内容是“我爱你”。'}
    content=content_match[1].strip()
    quoted=re.fullmatch(r'["“「`](.*?)["”」`](?:[吗呢]?[？?。！!]*)',content,re.S)
    if quoted: content=quoted[1]
    else: content=re.sub(r'吗[？?。！!]*$','',content).rstrip('？?')
    try: name=clean_name(name_match[1])
    except ValueError as error: return {'reply':str(error)}
    if not content or len(content)>12000:
        return {'reply':'请提供1到12000字的文本内容。'}
    return {'write':{'name':name,'content':content}}

def create_text_file(request, on_step=None):
    folder=desktop_folder()
    name=clean_name(request['name'])
    target=folder/name
    if on_step: on_step('准备创建文本文件',str(target))
    try:
        # Exclusive creation also prevents following an existing same-name link.
        with target.open('x',encoding='utf-8') as file:
            file.write(request['content'])
    except FileExistsError:
        if on_step: raise FileExistsError(f'桌面已有“{name}”，没有覆盖。请换一个文件名。')
        return voice.file_exists(name)
    if target.read_text(encoding='utf-8') != request['content']:
        raise OSError('文件已写入，但重新读取的内容不一致，请检查文件。')
    if on_step: on_step('已重新读取核对，内容一致',str(target))
    return voice.file_created(str(target), request['content'], target.parent == folder)
