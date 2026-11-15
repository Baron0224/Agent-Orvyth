import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from chat_web import ChatServer, Handler
from desktop_pairing import DesktopPairing


class DesktopPairingTest(unittest.TestCase):
    def test_owner_and_origin_one_use_restart_and_live_revoke(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = ChatServer(0, db_path=root / 'browser.sqlite3')
            daily_cookie, owner = server.store.owner(create=True)
            other_cookie, _ = server.store.owner(create=True)
            pairing_path = root / 'desktop-pairing.sqlite3'
            server.desktop = DesktopPairing(pairing_path, owner)
            chat = server.state(owner)['active_chat']
            ready, release = threading.Event(), threading.Event()

            def slow(handler, *_):
                handler.headers_for(200, 'application/x-ndjson; charset=utf-8')
                handler.end_headers()
                handler.wfile.write(b'{"type":"delta"}\n')
                handler.wfile.flush()
                ready.set()
                release.wait(5)

            def call(path, body=None, cookie=None, key=None, origin=None):
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                headers = {'Origin': server.origin if origin is None else origin}
                if cookie:
                    headers['Cookie'] = 'orvyth_session=' + cookie
                if key:
                    headers['X-Orvyth-Desktop'] = key
                if body is not None:
                    headers['Content-Type'] = 'application/json'
                conn.request('GET' if body is None else 'POST', '/api/' + path,
                             None if body is None else json.dumps(body), headers)
                return conn, conn.getresponse()

            def check(path, body=None, status=200, **kwargs):
                conn, response = call(path, body, **kwargs)
                try:
                    result = json.loads(response.read())
                    self.assertEqual(response.status, status, result)
                    return result
                finally:
                    conn.close()

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                pending = check('desktop/start', {})
                code = {'code': pending['code']}
                self.assertEqual(check('desktop/claim', pending), {'waiting': True})
                check('desktop/approve', code, cookie=other_cookie, status=403)
                check('desktop/approve', code, cookie=daily_cookie, origin='http://example.test', status=403)
                check('desktop/approve', code, cookie=daily_cookie)
                check('desktop/approve', code, cookie=daily_cookie, status=400)
                check('desktop/claim', {**pending, 'proof': 'x' * 43}, status=400)
                key = check('desktop/claim', pending)['token']
                check('desktop/claim', pending, status=400)
                check('desktop/session', key='x' * 43, status=401)
                check('clear', {'chat_id': chat}, key=key, status=403)
                server.desktop = DesktopPairing(pairing_path, owner)
                self.assertEqual(check('desktop/session', key=key), {'active_chat': chat})
                message = {'message': 'isolated stream', 'chat_id': chat}
                with patch.object(Handler, 'stream_reply', slow):
                    conn, response = call('chat', message, key=key)
                    try:
                        self.assertEqual(response.readline(), b'{"type":"delta"}\n')
                        self.assertTrue(ready.wait(1))
                        device = check('desktop/list', {}, cookie=daily_cookie)['devices'][0]
                        self.assertEqual(check('desktop/revoke', {'id': device['id']}, cookie=daily_cookie), {'devices': []})
                        self.assertEqual(response.read(), b'')
                        self.assertFalse(release.is_set())
                    finally:
                        conn.close()
                check('desktop/session', key=key, status=401)
                check('chat', message, key=key, status=401)
                pending = check('desktop/start', {})
                with patch('desktop_pairing.time.monotonic', return_value=10**12):
                    check('desktop/approve', {'code': pending['code']}, cookie=daily_cookie, status=400)
            finally:
                release.set()
                server.shutdown()
                server.server_close()
                thread.join()
