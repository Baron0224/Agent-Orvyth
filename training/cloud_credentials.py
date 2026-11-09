"""Current-Windows-user DPAPI storage; callers must obtain consent before save/delete."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import tempfile


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def credential_path():
    base = Path(os.environ['LOCALAPPDATA'])
    return base / 'Orvyth' / 'credentials' / 'deepseek.dpapi'


def transform(data, decrypt=False):
    if os.name != 'nt':
        raise OSError('Windows required')
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    try:
        # UI forbidden, no LOCAL_MACHINE flag: scoped to the current user.
        if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
            raise OSError('Credential protection failed')
        return ctypes.string_at(result.data, result.size)
    finally:
        ctypes.memset(buffer, 0, len(buffer))
        if result.data:
            ctypes.memset(result.data, 0, result.size)
            kernel.LocalFree(result.data)


def load_key():
    path = credential_path()
    if not path.exists():
        return ''
    if path.stat().st_size > 65536:
        raise ValueError('Invalid credential file')
    key = transform(path.read_bytes(), decrypt=True).decode('utf8').strip()
    if not key:
        raise ValueError('Empty credential')
    return key


def save_key(key):
    if not key.strip():
        raise ValueError('Empty credential')
    encrypted = transform(key.encode('utf8'))
    path = credential_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.deepseek-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encrypted)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def forget_key():
    # Only the one fixed application file; no recursive removal.
    credential_path().unlink(missing_ok=True)
