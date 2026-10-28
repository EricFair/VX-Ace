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
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject

FILES={'enemies':'Enemies','skills':'Skills','states':'States','weapons':'Weapons','armors':'Armors'}
CLASSES={'enemies':'Enemy','skills':'Skill','states':'State','weapons':'Weapon','armors':'Armor'}
S=backend.convert


def feature(code=21,data_id=2,value=1.0):
    return RubyObject('RPG::BaseItem::Feature',{'@code':code,'@data_id':data_id,'@value':value})


def make(table,identifier=1):
    values={'id':identifier,'name':S('Template '+table),'icon_index':7,'description':S('Template text'),
            'features':[feature()],'note':S('<fixture notetag>')}
    # Editor-saved schema: enemies lack icon_index/description but keep hit/eva; states lack description.
    if table=='enemies':
        del values['icon_index'];del values['description']
        values.update(battler_name=S('Bat'),battler_hue=0,params=[100,0,10,5,5,5,20,5],exp=5,gold=3,hit=95,eva=5,
            drop_items=[RubyObject('RPG::Enemy::DropItem',{'@kind':1,'@data_id':1,'@denominator':4}) for _ in range(3)],
            actions=[RubyObject('RPG::Enemy::Action',{'@condition_type':0,'@condition_param1':0,'@condition_param2':0,'@skill_id':1,'@rating':5})])
    elif table=='skills':
        values.update(scope=1,occasion=1,speed=0,success_rate=100,repeats=1,tp_gain=0,hit_type=1,animation_id=3,
            effects=[RubyObject('RPG::UsableItem::Effect',{'@code':21,'@data_id':1,'@value1':1.0,'@value2':0.0})],
            damage=RubyObject('RPG::UsableItem::Damage',{'@type':1,'@element_id':2,'@formula':S('a.atk * 4 - b.def * 2'),'@variance':20,'@critical':False}),
            stype_id=1,mp_cost=5,tp_cost=0,message1=S('%s attacks!'),message2=S(''),required_wtype_id1=0,required_wtype_id2=0)
    elif table=='states':
        del values['description']
        values.update(restriction=0,priority=50,remove_at_battle_end=True,remove_by_restriction=False,auto_removal_timing=1,
            min_turns=2,max_turns=4,remove_by_damage=False,release_by_damage=False,chance_by_damage=100,remove_by_walking=False,steps_to_remove=100,
            message1=S('is poisoned'),message2=S(''),message3=S(''),message4=S('recovers'))
    elif table=='weapons':
        values.update(price=100,etype_id=0,params=[0,0,10,0,0,0,0,0],wtype_id=1,animation_id=1)
    else:
        values.update(price=80,etype_id=1,params=[0,0,0,5,0,0,0,0],atype_id=1)
    return RubyObject('RPG::'+CLASSES[table],{'@'+k:v for k,v in values.items()})


def fixture(table):
    second=make(table,2);second.set('custom_existing_field',S('preserve'))
    return [None,make(table),second]


OVERRIDES={
    'enemies':{'name':'Cave Bat','params':[180,0,14,8,10,10,22,10],'exp':12,'gold':8,'battler_name':'Bat','battler_hue':90},
    'skills':{'name':'Rend','description':'Tears.','icon_index':9,'mp_cost':7,'tp_cost':3,'message1':'%s rends!','damage_formula':'a.atk * 5 - b.def * 2','damage_variance':10,'damage_critical':True},
    'states':{'name':'Bleed','message1':'bleeds','priority':60,'min_turns':1,'max_turns':3,'auto_removal_timing':2},
    'weapons':{'name':'Iron Sword','description':'A sword.','icon_index':10,'price':250,'params':[0,0,15,0,0,0,0,-5]},
    'armors':{'name':'Iron Shield','description':'A shield.','icon_index':11,'price':200,'params':[0,0,0,12,0,0,0,0]},
}


def mutation(table,root,**overrides):
    snap=append.snapshot(root,table,1)
    return {'action':'append_database_entry','template_id':1,'new_id':len(root),
            'expected_array_sha256':snap['array_sha256'],'expected_template_sha256':snap['template_sha256'],
            'overrides':{**OVERRIDES[table],**overrides}}


