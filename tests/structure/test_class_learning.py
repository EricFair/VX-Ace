import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_class_learning as learning
import vxace_database_entries as entries
import vxace_python_mutator as backend
import test_regions as region_fixtures
import test_database_append as table_tests
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject

S=backend.convert


def entry(level,skill_id,note=''):
    return RubyObject('RPG::Class::Learning',{'@level':level,'@skill_id':skill_id,'@note':S(note)})


def klass(identifier,learnings=None,name=None):
    return RubyObject('RPG::Class',{'@id':identifier,'@name':S(name or 'Class %d'%identifier),'@icon_index':0,'@description':S(''),'@features':[],
                                    '@note':S('<keep>'),'@exp_params':[30,20,30,30],'@params':[0]*24,
                                    '@learnings':[entry(1,1)] if learnings is None else learnings})


def classes():
    return [None,klass(1),klass(2,[])]


def skills(count=3):
    return [None]+[table_tests.make('skills',i) for i in range(1,count+1)]


def mutation(root,skill_list,class_id=1,**over):
    chosen=root[class_id]
    return {'action':'append_class_learning','expected_array_sha256':learning.digest(root),'expected_class_sha256':learning.digest(chosen),
            'expected_learning_count':len(chosen.get('learnings')),'expected_skills_sha256':learning.digest(skill_list),
            'skill_id':3,'level':3,'class_id':class_id,**over}


def apply(root,spec,skill_list):
    learning.append_learning(root,spec,skill_list)


