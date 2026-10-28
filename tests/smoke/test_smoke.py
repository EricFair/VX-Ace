import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import vxace_smoke as smoke
import vxace_python_mutator as backend

TOOL = ROOT / 'tools/vxace_smoke.py'
NONCE = 'a1b2c3d4e5f60718293a4b5c6d7e8f90'

FAKE_GAME = r'''
import os, sys, time
mode = os.environ.get("FAKE_MODE", "pass")
nonce = os.environ["VXA_SMOKE_NONCE"]
out = os.environ["VXA_SMOKE_OUT"]
test = "true" if "test" in sys.argv[1:] else "false"
if mode == "wrongtest":
    test = "false" if test == "true" else "true"
if mode == "sleep":
    time.sleep(60)
if mode == "nofile":
    sys.exit(0)
header = "\t".join(["VXA_SMOKE", "ffffffffffffffffffffffffffffffff" if mode == "badnonce" else nonce, "1.9.2", test, "false"])
records = ["INFO\tboot\tmode=" + os.environ["VXA_SMOKE_START"], "PASS\tfirst\t"]
if mode == "fail":
    records.append("FAIL\tcheck_two\tcheck returned false")
if mode == "uncaught":
    records.append("ERROR\tuncaught\tRuntimeError: boom @ {0001}:12:in `foo' | {0099}:3:in `bar'")
lines = [header] + records
count = len(records)
if mode == "badcount":
    count += 1
if mode != "nofooter":
    lines.append("END\t%s\t%d" % (nonce, count))
if mode == "after":
    lines.append("PASS\tlate\t")
if mode == "unknown":
    lines.insert(2, "WARN\tx\ty")
with open(out, "ab") as f:
    f.write(("\n".join(lines) + "\n").encode("utf-8"))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
'''


