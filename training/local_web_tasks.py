"""Local 8775 work requests: explicit slots, bounded tools, durable evidence.

No account fallback, external sending, shell tools, or model calls live here.
"""
from collections import deque
from pathlib import Path
import os
import re

from file_lookup import SKIP, normalize, search_roots
from file_write import clean_name, create_text_file, desktop_folder
from project_lookup import named_project

TASK_VERSION = 1
MAX_CANDIDATES = 8
MAX_VISITED = 30000
MAX_SECONDS = 3


def enabled(provider, port):
    return provider == 'ollama' and port == 8775


def personal_reply(memory, owner, question):
    if memory.is_command(question):
        return None
    if re.search(r'我|本人|档案', question) and re.search(r'密码|验证码|密钥', question):
        return '档案里没有可用于回答的密码记录。我不会保存或展示凭据，请通过对应服务的官方渠道处理。'
    topics = []
    if re.search(r'我叫(?:什么|啥)|我的?(?:真实)?(?:姓名|名字)', question):
        topics.append(('姓名', r'(?:真实姓名|姓名|我的名字是|我叫)\s*[：:是]?\s*([^，。；;\n]+)'))
    if re.search(r'(?:我.*)?(?:在哪上学|在哪就读|我的学校|就读学校)', question):
        topics.append(('学校', r'(?:学校|就读学校|就读于|我在)\s*[：:是]?\s*([^，。；;\n]+)'))
    ordinary = re.search(r'我的(.{1,20}?)(?:是什么|叫什么|是谁)[？?。]*$', question)
    if not topics and not ordinary:
        return None
    try:
        entries = memory.entries(owner)
    except (OSError, ValueError):
        return '当前账户档案暂时无法读取，这次不能确认个人信息。'
    if ordinary and not topics:
        # An unstructured archive is not a licence to infer an unnamed personal fact.
        label = ordinary[1]
        if re.search(r'文件|路径|目录|项目|模型|任务|记忆|档案', label):
            return None
        topics = [(label, re.escape(label) + r'\s*[：:是]\s*([^，。；;\n]+)')]
    answers = []
    for label, pattern in topics:
        values = {m[1].strip() for item in entries for m in re.finditer(pattern, item['content'])}
        if label == '姓名':
            values = {v for v in values if not re.search(r'学校|学院|大学|学生|大[一二三四]|\d|密码|密钥', v)}
        values = {v for v in values if not re.search(r'密码|密钥|验证码', v)}
        if len(values) == 1:
            answers.append(label + '：' + next(iter(values)))
        elif values:
            answers.append(label + '：档案里有多条不同记录，需要你确认，不能替你选。')
        else:
            answers.append(label + '：当前账户档案里没有能确认的记录。')
    return '\n'.join(answers)


def _quoted_paths(text):
    return [Path(v) for v in re.findall(r'["“`]([^"”`\n]+)["”`]', text)
            if re.match(r'[A-Za-z]:[\\/]|/', v)]


def _state(action, slots=None, **extra):
    return {'kind': 'local_task', 'local_task': {'version': TASK_VERSION, 'action': action,
            'phase': 'needs_input', 'slots': slots or {}}, **extra}


def _reply(text, state):
    return {'reply': text, 'file_lookup': state}


def _scan(fragment, roots):
    """Names only; shared legacy lookup rejects two-character names such as 简历."""
    import time
    deadline = time.monotonic() + MAX_SECONDS
    pending = deque((Path(root), 0) for root in roots)
    seen, hits, visited, limited = set(), [], 0, False
    while pending and visited < MAX_VISITED and time.monotonic() < deadline:
        folder, depth = pending.popleft()
        try:
            if folder.name.casefold() in SKIP or folder.is_symlink() or folder.is_junction():
                continue
            key = str(folder.resolve()).casefold()
            if key in seen:
                continue
            seen.add(key)
            with os.scandir(folder) as entries:
                for entry in entries:
                    visited += 1
                    if visited >= MAX_VISITED or time.monotonic() >= deadline:
                        limited = True
                        break
                    path = Path(entry.path)
                    if entry.name.startswith('.') or entry.name.casefold() in SKIP or entry.is_symlink() or path.is_junction():
                        continue
                    if entry.is_file(follow_symlinks=False) and normalize(fragment) in normalize(path.stem):
                        hits.append(str(path.resolve()))
                        if len(hits) >= MAX_CANDIDATES:
                            return sorted(hits), True
                    elif entry.is_dir(follow_symlinks=False):
                        if depth < 6:
                            pending.append((path, depth + 1))
                        else:
                            limited = True
        except OSError:
            limited = True
    return sorted(set(hits)), limited or bool(pending)


