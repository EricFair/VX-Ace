import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import vxace_smoke as smoke

RUNTIME = ROOT / 'tools/smoke/vxa_smoke_runtime.rb'
EXAMPLE = ROOT / 'tools/smoke/example_suite.rb'
STUBS = Path(__file__).resolve().parent / 'stub_rgss.rb'
RUBY = shutil.which('ruby')
NONCE = 'a1b2c3d4e5f60718293a4b5c6d7e8f90'


@unittest.skipUnless(RUBY, 'Ruby required')
class RuntimeSyntaxTests(unittest.TestCase):
    def test_runtime_and_example_pass_host_syntax_check(self):
        for path in (RUNTIME, EXAMPLE):
            result = subprocess.run([RUBY, '-c', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_avoids_post_1_9_2_syntax(self):
        text = RUNTIME.read_text(encoding='utf-8')
        for token in ('&.', '%i[', '<<~', '.then', 'File.exists?'):
            self.assertNotIn(token, text)
        text.encode('ascii')


@unittest.skipUnless(RUBY, 'Ruby required')
class RuntimeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def play(self, suite='', env=None, nonce=NONCE, extra_ruby=''):
        (self.dir / 'suite.rb').write_text(suite, encoding='utf-8')
        driver = self.dir / 'driver.rb'
        driver.write_text(
            "require %s\nload %s\nload 'suite.rb'\n%s\nSceneManager.run\nputs 'RETURNED'\n"
            % (repr(str(STUBS)).replace("'", '"'), repr(str(RUNTIME)).replace("'", '"'), extra_ruby), encoding='utf-8')
        environment = {k: v for k, v in os.environ.items() if not k.startswith('VXA_SMOKE_')}
        if nonce:
            environment.update({'VXA_SMOKE_NONCE': nonce, 'VXA_SMOKE_OUT': 'vxa_smoke_%s.txt' % nonce})
        environment.update(env or {})
        (self.dir / ('vxa_smoke_%s.txt' % NONCE)).unlink() if (self.dir / ('vxa_smoke_%s.txt' % NONCE)).exists() else None
        proc = subprocess.run([RUBY, str(driver)], cwd=str(self.dir), env=environment, capture_output=True, text=True)
        out = self.dir / ('vxa_smoke_%s.txt' % NONCE)
        return proc, (out.read_text(encoding='utf-8') if out.exists() else None)

    def parsed(self, text):
        return smoke.parse_results(text.encode('utf-8'), NONCE)

    def test_inert_without_nonce(self):
        proc, text = self.play("VXA_Smoke.check('x') { raise 'never' }\nVXA_Smoke.on_map { raise 'never' }\n",
                               nonce=None, extra_ruby="puts SceneManager.first_scene_class\nputs Input.trigger?(:C)\nVXA_Smoke.press(:C)\nputs Input.trigger?(:C)\nputs Graphics.method(:update).owner.inspect\nexit")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(text)
        self.assertEqual(proc.stdout.split(), ['Scene_Title', 'false', 'false', '#<Class:Graphics>'])
        self.assertEqual(list(self.dir.glob('vxa_smoke_*')), [])

    def test_inert_with_bad_nonce_or_out_name(self):
        for env in ({'VXA_SMOKE_NONCE': 'ABC', 'VXA_SMOKE_OUT': 'vxa_smoke_ABC.txt'},
                    {'VXA_SMOKE_NONCE': NONCE, 'VXA_SMOKE_OUT': 'other.txt'},
                    {'VXA_SMOKE_NONCE': NONCE, 'VXA_SMOKE_OUT': '../vxa_smoke_%s.txt' % NONCE}):
            proc, text = self.play(nonce=None, env=env, extra_ruby="puts SceneManager.first_scene_class\nexit")
            self.assertEqual(proc.stdout.split(), ['Scene_Title'])
            self.assertEqual([p.name for p in self.dir.iterdir() if p.name.endswith('.txt')], [])

    def test_header_records_footer_and_sanitising(self):
        suite = ("VXA_Smoke.check('ok') { true }\n"
                 "VXA_Smoke.on_map do\n"
                 "  VXA_Smoke.check('bad') { false }\n"
                 "  VXA_Smoke.check('err') { raise \"x\\ty\\nz\" }\n"
                 "  VXA_Smoke.info(\"tab\\tname\", 'a' * 5000)\n"
                 "end\n"
                 "VXA_Smoke.on_boot { VXA_Smoke.info('boot_hook', 'ran') }\n"
                 "VXA_Smoke.on_finish { VXA_Smoke.info('fin', 'ran') }\n")
        proc, text = self.play(suite, env={'VXA_SMOKE_FRAMES': '5'})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn('RETURNED', proc.stdout)
        result = self.parsed(text)
        self.assertEqual(result['problems'], [])
        self.assertTrue(result['header']['ruby_version'])
        self.assertTrue(result['header']['test'])
        names = [(r['type'], r['name']) for r in result['records']]
        self.assertIn(('PASS', 'ok'), names)
        self.assertIn(('FAIL', 'bad'), names)
        self.assertIn(('ERROR', 'err'), names)
        self.assertIn(('INFO', 'tab name'), names)
        self.assertIn(('INFO', 'boot_hook'), names)
        self.assertIn(('INFO', 'fin'), names)
        self.assertIn(('INFO', 'final_state'), names)
        self.assertIn(('INFO', 'map_arrival'), names)
        err = [r for r in result['records'] if r['name'] == 'err'][0]
        self.assertIn('x y z', err['detail'])
        big = [r for r in result['records'] if r['name'] == 'tab name'][0]
        self.assertLessEqual(len(big['detail']), 1003)
        self.assertEqual(text.splitlines()[0].split('\t')[:2], ['VXA_SMOKE', NONCE])
        self.assertEqual(text.splitlines()[-1], 'END\t%s\t%d' % (NONCE, len(result['records'])))
        final = [r for r in result['records'] if r['name'] == 'final_state'][0]['detail']
        self.assertIn('map=3 x=4 y=5', final)
        self.assertIn('frame=5', final)

    def test_hook_exception_is_recorded_not_fatal(self):
        suite = "VXA_Smoke.on_map { raise 'hook failed' }\nVXA_Smoke.at_frame(2) { raise 'frame hook failed' }\n"
        proc, text = self.play(suite, env={'VXA_SMOKE_FRAMES': '4'})
        result = self.parsed(text)
        self.assertEqual(result['problems'], [])
        errors = [r['name'] for r in result['records'] if r['type'] == 'ERROR']
        self.assertEqual(errors, ['on_map', 'at_frame_2'])
        self.assertIn('final_state', [r['name'] for r in result['records']])

    def test_uncaught_exception_is_wrapped_with_footer_and_exit(self):
        proc, text = self.play('', env={'VXA_SMOKE_FRAMES': '50'}, extra_ruby='$crash_at = 3')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = self.parsed(text)
        self.assertEqual(result['problems'], [])
        uncaught = [r for r in result['records'] if r['name'] == 'uncaught']
        self.assertEqual(len(uncaught), 1)
        self.assertEqual(uncaught[0]['type'], 'ERROR')
        self.assertIn('ArgumentError: boom line feed', uncaught[0]['detail'])
        self.assertIn('stub_rgss.rb', uncaught[0]['detail'])

    def test_virtual_input_and_auto_confirm(self):
        suite = "VXA_Smoke.at_frame(1) { VXA_Smoke.press(:C, 2); VXA_Smoke.press(:DOWN, 1) }\n"
        proc, text = self.play(suite, env={'VXA_SMOKE_FRAMES': '6'},
                               extra_ruby="at_exit { puts $seen.map { |a| a.join(',') }.join(' ') }")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        seen = proc.stdout.split()
        self.assertEqual(seen[:4], ['false,false,0', 'true,true,2', 'false,true,0', 'false,false,0'])
        proc, text = self.play('', env={'VXA_SMOKE_FRAMES': '6', 'VXA_SMOKE_AUTO_CONFIRM': '2'},
                               extra_ruby="at_exit { puts $seen.map { |a| a[0] }.join(',') }")
        self.assertEqual(proc.stdout.split()[0], 'false,false,true,false,true,false')

    def test_runaway_event_detection_flags_once(self):
        suite = "VXA_Smoke.at_frame(1) { $game_map.interpreter.start(7) }\n"
        proc, text = self.play(suite, env={'VXA_SMOKE_FRAMES': '700'})
        result = self.parsed(text)
        runaway = [r for r in result['records'] if r['name'] == 'runaway_event']
        self.assertEqual(len(runaway), 1)
        self.assertEqual((runaway[0]['type'], runaway[0]['detail']), ('FAIL', 'map 3 event 7'))
        proc, text = self.play("VXA_Smoke.at_frame(1) { $game_map.interpreter.start(7) }\nVXA_Smoke.at_frame(50) { $game_map.interpreter.running = false }\n",
                               env={'VXA_SMOKE_FRAMES': '700'})
        self.assertNotIn('runaway_event', text)

    def test_waiting_for_message_is_not_runaway(self):
        stub = "class Stub_Message; def busy?; true; end; end; $game_message = Stub_Message.new"
        proc, text = self.play("VXA_Smoke.at_frame(1) { $game_map.interpreter.start(7) }\n",
                               env={'VXA_SMOKE_FRAMES': '700'}, extra_ruby=stub)
        result = self.parsed(text)
        self.assertEqual(result['problems'], [])
        self.assertNotIn('runaway_event', text)
        waiting = [r for r in result['records'] if r['name'] == 'waiting_for_message']
        self.assertEqual([(r['type'], r['detail']) for r in waiting], [('INFO', 'map 3 event 7')])

    def test_save_start_success_and_failure(self):
        proc, text = self.play('', env={'VXA_SMOKE_START': 'save:1', 'VXA_SMOKE_FRAMES': '3'})
        result = self.parsed(text)
        self.assertEqual(result['problems'], [])
        self.assertIn(('INFO', 'boot', 'mode=save:1'), [(r['type'], r['name'], r['detail']) for r in result['records']])
        self.assertIn('final_state', [r['name'] for r in result['records']])
        proc, text = self.play('', env={'VXA_SMOKE_START': 'save:6', 'VXA_SMOKE_FRAMES': '3'})
        result = self.parsed(text)
        self.assertEqual(result['problems'], [])
        self.assertIn('load_save', [r['name'] for r in result['records'] if r['type'] == 'FAIL'])
        self.assertNotIn('final_state', [r['name'] for r in result['records']])

    def test_gameover_scene_detected(self):
        proc, text = self.play("VXA_Smoke.at_frame(1) { SceneManager.goto(Scene_Gameover) }\n", env={'VXA_SMOKE_FRAMES': '4'},
                               extra_ruby="class Scene_Gameover; def update; Graphics.update; end; end")
        self.assertIn('gameover', [r['name'] for r in self.parsed(text)['records']])


if __name__ == '__main__':
    unittest.main()
