import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_database_append as append
import vxace_database_entries as entries
import vxace_python_mutator as backend
import test_regions as region_fixtures
import test_database_append as table_tests
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject

S=backend.convert


def command(code=0,indent=0,params=None):
    return RubyObject('RPG::EventCommand',{'@code':code,'@indent':indent,'@parameters':[] if params is None else params})


def condition(**valid):
    values={'turn_ending':False,'turn_valid':False,'enemy_valid':False,'actor_valid':False,'switch_valid':False,
            'turn_a':0,'turn_b':0,'enemy_index':0,'enemy_hp':50,'actor_id':1,'actor_hp':50,'switch_id':1,**valid}
    return RubyObject('RPG::Troop::Page::Condition',{'@'+k:v for k,v in values.items()})


def page(cond=None,commands=None):
    return RubyObject('RPG::Troop::Page',{'@condition':cond or condition(),'@span':0,'@list':commands if commands is not None else [command()]})


def member(enemy_id=1,x=100,y=120,hidden=False):
    return RubyObject('RPG::Troop::Member',{'@enemy_id':enemy_id,'@x':x,'@y':y,'@hidden':hidden})


def troop(identifier,pages=None,members=None):
    return RubyObject('RPG::Troop',{'@id':identifier,'@name':S('Template troop'),'@members':[member()] if members is None else members,
                                    '@pages':[page()] if pages is None else pages})


def troops():
    return [None,troop(1),troop(2)]


def enemies(count=2):
    return [None]+[table_tests.make('enemies',i) for i in range(1,count+1)]


MEMBERS=[{'enemy_id':1,'x':200,'y':300,'hidden':False},{'enemy_id':2,'x':0,'y':416,'hidden':True}]


def mutation(root,foes,**overrides):
    snap=append.snapshot(root,'troops',1,foes)
    return {'action':'append_database_entry','template_id':1,'new_id':len(root),
            'expected_array_sha256':snap['array_sha256'],'expected_template_sha256':snap['template_sha256'],
            'expected_enemies_sha256':snap['enemies_sha256'],
            'overrides':{'name':'Bat Pair','members':MEMBERS,**overrides}}


