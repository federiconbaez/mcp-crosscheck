"""A minimal JSON-RPC/MCP client on top of a wire connection (written for this project; shares no code with the servers)."""
from . import wire


class Client:
    def __init__(self, conn):
        self.conn = conn
        self.n = 0
        self.init_result = None

    def frame(self, method, params=None, mid=None):
        self.n += 1
        m = {"jsonrpc": "2.0", "id": self.n if mid is None else mid, "method": method}
        if params is not None:
            m["params"] = params
        return m

    def request(self, method, params=None, mid=None, headers=None):
        return self.conn.send(self.frame(method, params, mid), headers=headers)

    def notify(self, method, params=None):
        m = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            m["params"] = params
        return self.conn.send(m)

    def initialize(self, version="2025-03-26", capabilities=None):
        rep = self.request("initialize", {"protocolVersion": version, "capabilities": capabilities or {},
                                          "clientInfo": {"name": "mcp-crosscheck", "version": "1"}})
        if rep.result is not None:
            self.init_result = rep.result
            self.notify("notifications/initialized")
        return rep

    def tool(self, name, arguments=None):
        return self.request("tools/call", {"name": name, "arguments": arguments or {}})

    def tool_json(self, name, arguments=None):
        """Call a tool and decode its JSON text payload; raises AssertionError-friendly errors via Fail in the battery."""
        import json
        rep = self.tool(name, arguments)
        if rep.result is None:
            raise wire.WireError("tool %s failed: %r" % (name, rep.msg))
        if rep.result.get("isError"):
            raise wire.WireError("tool %s returned isError: %s" % (name, rep.result["content"][0].get("text", "")[:200]))
        return json.loads(rep.result["content"][0]["text"])

    def close(self):
        return self.conn.close()
