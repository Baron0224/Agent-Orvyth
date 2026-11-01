"""仅供本机开发使用的 OpenAgent 浏览器聊天服务。"""

import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from chat_local import DEFAULT_MODEL, LocalChat, PRIVACY_NOTICE


ASSETS = Path(__file__).with_name("browser")
SESSION_TTL = 30 * 60


class Session:
    def __init__(self, model):
        self.chat = LocalChat(model)
        self.lock = threading.Lock()
        self.touched = time.monotonic()


class ChatServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=8765, model=DEFAULT_MODEL):
        LocalChat(model)  # 在启动时验证本地模型配置。
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.model = model
        self.sessions = {}
        self.sessions_lock = threading.Lock()
        self.generation_lock = threading.Lock()

    def session(self, cookie_header, create=False):
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header or "")
        except Exception:
            return None, None
        value = cookie.get("openagent_session")
        token = value.value if value else None
        now = time.monotonic()
        with self.sessions_lock:
            for key, session in list(self.sessions.items()):
                if now - session.touched > SESSION_TTL and not session.lock.locked():
                    del self.sessions[key]
            if token in self.sessions:
                session = self.sessions[token]
            elif create and len(self.sessions) < 32:
                token = secrets.token_urlsafe(32)
                session = self.sessions[token] = Session(self.model)
            else:
                return None, None
            session.touched = now
            return token, session


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # 不在访问日志中输出请求或聊天内容。

    def headers_for(self, status, content_type, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header("Set-Cookie", f"openagent_session={cookie}; HttpOnly; SameSite=Strict; Path=/")

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

    def do_GET(self):
        if not self.valid_host():
            return
        if self.path == "/api/session":
            token, session = self.server.session(self.headers.get("Cookie"), create=True)
            if not session:
                self.json_response(503, {"error": "会话已满，请稍后再试。"})
                return
            if not session.lock.acquire(blocking=False):
                self.json_response(409, {"error": "上一条回复仍在生成，请稍后刷新。"})
                return
            try:
                self.json_response(200, {"messages": session.chat.history, "privacy": PRIVACY_NOTICE}, token)
            finally:
                session.lock.release()
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
        assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/styles.css": ("styles.css", "text/css")}
        if self.path not in assets:
            self.json_response(404, {"error": "页面不存在。"})
            return
        filename, content_type = assets[self.path]
        body = (ASSETS / filename).read_bytes()
        self.headers_for(200, content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self.valid_host():
            return
        if self.headers.get("Origin") != self.server.origin:
            self.json_response(403, {"error": "仅接受本机聊天页面发出的请求。"})
            return
        if self.path not in {"/api/chat", "/api/clear"}:
            self.json_response(404, {"error": "接口不存在。"})
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.json_response(415, {"error": "请求格式应为 JSON。"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384 or self.headers.get("Transfer-Encoding"):
                raise ValueError()
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            self.json_response(400, {"error": "请求内容为空、过大或格式不正确。"})
            return
        _, session = self.server.session(self.headers.get("Cookie"))
        if session is None:
            self.json_response(410, {"error": "会话已过期，请刷新页面重新开始。"})
            return
        question = payload.get("message")
        if self.path == "/api/chat" and (not isinstance(question, str) or not question.strip() or len(question) > 2000):
            self.json_response(400, {"error": "请输入 1 到 2000 字的消息。"})
            return
        if not session.lock.acquire(blocking=False):
            self.json_response(409, {"error": "请等当前回复结束后再操作。"})
            return
        try:
            if self.path == "/api/clear":
                session.chat.clear()
                self.json_response(200, {"ok": True})
                return
            if not self.server.generation_lock.acquire(blocking=False):
                self.json_response(503, {"error": "模型正在回答另一条消息，请稍后重试。"})
                return
            try:
                self.headers_for(200, "application/x-ndjson; charset=utf-8")
                self.end_headers()

                def emit(payload):
                    self.wfile.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
                    self.wfile.flush()

                stream = session.chat.reply(question.strip())
                try:
                    for content in stream:
                        emit({"type": "delta", "content": content})
                    emit({"type": "done"})
                except (RuntimeError, ValueError) as error:
                    emit({"type": "error", "message": str(error)})
                finally:
                    stream.close()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                self.server.generation_lock.release()
        finally:
            session.touched = time.monotonic()
            session.lock.release()


def main():
    parser = argparse.ArgumentParser(description="OpenAgent 本机浏览器聊天")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--open", action="store_true", help="启动后打开默认浏览器")
    args = parser.parse_args()
    try:
        server = ChatServer(args.port, args.model)
    except (OSError, ValueError) as error:
        parser.exit(1, f"无法启动：{error}\n如果页面已经打开，可直接使用；端口被占用时可添加 --port 8766。\n")
    print(f"OpenAgent 已启动：{server.origin}", flush=True)
    print("保持此窗口开启；按 Ctrl+C 关闭。聊天仅临时保留，当前未联网搜索。", flush=True)
    if args.open:
        webbrowser.open(server.origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已关闭本机聊天服务。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