def route(question, context=None):
    """A plan carries local_task v1: action / phase / slots, plus preview evidence."""
    context = context or {}
    task = context.get('local_task') or {}
    if task.get('version') != TASK_VERSION:
        task = {}
    short = re.sub(r'[\s，。？！?!]', '', question)
    paths = _quoted_paths(question)
    sending = bool(re.search(r'发给|发送给|传给|发过去|发送文件', question))
    creating = bool(re.search(r'创建|新建|建立|建个|建一个|写个|写一个', question) and re.search(r'文件|文本|文档|\.txt', question))
    finding = bool(re.search(r'查找|找一下|找找|找到|寻找|搜索|找', question) and re.search(r'文件|简历|\.png|\.txt|图片', question))
    if finding and named_project(question) and not (sending or creating):
        return None  # Existing project-scoped lookup owns its artifact/type parsing.
    if (sending or creating or finding) and re.search(r'不要|别(?:创建|新建|找|发)|先不(?:创建|新建|找|发)', question):
        state = _state('cancel')
        state['local_task']['phase'] = 'cancelled'
        return _reply('这轮先不执行文件操作。', state)
    if short in ('取消', '算了', '先不做了') and task:
        state = {**context, 'local_task': {**task, 'phase': 'cancelled'}}
        return _reply('已停止这项文件任务。', state)
    if short in ('继续', '接着做', '继续刚才的任务'):
        if not task or task.get('phase') == 'cancelled':
            return _reply('当前聊天没有可接续的文件任务。告诉我要继续哪件事。', _state('clarify'))
        if context.get('paths'):
            return _candidates(context, '接着上次的文件任务；候选顺序和选择保持不变：')
        if task['action'] == 'create' and task.get('phase') == 'completed':
            path = Path(task['slots']['path'])
            return _reply('上次创建的文件：`' + str(path) + '`。' + ('文件仍存在；没有再次创建或覆盖。' if path.is_file() else '文件现在不存在，不能说它仍可用。'), context)
        return _reply(task.get('prompt', '请补充这项任务缺少的参数。'), context)
    if context.get('kind') == 'file_lookup' and task and not (sending or creating or finding):
        selection = re.fullmatch(r'(?:选|选择|预览|看)?第?([0-9]+|[一二三四五六七八])(?:个|项|张|张图|个文件)?', short)
        if selection:
            index = int(selection[1]) - 1 if selection[1].isdigit() else '一二三四五六七八'.index(selection[1])
            if not 0 <= index < len(context.get('paths', [])):
                return _candidates(context, '请指定列表内的一个序号：')
            state = {**context, 'selected_index': index,
                     'local_task': {**task, 'phase': 'selected'}}
            return _candidates(state, '已选中第' + str(index + 1) + '个候选；仅定位名称，尚未读取内容：')
        if short in ('返回候选列表', '不是这个', '不对', '返回列表'):
            return _candidates({**context, 'selected_index': None,
                                'local_task': {**task, 'phase': 'candidates'}}, '原候选列表如下：')
    pending = task.get('phase') == 'needs_input'
    if sending or (pending and task.get('action') == 'send' and (paths or re.search(r'邮箱|邮件|微信|QQ|渠道|收件人', question))):
        slots = dict(task.get('slots', {})) if pending and task.get('action') == 'send' else {}
        recipient = re.search(r'(?:发给|发送给|传给|收件人[：:是]?)[\s]*(.{1,24}?)(?=[，,。；;\n]|$)', question)
        channel = re.search(r'邮件|邮箱|微信|QQ', question)
        if recipient:
            slots['recipient_label'] = recipient[1].strip()
        if channel:
            slots['channel'] = channel[0]
        if paths and paths[0].is_file():
            slots['path'] = str(paths[0].resolve())
        state = _state('send', slots)
        missing = ([] if slots.get('path') else ['哪个文件（候选或完整路径）']) + ([] if slots.get('channel') else ['发送渠道'])
        prompt = ('收件人先记为“' + slots['recipient_label'] + '”；' if slots.get('recipient_label') else '')
        prompt += ('还缺' + '、'.join(missing) + '。' if missing else '文件和渠道已记录。')
        prompt += '收件人信息还需核对。我目前没有发送工具，只能帮你定位和准备，不能替你发出。'
        state['local_task']['prompt'] = prompt
        return _reply(prompt, state)
    if creating or (pending and task.get('action') == 'create' and re.search(r'名字|文件名|内容|写入|里面写|桌面|[A-Za-z]:[\\/]', question)):
        slots = dict(task.get('slots', {})) if pending and task.get('action') == 'create' else {}
        if '桌面' in question:
            slots['desktop'] = True
        content = re.search(r'(?:里面写|里边写|里写|写入|写上|写下|内容(?:是|为))[：:\s]*(.*)', question, re.S)
        head = question[:content.start()] if content else question
        name = re.search(r'(?:名字叫|命名为|名为|叫做|文件名(?:为|是)?|叫)[：:\s]*([^，,；;\n]+)', head)
        if name:
            slots['name'] = name[1].strip().strip('"“”`')
        if paths:
            if paths[0].suffix.lower() == '.txt':
                slots.update(path=str(paths[0]), name=paths[0].name)
            else:
                slots['folder'] = str(paths[0])
        if content:
            value = content[1].strip()
            quoted = re.fullmatch(r'["“`](.*)["”`][。！!]*', value, re.S)
            slots['content'] = quoted[1] if quoted else value
        state = _state('create', slots)
        missing = []
        if not slots.get('name'):
            missing.append('文件名')
        if not slots.get('content'):
            missing.append('要写入的内容')
        if not any(slots.get(k) for k in ('desktop', 'path', 'folder')):
            missing.append('保存目录（或说桌面）')
        if missing:
            prompt = '还缺' + '、'.join(missing) + '，其余已提供的信息会保留。'
            state['local_task']['prompt'] = prompt
            return _reply(prompt, state)
        try:
            name = clean_name(slots['name'])
            target = Path(slots['path']) if slots.get('path') else (desktop_folder() if slots.get('desktop') else Path(slots['folder'])) / name
            if not target.is_absolute() or not target.parent.is_dir():
                raise ValueError('保存目录不存在或不是完整路径。请补充一个已有目录。')
            if any(p.is_symlink() or p.is_junction() for p in (target, *target.parents)):
                raise ValueError('不能写入链接路径。')
            if len(slots['content']) > 12000:
                raise ValueError('文本内容不能超过12000字。')
            slots.update(name=name, path=str(target.resolve()))
            state['local_task']['phase'] = 'ready'
        except (OSError, ValueError) as error:
            state['local_task']['prompt'] = str(error)
            return _reply(str(error), state)
        return {'local_text_write': slots, 'file_lookup': state}
    if finding or (pending and task.get('action') == 'find' and paths):
        old = task.get('slots', {}) if pending and task.get('action') == 'find' else {}
        without_paths = re.sub(r'["“`][^"”`]+["”`]', '', question) if paths else question
        found = re.search(r'(?:查找|找一下|找找|找到|寻找|搜索|找)\s*(.*)', without_paths)
        fragment = found[1] if found else ''
        fragment = re.sub(r'^(?:\s|里面|里的|中|里|内|的)+', '', fragment).strip(' ，,。')
        fragment = re.split(r'[,，;；]\s*(?:在|目录|范围)', fragment, maxsplit=1)[0]
        fragment = re.sub(r'(?:按)?(?:文件名)?(?:片段)?[：:]*', '', fragment)
        fragment = re.sub(r'(?:的)?(?:文件|图片)(?:候选)?[。！!？?]*$', '', fragment).strip(' ，,。')
        fragment = fragment or old.get('fragment', '')
        roots = paths or [Path(p) for p in old.get('roots', [])] or search_roots()
        state = _state('find', {'fragment': fragment, 'roots': [str(p) for p in roots]})
        if len(normalize(fragment)) < 2:
            prompt = '还缺要查找的文件名片段，请提供至少两个字符。'
            state['local_task']['prompt'] = prompt
            return _reply(prompt, state)
        hits, limited = _scan(fragment, roots)
        state.update(kind='file_lookup', paths=hits, roots=[str(p.resolve()) for p in roots],
                     selected_index=None, match='name_only', status='limited' if limited else 'searched')
        state['local_task']['phase'] = 'candidates' if hits else 'needs_input'
        if hits:
            return _candidates(state, '找到名称候选，尚未核实内容：')
        prompt = '在这些目录按名称片段“' + fragment + '”没有找到文件：' + '、'.join(map(str, roots)) + '。'
        prompt += '搜索受时间、深度、数量或权限限制，不能断言其他位置没有。请补充下一步要查的目录。'
        state['local_task']['prompt'] = prompt
        return _reply(prompt, state)
    return None


