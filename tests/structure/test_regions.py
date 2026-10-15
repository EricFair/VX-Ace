import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import vxace_map_regions as regions
import vxace_python_mutator as backend
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject, Table, RubyUserDef


def fixture():
    table = Table(3, 2, 4, dim=3, data=list(range(18)) + [0x701, 0x123f, 0xffa5, 0, 1, 15])
    root = RubyObject('RPG::Map', {'@width': 3, '@height': 2, '@data': table,
                                 '@fixture_alias': table, '@opaque': RubyUserDef('PrivateOpaque', b'\xff\x00')})
    return root


def mutation(root, cells=None):
    return {'action': 'set_regions', 'expected_table_sha256': regions.fingerprint(regions.table_for(root)),
            'cells': cells if cells is not None else [{'x': 0, 'y': 0, 'expected_region': 7, 'value': 63}]}


class RegionUnitTests(unittest.TestCase):
    def test_region_change_preserves_tiles_all_lower_bits_and_unknown_alias(self):
        root = fixture(); original = root.get('data'); before = original.to_payload()
        backend.apply(root, {'type': 'map_region', 'mutation': mutation(root)})
        changed = root.get('data')
        self.assertEqual(changed.data[18], 0x3f01)
        self.assertEqual(changed.data[:18], original.data[:18])
        self.assertEqual(changed.data[19:], original.data[19:])
        self.assertEqual(root.get('fixture_alias').to_payload(), before)
        self.assertIsNot(changed, root.get('fixture_alias'))
        self.assertEqual(root.get('opaque').payload, b'\xff\x00')

    def test_editor_regions_zero_and_63_preserve_reserved_bits(self):
        root = fixture()
        cells = [{'x': 1, 'y': 0, 'expected_region': 18, 'value': 0},
                 {'x': 0, 'y': 1, 'expected_region': 0, 'value': 63}]
        regions.apply(root, mutation(root, cells))
        self.assertEqual(root.get('data').data[19], 0x003f)
        self.assertEqual(root.get('data').data[21], 0x3f00)

    def test_exact_native_payload_hash_and_per_cell_precondition_are_required(self):
        for field, value in (('expected_table_sha256', '0'*64), ('expected_table_sha256', None), ('action', 'paint_tiles')):
            root = fixture(); spec = mutation(root); spec[field] = value; before = marshal_rb.dump(root)
            with self.assertRaises(ValueError): regions.apply(root, spec)
            self.assertEqual(marshal_rb.dump(root), before)
        root = fixture(); spec = mutation(root); spec['cells'][0]['expected_region'] = 8
        with self.assertRaisesRegex(ValueError, 'precondition'): regions.apply(root, spec)

    def test_graphics_or_shadow_change_makes_full_table_fingerprint_stale(self):
        for pos in (0, 18):
            root = fixture(); spec = mutation(root); root.get('data').data[pos] ^= 1
            with self.assertRaisesRegex(ValueError, 'fingerprint'): regions.apply(root, spec)

    def test_duplicate_noop_invalid_type_bounds_and_unknown_fields_refuse_atomically(self):
        bad = [[{'x': 0, 'y': 0, 'expected_region': 7, 'value': 7}],
               [{'x': 0, 'y': 0, 'expected_region': 7, 'value': True}],
               [{'x': 0, 'y': 0, 'expected_region': 7, 'value': 64}],
               [{'x': 2, 'y': 0, 'expected_region': 255, 'value': 1}],
               [{'x': 0, 'y': 0, 'expected_region': -1, 'value': 1}],
               [{'x': 3, 'y': 0, 'expected_region': 0, 'value': 1}],
               [{'x': 0, 'y': 2, 'expected_region': 0, 'value': 1}],
               [{'x': True, 'y': 0, 'expected_region': 0, 'value': 1}],
               [{'x': 0, 'y': 0, 'expected_region': 7, 'value': 1, 'shadow': 15}], [], 'cells']
        good = {'x': 0, 'y': 0, 'expected_region': 7, 'value': 1}
        bad += [[good, good], [good]*257, [good, {'x': 2, 'y': 0, 'expected_region': 2, 'value': 3}]]
        for cells in bad:
            root = fixture(); before = marshal_rb.dump(root)
            with self.subTest(cells=str(cells)[:100]), self.assertRaises(ValueError): regions.apply(root, mutation(root, cells))
            self.assertEqual(marshal_rb.dump(root), before)
        root = fixture(); spec = mutation(root); spec['width'] = 10
        with self.assertRaises(ValueError): regions.apply(root, spec)

    def test_non_native_wrong_layers_shapes_and_oversized_maps_are_refused(self):
        for root in ([], RubyObject('CustomMap', {}), RubyObject('RPG::Map', {'@width': 501, '@height': 1}),
                     RubyObject('RPG::Map', {'@width': True, '@height': 2}),
                     RubyObject('RPG::Map', {'@width': 3, '@height': 2, '@data': Table(3,2,3,dim=3)})):
            with self.subTest(root=root), self.assertRaises(ValueError): regions.table_for(root)

    def test_snapshot_exact_metadata_and_bounded_unique_cells(self):
        root = fixture(); snap = regions.snapshot(root, [{'x': 2, 'y': 0}])
        self.assertEqual(snap['cells'], [{'x': 2, 'y': 0, 'region': 255, 'lower_metadata_byte': 165}])
        self.assertEqual(snap['region_counts'], {0:3,7:1,18:1,255:1})
        with self.assertRaises(ValueError): regions.snapshot(root, [{'x': 2, 'y': 0, 'value': 1}])

    def test_mutated_map_roundtrips_through_pinned_codec_and_preserves_unknowns(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'map.rvdata2'; output = Path(tmp) / 'new.rvdata2'
            root = fixture(); source.write_bytes(marshal_rb.dump(root)); original = source.read_bytes()
            loaded, _ = backend.load(source)
            regions.apply(loaded, mutation(loaded)); backend.write(loaded, output)
            final, raw = backend.load(output)
            self.assertEqual(final.get('data').data[18], 0x3f01)
            self.assertEqual(final.get('fixture_alias').data[18], 0x701)
            self.assertEqual(source.read_bytes(), original)

    def test_candidate_postcondition_rejects_unapproved_tile_shadow_region_or_field_changes(self):
        before=fixture(); spec=mutation(before)
        for tamper in ('tile','shadow','other_region','field'):
            candidate=marshal_rb.load(marshal_rb.dump(before)); regions.apply(candidate,spec)
            regions.verify_transition(before,candidate,spec)
            if tamper=='tile': candidate.get('data').data[0]^=1
            elif tamper=='shadow': candidate.get('data').data[18]^=1
            elif tamper=='other_region': candidate.get('data').data[19]^=0x100
            else: candidate.set('width',4)
            with self.subTest(tamper=tamper), self.assertRaises(ValueError): regions.verify_transition(before,candidate,spec)


@unittest.skipUnless(shutil.which('ruby'), 'Ruby required for independent native-map fixture/extraction')
class RegionCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.game=self.base/'game'; self.index=self.base/'index'
        subprocess.run(['ruby',str(ROOT/'tests/project_reader/make_fixture.rb'),str(self.game)],check=True,capture_output=True)
        # Extend the independently Ruby-marshalled baseline with original,
        # standard map Table/tileset/encounter fields for this guarded subset.
        ruby = '''class Table
  def initialize(x,y,z,values); @x,@y,@z,@values=x,y,z,values; end
  def _dump(_); [3,@x,@y,@z,@values.size].pack('V5')+@values.pack('v*'); end
  def self._load(raw); dim,x,y,z,n=raw.unpack('V5'); new(x,y,z,raw[20..-1].unpack('v*')); end
end
module RPG; class Tileset; end; class Map; class Encounter; end; end; end
mapfile=ARGV[0]+'/Data/Map001.rvdata2'
map=Marshal.load(File.binread(mapfile))
map.instance_variable_set(:@width,3); map.instance_variable_set(:@height,2)
map.instance_variable_set(:@data,Table.new(3,2,4,[1552]*6+[0]*12+[0x701,0,0,0,0,0]))
map.instance_variable_set(:@tileset_id,1)
enc=RPG::Map::Encounter.new
enc.instance_variable_set(:@troop_id,1);enc.instance_variable_set(:@weight,10);enc.instance_variable_set(:@region_set,[7])
map.instance_variable_set(:@encounter_list,[enc])
File.binwrite(mapfile,Marshal.dump(map))
tileset=RPG::Tileset.new
tileset.instance_variable_set(:@id,1);tileset.instance_variable_set(:@name,'Region fixture')
tileset.instance_variable_set(:@tileset_names,['','','','','A5','B','','',''])
flags=Table.new(8192,1,1,[0]*8192)
def flags._dump(_); [1,8192,1,1,8192].pack('V5')+([0]*8192).pack('v*'); end
tileset.instance_variable_set(:@flags,flags)
File.binwrite(ARGV[0]+'/Data/Tilesets.rvdata2',Marshal.dump([nil,tileset]))
system=Marshal.load(File.binread(ARGV[0]+'/Data/System.rvdata2'))
system.instance_variable_set(:@version_id,42)
File.binwrite(ARGV[0]+'/Data/System.rvdata2',Marshal.dump(system))
'''
        # Load original fixture class definitions without rewriting the fixture.
        fixture_source=(ROOT/'tests/project_reader/make_fixture.rb').read_text()
        class_source='module RPG'+fixture_source.split('module RPG',1)[1].split('actor =',1)[0]
        script=self.base/'extend.rb'; script.write_text(class_source+'\n'+ruby,encoding='utf-8')
        result=subprocess.run(['ruby',str(script),str(self.game)],capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stderr)
        result=subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stderr)
        self.root,_=backend.load(self.game/'Data/Map001.rvdata2')
        self.spec={'changes':[{'kind':'map_region','locator':{'map_id':1},'proposal':'Original region fixture edit',
                              'mutation':mutation(self.root)}]}
        self.specfile=self.base/'spec.json';self.specfile.write_text(json.dumps(self.spec))

    def stage(self, backend_name='python', extra=()):
        return subprocess.run([sys.executable,str(ROOT/'tools/vxace_copy_patcher.py'),str(self.index),
              '--project',str(self.game),'--spec',str(self.specfile),'--copy',str(self.base/'copy'),
              '--audit',str(self.base/'audit'),'--backend',backend_name,*extra],capture_output=True,text=True)

    def test_guarded_region_copy_impact_reload_version_and_postgates(self):
        from vxace_copy_patcher import current_inventory
        before=current_inventory(self.game); result=self.stage()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(current_inventory(self.game),before)
        root,_=backend.load(self.base/'copy/Data/Map001.rvdata2')
        self.assertEqual(root.get('data').data[18],0x3f01)
        system,_=backend.load(self.base/'copy/Data/System.rvdata2')
        self.assertEqual(system.get('version_id'),43)
        audit=json.loads((self.base/'audit/audit.json').read_text())
        self.assertEqual(len(audit['changes']),2)
        self.assertEqual(audit['changes'][0]['regions']['before']['cells'][0]['region'],7)
        self.assertEqual(audit['changes'][0]['regions']['after']['cells'][0]['region'],63)
        self.assertTrue((self.base/'audit/post-validation/validation.json').is_file())
        self.assertTrue((self.base/'audit/post-map-audit.json').is_file())
        impact=json.loads((self.base/'audit/structural-impact.json').read_text())
        self.assertEqual(impact['impacts'][0]['encounters'][0]['region_set'],[7])

    def test_region_copy_refuses_ruby_backend_no_reindex_duplicate_map_and_stale_precondition(self):
        for backend_name,extra in (('ruby',()),('python',('--no-reindex',))):
            result=self.stage(backend_name,extra)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertFalse((self.base/'copy').exists())
            self.assertFalse((self.base/'audit').exists())
        self.spec['changes']*=2;self.specfile.write_text(json.dumps(self.spec))
        self.assertNotEqual(self.stage().returncode,0)
        self.spec['changes']=self.spec['changes'][:1]
        self.spec['changes'][0]['mutation']['expected_table_sha256']='0'*64
        self.specfile.write_text(json.dumps(self.spec))
        self.assertNotEqual(self.stage().returncode,0)
        self.assertFalse((self.base/'copy').exists())

    def test_region_snapshot_cli_native_index_agreement_and_output_safety(self):
        before=(self.game/'Data/Map001.rvdata2').read_bytes()
        output=self.base/'snapshot'
        args=[str(self.index),'--project',str(self.game),'--map','1','--cell','0','0','--output',str(output)]
        self.assertEqual(regions.main(args),0)
        result=json.loads((output/'region-snapshot.json').read_text())
        self.assertEqual(result['cells'][0]['region'],7)
        self.assertEqual(result['table_sha256'],regions.fingerprint(self.root.get('data')))
        self.assertEqual((self.game/'Data/Map001.rvdata2').read_bytes(),before)
        args[-1]=str(self.game/'report')
        self.assertEqual(regions.main(args),2)
        self.assertFalse((self.game/'report').exists())

    def test_region_failure_after_apply_rolls_back_the_whole_copy(self):
        import vxace_copy_patcher as patcher
        before=patcher.current_inventory(self.game)
        original=patcher.run
        def fail_reader(command, **kwargs):
            if len(command)>1 and Path(command[1]).name=='vxace_project_reader.py':
                return subprocess.CompletedProcess(command,1,'','injected post-copy extraction failure')
            return original(command,**kwargs)
        with patch.object(patcher,'run',side_effect=fail_reader), self.assertRaisesRegex(RuntimeError,'re-index failed'):
            patcher.build(self.index,self.game,self.specfile,self.base/'copy',self.base/'audit',shutil.which('ruby'),
                          ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')
        self.assertFalse((self.base/'copy').exists())
        failure=json.loads((self.base/'audit/failure.json').read_text())
        self.assertTrue(failure['staged_copy_removed'])
        self.assertEqual(patcher.current_inventory(self.game),before)

    def test_mixed_region_and_event_structure_advances_version_once(self):
        import vxace_event_structure as structure
        # Prepare an independent source/index with a valid native root list.
        source=self.game/'Data/Map001.rvdata2'
        root,_=backend.load(source)
        page=root.get('events').get(1).get('pages')[0]
        page.set('trigger',0)
        page.set('list',[RubyObject('RPG::EventCommand',{'@code':0,'@indent':0,'@parameters':[]})])
        backend.write(root,source)
        index=self.base/'mixed-index'
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(index)],check=True,capture_output=True)
        self.index=index
        snap=structure.snapshot(root,{'scope':'map','event_id':1,'page':1},backend.object_by_id)
        self.spec['changes'].append({'kind':'event','locator':{'map_id':1,'event_id':1,'page':1,'command_index':0},
              'mutation':{'action':'insert_commands','expected_list_sha256':snap['list_sha256'],
                          'commands':[{'code':230,'indent':0,'parameters':[1]}]}})
        self.specfile.write_text(json.dumps(self.spec))
        result=self.stage()
        self.assertEqual(result.returncode,0,result.stderr)
        system,_=backend.load(self.base/'copy/Data/System.rvdata2')
        self.assertEqual(system.get('version_id'),43)
        final,_=backend.load(self.base/'copy/Data/Map001.rvdata2')
        self.assertEqual(final.get('data').data[18],0x3f01)
        self.assertEqual(final.get('events').get(1).get('pages')[0].get('list')[0].get('code'),230)


if __name__ == '__main__':
    unittest.main()
