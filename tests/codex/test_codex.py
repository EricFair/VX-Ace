import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READER = ROOT / "tools" / "vxace_project_reader.py"
CODEX = ROOT / "tools" / "vxace_codex.py"
FIXTURE = ROOT / "tests" / "project_reader" / "make_fixture.rb"


class CodexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ruby = shutil.which("ruby")
        if not cls.ruby:
            raise unittest.SkipTest("Ruby is required for project-reader fixture tests")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name)
        cls.project = cls.base / "SyntheticVXACE"
        cls.index = cls.base / "index"
        subprocess.run([cls.ruby, str(FIXTURE), str(cls.project)], check=True)
        proc = subprocess.run([sys.executable, str(READER), str(cls.project), "--output", str(cls.index), "--ruby", cls.ruby], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def load(self, rel):
        with (self.index / rel).open("r", encoding="utf-8") as f:
            return json.load(f)

    def test_reader_generates_codex_automatically(self):
        project = self.load("project.json")
        self.assertEqual(project["codex_generation"]["status"], "ok")
        self.assertTrue((self.index / "codex" / "index.json").is_file())
        self.assertTrue((self.index / "codex" / "summary.md").is_file())

    def test_quest_candidate_is_evidence_based(self):
        codex = self.load("codex/index.json")
        quests = [x for x in codex["systems"] if x["type"] == "quest_candidate"]
        self.assertEqual(len(quests), 1)
        quest = quests[0]
        self.assertEqual(quest["state_variable"]["name"], "QuestStage")
        self.assertEqual(quest["state_variable"]["observed_values"], [2])
        self.assertEqual(quest["stage_meanings"], {})
        self.assertEqual(quest["confidence"], "high")
        self.assertTrue(any(x.get("common_event_name") == "Advance Quest" for x in quest["evidence"]))

    def test_state_machine_does_not_invent_value_meanings(self):
        states = self.load("codex/state-machines.json")
        state = next(x for x in states if x["name"] == "QuestStage")
        self.assertEqual(state["observed_values"], [2])
        self.assertEqual(state["value_meanings"], {})
        self.assertIn("intentionally left blank", state["note"])

    def test_boss_gate_and_cutscene_candidates(self):
        systems = self.load("codex/systems.json")
        gates = [x for x in systems if x["type"] == "boss_or_battle_gate_candidate"]
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0]["troop"]["name"], "Test Slimes")
        self.assertIn("BossDefeated", [x["name"] for x in gates[0]["related_switches"]])
        cutscenes = [x for x in systems if x["type"] == "cutscene_candidate"]
        self.assertEqual(len(cutscenes), 1)
        self.assertEqual(cutscenes[0]["event_name"], "Opening Cutscene")
        self.assertEqual(cutscenes[0]["autorun_pages"], [1])

    def test_graph_preserves_transfer_source_and_destination(self):
        graph = self.load("codex/graph.json")
        edge = next(x for x in graph["edges"] if x["relation"] == "transfers_to")
        self.assertEqual(edge["from"], "map:1:event:1:page:1")
        self.assertEqual(edge["to"], "map:2")

    def test_map_codex_links_event_dependencies(self):
        maps = self.load("codex/maps.json")
        test_map = next(x for x in maps if x["map_id"] == 1)
        gate = next(x for x in test_map["events"] if x["name"] == "Quest Gate")
        page = gate["pages"][0]
        self.assertIn("QuestStarted", [x["name"] for x in page["switches"]])
        self.assertIn("Advance Quest", [x["name"] for x in page["common_events"]])
        self.assertEqual(page["battles"][0]["troop_name"], "Test Slimes")
        self.assertEqual(page["transfers"][0]["map_name"], "Destination")

    def test_script_codex_preserves_order_and_collisions(self):
        scripts = self.load("codex/scripts.json")
        self.assertEqual([x["name"] for x in scripts["scripts"]], ["Core Battle", "Alias Extension", "Destructive Extension"])
        destructive = scripts["scripts"][2]
        self.assertTrue(any(x["method"] == "Game_Battler#item_apply" and x["severity"] == "high" for x in destructive["collision_candidates"]))

    def test_codex_can_be_regenerated_independently(self):
        shutil.rmtree(self.index / "codex")
        proc = subprocess.run([sys.executable, str(CODEX), str(self.index)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(result["system_count"], 3)


if __name__ == "__main__":
    unittest.main()
