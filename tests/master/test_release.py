import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests/mutation"))
import test_v08 as baseline
import vxace_master as master
import vxace_inspect as inspection
import vxace_python_mutator as python_backend
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject, RubyFloat


@unittest.skipUnless(shutil.which("ruby"), "Ruby required for fixture and independent verification")
class PythonCopyBackendTests(baseline.MutationV08Tests):
    def setUp(self):
        super().setUp()
        original = baseline.run
        def python_runner(*args):
            if len(args) > 1 and Path(str(args[1])).name == "vxace_copy_patcher.py":
                args = (*args, "--backend", "python")
            return original(*args)
        self.runner = patch.object(baseline, "run", side_effect=python_runner)
        self.runner.start()
        self.addCleanup(self.runner.stop)


class ReleaseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_real_failure_shape_preserves_legacy_float_text(self):
        # Modern Ruby changes a legacy f"500" record into f"5e2". No private
        # game data is used in this minimal regression fixture.
        raw = b"\x04\x08f\x08500"
        file = self.base / "legacy.rvdata2"
        file.write_bytes(raw)
        root, original = python_backend.load(file)
        out = self.base / "roundtrip.rvdata2"
        python_backend.write(root, out)
        self.assertEqual(out.read_bytes(), raw)

    def test_unrelated_legacy_float_bytes_survive_database_mutation(self):
        source = self.base / "database.rvdata2"
        root = [None, RubyObject("RPG::Actor", {"@id": 1, "@name": python_backend.convert("Eric"),
                                               "@value": RubyFloat(500.0, raw=b"500")})]
        source.write_bytes(marshal_rb.dump(root))
        loaded, raw = python_backend.load(source)
        python_backend.apply(loaded, {"type": "database", "mutation": {"id": 1, "field": "name", "value": "Test"}})
        out = self.base / "candidate.rvdata2"
        python_backend.write(loaded, out)
        candidate = marshal_rb.load(out.read_bytes())
        self.assertEqual(candidate[1].get("value").raw, b"500")
        self.assertEqual(source.read_bytes(), raw)

    def test_python_backend_rejects_type_changes_and_unknown_fields(self):
        root = [None, RubyObject("RPG::Actor", {"@id": 1, "@name": python_backend.convert("Eric")})]
        for field, value in (("name", 7), ("missing", "new"), ("id", 2)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                python_backend.apply(root, {"type": "database", "mutation": {"id": 1, "field": field, "value": value}})

    def test_script_mutation_refuses_trailing_compressed_payload(self):
        root = [[1, python_backend.convert("Main"), python_backend.RubyString(zlib.compress(b"puts 1") + b"trailing")]]
        with self.assertRaises(ValueError):
            python_backend.apply(root, {"type": "scripts", "mutation": {"script_index": 0, "search": "puts 1", "replace": "puts 2"}})

    def test_config_cannot_weaken_original_project_policy(self):
        config = json.loads((ROOT / "vxace-master.json").read_text())
        config["safety"]["original_project_writes"] = True
        path = self.base / "unsafe.json"
        path.write_text(json.dumps(config))
        with self.assertRaises(ValueError):
            master.settings(path)

    def test_inspection_separates_variable_transfers_from_direct_coordinates(self):
        index = self.base / "index"
        (index / "maps").mkdir(parents=True)
        (index / "analysis").mkdir()
        (index / "project.json").write_text(json.dumps({"errors": []}))
        (index / "maps/map-001.json").write_text(json.dumps({"__class__": "RPG::Map", "width": 10, "height": 10}))
        transfers = [{"designation": "variables", "map_id": 999, "x": 999, "y": 999},
                     {"designation": "direct", "map_id": 1, "x": 10, "y": 0}]
        (index / "analysis/event-references.json").write_text(json.dumps({"map_transfers": transfers}))
        result = inspection.inspect(index)
        self.assertEqual([x["code"] for x in result["findings"]], ["transfer_out_of_bounds"])
        self.assertEqual(result["classes"]["RPG::Map"]["fields"]["width"], ["int"])

    def test_refused_project_gate_prevents_copy_even_when_target_would_pass(self):
        project = self.base / "game"
        (project / "Data").mkdir(parents=True)
        (project / "Data/Actors.rvdata2").write_bytes(marshal_rb.dump([None, RubyObject("RPG::Actor", {
            "@id": 1, "@name": python_backend.convert("Eric")})]))
        (project / "Data/Other.rvdata2").write_bytes(b"bad")
        index = self.base / "index"
        index.mkdir()
        from vxace_copy_patcher import current_inventory
        inventory = current_inventory(project)
        (index / "manifest.json").write_text(json.dumps({"read_only": True, "files": [
            {"path": k, "sha256": v} for k, v in inventory.items()]}))
        spec = self.base / "spec.json"
        spec.write_text(json.dumps({"changes": [{"kind": "database", "locator": {"table": "actors", "id": 1},
                                              "mutation": {"field": "name", "value": "Test"}}]}))
        with patch("vxace_project_validator.find_ruby", return_value=sys.executable):
            from vxace_copy_patcher import build
            with self.assertRaisesRegex(RuntimeError, "project-wide"):
                build(index, project, spec, self.base / "copy", self.base / "audit", sys.executable,
                      ROOT / "tools/vxace_python_mutator.py", None, None, True)
        self.assertFalse((self.base / "copy").exists())
        self.assertEqual(current_inventory(project), inventory)

    @unittest.skipUnless(shutil.which("ruby"), "Ruby required for full master fixture")
    def test_master_runs_read_only_complete_pipeline(self):
        project = self.base / "game"
        subprocess.run(["ruby", str(ROOT / "tests/project_reader/make_fixture.rb"), str(project)], check=True)
        result = master.workflow(project, self.base / "report", shutil.which("ruby"), ROOT / "vxace-master.json")
        self.assertTrue(result["source_unchanged"])
        self.assertFalse(result["mutation_performed"])
        self.assertEqual([x["name"] for x in result["stages"]], ["validation", "codec-audit", "reader", "inspection"])
        self.assertTrue(result["copy_mutation_ready"])
