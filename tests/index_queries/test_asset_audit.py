import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from vxace_asset_audit import audit, catalog, main, safe_name
from vxace_copy_patcher import current_inventory
from vxace_index_query import Index


class AssetAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.index = self.base / 'index'; self.game = self.base / 'game'; self.rtp = self.base / 'rtp'
        (self.game / 'Data').mkdir(parents=True); (self.rtp / 'Graphics').mkdir(parents=True)
        (self.game / 'Data/Actors.rvdata2').write_bytes(b'hashed source fixture, never executed')
        self.write('project.json', {'errors': [], 'map_count': 0, 'database_files_decoded': ['Actors.rvdata2']})
        self.actors = [None, {'__class__': 'RPG::Actor', 'character_name': 'Hero', 'face_name': ''}]
        self.write('database/actors.json', self.actors)
        (self.index / 'maps').mkdir()
        self.refresh()

    def write(self, name, value):
        file = self.index / name; file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(value), encoding='utf-8')

    def refresh(self):
        self.write('manifest.json', {'read_only': True, 'files': [{'path': k, 'sha256': v}
                   for k, v in current_inventory(self.game).items()]})

    def asset(self, root, relative):
        file = root / relative; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(b'presence fixture, not decoded')
        self.refresh(); return file

    def test_missing_rtp_is_uncertain_and_supplied_rtp_makes_absence_missing(self):
        self.assertEqual(audit(self.index, self.game)['counts'], {'unresolved_without_rtp': 1})
        self.assertEqual(audit(self.index, self.game, self.rtp)['counts'], {'missing': 1})

    def test_project_assets_take_precedence_over_rtp(self):
        self.asset(self.game, 'Graphics/Characters/Hero.png'); self.asset(self.rtp, 'Graphics/Characters/Hero.png')
        row = audit(self.index, self.game, self.rtp)['references'][0]
        self.assertEqual(row['status'], 'found'); self.assertEqual(row['matches'], [{'source': 'project', 'path': 'Graphics/Characters/Hero.png'}])

    def test_explicit_rtp_resolves_missing_project_asset(self):
        self.asset(self.rtp, 'Graphics/Characters/Hero.png')
        result = audit(self.index, self.game, self.rtp)
        self.assertEqual(result['counts'], {'found': 1}); self.assertTrue(result['asset_names_and_metadata_unchanged'])

    def test_file_folder_and_extension_case_mismatches_are_reported(self):
        for i, relative in enumerate(('graphics/Characters/Hero.png', 'Graphics/characters/Hero.png', 'Graphics/Characters/hero.png', 'Graphics/Characters/Hero.PNG')):
            with self.subTest(relative=relative):
                rtp = self.base / ('case-rtp-' + str(i)); rtp.mkdir()
                self.asset(rtp, relative)
                self.assertEqual(audit(self.index, self.game, rtp)['counts'], {'case_mismatch': 1})

    def test_rtp_text_sidecars_are_not_competing_graphics(self):
        self.asset(self.rtp, 'Graphics/Characters/Hero.png'); self.asset(self.rtp, 'Graphics/Characters/Hero.txt')
        result = audit(self.index, self.game, self.rtp)
        self.assertEqual(result['counts'], {'found': 1})
        self.assertEqual(len(result['references'][0]['matches']), 1)

    def test_project_case_mismatch_is_not_hidden_by_exact_rtp_match(self):
        self.asset(self.game, 'Graphics/Characters/hero.png'); self.asset(self.rtp, 'Graphics/Characters/Hero.png')
        row = audit(self.index, self.game, self.rtp)['references'][0]
        self.assertEqual(row['status'], 'case_mismatch'); self.assertEqual(row['matches'][0]['source'], 'project')

    def test_multiple_extensions_remain_ambiguous(self):
        self.asset(self.rtp, 'Graphics/Characters/Hero.png'); self.asset(self.rtp, 'Graphics/Characters/Hero.jpg')
        self.assertEqual(audit(self.index, self.game, self.rtp)['counts'], {'ambiguous': 1})

    def test_unknown_format_is_not_claimed_playable(self):
        self.asset(self.rtp, 'Graphics/Characters/Hero.webp')
        self.assertEqual(audit(self.index, self.game, self.rtp)['counts'], {'unverified_extension': 1})

    def test_nested_dotted_and_explicit_extension_names(self):
        for name, relative in (('sets/Hero.v2', 'Graphics/Characters/sets/Hero.v2.png'),
                               ('Hero.png', 'Graphics/Characters/Hero.png')):
            self.actors[1]['character_name'] = name; self.write('database/actors.json', self.actors)
            self.asset(self.rtp, relative)
            self.assertEqual(audit(self.index, self.game, self.rtp)['counts'], {'found': 1})

    def test_unsafe_and_opaque_references_do_not_resolve_outside_assets(self):
        for name in ('../secret', '/absolute', 'C:/secret', 'a\\..\\secret', 'a\nb', 'a//b', {'__bytes__': 'opaque'}):
            with self.subTest(name=name):
                self.actors[1]['character_name'] = name; self.write('database/actors.json', self.actors)
                row = audit(self.index, self.game, self.rtp)['references'][0]
                self.assertIn(row['status'], ('unsafe_reference', 'opaque_reference')); self.assertFalse(row['matches'])

    def test_event_move_route_audio_and_database_refs_have_exact_evidence(self):
        self.write('database/actors.json', [])
        obj = {'__class__': 'RPG::Map', 'parallax_name': 'Sky', 'events': {'1': {'pages': [{'list': [
               {'__class__': 'RPG::EventCommand', 'code': 101, 'parameters': ['Face', 0, 0, 2]},
               {'__class__': 'RPG::EventCommand', 'code': 231, 'parameters': [1, 'Portrait', 0]},
               {'__class__': 'RPG::MoveCommand', 'code': 41, 'parameters': ['Hero', 0]},
               {'__class__': 'RPG::BGM', 'name': 'Theme', 'volume': 100}]}]}}}
        self.write('maps/map-001.json', obj); self.write('project.json', {'errors': [], 'map_count': 1, 'database_files_decoded': ['Actors.rvdata2']})
        result = audit(self.index, self.game, self.rtp)
        self.assertEqual({(x['folder'], x['name']) for x in result['references']}, {
            ('Graphics/Parallaxes', 'Sky'), ('Graphics/Faces', 'Face'), ('Graphics/Pictures', 'Portrait'),
            ('Graphics/Characters', 'Hero'), ('Audio/BGM', 'Theme')})
        face = next(x for x in result['references'] if x['name'] == 'Face')
        self.assertEqual(face['evidence'][0], {'file': 'maps/map-001.json', 'path': ['events', '1', 'pages', 0, 'list', 0, 'parameters', 0]})

    def test_duplicate_references_have_counts_and_bounded_evidence(self):
        self.write('database/actors.json', [self.actors[1]] * 9)
        row = audit(self.index, self.game)['references'][0]
        self.assertEqual(row['reference_count'], 9); self.assertEqual(len(row['evidence']), 3)

    def test_cli_integrity_stale_refusal_and_external_output(self):
        self.asset(self.rtp, 'Graphics/Characters/Hero.png')
        before = (current_inventory(self.game), current_inventory(self.index), current_inventory(self.rtp))
        output = self.base / 'report'
        args = [str(self.index), '--project', str(self.game), '--rtp', str(self.rtp), '--output', str(output)]
        self.assertEqual(main(args), 0)
        self.assertEqual(before, (current_inventory(self.game), current_inventory(self.index), current_inventory(self.rtp)))
        self.assertEqual(main(args), 2)
        (self.game / 'Data/Actors.rvdata2').write_bytes(b'changed')
        args[-1] = str(self.base / 'stale'); self.assertEqual(main(args), 2); self.assertFalse(Path(args[-1]).exists())

    def test_budgets_and_asset_metadata_change_refuse_complete_results(self):
        self.asset(self.rtp, 'Graphics/Characters/Hero.png')
        with patch('vxace_asset_audit.MAX_ASSET_FILES', 1), self.assertRaises(ValueError):
            audit(self.index, self.game, self.rtp)
        with patch('vxace_asset_audit.MAX_REFERENCES', 0), self.assertRaises(ValueError):
            audit(self.index, self.game, self.rtp)
        data = Index(self.index)
        def change():
            (self.rtp / 'Graphics/Characters/Hero.png').write_bytes(b'changed metadata size')
        data.unchanged = change
        with self.assertRaisesRegex(ValueError, 'metadata changed'): audit(data, self.game, self.rtp)

    def test_rtp_roots_cannot_overlap_project(self):
        for rtp in (self.game, self.game / 'Data', self.game.parent):
            with self.subTest(rtp=rtp), self.assertRaises(ValueError): audit(self.index, self.game, rtp)

    def test_wrong_rtp_directory_does_not_produce_mass_missing_errors(self):
        wrong = self.base / 'not-rtp'; wrong.mkdir()
        with self.assertRaisesRegex(ValueError, 'Graphics/ or Audio/'):
            audit(self.index, self.game, wrong)

    def test_reports_cannot_write_inside_the_read_only_rtp_root(self):
        self.asset(self.rtp, 'Graphics/Characters/Hero.png')
        before = current_inventory(self.rtp)
        for output in (self.rtp / 'report', self.rtp / 'Graphics/report'):
            args = [str(self.index), '--project', str(self.game), '--rtp', str(self.rtp), '--output', str(output)]
            self.assertEqual(main(args), 2); self.assertFalse(output.exists())
        self.assertEqual(before, current_inventory(self.rtp))

    def test_linked_asset_cannot_escape_catalog_root(self):
        target = self.base / 'outside.png'; target.write_bytes(b'outside')
        link = self.rtp / 'Graphics/Characters/Hero.png'; link.parent.mkdir()
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest('Link creation requires platform privileges')
        with self.assertRaisesRegex(ValueError, 'Linked'):
            audit(self.index, self.game, self.rtp)

    def test_malformed_recognized_event_parameters_are_refused(self):
        self.write('database/actors.json', [{'__class__': 'RPG::EventCommand', 'code': 322, 'parameters': [1]}])
        with self.assertRaises(ValueError): audit(self.index, self.game)


if __name__ == '__main__':
    unittest.main()
