"""浏览器版的本机 SQLite 存储，不写入 Git 仓库。"""

from chat_preferences import DEFAULTS, RETIRED, addressed, validate as validate_preferences
import base64
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, date, timedelta


def local_now():
    return datetime.now().astimezone()


class MissingRecord(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS owners (
                    id TEXT PRIMARY KEY, profile TEXT NOT NULL, active_chat TEXT);
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                    manual_title INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS chats_owner ON chats(owner, updated);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, chat TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS messages_chat ON messages(chat, id);
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
            """)
            if 'search_evidence' not in {row['name'] for row in db.execute('PRAGMA table_info(messages)')}:
                db.execute('ALTER TABLE messages ADD COLUMN search_evidence TEXT')
            columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)")}
            if 'task_trace' not in {row['name'] for row in db.execute('PRAGMA table_info(messages)')}:
                db.execute('ALTER TABLE messages ADD COLUMN task_trace TEXT')
            for name, kind in (("remind_time", "TEXT"), ("start_date", "TEXT"), ("end_date", "TEXT"), ("last_done_date", "TEXT"), ("due_at", "REAL")):
                if name not in columns:
                    db.execute(f"ALTER TABLE tasks ADD COLUMN {name} {kind}")
            db.execute("CREATE TABLE IF NOT EXISTS reminder_drafts (chat TEXT PRIMARY KEY, owner TEXT NOT NULL, data TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def key(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def owner(self, token=None, create=False):
        with self.connect() as db:
            if token and re.fullmatch(r"[A-Za-z0-9_-]{40,80}", token):
                owner = self.key(token)
                if db.execute("SELECT 1 FROM owners WHERE id=?", (owner,)).fetchone():
                    return token, owner
            if not create:
                return None, None
            token = secrets.token_urlsafe(32)
            owner = self.key(token)
            profile = {"name": "我的空间", "avatar": "", "pet_name": "小白", "pet_motion": True}
            db.execute("INSERT INTO owners(id, profile) VALUES (?,?)", (owner, json.dumps(profile)))
            chat = self._new_chat(db, owner)
            db.execute("UPDATE owners SET active_chat=? WHERE id=?", (chat, owner))
            return token, owner

    def _new_chat(self, db, owner):
        chat = uuid.uuid4().hex
        now = time.time()
        db.execute("INSERT INTO chats(id,owner,title,created,updated) VALUES (?,?,?,?,?)", (chat, owner, "新聊天", now, now))
        return chat

    def require_chat(self, db, owner, chat):
        row = db.execute("SELECT * FROM chats WHERE id=? AND owner=?", (chat, owner)).fetchone()
        if not row:
            raise MissingRecord("找不到这段聊天，请刷新后重试。")
        return row

    def state(self, owner):
        with self.connect() as db:
            profile = db.execute("SELECT profile, active_chat FROM owners WHERE id=?", (owner,)).fetchone()
            chats = [dict(row) for row in db.execute("SELECT id,title,created,updated FROM chats WHERE owner=? ORDER BY updated DESC", (owner,))]
            tasks = []
            now = local_now()
            today = now.date().isoformat()
            for row in db.execute("SELECT * FROM tasks WHERE owner=? ORDER BY created DESC", (owner,)):
                item = dict(row)
                if item["remind_time"]:
                    if item["due_at"] is not None:
                        item["waiting"] = now.timestamp() < item["due_at"] and not item["last_done_date"]
                        item["expired"] = False
                        item["done"] = int(bool(item["last_done_date"]))
                    else:
                        expired = bool(item["end_date"] and today > item["end_date"])
                        scheduled = today < item["start_date"] or bool(item["last_done_date"] and item["last_done_date"] < today and now.strftime("%H:%M") < item["remind_time"])
                        item["waiting"] = scheduled
                        item["expired"] = expired
                        item["done"] = int(expired or scheduled or item["last_done_date"] == today)
                if item["remind_time"]:
                    item["occurrence_date"] = today
                    if item["due_at"] is not None:
                        item["remind_due"] = not item["done"] and not item["waiting"]
                    else:
                        item["remind_due"] = not item["done"] and not item["waiting"] and today >= item["start_date"] and now.strftime("%H:%M") >= item["remind_time"]
                tasks.append(item)
            messages = []
            for row in db.execute("SELECT role,content,task_trace FROM messages WHERE chat=? ORDER BY id", (profile["active_chat"],)):
                item={'role':row['role'],'content':row['content']}
                if row['task_trace']: item['task_trace']=json.loads(row['task_trace'])
                messages.append(item)
            return {"profile": {**DEFAULTS, **{k: v for k, v in json.loads(profile["profile"]).items() if k not in RETIRED}}, "chats": chats, "tasks": tasks,
                    "active_chat": profile["active_chat"], "messages": messages}

    def history(self, owner, chat):
        with self.connect() as db:
            self.require_chat(db, owner, chat)
            rows = db.execute("SELECT role,content FROM messages WHERE chat=? ORDER BY id DESC LIMIT 16", (chat,)).fetchall()
            return [dict(row) for row in reversed(rows)]

    def latest_search_evidence(self, owner, chat):
        """Only the immediately preceding assistant reply, in this owner's chat."""
        with self.connect() as db:
            self.require_chat(db, owner, chat)
            row = db.execute("SELECT search_evidence FROM messages WHERE chat=? AND role='assistant' ORDER BY id DESC LIMIT 1", (chat,)).fetchone()
            return json.loads(row[0]) if row and row[0] else None

    def chat_action(self, owner, action, chat=None, title=None):
        with self.connect() as db:
            if action == "new":
                chat = self._new_chat(db, owner)
            else:
                self.require_chat(db, owner, chat)
            if action in {"new", "open"}:
                db.execute("UPDATE owners SET active_chat=? WHERE id=?", (chat, owner))
            elif action == "rename":
                title = self.text(title, 60, "聊天标题")
                db.execute("UPDATE chats SET title=?,manual_title=1 WHERE id=?", (title, chat))
            elif action == "clear":
                db.execute("DELETE FROM messages WHERE chat=?", (chat,))
                db.execute("DELETE FROM reminder_drafts WHERE chat=? AND owner=?", (chat, owner))
                db.execute("UPDATE owners SET active_chat=? WHERE id=?", (chat, owner))
            elif action == "delete":
                db.execute("DELETE FROM messages WHERE chat=?", (chat,))
                db.execute("DELETE FROM chats WHERE id=?", (chat,))
                db.execute("DELETE FROM reminder_drafts WHERE chat=? AND owner=?", (chat, owner))
                active = db.execute("SELECT active_chat FROM owners WHERE id=?", (owner,)).fetchone()[0]
                if active == chat:
                    other = db.execute("SELECT id FROM chats WHERE owner=? ORDER BY updated DESC LIMIT 1", (owner,)).fetchone()
                    replacement = other[0] if other else self._new_chat(db, owner)
                    db.execute("UPDATE owners SET active_chat=? WHERE id=?", (replacement, owner))
            else:
                raise ValueError("未知聊天操作。")

    def save_pair(self, owner, chat, question, answer, task_trace=None, search_evidence=None):
        with self.connect() as db:
            row = self.require_chat(db, owner, chat)
            address = json.loads(db.execute("SELECT profile FROM owners WHERE id=?", (owner,)).fetchone()["profile"]).get("user_address", "")
            answer = addressed(answer, address)
            db.executemany("INSERT INTO messages(chat,role,content) VALUES (?,?,?)", [
                (chat, "user", question), (chat, "assistant", answer)])
            if search_evidence:
                db.execute('UPDATE messages SET search_evidence=? WHERE id=last_insert_rowid()', (json.dumps(search_evidence,ensure_ascii=False),))
            if task_trace:
                db.execute('UPDATE messages SET task_trace=? WHERE id=last_insert_rowid()', (json.dumps(task_trace,ensure_ascii=False),))
            title = row["title"]
            if not row["manual_title"] and title == "新聊天":
                title = re.sub(r"\s+", " ", question).strip()[:24]
            db.execute("UPDATE chats SET title=?,updated=? WHERE id=?", (title, time.time(), chat))

        return answer

    @staticmethod
    def text(value, limit, label):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise ValueError(f"{label}请输入 1 到 {limit} 字。")
        return value.strip()

    def save_profile(self, owner, payload):
        name = self.text(payload.get("name"), 24, "昵称")
        pet_name = self.text(payload.get("pet_name"), 16, "精灵名字")
        avatar = payload.get("avatar", "")
        motion = payload.get("pet_motion", True)
        kind = payload.get("pet_kind")
        if kind is not None and kind not in ("dog", "cat", "rabbit", "robot"):
            raise ValueError("请选择小狗、小猫、小兔子或小机器人。")
        if not isinstance(motion, bool) or not isinstance(avatar, str):
            raise ValueError("资料格式不正确。")
        if avatar:
            prefix = "data:image/png;base64,"
            try:
                if not avatar.startswith(prefix):
                    raise ValueError()
                decoded = base64.b64decode(avatar[len(prefix):], validate=True)
                if len(decoded) > 150000 or not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError("头像请使用不超过 150KB 的 PNG 图片。") from None
        profile = {"name": name, "pet_name": pet_name, "avatar": avatar, "pet_motion": motion}
        with self.connect() as db:
            previous = db.execute("SELECT profile FROM owners WHERE id=?", (owner,)).fetchone()
            old_profile = json.loads(previous["profile"])
            preferences = validate_preferences({key: payload.get(key, old_profile.get(key, default)) for key, default in DEFAULTS.items()})
            profile.update(preferences)
            if kind is None:
                previous = db.execute("SELECT profile FROM owners WHERE id=?", (owner,)).fetchone()
                kind = json.loads(previous["profile"]).get("pet_kind", "dog")
            profile["pet_kind"] = kind
            db.execute("UPDATE owners SET profile=? WHERE id=?", (json.dumps(profile), owner))

    def task_action(self, owner, action, payload):
        with self.connect() as db:
            if action == "add":
                title = self.text(payload.get("title"), 160, "任务")
                db.execute("INSERT INTO tasks(id,owner,title,created) VALUES (?,?,?,?)", (uuid.uuid4().hex, owner, title, time.time()))
                return
            task = payload.get("id")
            row = db.execute("SELECT * FROM tasks WHERE id=? AND owner=?", (task, owner)).fetchone()
            if not row:
                raise MissingRecord("任务不存在。")
            if action == "toggle":
                if not isinstance(payload.get("done"), bool):
                    raise ValueError("任务状态不正确。")
                if row["remind_time"]:
                    today = local_now().date().isoformat()
                    if row["due_at"] is not None and local_now().timestamp() < row["due_at"]:
                        raise ValueError("提醒时间还没到。")
                    if row["due_at"] is None and row["end_date"] and today > row["end_date"]:
                        raise ValueError("这个周期已结束。")
                    if today < row["start_date"]:
                        raise ValueError("任务尚未开始。")
                    db.execute("UPDATE tasks SET last_done_date=? WHERE id=? AND owner=?", (today if payload["done"] else None, task, owner))
                else:
                    db.execute("UPDATE tasks SET done=? WHERE id=? AND owner=?", (int(payload["done"]), task, owner))
            elif action == "delete":
                db.execute("DELETE FROM tasks WHERE id=? AND owner=?", (task, owner))
            else:
                raise ValueError("未知任务操作。")

    def reminder_chat(self, owner, chat, question):
        from reminders import process_reminder
        with self.connect() as db:
            row = self.require_chat(db, owner, chat)
            saved = db.execute("SELECT data FROM reminder_drafts WHERE chat=? AND owner=?", (chat, owner)).fetchone()
            draft = json.loads(saved[0]) if saved else None
            result = process_reminder(question, draft, local_now())
            if result is None:
                return None
            reply, next_draft, task = result
            address = json.loads(db.execute("SELECT profile FROM owners WHERE id=?", (owner,)).fetchone()['profile']).get('user_address', '')
            reply = addressed(reply, address)
            if next_draft is None:
                db.execute("DELETE FROM reminder_drafts WHERE chat=? AND owner=?", (chat, owner))
            else:
                db.execute("INSERT INTO reminder_drafts(chat,owner,data) VALUES (?,?,?) ON CONFLICT(chat) DO UPDATE SET data=excluded.data,owner=excluded.owner", (chat,owner,json.dumps(next_draft,ensure_ascii=False)))
            if task:
                db.execute("INSERT INTO tasks(id,owner,title,created,remind_time,start_date,end_date,due_at) VALUES (?,?,?,?,?,?,?,?)", (uuid.uuid4().hex,owner,task["title"],time.time(),task["time"],task["start"],task["end"],task.get("due_at")))
            db.executemany("INSERT INTO messages(chat,role,content) VALUES (?,?,?)", [(chat,"user",question),(chat,"assistant",reply)])
            title = row["title"]
            if not row["manual_title"] and title == "新聊天":
                title = re.sub(r"\s+", " ", question).strip()[:24]
            db.execute("UPDATE chats SET title=?,updated=? WHERE id=?", (title,time.time(),chat))
            return reply
