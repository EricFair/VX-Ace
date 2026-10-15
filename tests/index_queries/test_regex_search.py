import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_regex_search as regex
from vxace_search import search as literal
from vxace_copy_patcher import current_inventory
import test_queries as fixtures


class RegexTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.Queries('test_search_all_scopes_exact_provenance_no_execution')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.index=self.fixture.index;self.project=self.fixture.project;self.base=self.fixture.base

    def test_regex_all_scopes_provenance_case_and_literal_unchanged(self):
        before=current_inventory(self.project);indexed=current_inventory(self.index)
        result=regex.search(self.index,r'need[l]e')
        self.assertEqual(result['matches'],5)
        self.assertEqual({hit['scope'] for hit in result['hits']},{'events','database','scripts'})
        hit=next(hit for hit in result['hits'] if hit.get('event_scope')=='map')
        self.assertEqual(hit['path'],['events','1','pages',0,'list',1,'parameters',0])
        self.assertEqual((hit['page'],hit['command_index'],hit['command_code']),(1,1,401))
        self.assertEqual(regex.search(self.index,'STRASSE')['matches'],0)
        self.assertEqual(literal(self.index,'STRASSE')['matches'],1)
        self.assertEqual(literal(self.index,'need[l]e')['matches'],0)
        self.assertEqual(regex.search(self.index,'NEEDLE',case_sensitive=True)['matches'],0)
        self.assertEqual(current_inventory(self.project),before);self.assertEqual(current_inventory(self.index),indexed)

    def test_code_scope_pagination_and_matching_field_counts(self):
        self.assertEqual(regex.search(self.index,r'needle\s+(common|troop)',code=108)['matches'],2)
        first=regex.search(self.index,'needle',limit=2);second=regex.search(self.index,'needle',limit=2,offset=2)
        self.assertEqual((first['matches'],first['returned'],first['next_offset']),(5,2,2))
        self.assertNotEqual(first['hits'],second['hits'])
        self.assertEqual(regex.search(self.index,'needle',offset=99)['returned'],0)
        self.assertEqual(regex.search(self.index,r'^Quiet\s+Meadow$',scopes=['maps'])['matches'],1)
        self.assertEqual(regex.bounded_matches('a',False,['aaaa']),[True])
        self.assertEqual(regex.bounded_matches('^$',False,['','x']),[True,False])

    def test_invalid_patterns_and_strict_options_refuse(self):
        for pattern in ('[','(?P<','a{999999999999999999999}', '', 'x'*513, 'x\ny',None):
            with self.assertRaises(ValueError):regex.search(self.index,pattern)
        for options in ({'code':True},{'scopes':[]},{'scopes':['bad']},{'scopes':['maps'],'code':401},
                        {'case_sensitive':1},{'limit':True},{'offset':-1},{'limit':1001}):
            with self.assertRaises(ValueError):regex.search(self.index,'needle',**options)

    def test_actual_catastrophic_pattern_is_killed_and_no_report_written(self):
        self.fixture.map['events']['1']['pages'][0]['list'][1]['parameters']=['a'*32+'!'];self.fixture.sync()
        start=time.monotonic()
        with patch.object(regex,'WORKER_TIMEOUT',0.4):
            code=regex.main([str(self.index),'--project',str(self.project),'--output',str(self.base/'timed-out'),
                             '--pattern','(a+)+$','--scope','events'])
        self.assertEqual(code,2);self.assertLess(time.monotonic()-start,4)
        self.assertFalse((self.base/'timed-out').exists())

    def test_text_ipc_result_and_candidate_budgets_refuse(self):
        with self.assertRaises(ValueError):regex.bounded_matches('x',False,['x'*(regex.MAX_TEXT_CHARS+1)])
        with patch.object(regex,'MAX_INPUT_BYTES',100):
            with self.assertRaises(ValueError):regex.search(self.index,'needle')
        with patch.object(regex,'MAX_CANDIDATES',1):
            with self.assertRaises(ValueError):regex.search(self.index,'needle')
        with patch.object(regex,'MAX_RESULT_BYTES',100):
            with self.assertRaises(ValueError):regex.search(self.index,'needle')

    def test_worker_failure_truncation_and_nonboolean_masks_refuse(self):
        for result in (subprocess.CompletedProcess([],1,b'',b'failure'),subprocess.CompletedProcess([],0,b'not-json',b''),
                       subprocess.CompletedProcess([],0,b'{"matched":[]}',b''),subprocess.CompletedProcess([],0,b'{"matched":[1]}',b''),
                       subprocess.CompletedProcess([],0,b'{"matched":[true],"extra":true}',b'')):
            with patch.object(regex.subprocess,'run',return_value=result):
                with self.assertRaises(ValueError):regex.bounded_matches('x',False,['x'])
        with patch.object(regex,'MAX_OUTPUT_BYTES',2):
            with self.assertRaises(ValueError):regex.bounded_matches('x',False,['x'])

    def test_cli_freshness_external_output_and_nonexecution(self):
        self.fixture.map['note']='raise "NEVER EXECUTE"';self.fixture.sync()
        before=current_inventory(self.project);output=self.base/'report'
        result=subprocess.run([sys.executable,str(ROOT/'tools/vxace_regex_search.py'),str(self.index),'--project',str(self.project),
                               '--pattern',r'raise\s+"NEVER EXECUTE"','--scope','maps','--output',str(output)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads((output/'regex-search.json').read_text());self.assertEqual(report['matches'],1)
        self.assertTrue(report['source_unchanged']);self.assertFalse(report['mutation_authorized'])
        self.assertEqual(current_inventory(self.project),before)
        args=[str(self.index),'--project',str(self.project),'--pattern','needle','--output',str(self.project/'bad')]
        self.assertEqual(regex.main(args),2);self.assertFalse((self.project/'bad').exists())
        (self.project/'Data/source.rvdata2').write_bytes(b'changed')
        args[-1]=str(self.base/'stale');self.assertEqual(regex.main(args),2);self.assertFalse((self.base/'stale').exists())

    def test_changed_index_during_worker_refuses_complete_result(self):
        original=regex.bounded_matches
        def changed(*args):
            result=original(*args)
            self.fixture.map['note']='changed during matching';self.fixture.sync()
            return result
        with patch.object(regex,'bounded_matches',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'changed'):regex.search(self.index,'needle')

    def test_worker_ignores_pythonpath_and_does_not_import_project_code(self):
        trap=self.base/'untrusted';trap.mkdir();marker=self.base/'must-not-exist.txt'
        (trap/'re.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("executed")\nraise RuntimeError("trap")\n')
        with patch.dict('os.environ',{'PYTHONPATH':str(trap)}):
            self.assertEqual(regex.bounded_matches('a+',False,['aaa','bbb']),[True,False])
        self.assertFalse(marker.exists())


if __name__=='__main__':unittest.main()
