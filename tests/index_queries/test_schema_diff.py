import json
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_schema_diff as schema
from vxace_copy_patcher import current_inventory


class SchemaDiffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.bp,self.bi=self.fixture('baseline');self.tp,self.ti=self.fixture('target')
        self.output=self.root/'report'

    def fixture(self,name):
        project=self.root/(name+'-game');index=self.root/(name+'-index')
        (project/'Data').mkdir(parents=True);(project/'Data/source.rvdata2').write_bytes(b'not-executed')
        index.mkdir();(index/'maps').mkdir();(index/'database').mkdir()
        self.write(index,'project.json',{'errors':[],'map_count':1,'database_files_decoded':[]})
        self.write(index,'manifest.json',{'read_only':True,'files':[{'path':k,'sha256':v} for k,v in current_inventory(project).items()]})
        self.write(index,'maps/map-001.json',{'__class__':'RPG::Map','width':17,'events':{},'note':''})
        self.write(index,'database/actors.json',[None,{'__class__':'RPG::Actor','id':1,'name':'A','custom':None}])
        (index/'scripts').mkdir();(index/'scripts/danger.rb').write_text('raise "NEVER EXECUTE"')
        return project,index

    def write(self,index,path,value):(index/path).write_text(json.dumps(value),encoding='utf-8')
    def run_diff(self):return schema.workflow(self.bi,self.bp,self.ti,self.tp,self.output)
    def read(self,index,path):return json.loads((index/path).read_text())

    def test_identical_shapes_are_read_only_with_bound_both_snapshots(self):
        before=[current_inventory(p) for p in (self.bp,self.bi,self.tp,self.ti)]
        result=self.run_diff()
        self.assertTrue(result['both_sources_unchanged']);self.assertFalse(result['mutation_authorized'])
        self.assertEqual(set(result['counts'].values()),{0})
        self.assertEqual([current_inventory(p) for p in (self.bp,self.bi,self.tp,self.ti)],before)
        self.assertEqual(set(result['snapshots']),{'baseline','target'})
        self.assertTrue((self.output/'schema-diff.md').is_file())

    def test_relative_added_absent_classes_fields_and_type_evidence(self):
        self.write(self.bi,'database/actors.json',[{'__class__':'RPG::Actor','id':1,'name':'A','old':False},{'__class__':'OldClass','x':1}])
        self.write(self.ti,'database/actors.json',[{'__class__':'RPG::Actor','id':1,'name':['A'],'new':True},{'__class__':'CustomClass','x':None}])
        result=self.run_diff();self.assertEqual(result['counts'],{'classes_only_in_target':1,'classes_only_in_baseline':1,'fields_only_in_target':1,'fields_only_in_baseline':1,'field_type_sets_changed':1})
        actor=next(row for row in result['classes'] if row['class']=='RPG::Actor');name=next(row for row in actor['fields'] if row['field']=='name')
        self.assertEqual(name['status'],'type_set_changed')
        self.assertEqual(name['baseline']['types']['str']['evidence'][0],{'file':'database/actors.json','path':[0,'name']})
        self.assertEqual(name['target']['types']['list']['count'],1)

    def test_normalized_types_nested_fields_counts_and_sample_cap(self):
        values=[None,True,1,1.5,'x',[],{}]
        rows=[{'__class__':'RPG::Actor','value':v,'nested':{'__class__':'Nested','flag':True}} for v in values]
        self.write(self.ti,'database/actors.json',rows*4)
        result=self.run_diff();actor=next(row for row in result['classes'] if row['class']=='RPG::Actor')
        field=next(row for row in actor['fields'] if row['field']=='value')['target']
        self.assertEqual(set(field['types']),{'NoneType','bool','int','float','str','list','dict'})
        self.assertEqual(field['observations'],28);self.assertEqual(len(field['evidence']),3)
        self.assertTrue(all(len(value['evidence'])==3 for value in field['types'].values()))
        self.assertEqual(next(row for row in result['classes'] if row['class']=='Nested')['target_objects'],28)

    def test_counts_alone_do_not_claim_schema_drift(self):
        rows=self.read(self.ti,'database/actors.json');rows.append(rows[-1]);self.write(self.ti,'database/actors.json',rows)
        result=self.run_diff();self.assertEqual(set(result['counts'].values()),{0})
        actor=next(row for row in result['classes'] if row['class']=='RPG::Actor');self.assertEqual((actor['baseline_objects'],actor['target_objects']),(1,2))

    def test_both_sources_must_be_fresh_and_complete(self):
        for project in (self.bp,self.tp):
            file=project/'Data/source.rvdata2';file.write_bytes(b'changed')
            with self.assertRaises(ValueError):self.run_diff()
            self.assertFalse(self.output.exists());file.write_bytes(b'not-executed')
        self.write(self.bi,'project.json',{'errors':['partial extraction']})
        with self.assertRaises(ValueError):self.run_diff()
        self.assertFalse(self.output.exists())

    def test_outputs_inside_either_project_or_index_and_existing_refuse(self):
        for root in (self.bp,self.bi,self.tp,self.ti):
            self.output=root/'forbidden'
            with self.assertRaises(ValueError):self.run_diff()
            self.assertFalse(self.output.exists())
        self.output=self.root/'exists';self.output.mkdir()
        with self.assertRaises(ValueError):self.run_diff()

    def test_either_project_or_read_index_change_refuses_without_report(self):
        original=schema.compare
        for root,path in ((self.bp,'Data/source.rvdata2'),(self.tp,'Data/source.rvdata2'),(self.bi,'database/actors.json'),(self.ti,'database/actors.json')):
            file=root/path;raw=file.read_bytes()
            def changed(a,b):
                result=original(a,b);file.write_bytes(raw+b' ');return result
            with patch.object(schema,'compare',side_effect=changed),self.assertRaises(ValueError):self.run_diff()
            self.assertFalse(self.output.exists());file.write_bytes(raw)

    def test_budgets_refuse_complete_report_instead_of_partial(self):
        for key,value in (('MAX_CLASSES',1),('MAX_FIELDS',1),('MAX_EVIDENCE_BYTES',20),('MAX_REPORT_BYTES',100),('MAX_SOURCE_ENTRIES',0),('MAX_SOURCE_BYTES',1),('MAX_SOURCE_FILE_BYTES',1)):
            with patch.object(schema,key,value),self.assertRaises(ValueError):self.run_diff()
            self.assertFalse(self.output.exists())
        with patch('vxace_index_query.MAX_STEPS',5),self.assertRaises(ValueError):self.run_diff()
        self.assertFalse(self.output.exists())

    def test_report_write_failure_cleans_only_new_reports(self):
        before=[current_inventory(p) for p in (self.bp,self.bi,self.tp,self.ti)]
        original=Path.write_text
        def failed(path,*args,**kwargs):
            if path.name=='schema-diff.md':raise OSError('simulated output failure')
            return original(path,*args,**kwargs)
        with patch.object(Path,'write_text',failed),self.assertRaises(OSError):self.run_diff()
        self.assertFalse(self.output.exists())
        self.assertEqual([current_inventory(p) for p in (self.bp,self.bi,self.tp,self.ti)],before)

    def test_malformed_class_oversized_keys_and_missing_maps_refuse(self):
        for value in ({'__class__':True},{'__class__':'x','x'*257:1}):
            self.write(self.ti,'database/actors.json',[value])
            with self.assertRaises(ValueError):self.run_diff()
            self.assertFalse(self.output.exists())
        (self.ti/'maps/map-001.json').unlink()
        with self.assertRaises(ValueError):self.run_diff()

    def test_linked_source_and_output_refused_when_platform_permits(self):
        link=self.root/'linked'
        try:link.symlink_to(self.root/'target-game',target_is_directory=True)
        except OSError:self.skipTest('Symlink unavailable')
        self.output=link/'report'
        with self.assertRaises(ValueError):self.run_diff()
        self.assertFalse(self.output.exists())
        self.output=self.root/'report'
        outside=self.root/'outside.bin';outside.write_bytes(b'private fixture')
        (self.tp/'Data/linked.bin').symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'Linked'):self.run_diff()
        self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
