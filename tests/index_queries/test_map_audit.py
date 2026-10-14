import copy
import json
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from vxace_copy_patcher import current_inventory
from vxace_index_query import Index
from vxace_map_audit import audit, main, tile_info, tile_passage


def native_table(dimensions, sizes, values):
    return {'__class__': 'Table', 'dimensions': dimensions,
            **dict(zip(('xsize', 'ysize', 'zsize'), sizes)), 'data': values}


class MapAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.index = self.base / 'index'; self.game = self.base / 'game'
        (self.game / 'Data').mkdir(parents=True)
        (self.game / 'Data/Map001.rvdata2').write_bytes(b'hashed fixture only, never deserialized')
        self.write('project.json', {'errors': [], 'map_count': 1, 'database_files_decoded': ['Tilesets.rvdata2']})
        self.write('manifest.json', {'read_only': True, 'files': [{'path': k, 'sha256': v}
                   for k, v in current_inventory(self.game).items()]})
        self.flags = [0] * 8192; self.flags[0] = 16; self.flags[1] = 15; self.flags[128] = 16
        self.ts = [None, {'__class__': 'RPG::Tileset', 'id': 1, 'name': 'Synthetic Exterior',
                   'tileset_names': ['A1', 'A2', 'A3', 'A4', 'A5', 'B', 'C', 'D', 'E'],
                   'flags': native_table(1, (8192, 1, 1), self.flags)}]
        self.m = {'__class__': 'RPG::Map', 'width': 2, 'height': 2, 'tileset_id': 1, 'events': {},
                  'data': native_table(3, (2, 2, 4), [1552] * 4 + [0] * 4 + [0, 1, 128, 0] + [0, 0x701, 0, 0])}
        self.sync()

    def write(self, name, obj):
        target = self.index / name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(obj), encoding='utf-8')

    def sync(self):
        self.write('database/tilesets.json', self.ts); self.write('maps/map-001.json', self.m)

    def test_native_sheet_coordinates_across_halves_and_boundaries(self):
        # Independent known atlas positions, including right-half first cell.
        for tid, sheet, col, row in ((0, 'B', 0, 0), (127, 'B', 7, 15), (128, 'B', 8, 0),
              (255, 'B', 15, 15), (256, 'C', 0, 0), (768, 'E', 0, 0),
              (1536, 'A5', 0, 0), (1552, 'A5', 0, 2)):
            with self.subTest(tid=tid):
                value = tile_info(tid)
                self.assertEqual((value['sheet'], value['column'], value['row']), (sheet, col, row))

    def test_autotile_boundaries_and_shape_are_distinct_from_regular_cells(self):
        for tid, sheet, kind, shape in ((2048, 'A1', 0, 0), (2815, 'A1', 15, 47),
                (2816, 'A2', 0, 0), (4351, 'A2', 31, 47), (4352, 'A3', 0, 0),
                (5888, 'A4', 0, 0), (8191, 'A4', 47, 47)):
            v = tile_info(tid)
            self.assertEqual((v['sheet'], v['kind_on_sheet'], v['shape']), (sheet, kind, shape))
            self.assertNotIn('column', v)

    def test_native_layer_order_star_skip_and_direction_flags(self):
        self.flags[2] = 1; self.flags[3] = 16 | 15
        self.assertEqual(tile_passage([1552, 0, 1], self.flags), dict.fromkeys(('down', 'left', 'right', 'up'), False))
        self.assertEqual(tile_passage([1552, 0, 3], self.flags), dict.fromkeys(('down', 'left', 'right', 'up'), True))
        self.assertEqual(tile_passage([1552, 1, 2], self.flags), {'down': False, 'left': True, 'right': True, 'up': True})
        self.assertFalse(any(tile_passage([0, 0, 0], self.flags).values()))

    def test_gap_is_uncertain_instead_of_silently_passable(self):
        self.assertTrue(tile_info(1024)['unsupported_gap'])
        self.assertTrue(all(x is None for x in tile_passage([1552, 0, 1024], self.flags).values()))
        self.m['data']['data'][8] = 1024; self.sync()
        r = audit(self.index, 1, (0, 0))
        self.assertEqual(r['findings'][0]['code'], 'unsupported_tile_id')

    def test_xy_plane_layout_regions_and_shadow_are_read_independently(self):
        r = audit(self.index, 1, (1, 0)); m = r['maps'][0]
        self.assertEqual(m['cell']['layers_bottom_to_top'], [1552, 0, 1])
        self.assertEqual((m['cell']['region'], m['cell']['shadow_bits']), (7, 1))
        self.assertEqual(m['regions'], {'0': 3, '7': 1}); self.assertEqual(m['shadow_cells'], 1)
        self.assertFalse(r['mutation_authorized'])
        self.assertTrue(any('runtime' in x.lower() for x in r['limits']))

    def test_cli_preserves_source_and_index_and_requires_freshness(self):
        before = (current_inventory(self.game), current_inventory(self.index))
        output = self.base / 'report'
        self.assertEqual(main([str(self.index), '--project', str(self.game), '--output', str(output), '--map', '1', '--cell', '1', '0']), 0)
        r = json.loads((output / 'map-audit.json').read_text())
        self.assertTrue(r['source_unchanged']); self.assertTrue(r['read_index_files_unchanged'])
        self.assertEqual(before, (current_inventory(self.game), current_inventory(self.index)))
        (self.game / 'Data/Map001.rvdata2').write_bytes(b'changed')
        refused = self.base / 'stale'
        self.assertEqual(main([str(self.index), '--project', str(self.game), '--output', str(refused)]), 2)
        self.assertFalse(refused.exists())

    def test_report_inside_input_and_existing_output_are_refused(self):
        for output in (self.game / 'report', self.index / 'report', self.base):
            with self.subTest(output=output):
                self.assertEqual(main([str(self.index), '--project', str(self.game), '--output', str(output)]), 2)

    def test_invalid_selection_is_refused(self):
        for mid, cell in ((True, None), (0, None), (99, None), (None, [0, 0]), (1, [-1, 0]),
                          (1, [2, 0]), (1, [True, 0]), (1, [0]), (1, [0, 0, 0])):
            with self.subTest(mid=mid, cell=cell), self.assertRaises(ValueError):
                audit(self.index, mid, cell)

    def test_malformed_and_oversized_tables_are_refused(self):
        original = copy.deepcopy(self.m)
        cases = [('width', True), ('tileset_id', 99)]
        for key, value in cases:
            self.m = copy.deepcopy(original); self.m[key] = value; self.sync()
            with self.assertRaises(ValueError): audit(self.index)
        for field, value in (('xsize', 3), ('dimensions', 2), ('data', [0]),
                             ('data', [-1] * 16), ('data', [True] * 16), ('data', [8192] * 16)):
            self.m = copy.deepcopy(original); self.m['data'][field] = value; self.sync()
            with self.subTest(field=field), self.assertRaises(ValueError): audit(self.index)

    def test_tileset_identity_flags_and_sheet_names_are_validated(self):
        original = copy.deepcopy(self.ts)
        for key, value in (('id', 2), ('tileset_names', ['B']), ('flags', {'__class__': 'Opaque'})):
            self.ts = copy.deepcopy(original); self.ts[1][key] = value; self.sync()
            with self.assertRaises(ValueError): audit(self.index)

    def test_missing_sheet_produces_review_without_asset_existence_claim(self):
        self.ts[1]['tileset_names'][4] = ''; self.sync()
        result = audit(self.index)
        self.assertEqual(result['findings'][0]['code'], 'empty_tileset_sheet')
        self.assertTrue(any('image existence' in x for x in result['limits']))

    def test_walk_budget_and_changing_input_refuse_complete_result(self):
        with patch('vxace_index_query.MAX_STEPS', 20), self.assertRaises(ValueError): audit(self.index)
        data = Index(self.index)
        original = data.unchanged
        def changed():
            (self.index / 'maps/map-001.json').write_text('{}', encoding='utf-8')
            original()
        data.unchanged = changed
        with self.assertRaises(ValueError): audit(data)

    @unittest.skipUnless(shutil.which('ruby'), 'Ruby needed for independent reader integration')
    def test_independent_ruby_reader_produces_accepted_native_tables(self):
        project = self.base / 'ruby-game'; index = self.base / 'ruby-index'
        subprocess.run(['ruby', str(Path(__file__).with_name('make_map_fixture.rb')), str(project)], check=True)
        before = current_inventory(project)
        proc = subprocess.run([sys.executable, str(ROOT / 'tools/vxace_project_reader.py'),
                               str(project), '--output', str(index), '--ruby', shutil.which('ruby')],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(main([str(index), '--project', str(project), '--output', str(self.base / 'ruby-report'),
                               '--map', '1', '--cell', '1', '0']), 0)
        result = json.loads((self.base / 'ruby-report/map-audit.json').read_text())
        self.assertEqual(result['maps'][0]['cell']['layers_bottom_to_top'], [1552, 0, 1])
        self.assertEqual(result['maps'][0]['cell']['region'], 7)
        self.assertFalse(any(result['maps'][0]['cell']['static_tile_passage_only'].values()))
        self.assertEqual(before, current_inventory(project))


if __name__ == '__main__':
    unittest.main()
