import contextlib
import io
import json
import os
import tempfile
import unittest

from mcpcross import cli
from tests.helpers import FAMILY, siblings_present


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = cli.main(argv)
        except SystemExit as exc:
            rc = exc.code
    return rc, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def test_list_text_and_json(self):
        rc, out, _ = run(["list"])
        self.assertEqual(rc, 0)
        self.assertIn("XC-LIF-01", out)
        rc, out, _ = run(["list", "--json"])
        rows = json.loads(out)
        self.assertGreaterEqual(len(rows), 50)
        self.assertTrue(all({"id", "title", "spec", "transports"} <= set(r) for r in rows))

    def test_missing_family_dir_exit_2(self):
        rc, _, err = run(["run", "--family-dir", "/nonexistent-dir", "--no-write"])
        self.assertEqual(rc, 2)
        self.assertIn("lacks", err)

    def test_unknown_target_exit_2(self):
        rc, _, err = run(["run", "--targets", "bogus", "--no-write"])
        self.assertEqual(rc, 2)

    def test_bad_transport_exit_2(self):
        rc, _, err = run(["run", "--transports", "carrier-pigeon", "--no-write"])
        self.assertEqual(rc, 2)

    @unittest.skipUnless(siblings_present(), "sibling family directories not present")
    def test_quick_run_writes_reports(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, _ = run(["run", "--family-dir", FAMILY, "--targets", "base", "--transports", "stdio", "--only", "XC-LIF-01,XC-RPC-01",
                              "--skip", "differential,crosstoken", "--out", d])
            self.assertEqual(rc, 0, out)
            self.assertIn("CROSSCHECK PASS", out)
            self.assertTrue(os.path.exists(os.path.join(d, "crosscheck.json")))
            self.assertTrue(os.path.exists(os.path.join(d, "crosscheck.md")))
            with open(os.path.join(d, "crosscheck.json")) as f:
                rep = json.load(f)
            self.assertEqual(rep["battery"]["summary"]["base"]["stdio"]["pass"], 2)


if __name__ == "__main__":
    unittest.main()
