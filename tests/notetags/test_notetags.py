import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import vxace_notetags as nt
from vxace_copy_patcher import current_inventory

SCRIPT = r'''# <comment_only> is ignored
module Parsers
  def self.load(note)
    return 1 if note =~ /<foo[ _]bar:\s*(\d+)>/i
    return 2 if note =~ /<Strict:\s*(\d+)>/
    return 3 if note =~ /<(?:alpha|beta)>/i
    note.scan(/<shared tag>/i)
    return 4 if note =~ /<#{dynamic}: (\d+)>/
  end
end
'''
SCRIPT2 = 'x = $1 if note =~ /<shared[ _]tag>/i\ny = 2 if note =~ /<lonely>/i\n'


def command(code, parameters=None):
    return {'__class__': 'RPG::EventCommand', 'code': code, 'indent': 0, 'parameters': parameters or []}


def page(rows):
    return {'__class__': 'RPG::Event::Page', 'list': rows + [command(0)]}


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.index = self.base / 'index'; self.project = self.base / 'game'
        (self.project / 'Data').mkdir(parents=True)
        (self.project / 'Data/source.rvdata2').write_bytes(b'fixture-not-executed')
        self.write('project.json', {'errors': [], 'map_count': 1, 'script_count': 2, 'database_files_decoded': ['Actors.rvdata2', 'CommonEvents.rvdata2', 'Troops.rvdata2']})
        self.write('manifest.json', {'read_only': True, 'files': [{'path': k, 'sha256': v} for k, v in current_inventory(self.project).items()]})
        self.write('maps/map-001.json', {'__class__': 'RPG::Map', 'display_name': 'Meadow', 'note': '<MapTag: 1>', 'events': {'1': {
            '__class__': 'RPG::Event', 'id': 1, 'name': 'Gate', 'pages': [page([command(108, ['<foo bar: 3>']), command(408, ['<Fo_Bar: 4>']), command(401, ['<ignored: text>'])])]}}})
        self.write('database/common-events.json', [None, {'__class__': 'RPG::CommonEvent', 'id': 1, 'name': 'C', 'trigger': 0, 'list': [command(108, ['<alpha>']), command(0)]}])
        self.write('database/troops.json', [None, {'__class__': 'RPG::Troop', 'id': 1, 'name': 'T', 'pages': [page([command(108, ['<fooo bar: 1>'])])]}])
        self.write('database/actors.json', [None, {'__class__': 'RPG::Actor', 'id': 1, 'name': 'Hero',
                   'note': '<foo bar: 1>\n<strict: 2>\n<STRICT: 3>\n<shared tag>\n<beta>\n<nobody: 9>\n<block>\n</block>'}])
        self.write('scripts/order.json', {'scripts': [{'index': 0, 'path': '000_One.rb'}, {'index': 1, 'path': '001_Two.rb'}]})
        (self.index / 'scripts/000_One.rb').write_text(SCRIPT, encoding='utf-8')
        (self.index / 'scripts/001_Two.rb').write_text(SCRIPT2, encoding='utf-8')

    def write(self, path, value):
        file = self.index / path; file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(value), encoding='utf-8')

    def tag(self, result, key):
        return next(t for t in result['tags'] if t['key'] == key)


class ExtractionTests(Base):
    def test_tag_forms_and_normalization(self):
        tags = nt.extract_tags('<Foo   Bar: 5>\n<flag>\n</flag> <move 3 4> <3> < > text')
        self.assertEqual([(t['name'], t['form']) for t in tags],
                         [('Foo Bar', 'valued'), ('flag', 'bare'), ('flag', 'close'), ('move 3 4', 'args'), ('3', 'bare')])
        self.assertEqual(tags[0]['value'], '5')
        self.assertEqual(nt.canon('Foo_  Bar'), 'foobar')
        self.assertEqual(nt.keys_for(tags[3]), ['move34', 'move3', 'move'])

    def test_note_and_comment_scopes_collected(self):
        found = {(ev['source'], tag['name']) for tag, ev in nt.uses(nt.Index(self.index))}
        self.assertIn(('database', 'foo bar'), found); self.assertIn(('map', 'MapTag'), found)
        self.assertIn(('event_comment', 'foo bar'), found); self.assertIn(('event_comment', 'Fo_Bar'), found)
        self.assertIn(('event_comment', 'alpha'), found); self.assertIn(('event_comment', 'fooo bar'), found)
        self.assertNotIn(('event_comment', 'ignored'), found)  # 401 message text is not a comment


