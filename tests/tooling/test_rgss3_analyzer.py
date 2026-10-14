import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import rgss3_analyzer as analyzer


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.fixture_dir = os.path.join(ROOT, "tools", "fixtures")
        paths = analyzer.discover_scripts(self.fixture_dir)
        self.scripts = [analyzer.analyze_script(p, i, root=self.fixture_dir) for i, p in enumerate(paths)]
        self.report = analyzer.build_report(self.scripts)

    def test_discovers_expected_scripts(self):
        self.assertEqual([s["name"] for s in self.scripts], [
            "001_Core.rb", "002_Addon.rb", "003_Conflict.rb", "004_LateDependency.rb"
        ])

    def test_method_collision_detected(self):
        collisions = {x["method"]: x for x in self.report["method_collisions"]}
        self.assertIn("Game_Battler#item_apply", collisions)
        self.assertEqual(collisions["Game_Battler#item_apply"]["severity"], "high")
        self.assertEqual(len(collisions["Game_Battler#item_apply"]["occurrences"]), 3)

    def test_alias_detected(self):
        addon = [s for s in self.scripts if s["name"] == "002_Addon.rb"][0]
        aliases = {(a["new"], a["old"]) for a in addon["aliases"]}
        self.assertIn(("addon_item_apply", "item_apply"), aliases)

    def test_import_dependency_order(self):
        findings = [x for x in self.report["dependency_findings"] if x["key"] == "FutureCore"]
        self.assertTrue(any(x["status"] == "defined_later" for x in findings))

    def test_save_hook_detected(self):
        hooks = [x for x in self.report["save_hook_scripts"] if x["script"] == "001_Core.rb"]
        self.assertTrue(hooks)
        self.assertTrue(any(h["method"] == "make_save_contents" for h in hooks[0]["hooks"]))

    def test_note_parser_detected(self):
        matches = [x for x in self.report["note_parser_scripts"] if x["script"] == "003_Conflict.rb"]
        self.assertTrue(matches)

    def test_markdown_report(self):
        text = analyzer.markdown_report(self.report)
        self.assertIn("RGSS3 Compatibility Analysis", text)
        self.assertIn("Game_Battler#item_apply", text)

    def test_singleton_save_hook_is_classified(self):
        core = [s for s in self.scripts if s["name"] == "001_Core.rb"][0]
        matches = [m for m in core["methods"] if m["scope"] == "DataManager" and m["name"] == "make_save_contents"]
        self.assertTrue(matches)
        self.assertTrue(matches[0]["singleton"])

    def test_fail_on_high_exit_code(self):
        rc = analyzer.main([self.fixture_dir, "--fail-on-high"])
        self.assertEqual(rc, 2)

    def test_order_manifest_changes_dependency_status(self):
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, "Addon.rb")
            c = os.path.join(td, "Core.rb")
            with open(a, "w", encoding="utf-8") as fh:
                fh.write('if $imported["Core"]\nend\n')
            with open(c, "w", encoding="utf-8") as fh:
                fh.write('$imported["Core"] = true\n')
            order = os.path.join(td, "order.json")
            with open(order, "w", encoding="utf-8") as fh:
                json.dump(["Core.rb", "Addon.rb"], fh)
            paths = analyzer.discover_scripts(td, order)
            scripts = [analyzer.analyze_script(path, i, root=td) for i, path in enumerate(paths)]
            report = analyzer.build_report(scripts)
            core_findings = [x for x in report["dependency_findings"] if x["key"] == "Core"]
            self.assertTrue(core_findings)
            self.assertTrue(all(x["status"] == "satisfied_before_use" for x in core_findings))

    def test_constant_collision(self):
        with tempfile.TemporaryDirectory() as td:
            for idx, value in [(1, 3), (2, 5)]:
                with open(os.path.join(td, "%03d.rb" % idx), "w", encoding="utf-8") as fh:
                    fh.write('module BattleManager\n  MAX_ACTIONS = %d\nend\n' % value)
            paths = analyzer.discover_scripts(td)
            scripts = [analyzer.analyze_script(path, i, root=td) for i, path in enumerate(paths)]
            report = analyzer.build_report(scripts)
            self.assertTrue(any(x["constant"].endswith("MAX_ACTIONS") for x in report["constant_collisions"]))

    def test_cli_outputs_files(self):
        with tempfile.TemporaryDirectory() as td:
            j = os.path.join(td, "report.json")
            m = os.path.join(td, "report.md")
            rc = analyzer.main([self.fixture_dir, "--json", j, "--markdown", m])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(j))
            self.assertTrue(os.path.exists(m))
            with open(j, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertGreaterEqual(data["summary"]["method_collision_candidates"], 1)


if __name__ == "__main__":
    unittest.main()
