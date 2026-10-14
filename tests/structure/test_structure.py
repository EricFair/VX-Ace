import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_python_mutator as backend
import vxace_event_structure as structure
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject, RubyHash, RubyUserDef


def row(code, parameters=None, indent=0):
    return {'code':code,'indent':indent,'parameters':parameters or []}


def command(code, parameters=None, indent=0):
    return RubyObject('RPG::EventCommand',{'@code':code,'@indent':indent,'@parameters':backend.convert(parameters or [])})


def page(troop=False):
    condition=({'turn_valid':False,'turn_a':0,'turn_b':0,'switch_valid':False,'switch_id':1}
               if troop else {'switch1_valid':False,'switch1_id':1,'switch2_valid':False,'switch2_id':1,
                              'self_switch_valid':False,'self_switch_ch':backend.convert('A')})
    return RubyObject('RPG::Troop::Page' if troop else 'RPG::Event::Page',{
        '@condition':RubyObject('RPG::Troop::Page::Condition' if troop else 'RPG::Event::Page::Condition',{'@'+k:v for k,v in condition.items()}),
        '@list':[command(101,['',0,0,2]),command(401,['BASELINE']),command(0)],
        '@span' if troop else '@trigger':0,'@opaque_fixture':RubyUserDef('CustomPayload',b'preserve\x00\xff')})


def fixture(scope='map'):
    if scope=='map':
        owner=RubyObject('RPG::Event',{'@id':1,'@name':backend.convert('Test'),'@x':8,'@y':7,'@pages':[page()]})
        root=RubyObject('RPG::Map',{'@width':17,'@height':13,'@events':RubyHash([(1,owner)])})
        locator={'scope':'map','event_id':1,'page':1}
    else:
        owner=RubyObject('RPG::Troop' if scope=='troop' else 'RPG::CommonEvent',{'@id':1,'@name':backend.convert('Test')})
        if scope=='troop': owner.set('pages',[page(True)])
        else: owner.set('trigger',0); owner.set('list',[command(101,['',0,0,2]),command(401,['BASELINE']),command(0)])
        root=[None,owner]
        locator={'scope':scope, 'troop_id' if scope=='troop' else 'common_event_id':1}
        if scope=='troop': locator['page']=1
    return root,owner,locator


def mutate(root, locator, action, **values):
    backend.apply(root,{'type':'event','mutation':{**locator,'action':action,**values}})


