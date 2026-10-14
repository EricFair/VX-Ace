import json,tempfile,unittest
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[2]

def mod(name,file):
    s=importlib.util.spec_from_file_location(name,ROOT/file); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
impact=mod('impact','tools/vxace_impact.py'); sem=mod('sem','tools/vxace_semantic_diff.py')

class ImpactTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.r=Path(self.t.name); (self.r/'codex').mkdir(); (self.r/'database').mkdir()
        (self.r/'codex/graph.json').write_text(json.dumps({'nodes':[{'id':'map:1:event:1:page:1','label':'Gate'},{'id':'switch:1','label':'QuestStarted'}], 'edges':[{'from':'switch:1','to':'map:1:event:1:page:1','relation':'read_by'}]}))
        (self.r/'codex/maps.json').write_text(json.dumps([{'map_id':1,'name':'Start','events':[{'event_id':1,'name':'Gate','pages':[{'page':1,'switches':[{'id':1,'name':'QuestStarted','roles':['read']}]}]}]}]))
        (self.r/'codex/scripts.json').write_text(json.dumps({'scripts':[{'index':2,'name':'BattleExt','path':'002_BattleExt.rb','classes':['Game_Battler'],'methods':['Game_Battler#item_apply'],'aliases':[],'save_hooks':[],'collision_candidates':[{'method':'Game_Battler#item_apply','severity':'high'}]}]}))
        (self.r/'database/actors.json').write_text(json.dumps([None,{'id':1,'name':'Alicia'}]))
    def tearDown(self): self.t.cleanup()
    def spec(self,changes):
        p=self.r/'spec.json'; p.write_text(json.dumps({'title':'x','changes':changes})); return p
    def test_event_dependencies(self):
        r=impact.build(self.r,self.spec([{'kind':'event','locator':{'map_id':1,'event_id':1,'page':1}}])); self.assertEqual(r['impacts'][0]['dependencies'][0]['node']['id'],'switch:1')
    def test_script_collision_high_risk(self):
        r=impact.build(self.r,self.spec([{'kind':'script','script_path':'002_BattleExt.rb'}])); self.assertEqual(r['high_risk_count'],1)
    def test_database_target_verified(self):
        r=impact.build(self.r,self.spec([{'kind':'database','locator':{'table':'actors','id':1}}])); self.assertEqual(r['impacts'][0]['target']['name'],'Alicia')
    def test_missing_target_refused(self):
        with self.assertRaises(ValueError): impact.build(self.r,self.spec([{'kind':'event','locator':{'map_id':9,'event_id':1,'page':1}}]))

class SemanticTests(unittest.TestCase):
    def mk(self,root,systems,edges=None):
        (root/'codex').mkdir(parents=True); (root/'codex/systems.json').write_text(json.dumps(systems)); (root/'codex/state-machines.json').write_text('[]'); (root/'codex/graph.json').write_text(json.dumps({'nodes':[],'edges':edges or []})); (root/'codex/scripts.json').write_text(json.dumps({'scripts':[]}))
    def test_semantic_added_system(self):
        with tempfile.TemporaryDirectory() as td:
            b=Path(td)/'b'; a=Path(td)/'a'; self.mk(b,[]); self.mk(a,[{'id':'quest-1','type':'quest_candidate'}]); r=sem.build(b,a); self.assertEqual(r['sections']['systems']['added'][0]['id'],'quest-1')
    def test_semantic_edge_change(self):
        with tempfile.TemporaryDirectory() as td:
            b=Path(td)/'b'; a=Path(td)/'a'; self.mk(b,[]); self.mk(a,[],[{'from':'switch:1','to':'map:1','relation':'read_by'}]); r=sem.build(b,a); self.assertEqual(len(r['sections']['graph_edges']['added']),1)
    def test_no_change(self):
        with tempfile.TemporaryDirectory() as td:
            b=Path(td)/'b'; a=Path(td)/'a'; self.mk(b,[]); self.mk(a,[]); r=sem.build(b,a); self.assertFalse(r['changed'])

if __name__=='__main__': unittest.main()
