"""Raw transports. A *connection* sends one raw JSON-RPC frame and returns exactly what came back.

* ``StdioConn``: one server subprocess speaking newline-delimited JSON. Because a server may legitimately stay silent (a
  notification) we append a sentinel ``ping`` after each frame and read until its response: everything before it is the
  frame's answer, and server-initiated notifications are separated out.
* ``HttpConn``: one ``http.client`` request per call (no keep-alive state to desynchronise).
"""
import http.client
import json
import os
import queue
import signal
import subprocess
import sys
import threading

TIMEOUT = 25.0
SENTINEL_ID = "__xc_sentinel__"


class WireError(Exception):
    pass


class Reply:
    """What came back for one frame. ``msg`` is the parsed answer (dict, list for batches) or None for silence."""

    def __init__(self, msg=None, raw=None, status=None, headers=None, notes=None, eof=False):
        self.msg, self.raw, self.status = msg, raw, status
        self.headers = headers or {}
        self.notes = notes or []
        self.eof = eof

    @property
    def error(self):
        """The JSON-RPC error object, or None. (HTTP 401/403 bodies are OAuth-style {"error": "invalid_token"}; see ``reason``.)"""
        e = self.msg.get("error") if isinstance(self.msg, dict) else None
        return e if isinstance(e, dict) else None

    @property
    def reason(self):
        """Human-readable refusal text from either a JSON-RPC error or an OAuth-style HTTP error body."""
        if isinstance(self.msg, dict):
            e = self.msg.get("error")
            if isinstance(e, dict):
                return str(e.get("message", ""))
            if isinstance(e, str):
                return "%s: %s" % (e, self.msg.get("error_description", ""))
        return ""

    @property
    def code(self):
        e = self.error
        return e.get("code") if isinstance(e, dict) else None

    @property
    def result(self):
        return self.msg.get("result") if isinstance(self.msg, dict) else None

    def __repr__(self):
        return "Reply(status=%r, msg=%s)" % (self.status, json.dumps(self.msg)[:200])


class StdioConn:
    kind = "stdio"

    def __init__(self, cmd, env, cwd):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=cwd)
        self.lines = queue.Queue()
        self.stderr = []
        threading.Thread(target=self._pump_out, daemon=True).start()
        threading.Thread(target=self._pump_err, daemon=True).start()
        self.n = 0

    def _pump_out(self):
        for line in iter(self.proc.stdout.readline, b""):
            self.lines.put(line)
        self.lines.put(None)

    def _pump_err(self):
        for line in iter(self.proc.stderr.readline, b""):
            self.stderr.append(line.decode("utf-8", "replace"))

    def alive(self):
        return self.proc.poll() is None

    def write_raw(self, data):
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def send(self, frame, headers=None):
        data = frame if isinstance(frame, bytes) else (frame if isinstance(frame, str) else json.dumps(frame)).encode("utf-8")
        self.n += 1
        sid = "%s%d" % (SENTINEL_ID, self.n)
        try:
            self.write_raw(data + b"\n" + json.dumps({"jsonrpc": "2.0", "id": sid, "method": "ping"}).encode() + b"\n")
        except (BrokenPipeError, OSError):
            return Reply(eof=True)
        answers, notes = [], []
        while True:
            try:
                line = self.lines.get(timeout=TIMEOUT)
            except queue.Empty:
                raise WireError("timeout waiting for the server (stderr tail: %r)" % self.stderr[-2:])
            if line is None:
                self.lines.put(None)
                return Reply(msg=answers[0] if answers else None, notes=notes, eof=True)
            text = line.decode("utf-8", "replace").rstrip("\r\n")
            try:
                obj = json.loads(text)
            except ValueError:
                raise WireError("non-JSON line on stdout: %r" % text[:120])
            if isinstance(obj, dict) and obj.get("id") == sid:
                break
            if isinstance(obj, dict) and "method" in obj and "id" not in obj:
                notes.append(obj)
            else:
                answers.append(obj)
        if len(answers) > 1:
            raise WireError("server answered one frame with %d messages" % len(answers))
        return Reply(msg=answers[0] if answers else None, raw=text, notes=notes)

    def drain_notes(self, wait=0.3):
        """Notifications that arrive on their own (no frame sent). Used to look for list_changed pushes."""
        notes = []
        while True:
            try:
                line = self.lines.get(timeout=wait)
            except queue.Empty:
                return notes
            if line is None:
                self.lines.put(None)
                return notes
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            notes.append(obj)

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(8)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(5)
        return self.proc.returncode

    def kill(self):
        self.proc.send_signal(signal.SIGKILL)
        self.proc.wait(5)


class HttpConn:
    kind = "http"

    def __init__(self, port, token=None, host="127.0.0.1"):
        self.host, self.port, self.token = host, port, token
        self.session = None

    def request(self, method, path, body=None, headers=None, bearer=True):
        h = {}
        if self.token and bearer:
            h["Authorization"] = "Bearer " + self.token
        h.update(headers or {})
        c = http.client.HTTPConnection(self.host, self.port, timeout=TIMEOUT)
        try:
            try:
                c.request(method, path, body=body, headers=h)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the server may answer (e.g. 413) and close before we finish sending a huge body; read its answer
            r = c.getresponse()
            data = r.read()
            hdrs = {k.lower(): v for k, v in r.getheaders()}
            status = r.status
        except (OSError, http.client.HTTPException) as exc:
            raise WireError("http error: %r" % exc)
        finally:
            c.close()
        text = data.decode("utf-8", "replace")
        msg = None
        if text.strip():
            try:
                msg = json.loads(text)
            except ValueError:
                msg = None
        return Reply(msg=msg, raw=text, status=status, headers=hdrs)

    def send(self, frame, headers=None, session=True):
        body = frame if isinstance(frame, (bytes, str)) else json.dumps(frame)
        if isinstance(body, str):
            body = body.encode("utf-8")
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if session and self.session:
            h["Mcp-Session-Id"] = self.session
        h.update(headers or {})
        h = {k: v for k, v in h.items() if v is not None}
        rep = self.request("POST", "/mcp", body, h)
        if "mcp-session-id" in rep.headers and self.session is None:
            self.session = rep.headers["mcp-session-id"]
        return rep

    def close(self):
        if self.session:
            try:
                self.request("DELETE", "/mcp", None, {"Mcp-Session-Id": self.session})
            except WireError:
                pass
            self.session = None
        return 0


def pyenv(pythonpath, extra=None):
    env = dict(os.environ, PYTHONPATH=pythonpath, PYTHONUNBUFFERED="1")
    for k in ("MCP_TOKEN", "MCP_FORGE_SECRET", "MCP_FORGE_HOME", "MCP_FORGE_ISSUER", "MCP_FORGE_AUDIENCE", "MCP_FORGE_CRASH_POINT", "MCP_FORGE_ALLOW_KIDLESS"):
        env.pop(k, None)
    env.update(extra or {})
    return env


PY = sys.executable