class StructureTests(unittest.TestCase):
    def test_insert_delete_commands_all_three_scopes_preserve_opaque_data(self):
        for scope in ('map','common_event','troop'):
            with self.subTest(scope=scope):
                root,owner,loc=fixture(scope); before=marshal_rb.dump(root)
                snap=structure.snapshot(root,loc,backend.object_by_id)
                mutate(root,{**loc,'command_index':2},'insert_commands',expected_list_sha256=snap['list_sha256'],commands=[row(230,[1])])
                after=structure.snapshot(root,loc,backend.object_by_id)
                self.assertEqual([r['code'] for r in after['commands']],[101,401,230,0])
                mutate(root,{**loc,'command_index':2},'delete_commands',expected_list_sha256=after['list_sha256'],count=1)
                self.assertEqual(marshal_rb.dump(root),before)

    def test_insert_delete_pages_map_and_troop_and_independent_clone(self):
        for scope in ('map','troop'):
            with self.subTest(scope=scope):
                root,owner,loc=fixture(scope); old=marshal_rb.dump(root)
                snap=structure.snapshot(root,loc,backend.object_by_id)
                conditions={'self_switch_valid':True,'self_switch_ch':'A'} if scope=='map' else {'turn_valid':True,'turn_a':0,'turn_b':0}
                mutate(root,{**loc,'page':2},'insert_page',expected_pages_sha256=snap['pages_sha256'],template_page=1,
                       expected_template_sha256=snap['page_sha256'],conditions=conditions,
                       commands=[row(101,['',0,0,2]),row(401,['PAGE']),row(0)],acknowledge_page_priority_change=True)
                self.assertEqual(len(owner.get('pages')),2)
                self.assertIsNot(owner.get('pages')[0].get('condition'),owner.get('pages')[1].get('condition'))
                self.assertEqual(owner.get('pages')[0].get('list')[1].get('parameters')[0].data,b'BASELINE')
                snap=structure.snapshot(root,{**loc,'page':2},backend.object_by_id)
                mutate(root,{**loc,'page':2},'delete_page',expected_pages_sha256=snap['pages_sha256'],expected_page_sha256=snap['page_sha256'],acknowledge_page_priority_change=True)
                self.assertEqual(marshal_rb.dump(root),old)

    def test_insert_cannot_split_message_header_from_continuation(self):
        root,owner,loc=fixture(); snap=structure.snapshot(root,loc,backend.object_by_id)
        with self.assertRaisesRegex(ValueError,'split'):
            mutate(root,{**loc,'command_index':1},'insert_commands',expected_list_sha256=snap['list_sha256'],commands=[row(230,[1])])

    def test_delete_cannot_split_compound_message(self):
        root,owner,loc=fixture(); snap=structure.snapshot(root,loc,backend.object_by_id)
        with self.assertRaisesRegex(ValueError,'split'):
            mutate(root,{**loc,'command_index':0},'delete_commands',expected_list_sha256=snap['list_sha256'],count=1)

    def test_final_terminator_cannot_be_deleted(self):
        root,owner,loc=fixture(); snap=structure.snapshot(root,loc,backend.object_by_id)
        with self.assertRaises(ValueError):
            mutate(root,{**loc,'command_index':2},'delete_commands',expected_list_sha256=snap['list_sha256'],count=1)

    def test_nested_if_else_and_loop_are_atomic_units(self):
        commands=[command(111,[0,1,0]),command(112,[],1),command(230,[1],2),command(413,[],1),command(411),command(108,['else'],1),command(412),command(0)]
        self.assertEqual(structure.validate_list(commands),{0,7})
        root,owner,loc=fixture(); owner.get('pages')[0].set('list',commands)
        snap=structure.snapshot(root,loc,backend.object_by_id)
        with self.assertRaises(ValueError):
            mutate(root,{**loc,'command_index':1},'delete_commands',expected_list_sha256=snap['list_sha256'],count=1)
        mutate(root,{**loc,'command_index':0},'delete_commands',expected_list_sha256=snap['list_sha256'],count=7)
        self.assertEqual(owner.get('pages')[0].get('list')[0].get('code'),0)

    def test_choice_battle_shop_script_and_route_units_remain_grouped(self):
        groups=[
            [command(102,[['Yes'],0]),command(402,[0,'Yes']),command(108,['x'],1),command(404)],
            [command(301,[0,1,True,True]),command(601),command(108,['win'],1),command(602),command(108,['escape'],1),command(603),command(108,['lose'],1),command(604)],
            [command(302,[0,1,0,0,False]),command(605,[0,2,0,0])],
            [command(355,['a=1']),command(655,['a+=1'])],
            [command(205,[0,None]),command(505,[None])],
        ]
        for group in groups:
            with self.subTest(code=group[0].get('code')):
                self.assertEqual(structure.validate_list(group+[command(0)]),{0,len(group)})

    def test_malformed_source_lists_are_refused(self):
        malformed=[[command(401,['orphan']),command(0)], [command(111,[0,1,0]),command(0)],
                   [command(412),command(0)],[command(108,['x'],1),command(0)], [command(0),command(0)]]
        for commands in malformed:
            with self.subTest(commands=commands),self.assertRaises(ValueError): structure.validate_list(commands)

    def test_deleting_a_label_cannot_leave_a_dangling_jump(self):
        root,owner,loc=fixture(); owner.get('pages')[0].set('list',[command(118,['label']),command(119,['label']),command(0)])
        snap=structure.snapshot(root,loc,backend.object_by_id)
        with self.assertRaisesRegex(ValueError,'label'):
            mutate(root,{**loc,'command_index':0},'delete_commands',expected_list_sha256=snap['list_sha256'],count=1)

    def test_stale_command_and_page_fingerprints_are_refused(self):
        root,owner,loc=fixture()
        with self.assertRaisesRegex(ValueError,'fingerprint'):
            mutate(root,{**loc,'command_index':2},'insert_commands',expected_list_sha256='0'*64,commands=[row(230,[1])])
        with self.assertRaisesRegex(ValueError,'fingerprint'):
            mutate(root,loc,'delete_page',expected_pages_sha256='0'*64,expected_page_sha256='0'*64,acknowledge_page_priority_change=True)

    def test_final_page_and_common_event_page_operations_refused(self):
        root,owner,loc=fixture(); snap=structure.snapshot(root,loc,backend.object_by_id)
        with self.assertRaisesRegex(ValueError,'final page'):
            mutate(root,loc,'delete_page',expected_pages_sha256=snap['pages_sha256'],expected_page_sha256=snap['page_sha256'],acknowledge_page_priority_change=True)
        root,owner,loc=fixture('common_event')
        with self.assertRaises(ValueError): mutate(root,loc,'delete_page')

    def test_page_priority_ack_and_enabled_condition_required(self):
        root,owner,loc=fixture(); snap=structure.snapshot(root,loc,backend.object_by_id)
        values=dict(expected_pages_sha256=snap['pages_sha256'],expected_template_sha256=snap['page_sha256'],template_page=1,commands=[row(0)],conditions={'self_switch_valid':False})
        with self.assertRaisesRegex(ValueError,'acknowledged'):
            mutate(root,{**loc,'page':2},'insert_page',**values)
        with self.assertRaisesRegex(ValueError,'enabled'):
            mutate(root,{**loc,'page':2},'insert_page',**values,acknowledge_page_priority_change=True)

    def test_repeating_trigger_edits_are_refused_all_scopes(self):
        for scope in ('map','common_event','troop'):
            root,owner,loc=fixture(scope)
            holder=owner if scope=='common_event' else owner.get('pages')[0]
            holder.set('span' if scope=='troop' else 'trigger',2 if scope=='troop' else 3 if scope=='map' else 1)
            snap=structure.snapshot(root,loc,backend.object_by_id)
            with self.subTest(scope=scope),self.assertRaisesRegex(ValueError,'Repeating'):
                mutate(root,{**loc,'command_index':2},'insert_commands',expected_list_sha256=snap['list_sha256'],commands=[row(230,[1])])

    def test_negative_boolean_and_fractional_indexes_are_refused(self):
        for index in (-1,True,1.5):
            root,owner,loc=fixture(); snap=structure.snapshot(root,loc,backend.object_by_id)
            with self.subTest(index=index),self.assertRaises(ValueError):
                mutate(root,{**loc,'command_index':index},'insert_commands',expected_list_sha256=snap['list_sha256'],commands=[row(230,[1])])

    def test_unsupported_new_commands_and_orphan_continuations_refused(self):
        for rows in ([row(355,['arbitrary code'])],[row(401,['orphan'])],[row(0)], [row(111,[0,1,0])],
                     [row(121,[2,1,0])], [row(123,['E',0])], [row(230,[3601])],
                     [row(101,['',True,0,2])], [row(118,['duplicate']),row(118,['duplicate'])]):
            with self.subTest(rows=rows),self.assertRaises(ValueError): structure.new_commands(rows,backend.convert,'map')

    def test_all_new_command_schemas_roundtrip_and_scope_limits(self):
        rows=[row(101,['',0,0,2]),row(401,['text']),row(108,['comment']),row(408,['continued']),
              row(121,[1,2,0]),row(123,['A',0]),row(117,[1]),row(118,['done']),row(119,['done']),row(230,[1])]
        native=structure.new_commands(rows,backend.convert,'map')
        self.assertEqual(structure.command_rows(marshal_rb.load(marshal_rb.dump(native))),rows)
        for scope in ('troop','common_event'):
            with self.subTest(scope=scope),self.assertRaises(ValueError):
                structure.new_commands([row(123,['A',0])],backend.convert,scope)

    def test_native_version_update_requires_exact_non_exhausted_integer(self):
        for old,expected in ((10,9),(2**31-1,2**31-1),(0,False),(-1,-1)):
            root=RubyObject('RPG::System',{'@version_id':old})
            with self.subTest(old=old,expected=expected),self.assertRaises(ValueError):
                backend.apply(root,{'type':'system_version','mutation':{'expected_version':expected}})
            self.assertEqual(root.get('version_id'),old)

    def test_mutations_cannot_override_locator_fields(self):
        from vxace_copy_patcher import normalize_changes
        spec={'changes':[{'kind':'event','locator':{'map_id':1,'event_id':1,'page':1,'command_index':0},'mutation':{'action':'insert_commands','event_id':2}}]}
        with self.assertRaisesRegex(ValueError,'override'): normalize_changes(Path('.'),spec)

    def test_cross_file_references_checked_against_actual_index(self):
        with tempfile.TemporaryDirectory() as td:
            index=Path(td); (index/'database').mkdir()
            (index/'database/system.json').write_text(json.dumps({'switches':['','one']}))
            (index/'database/common-events.json').write_text(json.dumps([None,{'id':1}]))
            structure.validate_project_references(index,{'commands':[row(117,[1]),row(121,[1,1,0])]})
            for rows in ([row(117,[2])],[row(121,[1,2,0])]):
                with self.assertRaises(ValueError): structure.validate_project_references(index,{'commands':rows})

    def test_troop_page_contexts_keep_distinct_ids_and_page_numbers(self):
        from vxace_project_reader import ctx
        from vxace_codex_lib.common import ctx_key
        context=ctx('troop','troops.json',{'path':[1,'pages',1,'list',0],'code':121})
        self.assertEqual((context['troop_id'],context['page'],context['command_index']),(1,2,0))
        self.assertNotEqual(ctx_key(context),ctx_key({**context,'troop_id':2}))


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent re-index integration')
class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.project=self.base/'project'; (self.project/'Data').mkdir(parents=True)
        root,owner,self.loc=fixture(); self.root=root
        # The production Ruby reader intentionally cannot load arbitrary custom
        # _dump hooks. Opaque preservation is tested above at the codec layer;
        # this independent re-index fixture uses only native page fields.
        del owner.get('pages')[0].ivars['@opaque_fixture']
        (self.project/'Data/Map001.rvdata2').write_bytes(marshal_rb.dump(root))
        (self.project/'Data/System.rvdata2').write_bytes(marshal_rb.dump(RubyObject('RPG::System',{'@version_id':10,'@switches':backend.convert(['','one']),'@variables':backend.convert(['','one'])})))
        self.index=self.base/'index'
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.project),'--output',str(self.index)],check=True,capture_output=True)
        self.snap=structure.snapshot(root,self.loc,backend.object_by_id)

    def spec(self, mutation):
        change={'kind':'event','locator':{'map_id':1,'event_id':1,'page':1,'command_index':2},'proposal':'Reviewed structural test','mutation':mutation}
        path=self.base/'spec.json'; path.write_text(json.dumps({'changes':[change]})); return path,change

    def build(self, spec, no_reindex=False):
        from vxace_copy_patcher import build
        return build(self.index,self.project,spec,self.base/'copy',self.base/'audit',shutil.which('ruby'),ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py',no_reindex)

    def test_transaction_generates_post_validation_and_semantic_diff(self):
        original=(self.project/'Data/Map001.rvdata2').read_bytes()
        spec,change=self.spec({'action':'insert_commands','expected_list_sha256':self.snap['list_sha256'],'commands':[row(230,[1])]})
        result=self.build(spec)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['changes'][0]['structural']['before']['command_count'],3)
        self.assertEqual(result['changes'][0]['structural']['after']['command_count'],4)
        self.assertEqual(backend.load(self.base/'copy/Data/System.rvdata2')[0].get('version_id'),11)
        self.assertEqual(backend.load(self.project/'Data/System.rvdata2')[0].get('version_id'),10)
        self.assertTrue((self.base/'audit/semantic-diff.json').is_file())
        self.assertTrue(json.loads((self.base/'audit/post-validation/validation.json').read_text())['copy_mutation_ready'])
        self.assertEqual((self.project/'Data/Map001.rvdata2').read_bytes(),original)

    def test_failed_second_mutation_removes_entire_partial_copy(self):
        spec,change=self.spec({'action':'insert_commands','expected_list_sha256':self.snap['list_sha256'],'commands':[row(230,[1])]})
        spec.write_text(json.dumps({'changes':[change,change]}))
        with self.assertRaises(RuntimeError): self.build(spec)
        self.assertFalse((self.base/'copy').exists())
        self.assertTrue(json.loads((self.base/'audit/failure.json').read_text())['staged_copy_removed'])

    def test_structural_reindex_cannot_be_disabled(self):
        spec,change=self.spec({'action':'insert_commands','expected_list_sha256':self.snap['list_sha256'],'commands':[row(230,[1])]})
        with self.assertRaisesRegex(ValueError,'require'): self.build(spec,True)
        self.assertFalse((self.base/'copy').exists())