class FakeStageMixin:
    """Builds a synthetic staged work directory so run() tests need no Ruby or Game.exe."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / 'project'
        (self.project / 'Data').mkdir(parents=True)
        (self.project / 'Data/Scripts.rvdata2').write_bytes(b'project scripts')
        self.work = self.base / 'work'
        (self.work / 'copy/Data').mkdir(parents=True)
        scripts = self.work / 'copy/Data/Scripts.rvdata2'
        scripts.write_bytes(b'staged scripts')
        self.scripts = scripts
        record = {'version': '1.8.0', 'project': str(self.project), 'copy': str(self.work / 'copy'), 'slot_name': smoke.SLOT_NAME,
                  'slot_index': 1, 'script_names': ['Core', smoke.SLOT_NAME, 'Main'],
                  'scripts_sha256': hashlib.sha256(b'staged scripts').hexdigest(), 'slot_source_sha256': '0' * 64, 'suite_sha256': None}
        (self.work / smoke.STAGE_FILE).write_text(json.dumps(record), encoding='utf-8')
        (self.base / 'fake_game.py').write_text(FAKE_GAME, encoding='utf-8')
        self.out = self.base / 'out'
        self.out.mkdir()

    def run_cli(self, *extra, mode='pass', env=None, json_name='r.json', md_name='r.md', launcher=True):
        import os
        environment = dict(os.environ, FAKE_MODE=mode, **(env or {}))
        args = [sys.executable, str(TOOL), 'run', str(self.work), '--json', str(self.out / json_name), '--markdown', str(self.out / md_name)]
        if launcher:
            args += ['--launcher', json.dumps([sys.executable, str(self.base / 'fake_game.py')])]
        proc = subprocess.run(args + list(extra), capture_output=True, text=True, env=environment)
        report = None
        if (self.out / json_name).exists():
            report = json.loads((self.out / json_name).read_text(encoding='utf-8'))
        return proc, report


class RunTests(FakeStageMixin, unittest.TestCase):
    def test_passing_run_reports_pass_and_evidence_flags(self):
        proc, report = self.run_cli('--mode', 'test', '--start', 'save:2', '--frames', '90', '--auto-confirm', '4')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report['status'], 'pass')
        self.assertEqual((report['mode'], report['start'], report['frames'], report['auto_confirm']), ('test', 'save:2', 90, 4))
        self.assertEqual(report['counts'], {'PASS': 1, 'FAIL': 0, 'ERROR': 0, 'INFO': 1})
        self.assertEqual(report['runtime'], {'ruby_version': '1.9.2', 'test': True, 'btest': False})
        self.assertFalse(report['runtime_compatibility_proven'])
        self.assertFalse(report['mutation_authorized'])
        self.assertEqual(report['process_exit_code'], 0)
        self.assertRegex(report['nonce'], '^[a-f0-9]{32}$')
        self.assertEqual(report['results_file'], 'vxa_smoke_' + report['nonce'] + '.txt')
        self.assertIn('**pass**', (self.out / 'r.md').read_text(encoding='utf-8'))

    def test_normal_mode_omits_test_argument_and_repeat_runs_use_new_nonces(self):
        proc, first = self.run_cli('--mode', 'normal')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(first['runtime']['test'])
        proc, second = self.run_cli('--mode', 'normal', json_name='r2.json', md_name='r2.md')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotEqual(first['nonce'], second['nonce'])

    def test_header_test_flag_must_match_requested_mode(self):
        for run_mode in ('test', 'normal'):
            proc, report = self.run_cli('--mode', run_mode, mode='wrongtest', json_name=run_mode + '.json', md_name=run_mode + '.md')
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(report['status'], 'incomplete')
            self.assertTrue(any('$TEST' in problem for problem in report['problems']))

    def test_fail_record_exits_3(self):
        proc, report = self.run_cli('--mode', 'test', mode='fail')
        self.assertEqual(proc.returncode, 3)
        self.assertEqual((report['status'], report['counts']['FAIL']), ('failed', 1))

    def test_uncaught_error_exits_3_and_maps_script_ids(self):
        proc, report = self.run_cli('--mode', 'test', mode='uncaught')
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['uncaught'], 1)
        refs = {(r['id'], r['script']) for r in report['script_refs']}
        self.assertEqual(refs, {('0001', smoke.SLOT_NAME), ('0099', None)})

    def test_invalid_result_files_are_incomplete_exit_3(self):
        for mode, fragment in (('badnonce', 'nonce'), ('nofooter', 'footer'), ('badcount', 'count'), ('after', 'after footer'),
                               ('unknown', 'unknown'), ('nofile', 'not written')):
            proc, report = self.run_cli('--mode', 'test', mode=mode, json_name=mode + '.json', md_name=mode + '.md')
            self.assertEqual(proc.returncode, 3, mode)
            self.assertEqual(report['status'], 'incomplete', mode)
            self.assertTrue(any(fragment in problem for problem in report['problems']), (mode, report['problems']))

    def test_timeout_kills_process_and_reports(self):
        proc, report = self.run_cli('--mode', 'test', '--timeout', '1', mode='sleep')
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(report['status'], 'timeout')
        self.assertTrue(report['timed_out'])
        self.assertLess(report['duration_seconds'], 30)

    def test_changed_staged_scripts_refuse_before_launch(self):
        self.scripts.write_bytes(b'tampered')
        proc, report = self.run_cli('--mode', 'test')
        self.assertEqual(proc.returncode, 2)
        self.assertIsNone(report)
        self.assertEqual(list((self.work / 'copy').glob('vxa_smoke_*')), [])

    def test_output_guards(self):
        existing = self.out / 'exists.json'
        existing.write_text('x')
        for json_path, md_path in ((existing, self.out / 'a.md'), (self.out / 'a.json', existing),
                                   (self.project / 'a.json', self.out / 'a.md'), (self.out / 'a.json', self.project / 'a.md'),
                                   (self.work / 'copy/a.json', self.out / 'a.md'), (self.out / 'a.json', self.work / 'copy/a.md'),
                                   (self.out / 'same.json', self.out / 'same.json')):
            proc = subprocess.run([sys.executable, str(TOOL), 'run', str(self.work), '--mode', 'test', '--json', str(json_path), '--markdown', str(md_path),
                                   '--launcher', json.dumps([sys.executable, str(self.base / 'fake_game.py')])], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2, (json_path, md_path))
        self.assertEqual(list((self.work / 'copy').glob('vxa_smoke_*')), [])

    def test_bad_start_frames_timeout_auto_confirm_and_mode(self):
        for extra in (('--start', 'save:0'), ('--start', 'save:17'), ('--start', 'load'), ('--start', 'save:1;x'), ('--frames', '0'),
                      ('--frames', '1000001'), ('--frames', 'x'), ('--auto-confirm', '-1'), ('--timeout', '0'), ('--timeout', '9999')):
            proc, report = self.run_cli('--mode', 'test', *extra)
            self.assertEqual(proc.returncode, 2, extra)
            self.assertIsNone(report)
        proc, report = self.run_cli('--mode', 'weird')
        self.assertEqual(proc.returncode, 2)

    def test_missing_or_corrupt_stage_record_refuses(self):
        (self.work / smoke.STAGE_FILE).write_text('{"version": "1.8.0"}')
        proc, report = self.run_cli('--mode', 'test')
        self.assertEqual(proc.returncode, 2)
        (self.work / smoke.STAGE_FILE).unlink()
        proc, report = self.run_cli('--mode', 'test')
        self.assertEqual(proc.returncode, 2)

    @unittest.skipIf(sys.platform == 'win32', 'real launch is Windows-only; other hosts must refuse')
    def test_real_launch_refused_off_windows(self):
        proc, report = self.run_cli('--mode', 'test', launcher=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('Windows', proc.stderr)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows-only check')
    def test_real_launch_without_game_exe_refused(self):
        proc, report = self.run_cli('--mode', 'test', launcher=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('Game.exe', proc.stderr)


class ParseTests(unittest.TestCase):
    def good(self, *middle, count=None, footer=True):
        lines = ['\t'.join(['VXA_SMOKE', NONCE, '1.9.2', 'true', 'false'])] + list(middle)
        if footer:
            lines.append('END\t%s\t%d' % (NONCE, len(middle) if count is None else count))
        return ('\n'.join(lines) + '\n').encode()

    def test_valid_and_strict_failures(self):
        self.assertEqual(smoke.parse_results(self.good('PASS\ta\t'), NONCE)['problems'], [])
        cases = {'no records': self.good(), 'bad count': self.good('PASS\ta\t', count=2), 'no footer': self.good('PASS\ta\t', footer=False),
                 'wrong type': self.good('NOPE\ta\tb'), 'two fields': self.good('PASS\ta'), 'empty': b'',
                 'oversize': b'x' * (smoke.MAX_RESULT_BYTES + 1), 'binary': b'\xff\xfe', 'blank line': self.good('PASS\ta\t', '')}
        for label, raw in cases.items():
            self.assertTrue(smoke.parse_results(raw, NONCE)['problems'], label)
        other = self.good('PASS\ta\t').replace(NONCE.encode(), b'0' * 32)
        self.assertTrue(smoke.parse_results(other, NONCE)['problems'])

    def test_records_after_footer_and_duplicate_header_refused(self):
        raw = self.good('PASS\ta\t') + b'PASS\tb\t\n'
        self.assertIn('records after footer', ' '.join(smoke.parse_results(raw, NONCE)['problems']))
        raw = self.good('PASS\ta\t') [:-1]
        self.assertTrue(smoke.parse_results(raw, NONCE)['problems'])


@unittest.skipUnless(shutil.which('ruby'), 'Ruby required for staging')
class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.game = self.base / 'game'
        subprocess.run(['ruby', str(ROOT / 'tests/project_reader/make_fixture.rb'), str(self.game)], check=True, capture_output=True)
        ruby = self.base / 'main.rb'
        ruby.write_text("require 'zlib'\np=ARGV[0]+'/Data/Scripts.rvdata2'\ns=Marshal.load(File.binread(p))\ns << [104,'Main',Zlib::Deflate.deflate(\"# owned header\\r\\nrgss_main { SceneManager.run }\\r\\n\").force_encoding('UTF-8')]\nFile.binwrite(p,Marshal.dump(s))\n", encoding='utf-8')
        subprocess.run(['ruby', str(ruby), str(self.game)], check=True, capture_output=True)
        (self.game / 'Game.exe').write_bytes(b'fake exe')
        self.work = self.base / 'work'

    def stage(self, *extra, work=None):
        return subprocess.run([sys.executable, str(TOOL), 'stage', str(self.game), '--work', str(work or self.work), *extra], capture_output=True, text=True)

    def test_stage_inserts_harness_before_main_and_leaves_original_untouched(self):
        from vxace_copy_patcher import current_inventory
        before = current_inventory(self.game)
        suite = self.base / 'suite.rb'
        suite.write_text("VXA_Smoke.check('é unicode') { true }\n", encoding='utf-8')
        result = self.stage('--suite', str(suite))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(current_inventory(self.game), before)
        for name in ('validation', 'index', 'snapshot', 'plan', 'audit', 'copy'):
            self.assertTrue((self.work / name).is_dir(), name)
        for name in ('spec.json', 'impact.json', 'impact.md', smoke.STAGE_FILE):
            self.assertTrue((self.work / name).is_file(), name)
        root, _ = backend.load(self.work / 'copy/Data/Scripts.rvdata2')
        names = [entry[1].data.decode('utf-8') for entry in root]
        slot = names.index(smoke.SLOT_NAME)
        self.assertEqual(names[slot + 1], 'Main')
        original, _ = backend.load(self.game / 'Data/Scripts.rvdata2')
        self.assertEqual(len(names), len(original) + 1)
        source = zlib.decompress(root[slot][2].data).decode('utf-8')
        self.assertTrue(source.startswith(smoke.RUNTIME.read_bytes().decode('utf-8')))
        self.assertIn("é unicode", source)
        record = json.loads((self.work / smoke.STAGE_FILE).read_text(encoding='utf-8'))
        self.assertEqual(record['scripts_sha256'], hashlib.sha256((self.work / 'copy/Data/Scripts.rvdata2').read_bytes()).hexdigest())
        self.assertEqual(record['slot_source_sha256'], hashlib.sha256(source.encode('utf-8')).hexdigest())
        self.assertEqual(record['suite_sha256'], hashlib.sha256(suite.read_bytes()).hexdigest())
        self.assertEqual(record['project'], str(self.game))
        self.assertEqual(record['script_names'], names)
        self.assertFalse(record['runtime_compatibility_proven'])
        self.assertTrue((self.work / 'copy/Game.exe').is_file())
        self.assertEqual(list(self.game.glob('vxa_smoke_*')), [])

    def test_staged_copy_runs_with_fake_launcher_end_to_end(self):
        self.assertEqual(self.stage().returncode, 0)
        fake = self.base / 'fake_game.py'
        fake.write_text(FAKE_GAME, encoding='utf-8')
        proc = subprocess.run([sys.executable, str(TOOL), 'run', str(self.work), '--mode', 'test', '--json', str(self.base / 'r.json'), '--markdown', str(self.base / 'r.md'),
                               '--launcher', json.dumps([sys.executable, str(fake)])], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads((self.base / 'r.json').read_text())['status'], 'pass')

    def test_stage_refusals(self):
        self.assertEqual(self.stage(work=self.game / 'inside').returncode, 2)
        self.assertEqual(self.stage(work=self.base).returncode, 2)
        self.work.mkdir()
        self.assertEqual(self.stage().returncode, 2)
        big = self.base / 'big.rb'
        big.write_bytes(b'#' * (256 * 1024))
        self.assertEqual(self.stage('--suite', str(big), work=self.base / 'w2').returncode, 2)
        nul = self.base / 'nul.rb'
        nul.write_bytes(b'x\0y')
        self.assertEqual(self.stage('--suite', str(nul), work=self.base / 'w3').returncode, 2)
        bad = self.base / 'bad.rb'
        bad.write_bytes(b'\xff\xfe')
        self.assertEqual(self.stage('--suite', str(bad), work=self.base / 'w4').returncode, 2)

    def test_stage_refuses_without_canonical_main_and_keeps_work_dir(self):
        ruby = self.base / 'custom.rb'
        ruby.write_text("require 'zlib'\np=ARGV[0]+'/Data/Scripts.rvdata2'\ns=Marshal.load(File.binread(p))\ns[-1][2]=Zlib::Deflate.deflate(\"puts 1\\r\\nrgss_main { SceneManager.run }\\r\\n\").force_encoding('UTF-8')\nFile.binwrite(p,Marshal.dump(s))\n", encoding='utf-8')
        subprocess.run(['ruby', str(ruby), str(self.game)], check=True, capture_output=True)
        result = self.stage()
        self.assertEqual(result.returncode, 2)
        self.assertTrue(self.work.exists())
        self.assertFalse((self.work / 'copy').exists())


if __name__ == '__main__':
    unittest.main()
