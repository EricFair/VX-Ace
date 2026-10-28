import json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_map_encounters as enc
import vxace_map_regions as regions
import vxace_python_mutator as backend
import vxace_copy_patcher as patcher
from vxace_index_query import Index
from vxace_patch_planner import build_plan
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject

TROOPS_RUBY='''module RPG
  class Troop; class Member; end; class Page; end; end
  class Enemy; end
end
def fill(obj,h) h.each{|k,v|obj.instance_variable_set("@#{k}",v)}; obj end
def mem(eid) fill(RPG::Troop::Member.new,enemy_id:eid,x:100,y:120,hidden:false) end
def troop(id,name,eids) fill(RPG::Troop.new,id:id,name:name,members:eids.map{|e|mem(e)},pages:[]) end
list=[nil,troop(1,"Bats",[1,1]),troop(2,"Slime",[2]),troop(3,"Boss",[3])]
File.binwrite(ARGV[0]+"/Data/Troops.rvdata2",Marshal.dump(list))
enemies=[nil]+(1..3).map{|i| fill(RPG::Enemy.new,id:i,name:"Foe#{i}")}
File.binwrite(ARGV[0]+"/Data/Enemies.rvdata2",Marshal.dump(enemies))
'''


def entry(troop_id=1,weight=10,regions_=(),**extra):
    return RubyObject('RPG::Map::Encounter',{'@troop_id':troop_id,'@weight':weight,'@region_set':list(regions_),**extra})


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independently authored native map fixture')
class MapEncounterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.game=self.base/'game';self.index=self.base/'index'
        subprocess.run(['ruby',str(ROOT/'tests/structure/make_map_template.rb'),str(self.game)],check=True,capture_output=True)
        script=self.base/'troops.rb'
        fixture=(ROOT/'tests/project_reader/make_fixture.rb').read_text()
        classes='module RPG'+fixture.split('module RPG',1)[1].split('actor =',1)[0]
        script.write_text(classes+'\n'+TROOPS_RUBY,encoding='utf-8')
        subprocess.run(['ruby',str(script),str(self.game)],check=True,capture_output=True)
        (self.game/'Save01.rvdata2').write_bytes(b'private preservation sentinel; never parsed')
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)
        self.source=self.game/'Data/Map001.rvdata2';self.before,_=backend.load(self.source)
        self.troops=enc.troops_for(self.source)
        self.mutation=self.make(self.before)
        self.spec={'changes':[{'kind':'map_encounter','locator':{'map_id':1},'proposal':'Add a reviewed random encounter.','mutation':self.mutation}]}
        self.specfile=self.base/'spec.json';self.save_spec()

    def make(self,root,**over):
        return {'action':'append_encounter','expected_map_sha256':enc.fingerprint(root),
                'expected_encounter_count':len(root.get('encounter_list')),'expected_troops_sha256':enc.troops_digest(self.troops),
                'troop_id':2,'weight':10,'region_ids':[],'encounter_step':None,**over}

    def save_spec(self):self.specfile.write_text(json.dumps(self.spec),encoding='utf-8')
    def clone(self,root=None):return marshal_rb.load(marshal_rb.dump(root or self.before))
    def stage(self,**kwargs):
        return patcher.build(self.index,self.game,self.specfile,self.base/'copy',self.base/'audit',shutil.which('ruby'),
                             ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py',**kwargs)

    # ---- unit ----
    def test_whole_map_append_builds_exact_native_object_and_preserves_everything_else(self):
        root=self.clone();enc.apply(root,self.mutation,self.troops)
        listed=root.get('encounter_list');self.assertEqual(len(listed),1)
        self.assertEqual((listed[0].cls,listed[0].ivars),('RPG::Map::Encounter',{'@troop_id':2,'@weight':10,'@region_set':[]}))
        self.assertEqual(root.get('encounter_step'),30)
        enc.verify_transition(self.before,root,self.mutation,self.troops)
        stripped=lambda r:marshal_rb.dump(RubyObject(r.cls,{k:v for k,v in r.ivars.items() if k!='@encounter_list'}))
        self.assertEqual(stripped(root),stripped(self.before))
        self.assertEqual(self.before.get('encounter_list'),[])

    def test_region_set_is_sorted_and_encounter_step_is_set(self):
        mutation=self.make(self.before,region_ids=[40,3,9],weight=100,encounter_step=999)
        root=self.clone();enc.apply(root,mutation,self.troops)
        self.assertEqual(root.get('encounter_list')[0].get('region_set'),[3,9,40])
        self.assertEqual(root.get('encounter_step'),999)
        enc.verify_transition(self.before,root,self.mutation|mutation,self.troops)
        edge=self.make(self.before,region_ids=list(range(1,33)),weight=1,encounter_step=1)
        root=self.clone();enc.apply(root,edge,self.troops);self.assertEqual(root.get('encounter_step'),1)

    def test_existing_valid_entries_are_kept_and_duplicates_refused(self):
        root=self.clone();enc.apply(root,self.mutation,self.troops)
        same=self.make(root,troop_id=2)
        with self.assertRaisesRegex(ValueError,'Duplicate'):enc.apply(self.clone(root),same,self.troops)
        other=self.make(root,troop_id=2,region_ids=[5]);after=self.clone(root);enc.apply(after,other,self.troops)
        self.assertEqual([e.get('region_set') for e in after.get('encounter_list')],[[],[5]])
        enc.verify_transition(root,after,other,self.troops)
        third=self.make(after,troop_id=2,region_ids=[5]);
        with self.assertRaisesRegex(ValueError,'Duplicate'):enc.apply(self.clone(after),third,self.troops)
        # Same regions with a different troop, or the same troop on a different set, remain allowed.
        enc.apply(self.clone(after),self.make(after,troop_id=3,region_ids=[5]),self.troops)

    def test_existing_odd_entries_refuse(self):
        odd={'extra ivar':RubyObject('RPG::Map::Encounter',{'@troop_id':1,'@weight':10,'@region_set':[],'@x':1}),
             'missing ivar':RubyObject('RPG::Map::Encounter',{'@troop_id':1,'@weight':10}),
             'wrong class':RubyObject('RPG::Other',{'@troop_id':1,'@weight':10,'@region_set':[]}),
             'zero weight':entry(weight=0),'big weight':entry(weight=101),'bool weight':entry(weight=True),
             'region 64':entry(regions_=[64]),'region 0':entry(regions_=[0]),'dup regions':entry(regions_=[2,2]),
             'string troop':entry(troop_id=backend.convert('1')),'nil entry':None,'int entry':5}
        for label,value in odd.items():
            root=self.clone();root.set('encounter_list',[value])
            with self.subTest(label=label),self.assertRaises(ValueError):enc.existing(root)
            mutation=self.make(self.before,expected_encounter_count=1)
            mutation['expected_map_sha256']=enc.fingerprint(root)
            with self.subTest(label=label,apply=True),self.assertRaises(ValueError):enc.apply(root,mutation,self.troops)
        alias=entry();root=self.clone();root.set('encounter_list',[alias,alias])
        with self.assertRaises(ValueError):enc.existing(root)
        root=self.clone();root.set('encounter_list',entry())
        with self.assertRaises(ValueError):enc.existing(root)

    def test_troop_bounds_and_nil_or_sparse_troops_refuse(self):
        for troop in (0,4,-1,True,'2',None,2.0,[2]):
            with self.subTest(troop=troop),self.assertRaises(ValueError):enc.apply(self.clone(),{**self.mutation,'troop_id':troop},self.troops)
        for hole in (1,2,3):
            troops=marshal_rb.load(marshal_rb.dump(self.troops));troops[hole]=None
            mutation={**self.mutation,'expected_troops_sha256':enc.troops_digest(troops)}
            with self.subTest(hole=hole),self.assertRaises(ValueError):enc.apply(self.clone(),mutation,troops)
        with self.assertRaises(ValueError):enc.apply(self.clone(),self.mutation,[None])
        with self.assertRaises(ValueError):enc.apply(self.clone(),self.mutation,None)

    def test_weight_region_and_step_bounds_refuse_atomically(self):
        bad=[('weight',0),('weight',101),('weight',True),('weight','5'),('weight',5.0),('weight',None),
             ('region_ids',[0]),('region_ids',[64]),('region_ids',[1,1]),('region_ids',list(range(1,34))),('region_ids','x'),
             ('region_ids',[True]),('region_ids',None),('region_ids',[1.0]),('region_ids',[-1]),
             ('encounter_step',0),('encounter_step',1000),('encounter_step',True),('encounter_step','30'),('encounter_step',1.5)]
        for field,value in bad:
            root=self.clone();before=marshal_rb.dump(root)
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):enc.apply(root,{**self.mutation,field:value},self.troops)
            self.assertEqual(marshal_rb.dump(root),before)

    def test_stale_hashes_count_and_unknown_schema_refuse(self):
        cases=[('expected_map_sha256','0'*64),('expected_map_sha256',None),('expected_map_sha256','A'*64),('expected_map_sha256','abc'),
               ('expected_troops_sha256','0'*64),('expected_troops_sha256',5),('expected_encounter_count',1),
               ('expected_encounter_count',True),('expected_encounter_count',-1),('action','set_encounters')]
        for field,value in cases:
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):enc.apply(self.clone(),{**self.mutation,field:value},self.troops)
        for mutation in ({**self.mutation,'extra':1},{k:v for k,v in self.mutation.items() if k!='weight'},[],None):
            with self.assertRaises(ValueError):enc.apply(self.clone(),mutation,self.troops)
        root=self.clone();root.get('data').data[0]^=1
        with self.assertRaisesRegex(ValueError,'fingerprint'):enc.apply(root,self.mutation,self.troops)
        root=self.clone();root.set('custom_field',1)
        with self.assertRaises(ValueError):enc.apply(root,self.mutation,self.troops)
        changed=marshal_rb.load(marshal_rb.dump(self.troops));changed[1].set('id',1);changed[3].set('name',backend.convert('Changed'))
        with self.assertRaisesRegex(ValueError,'troops fingerprint'):enc.apply(self.clone(),self.mutation,changed)

    def test_candidate_verifier_detects_tampering(self):
        def good():
            root=self.clone();enc.apply(root,self.mutation,self.troops);return root
        def tile(r):r.get('data').data[0]^=1
        def event(r):r.get('events').pairs.clear()
        def meta(r):r.set('disable_dashing',True)
        def note(r):r.set('note',backend.convert('x'))
        def step(r):r.set('encounter_step',31)
        def weight(r):r.get('encounter_list')[0].set('weight',11)
        def troop(r):r.get('encounter_list')[0].set('troop_id',3)
        def regions_(r):r.get('encounter_list')[0].set('region_set',[4])
        def extra(r):r.get('encounter_list').append(entry(3))
        def ivar(r):r.get('encounter_list')[0].set('mystery',1)
        def drop(r):r.get('encounter_list').pop()
        def prefix(r):r.get('encounter_list').insert(0,entry(1))
        for fn in (tile,event,meta,note,step,weight,troop,regions_,extra,ivar,drop,prefix):
            root=good()
            fn(root)
            with self.subTest(tamper=fn.__name__),self.assertRaises(ValueError):enc.verify_transition(self.before,root,self.mutation,self.troops)
        # An existing-prefix change is caught as well.
        base=self.clone();enc.apply(base,self.mutation,self.troops)
        after=self.clone(base);enc.apply(after,self.make(base,troop_id=3),self.troops)
        enc.verify_transition(base,after,self.make(base,troop_id=3),self.troops)
        after.get('encounter_list')[0].set('weight',55)
        with self.assertRaises(ValueError):enc.verify_transition(base,after,self.make(base,troop_id=3),self.troops)

    def test_snapshot_is_readonly_and_refuses_stale_index_contained_or_existing_output(self):
        before=patcher.current_inventory(self.game);out=self.base/'snapshot'
        args=[str(self.index),'--project',str(self.game),'--map','1','--output',str(out)]
        self.assertEqual(enc.main(args),0)
        snap=json.loads((out/'map-encounter-snapshot.json').read_text())
        self.assertEqual(snap['map_sha256'],self.mutation['expected_map_sha256'])
        self.assertEqual((snap['encounter_count'],snap['encounters'],snap['encounter_step']),(0,[],30))
        self.assertEqual(snap['troops_sha256'],self.mutation['expected_troops_sha256'])
        self.assertEqual(snap['troop_id_range'],[1,3]);self.assertFalse(snap['mutation_authorized'])
        self.assertEqual([t['name'] for t in snap['troops']],['Bats','Slime','Boss'])
        self.assertEqual(patcher.current_inventory(self.game),before)
        self.assertEqual(enc.main(args),2)
        args[-1]=str(self.game/'report');self.assertEqual(enc.main(args),2);self.assertFalse((self.game/'report').exists())
        file=self.index/'maps/map-001.json';value=json.loads(file.read_text());value['encounter_step']=99;file.write_text(json.dumps(value))
        with self.assertRaises(ValueError):enc.indexed_snapshot(Index(self.index),self.game,1)

    def test_lowlevel_requires_actual_canonical_native_map_and_rejects_forged_context(self):
        spec={'type':'map_encounter','mutation':self.mutation}
        with self.assertRaises(ValueError):backend.apply(self.clone(),spec)
        wrong=self.base/'Map001.rvdata2';wrong.write_bytes(self.source.read_bytes())
        with self.assertRaises(ValueError):backend.apply(self.clone(),spec,source_path=wrong)
        forged=self.clone();forged.set('note',backend.convert('Forged'))
        with self.assertRaises(ValueError):backend.apply(forged,spec,source_path=self.source)
        root=self.clone();backend.apply(root,spec,source_path=self.source)
        enc.verify_transition(self.before,root,self.mutation,self.troops)

    def test_planner_binds_native_state_and_refuses_stale_guard_and_mixed_plan(self):
        plan=build_plan(self.index,self.game,self.specfile,self.base/'plan')
        self.assertEqual(plan['changes'][0]['added'],{'troop_id':2,'weight':10,'region_set':[]})
        self.assertEqual(plan['changes'][0]['before']['encounters'],[])
        self.assertTrue(any('encounters enabled' in c for c in plan['regression_checks']))
        self.mutation['expected_troops_sha256']='0'*64;self.save_spec()
        with self.assertRaises(ValueError):build_plan(self.index,self.game,self.specfile,self.base/'bad-plan')
        self.mutation['expected_troops_sha256']=enc.troops_digest(self.troops);self.spec['changes']*=2;self.save_spec()
        with self.assertRaises(ValueError):build_plan(self.index,self.game,self.specfile,self.base/'mixed-plan')

    # ---- end to end ----
    def test_complete_copy_chain_appends_only_the_encounter_and_advances_version(self):
        self.mutation.update(region_ids=[3,9],weight=25,encounter_step=45);self.save_spec()
        before=patcher.current_inventory(self.game);result=self.stage();self.assertEqual(result['status'],'ok')
        copied=self.base/'copy';after=patcher.current_inventory(copied)
        self.assertEqual(patcher.current_inventory(self.game),before)
        self.assertEqual({k for k in before if before[k]!=after[k]},{'Data/Map001.rvdata2','Data/System.rvdata2'})
        self.assertEqual(set(before),set(after))
        self.assertEqual((self.game/'Data/Troops.rvdata2').read_bytes(),(copied/'Data/Troops.rvdata2').read_bytes())
        final,_=backend.load(copied/'Data/Map001.rvdata2')
        enc.verify_transition(self.before,final,self.mutation,self.troops)
        self.assertEqual((final.get('encounter_step'),[(e.get('troop_id'),e.get('weight'),e.get('region_set')) for e in final.get('encounter_list')]),(45,[(2,25,[3,9])]))
        old_system,_=backend.load(self.game/'Data/System.rvdata2');new_system,_=backend.load(copied/'Data/System.rvdata2')
        self.assertEqual(new_system.get('version_id'),old_system.get('version_id')+1)
        record=result['changes'][0]['encounter']
        self.assertEqual(record['before']['encounters'],[]);self.assertEqual(record['after']['encounters'],record['after']['encounters'])
        self.assertEqual(len(record['after']['encounters']),1);self.assertEqual(record['after']['encounter_step'],45)
        self.assertTrue(record['other_map_fields_unchanged'])
        for file in ('post-validation/validation.json','post-map-audit.json','structural-impact.json','semantic-diff.json'):
            self.assertTrue((self.base/'audit'/file).exists())
        impact=json.loads((self.base/'audit/structural-impact.json').read_text())['impacts'][0]
        self.assertEqual(impact['troop']['name'],'Slime');self.assertEqual([m['name'] for m in impact['troop']['members']],['Foe2'])
        self.assertEqual(impact['region_usage']['unpainted_regions'],[3,9])
        self.assertTrue(any('encounters enabled' in x for x in impact['limitations']))
        ruby=("load ARGV.shift; ARGV.shift; class RPG::Map::Encounter; end; m=Marshal.load(File.binread(ARGV.shift)); e=m.instance_variable_get(:@encounter_list); "
              "abort 'wrong list' unless e.size==1 && e[0].class==RPG::Map::Encounter && e[0].instance_variable_get(:@troop_id)==2 && "
              "e[0].instance_variable_get(:@weight)==25 && e[0].instance_variable_get(:@region_set)==[3,9] && m.instance_variable_get(:@encounter_step)==45")
        check=subprocess.run(['ruby','-e',ruby,str(ROOT/'tests/structure/make_map_template.rb'),str(self.base/'ruby-independent'),str(copied/'Data/Map001.rvdata2')],capture_output=True)
        self.assertEqual(check.returncode,0,check.stderr)

    def test_unset_step_leaves_encounter_step_unchanged_in_copy(self):
        self.stage();final,_=backend.load(self.base/'copy/Data/Map001.rvdata2')
        self.assertEqual(final.get('encounter_step'),30)

    def test_ruby_no_reindex_two_changes_and_region_combination_refuse_before_copy(self):
        with self.assertRaises(ValueError):self.stage(no_reindex=True)
        with self.assertRaises(ValueError):patcher.build(self.index,self.game,self.specfile,self.base/'copy',self.base/'audit',shutil.which('ruby'),ROOT/'tools/rvdata2_mutator.rb',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')
        second=json.loads(json.dumps(self.spec['changes'][0]));second['mutation']['troop_id']=3
        self.spec['changes'].append(second);self.save_spec()
        with self.assertRaisesRegex(ValueError,'one map encounter'):self.stage()
        table=regions.table_for(self.before)
        region={'kind':'map_region','locator':{'map_id':1},'proposal':'Region edit on the same map.',
                'mutation':{'action':'set_regions','expected_table_sha256':regions.fingerprint(table),
                            'cells':[{'x':0,'y':0,'expected_region':0,'value':5}]}}
        self.spec['changes']=[self.spec['changes'][0],region];self.save_spec()
        with self.assertRaisesRegex(ValueError,'cannot be combined'):self.stage()
        self.spec['changes']=[region,self.spec['changes'][0]];self.save_spec()
        with self.assertRaisesRegex(ValueError,'cannot be combined'):self.stage()
        self.assertFalse((self.base/'copy').exists());self.assertFalse((self.base/'audit').exists())

    def test_stale_and_invalid_inputs_refuse_before_copy(self):
        for field,value in (('expected_map_sha256','0'*64),('expected_troops_sha256','0'*64),('expected_encounter_count',3),('troop_id',9),('weight',0)):
            good=dict(self.mutation);self.mutation[field]=value;self.save_spec()
            with self.subTest(field=field),self.assertRaises(ValueError):self.stage()
            self.mutation.clear();self.mutation.update(good)
        for loc in ({'map_id':True},{'map_id':0},{'map_id':1000},{'map_id':1,'field':'width'}):
            bad={**self.spec['changes'][0],'locator':loc}
            with self.assertRaises(ValueError):patcher.normalize_changes(self.index,{'changes':[bad]})
        self.save_spec();self.assertFalse((self.base/'copy').exists());self.assertFalse((self.base/'audit').exists())

    def test_reader_failure_rolls_back_whole_copy_and_preserves_source(self):
        before=patcher.current_inventory(self.game);original=patcher.run
        def fail(command,**kwargs):
            if len(command)>1 and Path(command[1]).name=='vxace_project_reader.py':return subprocess.CompletedProcess(command,1,'','injected reader failure')
            return original(command,**kwargs)
        with patch.object(patcher,'run',side_effect=fail),self.assertRaisesRegex(RuntimeError,'re-index failed'):self.stage()
        self.assertFalse((self.base/'copy').exists());self.assertEqual(patcher.current_inventory(self.game),before)
        self.assertTrue(json.loads((self.base/'audit/failure.json').read_text())['staged_copy_removed'])


if __name__=='__main__':unittest.main()
