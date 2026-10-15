import re
import unittest

from mcpcross import battery, differential, targets


class RegistryTests(unittest.TestCase):
    def test_check_ids_unique_and_well_formed(self):
        ids = [c["id"] for c in battery.CHECKS]
        self.assertEqual(len(ids), len(set(ids)))
        for i in ids:
            self.assertRegex(i, r"^XC-[A-Z]{3}-\d{2}$")

    def test_every_check_documents_title_and_spec_and_transports(self):
        for c in battery.CHECKS:
            self.assertTrue(c["title"].strip(), c["id"])
            self.assertTrue(c["spec"].strip(), c["id"])
            self.assertTrue(set(c["transports"]) <= {"stdio", "http"} and c["transports"], c["id"])
            self.assertTrue(callable(c["fn"]))

    def test_battery_size_floor(self):
        self.assertGreaterEqual(len(battery.CHECKS), 50)

    def test_every_group_present(self):
        groups = {c["id"].split("-")[1] for c in battery.CHECKS}
        self.assertTrue({"LIF", "RPC", "TLS", "RES", "PRM", "CAP", "AUT", "HTP", "STD", "PER", "CON"} <= groups)

    def test_http_only_and_stdio_only_checks_exist(self):
        self.assertTrue(any(c["transports"] == ("http",) for c in battery.CHECKS))
        self.assertTrue(any(c["transports"] == ("stdio",) for c in battery.CHECKS))

    def test_differential_case_names_unique_and_states_known(self):
        names = [c[0] for c in differential.CASES]
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(names), 60)
        for _, _, state in differential.CASES:
            self.assertIn(state, ("pre", "post", "post0618", "post1105"))

    def test_targets_cover_the_four_servers(self):
        self.assertEqual([t.name for t in targets.TARGETS], ["base", "memory", "auth", "resources"])
        self.assertEqual([t.name for t in targets.TARGETS if t.kidless_flag], ["auth"])
        with self.assertRaises(ValueError):
            targets.select(["nope"], "/nonexistent")

    def test_select_reports_missing_siblings(self):
        with self.assertRaises(FileNotFoundError):
            targets.select(["base"], "/nonexistent-family-dir")

    def test_no_check_imports_family_code(self):
        src = ""
        for mod in (battery, differential):
            with open(mod.__file__) as f:
                src += f.read()
        self.assertIsNone(re.search(r"^\s*(from|import)\s+(mcpforge|mcpmem|mcpauth|mcpres)\b", src, re.M))


if __name__ == "__main__":
    unittest.main()
