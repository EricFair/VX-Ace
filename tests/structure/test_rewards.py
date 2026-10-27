import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_event_rewards as rewards
import vxace_event_structure as structure
import vxace_python_mutator as backend
from vxace_copy_patcher import current_inventory,build
from vxace_index_query import Index
from rpgvxace_mcp import marshal_rb


def row(code,parameters):return {'code':code,'indent':0,'parameters':parameters}


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native reward fixture')
class RewardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.game=self.base/'game';self.index=self.base/'index';self.specfile=self.base/'spec.json'
        subprocess.run(['ruby',str(ROOT/'tests/structure/make_reward_fixture.rb'),str(self.game)],check=True,capture_output=True)
        self.before,_=backend.load(self.game/'Data/Map001.rvdata2');self.read()
        snap=rewards.snapshot(Index(self.index),self.game,1,1,1)
        self.mutation={'action':'insert_commands','expected_list_sha256':snap['expected_list_sha256'],
                       'reward_guard':snap['reward_guard'],'commands':[row(101,['',0,0,2]),row(401,['A reward.']),row(125,[0,0,25]),row(126,[1,0,0,1]),row(123,['A',0])]}
        self.spec={'changes':[{'kind':'event','locator':{'map_id':1,'event_id':1,'page':1,'command_index':0},'proposal':'One-time native reward.','mutation':self.mutation}]}
        self.specfile.write_text(json.dumps(self.spec))

    def read(self):
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)

    def clone(self):return marshal_rb.load(marshal_rb.dump(self.before))

    def native_mutation(self,**extra):return {'scope':'map','event_id':1,'page':1,'command_index':0,**self.mutation,**extra}

    def stage(self,extra=()):
        return subprocess.run([sys.executable,str(ROOT/'tools/vxace_copy_patcher.py'),str(self.index),'--project',str(self.game),
                               '--spec',str(self.specfile),'--copy',str(self.base/'copy'),'--audit',str(self.base/'audit'),'--backend','python',*extra],capture_output=True,text=True)

    def apply(self,candidate,mutation=None):backend.apply(candidate,{'type':'event','mutation':mutation or self.native_mutation()},source_path=self.game/'Data/Map001.rvdata2')

    def test_native_reward_commands_and_candidate_preservation(self):
        candidate=self.clone();self.apply(candidate);rewards.verify_transition(self.before,candidate,self.native_mutation(),self.game/'Data/Map001.rvdata2')
        pages=candidate.get('events').pairs[0][1].get('pages')
        self.assertEqual([command.get('code') for command in pages[0].get('list')],[101,401,125,126,123,0])
        self.assertEqual(structure.fingerprint(pages[1]),structure.fingerprint(self.before.get('events').pairs[0][1].get('pages')[1]))

    def test_candidate_verifier_rejects_higher_page_table_and_other_event_changes(self):
        for mode in ('page','table','event'):
            candidate=self.clone();self.apply(candidate)
            if mode=='page':candidate.get('events').pairs[0][1].get('pages')[1].get('condition').set('self_switch_valid',False)
            elif mode=='table':candidate.get('data').data[0]=1
            else:candidate.get('events').pairs[1][1].set('name',backend.convert('Changed'))
            with self.assertRaises(ValueError):rewards.verify_transition(self.before,candidate,self.native_mutation(),self.game/'Data/Map001.rvdata2')

    def test_variable_removal_zero_boolean_limits_duplicate_and_script_rows_refuse(self):
        for bad in (row(125,[1,0,25]),row(125,[0,1,1]),row(125,[0,0,0]),row(125,[0,0,True]),row(125,[0,0,100000000]),
                    row(126,[1,1,0,1]),row(126,[1,0,1,1]),row(126,[1,0,0,100]),row(126,[True,0,0,1]),row(355,['danger']),row(401,['\\V[1]'])):
            mutation=self.native_mutation(commands=[bad,row(123,['A',0])]);candidate=self.clone();before=marshal_rb.dump(candidate)
            with self.assertRaises(ValueError):self.apply(candidate,mutation)
            self.assertEqual(marshal_rb.dump(candidate),before)
        for rows in ([row(125,[0,0,1])]*2+[row(123,['A',0])],[row(125,[0,0,1])],
                     [row(123,['A',0]),row(125,[0,0,1])],[row(125,[0,0,1]),row(123,['A',1])]):
            with self.assertRaises(ValueError):rewards.reward_rows(rows)

    def test_higher_condition_trigger_shape_commands_and_nonblank_lower_refuse(self):
        for mode in ('condition','trigger','count','higher','lower'):
            candidate=self.clone();pages=candidate.get('events').pairs[0][1].get('pages')
            if mode=='condition':pages[1].get('condition').set('switch1_valid',True)
            elif mode=='trigger':pages[1].set('trigger',3)
            elif mode=='count':pages.append(pages[1])
            elif mode=='higher':pages[1].get('list').insert(0,backend.RubyObject('RPG::EventCommand',{'@code':123,'@indent':0,'@parameters':backend.convert(['A',1])}))
            else:pages[0].get('list').insert(0,backend.RubyObject('RPG::EventCommand',{'@code':230,'@indent':0,'@parameters':[1]}))
            with self.assertRaises(ValueError):rewards.guard_pages(candidate,1)

    def test_native_map_path_scope_page_index_and_guard_required(self):
        with self.assertRaises(ValueError):backend.apply(self.clone(),{'type':'event','mutation':self.native_mutation()})
        for change in ({'scope':'troop'},{'page':2},{'command_index':1},{'reward_guard':{}},{'action':'insert_page'}):
            with self.assertRaises(ValueError):self.apply(self.clone(),self.native_mutation(**change))
        with self.assertRaises(ValueError):rewards.item_context(self.native_mutation(),self.game/'Map001.rvdata2')

    def test_stale_pages_letter_items_and_actual_item_identity_refuse(self):
        for field,value in (('expected_pages_sha256','0'*64),('expected_items_sha256','0'*64),('self_switch','B')):
            guard=dict(self.mutation['reward_guard'],**{field:value})
            with self.assertRaises(ValueError):self.apply(self.clone(),self.native_mutation(reward_guard=guard))
        items,_=backend.load(self.game/'Data/Items.rvdata2');items[1].set('id',2)
        (self.game/'Data/Items.rvdata2').write_bytes(marshal_rb.dump(items))
        guard=dict(self.mutation['reward_guard'],expected_items_sha256=structure.fingerprint(items))
        with self.assertRaises(ValueError):self.apply(self.clone(),self.native_mutation(reward_guard=guard))

    def test_missing_native_item_refuses_even_with_self_consistent_index_claim(self):
        mutation=self.native_mutation(commands=[row(126,[2,0,0,1]),row(123,['A',0])])
        with self.assertRaises(ValueError):self.apply(self.clone(),mutation)
        data=json.loads((self.index/'database/items.json').read_text());data[1]['name']='Forged';(self.index/'database/items.json').write_text(json.dumps(data))
        with self.assertRaises(ValueError):rewards.snapshot(Index(self.index),self.game,1,1,1)

    def test_gold_only_reward_does_not_claim_an_item_binding(self):
        guard=dict(self.mutation['reward_guard'],expected_items_sha256=None)
        mutation=self.native_mutation(commands=[row(125,[0,0,25]),row(123,['A',0])],reward_guard=guard)
        candidate=self.clone();self.apply(candidate,mutation);rewards.verify_transition(self.before,candidate,mutation,self.game/'Data/Map001.rvdata2')
        with self.assertRaises(ValueError):self.apply(self.clone(),dict(mutation,reward_guard=self.mutation['reward_guard']))

    def test_copy_chain_native_version_source_items_and_postgates(self):
        original=current_inventory(self.game);result=self.stage();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(current_inventory(self.game),original)
        candidate,_=backend.load(self.base/'copy/Data/Map001.rvdata2');rewards.verify_transition(self.before,candidate,self.native_mutation(),self.game/'Data/Map001.rvdata2')
        system,_=backend.load(self.base/'copy/Data/System.rvdata2');self.assertEqual(system.get('version_id'),21)
        self.assertEqual((self.base/'copy/Data/Items.rvdata2').read_bytes(),(self.game/'Data/Items.rvdata2').read_bytes())
        audit=json.loads((self.base/'audit/audit.json').read_text());self.assertTrue(audit['changes'][0]['one_time_rewards']['only_approved_native_map_change'])
        impact=json.loads((self.base/'audit/structural-impact.json').read_text())
        self.assertEqual(impact['impacts'][0]['one_time_rewards']['proposed']['gold'],25)
        for name in ('post-validation/validation.json','semantic-diff.json','structural-impact.json'):self.assertTrue((self.base/'audit'/name).is_file())

    def test_single_change_python_and_reindex_mandatory(self):
        for extra in (('--backend','ruby'),('--no-reindex',)):
            result=self.stage(extra);self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())
        self.spec['changes'][0]['locator']['map_id']=True;self.specfile.write_text(json.dumps(self.spec))
        result=self.stage();self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())
        self.spec['changes'][0]['locator']['map_id']=1
        self.spec['changes'].append(self.spec['changes'][0]);self.specfile.write_text(json.dumps(self.spec))
        result=self.stage();self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())

    def test_snapshot_planner_readonly_and_index_followup_tamper_refused(self):
        original=current_inventory(self.game)
        result=subprocess.run([sys.executable,str(ROOT/'tools/vxace_event_rewards.py'),str(self.index),'--project',str(self.game),
                               '--map','1','--event','1','--item','1','--output',str(self.base/'snapshot')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(json.loads((self.base/'snapshot/event-reward-snapshot.json').read_text())['mutation_authorized'])
        result=subprocess.run([sys.executable,str(ROOT/'tools/vxace_patch_planner.py'),str(self.index),'--project',str(self.game),
                               '--spec',str(self.specfile),'--output',str(self.base/'plan')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(current_inventory(self.game),original)
        path=self.index/'maps/map-001.json';data=json.loads(path.read_text());data['events']['1']['pages'][1]['list'][1]['parameters']=['Forged'];path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):rewards.snapshot(Index(self.index),self.game,1,1,1)

    def test_final_item_context_change_rolls_back_with_source_unchanged(self):
        original=rewards.item_context;source_before=current_inventory(self.game);injected=False
        def changed(mutation,source_path):
            nonlocal injected
            path=Path(source_path)
            if self.base/'copy' in path.parents and len(backend.load(path)[0].get('events').pairs[0][1].get('pages')[0].get('list'))>1 and not injected:
                items,_=backend.load(path.parent/'Items.rvdata2');items[1].set('name',backend.convert('Changed'));(path.parent/'Items.rvdata2').write_bytes(marshal_rb.dump(items));injected=True
            return original(mutation,source_path)
        with patch.object(rewards,'item_context',side_effect=changed):
            with self.assertRaises((ValueError,RuntimeError)):
                build(self.index,self.game,self.specfile,self.base/'copy',self.base/'audit',shutil.which('ruby'),ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')
        self.assertTrue(injected);self.assertFalse((self.base/'copy').exists());self.assertEqual(current_inventory(self.game),source_before)
        self.assertTrue((self.base/'audit/failure.json').is_file())


if __name__=='__main__':unittest.main()