class DerivationTests(unittest.TestCase):
    def test_simple_and_separators(self):
        self.assertEqual(nt.derive(r'<foo[ _]bar:\s*(\d+)>')[0], ['foo bar'])
        self.assertEqual(nt.derive(r'^\s*<hp\s+rate\s*=\s*(\d+)>')[0], ['hp rate'])
        names, closing, partial, opaque = nt.derive(r'<\/block>')
        self.assertEqual((names, closing, opaque), (['block'], True, None))

    def test_alternation_and_optional(self):
        self.assertEqual(nt.derive(r'<(?:FOO|BAR)>')[0], ['BAR', 'FOO'])
        self.assertEqual(nt.derive(r'<(FOO|BAR):\s*(\d+)>')[0], ['BAR', 'FOO'])
        self.assertEqual(nt.derive(r'<foo(?:bar)?>')[0], ['foo', 'foobar'])

    def test_opaque_and_non_tag_patterns(self):
        for pattern in (r'<#{tag}: (\d+)>', r'<(\w+)>', r'<[a-z]+>'):
            names, _, _, opaque = nt.derive(pattern)
            self.assertEqual(names, []); self.assertTrue(opaque)
        self.assertIsNone(nt.derive(r'[\r\n]+'))
        self.assertIsNone(nt.derive(r'(?<name>\d+)'))
        self.assertTrue(nt.derive(r'<foo_#{n}>')[2])  # prefix only

    def test_line_scanning_literals_flags_and_hints(self):
        got = nt.parser_candidates('x = /<a b>/i; y = %r{<c>}m; z = "<d>"')
        self.assertEqual(got, [('regex', '<a b>', 'i'), ('regex', '<c>', 'm')])  # a bare string with no regex hint is ignored
        got = nt.parser_candidates('note.include?("<d>") && Regexp.new("<e:\\\\s*(\\\\d+)>")')
        self.assertEqual([k for k, _, _ in got], ['string', 'string'])
        self.assertEqual(got[1][1], r'<e:\s*(\d+)>')
        self.assertIsNone(nt.derive(nt.parser_candidates('a = b / c < d / e')[0][1]))  # division is not a tag pattern


