"""Explicit local Word creation through pinned docx-cli."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET
from file_write import desktop_folder, clean_name


def word_request(question):
    if not re.search(r'word|docx', question, re.I) or not re.search(r'做|创建|新建|生成|建个|建一个', question):
        return None
    if re.search(r'不要|先不|别(?:做|创建|新建|生成)', question):
        return {'reply': '好，这次先不创建 Word。'}
    if re.search(r'[A-Za-z]:[\\/]|保存到|放到|放在', question) and '桌面' not in question:
        return {'reply': '目前新建 Word 默认保存在桌面。请确认保存到桌面，并告诉我文档内容。'}
    match = re.search(r'(?:里面|里边|里|中)(?:写入|写上|写下|写)|内容(?:是|为)|写入|写上', question)
    if not match:
        return {'reply': '告诉我 Word 里要写什么，例如：帮我做一个 Word，里面写“你好”。默认保存在桌面。'}
    content = question[match.end():].lstrip('：: ').strip()
    quoted = re.fullmatch(r'[“"「](.*)[”"」][。！!？?]*', content, re.S)
    if quoted:
        content = quoted[1]
    if not content or len(content) > 12000:
        return {'reply': '请提供1到12000字的文档内容。'}
    name_match = re.search(r'(?:名字叫|命名为|名为|文件名是)[：:\s]*[“"]?([^”"，,。\n]+)', question[:match.start()])
    name = name_match[1].strip() if name_match else 'Word文档-' + str(time.time_ns())
    name = re.sub(r'\.docx$', '', name, flags=re.I)
    try:
        name = clean_name(name).removesuffix('.txt') + '.docx'
    except ValueError as error:
        return {'reply': str(error)}
    return {'word_write': {'name': name, 'content': content}}


def create_word_file(request, on_step=None):
    folder = desktop_folder()
    name = request['name']
    if Path(name).name != name or not name.endswith('.docx'):
        raise ValueError('Word文件名不正确。')
    clean_name(name[:-5])
    target = folder / name
    binary = os.environ.get('ORVYTH_DOCX_CLI') or str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Orvyth/tools/docx-cli/v0.27.0/docx.exe')
    def run(args):
        try:
            subprocess.run([binary, *args], check=True, capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except FileNotFoundError:
            raise OSError('没有找到Word工具程序，请检查 docx-cli 安装路径。') from None
        except subprocess.TimeoutExpired:
            raise OSError(f'Word{args[0]}步骤超时，请稍后重试。') from None
        except subprocess.CalledProcessError as error:
            detail=(error.stdout or error.stderr or b'').decode('utf-8', errors='replace')[:600]
            raise OSError(f'Word{args[0]}步骤失败（退出码{error.returncode}）：{detail}') from None
        except OSError as error:
            raise OSError(f'无法启动Word工具（系统错误码{error.winerror if hasattr(error,"winerror") else error.errno}）。') from None
    if on_step: on_step('正在创建Word文档', str(target))
    with tempfile.TemporaryDirectory(prefix='orvyth-create-word-') as base:
        source = Path(base) / 'content.txt'
        source.write_text(request['content'], encoding='utf-8')
        output = Path(base) / 'output.docx'
        run(['create', str(output), '--text-file', str(source)])
        run(['validate', str(output)])
        with zipfile.ZipFile(output) as archive:
            xml = ET.fromstring(archive.read('word/document.xml'))
        text = ''.join(xml.itertext())
        for line in request['content'].splitlines():
            if line and line not in text:
                raise OSError('Word内容核对失败，未保存到桌面。')
        with target.open('xb') as file:
            file.write(output.read_bytes())
    if on_step: on_step('已校验Word结构与内容', str(target))
    return f'已经在桌面创建“{name}”。\n保存位置：{target}'
