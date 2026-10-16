import json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_map_labels as labels
import vxace_python_mutator as backend
import vxace_copy_patcher as patcher
from vxace_index_query import Index
from vxace_patch_planner import build_plan


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native map-tree fixture')
class MapLabelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.game=self.base/'game';self.index=self.base/'index'
        ruby="""load ARGV.shift
root=ARGV[0]; data=File.join(root,'Data')
infos=Marshal.load(File.binread(File.join(data,'MapInfos.rvdata2')))
second=Marshal.load(Marshal.dump(infos.fetch(1)))
second.instance_variable_set(:@name,'Second Map'.encode(Encoding::UTF_8));second.instance_variable_set(:@parent_id,1)
second.instance_variable_set(:@order,2);second.instance_variable_set(:@expanded,true)
infos[2]=second;File.binwrite(File.join(data,'MapInfos.rvdata2'),Marshal.dump(infos))
File.binwrite(File.join(data,'Map002.rvdata2'),File.binread(File.join(data,'Map001.rvdata2')))
"""
        subprocess.run(['ruby','-e',ruby,str(ROOT/'tests/structure/make_map_template.rb'),str(self.game)],check=True,capture_output=True)
        (self.game/'Save01.rvdata2').write_bytes(b'private save preservation sentinel; never parsed')
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)
        self.source=self.game/'Data/MapInfos.rvdata2';self.before,_=backend.load(self.source)
        self.snap=labels.indexed_snapshot(Index(self.index),self.game,1)
        self.mutation={'action':'set_tree_name','map_id':1,**self.snap['guard'],'value':'Oakfall Village'}
        mutation=dict(self.mutation);mutation.pop('map_id')
        self.spec={'changes':[{'kind':'map_label','locator':{'map_id':1},'proposal':'Rename the reviewed editor/tree label only.','mutation':mutation}]}
        self.specfile=self.base/'spec.json';self.save_spec()

    def save_spec(self):self.specfile.write_text(json.dumps(self.spec),encoding='utf-8')
    def clone(self):return backend.marshal_rb.load(backend.marshal_rb.dump(self.before))
    def stage(self):
        return patcher.build(self.index,self.game,self.specfile,self.base/'copy',self.base/'audit',shutil.which('ruby'),
                             ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')

    def test_native_candidate_preserves_child_metadata_pair_order_and_independent_ruby_decoding(self):
        before=patcher.current_inventory(self.game);root=self.clone();labels.apply(root,self.mutation,self.game)
        labels.verify_transition(self.before,root,self.mutation,self.game)
        self.assertEqual([key for key,_ in root.pairs],[1,2])
        self.assertEqual(root.get(2).get('name').data,b'Second Map')
        self.assertEqual((root.get(2).get('parent_id'),root.get(2).get('order'),root.get(2).get('expanded')),(1,2,True))
        self.assertEqual(patcher.current_inventory(self.game),before)
        candidate=self.base/'candidate.rvdata2';backend.write(root,candidate)
        ruby="load ARGV.shift; ARGV.shift; i=Marshal.load(File.binread(ARGV.shift)); abort 'wrong label' unless i[1].instance_variable_get(:@name)=='Oakfall Village' && i[2].instance_variable_get(:@parent_id)==1"
        check=subprocess.run(['ruby','-e',ruby,str(ROOT/'tests/structure/make_map_template.rb'),str(self.base/'ruby-independent'),str(candidate)],capture_output=True)
        self.assertEqual(check.returncode,0,check.stderr)

    def test_shared_old_string_and_duplicate_labels_are_preserved_when_target_detaches(self):
        before=self.clone();before.get(2).set('name',before.get(1).get('name'));backend.write(before,self.source)
        _,guard=labels.context(before,self.game,1)
        mutation={**self.mutation,**guard,'value':'Oakfall Forêt'}
        root=backend.marshal_rb.load(backend.marshal_rb.dump(before));labels.apply(root,mutation,self.game)
        labels.verify_transition(before,root,mutation,self.game)
        self.assertEqual(root.get(1).get('name').data,'Oakfall Forêt'.encode())
        self.assertEqual(root.get(2).get('name').data,b'MAP001')
        self.assertIsNot(root.get(1).get('name'),root.get(2).get('name'))

    def test_stale_guards_wrong_actions_invalid_text_ids_and_extra_fields_refuse_atomically(self):
        bad=[{field:'0'*64} for field in ('expected_infos_sha256','expected_entry_sha256','expected_inventory_sha256')]
        bad += [{'expected_name':'Wrong'},{'expected_name':False},{'map_id':True},{'map_id':3},
                {'action':'reparent'},{'parent_id':2},{'value':'MAP001'},{'value':'a\nb'},{'value':True},{'value':'x'*65}]
        for extra in bad:
            root=self.clone();before=backend.marshal_rb.dump(root)
            with self.subTest(extra=extra),self.assertRaises(ValueError):labels.apply(root,{**self.mutation,**extra},self.game)
            self.assertEqual(backend.marshal_rb.dump(root),before)

    def test_unsupported_tree_schema_cycles_aliases_and_native_encodings_refuse(self):
        for mode in ('field','cycle','order','alias','default','encoding'):
            root=self.clone()
            if mode=='field':root.get(1).set('extra',1)
            elif mode=='cycle':root.get(1).set('parent_id',2)
            elif mode=='order':root.get(2).set('order',1)
            elif mode=='alias':root.pairs[1]=(2,root.get(1))
            elif mode=='default':root.default=0
            else:root.get(1).set('name',backend.RubyString('é'.encode(),{'E':False}))
            backend.write(root,self.source)
            with self.subTest(mode=mode),self.assertRaises(ValueError):labels.context(root,self.game,1)

    def test_missing_orphan_and_case_aliased_map_inventory_refuse(self):
        extra=self.game/'Data/Map003.rvdata2';extra.write_bytes((self.game/'Data/Map001.rvdata2').read_bytes())
        with self.assertRaises(ValueError):labels.context(self.before,self.game,1)
        extra.unlink();second=self.game/'Data/Map002.rvdata2';raw=second.read_bytes();second.unlink()
        with self.assertRaises(ValueError):labels.context(self.before,self.game,1)
        second.write_bytes(raw);first=self.game/'Data/Map001.rvdata2';first.rename(self.game/'Data/map001.rvdata2')
        with self.assertRaises(ValueError):labels.context(self.before,self.game,1)

    def test_candidate_verifier_refuses_other_entry_parent_scroll_and_map_context_changes(self):
        for mode in ('name','parent','scroll','map'):
            root=self.clone();labels.apply(root,self.mutation,self.game)
            if mode=='name':root.get(2).set('name',backend.convert('Other'))
            elif mode=='parent':root.get(2).set('parent_id',0)
            elif mode=='scroll':root.get(1).set('scroll_x',0)
            else:
                file=self.game/'Data/Map002.rvdata2';raw=file.read_bytes();file.write_bytes(raw+b'changed')
            with self.subTest(mode=mode),self.assertRaises(ValueError):labels.verify_transition(self.before,root,self.mutation,self.game)

    def test_lowlevel_requires_actual_canonical_tree_and_rejects_forged_root_context(self):
        spec={'type':'map_label','mutation':self.mutation}
        with self.assertRaises(ValueError):backend.apply(self.clone(),spec)
        with self.assertRaises(ValueError):backend.apply(self.clone(),spec,source_path=self.game/'Data/Map001.rvdata2')
        root=self.clone();root.get(1).set('name',backend.convert('Forged'))
        with self.assertRaises(ValueError):backend.apply(root,spec,source_path=self.source)
        root=self.clone();backend.apply(root,spec,source_path=self.source);labels.verify_transition(self.before,root,self.mutation,self.game)

    def test_snapshot_output_safety_and_indexed_tree_agreement(self):
        before=patcher.current_inventory(self.game);out=self.base/'snapshot'
        args=[str(self.index),'--project',str(self.game),'--map','1','--output',str(out)]
        self.assertEqual(labels.main(args),0);observed=json.loads((out/'map-label-snapshot.json').read_text())
        self.assertEqual(observed['guard'],self.snap['guard']);self.assertEqual(patcher.current_inventory(self.game),before)
        self.assertEqual(labels.main(args),2);args[-1]=str(self.game/'report');self.assertEqual(labels.main(args),2)
        file=self.index/'database/map-infos.json';value=json.loads(file.read_text());value['1']['name']='Forged';file.write_text(json.dumps(value))
        with self.assertRaises(ValueError):labels.indexed_snapshot(Index(self.index),self.game,1)

    def test_planner_native_preconditions_and_backend_reindex_mixed_locator_refusals(self):
        plan=build_plan(self.index,self.game,self.specfile,self.base/'plan');self.assertEqual(plan['changes'][0]['after'],'Oakfall Village')
        self.spec['changes'][0]['mutation']['expected_entry_sha256']='0'*64;self.save_spec()
        with self.assertRaises(ValueError):build_plan(self.index,self.game,self.specfile,self.base/'bad-plan')
        self.spec['changes'][0]['mutation']['expected_entry_sha256']=self.mutation['expected_entry_sha256'];self.save_spec()
        for mutator,no_reindex in ((ROOT/'tools/rvdata2_mutator.rb',False),(ROOT/'tools/vxace_python_mutator.py',True)):
            with self.assertRaises(ValueError):patcher.build(self.index,self.game,self.specfile,self.base/'copy',self.base/'audit',shutil.which('ruby'),mutator,ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py',no_reindex)
        self.spec['changes']*=2;self.save_spec()
        with self.assertRaises(ValueError):self.stage()
        with self.assertRaises(ValueError):build_plan(self.index,self.game,self.specfile,self.base/'mixed-plan')
        bad={**self.spec['changes'][0],'locator':{'map_id':1,'parent_id':0}}
        with self.assertRaises(ValueError):patcher.normalize_changes(self.index,{'changes':[bad]})
        self.assertFalse((self.base/'copy').exists());self.assertFalse((self.base/'audit').exists())

    def test_complete_copy_chain_changes_only_mapinfos_and_preserves_maps_system_and_saves(self):
        before=patcher.current_inventory(self.game);result=self.stage();self.assertEqual(result['status'],'ok')
        after=patcher.current_inventory(self.base/'copy');self.assertEqual(set(before),set(after))
        self.assertEqual({p for p in before if before[p]!=after[p]},{'Data/MapInfos.rvdata2'})
        self.assertEqual(patcher.current_inventory(self.game),before);self.assertEqual(len(result['changes']),1)
        final,_=backend.load(self.base/'copy/Data/MapInfos.rvdata2');labels.verify_transition(self.before,final,self.mutation,self.game)
        self.assertTrue(result['changes'][0]['map_label']['system_version_unchanged'])
        for file in ('post-validation/validation.json','post-map-audit.json','structural-impact.json','semantic-diff.json'):
            self.assertTrue((self.base/'audit'/file).exists())

    def test_reader_failure_rolls_back_whole_copy(self):
        before=patcher.current_inventory(self.game);original=patcher.run
        def fail(command,**kwargs):
            if len(command)>1 and Path(command[1]).name=='vxace_project_reader.py':return subprocess.CompletedProcess(command,1,'','injected reader failure')
            return original(command,**kwargs)
        with patch.object(patcher,'run',side_effect=fail),self.assertRaisesRegex(RuntimeError,'re-index failed'):self.stage()
        self.assertFalse((self.base/'copy').exists());self.assertEqual(patcher.current_inventory(self.game),before)
        self.assertTrue(json.loads((self.base/'audit/failure.json').read_text())['staged_copy_removed'])

    def test_final_unapproved_map_change_rolls_back_copy(self):
        before=patcher.current_inventory(self.game);original=patcher.run
        def tamper(command,**kwargs):
            result=original(command,**kwargs)
            if len(command)>1 and Path(command[1]).name=='vxace_semantic_diff.py':
                file=self.base/'copy/Data/Map002.rvdata2';file.write_bytes(file.read_bytes()+b'changed')
            return result
        with patch.object(patcher,'run',side_effect=tamper),self.assertRaisesRegex(RuntimeError,'post-copy project validation|final copied-file preservation'):self.stage()
        self.assertFalse((self.base/'copy').exists());self.assertEqual(patcher.current_inventory(self.game),before)


if __name__=='__main__':unittest.main()
