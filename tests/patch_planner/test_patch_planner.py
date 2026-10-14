import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLANNER = ROOT / "tools" / "vxace_patch_planner.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PatchPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.project = self.base / "Game"
        self.index = self.base / "index"
        self.out = self.base / "patch"
        (self.project / "Data").mkdir(parents=True)
        (self.index / "scripts").mkdir(parents=True)
        src = self.project / "Data" / "System.rvdata2"
        src.write_bytes(b"synthetic-system")
        script = self.index / "scripts" / "001_Test.rb"
        script.write_text("class Game_System\n  def foo\n    1\n  end\nend\n", encoding="utf-8")
        (self.index / "manifest.json").write_text(json.dumps({
            "reader_version": "0.6.0", "read_only": True,
            "files": [{"path": "Data/System.rvdata2", "sha256": sha(src), "size": src.stat().st_size}],
        }), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_planner(self, spec):
        spec_path = self.base / "spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        return subprocess.run([sys.executable, str(PLANNER), str(self.index), "--project", str(self.project), "--spec", str(spec_path), "--output", str(self.out)], capture_output=True, text=True)

    def test_script_diff_plan(self):
        p = self.run_planner({"title":"Test", "changes":[{"kind":"script","script_path":"001_Test.rb","search":"    1\n","replace":"    2\n"}]})
        self.assertEqual(p.returncode, 0, p.stderr)
        plan = json.loads((self.out / "plan.json").read_text())
        self.assertEqual(plan["freshness"]["status"], "fresh")
        self.assertIn("-    1", plan["changes"][0]["diff"])
        self.assertIn("+    2", plan["changes"][0]["diff"])
        self.assertFalse(plan["binary_writer_enabled"])

    def test_refuses_stale_index(self):
        (self.project / "Data" / "System.rvdata2").write_bytes(b"changed")
        p = self.run_planner({"changes":[{"kind":"event","locator":{"map_id":1,"event_id":2,"page":1},"proposal":{"set_self_switch":"A"}}]})
        self.assertEqual(p.returncode, 3)
        self.assertIn("stale_index", p.stderr)
        self.assertFalse(self.out.exists())

    def test_event_and_database_are_structural_only(self):
        p = self.run_planner({"changes":[
            {"kind":"event","locator":{"map_id":1,"event_id":2,"page":1},"proposal":{"append":["Self Switch A = ON"]}},
            {"kind":"database","locator":{"table":"states","id":4},"proposal":{"note":"change poison rate"}}
        ]})
        self.assertEqual(p.returncode, 0, p.stderr)
        plan = json.loads((self.out / "plan.json").read_text())
        self.assertTrue(all(x["apply_mode"] == "manual_or_future_verified_writer" for x in plan["changes"]))
        self.assertFalse(plan["rollback"]["source_modified"])

    def test_script_search_must_be_unique(self):
        p = self.run_planner({"changes":[{"kind":"script","script_path":"001_Test.rb","search":"missing","replace":"x"}]})
        self.assertEqual(p.returncode, 2)
        self.assertIn("found 0", p.stderr)

    def test_path_traversal_refused(self):
        p = self.run_planner({"changes":[{"kind":"script","script_path":"../secret.rb","search":"x","replace":"y"}]})
        self.assertEqual(p.returncode, 2)
        self.assertIn("Unsafe relative path", p.stderr)


if __name__ == "__main__":
    unittest.main()
