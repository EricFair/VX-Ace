import json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_map_names as names
import vxace_python_mutator as backend
import vxace_copy_patcher as patcher
from vxace_index_query import Index
from vxace_patch_planner import build_plan


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independently authored native map fixture')
class MapNameTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.game=self.base/'game';self.index=self.base/'index'
        subprocess.run(['ruby',str(ROOT/'tests/structure/make_map_template.rb'),str(self.game)],check=True,capture_output=True)
        (self.game/'Save01.rvdata2').write_bytes(b'private preservation sentinel; never parsed')
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)
        self.source=self.game/'Data/Map001.rvdata2';self.before,_=backend.load(self.source)
        self.mutation={'action':'set_display_name','expected_map_sha256':names.fingerprint(self.before),
                       'expected_display_name':'','value':'Oakfall Village'}
        self.spec={'changes':[{'kind':'map_name','locator':{'map_id':1},'proposal':'Display the reviewed village name.', 'mutation':self.mutation}]}
        self.specfile=self.base/'spec.json';self.save_spec()

    def save_spec(self):self.specfile.write_text(json.dumps(self.spec),encoding='utf-8')
    def clone(self):return backend.marshal_rb.load(backend.marshal_rb.dump(self.before))
    def stage(self,**kwargs):
        return patcher.build(self.index,self.game,self.specfile,self.base/'copy',self.base/'audit',shutil.which('ruby'),
                             ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py',**kwargs)

    def test_detached_utf8_and_empty_names_preserve_shared_old_string_and_all_fields(self):
        root=self.clone();root.set('note',root.get('display_name'))
        mutation={**self.mutation,'expected_map_sha256':names.fingerprint(root),'value':'Oakfall — Café'}
        before=backend.marshal_rb.load(backend.marshal_rb.dump(root));names.apply(root,mutation)
        names.verify_transition(before,root,mutation)
        self.assertEqual(root.get('note').data,b'');self.assertIsNot(root.get('note'),root.get('display_name'))
        self.assertEqual(root.get('display_name').data,'Oakfall — Café'.encode())
        clearing={**mutation,'expected_map_sha256':names.fingerprint(root),'expected_display_name':mutation['value'],'value':''}
        names.apply(root,clearing);self.assertEqual(names.current(root),'')

    def test_stale_map_or_display_name_and_unapproved_schema_refuse_atomically(self):
        for extra in ({'expected_map_sha256':'0'*64},{'expected_display_name':'Wrong'},
                      {'expected_display_name':False},{'action':'rename_tree'},{'field':'width'},{'value':''}):
            root=self.clone();before=backend.marshal_rb.dump(root)
            with self.subTest(extra=extra),self.assertRaises(ValueError):names.apply(root,{**self.mutation,**extra})
            self.assertEqual(backend.marshal_rb.dump(root),before)
        root=self.clone();root.get('data').data[0]^=1
        with self.assertRaisesRegex(ValueError,'fingerprint'):names.apply(root,self.mutation)

    def test_invalid_bounded_plain_text_and_legacy_native_encodings_refuse(self):
        for value in (None,True,1,[],{},'x'*65,'a\nb','a\x00b',' a','a ','a\u2028b','a\u202eb','\ud800'):
            with self.subTest(value=repr(value)),self.assertRaises((ValueError,UnicodeError)):names.name(value)
        for old in (1,backend.RubyString(b'\xff',{'E':True}),backend.RubyString(b'Cafe',{'encoding':'Windows-1252'}),backend.RubyString('é'.encode(),{'E':False})):
            root=self.clone();root.set('display_name',old)
            with self.assertRaises((ValueError,UnicodeError)):names.current(root)
        root=self.clone();root.set('custom_field',1)
        with self.assertRaises(ValueError):names.current(root)

    def test_candidate_verifier_detects_tile_event_metadata_and_alias_tampering(self):
        for tamper in ('tile','event','metadata','name'):
            root=self.clone();names.apply(root,self.mutation)
            if tamper=='tile':root.get('data').data[0]^=1
            elif tamper=='event':root.get('events').pairs.clear()
            elif tamper=='metadata':root.set('disable_dashing',True)
            else:root.set('display_name',backend.convert('Other'))
            with self.subTest(tamper=tamper),self.assertRaises(ValueError):names.verify_transition(self.before,root,self.mutation)

    def test_snapshot_is_readonly_and_refuses_stale_index_contained_or_existing_output(self):
        before=patcher.current_inventory(self.game);out=self.base/'snapshot'
        args=[str(self.index),'--project',str(self.game),'--map','1','--output',str(out)]
        self.assertEqual(names.main(args),0)
        self.assertEqual(json.loads((out/'map-name-snapshot.json').read_text())['map_sha256'],self.mutation['expected_map_sha256'])
        self.assertEqual(patcher.current_inventory(self.game),before)
        self.assertEqual(names.main(args),2)
        args[-1]=str(self.game/'report');self.assertEqual(names.main(args),2);self.assertFalse((self.game/'report').exists())
        file=self.index/'maps/map-001.json';value=json.loads(file.read_text());value['display_name']='Forged';file.write_text(json.dumps(value))
        with self.assertRaises(ValueError):names.indexed_snapshot(Index(self.index),self.game,1)

    def test_lowlevel_requires_actual_canonical_native_map_and_rejects_forged_context(self):
        spec={'type':'map_name','mutation':self.mutation}
        with self.assertRaises(ValueError):backend.apply(self.clone(),spec)
        wrong=self.base/'Map001.rvdata2';wrong.write_bytes(self.source.read_bytes())
        with self.assertRaises(ValueError):backend.apply(self.clone(),spec,source_path=wrong)
        forged=self.clone();forged.set('note',backend.convert('Forged'))
        with self.assertRaises(ValueError):backend.apply(forged,spec,source_path=self.source)
        root=self.clone();backend.apply(root,spec,source_path=self.source)
        names.verify_transition(self.before,root,self.mutation)

    def test_planner_binds_native_name_and_refuses_stale_guard_and_mixed_plan(self):
        plan=build_plan(self.index,self.game,self.specfile,self.base/'plan')
        self.assertEqual(plan['changes'][0]['before'],'');self.assertEqual(plan['changes'][0]['after'],'Oakfall Village')
        self.mutation['expected_map_sha256']='0'*64;self.save_spec()
        with self.assertRaises(ValueError):build_plan(self.index,self.game,self.specfile,self.base/'bad-plan')
        self.mutation['expected_map_sha256']=names.fingerprint(self.before);self.spec['changes']*=2;self.save_spec()
        with self.assertRaises(ValueError):build_plan(self.index,self.game,self.specfile,self.base/'mixed-plan')

    def test_complete_copy_chain_changes_only_name_and_version_with_all_postgates(self):
        before=patcher.current_inventory(self.game);result=self.stage();self.assertEqual(result['status'],'ok')
        copied=self.base/'copy';after=patcher.current_inventory(copied)
        self.assertEqual(patcher.current_inventory(self.game),before)
        self.assertEqual({k for k in before if before[k]!=after[k]},{'Data/Map001.rvdata2','Data/System.rvdata2'})
        self.assertEqual(set(before),set(after));final,_=backend.load(copied/'Data/Map001.rvdata2')
        names.verify_transition(self.before,final,self.mutation)
        old_system,_=backend.load(self.game/'Data/System.rvdata2');new_system,_=backend.load(copied/'Data/System.rvdata2')
        self.assertEqual(new_system.get('version_id'),old_system.get('version_id')+1)
        self.assertTrue(result['changes'][0]['map_name']['other_native_fields_and_aliases_preserved'])
        for file in ('post-validation/validation.json','post-map-audit.json','structural-impact.json','semantic-diff.json'):
            self.assertTrue((self.base/'audit'/file).exists())
        impact=json.loads((self.base/'audit/structural-impact.json').read_text())
        self.assertEqual(impact['impacts'][0]['target']['after'],'Oakfall Village')
        ruby="load ARGV.shift; ARGV.shift; m=Marshal.load(File.binread(ARGV.shift)); abort 'wrong name' unless m.instance_variable_get(:@display_name)=='Oakfall Village'"
        # Independent Ruby decoder uses the authored class definitions, never engine code.
        check=subprocess.run(['ruby','-e',ruby,str(ROOT/'tests/structure/make_map_template.rb'),str(self.base/'ruby-independent'),str(copied/'Data/Map001.rvdata2')],capture_output=True)
        self.assertEqual(check.returncode,0,check.stderr)

    def test_ruby_no_reindex_mixed_mutation_and_invalid_locator_refuse_before_copy(self):
        with self.assertRaises(ValueError):self.stage(no_reindex=True)
        with self.assertRaises(ValueError):patcher.build(self.index,self.game,self.specfile,self.base/'copy',self.base/'audit',shutil.which('ruby'),ROOT/'tools/rvdata2_mutator.rb',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')
        self.spec['changes']*=2;self.save_spec()
        with self.assertRaises(ValueError):self.stage()
        self.assertFalse((self.base/'copy').exists());self.assertFalse((self.base/'audit').exists())
        for loc in ({'map_id':True},{'map_id':0},{'map_id':1000},{'map_id':1,'field':'width'}):
            bad={**self.spec['changes'][0],'locator':loc}
            with self.assertRaises(ValueError):patcher.normalize_changes(self.index,{'changes':[bad]})

    def test_reader_failure_rolls_back_whole_copy_and_preserves_source(self):
        before=patcher.current_inventory(self.game);original=patcher.run
        def fail(command,**kwargs):
            if len(command)>1 and Path(command[1]).name=='vxace_project_reader.py':return subprocess.CompletedProcess(command,1,'','injected reader failure')
            return original(command,**kwargs)
        with patch.object(patcher,'run',side_effect=fail),self.assertRaisesRegex(RuntimeError,'re-index failed'):self.stage()
        self.assertFalse((self.base/'copy').exists());self.assertEqual(patcher.current_inventory(self.game),before)
        self.assertTrue(json.loads((self.base/'audit/failure.json').read_text())['staged_copy_removed'])

    def test_final_unapproved_save_change_rolls_back_copy(self):
        before=patcher.current_inventory(self.game);original=patcher.run
        def tamper(command,**kwargs):
            result=original(command,**kwargs)
            if len(command)>1 and Path(command[1]).name=='vxace_semantic_diff.py':(self.base/'copy/Save01.rvdata2').write_bytes(b'changed')
            return result
        with patch.object(patcher,'run',side_effect=tamper),self.assertRaisesRegex(RuntimeError,'final copied-file preservation'):self.stage()
        self.assertFalse((self.base/'copy').exists());self.assertEqual(patcher.current_inventory(self.game),before)


if __name__=='__main__':unittest.main()
