import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_upper_tiles as upper
import vxace_python_mutator as backend
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject,Table


def png(width=512,height=512):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\0'*(width*4))*height))+chunk(b'IEND',b'')


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native map fixture')
class UpperTileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.game=self.base/'game';self.index=self.base/'index';self.specfile=self.base/'spec.json'
        subprocess.run(['ruby',str(ROOT/'tests/project_reader/make_fixture.rb'),str(self.game)],check=True,capture_output=True)
        root,_=backend.load(self.game/'Data/Map001.rvdata2');root.set('tileset_id',1)
        root.get('data').data[300]=0x1aff
        (self.game/'Data/Map001.rvdata2').write_bytes(marshal_rb.dump(root));self.before=root
        flags=[0]*8192;flags[0]=0x10;flags[1]=15;flags[8]=0
        names=[backend.convert('') for _ in range(9)];names[5]=backend.convert('Fixture_B')
        self.tileset=RubyObject('RPG::Tileset',{'@id':1,'@name':backend.convert('Authored'), '@mode':0,
                    '@note':backend.convert(''),'@tileset_names':names,'@flags':Table(8192,1,1,dim=1,data=flags)})
        (self.game/'Data/Tilesets.rvdata2').write_bytes(marshal_rb.dump([None,self.tileset]))
        system,_=backend.load(self.game/'Data/System.rvdata2');system.set('version_id',10)
        (self.game/'Data/System.rvdata2').write_bytes(marshal_rb.dump(system))
        troops,_=backend.load(self.game/'Data/Troops.rvdata2')
        for troop in troops:
            if troop is not None:troop.set('pages',[])
        (self.game/'Data/Troops.rvdata2').write_bytes(marshal_rb.dump(troops))
        self.image=self.game/'Graphics/Tilesets/Fixture_B.png';self.image.parent.mkdir(parents=True);self.image.write_bytes(png())
        self.read()
        snap=upper.snapshot(self.before,self.game,[{'x':1,'y':1}],[1,8])
        self.mutation={'action':'paint_upper_tiles','expected_table_sha256':snap['table_sha256'],
                       'expected_tileset_sha256':snap['tileset_sha256'],'expected_assets':snap['assets'],
                       'cells':[{'x':1,'y':1,'expected_tile':0,'value':1},{'x':2,'y':1,'expected_tile':0,'value':8}]}
        self.spec={'changes':[{'kind':'map_tile','locator':{'map_id':1},'proposal':'Paint two authored upper tiles.','mutation':self.mutation}]}
        self.specfile.write_text(json.dumps(self.spec))

    def read(self):
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)

    def stage(self,backend_name='python',extra=()):
        return subprocess.run([sys.executable,str(ROOT/'tools/vxace_copy_patcher.py'),str(self.index),'--project',str(self.game),
                               '--spec',str(self.specfile),'--copy',str(self.base/'copy'),'--audit',str(self.base/'audit'),
                               '--backend',backend_name,*extra],capture_output=True,text=True)

    def test_native_upper_words_only_preserve_ground_metadata_and_unknown_alias(self):
        root=marshal_rb.load(marshal_rb.dump(self.before));root.set('unknown_alias',root.get('data'))
        old=marshal_rb.load(marshal_rb.dump(root));payload=root.get('data').to_payload()
        upper.apply(root,self.mutation,self.game);upper.verify_transition(old,root,self.mutation)
        self.assertEqual(root.get('unknown_alias').to_payload(),payload)
        self.assertIsNot(root.get('data'),root.get('unknown_alias'))
        self.assertEqual(root.get('data').data[300],0x1aff)
        self.assertEqual(root.get('data').data[:200],self.before.get('data').data[:200])

    def test_snapshot_native_upper_priority_over_nonstar_ground(self):
        table=self.before.get('data');plane=table.xsize*table.ysize;pos=11
        flags=self.tileset.get('flags').data
        for ground_flag,middle,top,expected in ((0,0,1,False),(15,0,8,True),(0,1,0,False),(15,8,0,True)):
            flags[2816]=ground_flag
            (self.game/'Data/Tilesets.rvdata2').write_bytes(marshal_rb.dump([None,self.tileset]))
            table.data[pos]=2816;table.data[pos+plane]=middle;table.data[pos+2*plane]=top
            observed=upper.snapshot(self.before,self.game,[{'x':1,'y':1}],[1,8])['cells'][0]
            self.assertEqual(observed['tile_id'],top)
            self.assertEqual(observed['passage'],{name:expected for name in ('down','left','right','up')},
                             (ground_flag,middle,top))

    def test_candidate_verifier_refuses_ground_region_shadow_unknown_field_and_shape_changes(self):
        for changed in ('ground','metadata','field','shape'):
            after=marshal_rb.load(marshal_rb.dump(self.before));upper.apply(after,self.mutation,self.game)
            if changed=='ground':after.get('data').data[0]=1
            elif changed=='metadata':after.get('data').data[300]=0
            elif changed=='field':after.set('note',backend.convert('altered'))
            else:after.set('width',9)
            with self.assertRaises(ValueError):upper.verify_transition(self.before,after,self.mutation)

    def test_stale_native_table_tileset_or_asset_hash_refuses_without_mutating(self):
        for field in ('expected_table_sha256','expected_tileset_sha256','expected_assets'):
            root=marshal_rb.load(marshal_rb.dump(self.before));raw=marshal_rb.dump(root);mutation=json.loads(json.dumps(self.mutation))
            if field=='expected_assets':mutation[field][0]['sha256']='0'*64
            else:mutation[field]='0'*64
            with self.assertRaises(ValueError):upper.apply(root,mutation,self.game)
            self.assertEqual(marshal_rb.dump(root),raw)

    def test_a5_autotiles_layer_override_duplicates_bool_and_noop_cells_refuse(self):
        for update in ({'value':1536},{'value':2816},{'layer':0},{'x':True},{'value':0},{'expected_tile':1}):
            mutation=json.loads(json.dumps(self.mutation));mutation['cells'][0].update(update)
            with self.assertRaises(ValueError):upper.apply(marshal_rb.load(marshal_rb.dump(self.before)),mutation,self.game)
        mutation=json.loads(json.dumps(self.mutation));mutation['cells'].append(mutation['cells'][0])
        with self.assertRaises(ValueError):upper.apply(self.before,mutation,self.game)

    def test_missing_ambiguous_case_mismatch_wrong_dimensions_and_corrupt_png_refuse(self):
        original=self.image.read_bytes()
        for mode in ('missing','ambiguous','case','dimensions','corrupt'):
            self.image.write_bytes(original)
            if mode=='missing':self.image.unlink()
            elif mode=='ambiguous':self.image.with_suffix('.jpg').write_bytes(original)
            elif mode=='case':self.image.rename(self.image.with_name('fixture_b.png'))
            elif mode=='dimensions':self.image.write_bytes(png(256,512))
            else:self.image.write_bytes(b'invalid PNG')
            with self.assertRaises(ValueError):upper.apply(marshal_rb.load(marshal_rb.dump(self.before)),self.mutation,self.game)
            for path in self.image.parent.iterdir():path.unlink()
        self.image.write_bytes(original)

    def test_lowlevel_backend_requires_real_map_path_and_revalidates_actual_assets(self):
        spec={'type':'map_tile','mutation':self.mutation,'context':{'rtp':None}}
        with self.assertRaises(ValueError):backend.apply(self.before,spec)
        self.image.write_bytes(png(256,512))
        with self.assertRaises(ValueError):backend.apply(self.before,spec,source_path=self.game/'Data/Map001.rvdata2')
        self.assertEqual(self.before.get('data').data[211],0)

    def test_complete_copy_chain_advances_version_once_and_preserves_all_other_data(self):
        from vxace_copy_patcher import current_inventory
        original=current_inventory(self.game);result=self.stage();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(current_inventory(self.game),original)
        candidate,_=backend.load(self.base/'copy/Data/Map001.rvdata2');upper.verify_transition(self.before,candidate,self.mutation)
        system,_=backend.load(self.base/'copy/Data/System.rvdata2');self.assertEqual(system.get('version_id'),11)
        self.assertEqual((self.game/'Data/Tilesets.rvdata2').read_bytes(),(self.base/'copy/Data/Tilesets.rvdata2').read_bytes())
        audit=json.loads((self.base/'audit/audit.json').read_text())
        self.assertTrue(audit['changes'][0]['upper_tiles']['only_approved_upper_bytes_changed'])
        for path in ('post-validation/validation.json','post-map-audit.json','semantic-diff.json','structural-impact.json'):
            self.assertTrue((self.base/'audit'/path).is_file())

    def test_python_reindex_and_single_map_operation_are_mandatory(self):
        for backend_name,extra in (('ruby',()),('python',('--no-reindex',))):
            result=self.stage(backend_name,extra);self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())
        self.spec['changes'].append(self.spec['changes'][0]);self.specfile.write_text(json.dumps(self.spec))
        result=self.stage();self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())

    def test_rtp_output_paths_and_missing_explicit_rtp_are_refused(self):
        rtp=self.base/'rtp';image=rtp/'Graphics/Tilesets/Fixture_B.png';image.parent.mkdir(parents=True)
        self.image.rename(image);self.read()
        snap=upper.snapshot(self.before,self.game,[{'x':1,'y':1}],[1,8],rtp)
        self.mutation['expected_assets']=snap['assets'];self.specfile.write_text(json.dumps(self.spec))
        result=self.stage();self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())
        refused=self.stage(extra=('--rtp',str(rtp),'--copy',str(rtp/'unsafe-copy')))
        self.assertNotEqual(refused.returncode,0);self.assertFalse((rtp/'unsafe-copy').exists())
        passed=self.stage(extra=('--rtp',str(rtp)));self.assertEqual(passed.returncode,0,passed.stderr)

    def test_post_reindex_failure_rolls_back_and_retains_audit(self):
        reader=self.base/'failed-reader.py';reader.write_text('raise SystemExit(8)\n')
        result=self.stage(extra=('--reader',str(reader)));self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.base/'copy').exists());failure=json.loads((self.base/'audit/failure.json').read_text())
        self.assertTrue(failure['staged_copy_removed'])

    def test_other_ordinary_sheet_slots_require_and_bind_their_own_images(self):
        names=self.tileset.get('tileset_names')
        for slot,label in ((6,'Fixture_C'),(7,'Fixture_D'),(8,'Fixture_E')):
            names[slot]=backend.convert(label);(self.image.parent/(label+'.png')).write_bytes(png())
        (self.game/'Data/Tilesets.rvdata2').write_bytes(marshal_rb.dump([None,self.tileset]));self.read()
        snap=upper.snapshot(self.before,self.game,[{'x':1,'y':1}],[256,512,768])
        self.assertEqual([binding['slot'] for binding in snap['assets']],[6,7,8])
        self.mutation['expected_assets']=snap['assets'];self.mutation['expected_tileset_sha256']=snap['tileset_sha256']
        self.mutation['cells']=[{'x':n+1,'y':1,'expected_tile':0,'value':value} for n,value in enumerate((256,512,768))]
        self.specfile.write_text(json.dumps(self.spec));result=self.stage();self.assertEqual(result.returncode,0,result.stderr)

    def test_snapshot_and_planner_are_read_only_external_review(self):
        from vxace_copy_patcher import current_inventory
        before=current_inventory(self.game)
        result=subprocess.run([sys.executable,str(ROOT/'tools/vxace_upper_tiles.py'),str(self.index),'--project',str(self.game),
                               '--map','1','--cell','1','1','--tile','1','--output',str(self.base/'snapshot')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        snap=json.loads((self.base/'snapshot/upper-tile-snapshot.json').read_text());self.assertFalse(snap['mutation_authorized'])
        plan=subprocess.run([sys.executable,str(ROOT/'tools/vxace_patch_planner.py'),str(self.index),'--project',str(self.game),
                             '--spec',str(self.specfile),'--output',str(self.base/'plan')],capture_output=True,text=True)
        self.assertEqual(plan.returncode,0,plan.stderr);self.assertEqual(current_inventory(self.game),before)


if __name__=='__main__':unittest.main()
