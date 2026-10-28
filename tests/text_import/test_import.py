import csv
import io
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
sys.path.insert(0,str(ROOT/'tests/index_queries'))
sys.path.insert(0,str(ROOT/'tests/text_export'))
import vxace_text_export as te
import vxace_text_import as ti
from vxace_copy_patcher import current_inventory
import test_queries as fixtures
from test_codes import cmd

KEY='map:001/event:1/page:1/cmd:0'


class Import(unittest.TestCase):
    """Synthetic JSON index (same fixture approach as tests/text_export; no Ruby needed)."""
    def setUp(self):
        self.f=fixtures.Queries('test_search_all_scopes_exact_provenance_no_execution')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.index,self.project,self.base=self.f.index,self.f.project,self.f.base
        self.f.write('database/system.json',{'game_title':'Test Quest','currency_unit':'Gold','variables':['']+['v']*5,
            'elements':['','Fire'],'skill_types':[],'weapon_types':[],'armor_types':[],'terms':{}})
        self.f.write('database/actors.json',[None,{'__class__':'RPG::Actor','id':1,'name':'Eric','nickname':'Hero','description':'A brave one.\nReally.'}])
        self.f.write('database/states.json',[None,{'__class__':'RPG::State','id':1,'name':'Poison','message1':' is poisoned!','message2':'','message3':'','message4':''}])
        self.f.write('project.json',{'errors':[],'map_count':1,'script_count':1,'database_files_decoded':['CommonEvents.rvdata2','Troops.rvdata2','Actors.rvdata2','System.rvdata2']})
        self.f.write('database/common-events.json',[None,{'__class__':'RPG::CommonEvent','id':5,'name':'Shop','trigger':0,'list':[cmd(101,['',0,0,2]),cmd(401,['Welcome']),cmd(0)]}])
        self.f.write('database/troops.json',[None,{'__class__':'RPG::Troop','id':2,'name':'Slime','pages':[fixtures.page([cmd(0),cmd(101,['',0,0,2]),cmd(401,['Splat']),cmd(0)])]}])
        self.set_events([cmd(101,['Actor1',2,1,2]),cmd(401,['Hello \\N[1]!']),cmd(401,['Second line']),cmd(0)])
        self.n=0

    def set_events(self,rows):
        self.f.map['events']['1']['pages']=[fixtures.page(rows)];self.f.sync()

    def exported(self): return {e['key']:e for e in te.export_text(self.index,include_name_commands=True)['entries']}

    def csv(self,rows,bom=False,newline='\r\n'):
        """rows: key -> translation or (translation, fingerprint); fingerprints default to the current export."""
        self.n+=1;path=self.base/('edit%d.csv'%self.n);now=self.exported()
        buf=io.StringIO();w=csv.writer(buf,lineterminator=newline)
        w.writerow(['key','context','speaker','original','translation','fingerprint'])
        for key,val in rows.items():
            tr,fp=val if isinstance(val,tuple) else (val,now[key]['fingerprint'] if key in now else 'none')
            w.writerow([key,'ctx','',now[key]['text'] if key in now else '',tr,fp])
        path.write_bytes(buf.getvalue().encode('utf-8-sig' if bom else 'utf-8'))
        return path

    def run_import(self,rows,**opts):
        self.n+=1
        out=self.base/('out%d'%self.n);out.mkdir()
        csvp=self.csv(rows) if isinstance(rows,dict) else rows
        rep=ti.run(self.index,self.project,csvp,out/'spec.json',out/'report.md',out/'report.json',**opts)
        spec=out/'spec.json'
        return rep,(json.loads(spec.read_text(encoding='utf-8')) if spec.exists() else None),out

    def status(self,rep,key): return [r for r in rep['rows_detail'] if r['key']==key][0]

    def test_equal_lines_one_change_per_changed_line_exact_shapes(self):
        rep,spec,_=self.run_import({KEY:'Hello \\N[1]!\nZweite Zeile'})
        self.assertEqual(spec['title'],'Import edited text')
        self.assertEqual(spec['changes'],[{'kind':'event','locator':{'map_id':1,'event_id':1,'page':1,'command_index':2},
            'proposal':'Import edited text for %s (line 2).'%KEY,
            'mutation':{'action':'set_parameter','parameter_index':0,'value':'Zweite Zeile'}}])
        self.assertEqual(rep['counts']['applied'],1)

    def test_all_lines_changed_and_header_never_touched(self):
        rep,spec,_=self.run_import({KEY:'A\nB'})
        self.assertEqual([c['locator']['command_index'] for c in spec['changes']],[1,2])
        self.assertTrue(all(c['mutation']['parameter_index']==0 for c in spec['changes']))

    def test_shorter_refused_without_flag_padded_with_flag(self):
        rep,spec,_=self.run_import({KEY:'Only one'})
        self.assertEqual(rep['counts']['refused_line_count'],1);self.assertIsNone(spec)
        self.assertIn('--allow-shorter',self.status(rep,KEY)['reason'])
        rep,spec,_=self.run_import({KEY:'Only one'},allow_shorter=True)
        self.assertEqual([c['mutation']['value'] for c in spec['changes']],['Only one',''])
        self.assertIn('padded',self.status(rep,KEY)['notes'][0])

    def test_longer_refused_as_structural(self):
        rep,spec,_=self.run_import({KEY:'a\nb\nc'},allow_shorter=True)
        self.assertEqual(rep['counts']['refused_line_count'],1);self.assertIn('structural',self.status(rep,KEY)['reason'])

    def test_stale_fingerprint_and_unknown_key(self):
        rep,spec,_=self.run_import({KEY:('x\ny','0'*64),'map:009/event:1/page:1/cmd:0':('t','abc')})
        self.assertEqual((rep['counts']['stale'],rep['counts']['unknown'],rep['counts']['applied']),(1,1,0))
        self.assertIsNone(spec)

    def test_source_changed_after_export_is_stale(self):
        csvp=self.csv({KEY:'A\nB'})
        self.set_events([cmd(101,['Actor1',2,1,2]),cmd(401,['Changed']),cmd(401,['Second line']),cmd(0)])
        rep,_,_=self.run_import(csvp)
        self.assertEqual(rep['counts']['stale'],1)

    def test_unchanged_and_empty_rows_skipped(self):
        rep,spec,_=self.run_import({KEY:'Hello \\N[1]!\nSecond line','db:actors/1/name':''})
        self.assertEqual((rep['counts']['unchanged'],rep['counts']['skipped_empty'],rep['counts']['applied']),(1,1,0))

    def test_choices_with_branch_labels_and_count_rule(self):
        self.set_events([cmd(102,[['Yes','No'],2]),cmd(402,[0,'Yes']),cmd(101,['',0,0,2],1),cmd(401,['nested'],1),
                         cmd(402,[1,'No']),cmd(403,[6,None]),cmd(404),cmd(0)])
        rep,spec,_=self.run_import({KEY:'Ja | Nein'})
        self.assertEqual([(c['locator']['command_index'],c['mutation']['parameter_index'],c['mutation']['value']) for c in spec['changes']],
                         [(0,0,['Ja','Nein']),(1,1,'Ja'),(4,1,'Nein')])
        rep,spec,_=self.run_import({KEY:'Ja\nNein'})
        self.assertEqual(len(spec['changes']),3)
        rep,spec,_=self.run_import({KEY:'Only'})
        self.assertEqual(rep['counts']['refused_line_count'],1)

    def test_scrolling_and_common_and_troop(self):
        self.set_events([cmd(105,[2,False]),cmd(405,['Long ago']),cmd(405,['in a land']),cmd(0)])
        rep,spec,_=self.run_import({KEY:'Vor langer Zeit\nin einem Land','common:5/cmd:0':'Willkommen','troop:2/page:1/cmd:1':'Platsch'})
        self.assertEqual(rep['counts']['applied'],3)
        locs=sorted(json.dumps(c['locator'],sort_keys=True) for c in spec['changes'])
        self.assertEqual(locs,sorted([json.dumps({'map_id':1,'event_id':1,'page':1,'command_index':1},sort_keys=True),
                                      json.dumps({'map_id':1,'event_id':1,'page':1,'command_index':2},sort_keys=True),
                                      json.dumps({'common_event_id':5,'command_index':1},sort_keys=True),
                                      json.dumps({'troop_id':2,'page':1,'command_index':2},sort_keys=True)]))

    def test_name_commands(self):
        self.set_events([cmd(320,[1,'Renamed']),cmd(0)])
        rep,spec,_=self.run_import({KEY:'Neu'})
        self.assertEqual(spec['changes'][0]['mutation'],{'action':'set_parameter','parameter_index':1,'value':'Neu'})

    def test_database_field_and_multiline_rule(self):
        rep,spec,_=self.run_import({'db:actors/1/name':'Erik','db:actors/1/description':'Eine\nZeile','db:states/1/message1':'a\nb'})
        self.assertEqual((rep['counts']['applied'],rep['counts']['refused_invalid']),(2,1))
        self.assertIn({'kind':'database','locator':{'table':'actors','id':1},'proposal':'Import edited text for db:actors/1/name.',
                       'mutation':{'field':'name','value':'Erik'}},spec['changes'])

    def test_system_text_unsupported(self):
        rep,spec,_=self.run_import({'db:system/game_title':'Neu','db:system/elements/1':'Feuer'})
        self.assertEqual(rep['counts']['unsupported'],2);self.assertIsNone(spec)

    def test_map_display_name_goes_to_own_spec(self):
        snap={'display_name':'Quiet Meadow','map_sha256':'a'*64}
        with patch.object(ti,'map_name_snapshot',return_value=snap):
            rep,spec,out=self.run_import({'map:001/display_name':'Stille Wiese',KEY:'A\nB'})
        self.assertEqual(len(spec['changes']),2)
        second=json.loads((out/'spec.mapname-001.json').read_text(encoding='utf-8'))
        self.assertEqual(second['changes'],[{'kind':'map_name','locator':{'map_id':1},'proposal':'Import edited display name for map:001/display_name.',
            'mutation':{'action':'set_display_name','expected_map_sha256':'a'*64,'expected_display_name':'Quiet Meadow','value':'Stille Wiese'}}])
        with patch.object(ti,'map_name_snapshot',return_value=snap):
            rep,spec,_=self.run_import({'map:001/display_name':'two\nlines'})
        self.assertEqual(rep['counts']['refused_invalid'],1)

    def test_bom_quoting_and_excel_newlines(self):
        for bom in (False,True):
            path=self.csv({KEY:'Zeile "eins", ok\nZeile zwei'},bom=bom,newline='\r\n')
            rep,spec,_=self.run_import(path)
            self.assertEqual(spec['changes'][0]['mutation']['value'],'Zeile "eins", ok')
        raw=self.base/'raw.csv'
        raw.write_bytes(('key,translation,fingerprint\r\n%s,"A\r\nB",%s\r\n'%(KEY,self.exported()[KEY]['fingerprint'])).encode('utf-8'))
        rep,spec,_=self.run_import(raw)
        self.assertEqual([c['mutation']['value'] for c in spec['changes']],['A','B'])

    def test_missing_columns_refused(self):
        raw=self.base/'bad.csv';raw.write_text('key,original\nx,y\n',encoding='utf-8')
        with self.assertRaises(ValueError): self.run_import(raw)

    def test_control_characters_refused_escape_codes_preserved(self):
        rep,spec,_=self.run_import({KEY:'a\x07\nb'})
        self.assertEqual(rep['counts']['refused_invalid'],1)
        rep,spec,_=self.run_import({KEY:'a\tb\nc'})
        self.assertEqual(rep['counts']['refused_invalid'],1)
        rep,spec,_=self.run_import({KEY:'\\C[2]Rot\\C[0] \\V[1]\nx'})
        self.assertEqual(spec['changes'][0]['mutation']['value'],'\\C[2]Rot\\C[0] \\V[1]')

    def test_lint_warnings_do_not_refuse(self):
        rep,spec,_=self.run_import({KEY:'x'*60+'\nok'})
        st=self.status(rep,KEY);self.assertEqual(st['status'],'applied')
        self.assertTrue(any('line_too_wide' in w for w in st['warnings']))

    def test_duplicate_keys_not_applied(self):
        path=self.base/'dup.csv';fp=self.exported()[KEY]['fingerprint']
        path.write_text('key,translation,fingerprint\n%s,"A\nB",%s\n%s,"C\nD",%s\n'%(KEY,fp,KEY,fp),encoding='utf-8')
        rep,spec,_=self.run_import(path)
        self.assertEqual(rep['counts']['duplicate'],2);self.assertIsNone(spec)

    def test_output_guards(self):
        csvp=self.csv({KEY:'A\nB'});out=self.base/'g';out.mkdir()
        before=(current_inventory(self.project),current_inventory(self.index))
        for bad in (self.project/'spec.json',self.index/'spec.json'):
            with self.assertRaises(ValueError): ti.run(self.index,self.project,csvp,bad,out/'r.md')
        (out/'exists.json').write_text('{}')
        with self.assertRaises(ValueError): ti.run(self.index,self.project,csvp,out/'exists.json',out/'r.md')
        with self.assertRaises(ValueError): ti.run(self.index,self.project,csvp,out/'same',out/'same')
        self.assertEqual(before,(current_inventory(self.project),current_inventory(self.index)))
        self.assertEqual(sorted(p.name for p in out.iterdir()),['exists.json'])

    def test_stale_index_refused_and_nothing_written(self):
        csvp=self.csv({KEY:'A\nB'});(self.project/'Data/extra.rvdata2').write_bytes(b'new')
        out=self.base/'s';out.mkdir()
        with self.assertRaises(ValueError): ti.run(self.index,self.project,csvp,out/'spec.json',out/'r.md')
        self.assertEqual(list(out.iterdir()),[])

    def test_deterministic_order_independent_of_csv_order(self):
        rows={'db:actors/1/name':'Erik',KEY:'A\nB','common:5/cmd:0':'Willkommen'}
        _,a,_=self.run_import(rows)
        _,b,_=self.run_import(dict(reversed(list(rows.items()))))
        self.assertEqual(a,b)
        self.assertEqual(a['changes'][0]['locator'],{'common_event_id':5,'command_index':1})

    def test_cli_exit_codes_and_report_files(self):
        csvp=self.csv({KEY:'A\nB','db:system/game_title':'X'});out=self.base/'cli';out.mkdir()
        argv=[str(self.index),'--project',str(self.project),'--csv',str(csvp),'--spec-out',str(out/'s.json'),'--report',str(out/'r.md'),'--json',str(out/'r.json')]
        self.assertEqual(ti.main(argv),0)
        self.assertEqual(ti.main(argv),2)
        text=(out/'r.md').read_text(encoding='utf-8')
        self.assertIn('unsupported',text);self.assertIn('db:system/game_title',text)
        self.assertEqual(json.loads((out/'r.json').read_text(encoding='utf-8'))['counts']['applied'],1)


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for the independently authored native fixture')
class EndToEnd(unittest.TestCase):
    def test_import_plan_and_copy_changes_only_the_text(self):
        import vxace_python_mutator as backend
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        base=Path(tmp.name);game=base/'game';index=base/'index'
        subprocess.run(['ruby',str(ROOT/'tests/text_import/make_text_fixture.rb'),str(game)],check=True,capture_output=True)
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(game),'--output',str(index)],check=True,capture_output=True)
        entries={e['key']:e for e in te.export_text(index)['entries']}
        msg=entries[KEY];choice=entries['map:001/event:1/page:1/cmd:3']
        self.assertEqual(msg['lines'],['Hello traveler.','Welcome to town.'])
        edited=base/'edit.csv'
        with open(edited,'w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['key','context','speaker','original','translation','fingerprint'])
            w.writerow([msg['key'],msg['context'],'',msg['text'],'Hallo Reisender.\nWillkommen in der Stadt.',msg['fingerprint']])
            w.writerow([choice['key'],choice['context'],'',choice['text'],'Ja | Nein',choice['fingerprint']])
        out=base/'out';out.mkdir()
        self.assertEqual(ti.main([str(index),'--project',str(game),'--csv',str(edited),'--spec-out',str(out/'spec.json'),'--report',str(out/'report.md')]),0)
        spec=json.loads((out/'spec.json').read_text(encoding='utf-8'))
        self.assertEqual(len(spec['changes']),5)
        before=current_inventory(game)
        def run(tool,*a): return subprocess.run([sys.executable,str(ROOT/'tools'/tool),*a],capture_output=True,text=True)
        plan=run('vxace_patch_planner.py',str(index),'--project',str(game),'--spec',str(out/'spec.json'),'--output',str(base/'plan'))
        self.assertEqual(plan.returncode,0,plan.stderr)
        copy=run('vxace_copy_patcher.py',str(index),'--project',str(game),'--spec',str(out/'spec.json'),'--copy',str(base/'copy'),
                 '--audit',str(base/'audit'),'--backend','python')
        self.assertEqual(copy.returncode,0,copy.stderr+copy.stdout)
        self.assertEqual(current_inventory(game),before)
        after=current_inventory(base/'copy')
        self.assertEqual([k for k in after if after[k]!=before.get(k)],['Data/Map001.rvdata2'])
        root,_=backend.load(base/'copy/Data/Map001.rvdata2')
        page=root.get('events').get(1).get('pages')[0]
        by={}
        for c in page.get('list'):
            by.setdefault(c.get('code'),[]).append([x.data.decode() if hasattr(x,'data') else x for x in c.get('parameters')])
        self.assertEqual([p[0] for p in by[401]],['Hallo Reisender.','Willkommen in der Stadt.'])
        self.assertEqual(by[101],[['',0,0,2]])
        self.assertEqual(by[402],[[0,'Ja'],[1,'Nein']])


if __name__=='__main__': unittest.main()
