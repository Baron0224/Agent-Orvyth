"""Orvyth adapters for Hermes MemoryStore dependencies and per-owner paths."""
from contextvars import ContextVar
from pathlib import Path
import os
import tempfile
try:
    import fcntl
except ImportError:
    fcntl=None
try:
    import msvcrt
except ImportError:
    msvcrt=None

memory_root=ContextVar('orvyth_hermes_memory_root')

def get_memory_dir():
    return memory_root.get()

def mkdir_under_hermes_home(directory):
    root=get_memory_dir().resolve()
    directory=Path(directory).resolve()
    directory.relative_to(root)
    directory.mkdir(parents=True,exist_ok=True)

def atomic_write_text(path, content, tmp_prefix='.mem_'):
    path=Path(path)
    mkdir_under_hermes_home(path.parent)
    fd,temporary=tempfile.mkstemp(prefix=tmp_prefix,dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as file:
            file.write(content);file.flush();os.fsync(file.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def _memory_target_error(store, target, operations=None):
    return None if target in ('memory','user') else {'success':False,'error':'Unknown memory target'}
