"""本机 Orvyth：多聊天、个人资料、待办和本地模型流式回答。"""
import argparse
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import urllib.error
import urllib.request
import webbrowser
from browser_store import MissingRecord, Store
from chat_local import DEFAULT_MODEL, LocalChat, SYSTEM_PROMPT

ASSETS = Path(__file__).with_name("browser")

def default_database_path():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    legacy = base / "OpenAgent" / "browser.sqlite3"
    return legacy if legacy.exists() else base / "Orvyth" / "browser.sqlite3"

WEB_PRIVACY = (
    "浏览器版会将成功完成的聊天记录、待办任务、昵称、头像和偏好保存在这台电脑的 Orvyth 数据库中，"
    "关闭网页或重启服务后仍会保留。你可以在左侧删除聊天，在任务列表删除任务。"
    "回答时只把当前问题和有限的本聊天上下文发给本机 Ollama；头像和待办不会自动发给模型。"
    "这不是云同步，不同浏览器资料由本机 Cookie 区分；清除 Cookie 后会创建新的本机资料，旧数据库记录不会自动搬移。"
    "这不保证其他软件或操作系统没有日志。"
)
WEB_PROMPT = "\n".join(line for line in SYSTEM_PROMPT.splitlines() if not line.startswith((
    "当前问题和有限的对话历史", "退出本聊天程序", "关于保存或记录对话"))) + "\n" + WEB_PRIVACY

class ChatServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, port=8765, model=DEFAULT_MODEL, db_path=None):
        LocalChat(model)
        self.store = Store(db_path or default_database_path())
        self.model = model
        self.generation_lock = threading.Lock()
        self.chat_locks = {}
        self.locks_guard = threading.Lock()
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
    def chat_lock(self, chat):
        with self.locks_guard:
            return self.chat_locks.setdefault(chat, threading.Lock())
    def state(self, owner):
        return {**self.store.state(owner), "privacy": WEB_PRIVACY}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass
    def headers_for(self, status, content_type, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header("Set-Cookie", f"orvyth_session={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age=31536000")
    def json_response(self, status, payload, cookie=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.headers_for(status, "application/json; charset=utf-8", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def valid_host(self):
        if self.headers.get("Host") != self.server.origin.removeprefix("http://"):
            self.json_response(403, {"error": "请使用终端显示的本机地址打开页面。"})
            return False
        return True
    def owner(self, create=False):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            pass
        for name in ("orvyth_session", "openagent_session"):
            item = cookie.get(name)
            if item:
                token, owner = self.server.store.owner(item.value, False)
                if owner:
                    return token, owner
        return self.server.store.owner(None, create)
    def do_GET(self):
        if not self.valid_host():
            return
        if self.path == "/api/session":
            token, owner = self.owner(create=True)
            self.json_response(200, self.server.state(owner), token)
            return
        if self.path == "/api/status":
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open("http://127.0.0.1:11434/api/tags", timeout=3) as response:
                    models = json.load(response).get("models", [])
                ready = any(item.get("name") == self.server.model for item in models)
                self.json_response(200, {"ready": ready, "message": "可以聊天" if ready else "本地模型尚未下载，请按使用说明准备。"})
            except (OSError, ValueError, urllib.error.URLError):
                self.json_response(200, {"ready": False, "message": "请先打开 Ollama，再点检查连接。"})
            return
        assets = {"/particle-field.js": ("particle-field.js", "text/javascript"), "/assets/particle-ribbon.png": ("assets/particle-ribbon.png", "image/png"), "/": ("index.html", "text/html"), "/start": ("start.html", "text/html"), "/start.css": ("start.css", "text/css"), "/start.js": ("start.js", "text/javascript"), "/app.js": ("app.js", "text/javascript"), "/styles.css": ("styles.css", "text/css")}
        if self.path not in assets:
            self.json_response(404, {"error": "页面不存在。"})
            return
        filename, content_type = assets[self.path]
        body = (ASSETS / filename).read_bytes()
        self.headers_for(200, content_type if content_type.startswith("image/") else content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        if not self.valid_host():
            return
        if self.headers.get("Origin") != self.server.origin:
            self.json_response(403, {"error": "仅接受本机聊天页面发出的请求。"})
            return
        routes = {"/api/chat", "/api/clear", "/api/profile", "/api/chats/new", "/api/chats/open", "/api/chats/rename", "/api/chats/delete", "/api/tasks/add", "/api/tasks/toggle", "/api/tasks/delete"}
        if self.path not in routes:
            self.json_response(404, {"error": "接口不存在。"})
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.json_response(415, {"error": "请求格式应为 JSON。"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            limit = 230000 if self.path == "/api/profile" else 16384
            if not 0 < length <= limit or self.headers.get("Transfer-Encoding"):
                raise ValueError()
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            self.json_response(400, {"error": "请求内容为空、过大或格式不正确。"})
            return
        _, owner = self.owner()
        if not owner:
            self.json_response(410, {"error": "本机资料尚未载入，请刷新页面。"})
            return
        try:
            if self.path == "/api/profile":
                self.server.store.save_profile(owner, payload)
            elif self.path.startswith("/api/tasks/"):
                if self.path != "/api/tasks/add" and not isinstance(payload.get("id"), str):
                    raise ValueError("任务编号不正确。")
                self.server.store.task_action(owner, self.path.rsplit("/", 1)[1], payload)
            elif self.path == "/api/chats/new":
                self.server.store.chat_action(owner, "new")
            else:
                chat = payload.get("chat_id")
                if not isinstance(chat, str) or not re.fullmatch(r"[a-f0-9]{32}", chat):
                    raise ValueError("聊天编号不正确，请刷新页面。")
                lock = self.server.chat_lock(chat)
                if not lock.acquire(blocking=False):
                    self.json_response(409, {"error": "这段聊天正在回复，请稍后操作。"})
                    return
                try:
                    if self.path == "/api/chat":
                        self.stream_reply(owner, chat, payload)
                        return
                    action = "clear" if self.path == "/api/clear" else self.path.rsplit("/", 1)[1]
                    self.server.store.chat_action(owner, action, chat, payload.get("title"))
                finally:
                    lock.release()
            self.json_response(200, self.server.state(owner))
        except MissingRecord as error:
            self.json_response(404, {"error": str(error)})
        except ValueError as error:
            self.json_response(400, {"error": str(error)})
        except sqlite3.Error:
            self.json_response(503, {"error": "本机数据暂时无法读写，请稍后重试。"})
    def stream_reply(self, owner, chat, payload):
        question = Store.text(payload.get("message"), 2000, "消息")
        history = self.server.store.history(owner, chat)
        if not self.server.generation_lock.acquire(blocking=False):
            self.json_response(503, {"error": "模型正在回答另一条消息，请稍后重试。"})
            return
        try:
            self.headers_for(200, "application/x-ndjson; charset=utf-8")
            self.end_headers()
            def emit(data):
                self.wfile.write((json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
            local = LocalChat(self.server.model, system_prompt=WEB_PROMPT, privacy_notice=WEB_PRIVACY)
            local.history = history
            stream = local.reply(question)
            answer = []
            try:
                for content in stream:
                    answer.append(content)
                    emit({"type": "delta", "content": content})
                self.server.store.save_pair(owner, chat, question, "".join(answer))
                emit({"type": "done", "chat_id": chat})
            except (RuntimeError, ValueError, sqlite3.Error) as error:
                emit({"type": "error", "message": str(error) if not isinstance(error, sqlite3.Error) else "回答未能保存，请稍后重试。"})
            finally:
                stream.close()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            self.server.generation_lock.release()

def main():
    parser = argparse.ArgumentParser(description="Orvyth 本机浏览器聊天")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--data-dir", type=Path, help="指定本机数据目录；默认保存在用户应用数据目录")
    parser.add_argument("--open", action="store_true", help="启动后打开默认浏览器")
    args = parser.parse_args()
    try:
        server = ChatServer(args.port, args.model, args.data_dir / "browser.sqlite3" if args.data_dir else None)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"无法启动：{error}\n如果页面已经打开，可直接使用；端口被占用时可添加 --port 8766。\n")
    print(f"Orvyth 已启动：{server.origin}", flush=True)
    print(f"本机记录保存在：{server.store.path}", flush=True)
    print("保持此窗口开启；按 Ctrl+C 关闭。当前未联网搜索。", flush=True)
    if args.open:
        webbrowser.open(server.origin + "/start")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已关闭本机聊天服务。")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
