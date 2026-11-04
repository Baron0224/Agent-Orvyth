"""Bounded name lookup in local document/project folders; never follows links."""
from collections import deque
import os
from pathlib import Path
import re
import time

SKIP = {'.git', '.venv', 'venv', 'node_modules', '.ssh', '.aws', '.pi', 'cache', 'appdata', 'vendor', '__pycache__'}

def normalize(text):
    return re.sub(r'[^\w\u4e00-\u9fff]', '', text.casefold()).replace('_','')

def query_name(question):
    quoted = re.findall(r'["“`「]([^"”`」\r\n]+)["”`」]', question)
    if quoted: return quoted[0]
    english = re.search(r'[a-zA-Z][a-zA-Z0-9_.-]*(?: +[a-zA-Z0-9_.-]+)*', question)
    if english: return english.group().strip()
    name = re.sub(r'^(?:请|帮我|替我|我想|能不能|调取|读取|查看|打开|找一下|看一下|读一下|总结|分析|我|文档里|文档中|桌面上|的)+', '', question)
    return re.split(r'中的|里的|的内容|的故事|，|。|？', name)[0].strip()

def search_roots():
    configured = os.environ.get('ORVYTH_FILE_ROOTS')
    if configured: return [Path(p) for p in configured.split(os.pathsep) if p.strip()]
    home = Path.home()
    project = Path(__file__).resolve().parents[1]
    candidates = [home/'Documents', home/'Desktop', home/'桌面', project, project.parent]
    for cloud in (home/'OneDrive',):
        candidates.extend(cloud/name for name in ('Documents','文档','เอกสาร','Desktop','桌面'))
    return [p for p in candidates if p.is_dir()]

def find_matches(name, roots=None, seconds=3, limit=30000):
    key = normalize(name)
    if len(key)<3: return []
    roots = search_roots() if roots is None else roots
    queue = deque((Path(p), 0) for p in roots)
    seen=set(); matches=[]; visited=0; deadline=time.monotonic()+seconds
    while queue and visited<limit and time.monotonic()<deadline:
        folder,depth=queue.popleft()
        try:
            canonical=str(folder.resolve()).casefold()
            if canonical in seen: continue
            seen.add(canonical)
            with os.scandir(folder) as entries:
                for entry in entries:
                    visited+=1
                    if visited>=limit or time.monotonic()>=deadline: break
                    if entry.name.casefold() in SKIP or entry.name.startswith('.') or entry.is_symlink(): continue
                    target=Path(entry.path)
                    if hasattr(target,'is_junction') and target.is_junction(): continue
                    is_dir=entry.is_dir(follow_symlinks=False)
                    if key in normalize(target.stem if not is_dir else target.name):
                        matches.append(target.resolve())
                        if len(matches)>=8: return sorted(set(matches),key=str)
                        # The project itself is enough; let Pi inspect its contents.
                        continue
                    if is_dir and depth<6: queue.append((target,depth+1))
        except OSError: continue
    return sorted(set(matches),key=str)