class AppendUnitTests(unittest.TestCase):
    def test_every_table_clones_template_overrides_whitelist_and_forces_empty_note(self):
        for table in FILES:
            with self.subTest(table=table):
                root=fixture(table);before=marshal_rb.dump(root);spec=mutation(table,root)
                backend.apply(root,{'type':'database_entry','mutation':spec})
                self.assertEqual(marshal_rb.dump(root[:-1]),before)
                made=root[-1];tpl=root[1]
                self.assertEqual((made.cls,made.get('id')),(tpl.cls,3))
                self.assertEqual(made.get('name').data,OVERRIDES[table]['name'].encode())
                self.assertEqual(made.get('note').data,b'')
                self.assertEqual(tpl.get('note').data,b'<fixture notetag>')
                self.assertEqual(marshal_rb.dump(made.get('features')),marshal_rb.dump(tpl.get('features')))
                self.assertIsNot(made.get('features'),tpl.get('features'))
                self.assertEqual(root[2].get('custom_existing_field').data,b'preserve')
                append.verify_transition(marshal_rb.load(before),root,table,spec)

    def test_per_table_specific_values_and_inheritance(self):
        root=fixture('enemies');append.apply(root,mutation('enemies',root))
        self.assertEqual((root[-1].get('params'),root[-1].get('exp'),root[-1].get('gold'),root[-1].get('battler_hue')),([180,0,14,8,10,10,22,10],12,8,90))
        self.assertEqual(len(root[-1].get('drop_items')),3);self.assertEqual(root[-1].get('actions')[0].get('skill_id'),1)
        self.assertEqual((root[-1].get('hit'),root[-1].get('eva')),(95,5))
        self.assertIsNone(root[-1].get('icon_index'))
        root=fixture('skills');append.apply(root,mutation('skills',root));d=root[-1].get('damage')
        self.assertEqual((d.get('formula').data,d.get('variance'),d.get('critical'),d.get('type'),d.get('element_id')),(b'a.atk * 5 - b.def * 2',10,True,1,2))
        self.assertEqual(root[1].get('damage').get('variance'),20)
        self.assertEqual(root[-1].get('effects')[0].get('code'),21)
        self.assertEqual((root[-1].get('mp_cost'),root[-1].get('tp_cost')),(7,3))
        root=fixture('states');append.apply(root,mutation('states',root))
        self.assertEqual((root[-1].get('priority'),root[-1].get('min_turns'),root[-1].get('max_turns'),root[-1].get('auto_removal_timing')),(60,1,3,2))
        self.assertEqual(root[-1].get('message4').data,b'recovers')

    def test_snapshot_reports_inherited_summary_and_supported_overrides(self):
        snap=append.snapshot(fixture('enemies'),'enemies',1)
        self.assertEqual(snap['next_id'],3);self.assertEqual(snap['inherited']['features'],[[21,2,1.0]])
        self.assertEqual(len(snap['inherited']['drop_items']),3);self.assertTrue(snap['template_note_present'])
        self.assertIn('params',snap['supported_overrides']);self.assertNotIn('note',snap['supported_overrides'])

    def test_stale_hash_wrong_id_and_bad_schema_keys_refuse_without_change(self):
        for table in FILES:
            for key,value in (('expected_array_sha256','0'*64),('expected_template_sha256','0'*64),('new_id',1),('new_id',4),
                              ('new_id',True),('new_id',1000),('template_id',0),('template_id',True),('action','append_key_item'),('field','price')):
                root=fixture(table);spec=mutation(table,root);spec[key]=value;before=marshal_rb.dump(root)
                with self.subTest(table=table,key=key,value=value),self.assertRaises(ValueError):append.apply(root,spec)
                self.assertEqual(marshal_rb.dump(root),before)

    def test_unknown_note_type_range_and_formula_overrides_refuse(self):
        cases={'enemies':[{'note':'x'},{'id':5},{'icon_index':1},{'description':'x'},{'params':[1]*7},{'params':[0,0,1,1,1,1,1,1]},
                          {'params':[1,0,1,1,1,1,1,1000]},{'params':[1,0,1,1,1,1,1,True]},{'exp':-1},{'gold':10**7},{'battler_hue':361},
                          {'battler_name':'a/b'},{'battler_name':'..x'},{'battler_name':'x'*101},{'name':''},{'name':'x'*101},{'name':'a\nb'},{'name':5}],
               'skills':[{'note':'x'},{'mp_cost':10000},{'tp_cost':101},{'damage_formula':'a.atk * rand(5)'},{'damage_formula':'v[1] ; 5'},
                         {'damage_formula':''},{'damage_formula':5},{'damage_variance':101},{'damage_critical':1},{'message1':'x'*201},
                         {'icon_index':4096},{'element_id':3},{'damage':1}],
               'states':[{'note':'x'},{'priority':101},{'min_turns':5,'max_turns':2},{'min_turns':10000},{'auto_removal_timing':3},{'message5':'x'},{'message2':'a\x00'},{'description':'x'}],
               'weapons':[{'note':'x'},{'price':-1},{'params':[1000]+[0]*7},{'params':[0]*7},{'exp':1},{'features':[]}],
               'armors':[{'note':'x'},{'price':10**7},{'params':[-1000]+[0]*7},{'atype_id':2},{'description':'x'*1001},{'description':'a\x01'}]}
        for table,items in cases.items():
            for bad in items:
                root=fixture(table);spec=mutation(table,root);spec['overrides'].update(bad);before=marshal_rb.dump(root)
                with self.subTest(table=table,bad=bad),self.assertRaises(ValueError):append.apply(root,spec)
                self.assertEqual(marshal_rb.dump(root),before)
        root=fixture('enemies');spec=mutation('enemies',root);del spec['overrides']['name']
        with self.assertRaises(ValueError):append.apply(root,spec)
        root=fixture('enemies');spec=mutation('enemies',root);spec['extra']=1
        with self.assertRaises(ValueError):append.apply(root,spec)

    def test_damage_overrides_require_damage_template_and_unsupported_schema_refuses(self):
        root=fixture('skills');root[1].get('damage').set('type',0)
        with self.assertRaises(ValueError):append.apply(root,mutation('skills',root))
        for table in FILES:
            for bad in ('extra','missing','features','feature_field','type','params'):
                root=fixture(table);sel=root[1]
                if bad=='extra':sel.set('custom',True)
                elif bad=='missing':del sel.ivars['@note']
                elif bad=='features':sel.set('features',[1])
                elif bad=='feature_field':sel.get('features')[0].set('extra',1)
                elif bad=='type':sel.set('name','plain str')
                elif table in ('enemies','weapons','armors'):sel.set('params',[1,2])
                else:continue
                with self.subTest(table=table,bad=bad),self.assertRaises(ValueError):append.snapshot(root,table,1)
        root=fixture('skills');root[1].get('damage').cls='CustomDamage'
        with self.assertRaises(ValueError):append.snapshot(root,'skills',1)
        root=fixture('skills');root[1].get('effects')[0].set('value1',float('nan'))
        with self.assertRaises(ValueError):append.snapshot(root,'skills',1)
        root=fixture('enemies');root[1].get('actions')[0].cls='Custom'
        with self.assertRaises(ValueError):append.snapshot(root,'enemies',1)

    def test_array_admission_and_unsupported_tables(self):
        bad=fixture('enemies');bad[2].set('id',9)
        alias=fixture('enemies');alias[2]=alias[1]
        for root in ([],[None],{},[make('enemies'),make('enemies',2)],[None,make('skills')],bad,alias):
            with self.subTest(root=str(root)[:60]),self.assertRaises(ValueError):append.database_array(root,'enemies')
        for table in ('items','actors','troops'):
            with self.assertRaises(ValueError):append.table_spec(table)
        full=[None]+[make('weapons',i) for i in range(1,1000)]
        self.assertFalse(append.snapshot(full,'weapons',1)['append_slot_supported'])
        with self.assertRaises(ValueError):append.apply(full,mutation('weapons',full))

    def test_candidate_verifier_rejects_tampering(self):
        before=fixture('skills');spec=mutation('skills',before)
        for bad in ('prefix','new_effect','new_name','extra','missing','note'):
            after=marshal_rb.load(marshal_rb.dump(before));append.apply(after,spec)
            append.verify_transition(before,after,'skills',spec)
            if bad=='prefix':after[2].set('custom_existing_field',S('changed'))
            elif bad=='new_effect':after[-1].set('effects',[])
            elif bad=='new_name':after[-1].set('name',S('Different'))
            elif bad=='note':after[-1].set('note',S('<tag>'))
            elif bad=='extra':after.append(make('skills',4))
            else:after.pop()
            with self.subTest(bad=bad),self.assertRaises(ValueError):append.verify_transition(before,after,'skills',spec)


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native fixtures and extraction')
class AppendCopyTests(unittest.TestCase):
    RUBY='''module RPG
  class Enemy; class DropItem; end; class Action; end; end
  class Skill; end; class State; end; class Weapon; end; class Armor; end
  class Troop; end
  class BaseItem; class Feature; end; end
  class UsableItem; class Damage; end; class Effect; end; end
end
def fill(obj,h) h.each{|k,v|obj.instance_variable_set("@#{k}",v)}; obj end
def feature; fill(RPG::BaseItem::Feature.new,code:21,data_id:2,value:1.0); end
def base(id,name); {id:id,name:name,icon_index:7,description:"Template text",features:[feature],note:"<fixture notetag>"}; end
def enemy(id)
  drops=(1..3).map{fill(RPG::Enemy::DropItem.new,kind:1,data_id:1,denominator:4)}
  acts=[fill(RPG::Enemy::Action.new,condition_type:0,condition_param1:0,condition_param2:0,skill_id:1,rating:5)]
  fill(RPG::Enemy.new,base(id,"Bat").reject{|k,_|k==:icon_index||k==:description}.merge(battler_name:"Bat",battler_hue:0,params:[100,0,10,5,5,5,20,5],exp:5,gold:3,hit:95,eva:5,drop_items:drops,actions:acts))
end
def skill(id)
  eff=fill(RPG::UsableItem::Effect.new,code:21,data_id:1,value1:1.0,value2:0.0)
  dmg=fill(RPG::UsableItem::Damage.new,type:1,element_id:2,formula:"a.atk * 4 - b.def * 2",variance:20,critical:false)
  fill(RPG::Skill.new,base(id,"Slash").merge(scope:1,occasion:1,speed:0,success_rate:100,repeats:1,tp_gain:0,hit_type:1,animation_id:3,
    effects:[eff],damage:dmg,stype_id:1,mp_cost:5,tp_cost:0,message1:"%s attacks!",message2:"",required_wtype_id1:0,required_wtype_id2:0))
end
def state(id)
  fill(RPG::State.new,base(id,"Poison").reject{|k,_|k==:description}.merge(restriction:0,priority:50,remove_at_battle_end:true,remove_by_restriction:false,auto_removal_timing:1,
    min_turns:2,max_turns:4,remove_by_damage:false,release_by_damage:false,chance_by_damage:100,remove_by_walking:false,steps_to_remove:100,
    message1:"is poisoned",message2:"",message3:"",message4:"recovers"))
end
def weapon(id) fill(RPG::Weapon.new,base(id,"Sword").merge(price:100,etype_id:0,params:[0,0,10,0,0,0,0,0],wtype_id:1,animation_id:1)); end
def armor(id) fill(RPG::Armor.new,base(id,"Shield").merge(price:80,etype_id:1,params:[0,0,0,5,0,0,0,0],atype_id:1)); end
{"Enemies"=>:enemy,"Skills"=>:skill,"States"=>:state,"Weapons"=>:weapon,"Armors"=>:armor}.each do |file,maker|
  File.binwrite(ARGV[0]+"/Data/#{file}.rvdata2",Marshal.dump([nil,send(maker,1),send(maker,2)]))
end
troops=Marshal.load(File.binread(ARGV[0]+"/Data/Troops.rvdata2"))
troops.compact.each{|troop|troop.instance_variable_set(:@pages,[])}
File.binwrite(ARGV[0]+"/Data/Troops.rvdata2",Marshal.dump(troops))
'''

    def setUp(self):
        region_fixtures.RegionCopyTests.setUp(self)
        script=self.base/'tables.rb';script.write_text(self.RUBY,encoding='utf-8')
        subprocess.run(['ruby',str(script),str(self.game)],check=True,capture_output=True)
        self.index=self.base/'table-index'
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)

    stage=region_fixtures.RegionCopyTests.stage

    def write(self,table,mut=None,proposal='Append one template-clone entry.'):
        root,_=backend.load(self.game/('Data/'+FILES[table]+'.rvdata2'))
        change={'kind':'database_entry','locator':{'table':table},'proposal':proposal,'mutation':mut or mutation(table,root)}
        self.spec={'changes':[change]};self.specfile.write_text(json.dumps(self.spec));return root

    def test_complete_copy_chain_for_every_table(self):
        from vxace_copy_patcher import current_inventory
        for table in FILES:
            with self.subTest(table=table):
                for name in ('copy','audit'):shutil.rmtree(self.base/name,ignore_errors=True)
                before=current_inventory(self.game);root=self.write(table);result=self.stage()
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(current_inventory(self.game),before)
                final,_=backend.load(self.base/('copy/Data/'+FILES[table]+'.rvdata2'))
                append.verify_transition(root,final,table,self.spec['changes'][0]['mutation'])
                self.assertEqual(marshal_rb.dump(final[:-1]),marshal_rb.dump(root))
                self.assertEqual(final[-1].get('note').data,b'')
                self.assertEqual((self.base/'copy/Data/System.rvdata2').read_bytes(),(self.game/'Data/System.rvdata2').read_bytes())
                audit=json.loads((self.base/'audit/audit.json').read_text())
                self.assertTrue(audit['changes'][0]['entry']['approved_template_clone_verified'])
                self.assertTrue((self.base/'audit/post-validation/validation.json').is_file())
                self.assertTrue((self.base/'audit/semantic-diff.json').is_file())
                impact=json.loads((self.base/'audit/structural-impact.json').read_text())['impacts'][0]
                self.assertEqual((impact['target']['table'],impact['target']['new_id']),(table,3))
                self.assertTrue(impact['new_note_forced_empty']);self.assertIn('features',impact['inherited_from_template'])
                if table=='enemies':self.assertIn('drop_items',impact['inherited_from_template'])

    def test_combinations_backend_and_table_action_mismatches_refuse(self):
        self.write('enemies')
        for backend_name,extra in (('ruby',()),('python',('--no-reindex',))):
            self.assertNotEqual(self.stage(backend_name,extra).returncode,0)
            self.assertFalse((self.base/'copy').exists())
        good=self.spec['changes'][0]
        def attempt(changes):
            self.spec['changes']=changes;self.specfile.write_text(json.dumps(self.spec))
            self.assertNotEqual(self.stage().returncode,0);self.assertFalse((self.base/'copy').exists())
        attempt([good,good])
        attempt([good,{'kind':'database_entry','locator':{'table':'items'},'proposal':'x','mutation':{'action':'append_key_item'}}])
        bad=json.loads(json.dumps(good));bad['locator']['table']='items';attempt([bad])
        bad=json.loads(json.dumps(good));bad['mutation']['action']='append_key_item';attempt([bad])
        attempt([good,{'kind':'database','locator':{'table':'enemies','id':1},'mutation':{'field':'exp','value':1}}])

    def test_stale_hash_opaque_formula_and_note_override_refuse_before_copy(self):
        self.write('skills');good=self.spec['changes'][0]['mutation']
        for key,value in (('expected_array_sha256','0'*64),('new_id',9)):
            self.write('skills',{**good,key:value});self.assertNotEqual(self.stage().returncode,0)
        bad=json.loads(json.dumps(good));bad['overrides']['damage_formula']='a.atk * rand(3)'
        self.write('skills',bad);self.assertNotEqual(self.stage().returncode,0)
        bad=json.loads(json.dumps(good));bad['overrides']['note']='<x>'
        self.write('skills',bad);self.assertNotEqual(self.stage().returncode,0)
        self.assertFalse((self.base/'copy').exists());self.assertFalse((self.base/'audit').exists())

    def test_snapshot_cli_per_table_and_backward_compatible_item_option(self):
        for table in FILES:
            output=self.base/('snap-'+table)
            args=[str(self.index),'--project',str(self.game),'--table',table,'--template-id','1','--output',str(output)]
            self.assertEqual(entries.main(args),0)
            result=json.loads((output/'item-entry-snapshot.json').read_text())
            self.assertEqual((result['table'],result['next_id']),(table,3))
            self.assertIn('inherited',result);self.assertIn('supported_overrides',result)
            self.assertEqual(result['array_sha256'],append.digest(backend.load(self.game/('Data/'+FILES[table]+'.rvdata2'))[0]))
        base=[str(self.index),'--project',str(self.game)]
        with self.assertRaises(SystemExit):entries.main(base+['--table','enemies','--template-item','1','--output',str(self.base/'x1')])
        self.assertEqual(entries.main(base+['--table','troops','--template-id','1','--output',str(self.base/'x2')]),2)
        self.assertEqual(entries.main(base+['--table','enemies','--template-id','1','--output',str(self.game/'rep')]),2)
        self.assertFalse((self.game/'rep').exists())


if __name__=='__main__':unittest.main()
