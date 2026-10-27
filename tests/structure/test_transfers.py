import json
from pathlib import Path
import shutil,subprocess,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_transfers as transfer
import vxace_copy_patcher as patcher
from vxace_index_query import Index
from vxace_python_mutator import load,marshal_rb,apply,convert


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native fixture')
class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve()
        self.game=self.base/'game';self.index=self.base/'index'
        subprocess.run(['ruby',str(ROOT/'tests/structure/make_transfer_template.rb'),str(self.game)],check=True,capture_output=True)
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)
        self.path=self.game/'Data/Map001.rvdata2';self.root,_=load(self.path)
        self.evidence=transfer.snapshot(Index(self.index),self.game,1,1,2,3,4)
        self.mutation={'scope':'map','event_id':1,'page':1,'command_index':0,'action':'insert_commands',
                       **{key:self.evidence[key] for key in ('expected_list_sha256','commands','transfer_guard')}}

    def spec(self):
        mutation={key:value for key,value in self.mutation.items() if key not in ('scope','event_id','page','command_index')}
        value={'changes':[{'kind':'event','locator':{'map_id':1,'event_id':1,'page':1,'command_index':0},'proposal':'One direct native transfer on a blank event.','mutation':mutation}]}
        path=self.base/'spec.json';path.write_text(json.dumps(value));return path,value

    def build(self):
        spec,_=self.spec()
        return patcher.build(self.index,self.game,spec,self.base/'copy',self.base/'audit',shutil.which('ruby'),ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')

    def test_native_candidate_inserts_exact201_and_preserves_every_other_field(self):
        before=patcher.current_inventory(self.game);candidate=marshal_rb.load(marshal_rb.dump(self.root))
        apply(candidate,{'type':'event','mutation':self.mutation},source_path=self.path)
        transfer.verify_transition(self.root,candidate,self.mutation,self.path)
        commands=candidate.get('events').pairs[0][1].get('pages')[0].get('list')
        self.assertEqual((commands[0].get('code'),commands[0].get('parameters')),(201,[0,2,3,4,2,0]))
        commands.pop(0);self.assertEqual(marshal_rb.dump(candidate),marshal_rb.dump(self.root))
        self.assertEqual(patcher.current_inventory(self.game),before)

    def test_variable_bool_wrong_direction_fade_bounds_and_mixed_commands_refuse(self):
        for p in ([1,2,3,4,2,0],[0,True,3,4,2,0],[0,2,3,4,1,0],[0,2,3,4,2,3],[0,2,-1,4,2,0],[0,2,10,4,2,0],[0,1,3,4,2,0],[0,3,3,4,2,0]):
            mutation={**self.mutation,'commands':[{'code':201,'indent':0,'parameters':p}]}
            with self.assertRaises(ValueError):transfer.validate(self.root,mutation,self.path)
        for commands in (self.mutation['commands']*2,self.mutation['commands']+[{'code':125,'indent':0,'parameters':[0,0,1]}]):
            with self.assertRaises(ValueError):transfer.validate(self.root,{**self.mutation,'commands':commands},self.path)

    def test_missing_actual_context_guards_and_nonblank_or_repeating_source_refuse(self):
        for mutation,path in ((self.mutation,None),({**self.mutation,'transfer_guard':{}},self.path),({**self.mutation,'scope':'common_event'},self.path),({**self.mutation,'page':2},self.path),({**self.mutation,'command_index':1},self.path),({**self.mutation,'expected_list_sha256':'0'*64},self.path)):
            with self.assertRaises(ValueError):apply(marshal_rb.load(marshal_rb.dump(self.root)),{'type':'event','mutation':mutation},source_path=path)
        for mode in ('condition','trigger','logic'):
            root=marshal_rb.load(marshal_rb.dump(self.root));page=root.get('events').pairs[0][1].get('pages')[0]
            if mode=='condition':page.get('condition').set('switch1_valid',True)
            elif mode=='trigger':page.set('trigger',3)
            else:page.get('list')[0].set('code',355)
            self.path.write_bytes(marshal_rb.dump(root))
            with self.assertRaises(ValueError):transfer.snapshot(Index(self.index),self.game,1,1,2,3,4)
        self.path.write_bytes(marshal_rb.dump(self.root))

    def test_every_native_guard_and_guard_without_transfer_refuse(self):
        for key in transfer.GUARD_FIELDS:
            mutation={**self.mutation,'transfer_guard':{**self.mutation['transfer_guard'],key:'0'*64}}
            with self.assertRaises(ValueError):transfer.validate(self.root,mutation,self.path)
        mutation={**self.mutation,'commands':[{'code':230,'indent':0,'parameters':[1]}]}
        with self.assertRaises(ValueError):apply(self.root,{'type':'event','mutation':mutation},source_path=self.path)
        missing=dict(self.mutation);missing.pop('transfer_guard')
        with self.assertRaises(ValueError):apply(self.root,{'type':'event','mutation':missing},source_path=self.path)

    def test_exact_public_locator_and_native_direction_fade_enumerations(self):
        _,value=self.spec();loc=value['changes'][0]['locator']
        for modified in ({**loc,'map_id':True},{**loc,'event_id':True},{**loc,'page':True},{**loc,'command_index':False},{**loc,'extra':1}):
            value['changes'][0]['locator']=modified
            with self.assertRaises(ValueError):patcher.normalize_changes(self.index,value)
        value['changes'][0]['locator']=loc
        for modified in ({**value['changes'][0]['mutation'],'action':'set_parameters','parameters':[]},{**value['changes'][0]['mutation'],'extra':1}):
            altered={'changes':[{**value['changes'][0],'mutation':modified}]}
            with self.assertRaises(ValueError):patcher.normalize_changes(self.index,altered)
        with self.assertRaises(ValueError):apply(self.root,{'type':'event','mutation':{**self.mutation,'action':'set_parameters','parameters':[]}},source_path=self.path)
        for direction in (0,2,4,6,8):
            for fade in (0,1,2):
                rows=[{'code':201,'indent':0,'parameters':[0,2,3,4,direction,fade]}]
                candidate=marshal_rb.load(marshal_rb.dump(self.root))
                mutation={**self.mutation,'commands':rows}
                apply(candidate,{'type':'event','mutation':mutation},source_path=self.path)
                self.assertEqual(candidate.get('events').pairs[0][1].get('pages')[0].get('list')[0].get('parameters'),rows[0]['parameters'])

    def test_native_destination_and_indexed_tree_tilesets_must_agree(self):
        for relative in ('maps/map-001.json','maps/map-002.json','database/map-infos.json','database/tilesets.json'):
            path=self.index/relative;raw=path.read_bytes();value=json.loads(raw)
            if relative.startswith('maps'):value['width']=True
            elif isinstance(value,list):value[1]['id']=99
            else:value['2']['name']='Forged'
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):transfer.snapshot(Index(self.index),self.game,1,1,2,3,4)
            path.write_bytes(raw)
        destination,_=load(self.game/'Data/Map002.rvdata2');destination.set('events',self.root.get('events'))
        (self.game/'Data/Map002.rvdata2').write_bytes(marshal_rb.dump(destination))
        with self.assertRaises(ValueError):transfer.validate(self.root,self.mutation,self.path)

    def test_candidate_verifier_and_late_destination_context_tampering_refuse(self):
        candidate=marshal_rb.load(marshal_rb.dump(self.root));apply(candidate,{'type':'event','mutation':self.mutation},source_path=self.path)
        candidate.set('disable_dashing',True)
        with self.assertRaises(ValueError):transfer.verify_transition(self.root,candidate,self.mutation,self.path)
        transfer.final_context(self.mutation,self.game)
        path=self.game/'Data/Map002.rvdata2';root,_=load(path);root.set('disable_dashing',True);path.write_bytes(marshal_rb.dump(root))
        with self.assertRaises(ValueError):transfer.final_context(self.mutation,self.game)

    def test_copy_chain_changes_only_source_map_and_reload_version(self):
        before=patcher.current_inventory(self.game);result=self.build();after=patcher.current_inventory(self.base/'copy')
        self.assertEqual(result['status'],'ok');self.assertEqual(patcher.current_inventory(self.game),before)
        self.assertEqual(set(after),set(before));self.assertEqual({key for key in before if before[key]!=after[key]},{'Data/Map001.rvdata2','Data/System.rvdata2'})
        record=next(row for row in result['changes'] if row['kind']=='event');self.assertTrue(record['direct_transfer']['only_approved_native_map_change'])
        system,_=load(self.base/'copy/Data/System.rvdata2');original,_=load(self.game/'Data/System.rvdata2')
        self.assertEqual(system.get('version_id'),original.get('version_id')+1)
        for file in ('structural-impact.json','post-map-audit.json','semantic-diff.json','post-validation/validation.json'):self.assertTrue((self.base/'audit'/file).is_file())

    def test_planner_refuses_stale_guards_and_requires_single_python_transaction(self):
        spec,value=self.spec();cmd=[sys.executable,str(ROOT/'tools/vxace_patch_planner.py'),str(self.index),'--project',str(self.game),'--spec',str(spec),'--output',str(self.base/'plan')]
        self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        value['changes'][0]['mutation']['transfer_guard']['expected_destination_sha256']='0'*64;spec.write_text(json.dumps(value))
        self.assertNotEqual(subprocess.run(cmd[:-1]+[str(self.base/'bad-plan')],capture_output=True).returncode,0)
        spec,value=self.spec();common=[sys.executable,str(ROOT/'tools/vxace_copy_patcher.py'),str(self.index),'--project',str(self.game),'--spec',str(spec),'--copy',str(self.base/'copy'),'--audit',str(self.base/'audit')]
        for extra in (['--backend','ruby'],['--backend','python','--no-reindex']):
            self.assertNotEqual(subprocess.run(common+extra,capture_output=True).returncode,0);self.assertFalse((self.base/'copy').exists())
        value['changes'].append(value['changes'][0]);spec.write_text(json.dumps(value))
        self.assertNotEqual(subprocess.run(common+['--backend','python'],capture_output=True).returncode,0)

    def test_final_source_map_tampering_rolls_back_whole_copy(self):
        original=patcher.current_inventory;before=original(self.game);injected=False
        def altered(root):
            nonlocal injected
            if Path(root)==self.base/'copy' and (self.base/'audit/post-validation/validation.json').exists() and not injected:
                path=Path(root)/'Data/Map001.rvdata2';native,_=load(path);native.set('disable_dashing',True);path.write_bytes(marshal_rb.dump(native));injected=True
            return original(root)
        with patch.object(patcher,'current_inventory',side_effect=altered),self.assertRaises(RuntimeError):self.build()
        self.assertTrue(injected);self.assertFalse((self.base/'copy').exists());self.assertEqual(original(self.game),before)
        self.assertTrue(json.loads((self.base/'audit/failure.json').read_text())['staged_copy_removed'])


if __name__=='__main__':unittest.main()
