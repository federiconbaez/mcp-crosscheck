import json
import unittest

from mcpcross import crosstoken, differential, report, wire


def R(msg=None, status=None, eof=False):
    return wire.Reply(msg=msg, status=status, eof=eof)


def err(code, mid=1):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": "m"}}


class OutcomeTests(unittest.TestCase):
    def test_error_result_silence(self):
        self.assertEqual(differential.outcome(R(err(-32601)), "stdio"), "err-32601")
        self.assertEqual(differential.outcome(R({"jsonrpc": "2.0", "id": 1, "result": {}}), "stdio"), "result")
        self.assertEqual(differential.outcome(R(None), "stdio"), "silence")
        self.assertEqual(differential.outcome(R(None, eof=True), "stdio"), "eof")

    def test_null_id_is_distinguished(self):
        self.assertEqual(differential.outcome(R(err(-32600, None)), "stdio"), "err-32600(id:null)")

    def test_http_includes_status_and_code_only_strips_it(self):
        o = differential.outcome(R(err(-32602), status=200), "http")
        self.assertEqual(o, "200|err-32602")
        self.assertEqual(differential.code_only(o), "err-32602")
        self.assertEqual(differential.code_only("err-32602"), "err-32602")

    def test_batch_outcomes_are_sorted_and_comparable(self):
        a = differential.outcome(R([err(-32600), {"id": 2, "result": {}}]), "stdio")
        b = differential.outcome(R([{"id": 2, "result": {}}, err(-32600)]), "stdio")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("array["))

    def test_different_codes_give_different_outcomes(self):
        self.assertNotEqual(differential.outcome(R(err(-32601)), "stdio"), differential.outcome(R(err(-32602)), "stdio"))


class CrossTokenLogic(unittest.TestCase):
    def test_expectations_per_layer(self):
        for layer in ("L1", "L2", "L2b"):
            self.assertTrue(crosstoken.expected_accept(layer, "a", "a"))
            self.assertFalse(crosstoken.expected_accept(layer, "a", "b"))
        self.assertTrue(crosstoken.expected_accept("L3", "a", "b"))

    def test_layers_listed_in_order(self):
        self.assertEqual([l[0] for l in crosstoken.LAYERS], ["L1", "L2", "L2b", "L3"])

    def test_configs_differ_per_layer(self):
        from mcpcross import targets
        tl = targets.TARGETS
        l1 = crosstoken._configs("L1", tl)
        self.assertEqual(len({c["secret"] for c in l1.values()}), len(tl))
        self.assertEqual(len({c["audience"] for c in l1.values()}), 1)   # only the signature may differ
        self.assertTrue(all(c["kidless"] for c in l1.values()))
        l2 = crosstoken._configs("L2", tl)
        self.assertEqual(len({c["secret"] for c in l2.values()}), 1)
        self.assertEqual(len({c["audience"] for c in l2.values()}), len(tl))
        self.assertFalse(any(c["kidless"] for c in l2.values()))
        l3 = crosstoken._configs("L3", tl)
        self.assertEqual(len({c["audience"] for c in l3.values()}), 1)
        self.assertTrue(all(c["kidless"] for c in l3.values()))
        self.assertTrue(all(c["kidless"] for c in crosstoken._configs("L2b", tl).values()))


def fake_cross(ok=True):
    cell = lambda out, exp, good: {"outcome": out, "expected": exp, "ok": good, "usable": out == "accept", "code": -32001, "http": 401, "reason": "wrong audience"}
    m = {"a": {"a": cell("accept", "accept", True), "b": cell("reject", "reject", ok)},
         "b": {"a": cell("reject", "reject", True), "b": cell("accept", "accept", True)}}
    layer = {"layer": "L2", "title": "t", "expect": "e", "ok": ok, "transports": {"stdio": {"matrix": m, "ok": ok}}}
    return {"layers": [layer], "ok": ok, "targets": ["a", "b"], "transports": ["stdio"]}


class ReportTests(unittest.TestCase):
    def test_summarize_battery_counts(self):
        res = {"t": {"XC-A-01": {"stdio": {"status": "pass"}, "http": {"status": "fail"}}, "XC-A-02": {"stdio": {"status": "skip"}}}}
        s = report.summarize_battery(res)
        self.assertEqual(s["t"]["stdio"], {"pass": 1, "fail": 0, "skip": 1, "error": 0})
        self.assertEqual(s["t"]["http"]["fail"], 1)

    def test_differential_summary_flags_everything(self):
        diff = {"cases": [{"case": "c1", "by_transport": {"stdio": {"agree": False, "outcomes": {}}}, "transport_parity": False},
                          {"case": "c2", "by_transport": {"stdio": {"agree": True, "outcomes": {}}}}],
                "capabilities": {"t": {"rows": {"tools": {"consistent": False}}}}}
        s = report.differential_summary(diff)
        self.assertFalse(s["ok"])
        self.assertEqual(s["disagreements"], [("c1", "stdio")])
        self.assertEqual(s["transport_parity_failures"], ["c1"])
        self.assertEqual(s["capability_inconsistencies"], [("t", "tools")])

    def test_markdown_and_json_for_cross_token(self):
        from mcpcross import targets
        rep = report.build("/nonexistent", [targets.TARGETS[0], targets.TARGETS[1]], ("stdio",), cross=fake_cross(True))
        self.assertTrue(rep["ok"])
        md = report.to_markdown(rep)
        self.assertIn("overall verdict: PASS", md)
        self.assertIn("minted by", md)
        self.assertIn("rejected (rpc -32001: wrong audience)", md.replace("HTTP 401", "rpc -32001"))
        self.assertEqual(json.loads(report.to_json(rep))["crosstoken"]["layers"][0]["layer"], "L2")

    def test_failure_makes_overall_fail_and_is_visible(self):
        from mcpcross import targets
        rep = report.build("/nonexistent", [targets.TARGETS[0], targets.TARGETS[1]], ("stdio",), cross=fake_cross(False))
        self.assertFalse(rep["ok"])
        self.assertIn("overall verdict: FAIL", report.to_markdown(rep))
        self.assertIn("✘", report.to_markdown(rep))

    def test_battery_failure_lists_detail(self):
        from mcpcross import targets
        res = {"base": {"XC-RPC-01": {"stdio": {"status": "fail", "detail": "boom-detail", "ms": 1}}}}
        rep = report.build("/nonexistent", [targets.TARGETS[0]], ("stdio",), results=res)
        self.assertFalse(rep["ok"])
        self.assertIn("boom-detail", report.to_markdown(rep))

    def test_all_pass_and_skip_is_ok(self):
        from mcpcross import targets
        res = {"base": {"XC-RPC-01": {"stdio": {"status": "pass", "detail": "", "ms": 1}}, "XC-RPC-02": {"stdio": {"status": "skip", "detail": "n/a", "ms": 1}}}}
        self.assertTrue(report.build("/nonexistent", [targets.TARGETS[0]], ("stdio",), results=res)["ok"])


if __name__ == "__main__":
    unittest.main()
