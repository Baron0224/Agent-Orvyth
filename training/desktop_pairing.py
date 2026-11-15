"""Local desktop pairing: a browser approves, only the waiting app gets the key."""
from contextlib import closing
import hashlib
import re
import secrets
import socket
import sqlite3
import threading
import time

PAIR_SECONDS = 300


class DesktopPairing:
    def __init__(self, path, owner):
        self.path = path
        self.owner = owner
        self.lock = threading.Lock()
        self.pending = {}
        self.connections = {}
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS desktop_keys (digest TEXT PRIMARY KEY, owner TEXT NOT NULL, label TEXT NOT NULL)')

    def clean(self):
        now = time.monotonic()
        self.pending = {k: v for k, v in self.pending.items() if v[1] > now}

    def start(self):
        with self.lock:
            self.clean()
            if len(self.pending) >= 8:
                raise ValueError('待确认的配对太多，请稍后再试。')
            code = str(secrets.randbelow(90000000) + 10000000)
            while code in self.pending:
                code = str(secrets.randbelow(90000000) + 10000000)
            proof = secrets.token_urlsafe(32)
            self.pending[code] = (proof, time.monotonic() + PAIR_SECONDS, False)
            return {'code': code, 'proof': proof}

    def approve(self, code):
        with self.lock:
            self.clean()
            proof, expires, approved = self.pending.get(code, ('', 0, False))
            if not proof or approved:
                raise ValueError('确认码无效、已使用或已过期。')
            self.pending[code] = (proof, expires, True)

    def claim(self, code, proof):
        with self.lock:
            self.clean()
            pending = self.pending.get(code)
            if not pending or not secrets.compare_digest(proof, pending[0]):
                raise ValueError('配对请求无效或已过期，请重新开始。')
            if not pending[2]:
                return {'waiting': True}
            token = secrets.token_urlsafe(32)
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute('INSERT INTO desktop_keys VALUES (?,?,?)',
                           (self.digest(token), self.owner, token[:4]))
            del self.pending[code]
            return {'token': token}

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def authorize(self, token, connection):
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            return None
        digest = self.digest(token)
        with self.lock, closing(sqlite3.connect(self.path)) as db:
            if not db.execute('SELECT 1 FROM desktop_keys WHERE digest=? AND owner=?', (digest, self.owner)).fetchone():
                return None
            self.connections.setdefault(digest, set()).add(connection)
        return digest

    def release(self, digest, connection):
        with self.lock:
            active = self.connections.get(digest)
            if active is not None:
                active.discard(connection)
                if not active:
                    self.connections.pop(digest, None)

    def list(self):
        with self.lock, closing(sqlite3.connect(self.path)) as db:
            return [{'id': digest, 'label': label, 'length': 43} for digest, label in
                    db.execute('SELECT digest,label FROM desktop_keys WHERE owner=?', (self.owner,))]

    def revoke(self, digest):
        with self.lock:
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute('DELETE FROM desktop_keys WHERE digest=? AND owner=?', (digest, self.owner))
            for client in self.connections.pop(digest, ()):
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
