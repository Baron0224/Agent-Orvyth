"""本机 HTTP 边界、会话隔离和流式恢复；不下载或调用真实模型。"""

import http.client
import json
import threading
import time
import unittest
from unittest.mock import patch

from chat_web import ChatServer, SESSION_TTL


def fake_reply(chat, question):
    yield "测试回答"
    if question == "模拟失败":
        raise RuntimeError("模型连接中断")
    chat.history.extend([
        {"role": "user", "content": question},
        {"role": "assistant", "content": "测试回答"},
    ])


class WebChatTest(unittest.TestCase):
    def setUp(self):
        self.server = ChatServer(port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        _, headers, data = self.request("GET", "/api/session")
        self.cookie = headers["Set-Cookie"].split(";")[0]
        self.assertEqual(data["messages"], [])
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, payload=None, extra_headers=None):
        headers = {"Origin": self.server.origin}
        if hasattr(self, "cookie"):
            headers["Cookie"] = self.cookie
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        headers.update(extra_headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read().decode("utf-8")
            content_type = response.getheader("Content-Type", "")
            data = ([json.loads(line) for line in raw.splitlines()]
                    if "ndjson" in content_type else json.loads(raw) if "json" in content_type else raw)
            return response.status, dict(response.getheaders()), data
        finally:
            connection.close()

    def test_assets_and_path_boundary(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("输入消息", body)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("GET", "/../chat_local.py")[0], 404)

    def test_stream_history_isolation_and_clear(self):
        with patch("chat_web.LocalChat.reply", fake_reply):
            status, _, data = self.request("POST", "/api/chat", {"message": "你好"})
        self.assertEqual(status, 200)
        self.assertEqual(data, [{"type": "delta", "content": "测试回答"}, {"type": "done"}])
        self.assertEqual(len(self.request("GET", "/api/session")[2]["messages"]), 2)
        other = self.request("GET", "/api/session", extra_headers={"Cookie": ""})[2]
        self.assertEqual(other["messages"], [])
        self.assertEqual(self.request("POST", "/api/clear", {})[0], 200)
        self.assertEqual(self.request("GET", "/api/session")[2]["messages"], [])

    def test_stream_error_does_not_store_partial_answer(self):
        with patch("chat_web.LocalChat.reply", fake_reply):
            _, _, data = self.request("POST", "/api/chat", {"message": "模拟失败"})
        self.assertEqual(data[-1], {"type": "error", "message": "模型连接中断"})
        self.assertEqual(self.request("GET", "/api/session")[2]["messages"], [])
        self.assertFalse(self.server.generation_lock.locked())

    def test_host_and_cross_origin_rejected(self):
        self.assertEqual(self.request("GET", "/", extra_headers={"Host": "untrusted.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/chat", {"message": "你好"}, {"Origin": "http://untrusted.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/clear", {}, {"Origin": ""})[0], 403)

    def test_invalid_messages_rejected(self):
        for value in ["", "  ", None, 1, "字" * 2001]:
            with self.subTest(value=str(value)[:10]):
                self.assertEqual(self.request("POST", "/api/chat", {"message": value})[0], 400)
        self.assertEqual(self.request("POST", "/api/chat", ["not", "object"])[0], 400)
        self.assertEqual(self.request("POST", "/api/chat", {}, {"Content-Type": "text/plain"})[0], 415)

    def test_busy_requests_rejected_without_losing_session(self):
        _, session = self.server.session(self.cookie)
        with session.lock:
            self.assertEqual(self.request("POST", "/api/clear", {})[0], 409)
            self.assertEqual(self.request("GET", "/api/session")[0], 409)
        with self.server.generation_lock:
            self.assertEqual(self.request("POST", "/api/chat", {"message": "你好"})[0], 503)
        self.assertFalse(session.lock.locked())

    def test_expired_session_requires_refresh(self):
        _, session = self.server.session(self.cookie)
        session.touched = time.monotonic() - SESSION_TTL - 1
        self.assertEqual(self.request("POST", "/api/chat", {"message": "你好"})[0], 410)
        self.assertEqual(self.request("GET", "/api/session")[0], 200)


if __name__ == "__main__":
    unittest.main()
