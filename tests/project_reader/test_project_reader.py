import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READER = ROOT / "tools" / "vxace_project_reader.py"
FIXTURE = Path(__file__).with_name("make_fixture.rb")


class ProjectReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ruby = shutil.which("ruby")
        if not cls.ruby:
            raise unittest.SkipTest("Ruby is required for the v0.5 fixture/bridge tests")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.project = self.base / "SyntheticVXACE"
        subprocess.run([self.ruby, str(FIXTURE), str(self.project)], check=True)
        self.output = self.base / "index"

    def tearDown(self):
        self.tmp.cleanup()

    def run_reader(self):
        return subprocess.run(
            [sys.executable, str(READER), str(self.project), "--output", str(self.output), "--ruby", self.ruby],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

    def load(self, rel):
        with (self.output / rel).open("r", encoding="utf-8") as f:
            return json.load(f)

    def test_end_to_end_reader(self):
        proc = self.run_reader()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = self.load("project.json")
        self.assertEqual(summary["map_count"], 1)
        self.assertEqual(summary["script_count"], 3)
        self.assertEqual(summary["compatibility_analysis"]["status"], "ok")
        self.assertEqual(summary["errors"], [])

    def test_database_objects_and_table_are_normalized(self):
        proc = self.run_reader()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        actors = self.load("database/actors.json")
        self.assertEqual(actors[1]["__class__"], "RPG::Actor")
        self.assertEqual(actors[1]["name"], "Alicia")
        classes = self.load("database/classes.json")
        table = classes[1]["params"]
        self.assertEqual(table["__class__"], "Table")
        self.assertEqual(table["xsize"], 8)
        self.assertEqual(table["ysize"], 3)
        self.assertEqual(table["data"][:3], [1, 2, 3])

    def test_script_order_and_sources_are_preserved(self):
        proc = self.run_reader()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        order = self.load("scripts/order.json")["scripts"]
        self.assertEqual([x["name"] for x in order], ["Core Battle", "Alias Extension", "Destructive Extension"])
        self.assertTrue((self.output / "scripts" / order[0]["path"]).is_file())
        self.assertIn("def item_apply", (self.output / "scripts" / order[0]["path"]).read_text(encoding="utf-8"))

    def test_switch_variable_and_event_links(self):
        proc = self.run_reader()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        switches = {x["id"]: x for x in self.load("analysis/switches.json")}
        variables = {x["id"]: x for x in self.load("analysis/variables.json")}
        self.assertEqual(switches[1]["name"], "QuestStarted")
        self.assertTrue(switches[1]["reads"])
        self.assertTrue(switches[1]["writes"])
        self.assertEqual(variables[1]["name"], "QuestStage")
        self.assertTrue(variables[1]["writes"])
        callers = self.load("analysis/common-event-callers.json")
        self.assertEqual(callers[0]["common_event_id"], 1)
        self.assertEqual(callers[0]["name"], "Advance Quest")
        transfers = self.load("analysis/map-transfers.json")
        self.assertEqual(transfers[0]["map_id"], 2)
        self.assertEqual(transfers[0]["map_name"], "Destination")
        battles = self.load("analysis/battle-troop-links.json")
        self.assertEqual(battles[0]["troop_id"], 3)
        self.assertEqual(battles[0]["troop_name"], "Test Slimes")
        self.assertEqual(self.load("analysis/self-switch-writes.json")[0]["letter"], "A")

    def test_compatibility_report_is_generated(self):
        proc = self.run_reader()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = self.load("analysis/script-compatibility.json")
        methods = {item["method"]: item for item in report["method_collisions"]}
        self.assertIn("Game_Battler#item_apply", methods)
        self.assertEqual(methods["Game_Battler#item_apply"]["severity"], "high")
        self.assertTrue((self.output / "analysis/script-compatibility.md").is_file())

    def test_source_project_is_not_modified(self):
        before = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        proc = self.run_reader()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        after = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
