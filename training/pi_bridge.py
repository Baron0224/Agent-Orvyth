"""Bounded local Pi SDK subprocess; uses only project read tools."""
import json
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

BRIDGE = Path(__file__).with_name('pi') / 'bridge.mjs'

def available():
    return bool(shutil.which('node') and (BRIDGE.parent / 'node_modules/@earendil-works/pi-coding-agent/package.json').is_file())

def validate_request(payload):
    folder, task = payload.get('folder'), payload.get('task')
    if not isinstance(folder, str) or not folder.strip() or not Path(folder).is_absolute():
        raise ValueError('请填写项目文件夹的完整路径。')
    folder = Path(folder).resolve(strict=True)
    if not folder.is_dir():
        raise ValueError('项目文件夹不存在。')
    if not isinstance(task, str) or not 0 < len(task.strip()) <= 2000:
        raise ValueError('请输入2000字以内的任务。')
    return str(folder), task.strip()

def run_project(folder, task, model, timeout=180, only_file=None):
    if not available():
        raise RuntimeError('Pi 尚未安装，请在 training/pi 目录运行 npm ci --ignore-scripts。')
    process = subprocess.Popen([shutil.which('node'), str(BRIDGE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    events = queue.Queue()
    def read():
        # JSONL is split only at LF, not Unicode line separator characters.
        for line in process.stdout:
            events.put(line)
        events.put(None)
    threading.Thread(target=read, daemon=True).start()
    try:
        process.stdin.write(json.dumps({'folder':folder,'task':task,'model':model,'onlyFile':only_file},ensure_ascii=False).encode('utf-8'))
        process.stdin.close()
        deadline=time.monotonic()+timeout
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0: raise RuntimeError('任务超过3分钟，请缩小范围后重试。')
            try: line=events.get(timeout=min(remaining,1))
            except queue.Empty: continue
            if line is None: raise RuntimeError('Pi 提前退出，请检查安装和本地模型。')
            try: event=json.loads(line)
            except (ValueError,UnicodeDecodeError): continue
            if event.get('type') not in ('delta','tool','status','done','error'): continue
            yield event
            if event['type'] in ('done','error'): return
    finally:
        if process.poll() is None: process.kill()
        process.wait()
        process.stdout.close()