class TroopUnitTests(unittest.TestCase):
    def test_happy_path_clones_blank_page_rebuilds_members_and_adds_no_note(self):
        root=troops();foes=enemies();before=marshal_rb.dump(root);spec=mutation(root,foes)
        root.append(append.new_entry(root,'troops',spec,foes))
        made=root[-1]
        self.assertEqual(marshal_rb.dump(root[:-1]),before)
        self.assertEqual((made.cls,made.get('id'),made.get('name').data),('RPG::Troop',3,b'Bat Pair'))
        self.assertEqual([(m.get('enemy_id'),m.get('x'),m.get('y'),m.get('hidden')) for m in made.get('members')],[(1,200,300,False),(2,0,416,True)])
        self.assertTrue(all(m.cls=='RPG::Troop::Member' for m in made.get('members')))
        self.assertEqual(set(made.ivars),{'@id','@name','@members','@pages'})
        self.assertNotIn('@note',made.ivars)
        self.assertEqual(marshal_rb.dump(made.get('pages')),marshal_rb.dump(root[1].get('pages')))
        self.assertIsNot(made.get('pages')[0],root[1].get('pages')[0])
        self.assertEqual(root[1].get('members')[0].get('x'),100)
        append.verify_transition(marshal_rb.load(before),root,'troops',spec,foes)

    def test_apply_requires_native_path_for_enemies(self):
        root=troops();spec=mutation(root,enemies())
        with self.assertRaises(ValueError):append.apply(root,spec)

    def test_snapshot_reports_enemies_hash_range_and_blank_page(self):
        foes=enemies(3);snap=append.snapshot(troops(),'troops',1,foes)
        self.assertEqual(snap['enemies_sha256'],append.digest(foes))
        self.assertEqual((snap['valid_enemy_id_range'],snap['template_page_blank'],snap['next_id']),([1,3],True,3))
        self.assertFalse(snap['template_note_present']);self.assertEqual(snap['forced_values'],{'id':'new_id'})
        self.assertEqual(snap['supported_overrides'],['name','members'])
        with self.assertRaises(ValueError):append.snapshot(troops(),'troops',1)

    def test_member_validation_refuses(self):
        good=MEMBERS[0]
        bad_lists=[[],[good]*9,[{**good,'enemy_id':0}],[{**good,'enemy_id':3}],[{**good,'enemy_id':-1}],[{**good,'enemy_id':True}],[{**good,'enemy_id':'1'}],
                   [{**good,'x':-1}],[{**good,'x':545}],[{**good,'y':-1}],[{**good,'y':417}],[{**good,'x':1.0}],[{**good,'y':True}],
                   [{**good,'hidden':1}],[{**good,'hidden':'no'}],[{**good,'hidden':None}],
                   [{'enemy_id':1,'x':1,'y':1}],[{**good,'extra':1}],['x'],{'enemy_id':1},None]
        for members in bad_lists:
            root=troops();foes=enemies();spec=mutation(root,foes);spec['overrides']['members']=members;before=marshal_rb.dump(root)
            with self.subTest(members=str(members)[:70]),self.assertRaises(ValueError):append.new_entry(root,'troops',spec,foes)
            self.assertEqual(marshal_rb.dump(root),before)
        root=troops();foes=enemies();spec=mutation(root,foes);spec['overrides']['members']=[good]*8
        self.assertEqual(len(append.new_entry(root,'troops',spec,foes).get('members')),8)

    def test_nil_enemy_slot_refuses(self):
        root=troops();foes=enemies();spec=mutation(root,foes)
        foes[2]=None
        with self.assertRaises(ValueError):append.new_entry(root,'troops',spec,foes)
        with self.assertRaises(ValueError):append.troop_members([MEMBERS[1]],[None,foes[1],None])

    def test_name_and_override_key_refusals(self):
        for bad in ({'name':''},{'name':'x'*101},{'name':'a\nb'},{'name':5},{'note':'x'},{'pages':[]},{'id':9},{'features':[]}):
            root=troops();foes=enemies();spec=mutation(root,foes);spec['overrides'].update(bad)
            with self.subTest(bad=bad),self.assertRaises(ValueError):append.new_entry(root,'troops',spec,foes)
        for drop in ('name','members'):
            root=troops();foes=enemies();spec=mutation(root,foes);del spec['overrides'][drop]
            with self.subTest(drop=drop),self.assertRaises(ValueError):append.new_entry(root,'troops',spec,foes)

    def test_spec_schema_hashes_and_ids_refuse(self):
        for key,value in (('expected_enemies_sha256','0'*64),('expected_array_sha256','0'*64),('expected_template_sha256','0'*64),
                          ('new_id',2),('new_id',4),('new_id',True),('template_id',0),('template_id',3),('action','append_key_item'),('extra',1)):
            root=troops();foes=enemies();spec=mutation(root,foes);spec[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):append.new_entry(root,'troops',spec,foes)
        root=troops();foes=enemies();spec=mutation(root,foes);del spec['expected_enemies_sha256']
        with self.assertRaises(ValueError):append.new_entry(root,'troops',spec,foes)

    def test_enemies_hash_mismatch_when_enemies_change(self):
        root=troops();foes=enemies();spec=mutation(root,foes)
        foes[1].set('name',S('Changed'))
        with self.assertRaises(ValueError):append.new_entry(root,'troops',spec,foes)
        with self.assertRaises(ValueError):append.new_entry(root,'troops',spec,None)

    def test_non_blank_template_pages_refuse(self):
        cases={
            'condition_turn':[page(condition(turn_valid=True))],'condition_enemy':[page(condition(enemy_valid=True))],
            'condition_actor':[page(condition(actor_valid=True))],'condition_switch':[page(condition(switch_valid=True))],
            'condition_turn_ending':[page(condition(turn_ending=True))],
            'extra_command':[page(commands=[command(101,0,['',0,0,2]),command()])],
            'only_text_command':[page(commands=[command(101,0,['',0,0,2])])],
            'empty_list':[page(commands=[])],
            'terminator_indent':[page(commands=[command(0,1)])],
            'terminator_params':[page(commands=[command(0,0,[1])])],
            'two_pages':[page(),page()],'no_pages':[],
        }
        for name,pages in cases.items():
            root=[None,troop(1,pages),troop(2)];foes=enemies()
            with self.subTest(case=name),self.assertRaises(ValueError):append.snapshot(root,'troops',1,foes)
        for name in ('page_cls','cond_extra','cmd_extra','member_extra','member_type','span_type'):
            root=troops();t=root[1];pg=t.get('pages')[0]
            if name=='page_cls':pg.cls='Custom'
            elif name=='cond_extra':pg.get('condition').set('extra',1)
            elif name=='cmd_extra':pg.get('list')[0].set('extra',1)
            elif name=='member_extra':t.get('members')[0].set('extra',1)
            elif name=='member_type':t.get('members')[0].set('hidden',1)
            else:pg.set('span','0')
            with self.subTest(case=name),self.assertRaises(ValueError):append.snapshot(root,'troops',1,enemies())
        root=troops();root[1].set('note',S('x'))
        with self.assertRaises(ValueError):append.snapshot(root,'troops',1,enemies())
        root=troops();del root[1].ivars['@pages']
        with self.assertRaises(ValueError):append.snapshot(root,'troops',1,enemies())

    def test_blank_template_with_no_members_is_allowed(self):
        root=[None,troop(1,members=[]),troop(2)];foes=enemies()
        self.assertEqual(append.snapshot(root,'troops',1,foes)['template_member_count'],0)

    def test_array_admission(self):
        bad=troops();bad[2].set('id',9);alias=troops();alias[2]=alias[1]
        for root in ([],[None],{},[troop(1),troop(2)],bad,alias):
            with self.subTest(root=str(root)[:50]),self.assertRaises(ValueError):append.database_array(root,'troops')
        with self.assertRaises(ValueError):append.snapshot(troops(),'troops',1,[None,table_tests.make('skills')])

    def test_candidate_verifier_rejects_tampering(self):
        before=troops();foes=enemies();spec=mutation(before,foes)
        for bad in ('prefix','members','name','page','extra','missing','note'):
            after=marshal_rb.load(marshal_rb.dump(before));after.append(append.new_entry(after,'troops',spec,foes))
            append.verify_transition(before,after,'troops',spec,foes)
            if bad=='prefix':after[2].set('name',S('changed'))
            elif bad=='members':after[-1].get('members')[0].set('x',1)
            elif bad=='name':after[-1].set('name',S('Other'))
            elif bad=='page':after[-1].get('pages')[0].get('list').append(command(101,0,['',0,0,2]))
            elif bad=='note':after[-1].set('note',S('<tag>'))
            elif bad=='extra':after.append(troop(5))
            else:after.pop()
            with self.subTest(bad=bad),self.assertRaises(ValueError):append.verify_transition(before,after,'troops',spec,foes)


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native fixtures and extraction')
class TroopCopyTests(unittest.TestCase):
    RUBY='''module RPG
  class Troop; class Member; end; class Page; class Condition; end; end; end
  class EventCommand; end
end
def fill(obj,h) h.each{|k,v|obj.instance_variable_set("@#{k}",v)}; obj end
def cmd(code,indent,params) fill(RPG::EventCommand.new,code:code,indent:indent,parameters:params) end
def cond(over={}) fill(RPG::Troop::Page::Condition.new,{turn_ending:false,turn_valid:false,enemy_valid:false,actor_valid:false,switch_valid:false,turn_a:0,turn_b:0,enemy_index:0,enemy_hp:50,actor_id:1,actor_hp:50,switch_id:1}.merge(over)) end
def page(over={},list=[cmd(0,0,[])]) fill(RPG::Troop::Page.new,condition:cond(over),span:0,list:list) end
def mem(eid,x,y) fill(RPG::Troop::Member.new,enemy_id:eid,x:x,y:y,hidden:false) end
def troop(id,name,pages) fill(RPG::Troop.new,id:id,name:name,members:[mem(1,100,120)],pages:pages) end
list=[nil,troop(1,"Blank",[page]),troop(2,"Logic",[page({turn_valid:true},[cmd(101,0,["",0,0,2]),cmd(0,0,[])])])]
File.binwrite(ARGV[0]+"/Data/Troops.rvdata2",Marshal.dump(list))
'''

    def setUp(self):
        region_fixtures.RegionCopyTests.setUp(self)
        for name,source in (('tables.rb',table_tests.AppendCopyTests.RUBY),('troops.rb',self.RUBY)):
            script=self.base/name;script.write_text(source,encoding='utf-8')
            subprocess.run(['ruby',str(script),str(self.game)],check=True,capture_output=True)
        self.index=self.base/'troop-index'
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)

    stage=region_fixtures.RegionCopyTests.stage

    def mutation(self,template_id=1,**overrides):
        troop_root,_=backend.load(self.game/'Data/Troops.rvdata2');foes,_=backend.load(self.game/'Data/Enemies.rvdata2')
        # Hash directly so a deliberately non-blank template can still be specified (the tools must then refuse).
        return troop_root,{'action':'append_database_entry','template_id':template_id,'new_id':len(troop_root),
                           'expected_array_sha256':append.digest(troop_root),'expected_template_sha256':append.digest(troop_root[template_id]),
                           'expected_enemies_sha256':append.digest(foes),
                           'overrides':{'name':'Bat Pair','members':MEMBERS,**overrides}}

    def write(self,mut=None,**kw):
        root,spec=self.mutation(**kw)
        change={'kind':'database_entry','locator':{'table':'troops'},'proposal':'Append one blank-page troop.','mutation':mut or spec}
        self.spec={'changes':[change]};self.specfile.write_text(json.dumps(self.spec));return root

    def test_complete_copy_chain(self):
        from vxace_copy_patcher import current_inventory
        before=current_inventory(self.game);root=self.write();result=self.stage()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(current_inventory(self.game),before)
        final,_=backend.load(self.base/'copy/Data/Troops.rvdata2');foes,_=backend.load(self.game/'Data/Enemies.rvdata2')
        mut=self.spec['changes'][0]['mutation']
        append.verify_transition(root,final,'troops',mut,foes)
        self.assertEqual(marshal_rb.dump(final[:-1]),marshal_rb.dump(root))
        self.assertEqual((final[-1].get('id'),final[-1].get('name').data,len(final[-1].get('members'))),(3,b'Bat Pair',2))
        self.assertEqual((self.base/'copy/Data/Enemies.rvdata2').read_bytes(),(self.game/'Data/Enemies.rvdata2').read_bytes())
        audit=json.loads((self.base/'audit/audit.json').read_text())
        self.assertTrue(audit['changes'][0]['entry']['approved_template_clone_verified'])
        self.assertTrue((self.base/'audit/post-validation/validation.json').is_file())
        impact=json.loads((self.base/'audit/structural-impact.json').read_text())['impacts'][0]
        self.assertEqual((impact['target']['table'],impact['target']['new_id']),('troops',3))
        self.assertEqual(impact['troop']['template_troop']['page_count'],1)
        self.assertEqual([r['enemy_id'] for r in impact['troop']['referenced_enemies']],[1,2])
        self.assertFalse(impact['troop']['template_troop']['members_copied'])
        self.assertTrue(any('not wired' in text for text in impact['limitations']))

    def test_non_blank_template_stale_hashes_and_bad_members_refuse_before_copy(self):
        root=self.write(template_id=2);self.assertNotEqual(self.stage().returncode,0)
        self.write();good=self.spec['changes'][0]['mutation']
        for key,value in (('expected_enemies_sha256','0'*64),('expected_array_sha256','0'*64),('new_id',9)):
            self.write(mut={**good,key:value});self.assertNotEqual(self.stage().returncode,0)
        bad=json.loads(json.dumps(good));bad['overrides']['members']=[{'enemy_id':3,'x':1,'y':1,'hidden':False}]
        self.write(mut=bad);self.assertNotEqual(self.stage().returncode,0)
        bad=json.loads(json.dumps(good));bad['overrides']['note']='x'
        self.write(mut=bad);self.assertNotEqual(self.stage().returncode,0)
        self.assertFalse((self.base/'copy').exists());self.assertFalse((self.base/'audit').exists())

    def test_backend_combinations_and_second_append_refuse(self):
        self.write()
        for backend_name,extra in (('ruby',()),('python',('--no-reindex',))):
            self.assertNotEqual(self.stage(backend_name,extra).returncode,0)
            self.assertFalse((self.base/'copy').exists())
        good=self.spec['changes'][0]
        self.spec['changes']=[good,good];self.specfile.write_text(json.dumps(self.spec))
        self.assertNotEqual(self.stage().returncode,0);self.assertFalse((self.base/'copy').exists())

    def test_snapshot_cli_reports_enemies_hash_and_refuses_non_blank_template(self):
        output=self.base/'snap-troops'
        args=[str(self.index),'--project',str(self.game),'--table','troops','--template-id','1','--output',str(output)]
        self.assertEqual(entries.main(args),0)
        result=json.loads((output/'item-entry-snapshot.json').read_text())
        foes,_=backend.load(self.game/'Data/Enemies.rvdata2')
        self.assertEqual((result['table'],result['next_id'],result['template_page_blank']),('troops',3,True))
        self.assertEqual((result['enemies_sha256'],result['valid_enemy_id_range']),(append.digest(foes),[1,2]))
        self.assertEqual(entries.main([str(self.index),'--project',str(self.game),'--table','troops','--template-id','2','--output',str(self.base/'snap2')]),2)


if __name__=='__main__':unittest.main()