def _candidates(state, prefix):
    selected = state.get('selected_index')
    items = [(i, p) for i, p in enumerate(state.get('paths', [])) if selected is None or i == selected]
    text = prefix + '\n' + '\n'.join(f'{i+1}. `{p}`' for i, p in items)
    if selected is not None:
        text += '\n图片可使用下方预览；文本目前没有图片预览。可说“返回候选列表”。'
    else:
        text += '\n请指定序号。搜索范围：' + '、'.join(state.get('roots', []))
    if state.get('status') == 'limited':
        text += '\n搜索达到限制或部分目录不可访问，候选可能不全。'
    return _reply(text, state)


def create_text(slots, on_step):
    """Same exclusive-create/read-back contract as desktop text creation."""
    target = Path(slots['path'])
    clean_name(target.name)
    if any(p.is_symlink() or p.is_junction() for p in (target, *target.parents)):
        raise ValueError('不能写入链接路径。')
    if slots.get('desktop') and target.parent == desktop_folder():
        return create_text_file(slots, on_step=on_step)
    on_step('准备创建文本文件', str(target))
    with target.open('x', encoding='utf-8', newline='') as stream:
        stream.write(slots['content'])
    if target.read_bytes() != slots['content'].encode('utf-8'):
        raise OSError('写入后内容核对不一致，不能确认成功。')
    on_step('已重新读取核对，内容一致', str(target))
    return '已创建并逐字核对文本文件：`' + str(target) + '`\n内容：\n' + slots['content']
