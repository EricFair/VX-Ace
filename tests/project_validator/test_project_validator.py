import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools" / "vxace_project_validator.py"
FIXTURE = ROOT / "tests" / "project_reader" / "make_fixture.rb"

MUTATOR_SAFE = """#!/usr/bin/env ruby
require 'json'; require 'fileutils'
mode,input,output = ARGV
abort 'bad mode' unless mode == 'roundtrip'
FileUtils.mkdir_p(File.dirname(output)); FileUtils.cp(input, output)
puts JSON.generate({'status'=>'ok'})
"""
MUTATOR_BAD = """#!/usr/bin/env ruby
require 'json'; require 'fileutils'
mode,input,output = ARGV
abort 'bad mode' unless mode == 'roundtrip'
FileUtils.mkdir_p(File.dirname(output)); File.binwrite(output, File.binread(input) + 'x')
puts JSON.generate({'status'=>'ok'})
"""
BRIDGE = """#!/usr/bin/env ruby
require 'json'
mode,path = ARGV
abort 'bad mode' unless mode == 'scripts'
puts JSON.generate({'scripts'=>[{'index'=>0,'name'=>'Good','source'=>\"class A\\nend\\n\"},{'index'=>1,'name'=>'Bad','source'=>\"class B\\n\"}]})
"""

class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.project = self.base / "Game"
        (self.project / "Data").mkdir(parents=True)
        (self.project / "Game.rvproj2").write_text("RPGVXAce 1.02")
        (self.project / "Data" / "Actors.rvdata2").write_bytes(b"abc123")
        self.ruby = shutil.which("ruby")
        if not self.ruby:
            self.skipTest("Ruby required")
        self.safe = self.base / "safe.rb"; self.safe.write_text(MUTATOR_SAFE)
        self.bad = self.base / "bad.rb"; self.bad.write_text(MUTATOR_BAD)
        self.bridge = self.base / "bridge.rb"; self.bridge.write_text(BRIDGE)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, mutator, extra=None, name="report"):
        out = self.base / name
        cmd = [sys.executable, str(VALIDATOR), str(self.project), "--output", str(out), "--ruby", self.ruby, "--mutator", str(mutator), "--bridge", str(self.bridge)] + (extra or [])
        return subprocess.run(cmd, capture_output=True, text=True), out

    def test_byte_identical_project_is_ready(self):
        proc, out = self.call(self.safe, ["--skip-script-syntax"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads((out / "validation.json").read_text())
        self.assertTrue(report["copy_mutation_ready"])

    def test_byte_mismatch_refuses_mutation_readiness(self):
        proc, out = self.call(self.bad, ["--skip-script-syntax"])
        self.assertEqual(proc.returncode, 3)
        report = json.loads((out / "validation.json").read_text())
        self.assertEqual(report["roundtrip"]["files"][0]["reason"], "byte_mismatch")

    def test_source_project_is_immutable(self):
        before = (self.project / "Data" / "Actors.rvdata2").read_bytes()
        proc, _ = self.call(self.safe, ["--skip-script-syntax"])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(before, (self.project / "Data" / "Actors.rvdata2").read_bytes())

    def test_output_inside_source_is_rejected(self):
        out = self.project / "validation"
        proc = subprocess.run([sys.executable, str(VALIDATOR), str(self.project), "--output", str(out), "--ruby", self.ruby, "--mutator", str(self.safe), "--bridge", str(self.bridge), "--skip-script-syntax"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("outside the source project", proc.stderr)

    def test_host_ruby_syntax_is_diagnostic_not_mutation_gate(self):
        (self.project / "Data" / "Scripts.rvdata2").write_bytes(b"scripts")
        proc, out = self.call(self.safe)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads((out / "validation.json").read_text())
        self.assertTrue(report["copy_mutation_ready"])
        self.assertEqual(report["script_syntax"]["status"], "failed")
        self.assertFalse(report["script_syntax"]["ruby_19_compatibility_proven"])

    def test_empty_data_directory_is_error(self):
        (self.project / "Data" / "Actors.rvdata2").unlink()
        proc, _ = self.call(self.safe, ["--skip-script-syntax"])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("No .rvdata2 files", proc.stderr)

    def test_real_toolchain_fixture_passes_full_validator(self):
        project = self.base / "SyntheticVXACE"
        subprocess.run([self.ruby, str(FIXTURE), str(project)], check=True)
        out = self.base / "real-report"
        proc = subprocess.run([sys.executable, str(VALIDATOR), str(project), "--output", str(out), "--ruby", self.ruby], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads((out / "validation.json").read_text())
        self.assertTrue(report["copy_mutation_ready"])
        self.assertEqual(report["roundtrip"]["failed"], 0)
        self.assertEqual(report["script_syntax"]["status"], "pass")
        self.assertGreaterEqual(report["roundtrip"]["checked"], 8)

if __name__ == "__main__":
    unittest.main()
