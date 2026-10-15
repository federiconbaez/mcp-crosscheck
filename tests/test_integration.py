"""End-to-end against the real family (skipped if the sibling projects are not next to this repo)."""
import os
import shutil
import tempfile
import unittest

from mcpcross import crosstoken, differential, runner, targets
from tests.helpers import FAMILY, siblings_present

NEEDS = unittest.skipUnless(siblings_present(), "sibling family directories not present")


@NEEDS
class FullFamily(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.targets = targets.select(None, FAMILY)

    def test_battery_has_no_failures_on_any_target_or_transport(self):
        res = runner.run_battery(self.targets, FAMILY, ("stdio", "http"))
        self.assertEqual(set(res), {"base", "memory", "auth", "resources"})
        bad = [(t, cid, tr, r["detail"]) for t, cs in res.items() for cid, d in cs.items() for tr, r in d.items() if r["status"] in ("fail", "error")]
        self.assertEqual(bad, [])
        passed = sum(1 for cs in res.values() for d in cs.values() for r in d.values() if r["status"] == "pass")
        self.assertGreater(passed, 4 * 50)

    def test_differential_all_servers_agree_and_capabilities_match_behaviour(self):
        diff = differential.run_differential(self.targets, FAMILY, ("stdio", "http"))
        dis = [(c["case"], tr, d["outcomes"]) for c in diff["cases"] for tr, d in c["by_transport"].items() if not d["agree"]]
        self.assertEqual(dis, [])
        self.assertEqual([c["case"] for c in diff["cases"] if c.get("transport_parity") is False], [])
        self.assertEqual([(n, k) for n, t in diff["capabilities"].items() for k, r in t["rows"].items() if not r["consistent"]], [])

    def test_differential_is_not_vacuous_it_sees_many_distinct_outcomes(self):
        diff = differential.run_differential(self.targets[:2], FAMILY, ("stdio",))
        kinds = {next(iter(d["outcomes"].values())) for c in diff["cases"] for d in c["by_transport"].values()}
        self.assertTrue({"result", "silence", "err-32700(id:null)", "err-32600", "err-32601", "err-32602"} <= kinds, kinds)

    def test_cross_token_matrix(self):
        cross = crosstoken.run_crosstoken(self.targets, FAMILY, ("stdio", "http"))
        for layer in cross["layers"]:
            for tr, v in layer["transports"].items():
                for s, row in v["matrix"].items():
                    for d, cell in row.items():
                        self.assertTrue(cell["ok"], (layer["layer"], tr, s, d, cell))
        want = {"L1": "signature", "L2b": "audience"}   # each layer isolates ONE reason for refusal
        for layer in cross["layers"]:
            if layer["layer"] in want:
                for tr, v in layer["transports"].items():
                    for s, row in v["matrix"].items():
                        for d, cell in row.items():
                            if s != d:
                                self.assertIn(want[layer["layer"]], cell["reason"].lower(), (layer["layer"], tr, s, d, cell))
        l3 = [l for l in cross["layers"] if l["layer"] == "L3"][0]
        accepted = sum(1 for v in l3["transports"].values() for row in v["matrix"].values() for c in row.values() if c["outcome"] == "accept")
        self.assertEqual(accepted, 16 * 2)
        l1 = [l for l in cross["layers"] if l["layer"] == "L1"][0]
        rejected = sum(1 for v in l1["transports"].values() for row in v["matrix"].values() for c in row.values() if c["outcome"] == "reject")
        self.assertEqual(rejected, 12 * 2)


@NEEDS
class BrokenServersAreDetected(unittest.TestCase):
    """Inject one bug into a COPY of two family members and make sure crosscheck notices (cheap version of tools/mutation_sanity.py)."""

    def family_copy(self, *dirs):
        tmp = tempfile.mkdtemp(prefix="xc-test-fam-")
        self.addCleanup(shutil.rmtree, tmp, True)
        for d in dirs:
            shutil.copytree(os.path.join(FAMILY, d), os.path.join(tmp, d), ignore=shutil.ignore_patterns(".git", "__pycache__", "evidence", "tests", ".mcp*"))
        return tmp

    def mutate(self, tmp, rel, old, new):
        path = os.path.join(tmp, rel)
        with open(path) as f:
            src = f.read()
        self.assertEqual(src.count(old), 1)
        with open(path, "w") as f:
            f.write(src.replace(old, new))

    def test_wrong_method_not_found_code_is_caught_by_battery_and_differential(self):
        tmp = self.family_copy("mcp-base", "mcp-memory-first")
        self.mutate(tmp, "mcp-base/mcpforge/jsonrpc.py", "METHOD_NOT_FOUND = -32601", "METHOD_NOT_FOUND = -32602")
        ts = targets.select(["base", "memory"], tmp)
        res = runner.run_battery(ts, tmp, ("stdio",))
        self.assertTrue(any(r["status"] == "fail" for d in res["base"].values() for r in d.values()))
        diff = differential.run_differential(ts, tmp, ("stdio",))
        self.assertTrue(any(not d["agree"] for c in diff["cases"] for d in c["by_transport"].values()))

    def test_unchecked_signature_is_caught_by_cross_token_l1(self):
        tmp = self.family_copy("mcp-base", "mcp-memory-first")
        self.mutate(tmp, "mcp-base/mcpforge/auth.py", "        if not hmac.compare_digest(expected, signature):\n            raise AuthError(\"invalid_token\", \"signature verification failed\")",
                    "        if False:\n            raise AuthError(\"invalid_token\", \"signature verification failed\")")
        ts = targets.select(["base", "memory"], tmp)
        cross = crosstoken.run_layer("L1", ts, tmp, ("stdio",))
        self.assertFalse(cross["ok"])
        cell = cross["transports"]["stdio"]["matrix"]["memory"]["base"]
        self.assertEqual(cell["outcome"], "accept")
        self.assertFalse(cell["ok"])


if __name__ == "__main__":
    unittest.main()
