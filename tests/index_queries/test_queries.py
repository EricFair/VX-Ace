import copy
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
import vxace_index_query as access
from vxace_search import search, main as search_main
from vxace_event_lint import lint, main as lint_main, FLAGS
from vxace_copy_patcher import current_inventory


def command(code,p=None,indent=0):
    return {'__class__':'RPG::EventCommand','code':code,'indent':indent,'parameters':p or []}


def page(rows=None,trigger=0,**flags):
    return {'__class__':'RPG::Event::Page','trigger':trigger,
            'condition':{'__class__':'RPG::Event::Page::Condition',**{f:False for f in FLAGS},**flags},
            'list':rows if rows is not None else [command(0)]}


class Queries(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.index=self.base/'index'; self.project=self.base/'game'
        (self.project/'Data').mkdir(parents=True)
        (self.project/'Data/source.rvdata2').write_bytes(b'fixture-not-executed')
        self.write('project.json',{'errors':[],'map_count':1,'script_count':1,'database_files_decoded':['CommonEvents.rvdata2','Troops.rvdata2','Actors.rvdata2']})
        inventory=current_inventory(self.project)
        self.write('manifest.json',{'read_only':True,'files':[{'path':k,'sha256':v} for k,v in inventory.items()]})
        self.map={'__class__':'RPG::Map','display_name':'Quiet Meadow','note':'map note','events':{'1':{
            '__class__':'RPG::Event','id':1,'name':'Gate','pages':[page([command(101,['',0,0,2]),command(401,['Straße needle']),command(0)])]}}}
        self.sync()
        self.write('database/common-events.json',[None,{'__class__':'RPG::CommonEvent','id':1,'name':'Common','trigger':0,'list':[command(108,['needle common']),command(0)]}])
        self.write('database/troops.json',[None,{'__class__':'RPG::Troop','id':1,'name':'Slime','pages':[page([command(108,['needle troop']),command(0)])]}])
        self.write('database/actors.json',[None,{'__class__':'RPG::Actor','id':1,'name':'Needle Knight','note':'actor text'}])
        self.write('scripts/order.json',{'scripts':[{'index':0,'path':'000_Test.rb'}]})
        (self.index/'scripts/000_Test.rb').write_text('raise "DO NOT EXECUTE"\n# needle script\n',encoding='utf-8')

    def write(self,path,value):
        file=self.index/path; file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(value),encoding='utf-8')

    def sync(self): self.write('maps/map-001.json',self.map)

    def run_lint(self,pages):
        self.map['events']['1']['pages']=pages; self.sync(); return lint(self.index)

    def test_search_all_scopes_exact_provenance_no_execution(self):
        before=current_inventory(self.project); index_before=current_inventory(self.index)
        result=search(self.index,'needle')
        self.assertEqual(result['matches'],5)
        self.assertEqual({x['scope'] for x in result['hits']},{'events','database','scripts'})
        event=next(x for x in result['hits'] if x.get('event_scope')=='map')
        self.assertEqual((event['map_id'],event['event_id'],event['page'],event['command_index'],event['command_code']),(1,1,1,1,401))
        self.assertEqual(event['path'],['events','1','pages',0,'list',1,'parameters',0])
        self.assertEqual(next(x for x in result['hits'] if x['scope']=='scripts')['line'],2)
        self.assertEqual(current_inventory(self.project),before); self.assertEqual(current_inventory(self.index),index_before)

    def test_literal_unicode_case_and_no_regex(self):
        self.assertEqual(search(self.index,'STRASSE')['matches'],1)
        self.assertEqual(search(self.index,'NEEDLE',case_sensitive=True)['matches'],0)
        self.assertEqual(search(self.index,'needle.*')['matches'],0)
        self.assertEqual(search(self.index,'Meadow',scopes=['maps'])['matches'],1)

    def test_code_only_and_combined_query_have_distinct_semantics(self):
        result=search(self.index,code=108)
        self.assertEqual(result['matches'],2)
        self.assertEqual({h['event_scope'] for h in result['hits']},{'common_event','troop'})
        self.assertEqual(search(self.index,'troop',108)['matches'],1)
        self.assertEqual(search(self.index,code=0)['matches'],3)

    def test_pagination_preserves_complete_total_and_bounded_excerpts(self):
        first=search(self.index,'needle',limit=2)
        second=search(self.index,'needle',limit=2,offset=2)
        self.assertEqual((first['matches'],first['returned'],first['next_offset']),(5,2,2))
        self.assertTrue(first['truncated']); self.assertNotEqual(first['hits'],second['hits'])
        self.assertEqual(search(self.index,'needle',offset=99)['returned'],0)
        self.map['events']['1']['pages'][0]['list'][1]['parameters']=['needle'+'x'*1000]; self.sync()
        hit=search(self.index,'needle',scopes=['events'])['hits'][0]
        self.assertEqual(len(hit['excerpt']),300); self.assertTrue(hit['excerpt_truncated'])

    def test_search_invalid_arguments_refused(self):
        for kwargs in ({},{'query':''},{'query':'x\ny'},{'query':'x'*513},{'code':True},{'code':-1},
                       {'query':'x','limit':1001},{'query':'x','offset':-1},{'query':'x','scopes':['unknown']},
                       {'code':108,'scopes':['scripts']}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError): search(self.index,**kwargs)

    def test_unconditional_shadow_reports_highest_only_one_based(self):
        result=self.run_lint([page(),page(),page()])
        findings=[x for x in result['findings'] if x['code']=='unconditional_page_shadow']
        self.assertEqual(len(findings),1)
        self.assertEqual(findings[0]['evidence']['page'],3); self.assertEqual(findings[0]['shadowed_pages'],[1,2])

    def test_conditional_later_page_does_not_permanently_shadow(self):
        result=self.run_lint([page(),page(self_switch_valid=True)])
        self.assertFalse(result['findings']); self.assertTrue(result['coverage_complete'])

    def test_missing_conditions_are_unknown_not_unconditional(self):
        unknown=page(); del unknown['condition']['actor_valid']
        result=self.run_lint([page(),unknown])
        self.assertEqual([x['code'] for x in result['findings']],['unknown_page_conditions'])
        self.assertFalse(result['coverage_complete'])

    def test_highest_unconditional_autorun_without_release_warns(self):
        result=self.run_lint([page([command(115),command(0)],trigger=3)])
        self.assertEqual([x['code'] for x in result['findings']],['possible_autorun_lock'])

    def test_terminating_cutscene_pattern_not_misreported(self):
        result=self.run_lint([page([command(123,['A',0]),command(0)],trigger=3),page(self_switch_valid=True)])
        self.assertFalse(result['findings'])

    def test_possible_release_scripts_common_calls_require_runtime_review(self):
        for code,p in ((201,[0,1,0,0,2,0]),(214,[]),(353,[]),(354,[]),(117,[1]),(355,['custom']),
                       (205,[0,{}]),(111,[12,'script']),(122,[1,1,0,4,'script'])):
            with self.subTest(code=code):
                result=self.run_lint([page([command(code,p),command(0)],trigger=3)])
                self.assertEqual([x['code'] for x in result['findings']],['autorun_runtime_review'])

    def test_labels_local_case_sensitive_and_duplicates_explicit(self):
        result=self.run_lint([page([command(118,['Foo']),command(118,['Foo']),command(119,['foo']),command(0)])])
        self.assertEqual([x['code'] for x in result['findings']],['duplicate_label','missing_label'])
        self.assertEqual(result['findings'][1]['evidence']['path'][-1],2)

    def test_terminator_and_continuations_checked_all_scopes(self):
        result=self.run_lint([page([command(401,['orphan'])])])
        self.assertEqual({x['code'] for x in result['findings']},{'missing_root_terminator','orphan_continuation'})
        self.assertEqual(result['command_lists_checked'],3)

    def test_opaque_command_suppresses_unproven_missing_label(self):
        result=self.run_lint([page([{'__ref__':3},command(119,['maybe opaque label']),command(0)])])
        self.assertEqual([x['code'] for x in result['findings']],['opaque_command'])
        self.assertFalse(result['coverage_complete'])

    def test_complete_work_budgets_refuse_even_no_matches(self):
        with patch.object(access,'MAX_STEPS',3),self.assertRaisesRegex(ValueError,'budget'):
            search(self.index,'no such text')
        with patch.object(access,'MAX_FILE_BYTES',5),self.assertRaisesRegex(ValueError,'budget'):
            search(self.index,'x')
        with patch.object(access,'MAX_TOTAL_BYTES',200),self.assertRaisesRegex(ValueError,'budget'):
            lint(self.index)

    def test_paths_cannot_escape_via_script_order(self):
        (self.base/'secret.rb').write_text('needle')
        self.write('scripts/order.json',{'scripts':[{'index':0,'path':'../../secret.rb'}]})
        with self.assertRaisesRegex(ValueError,'Unsafe'): search(self.index,'needle')

    def test_index_integrity_and_missing_decoded_data_refused(self):
        data=access.Index(self.index)
        data.json('database/actors.json')
        self.write('database/actors.json',[])
        with self.assertRaisesRegex(ValueError,'changed'): data.unchanged()
        (self.index/'database/troops.json').unlink()
        with self.assertRaisesRegex(ValueError,'missing'): access.Index(self.index)

    def test_changed_source_during_analysis_does_not_write_report(self):
        def change(data):
            (self.project/'Data/source.rvdata2').write_bytes(b'changed')
            return search(data,'needle')
        with self.assertRaisesRegex(ValueError,'changed'):
            access.execute(self.index,self.project,self.base/'report',change,'search')
        self.assertFalse((self.base/'report').exists())

    def test_index_changes_between_reads_and_file_set_changes_refused(self):
        data=access.Index(self.index); data.json('database/actors.json')
        self.write('database/actors.json',[])
        with self.assertRaisesRegex(ValueError,'changed'): data.json('database/actors.json')
        data=access.Index(self.index); data.paths('database')
        self.write('database/extra.json',[])
        with self.assertRaisesRegex(ValueError,'file set changed'): data.unchanged()

    def test_missing_map_and_incomplete_script_order_refused(self):
        self.write('scripts/order.json',{'scripts':[]})
        with self.assertRaisesRegex(ValueError,'incomplete'): search(self.index,'needle',scopes=['scripts'])
        (self.index/'maps/map-001.json').unlink()
        with self.assertRaisesRegex(ValueError,'missing'): access.Index(self.index)

    def test_linked_index_input_is_refused(self):
        linked=self.base/'linked-index'
        try: linked.symlink_to(self.index,target_is_directory=True)
        except OSError: self.skipTest('Host does not grant symbolic-link creation')
        with self.assertRaisesRegex(ValueError,'Linked'): access.Index(linked)

    @unittest.skipUnless(shutil.which('ruby'),'Independent Ruby reader required')
    def test_search_consumes_independent_reader_output_without_modifying_fixture(self):
        game=self.base/'ruby-game'; index=self.base/'ruby-index'
        subprocess.run(['ruby',str(ROOT/'tests/project_reader/make_fixture.rb'),str(game)],check=True,capture_output=True)
        before=current_inventory(game)
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(game),'--output',str(index)],check=True,capture_output=True)
        result=search(index,'Game_Battler',scopes=['scripts'])
        self.assertEqual(result['matches'],3)
        self.assertTrue(all(x['line']==1 for x in result['hits']))
        # This legacy synthetic fixture intentionally omits troop pages. The
        # analyzer must refuse complete event coverage rather than skip it.
        with self.assertRaisesRegex(ValueError,'Opaque troop'): lint(index)
        self.assertEqual(current_inventory(game),before)

    def test_cli_freshness_reports_and_existing_output_protection(self):
        report=self.base/'report'
        args=[str(self.index),'--project',str(self.project),'--output',str(report),'--text','needle']
        self.assertEqual(search_main(args),0)
        r=json.loads((report/'search.json').read_text())
        self.assertTrue(r['source_unchanged']); self.assertTrue(r['read_index_files_unchanged']); self.assertFalse(r['mutation_authorized'])
        self.assertEqual(search_main(args),2)
        (self.project/'new.txt').write_text('change')
        args[4]=str(self.base/'stale-report')
        self.assertEqual(search_main(args),2); self.assertFalse((self.base/'stale-report').exists())

    def test_cli_outputs_cannot_enter_source_or_index(self):
        for target in (self.project/'report',self.index/'report'):
            with self.subTest(target=target):
                self.assertEqual(search_main([str(self.index),'--project',str(self.project),'--output',str(target),'--text','needle']),2)
                self.assertFalse(target.exists())

    def test_lint_exit_codes_distinguish_diagnostics_from_refusal(self):
        args=[str(self.index),'--project',str(self.project),'--output',str(self.base/'clean')]
        self.assertEqual(lint_main(args),0)
        self.run_lint([page(trigger=3)])
        args[4]=str(self.base/'warn'); self.assertEqual(lint_main(args),3)
        self.write('project.json',{'errors':[{'file':'unknown'}]})
        args[4]=str(self.base/'partial'); self.assertEqual(lint_main(args),2)


if __name__=='__main__': unittest.main()