class LearningUnitTests(unittest.TestCase):
    def test_happy_path_appends_one_learning_with_empty_note(self):
        root=classes();sk=skills();before=marshal_rb.dump(root);spec=mutation(root,sk)
        apply(root,spec,sk)
        made=root[1].get('learnings')
        self.assertEqual(len(made),2)
        last=made[-1]
        self.assertEqual((last.cls,last.get('level'),last.get('skill_id'),last.get('note').data),('RPG::Class::Learning',3,3,b''))
        self.assertEqual(list(last.ivars),['@level','@skill_id','@note'])
        self.assertEqual(root[1].get('note').data,b'<keep>')
        self.assertEqual(marshal_rb.dump(root[2]),marshal_rb.dump(classes()[2]))
        learning.verify_transition(marshal_rb.load(before),root,spec,sk)

    def test_first_learning_on_empty_list_and_level_bounds(self):
        for level in (1,99):
            root=classes();sk=skills();spec=mutation(root,sk,class_id=2,level=level);apply(root,spec,sk)
            self.assertEqual(root[2].get('learnings')[0].get('level'),level)
        for level in (0,100,-1,True,'3',3.0,None):
            root=classes();sk=skills();spec=mutation(root,sk,level=level);before=marshal_rb.dump(root)
            with self.subTest(level=level),self.assertRaises(ValueError):apply(root,spec,sk)
            self.assertEqual(marshal_rb.dump(root),before)

    def test_duplicate_skill_refused_at_any_level(self):
        for level in (1,2,50):
            root=classes();sk=skills();spec=mutation(root,sk,skill_id=1,level=level)
            with self.subTest(level=level),self.assertRaises(ValueError):apply(root,spec,sk)
        root=classes();sk=skills();apply(root,mutation(root,sk),sk)
        with self.assertRaises(ValueError):apply(root,mutation(root,sk),sk)

    def test_bad_and_nil_skill_refuse(self):
        for skill_id in (0,4,-1,True,'1',1.0,None,999):
            root=classes();sk=skills();spec=mutation(root,sk,skill_id=skill_id)
            with self.subTest(skill_id=skill_id),self.assertRaises(ValueError):apply(root,spec,sk)
        root=classes();sk=skills();spec=mutation(root,sk);sk[3]=None
        with self.assertRaises(ValueError):apply(root,spec,sk)
        root=classes();sk=skills();sk[2]=None;spec=mutation(root,sk,skill_id=2)
        with self.assertRaises(ValueError):apply(root,spec,sk)
        root=classes();sk=skills();sk[2]=table_tests.make('enemies',2);spec=mutation(root,sk)
        with self.assertRaises(ValueError):apply(root,spec,sk)

    def test_class_id_and_array_admission(self):
        for class_id in (0,3,-1,True,'1',None):
            root=classes();sk=skills();spec=mutation(root,sk);spec['class_id']=class_id
            with self.subTest(class_id=class_id),self.assertRaises(ValueError):apply(root,spec,sk)
        bad=classes();bad[2].set('id',9);alias=classes();alias[2]=alias[1]
        for root in ([],[None],{},[klass(1),klass(2)],bad,alias,[None,table_tests.make('skills')]):
            with self.subTest(root=str(root)[:50]),self.assertRaises(ValueError):learning.class_array(root)
        root=classes();root[2].cls='Custom'
        with self.assertRaises(ValueError):learning.class_array(root)

    def test_class_and_learnings_schema_refusals(self):
        for bad in ('extra','missing','learnings_type','learning_cls','learning_extra','learning_missing','level_type','skill_type','note_type','alias','shared','budget'):
            root=classes();sk=skills();chosen=root[1]
            if bad=='extra':chosen.set('custom',S('x'))
            elif bad=='missing':del chosen.ivars['@exp_params']
            elif bad=='learnings_type':chosen.set('learnings',None)
            elif bad=='learning_cls':chosen.get('learnings')[0].cls='Custom'
            elif bad=='learning_extra':chosen.get('learnings')[0].set('extra',1)
            elif bad=='learning_missing':del chosen.get('learnings')[0].ivars['@note']
            elif bad=='level_type':chosen.get('learnings')[0].set('level',1.5)
            elif bad=='skill_type':chosen.get('learnings')[0].set('skill_id',True)
            elif bad=='note_type':chosen.get('learnings')[0].set('note',5)
            elif bad=='alias':chosen.set('learnings',[chosen.get('learnings')[0]]*2)
            elif bad=='shared':root[2].set('learnings',chosen.get('learnings'))
            else:chosen.set('learnings',[entry(1,i%2+1) for i in range(learning.MAX_LEARNINGS)])
            spec={'action':learning.ACTION,'expected_array_sha256':learning.digest(root),'expected_class_sha256':learning.digest(chosen),
                  'expected_learning_count':len(chosen.get('learnings')) if isinstance(chosen.get('learnings'),list) else 0,
                  'expected_skills_sha256':learning.digest(sk),'skill_id':3,'level':3,'class_id':1}
            with self.subTest(bad=bad),self.assertRaises(ValueError):apply(root,spec,sk)
            if bad=='budget':
                self.assertFalse(learning.snapshot(root,sk,1)['append_supported']);continue
            with self.assertRaises(ValueError):learning.snapshot(root,sk,1)
        # Other classes may carry any shape of their own learnings; only the selected class is inspected.
        root=classes();root[2].get('learnings').append(entry(1,None));sk=skills();apply(root,mutation(root,sk),sk)

    def test_stale_hashes_count_and_schema_refuse(self):
        for key,value in (('expected_array_sha256','0'*64),('expected_class_sha256','0'*64),('expected_skills_sha256','0'*64),
                          ('expected_learning_count',0),('expected_learning_count',2),('expected_learning_count',True),('expected_learning_count','1'),
                          ('action','append_database_entry'),('extra',1)):
            root=classes();sk=skills();spec=mutation(root,sk);spec[key]=value;before=marshal_rb.dump(root)
            with self.subTest(key=key),self.assertRaises(ValueError):apply(root,spec,sk)
            self.assertEqual(marshal_rb.dump(root),before)
        for drop in learning.NATIVE_FIELDS:
            root=classes();sk=skills();spec=mutation(root,sk);del spec[drop]
            with self.subTest(drop=drop),self.assertRaises(ValueError):apply(root,spec,sk)

    def test_changes_after_snapshot_make_spec_stale(self):
        root=classes();sk=skills();spec=mutation(root,sk)
        sk[1].set('name',S('Renamed'))
        with self.assertRaises(ValueError):apply(root,spec,sk)
        root=classes();sk=skills();spec=mutation(root,sk)
        root[2].set('name',S('Other'))
        with self.assertRaises(ValueError):apply(root,spec,sk)
        root=classes();sk=skills();spec=mutation(root,sk)
        root[1].get('learnings')[0].set('level',2)
        with self.assertRaises(ValueError):apply(root,spec,sk)

    def test_snapshot_reports_hashes_count_list_and_ranges(self):
        root=classes();sk=skills(4);snap=learning.snapshot(root,sk,1)
        self.assertEqual((snap['array_sha256'],snap['class_sha256'],snap['skills_sha256']),(learning.digest(root),learning.digest(root[1]),learning.digest(sk)))
        self.assertEqual((snap['learning_count'],snap['valid_skill_id_range'],snap['valid_level_range'],snap['class_count']),(1,[1,4],[1,99],2))
        self.assertEqual(snap['learnings'][0]['skill_id'],1);self.assertEqual(snap['learnings'][0]['skill_name'],'Template skills')
        self.assertTrue(snap['append_supported'])
        with self.assertRaises(ValueError):learning.snapshot(root,sk,3)

    def test_native_mutation_locator_rules(self):
        root=classes();sk=skills();spec=mutation(root,sk);del spec['class_id']
        self.assertEqual(learning.native_mutation({'table':'classes','id':2},spec)['class_id'],2)
        for locator in ({'table':'classes'},{'table':'skills','id':1},{'table':'classes','id':0},{'table':'classes','id':True},{'table':'classes','id':1,'x':1},None):
            with self.subTest(locator=locator),self.assertRaises(ValueError):learning.native_mutation(locator,spec)
        with self.assertRaises(ValueError):learning.native_mutation({'table':'classes','id':1},{**spec,'class_id':2})

    def test_candidate_verifier_rejects_tampering(self):
        before=classes();sk=skills();spec=mutation(before,sk)
        for bad in ('prefix','other_class','other_field','new_level','new_skill','new_note','extra_learning','missing','shape','reorder'):
            after=marshal_rb.load(marshal_rb.dump(before));apply(after,spec,sk)
            learning.verify_transition(before,after,spec,sk)
            if bad=='prefix':after[1].get('learnings')[0].set('level',9)
            elif bad=='other_class':after[2].set('name',S('Changed'))
            elif bad=='other_field':after[1].set('note',S('changed'))
            elif bad=='new_level':after[1].get('learnings')[-1].set('level',4)
            elif bad=='new_skill':after[1].get('learnings')[-1].set('skill_id',2)
            elif bad=='new_note':after[1].get('learnings')[-1].set('note',S('<tag>'))
            elif bad=='extra_learning':after[1].get('learnings').append(entry(5,2))
            elif bad=='missing':after[1].get('learnings').pop()
            elif bad=='shape':after.append(klass(3))
            else:after[1].get('learnings').reverse()
            with self.subTest(bad=bad),self.assertRaises(ValueError):learning.verify_transition(before,after,spec,sk)

    def test_apply_needs_native_path_and_dispatch(self):
        root=classes();sk=skills();spec=mutation(root,sk)
        with self.assertRaises(ValueError):learning.apply(root,spec)
        with self.assertRaises(ValueError):entries.apply(root,spec)


