import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_map_events as events
import vxace_python_mutator as backend
from vxace_copy_patcher import current_inventory
from vxace_index_query import Index
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyHash


@unittest.skipUnless(shutil.which('ruby'),'Ruby needed for independent native template fixture')
class MapEventTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.game=self.base/'game';self.index=self.base/'index';self.specfile=self.base/'spec.json'
        subprocess.run(['ruby',str(ROOT/'tests/structure/make_dialogue_template.rb'),str(self.game)],check=True,capture_output=True)
        self.before,_=backend.load(self.game/'Data/Map001.rvdata2');self.read()
        snap=events.snapshot(self.before,1)
        self.mutation={'action':'append_dialogue_event','template_id':1,'new_id':3,'name':'Village Notice','x':3,'y':4,
                       'text':['A lost pendant lies beyond the village.','Please speak to the elder.'],
                       'expected_map_sha256':snap['map_sha256'],'expected_template_sha256':snap['template_sha256']}
        self.spec={'changes':[{'kind':'map_event','locator':{'map_id':1},'proposal':'Add a literal village notice.','mutation':self.mutation}]}
        self.specfile.write_text(json.dumps(self.spec))

    def read(self):
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)

    def clone(self):return marshal_rb.load(marshal_rb.dump(self.before))

    def stage(self,extra=()):
        return subprocess.run([sys.executable,str(ROOT/'tools/vxace_copy_patcher.py'),str(self.index),'--project',str(self.game),
                               '--spec',str(self.specfile),'--copy',str(self.base/'copy'),'--audit',str(self.base/'audit'),
                               '--backend','python',*extra],capture_output=True,text=True)

    def test_native_template_append_preserves_old_events_and_other_map_fields(self):
        candidate=self.clone();events.apply(candidate,self.mutation);events.verify_transition(self.before,candidate,self.mutation)
        added=candidate.get('events').pairs[-1][1]
        self.assertEqual((added.get('id'),added.get('x'),added.get('y')),(3,3,4))
        self.assertEqual([command.get('code') for command in added.get('pages')[0].get('list')],[101,401,401,0])
        self.assertEqual(added.get('name').data,b'Village Notice')
        self.assertEqual(added.get('pages')[0].get('graphic').get('character_name').data,b'')

    def test_unknown_event_hash_alias_is_detached_and_preserved(self):
        self.before.set('unknown_alias',self.before.get('events'))
        self.mutation['expected_map_sha256']=events.digest(self.before)
        candidate=self.clone();old_alias=events.digest(candidate.get('unknown_alias'))
        events.apply(candidate,self.mutation);events.verify_transition(self.before,candidate,self.mutation)
        self.assertIsNot(candidate.get('events'),candidate.get('unknown_alias'))
        self.assertEqual(events.digest(candidate.get('unknown_alias')),old_alias)

    def test_stale_map_or_template_refuses_without_changing_native_root(self):
        for field in ('expected_map_sha256','expected_template_sha256'):
            candidate=self.clone();before=marshal_rb.dump(candidate);mutation=dict(self.mutation,**{field:'0'*64})
            with self.assertRaises(ValueError):events.apply(candidate,mutation)
            self.assertEqual(marshal_rb.dump(candidate),before)

    def test_new_id_duplicate_hole_boolean_and_limit_refuse(self):
        for identifier in (1,2,4,True,0,1000):
            with self.assertRaises(ValueError):events.apply(self.clone(),dict(self.mutation,new_id=identifier))
        candidate=self.clone();candidate.get('events').pairs[1]=(999,candidate.get('events').pairs[1][1]);candidate.get('events').pairs[1][1].set('id',999)
        mutation=dict(self.mutation,new_id=1000,expected_map_sha256=events.digest(candidate))
        with self.assertRaises(ValueError):events.apply(candidate,mutation)

    def test_occupied_out_of_bounds_and_boolean_coordinates_refuse(self):
        for x,y in ((4,5),(1,1),(-1,0),(10,0),(0,10),(True,1)):
            with self.assertRaises(ValueError):events.apply(self.clone(),dict(self.mutation,x=x,y=y))

    def test_literal_text_schema_escape_controls_and_names_refuse(self):
        for change in ({'text':[]},{'text':['']},{'text':['x']*5},{'text':['\\V[1]']},{'text':['a\nb']},{'text':['x'*501]},
                       {'name':'Quest Gate'},{'name':''},{'name':'bad\0name'},{'commands':[]},{'text':[True]}):
            with self.assertRaises(ValueError):events.apply(self.clone(),dict(self.mutation,**change))
        candidate=self.clone();events.apply(candidate,dict(self.mutation,text=['Élder says hello.']))
        self.assertEqual(candidate.get('events').pairs[-1][1].get('pages')[0].get('list')[1].get('parameters')[0].data,'Élder says hello.'.encode())

    def test_unknown_and_nonblank_native_template_schema_refuses(self):
        for part in ('event','page','condition','graphic','route','command'):
            candidate=self.clone();event=candidate.get('events').pairs[0][1];page=event.get('pages')[0]
            selected={'event':event,'page':page,'condition':page.get('condition'),'graphic':page.get('graphic'),
                      'route':page.get('move_route'),'command':page.get('list')[0]}[part]
            selected.set('unknown',7)
            with self.assertRaises(ValueError):events.snapshot(candidate,1)
        for part,key,value in (('page','trigger',3),('page','move_type',3),('condition','switch1_valid',True),('graphic','tile_id',1)):
            candidate=self.clone();page=candidate.get('events').pairs[0][1].get('pages')[0]
            selected=page if part=='page' else page.get(part);selected.set(key,value)
            with self.assertRaises(ValueError):events.snapshot(candidate,1)

    def test_nonempty_commands_routes_or_multiple_pages_refuse(self):
        for mode in ('commands','routes','pages'):
            candidate=self.clone();event=candidate.get('events').pairs[0][1];page=event.get('pages')[0]
            if mode=='pages':event.set('pages',[page,page])
            elif mode=='commands':page.set('list',[*page.get('list'),*page.get('list')])
            else:page.get('move_route').set('list',[*page.get('move_route').get('list')]*2)
            with self.assertRaises(ValueError):events.snapshot(candidate,1)

    def test_ambiguous_hash_identity_default_and_alias_refuse(self):
        for mode in ('id','key','alias','default','coordinate'):
            candidate=self.clone();old=candidate.get('events')
            if mode=='id':old.pairs[0][1].set('id',7)
            elif mode=='key':old.pairs.append(old.pairs[0])
            elif mode=='alias':old.pairs.append((3,old.pairs[0][1]))
            elif mode=='coordinate':old.pairs[0][1].set('x',True)
            else:old.default=0
            with self.assertRaises(ValueError):events.snapshot(candidate,1)

    def test_candidate_verifier_rejects_old_event_table_name_position_and_dialogue_changes(self):
        for mode in ('old','table','name','position','text'):
            candidate=self.clone();events.apply(candidate,self.mutation);added=candidate.get('events').pairs[-1][1]
            if mode=='old':candidate.get('events').pairs[0][1].set('x',0)
            elif mode=='table':candidate.get('data').data[0]=1
            elif mode=='name':added.set('name',backend.convert('Changed'))
            elif mode=='position':added.set('x',9)
            else:added.get('pages')[0].get('list')[1].set('parameters',[backend.convert('Changed')])
            with self.assertRaises(ValueError):events.verify_transition(self.before,candidate,self.mutation)

    def test_complete_copy_chain_version_impact_and_postgates(self):
        original=current_inventory(self.game);result=self.stage();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(current_inventory(self.game),original)
        candidate,_=backend.load(self.base/'copy/Data/Map001.rvdata2');events.verify_transition(self.before,candidate,self.mutation)
        system,_=backend.load(self.base/'copy/Data/System.rvdata2');self.assertEqual(system.get('version_id'),21)
        for name in ('structural-impact.json','semantic-diff.json','post-validation/validation.json'):
            self.assertTrue((self.base/'audit'/name).is_file())
        report=json.loads((self.base/'audit/audit.json').read_text());self.assertTrue(report['changes'][0]['map_event']['old_events_and_other_map_fields_preserved'])

    def test_backend_reindex_and_single_map_transaction_mandatory(self):
        for extra in (('--backend','ruby'),('--no-reindex',)):
            result=self.stage(extra);self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())
        self.spec['changes'].append(self.spec['changes'][0]);self.specfile.write_text(json.dumps(self.spec))
        result=self.stage();self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())

    def test_readonly_snapshot_planner_and_index_tamper_refusal(self):
        original=current_inventory(self.game)
        result=subprocess.run([sys.executable,str(ROOT/'tools/vxace_map_events.py'),str(self.index),'--project',str(self.game),
                               '--map','1','--template-event','1','--output',str(self.base/'snapshot')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads((self.base/'snapshot/map-event-snapshot.json').read_text());self.assertFalse(report['mutation_authorized'])
        result=subprocess.run([sys.executable,str(ROOT/'tools/vxace_patch_planner.py'),str(self.index),'--project',str(self.game),
                               '--spec',str(self.specfile),'--output',str(self.base/'plan')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(current_inventory(self.game),original)
        path=self.index/'maps/map-001.json';data=json.loads(path.read_text());data['events']['1']['pages'][0]['trigger']=3;path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):events.indexed_snapshot(Index(self.index),self.game,1,1)
        data['events']['1']['pages'][0]['trigger']=0;data['data']['data'][0]=1;path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):events.indexed_snapshot(Index(self.index),self.game,1,1)

    def test_post_index_failure_rolls_back_retains_private_audit(self):
        reader=self.base/'failed-reader.py';reader.write_text('raise SystemExit(8)\n')
        result=self.stage(('--reader',str(reader)));self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.base/'copy').exists());self.assertTrue(json.loads((self.base/'audit/failure.json').read_text())['staged_copy_removed'])


    def blank_mutation(self,donor=1,**change):
        snap=events.blank_snapshot(self.before,donor)
        return dict({'action':'append_blank_event','donor_event_id':donor,'new_id':snap['next_event_id'],'name':'EV%03d'%snap['next_event_id'],'x':9,'y':9,
                     'expected_map_sha256':snap['map_sha256'],'expected_donor_sha256':snap['donor_sha256']},**change)

    def set_blank_spec(self,mutation):
        self.spec['changes'][0]['mutation']=mutation;self.specfile.write_text(json.dumps(self.spec))

    def test_blank_event_from_nonblank_donor_passes_v026_predicate(self):
        original=self.clone()
        donor=self.before.get('events').pairs[0][1]
        page=donor.get('pages')[0];page.set('priority_type',2);page.set('trigger',3);page.set('move_type',2);page.set('list',[page.get('list')[0],page.get('list')[0]])
        page.get('condition').set('switch1_valid',True);page.get('graphic').set('tile_id',5);page.get('move_route').set('repeat',False)
        donor.set('pages',[page,page])
        self.assertEqual(donor.get('id'),1)
        snap=events.blank_snapshot(self.before,1)
        mutation=self.blank_mutation(1)
        before=self.clone()
        events.apply(self.before,mutation);events.verify_transition(before,self.before,mutation)
        added=self.before.get('events').pairs[-1][1]
        self.assertIs(events.template(self.before,mutation['new_id']),added)
        self.assertEqual((added.get('id'),added.get('x'),added.get('y'),added.get('name').data),(mutation['new_id'],9,9,b'EV003'))
        blank=added.get('pages')[0]
        self.assertEqual(len(added.get('pages')),1);self.assertEqual(blank.get('priority_type'),0)
        self.assertEqual((blank.get('trigger'),blank.get('move_type'),blank.get('move_speed'),blank.get('move_frequency')),(0,0,3,3))
        self.assertEqual([c.get('code') for c in blank.get('list')],[0])
        self.assertEqual(blank.get('move_route').get('repeat'),True)
        self.assertEqual(snap['donor_sha256'],mutation['expected_donor_sha256'])
        self.assertNotEqual(events.digest(original),events.digest(before))

    def test_blank_event_equals_template_blank_defaults(self):
        mutation=self.blank_mutation(1);candidate=self.clone();events.apply(candidate,mutation);events.verify_transition(self.before,candidate,mutation)
        added=candidate.get('events').pairs[-1][1];events.template(candidate,3,True)
        graphic=added.get('pages')[0].get('graphic')
        self.assertEqual((graphic.get('tile_id'),graphic.get('character_name').data,graphic.get('direction'),graphic.get('pattern')),(0,b'',2,0))
        condition=added.get('pages')[0].get('condition')
        self.assertEqual((condition.get('self_switch_ch').data,condition.get('switch1_id'),condition.get('variable_value')),(b'A',1,0))

    def test_blank_event_refusals(self):
        for change in ({'x':4,'y':5},{'x':-1},{'x':10},{'y':10},{'x':True},{'new_id':2},{'new_id':4},{'new_id':True},{'name':''},{'name':'x'*101},{'name':self.before.get('events').pairs[0][1].get('name').data.decode()},
                       {'expected_map_sha256':'0'*64},{'expected_donor_sha256':'0'*64},{'donor_event_id':9},{'donor_event_id':2},{'donor_event_id':True},{'extra':1}):
            with self.assertRaises(ValueError,msg=str(change)):events.apply(self.clone(),dict(self.blank_mutation(1),**change))
        for part in ('event','page','condition','graphic','route','command','eventcommand'):
            candidate=self.clone();event=candidate.get('events').pairs[0][1];page=event.get('pages')[0]
            selected={'event':event,'page':page,'condition':page.get('condition'),'graphic':page.get('graphic'),
                      'route':page.get('move_route'),'command':page.get('move_route').get('list')[0],'eventcommand':page.get('list')[0]}[part]
            selected.set('unknown',7)
            with self.assertRaises(ValueError,msg=part):events.apply(candidate,dict(self.blank_mutation(1),expected_map_sha256='0'*64))
            with self.assertRaises(ValueError,msg=part):events.blank_snapshot(candidate,1)

    def test_blank_candidate_verifier_rejects_tampering(self):
        mutation=self.blank_mutation(1)
        for mode in ('old','table','name','position','page','extra'):
            candidate=self.clone();events.apply(candidate,mutation);added=candidate.get('events').pairs[-1][1]
            if mode=='old':candidate.get('events').pairs[0][1].set('x',0)
            elif mode=='table':candidate.get('data').data[0]=1
            elif mode=='name':added.set('name',backend.convert('Changed'))
            elif mode=='position':added.set('x',8)
            elif mode=='page':added.get('pages')[0].set('priority_type',1)
            else:candidate.set('unknown_field',1)
            with self.assertRaises(ValueError):events.verify_transition(self.before,candidate,mutation)

    def test_blank_event_copy_chain(self):
        mutation=self.blank_mutation(1);self.set_blank_spec(mutation);original=current_inventory(self.game)
        result=self.stage();self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(current_inventory(self.game),original)
        candidate,_=backend.load(self.base/'copy/Data/Map001.rvdata2');events.verify_transition(self.before,candidate,mutation)
        events.template(candidate,3)
        system,_=backend.load(self.base/'copy/Data/System.rvdata2');self.assertEqual(system.get('version_id'),21)
        report=json.loads((self.base/'audit/audit.json').read_text())['changes'][0]['map_event']
        self.assertEqual((report['action'],report['new_id'],report['donor_event_id']),('append_blank_event',3,1));self.assertTrue(report['blank_template_predicate_ok'])
        for name in ('structural-impact.json','semantic-diff.json','post-validation/validation.json'):self.assertTrue((self.base/'audit'/name).is_file())

    def test_blank_event_transaction_refusals(self):
        self.set_blank_spec(self.blank_mutation(1))
        for extra in (('--backend','ruby'),('--no-reindex',)):
            result=self.stage(extra);self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())
        self.spec['changes'].append(self.spec['changes'][0]);self.specfile.write_text(json.dumps(self.spec))
        self.assertNotEqual(self.stage().returncode,0);self.assertFalse((self.base/'copy').exists())
        self.spec['changes'].pop();self.set_blank_spec(dict(self.blank_mutation(1),x=4,y=5))
        self.assertNotEqual(self.stage().returncode,0);self.assertFalse((self.base/'copy').exists())
        self.set_blank_spec(dict(self.blank_mutation(1),expected_map_sha256='0'*64))
        self.assertNotEqual(self.stage().returncode,0);self.assertFalse((self.base/'copy').exists())

    def test_donor_snapshot_cli(self):
        original=current_inventory(self.game)
        result=subprocess.run([sys.executable,str(ROOT/'tools/vxace_map_events.py'),str(self.index),'--project',str(self.game),
                               '--map','1','--donor-event','1','--output',str(self.base/'snapshot')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads((self.base/'snapshot/map-event-snapshot.json').read_text())
        self.assertTrue(report['donor_schema_ok']);self.assertEqual((report['next_event_id'],report['default_name']),(3,'EV003'));self.assertFalse(report['mutation_authorized'])
        self.assertEqual(current_inventory(self.game),original)
        bad=subprocess.run([sys.executable,str(ROOT/'tools/vxace_map_events.py'),str(self.index),'--project',str(self.game),
                            '--map','1','--donor-event','2','--output',str(self.base/'snapshot2')],capture_output=True,text=True)
        self.assertNotEqual(bad.returncode,0)


if __name__=='__main__':unittest.main()
