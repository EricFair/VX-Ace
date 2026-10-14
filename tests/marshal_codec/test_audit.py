import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "vxace_codec_audit.py"
sys.path.insert(0, str(ROOT / "tools" / "_vendor"))
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject, RubyUserDef

spec = importlib.util.spec_from_file_location("codec_audit", TOOL)
audit_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_tool)


class AuditSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "game"
        self.data = self.project / "Data"
        self.data.mkdir(parents=True)
        self.file = self.data / "Actors.rvdata2"
        self.file.write_bytes(marshal_rb.dump([None, RubyObject("RPG::Actor", {"@id": 1})]))
        self.output = self.base / "report"

    def call(self, output=None):
        return subprocess.run([sys.executable, str(TOOL), str(self.project),
                               "--output", str(output or self.output)],
                              capture_output=True, text=True)

    def report(self):
        return json.loads((self.output / "codec-audit.json").read_text())

    def test_pass_never_grants_production_readiness_or_writes_game(self):
        before = {p.relative_to(self.project): p.read_bytes()
                  for p in self.project.rglob("*") if p.is_file()}
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.report()
        self.assertTrue(report["experimental_codec_pass"])
        self.assertFalse(report["mutation_authorized"])
        self.assertFalse(report["production_gate_satisfied"])
        self.assertNotIn("copy_mutation_ready", report)
        self.assertNotIn(str(self.project), json.dumps(report))
        after = {p.relative_to(self.project): p.read_bytes()
                 for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_opaque_custom_dump_is_preserved_without_loading_custom_code(self):
        self.file.write_bytes(marshal_rb.dump(RubyUserDef("Custom::Payload", b"opaque\x00\xff")))
        self.assertEqual(self.call().returncode, 0)
        self.assertTrue(self.report()["files"][0]["byte_identical"])

    def test_corrupt_file_refuses_but_other_files_are_still_audited(self):
        (self.data / "Broken.rvdata2").write_bytes(b"not marshal")
        self.assertEqual(self.call().returncode, 3)
        report = self.report()
        self.assertEqual((report["checked"], report["failed"]), (2, 1))
        self.assertFalse(report["experimental_codec_pass"])

    def test_trailing_bytes_refuse_instead_of_silently_discarding_data(self):
        self.file.write_bytes(self.file.read_bytes() + b"trailing payload")
        self.assertEqual(self.call().returncode, 3)
        self.assertEqual(self.report()["files"][0]["reason"], "codec_warnings")

    def test_output_inside_game_refused_before_creating_files(self):
        output = self.project / "audit"
        self.assertEqual(self.call(output).returncode, 2)
        self.assertFalse(output.exists())

    def test_existing_reports_cannot_be_overwritten(self):
        self.output.mkdir()
        marker = self.output / "keep.txt"
        marker.write_text("preserve")
        self.assertEqual(self.call().returncode, 2)
        self.assertEqual(marker.read_text(), "preserve")

    def test_empty_project_is_error_not_vacuous_pass(self):
        self.file.unlink()
        self.assertEqual(self.call().returncode, 2)
        self.assertFalse(self.output.exists())

    def test_timeout_is_a_refusal(self):
        with patch.object(audit_tool.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("codec", 1)):
            row = audit_tool.audit_file(self.file, audit_tool.digest(self.file), 1)
        self.assertEqual(row["reason"], "timeout")
        self.assertEqual(row["status"], "failed")

    def test_codec_error_report_omits_absolute_source_file_path(self):
        proc = subprocess.CompletedProcess([], 2, "", "cannot read " + str(self.file))
        with patch.object(audit_tool.subprocess, "run", return_value=proc):
            row = audit_tool.audit_file(self.file, audit_tool.digest(self.file), 1)
        self.assertNotIn(str(self.project), row["error"])
        self.assertIn(self.file.name, row["error"])

    def test_changed_source_inventory_refuses_an_otherwise_clean_audit(self):
        original = audit_tool.inventory
        calls = 0

        def changed_inventory(data):
            nonlocal calls
            calls += 1
            result = original(data)
            if calls == 2:
                result["NewMap.rvdata2"] = "new source content"
            return result

        with patch.object(audit_tool, "inventory", side_effect=changed_inventory):
            report = audit_tool.audit(self.project, self.output)
        self.assertFalse(report["source_data_unchanged"])
        self.assertFalse(report["experimental_codec_pass"])

    def test_byte_difference_refuses_even_without_codec_warning(self):
        result = {"source_sha256": "original", "roundtrip_sha256": "different",
                  "byte_identical": False, "warnings": [], "warning_count": 0}
        proc = subprocess.CompletedProcess([], 0, json.dumps(result), "")
        with patch.object(audit_tool.subprocess, "run", return_value=proc):
            row = audit_tool.audit_file(self.file, "original", 1)
        self.assertEqual(row["reason"], "byte_mismatch")
        self.assertEqual(row["status"], "failed")

    @unittest.skipUnless(shutil.which("ruby"), "Ruby required for cross-backend fixture")
    def test_python_and_production_ruby_gates_agree_on_ruby_generated_fixture(self):
        project = self.base / "ruby-generated-game"
        fixture = ROOT / "tests/project_reader/make_fixture.rb"
        subprocess.run(["ruby", str(fixture), str(project)], check=True, capture_output=True)
        production_out = self.base / "production-report"
        proc = subprocess.run([sys.executable, str(ROOT / "tools/vxace_project_validator.py"),
                               str(project), "--output", str(production_out)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        production = json.loads((production_out / "validation.json").read_text())
        experimental = audit_tool.audit(project, self.output)
        self.assertTrue(experimental["experimental_codec_pass"])
        ruby_files = {r["path"]: r["source_sha256"] for r in production["roundtrip"]["files"]}
        python_files = {r["path"]: r["source_sha256"] for r in experimental["files"]}
        self.assertEqual(ruby_files, python_files)
        self.assertGreater(len(python_files), 5)
        self.assertFalse(experimental["production_gate_satisfied"])
