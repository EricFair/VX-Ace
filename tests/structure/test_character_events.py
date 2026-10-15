import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_map_events as map_fixture
from test_upper_tiles import png
import vxace_map_events as events
import vxace_character_graphics as graphics
import vxace_python_mutator as backend
from vxace_copy_patcher import current_inventory,build
from rpgvxace_mcp import marshal_rb
ROOT=map_fixture.ROOT


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native fixture')
class CharacterEventTests(unittest.TestCase):
    read=map_fixture.MapEventTests.read
    stage=map_fixture.MapEventTests.stage
    clone=map_fixture.MapEventTests.clone

    def setUp(self):
        map_fixture.MapEventTests.setUp(self)
        self.image=self.game/'Graphics/Characters/People.png';self.image.parent.mkdir(parents=True);self.image.write_bytes(png(384,256))
        self.graphic={'character_name':'People','character_index':2,'direction':4,'pattern':1}
        self.mutation.update(graphic=self.graphic,expected_asset=graphics.binding(self.game,None,self.graphic))
        self.specfile.write_text(json.dumps(self.spec));self.read()

    def test_native_character_fields_and_existing_map_preservation(self):
        candidate=self.clone();events.apply(candidate,self.mutation,self.game);events.verify_transition(self.before,candidate,self.mutation,self.game)
        graphic=candidate.get('events').pairs[-1][1].get('pages')[0].get('graphic')
        self.assertEqual(graphic.get('character_name').data,b'People');self.assertEqual(graphic.get('character_index'),2)
        self.assertEqual((graphic.get('tile_id'),graphic.get('direction'),graphic.get('pattern')),(0,4,1))

    def test_complete_graphical_append_gates_and_audit(self):
        original=current_inventory(self.game);result=self.stage();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(current_inventory(self.game),original)
        candidate,_=backend.load(self.base/'copy/Data/Map001.rvdata2');events.verify_transition(self.before,candidate,self.mutation,self.game)
        audit=json.loads((self.base/'audit/audit.json').read_text());self.assertEqual(audit['changes'][0]['map_event']['asset'],self.mutation['expected_asset'])

    def test_lowlevel_source_path_context_and_actual_asset_are_mandatory(self):
        spec={'type':'map_event','mutation':self.mutation,'context':{'rtp':None}}
        with self.assertRaises(ValueError):backend.apply(self.clone(),spec)
        for context in ({},{'rtp':True},{'rtp':None,'extra':1}):
            with self.assertRaises(ValueError):backend.apply(self.clone(),dict(spec,context=context),source_path=self.game/'Data/Map001.rvdata2')
        self.image.write_bytes(png(12,9))
        with self.assertRaises(ValueError):backend.apply(self.clone(),spec,source_path=self.game/'Data/Map001.rvdata2')

    def test_missing_corrupt_case_ambiguous_and_oversized_assets_refuse(self):
        original=self.image.read_bytes()
        for mode in ('missing','corrupt','case','ambiguous','dimensions','large'):
            self.image.write_bytes(original)
            if mode=='missing':self.image.unlink()
            elif mode=='corrupt':self.image.write_bytes(b'broken')
            elif mode=='case':self.image.rename(self.image.with_name('people.png'))
            elif mode=='ambiguous':self.image.with_suffix('.jpg').write_bytes(b'competing')
            elif mode=='dimensions':self.image.write_bytes(png(383,256))
            else:
                with self.image.open('wb') as handle:handle.truncate(32*1024*1024+1)
            with self.assertRaises(ValueError):events.apply(self.clone(),self.mutation,self.game)
            for path in self.image.parent.iterdir():path.unlink()

    def test_character_ranges_paths_extensions_and_unknown_fields_refuse(self):
        for change in ({'character_index':8},{'character_index':True},{'direction':3},{'direction':True},{'pattern':3},
                       {'character_name':'../People'},{'character_name':'People.png'},{'character_name':''},{'tile_id':1}):
            with self.assertRaises(ValueError):graphics.binding(self.game,None,dict(self.graphic,**change))

    def test_single_and_object_prefixes_bind_the_actual_native_grid(self):
        for name,single,object_character in (('$Solo',True,False),('!$Door',True,True),('$!Actor',True,False),('!People',False,True)):
            image=self.image.parent/(name+'.png');image.write_bytes(png(96,128) if single else png(384,256))
            graphic=dict(self.graphic,character_name=name,character_index=0)
            asset=graphics.binding(self.game,None,graphic)
            self.assertEqual(asset['layout'],'single_character' if single else 'eight_characters')
            self.assertEqual(asset['object_character'],object_character);self.assertEqual((asset['frame_width'],asset['frame_height']),(32,32))
            if single:
                with self.assertRaises(ValueError):graphics.binding(self.game,None,dict(graphic,character_index=1))

    def test_stale_asset_hash_and_partial_optional_schema_refuse_without_mutation(self):
        for mode in ('hash','graphic','asset'):
            candidate=self.clone();old=marshal_rb.dump(candidate);mutation=json.loads(json.dumps(self.mutation))
            if mode=='hash':mutation['expected_asset']['sha256']='0'*64
            elif mode=='graphic':del mutation['graphic']
            else:del mutation['expected_asset']
            with self.assertRaises(ValueError):events.apply(candidate,mutation,self.game)
            self.assertEqual(marshal_rb.dump(candidate),old)

    def test_rtp_is_explicit_project_first_and_outputs_external(self):
        rtp=self.base/'rtp';image=rtp/'Graphics/Characters/People.png';image.parent.mkdir(parents=True);self.image.rename(image);self.read()
        with self.assertRaises(ValueError):graphics.binding(self.game,None,self.graphic)
        asset=graphics.binding(self.game,rtp,self.graphic);self.assertEqual(asset['origin'],'rtp')
        self.mutation['expected_asset']=asset;self.specfile.write_text(json.dumps(self.spec))
        result=self.stage(('--rtp',str(rtp),'--audit',str(rtp/'unsafe')));self.assertNotEqual(result.returncode,0);self.assertFalse((rtp/'unsafe').exists())
        result=self.stage(('--rtp',str(rtp)));self.assertEqual(result.returncode,0,result.stderr)
        self.image.write_bytes(png(384,256));self.assertEqual(graphics.binding(self.game,rtp,self.graphic)['origin'],'project')

    def test_graphic_snapshot_is_readonly_and_rejects_rtp_outputs(self):
        original=current_inventory(self.game)
        command=[sys.executable,str(ROOT/'tools/vxace_map_events.py'),str(self.index),'--project',str(self.game),
                 '--map','1','--template-event','1','--character','People','--character-index','2']
        result=subprocess.run([*command,'--output',str(self.base/'snapshot')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        snap=json.loads((self.base/'snapshot/map-event-snapshot.json').read_text());self.assertFalse(snap['mutation_authorized'])
        self.assertEqual(snap['asset']['sha256'],self.mutation['expected_asset']['sha256']);self.assertEqual(current_inventory(self.game),original)
        rtp=self.base/'rtp';rtp.mkdir()
        result=subprocess.run([*command,'--rtp',str(rtp),'--output',str(rtp/'unsafe')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertFalse((rtp/'unsafe').exists())

    def test_postgate_asset_change_rolls_back_and_retains_failure_audit(self):
        original=graphics.binding;calls=0;source_before=current_inventory(self.game)
        def changed(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==4:(Path(args[0])/'Graphics/Characters/People.png').write_bytes(png(384,256)+b'changed')
            return original(*args,**kwargs)
        # Native preflight snapshot + new record + candidate verification + final resolution.
        with patch.object(graphics,'binding',side_effect=changed):
            with self.assertRaises((ValueError,RuntimeError)):
                build(self.index,self.game,self.specfile,self.base/'copy',self.base/'audit',shutil.which('ruby'),
                      ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')
        self.assertFalse((self.base/'copy').exists());self.assertTrue((self.base/'audit/failure.json').exists())
        self.assertEqual(current_inventory(self.game),source_before)


if __name__=='__main__':unittest.main()
