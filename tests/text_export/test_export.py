import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'tests/index_queries'))
import vxace_text_export as te
from vxace_copy_patcher import current_inventory
import test_queries as fixtures
from test_codes import cmd


class Export(unittest.TestCase):
    """Synthetic JSON index (the same fixture approach as tests/index_queries; no Ruby needed)."""
    def setUp(self):
        self.f=fixtures.Queries('test_search_all_scopes_exact_provenance_no_execution')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.index,self.project,self.base=self.f.index,self.f.project,self.f.base
        self.f.write('database/system.json',{'game_title':'Test Quest','currency_unit':'Gold','variables':['']+['v']*5,
            'elements':['','Fire'],'skill_types':['','Magic'],'weapon_types':['','Sword'],'armor_types':['','Shield'],
            'terms':{'basic':['Level','Lv'],'params':['Max HP'],'etypes':['Weapon'],'commands':['Fight','']}})
        self.f.write('database/actors.json',[None,{'__class__':'RPG::Actor','id':1,'name':'Eric','nickname':'Hero','description':'A brave one.\nReally.'},
                                              {'__class__':'RPG::Actor','id':2,'name':'Sam','nickname':'','description':''}])
        self.f.write('database/states.json',[None,{'__class__':'RPG::State','id':1,'name':'Poison','message1':' is poisoned!','message2':'','message3':'','message4':'recovers'}])
        self.f.write('database/skills.json',[None,{'__class__':'RPG::Skill','id':1,'name':'Fire','description':'Burns.','message1':' casts','message2':''}])
        self.f.write('project.json',{'errors':[],'map_count':1,'script_count':1,'database_files_decoded':['CommonEvents.rvdata2','Troops.rvdata2','Actors.rvdata2','System.rvdata2']})
        self.set_events([cmd(101,['Actor1',2,1,2]),cmd(401,['Hello \\N[1]!']),cmd(401,['Second line']),cmd(0)])

    def set_events(self,rows):
        self.f.map['events']['1']['pages']=[fixtures.page(rows)];self.f.sync()

    def export(self,**kw): return te.export_text(self.index,**kw)

    def entry(self,result,type_,n=0): return [e for e in result['entries'] if e['type']==type_][n]

    def codes(self,result): return [x['code'] for x in result['lint']['findings']]

    def msg(self,*lines,face='',**kw):
        self.set_events([cmd(101,[face,0,0,2])]+[cmd(401,[x]) for x in lines]+[cmd(0)])
        return self.export(**kw)

    def test_message_block_from_101_401(self):
        e=self.entry(self.export(),'message')
        self.assertEqual(e['lines'],['Hello \\N[1]!','Second line']);self.assertEqual(e['text'],'Hello \\N[1]!\nSecond line')
        self.assertEqual((e['face_name'],e['face_index'],e['background'],e['position'],e['speaker']),('Actor1',2,1,2,'Actor1[2]'))
        self.assertEqual(e['key'],'map:001/event:1/page:1/cmd:0')
        self.assertEqual((e['file'],e['path']),('maps/map-001.json',['events','1','pages',0,'list',0]))
        self.assertEqual(e['context'],'Map 001 - Quiet Meadow / Event 1 Gate, page 1 / command 0')

    def test_adjacent_blocks_split_and_empty_header_only(self):
        self.set_events([cmd(101,['',0,0,2]),cmd(401,['A']),cmd(101,['',0,0,2]),cmd(0)])
        r=self.export();msgs=[e for e in r['entries'] if e['type']=='message']
        self.assertEqual([m['lines'] for m in msgs],[['A'],[]])
        self.assertIn('empty_message',self.codes(r))

    def test_choices_with_cancel_and_branches(self):
        self.set_events([cmd(102,[['Yes','No'],2]),cmd(402,[0,'Yes']),cmd(101,['',0,0,2],1),cmd(401,['nested'],1),
                         cmd(402,[1,'No']),cmd(403,[6,None]),cmd(404),cmd(0)])
        r=self.export();c=self.entry(r,'choices')
        self.assertEqual((c['lines'],c['cancel_type'],c['cancel'],c['branch_labels']),(['Yes','No'],2,'choice 2',['Yes','No']))
        self.assertEqual([e['type'] for e in r['entries'] if e['scope']=='map' and e['type']!='map_name'],['choices','message'])

    def test_scrolling_text(self):
        self.set_events([cmd(105,[2,False]),cmd(405,['Long ago']),cmd(405,['in a land']),cmd(0)])
        e=self.entry(self.export(),'scrolling')
        self.assertEqual((e['lines'],e['speed'],e['no_fast']),(['Long ago','in a land'],2,False))

    def test_name_commands_optional(self):
        self.set_events([cmd(320,[1,'Renamed']),cmd(324,[1,'Nick']),cmd(325,[1,'Line1\nLine2']),cmd(0)])
        self.assertEqual([e for e in self.export()['entries'] if e['scope']=='map' and e['type']!='map_name'],[])
        r=self.export(include_name_commands=True)
        self.assertEqual([e['type'] for e in r['entries'] if e['scope']=='map' and e['type']!='map_name'],['actor_name','actor_nickname','actor_profile'])
        self.assertEqual(self.entry(r,'actor_profile')['lines'],['Line1','Line2'])

    def test_common_and_troop_scopes(self):
        self.f.write('database/common-events.json',[None,{'__class__':'RPG::CommonEvent','id':1,'name':'Shop','trigger':0,'list':[cmd(101,['',0,0,2]),cmd(401,['Welcome']),cmd(0)]}])
        self.f.write('database/troops.json',[None,{'__class__':'RPG::Troop','id':1,'name':'Slime','pages':[fixtures.page([cmd(101,['',0,0,2]),cmd(401,['Splat']),cmd(0)])]}])
        keys={e['key'] for e in self.export()['entries']}
        self.assertTrue({'common:1/cmd:0','troop:1/page:1/cmd:0'}<=keys)

    def test_database_and_system_text(self):
        by={e['key']:e for e in self.export()['entries']}
        for key,text in (('db:actors/1/name','Eric'),('db:actors/1/nickname','Hero'),('db:actors/1/description','A brave one.\nReally.'),
                         ('db:states/1/message1',' is poisoned!'),('db:states/1/message4','recovers'),('db:skills/1/message1',' casts'),
                         ('db:system/game_title','Test Quest'),('db:system/currency_unit','Gold'),('db:system/elements/1','Fire'),
                         ('db:system/skill_types/1','Magic'),('db:system/weapon_types/1','Sword'),('db:system/armor_types/1','Shield'),
                         ('db:system/terms/basic/0','Level'),('db:system/terms/params/0','Max HP'),('db:system/terms/etypes/0','Weapon'),
                         ('db:system/terms/commands/0','Fight'),('map:001/display_name','Quiet Meadow')):
            self.assertEqual(by[key]['text'],text,key)
        self.assertNotIn('db:actors/2/nickname',by);self.assertNotIn('db:system/terms/commands/1',by)
        self.assertEqual(by['db:actors/1/name']['path'],[1,'name'])

    def test_fingerprints_stable_across_runs_and_change_with_source(self):
        a=self.export();b=self.export()
        self.assertEqual([e['fingerprint'] for e in a['entries']],[e['fingerprint'] for e in b['entries']])
        self.set_events([cmd(101,['Actor1',2,1,2]),cmd(401,['Hello \\N[1]!']),cmd(401,['Second line!']),cmd(0)])
        self.assertNotEqual(self.entry(a,'message')['fingerprint'],self.entry(self.export(),'message')['fingerprint'])
        # Header parameters are part of the fingerprint, not only the text.
        self.set_events([cmd(101,['Actor1',3,1,2]),cmd(401,['Hello \\N[1]!']),cmd(401,['Second line']),cmd(0)])
        self.assertNotEqual(self.entry(a,'message')['fingerprint'],self.entry(self.export(),'message')['fingerprint'])

    def test_lint_line_count_and_width(self):
        self.assertIn('too_many_lines',self.codes(self.msg('a','b','c','d','e')))
        self.assertNotIn('too_many_lines',self.codes(self.msg('a','b','c','d')))
        self.assertIn('line_too_wide',self.codes(self.msg('x'*51)))
        self.assertNotIn('line_too_wide',self.codes(self.msg('x'*50)))
        self.assertIn('line_too_wide',self.codes(self.msg('x'*39,face='Actor1')))
        self.assertNotIn('line_too_wide',self.codes(self.msg('x'*38,face='Actor1')))
        self.assertNotIn('line_too_wide',self.codes(self.msg('\\C[2]'+'x'*50+'\\C[0]')))
        self.assertIn('line_too_wide',self.codes(self.msg('x'*30,max_width=20)))
        self.assertIn('too_many_lines',self.codes(self.msg('a','b','c',max_lines=2)))

    def test_lint_codes_and_references(self):
        r=self.msg('\\Z bad','\\V[9]','\\N[3]','\\C[40]','\\V[0]','\\N[2] ok',max_lines=10)
        self.assertEqual([(x['code'],x['line']) for x in r['lint']['findings']],
                         [('unknown_control_code',1),('reference_out_of_range',2),('reference_out_of_range',3),
                          ('color_out_of_range',4),('reference_out_of_range',5)])
        self.assertIn('malformed_control_code',self.codes(self.msg('\\V[x]')))
        self.assertIn('reference_out_of_range',self.codes(self.msg('\\I[10]',icon_count=10)))
        self.assertNotIn('reference_out_of_range',self.codes(self.msg('\\I[9999]')))

    def test_lint_whitespace_and_empty(self):
        r=self.msg('trail ','two  spaces','  indented ok')
        self.assertEqual([(x['code'],x['line']) for x in r['lint']['findings']],[('trailing_whitespace',1),('doubled_space',2)])
        self.assertIn('empty_message',self.codes(self.msg('   ')))
        self.assertEqual(self.codes(self.msg('Fine text')),[])

    def test_lint_counts_per_map_and_truncation(self):
        r=self.msg('a ','b ')
        self.assertEqual(r['lint']['counts_by_group']['map:001'],{'total':2,'trailing_whitespace':2})
        r=self.export(max_findings=1)
        self.assertEqual((len(r['lint']['findings']),r['lint']['finding_count'],r['lint']['findings_truncated']),(1,2,True))
        self.assertTrue(all(x['heuristic'] for x in r['lint']['findings']))

    def test_invalid_options_refused(self):
        for kw in ({'max_width':0},{'max_lines':True},{'max_findings':-1},{'icon_count':0}):
            with self.subTest(kw=kw),self.assertRaises(ValueError): self.export(**kw)

    def test_opaque_command_refuses(self):
        self.set_events([{'__ref__':3},cmd(0)])
        with self.assertRaises(ValueError): self.export()

    def test_csv_bom_escaping_and_columns(self):
        self.set_events([cmd(101,['',0,0,2]),cmd(401,['He said "hi", then']),cmd(401,['line two']),cmd(0)])
        out=self.base/'out'/'t.csv'
        te.run(self.index,self.project,csv_path=out)
        raw=out.read_bytes();self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
        rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline='')))
        self.assertEqual(rows[0],['key','context','speaker','original','translation','fingerprint'])
        row=next(r for r in rows if r[0]=='map:001/event:1/page:1/cmd:0')
        self.assertEqual((row[3],row[4]),('He said "hi", then\nline two',''));self.assertEqual(len(row[5]),64)

    def test_markdown_groups_and_word_counts(self):
        out=self.base/'t.md';te.run(self.index,self.project,markdown_path=out)
        md=out.read_text(encoding='utf-8')
        self.assertIn('## Map 001 - Quiet Meadow',md);self.assertIn('### Event 1 Gate, page 1 (4 words)',md)
        self.assertIn('> Hello \\N[1]!',md);self.assertIn('> Second line',md)

    def test_end_to_end_cli_outputs_and_source_unchanged(self):
        before=current_inventory(self.project);ibefore=current_inventory(self.index)
        o={k:self.base/'rep'/('t.'+k) for k in ('json','csv','md')}
        p=subprocess.run([sys.executable,str(ROOT/'tools/vxace_text_export.py'),str(self.index),'--project',str(self.project),
                          '--json',str(o['json']),'--csv',str(o['csv']),'--markdown',str(o['md'])],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        report=json.loads(o['json'].read_text(encoding='utf-8'))
        self.assertTrue(report['read_only']);self.assertFalse(report['mutation_authorized']);self.assertFalse(report['import_enabled'])
        self.assertTrue(report['source_unchanged']);self.assertEqual(report['entry_count'],len(report['entries']))
        self.assertTrue(o['csv'].read_bytes().startswith(b'\xef\xbb\xbf'))
        self.assertEqual(current_inventory(self.project),before);self.assertEqual(current_inventory(self.index),ibefore)

    def test_output_guards_and_stale_refusal(self):
        base=[str(self.index),'--project',str(self.project)]
        for bad in (self.project/'x.json',self.index/'x.json',self.project/'Data/x.json'):
            self.assertEqual(te.main(base+['--json',str(bad)]),2);self.assertFalse(bad.exists())
        existing=self.base/'exists.json';existing.write_text('keep')
        self.assertEqual(te.main(base+['--json',str(existing)]),2);self.assertEqual(existing.read_text(),'keep')
        same=self.base/'same.out'
        self.assertEqual(te.main(base+['--json',str(same),'--csv',str(same)]),2);self.assertFalse(same.exists())
        self.assertEqual(te.main(base),2)
        good=self.base/'stale.json';(self.project/'Data/source.rvdata2').write_bytes(b'changed')
        self.assertEqual(te.main(base+['--json',str(good)]),2);self.assertFalse(good.exists())


if __name__=='__main__': unittest.main()
