import json
from pathlib import Path
import shutil,subprocess,sys,tempfile,unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_maps as maps
from vxace_python_mutator import load,marshal_rb,RubyHash,convert
from vxace_index_query import Index
from vxace_copy_patcher import current_inventory
import vxace_copy_patcher as patcher


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native map fixture')
class MapAppendTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.game=self.base/'game';self.index=self.base/'index'
        subprocess.run(['ruby',str(ROOT/'tests/structure/make_map_template.rb'),str(self.game)],check=True,capture_output=True)
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)
        self.infos,_=load(self.game/'Data/MapInfos.rvdata2');self.native,_=load(self.game/'Data/Map001.rvdata2')
        self.snap=maps.snapshot(Index(self.index),self.game,1)
        self.mutation={'action':'append_blank_map','template_map_id':1,'new_id':2,'name':'New Clearing',**self.snap['guard']}

    def save(self,name,value):(self.game/'Data'/name).write_bytes(marshal_rb.dump(value))

    def test_candidate_preserves_source_table_and_old_tree_with_empty_new_map(self):
        before=current_inventory(self.game);infos,native=maps.candidates(self.infos,self.mutation,self.game)
        maps.verify(self.infos,infos,native,self.mutation,self.game)
        self.assertEqual(current_inventory(self.game),before)
        self.assertEqual(native.get('events').pairs,[])
        self.assertEqual(native.get('data').to_payload(),self.native.get('data').to_payload())
        selected=infos.pairs[-1][1];self.assertEqual(selected.get('name').data,b'New Clearing')
        self.assertEqual((selected.get('parent_id'),selected.get('order'),selected.get('scroll_x')),(0,2,0))
        infos.pairs.pop();self.assertEqual(marshal_rb.dump(infos),marshal_rb.dump(self.infos))

    def test_unknown_fields_runtime_logic_conditions_encounters_and_backgrounds_refuse(self):
        for mode in ('unknown','logic','condition','encounters','background','region'):
            native=marshal_rb.load(marshal_rb.dump(self.native))
            if mode=='unknown':native.set('extra',1)
            elif mode=='logic':native.get('events').pairs[0][1].get('pages')[0].get('list')[0].set('code',355)
            elif mode=='condition':native.get('events').pairs[0][1].get('pages')[0].get('condition').set('switch1_valid',True)
            elif mode=='encounters':native.set('encounter_list',[1])
            elif mode=='background':native.set('parallax_name',convert('Dynamic'))
            else:native.get('data').data[300]=256
            with self.assertRaises(ValueError):maps.inert_map(native)

    def test_tree_missing_parent_cycles_duplicate_order_or_unknown_schema_refuse(self):
        for mode in ('missing','cycle','order','unknown'):
            infos=marshal_rb.load(marshal_rb.dump(self.infos))
            if mode=='missing':infos.pairs[0][1].set('parent_id',2)
            elif mode=='cycle':infos.pairs[0][1].set('parent_id',1)
            elif mode=='order':infos.pairs.append((2,marshal_rb.load(marshal_rb.dump(infos.pairs[0][1]))))
            else:infos.pairs[0][1].set('extra',True)
            with self.assertRaises(ValueError):maps.info_table(infos)

    def test_stale_guards_extra_fields_bad_ids_and_duplicate_names_refuse(self):
        for field in self.snap['guard']:
            with self.assertRaises(ValueError):maps.candidates(self.infos,{**self.mutation,field:'0'*64},self.game)
        for extra in ({'new_id':True},{'new_id':1},{'name':'MAP001'},{'name':'bad\\name'},{'parent_id':1}):
            with self.assertRaises(ValueError):maps.candidates(self.infos,{**self.mutation,**extra},self.game)

    def test_orphan_missing_and_case_alias_map_files_refuse(self):
        path=self.game/'Data/Map002.rvdata2';path.write_bytes((self.game/'Data/Map001.rvdata2').read_bytes())
        with self.assertRaises(ValueError):maps.context(self.infos,self.game,1)
        path.unlink();source=self.game/'Data/Map001.rvdata2';source.rename(self.game/'Data/map001.rvdata2')
        with self.assertRaises(ValueError):maps.inventory(self.game)

    def test_actual_tree_tileset_and_normalized_template_must_agree(self):
        false=marshal_rb.load(marshal_rb.dump(self.infos));false.pairs[0][1].set('name',convert('Forged'))
        with self.assertRaises(ValueError):maps.context(false,self.game,1)
        path=self.index/'maps/map-001.json';value=json.loads(path.read_text());value['width']=True;path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):maps.snapshot(Index(self.index),self.game,1)
        self.save('Tilesets.rvdata2',[None])
        with self.assertRaises(ValueError):maps.context(self.infos,self.game,1)

    def test_candidate_verifier_rejects_extra_tree_entries_table_and_metadata_changes(self):
        for mode in ('tree','table','map'):
            infos,native=maps.candidates(self.infos,self.mutation,self.game)
            if mode=='tree':infos.pairs[0][1].set('name',convert('Changed'))
            elif mode=='table':native.get('data').data[0]=1
            else:native.set('disable_dashing',True)
            with self.assertRaises(ValueError):maps.verify(self.infos,infos,native,self.mutation,self.game)

    def test_empty_event_template_and_order_overflow(self):
        native=marshal_rb.load(marshal_rb.dump(self.native));native.set('events',RubyHash([],None));maps.inert_map(native)
        self.infos.pairs[0][1].set('order',2**31-1);self.save('MapInfos.rvdata2',self.infos)
        _,guard,_=maps.context(self.infos,self.game,1)
        with self.assertRaises(ValueError):maps.candidates(self.infos,{**self.mutation,**guard},self.game)

    def spec(self):
        mutation=dict(self.mutation);mutation.pop('template_map_id')
        result={'changes':[{'kind':'map_entry','locator':{'template_map_id':1},'proposal':'Append one empty map at the native next ID.', 'mutation':mutation}]}
        path=self.base/'spec.json';path.write_text(json.dumps(result));return path,result

    def test_coordinated_copy_tree_map_postgates_and_source_preservation(self):
        spec,_=self.spec();original=current_inventory(self.game)
        result=patcher.build(self.index,self.game,spec,self.base/'copy',self.base/'audit',shutil.which('ruby'),ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')
        self.assertEqual(result['status'],'ok');self.assertEqual(current_inventory(self.game),original)
        after_info,_=load(self.base/'copy/Data/MapInfos.rvdata2');after_map,_=load(self.base/'copy/Data/Map002.rvdata2')
        maps.verify(self.infos,after_info,after_map,self.mutation,self.game)
        self.assertEqual((self.base/'copy/Data/System.rvdata2').read_bytes(),(self.game/'Data/System.rvdata2').read_bytes())
        self.assertEqual((self.base/'copy/Data/Map001.rvdata2').read_bytes(),(self.game/'Data/Map001.rvdata2').read_bytes())
        self.assertEqual({entry['file'] for entry in result['roundtrip_preflight']},{'Map001.rvdata2','MapInfos.rvdata2'})
        for file in ('post-validation/validation.json','post-map-audit.json','structural-impact.json','semantic-diff.json'):
            self.assertTrue((self.base/'audit'/file).exists())
        copied=current_inventory(self.base/'copy');self.assertEqual(set(copied)-set(original),{'Data/Map002.rvdata2'})
        self.assertEqual({name for name in original if original[name]!=copied[name]},{'Data/MapInfos.rvdata2'})

    def test_python_reindex_single_transaction_and_planner_guards(self):
        spec,value=self.spec()
        common=[sys.executable,str(ROOT/'tools/vxace_copy_patcher.py'),str(self.index),'--project',str(self.game),'--spec',str(spec),
                '--copy',str(self.base/'copy'),'--audit',str(self.base/'audit')]
        for options in (('--backend','ruby'),('--backend','python','--no-reindex')):
            result=subprocess.run(common+list(options),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())
        planned=subprocess.run([sys.executable,str(ROOT/'tools/vxace_patch_planner.py'),str(self.index),'--project',str(self.game),
                                '--spec',str(spec),'--output',str(self.base/'plan')],capture_output=True,text=True)
        self.assertEqual(planned.returncode,0,planned.stderr)
        value['changes'].append(value['changes'][0]);spec.write_text(json.dumps(value))
        result=subprocess.run(common+['--backend','python'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())

    def test_final_copy_inventory_tampering_rolls_back_entire_new_map(self):
        spec,_=self.spec();original=current_inventory(self.game);inventory=patcher.current_inventory;injected=False
        def changed(root):
            nonlocal injected
            if Path(root)==self.base/'copy' and (self.base/'audit/post-validation/validation.json').exists() and not injected:
                native,_=load(self.base/'copy/Data/Map002.rvdata2');native.set('disable_dashing',True)
                (self.base/'copy/Data/Map002.rvdata2').write_bytes(marshal_rb.dump(native));injected=True
            return inventory(root)
        with patch.object(patcher,'current_inventory',side_effect=changed):
            with self.assertRaises(RuntimeError):
                patcher.build(self.index,self.game,spec,self.base/'copy',self.base/'audit',shutil.which('ruby'),ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')
        self.assertTrue(injected);self.assertFalse((self.base/'copy').exists());self.assertEqual(current_inventory(self.game),original)
        self.assertTrue(json.loads((self.base/'audit/failure.json').read_text())['staged_copy_removed'])


if __name__=='__main__':unittest.main()
