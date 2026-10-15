import http.server
import json
import threading
import unittest

from mcpcross import wire
from tests.helpers import FAKE_STDIO, HERE


class StdioWireTests(unittest.TestCase):
    def conn(self):
        c = wire.StdioConn([wire.PY, "-c", FAKE_STDIO], wire.pyenv(HERE), HERE)
        self.addCleanup(c.close)
        return c

    def test_request_gets_result(self):
        r = self.conn().send({"jsonrpc": "2.0", "id": 7, "method": "ping"})
        self.assertEqual(r.msg["id"], 7)
        self.assertIsNotNone(r.result)

    def test_unknown_method_is_error_with_code(self):
        r = self.conn().send({"jsonrpc": "2.0", "id": 1, "method": "zzz"})
        self.assertEqual(r.code, -32601)

    def test_notification_means_silence_detected_by_sentinel(self):
        r = self.conn().send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertIsNone(r.msg)
        self.assertFalse(r.eof)

    def test_garbage_gets_parse_error(self):
        r = self.conn().send("not json at all")
        self.assertEqual(r.code, -32700)

    def test_notifications_before_the_answer_are_collected(self):
        r = self.conn().send({"jsonrpc": "2.0", "id": 2, "method": "notify-me"})
        self.assertEqual(r.result, {"n": 1})
        self.assertEqual([n["method"] for n in r.notes], ["notifications/x"])

    def test_bytes_frames_are_sent_verbatim(self):
        r = self.conn().send(b'{"jsonrpc":"2.0","id":3,"method":"ping"}')
        self.assertEqual(r.msg["id"], 3)

    def test_dead_server_is_eof_not_a_hang(self):
        c = wire.StdioConn([wire.PY, "-c", "import sys; sys.exit(0)"], wire.pyenv(HERE), HERE)
        self.addCleanup(c.close)
        c.proc.wait(10)
        r = c.send({"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assertTrue(r.eof)


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        if self.path == "/big":
            self.send_response(413)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        out = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"echo_len": len(body), "auth": self.headers.get("Authorization"),
                                                                "sid": self.headers.get("Mcp-Session-Id")}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", "sess-1")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_DELETE(self):
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()


class HttpWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.port = cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_bearer_and_session_handling(self):
        c = wire.HttpConn(self.port, "tok")
        r1 = c.send({"jsonrpc": "2.0", "id": 1, "method": "x"})
        self.assertEqual(r1.status, 200)
        self.assertEqual(r1.result["auth"], "Bearer tok")
        self.assertIsNone(r1.result["sid"])
        self.assertEqual(c.session, "sess-1")
        r2 = c.send({"jsonrpc": "2.0", "id": 1, "method": "x"})
        self.assertEqual(r2.result["sid"], "sess-1")
        r3 = c.send({"jsonrpc": "2.0", "id": 1, "method": "x"}, session=False)
        self.assertIsNone(r3.result["sid"])
        c.close()
        self.assertIsNone(c.session)

    def test_big_body_413_is_read_even_if_server_hangs_up_early(self):
        c = wire.HttpConn(self.port, "tok")
        r = c.request("POST", "/big", b"x" * (3 << 20), {"Content-Type": "application/json"})
        self.assertEqual(r.status, 413)

    def test_connection_refused_is_wireerror(self):
        c = wire.HttpConn(1, "tok")
        with self.assertRaises(wire.WireError):
            c.send({"jsonrpc": "2.0", "id": 1, "method": "x"})

    def test_reason_for_oauth_style_and_jsonrpc_bodies(self):
        self.assertIn("invalid_token", wire.Reply(msg={"error": "invalid_token", "error_description": "bad"}).reason)
        self.assertEqual(wire.Reply(msg={"error": {"code": -1, "message": "m"}}).reason, "m")
        self.assertIsNone(wire.Reply(msg={"error": "invalid_token"}).error)
        self.assertEqual(wire.Reply(msg=None).reason, "")


if __name__ == "__main__":
    unittest.main()
