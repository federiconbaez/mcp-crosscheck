"""Start/stop one family member in a configurable way and mint tokens with *its own* CLI."""
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time

from . import targets, wire


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Deployment:
    """One target configured with a secret, audience and issuer. Owns a data dir and (lazily) an HTTP server process."""

    def __init__(self, target, family_dir, secret=None, audience=None, issuer=targets.ISSUER, kidless=False, tmp_root=None, label=""):
        self.target, self.family_dir = target, family_dir
        self.secret = secret or secrets.token_hex(24)
        self.audience = audience or target.audience
        self.issuer = issuer
        self.kidless = kidless and target.kidless_flag
        self.tmp = tempfile.mkdtemp(prefix="xc-%s-%s-" % (target.name, label), dir=tmp_root)
        self.data_dir = os.path.join(self.tmp, "data")
        self.root = target.root(family_dir)
        self.http_proc = None
        self.http_port = None
        self.stdio_conns = []
        self._tokens = {}

    # -- command lines ---------------------------------------------------------------------------------
    def env(self, **extra):
        e = {"MCP_FORGE_SECRET": self.secret, "MCP_FORGE_HOME": self.data_dir}
        e.update(extra)
        return wire.pyenv(self.root, e)

    def serve_cmd(self, transport, port=None, extra=()):
        cmd = [wire.PY, "-m", self.target.module, "serve", "--data-dir", self.data_dir, "--issuer", self.issuer, "--audience", self.audience]
        if self.kidless:
            cmd.append("--allow-kidless")
        if transport == "http":
            cmd += ["--transport", "http", "--port", str(port)]
        return cmd + list(extra)

    # -- tokens ----------------------------------------------------------------------------------------
    def mint(self, scope=None, ttl=None, aud=None, issuer=None, sub="crosscheck", cache=True):
        key = (scope, ttl, aud, issuer, sub)
        if cache and key in self._tokens:
            return self._tokens[key]
        cmd = [wire.PY, "-m", self.target.module, "mint-token", "--data-dir", self.data_dir, "--issuer", issuer or self.issuer,
               "--audience", self.audience, "--sub", sub]
        if scope is not None:
            cmd += ["--scope", scope]
        if ttl is not None:
            cmd.append("--ttl=%d" % ttl)
        if aud is not None:
            cmd += ["--aud", aud]
        r = subprocess.run(cmd, capture_output=True, text=True, env=self.env(), cwd=self.root, timeout=60)
        if r.returncode != 0 or not r.stdout.strip():
            raise RuntimeError("mint-token failed for %s: %s" % (self.target.name, r.stderr.strip()[:300]))
        tok = r.stdout.strip()
        if cache:
            self._tokens[key] = tok
        return tok

    # -- connections -----------------------------------------------------------------------------------
    def stdio(self, token=None, extra_env=None, extra_args=()):
        env = self.env(**({"MCP_TOKEN": token} if token else {}), **(extra_env or {}))
        conn = wire.StdioConn(self.serve_cmd("stdio", extra=extra_args), env, self.root)
        self.stdio_conns.append(conn)
        return conn

    def start_http(self, extra=()):
        if self.http_proc and self.http_proc.poll() is None:
            return self.http_port
        self.http_port = free_port()
        self.http_proc = subprocess.Popen(self.serve_cmd("http", self.http_port, extra), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                          env=self.env(), cwd=self.root, text=True)
        deadline = time.time() + 20
        while time.time() < deadline:
            if self.http_proc.poll() is not None:
                raise RuntimeError("%s http server exited early: %s" % (self.target.name, self.http_proc.stderr.read()[-300:]))
            try:
                socket.create_connection(("127.0.0.1", self.http_port), timeout=0.3).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("%s http server did not open its port" % self.target.name)
        return self.http_port

    def stop_http(self):
        p, self.http_proc = self.http_proc, None
        if p:
            p.terminate()
            try:
                p.wait(8)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(5)
            if p.stderr:
                p.stderr.close()

    def http(self, token=None):
        return wire.HttpConn(self.start_http(), token)

    def conn(self, transport, token=None):
        return self.stdio(token) if transport == "stdio" else self.http(token)

    def close(self):
        for c in self.stdio_conns:
            try:
                if c.alive():
                    c.close()
            except Exception:  # noqa: BLE001
                pass
        self.stop_http()
        shutil.rmtree(self.tmp, ignore_errors=True)