class RegistryTests(Base):
    def test_cross_reference_classifications(self):
        result = nt.registry(self.index)
        foo = self.tag(result, 'foobar')
        self.assertEqual(foo['status'], 'recognized')
        self.assertEqual({e['source'] for e in foo['evidence']}, {'database', 'event_comment'})
        self.assertEqual(foo['parsers'][0]['script'], '000_One.rb')
        self.assertEqual(self.tag(result, 'nobody')['status'], 'unrecognized')
        self.assertEqual(self.tag(result, 'beta')['status'], 'recognized')
        self.assertEqual(self.tag(result, 'alpha')['status'], 'recognized')
        self.assertEqual(self.tag(result, 'block')['status'], 'unrecognized')
        self.assertEqual(self.tag(result, 'block')['forms'], {'bare': 1, 'close': 1})
        self.assertEqual(self.tag(result, 'maptag')['status'], 'unrecognized')

    def test_typo_suggestion(self):
        typo = self.tag(nt.registry(self.index), 'fooobar')
        self.assertEqual(typo['status'], 'unrecognized')
        self.assertEqual(typo['suggestions'][0]['parser_tag'], 'foo bar')
        self.assertEqual(typo['suggestions'][0]['scripts'], ['000_One.rb'])

    def test_case_mismatch_only_without_ignorecase(self):
        result = nt.registry(self.index)
        strict = self.tag(result, 'strict')
        self.assertEqual(strict['status'], 'recognized')
        self.assertEqual(sorted(strict['case_mismatches']), ['STRICT', 'strict'])
        self.assertEqual(self.tag(result, 'foobar')['case_mismatches'], [])
        self.assertEqual(self.tag(result, 'beta')['case_mismatches'], [])

    def test_shared_unused_and_opaque(self):
        result = nt.registry(self.index)
        shared = self.tag(result, 'sharedtag')
        self.assertEqual(shared['shared_scripts'], ['000_One.rb', '001_Two.rb'])
        self.assertEqual([c['tag'] for c in result['possible_collisions']], ['shared tag'])
        self.assertTrue(result['possible_collisions'][0]['used'])
        self.assertEqual([u['tag'] for u in result['unused_parser_tags']], ['lonely'])
        self.assertEqual(result['counts']['opaque_parsers'], 1)
        self.assertIn('interpolation', result['opaque_parsers'][0]['opaque_reason'])
        self.assertTrue(result['heuristic']); self.assertFalse(result['mutation_authorized'])

    def test_budget_refuses(self):
        with patch.object(nt, 'MAX_PARSERS', 1):
            with self.assertRaises(ValueError): nt.registry(self.index)
        with patch.object(nt, 'MAX_USES', 2):
            with self.assertRaises(ValueError): nt.registry(self.index)


class CliTests(Base):
    def test_outputs_written_and_exit_review(self):
        before = current_inventory(self.project); indexed = current_inventory(self.index)
        out = self.base / 'out'
        code = nt.main([str(self.index), '--project', str(self.project), '--json', str(out / 'n.json'), '--markdown', str(out / 'n.md')])
        self.assertEqual(code, 3)
        report = json.loads((out / 'n.json').read_text(encoding='utf-8'))
        self.assertTrue(report['source_unchanged']); self.assertEqual(report['source_freshness'], 'fresh')
        md = (out / 'n.md').read_text(encoding='utf-8')
        self.assertIn('Unrecognized tags', md); self.assertIn('Heuristic', md)
        self.assertEqual(current_inventory(self.project), before); self.assertEqual(current_inventory(self.index), indexed)

    def test_clean_project_exits_zero(self):
        self.write('database/actors.json', [None]); self.write('database/troops.json', [None]); self.write('database/common-events.json', [None])
        self.write('maps/map-001.json', {'__class__': 'RPG::Map', 'note': '', 'events': {}})
        self.assertEqual(nt.main([str(self.index), '--project', str(self.project)]), 0)

    def test_output_guards_refuse_and_write_nothing(self):
        cases = [self.project / 'r.json', self.project / 'Data' / 'r.md', self.index / 'r.json', self.index / 'scripts' / 'r.md']
        for path in cases:
            with self.subTest(path=path):
                flag = '--markdown' if path.suffix == '.md' else '--json'
                self.assertEqual(nt.main([str(self.index), '--project', str(self.project), flag, str(path)]), 2)
                self.assertFalse(path.exists())
        existing = self.base / 'old.json'; existing.write_text('keep', encoding='utf-8')
        self.assertEqual(nt.main([str(self.index), '--project', str(self.project), '--json', str(existing)]), 2)
        self.assertEqual(existing.read_text(encoding='utf-8'), 'keep')
        same = self.base / 'same.out'
        self.assertEqual(nt.main([str(self.index), '--project', str(self.project), '--json', str(same), '--markdown', str(same)]), 2)
        self.assertFalse(same.exists())

    def test_stale_index_refused(self):
        (self.project / 'Data/source.rvdata2').write_bytes(b'changed')
        out = self.base / 'stale.json'
        self.assertEqual(nt.main([str(self.index), '--project', str(self.project), '--json', str(out)]), 2)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