def prelude():
    fixture=(ROOT/'tests/project_reader/make_fixture.rb').read_text()
    return 'module RPG'+fixture.split('module RPG',1)[1].split('actor =',1)[0]+'\n'


CLASS_RUBY='''module RPG; class Class; class Learning; end; end; end
def fill(obj,h) h.each{|k,v|obj.instance_variable_set("@#{k}",v)}; obj end
def learn(level,skill_id) fill(RPG::Class::Learning.new,level:level,skill_id:skill_id,note:"") end
def klass(id,name,learnings)
  fill(RPG::Class.new,id:id,name:name,icon_index:0,description:"",features:[],note:"<keep>",exp_params:[30,20,30,30],
       params:Table.new(8,3,1,(1..24).to_a),learnings:learnings)
end
File.binwrite(ARGV[0]+"/Data/Classes.rvdata2",Marshal.dump([nil,klass(1,"Knight",[learn(1,1)]),klass(2,"Mage",[])]))
'''


def write_native(case):
    for name,source in (('tables.rb',table_tests.AppendCopyTests.RUBY),('classes.rb',prelude()+CLASS_RUBY)):
        script=case.base/name;script.write_text(source,encoding='utf-8')
        subprocess.run(['ruby',str(script),str(case.game)],check=True,capture_output=True)


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native fixtures and extraction')
class LearningCopyTests(unittest.TestCase):
    def setUp(self):
        region_fixtures.RegionCopyTests.setUp(self)
        write_native(self)
        self.index=self.base/'learning-index'
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)

    stage=region_fixtures.RegionCopyTests.stage

    def spec_mutation(self,class_id=1,**over):
        root,_=backend.load(self.game/'Data/Classes.rvdata2');sk,_=backend.load(self.game/'Data/Skills.rvdata2')
        spec={'action':learning.ACTION,'expected_array_sha256':learning.digest(root),'expected_class_sha256':learning.digest(root[class_id]),
              'expected_learning_count':len(root[class_id].get('learnings')),'expected_skills_sha256':learning.digest(sk),'skill_id':2,'level':4,**over}
        return root,sk,spec

    def write(self,mut=None,class_id=1,**over):
        root,sk,spec=self.spec_mutation(class_id,**over)
        change={'kind':'database_entry','locator':{'table':'classes','id':class_id},'proposal':'Class learns one reviewed skill.','mutation':mut or spec}
        self.spec={'changes':[change]};self.specfile.write_text(json.dumps(self.spec));return root,sk

    def test_complete_copy_chain(self):
        from vxace_copy_patcher import current_inventory
        before=current_inventory(self.game);root,sk=self.write();result=self.stage()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(current_inventory(self.game),before)
        final,_=backend.load(self.base/'copy/Data/Classes.rvdata2')
        mut=learning.native_mutation({'table':'classes','id':1},self.spec['changes'][0]['mutation'])
        learning.verify_transition(root,final,mut,sk)
        made=final[1].get('learnings')
        self.assertEqual([(x.get('level'),x.get('skill_id'),x.get('note').data) for x in made],[(1,1,b''),(4,2,b'')])
        self.assertEqual(marshal_rb.dump(final[2]),marshal_rb.dump(root[2]))
        for name in ('Skills','System'):
            self.assertEqual((self.base/('copy/Data/%s.rvdata2'%name)).read_bytes(),(self.game/('Data/%s.rvdata2'%name)).read_bytes())
        audit=json.loads((self.base/'audit/audit.json').read_text())
        record=audit['changes'][0]['entry']
        self.assertTrue(record['approved_class_learning_verified']);self.assertTrue(record['skills_unchanged'])
        self.assertEqual((record['before']['learning_count'],record['after']['learning_count']),(1,2))
        self.assertTrue((self.base/'audit/post-validation/validation.json').is_file())
        impact=json.loads((self.base/'audit/structural-impact.json').read_text())['impacts'][0]
        self.assertEqual((impact['target']['class_id'],impact['target']['skill_id'],impact['target']['level']),(1,2,4))
        self.assertEqual(impact['learning_count_after'],2);self.assertTrue(any('retroactive' in text for text in impact['limitations']))

    def test_first_learning_on_empty_class(self):
        self.write(class_id=2,skill_id=1,level=1)
        self.assertEqual(self.stage().returncode,0)
        final,_=backend.load(self.base/'copy/Data/Classes.rvdata2')
        self.assertEqual([(x.get('level'),x.get('skill_id')) for x in final[2].get('learnings')],[(1,1)])

    def test_stale_duplicate_bad_skill_and_bad_level_refuse_before_copy(self):
        self.write();good=self.spec['changes'][0]['mutation']
        for key,value in (('expected_array_sha256','0'*64),('expected_class_sha256','0'*64),('expected_skills_sha256','0'*64),('expected_learning_count',5),
                          ('skill_id',1),('skill_id',3),('skill_id',0),('level',0),('level',100),('extra',1)):
            self.write(mut={**good,key:value});self.assertNotEqual(self.stage().returncode,0,key)
        self.write();self.spec['changes'][0]['locator']['id']=3;self.specfile.write_text(json.dumps(self.spec));self.assertNotEqual(self.stage().returncode,0)
        self.assertFalse((self.base/'copy').exists());self.assertFalse((self.base/'audit').exists())

    def test_backend_combinations_and_second_append_refuse(self):
        self.write()
        for backend_name,extra in (('ruby',()),('python',('--no-reindex',))):
            self.assertNotEqual(self.stage(backend_name,extra).returncode,0)
            self.assertFalse((self.base/'copy').exists())
        good=self.spec['changes'][0]
        def attempt(changes):
            self.spec['changes']=changes;self.specfile.write_text(json.dumps(self.spec))
            self.assertNotEqual(self.stage().returncode,0);self.assertFalse((self.base/'copy').exists())
        attempt([good,good])
        attempt([good,{'kind':'database','locator':{'table':'classes','id':1},'proposal':'x','mutation':{'field':'name','value':'Hero'}}])
        attempt([good,{'kind':'database','locator':{'table':'skills','id':1},'proposal':'x','mutation':{'field':'mp_cost','value':1}}])
        root,sk=self.write()
        attempt([good,{'kind':'database_entry','locator':{'table':'skills'},'proposal':'x','mutation':{'action':'append_database_entry'}}])
        bad=json.loads(json.dumps(good));bad['locator']={'table':'classes'};attempt([bad])
        bad=json.loads(json.dumps(good));bad['locator']={'table':'skills','id':1};attempt([bad])
        bad=json.loads(json.dumps(good));bad['mutation']['action']='append_database_entry';attempt([bad])

    def test_snapshot_cli_reports_hashes_and_refuses_misuse(self):
        output=self.base/'snap-classes'
        base=[str(self.index),'--project',str(self.game),'--table','classes']
        self.assertEqual(entries.main(base+['--class-id','1','--output',str(output)]),0)
        result=json.loads((output/'item-entry-snapshot.json').read_text())
        root,_=backend.load(self.game/'Data/Classes.rvdata2');sk,_=backend.load(self.game/'Data/Skills.rvdata2')
        self.assertEqual((result['table'],result['class_id'],result['learning_count'],result['valid_skill_id_range']),('classes',1,1,[1,2]))
        self.assertEqual((result['array_sha256'],result['class_sha256'],result['skills_sha256']),(learning.digest(root),learning.digest(root[1]),learning.digest(sk)))
        self.assertEqual(result['learnings'][0]['skill_id'],1)
        self.assertEqual(entries.main(base+['--class-id','3','--output',str(self.base/'x1')]),2)
        self.assertEqual(entries.main(base+['--class-id','1','--output',str(self.game/'rep')]),2)
        self.assertFalse((self.game/'rep').exists())
        with self.assertRaises(SystemExit):entries.main(base+['--output',str(self.base/'x2')])
        with self.assertRaises(SystemExit):entries.main(base+['--class-id','1','--template-id','1','--output',str(self.base/'x3')])
        with self.assertRaises(SystemExit):entries.main([str(self.index),'--project',str(self.game),'--table','skills','--template-id','1','--class-id','1','--output',str(self.base/'x4')])


if __name__=='__main__':unittest.main()
