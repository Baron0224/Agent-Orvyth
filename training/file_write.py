"""Explicit desktop text-file creation; no overwrites or executable files."""
import os
from pathlib import Path
import re

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
        return {'reply':'好，这次先不创建文件。'}
    name_match=re.search(r'(?:名字叫|命名为|名为|叫做|叫|文件名(?:为|是)?)[：:\s]*(.+?)(?=[，,；;\n]|(?:文档|文件)?(?:里面|里边|里)(?:写|面)|写入|写上|内容(?:是|为)|$)',question)
    content_match=re.search(r'(?:写入|写上|写下|内容(?:是|为))[：:\s]*(.+)',question,re.S)
    if not name_match or not content_match:
        return {'reply':'可以创建桌面文本文件。请把文件名和内容一起告诉我，例如：在桌面新建文档，名字叫“你好”，内容是“我爱你”。'}
    content=content_match[1].strip()
    quoted=re.fullmatch(r'["“「`](.*?)["”」`](?:[吗呢]?[？?。！!]*)',content,re.S)
    if quoted: content=quoted[1]
    else: content=re.sub(r'吗[？?。！!]*$','',content).rstrip('？?')
    try: name=clean_name(name_match[1])
    except ValueError as error: return {'reply':str(error)}
    if not content or len(content)>12000:
        return {'reply':'请提供1到12000字的文本内容。'}
    return {'write':{'name':name,'content':content}}

def create_text_file(request):
    folder=desktop_folder()
    name=clean_name(request['name'])
    target=folder/name
    try:
        # Exclusive creation also prevents following an existing same-name link.
        with target.open('x',encoding='utf-8') as file:
            file.write(request['content'])
    except FileExistsError:
        return f'桌面已经有“{name}”，我没有覆盖它。请换一个文件名再创建。'
    return f'已经在桌面创建“{name}”。\n保存位置：{target}\n内容：\n{request["content"]}'
