"""The family members under test, described only by how to run them (no imports of their code)."""
import os

UNION_SCOPES = ("mcp tools:read tools:write resources:read prompts:read memory:read memory:write memory:admin "
                "audit:read auth:admin data:read data:write")
READ_ONLY_BASE = "mcp"
ISSUER = "https://crosscheck.test"


class Target:
    def __init__(self, name, directory, module, audience, kidless_flag=False, notes=""):
        self.name, self.directory, self.module, self.audience = name, directory, module, audience
        self.kidless_flag = kidless_flag   # True: `serve --allow-kidless` exists (mcp-auth-hardened)
        self.notes = notes

    def root(self, family_dir):
        return os.path.join(family_dir, self.directory)

    def available(self, family_dir):
        r = self.root(family_dir)
        return os.path.isfile(os.path.join(r, self.module, "__main__.py"))

    def __repr__(self):
        return "Target(%s)" % self.name


TARGETS = [
    Target("base", "mcp-base", "mcpforge", "mcp-forge", notes="clean repackaging of mcp-forge"),
    Target("memory", "mcp-memory-first", "mcpmem", "mcp-memory-first", notes="journal, snapshots, versions"),
    Target("auth", "mcp-auth-hardened", "mcpauth", "mcp-auth-hardened", kidless_flag=True, notes="scopes, rotation, kid, RS256"),
    Target("resources", "mcp-resource-heavy", "mcpres", "mcp-resource-heavy", notes="resources, subscriptions, SSE"),
]
BY_NAME = {t.name: t for t in TARGETS}


def select(names, family_dir):
    chosen = []
    for n in names or [t.name for t in TARGETS]:
        if n not in BY_NAME:
            raise ValueError("unknown target %r (choose from %s)" % (n, ", ".join(BY_NAME)))
        chosen.append(BY_NAME[n])
    missing = [t.name for t in chosen if not t.available(family_dir)]
    if missing:
        raise FileNotFoundError("family directory %s lacks: %s (expected sibling dirs like mcp-base/)" % (family_dir, ", ".join(missing)))
    return chosen
