import json
from pathlib import Path
import shutil,subprocess,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_map_shops as shops
import vxace_copy_patcher as patcher
from vxace_index_query import Index
from vxace_python_mutator import load,marshal_rb,apply as backend_apply
from rpgvxace_mcp.rubytypes import RubyObject,RubyString

PLAIN_GOODS=[{'type':'weapon','id':1,'price':None},{'type':'armor','id':2,'price':250},{'type':'item','id':3,'price':0}]


def clone(value):return marshal_rb.load(marshal_rb.dump(value))
def command(code,parameters,indent=0):return RubyObject('RPG::EventCommand',{'@code':code,'@indent':indent,'@parameters':parameters})
def text(value):return RubyString(value.encode('utf-8'),{'E':True})


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native fixture')
class ShopTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve()
        self.game=self.base/'game';self.index=self.base/'index'
        subprocess.run(['ruby',str(ROOT/'tests/structure/make_shop_fixture.rb'),str(self.game)],check=True,capture_output=True)
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)
        self.path=self.game/'Data/Map001.rvdata2';self.root,_=load(self.path);self.arrays=shops.goods_arrays(self.path)

    # ---- helpers
    def page(self,root,event_id):return shops.locate(root,event_id).get('pages')[0]

    def make(self,root=None,event_id=1,goods=None,purchase_only=False,arrays=None,**over):
        root=root or self.root;arrays=arrays or self.arrays;event=shops.locate(root,event_id)
        value={'action':'add_shop','expected_map_sha256':shops.digest(root),'expected_event_sha256':shops.digest(event),
               'expected_list_sha256':shops.digest(event.get('pages')[0].get('list')),
               'expected_items_sha256':shops.digest(arrays['item']),'expected_weapons_sha256':shops.digest(arrays['weapon']),
               'expected_armors_sha256':shops.digest(arrays['armor']),'goods':[dict(g) for g in (goods or PLAIN_GOODS)],'purchase_only':purchase_only}
        value.update(over);return value

    def native(self,mutation,event_id=1):return {'event_id':event_id,**mutation}

    def codes(self,root,event_id):return [c.get('code') for c in self.page(root,event_id).get('list')]

    def spec(self,event_id=1,**kwargs):
        mutation=self.make(event_id=event_id,**kwargs)
        value={'changes':[{'kind':'map_shop','locator':{'map_id':1,'event_id':event_id},'proposal':'Add a reviewed shop.','mutation':mutation}]}
        path=self.base/'spec.json';path.write_text(json.dumps(value));return path,value

    def build(self,event_id=1,**kwargs):
        spec,_=self.spec(event_id,**kwargs)
        return patcher.build(self.index,self.game,spec,self.base/'copy',self.base/'audit',shutil.which('ruby'),ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')

    def refuses(self,root,mutation,event_id=1,arrays=None):
        before=marshal_rb.dump(root)
        with self.assertRaises(ValueError):shops.apply(root,self.native(mutation,event_id),arrays or self.arrays)
        self.assertEqual(marshal_rb.dump(root),before)

    # ---- snapshot
    def test_snapshot_reports_both_shapes_hashes_and_id_ranges(self):
        blank=shops.indexed_snapshot(Index(self.index),self.game,1,1);notice=shops.indexed_snapshot(Index(self.index),self.game,1,2)
        self.assertEqual((blank['event_shape'],blank['append_supported'],blank['dialogue_lines']),('blank',True,[]))
        self.assertEqual((notice['event_shape'],notice['dialogue_lines']),('dialogue',['Welcome!','Take a look.']))
        self.assertEqual(blank['id_ranges'],{'item':{'min_id':1,'max_id':3,'count':3},'weapon':{'min_id':1,'max_id':2,'count':2},'armor':{'min_id':1,'max_id':2,'count':2}})
        mutation=self.make()
        self.assertEqual((blank['map_sha256'],blank['event_sha256'],blank['list_sha256']),(mutation['expected_map_sha256'],mutation['expected_event_sha256'],mutation['expected_list_sha256']))
        self.assertEqual((blank['items_sha256'],blank['weapons_sha256'],blank['armors_sha256']),(mutation['expected_items_sha256'],mutation['expected_weapons_sha256'],mutation['expected_armors_sha256']))

    def test_snapshot_cli_writes_report_and_refuses_unsupported_event_without_authorizing(self):
        out=self.base/'snap'
        done=subprocess.run([sys.executable,str(ROOT/'tools/vxace_map_shops.py'),str(self.index),'--project',str(self.game),'--map','1','--event','2','--output',str(out)],capture_output=True,text=True)
        self.assertEqual(done.returncode,0,done.stderr);report=json.loads((out/'map-shop-snapshot.json').read_text())
        self.assertEqual((report['event_shape'],report['append_supported'],report['mutation_authorized']),('dialogue',True,False))
        done=subprocess.run([sys.executable,str(ROOT/'tools/vxace_map_shops.py'),str(self.index),'--project',str(self.game),'--map','1','--event','9','--output',str(self.base/'snap2')],capture_output=True,text=True)
        self.assertEqual(done.returncode,2);self.assertFalse((self.base/'snap2').exists())

    def test_snapshot_marks_nonconforming_event_unsupported(self):
        root=clone(self.root);self.page(root,1).set('trigger',3);self.path.write_bytes(marshal_rb.dump(root))
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.base/'index2')],check=True,capture_output=True)
        snap=shops.indexed_snapshot(Index(self.base/'index2'),self.game,1,1)
        self.assertFalse(snap['append_supported']);self.assertIsNone(snap['event_shape']);self.assertTrue(snap['unsupported_reason'])
        self.path.write_bytes(marshal_rb.dump(self.root))

    def test_snapshot_refuses_when_indexed_evidence_disagrees(self):
        for relative in ('maps/map-001.json','database/weapons.json'):
            path=self.index/relative;raw=path.read_bytes();value=json.loads(raw)
            if relative.startswith('maps'):value['width']=99
            else:value[1]['name']='Forged'
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):shops.indexed_snapshot(Index(self.index),self.game,1,1)
            path.write_bytes(raw)

    # ---- candidate construction
    def test_blank_event_gets_302_then_605_rows_with_native_parameters(self):
        candidate=clone(self.root);mutation=self.make(purchase_only=True);shops.apply(candidate,self.native(mutation),self.arrays)
        rows=[(c.get('code'),c.get('indent'),c.get('parameters')) for c in self.page(candidate,1).get('list')]
        self.assertEqual(rows,[(302,0,[1,1,0,0,True]),(605,0,[2,2,1,250]),(605,0,[0,3,1,0]),(0,0,[])])
        shops.verify_transition(self.root,candidate,self.native(mutation),self.arrays)
        self.page(candidate,1).set('list',[self.page(self.root,1).get('list')[0]])
        self.assertEqual(marshal_rb.dump(candidate),marshal_rb.dump(self.root))

    def test_dialogue_event_inserts_before_terminator_after_text_and_keeps_prefix(self):
        candidate=clone(self.root);mutation=self.make(event_id=2,goods=[{'type':'item','id':1,'price':None}])
        shops.apply(candidate,self.native(mutation,2),self.arrays);shops.verify_transition(self.root,candidate,self.native(mutation,2),self.arrays)
        self.assertEqual(self.codes(candidate,2),[101,401,401,302,0])
        self.assertEqual(self.page(candidate,2).get('list')[3].get('parameters'),[0,1,0,0,False])
        old=self.page(self.root,2).get('list')
        self.assertEqual(marshal_rb.dump(self.page(candidate,2).get('list')[:3]),marshal_rb.dump(old[:3]))
        self.assertEqual(marshal_rb.dump(self.page(candidate,2).get('list')[-1]),marshal_rb.dump(old[-1]))
        self.assertEqual(self.codes(candidate,1),[0])

    def test_maximum_goods_and_every_goods_type_and_price_boundary_are_accepted(self):
        for goods in ([{'type':'item','id':1,'price':9999999}],[{'type':'weapon','id':2,'price':0}],
                      [{'type':kind,'id':i,'price':None} for kind,n in (('item',3),('weapon',2),('armor',2)) for i in range(1,n+1)]):
            candidate=clone(self.root);shops.apply(candidate,self.native(self.make(goods=goods)),self.arrays)
            self.assertEqual(len(self.page(candidate,1).get('list')),len(goods)+1)

    # ---- goods validation
    def test_goods_bounds_types_duplicates_and_counts_refuse(self):
        bad=[[],[{'type':'item','id':1,'price':None}]*2,
             [{'type':'item','id':i%3+1,'price':None} for i in range(33)],
             [{'type':'gem','id':1,'price':None}],[{'type':'item','id':0,'price':None}],[{'type':'item','id':1000,'price':None}],
             [{'type':'item','id':True,'price':None}],[{'type':'item','id':1.0,'price':None}],[{'type':'item','id':'1','price':None}],
             [{'type':'item','id':1,'price':-1}],[{'type':'item','id':1,'price':10000000}],[{'type':'item','id':1,'price':True}],
             [{'type':'item','id':1,'price':1.5}],[{'type':'item','id':1,'price':'5'}],
             [{'type':'item','id':1}],[{'type':'item','id':1,'price':None,'extra':1}],['item'],None,
             [{'type':'item','id':4,'price':None}],[{'type':'weapon','id':3,'price':None}],[{'type':'armor','id':3,'price':None}]]
        for goods in bad:
            with self.subTest(goods=str(goods)[:60]):
                mutation=self.make();mutation['goods']=goods
                self.refuses(clone(self.root),mutation)
        for goods in ([{'type':'weapon','id':1,'price':None},{'type':'weapon','id':1,'price':5}],):
            self.refuses(clone(self.root),self.make(goods=goods))

    def test_purchase_only_must_be_boolean_and_schema_is_exact(self):
        for value in (1,0,None,'true'):self.refuses(clone(self.root),self.make(purchase_only=value))
        extra=self.make();extra['extra']=1;self.refuses(clone(self.root),extra)
        missing=self.make();missing.pop('expected_items_sha256');self.refuses(clone(self.root),missing)
        wrong=self.make(action='append_shop');self.refuses(clone(self.root),wrong)
        for event_id in (True,0,1000,'1',9):
            with self.assertRaises(ValueError):shops.apply(clone(self.root),self.native(self.make(),event_id),self.arrays)

    def test_nil_or_misnumbered_goods_entries_refuse(self):
        for kind in ('item','weapon','armor'):
            for damage in ('nil','id','class','alias'):
                arrays={key:clone(value) for key,value in self.arrays.items()}
                array=arrays[kind]
                if damage=='nil':array[1]=None
                elif damage=='id':array[1].set('id',2)
                elif damage=='class':array[1]=RubyObject('RPG::Skill',dict(array[1].ivars))
                else:array[2]=array[1]
                with self.subTest(kind=kind,damage=damage):
                    self.refuses(clone(self.root),self.make(arrays=arrays,goods=[{'type':kind,'id':1,'price':None}]),arrays=arrays)
        short={**self.arrays,'item':[None]}
        self.refuses(clone(self.root),self.make(arrays=self.arrays),arrays=short)

    # ---- stale guards and shape
    def test_every_stale_hash_refuses_and_leaves_root_untouched(self):
        for field in ('expected_map_sha256','expected_event_sha256','expected_list_sha256','expected_items_sha256','expected_weapons_sha256','expected_armors_sha256'):
            with self.subTest(field=field):self.refuses(clone(self.root),self.make(**{field:'0'*64}))
        for bad in ('A'*64,'0'*63,'g'*64,None,5):self.refuses(clone(self.root),self.make(expected_map_sha256=bad))
        changed=clone(self.arrays['weapon']);changed[1].set('name',text('Forged'))
        self.refuses(clone(self.root),self.make(),arrays={**self.arrays,'weapon':changed})

    def test_wrong_event_shapes_refuse(self):
        def mutate(name):
            root=clone(self.root);page=self.page(root,1);notice=self.page(root,2)
            if name=='two_pages':
                shops.locate(root,1).get('pages').append(clone(page))
            elif name=='condition':page.get('condition').set('switch1_valid',True)
            elif name=='touch_trigger':page.set('trigger',2)
            elif name=='autorun':page.set('trigger',3)
            elif name=='moving':page.set('move_type',1)
            elif name=='graphic':page.get('graphic').set('character_name',text('Actor1'))
            elif name=='logic':page.set('list',[command(121,[1,1,0]),command(0,[])])
            elif name=='existing_shop':page.set('list',[command(302,[0,1,0,0,False]),command(0,[])])
            elif name=='empty_list':page.set('list',[])
            elif name=='no_terminator':page.set('list',[command(101,[text(''),0,0,2])])
            elif name=='dialogue_after_logic':notice.set('list',notice.get('list')[:-1]+[command(121,[1,1,0]),command(0,[])])
            elif name=='five_lines':notice.set('list',[command(101,[text(''),0,0,2])]+[command(401,[text('x')]) for _ in range(5)]+[command(0,[])])
            elif name=='face_header':notice.set('list',[command(101,[text('Actor1'),0,0,2]),command(401,[text('x')]),command(0,[])])
            elif name=='bottom_position':notice.set('list',[command(101,[text(''),0,0,0]),command(401,[text('x')]),command(0,[])])
            elif name=='second_block':notice.set('list',notice.get('list')[:-1]+[command(101,[text(''),0,0,2]),command(401,[text('y')]),command(0,[])])
            elif name=='escape_code':notice.set('list',[command(101,[text(''),0,0,2]),command(401,[text('\\C[2]x')]),command(0,[])])
            elif name=='indented_text':notice.set('list',[command(101,[text(''),0,0,2]),command(401,[text('x')],1),command(0,[])])
            elif name=='only_header':notice.set('list',[command(101,[text(''),0,0,2]),command(0,[])])
            elif name=='blank_text':notice.set('list',[command(101,[text(''),0,0,2]),command(401,[text('')]),command(0,[])])
            return root
        for name,event_id in (('two_pages',1),('condition',1),('touch_trigger',1),('autorun',1),('moving',1),('graphic',1),('logic',1),('existing_shop',1),
                              ('empty_list',1),('no_terminator',1),('dialogue_after_logic',2),('five_lines',2),('face_header',2),('bottom_position',2),
                              ('second_block',2),('escape_code',2),('indented_text',2),('only_header',2),('blank_text',2)):
            with self.subTest(name=name):
                root=mutate(name);self.refuses(root,self.make(root=root,event_id=event_id),event_id)

    def test_event_shape_helper_names_blank_and_dialogue(self):
        self.assertEqual(shops.event_shape(self.root,1)[1:],('blank',[]))
        self.assertEqual(shops.event_shape(self.root,2)[1:],('dialogue',['Welcome!','Take a look.']))
        with self.assertRaises(ValueError):shops.event_shape(self.root,5)

    def test_unknown_list_alias_is_detached_and_preserved(self):
        root=clone(self.root);root.set('unknown_alias',self.page(root,1).get('list'))
        mutation=self.make(root=root);candidate=clone(root);before=shops.digest(candidate.get('unknown_alias'))
        shops.apply(candidate,self.native(mutation),self.arrays);shops.verify_transition(root,candidate,self.native(mutation),self.arrays)
        self.assertEqual(shops.digest(candidate.get('unknown_alias')),before);self.assertIsNot(candidate.get('unknown_alias'),self.page(candidate,1).get('list'))

    # ---- tampering
    def test_candidate_verifier_refuses_every_unapproved_change(self):
        mutation=self.native(self.make())
        def good():
            candidate=clone(self.root);shops.apply(candidate,mutation,self.arrays);return candidate
        shops.verify_transition(self.root,good(),mutation,self.arrays)
        def other_map_field(c):c.set('disable_dashing',True)
        def other_event(c):shops.locate(c,2).set('name',text('Forged'))
        def other_event_list(c):self.page(c,2).get('list')[1].get('parameters')[0]=text('Changed')
        def inserted_param(c):self.page(c,1).get('list')[0].get('parameters')[1]=2
        def inserted_price(c):self.page(c,1).get('list')[1].get('parameters')[3]=1
        def purchase_flag(c):self.page(c,1).get('list')[0].get('parameters')[4]=True
        def dropped_row(c):self.page(c,1).get('list').pop(1)
        def extra_row(c):self.page(c,1).get('list').insert(-1,command(605,[0,1,0,0]))
        def extra_command(c):self.page(c,1).get('list').insert(0,command(123,[text('A'),0]))
        def terminator(c):self.page(c,1).get('list')[-1].set('parameters',[1])
        def page_flag(c):self.page(c,1).set('through',True)
        def height(c):c.set('note','x')
        def append_event(c):c.set('events',type(c.get('events'))([*c.get('events').pairs,(3,clone(shops.locate(c,1)))],default=None))
        for tamper in (other_map_field,other_event,other_event_list,inserted_param,inserted_price,purchase_flag,dropped_row,extra_row,extra_command,terminator,page_flag,height,append_event):
            candidate=good();tamper(candidate)
            with self.subTest(tamper=tamper.__name__),self.assertRaises(ValueError):shops.verify_transition(self.root,candidate,mutation,self.arrays)
        with self.assertRaises(ValueError):shops.verify_transition(self.root,clone(self.root),mutation,self.arrays)

    def test_backend_mutator_requires_actual_native_context(self):
        mutation=self.native(self.make());spec={'type':'map_shop','mutation':mutation}
        candidate=clone(self.root);backend_apply(candidate,spec,source_path=self.path);self.assertEqual(self.codes(candidate,1),[302,605,605,0])
        for path in (None,self.game/'Data/Map1.rvdata2',self.game/'Data/MapInfos.rvdata2'):
            with self.assertRaises((ValueError,OSError)):backend_apply(clone(self.root),spec,source_path=path)
        other=clone(self.root);other.set('disable_dashing',True)
        with self.assertRaises(ValueError):backend_apply(other,spec,source_path=self.path)
        self.assertEqual(self.codes(self.root,1),[0])

    def test_final_context_detects_changed_goods_arrays(self):
        mutation=self.make();shops.final_context(mutation,self.game)
        arrays=shops.goods_arrays(self.path);weapons=clone(arrays['weapon']);weapons[2].set('name',text('Forged'))
        (self.game/'Data/Weapons.rvdata2').write_bytes(marshal_rb.dump(weapons))
        with self.assertRaises(ValueError):shops.final_context(mutation,self.game)

    # ---- spec, planner, impact, patcher
    def test_locator_and_mutation_normalisation_is_exact(self):
        _,value=self.spec();change=value['changes'][0]
        patcher.normalize_changes(self.index,value)
        for loc in ({'map_id':1},{'map_id':True,'event_id':1},{'map_id':1,'event_id':True},{'map_id':1,'event_id':1,'page':1},{'map_id':1,'event_id':0},{'map_id':0,'event_id':1},{'map_id':1000,'event_id':1}):
            with self.assertRaises(ValueError):patcher.normalize_changes(self.index,{'changes':[{**change,'locator':loc}]})
        for mutation in ({**change['mutation'],'event_id':1},{**change['mutation'],'extra':1},{k:v for k,v in change['mutation'].items() if k!='goods'},{**change['mutation'],'purchase_only':'no'}):
            with self.assertRaises(ValueError):patcher.normalize_changes(self.index,{'changes':[{**change,'mutation':mutation}]})

    def test_copy_chain_changes_only_map_and_reload_version_for_both_shapes(self):
        for event_id,codes in ((1,[302,605,605,0]),(2,[101,401,401,302,605,605,0])):
            with self.subTest(event_id=event_id):
                for name in ('copy','audit'):shutil.rmtree(self.base/name,ignore_errors=True)
                before=patcher.current_inventory(self.game);result=self.build(event_id,purchase_only=event_id==2)
                after=patcher.current_inventory(self.base/'copy')
                self.assertEqual(result['status'],'ok');self.assertEqual(patcher.current_inventory(self.game),before)
                self.assertEqual(set(after),set(before));self.assertEqual({key for key in before if before[key]!=after[key]},{'Data/Map001.rvdata2','Data/System.rvdata2'})
                final,_=load(self.base/'copy/Data/Map001.rvdata2');self.assertEqual(self.codes(final,event_id),codes)
                self.assertIs(self.page(final,event_id).get('list')[codes.index(302)].get('parameters')[4],event_id==2)
                system,_=load(self.base/'copy/Data/System.rvdata2');original,_=load(self.game/'Data/System.rvdata2')
                self.assertEqual(system.get('version_id'),original.get('version_id')+1)
                record=next(row for row in result['changes'] if row['kind']=='map_shop')
                self.assertTrue(record['shop']['only_approved_event_list_changed']);self.assertEqual(len(record['shop']['inserted_rows']),3)
                self.assertEqual(record['shop']['event_shape'],'blank' if event_id==1 else 'dialogue')
                for file in ('structural-impact.json','post-map-audit.json','semantic-diff.json','post-validation/validation.json'):self.assertTrue((self.base/'audit'/file).is_file())
                impact=json.loads((self.base/'audit/structural-impact.json').read_text())['impacts'][0]
                self.assertEqual((impact['kind'],impact['severity']),('map_shop','high'));self.assertEqual([g['name'] for g in impact['goods']],['Sword','Helm','Elixir'])
                self.assertEqual([g['effective_price'] for g in impact['goods']],[10,250,0])

    def test_planner_and_impact_cli_and_stale_guards(self):
        spec,value=self.spec()
        plan=[sys.executable,str(ROOT/'tools/vxace_patch_planner.py'),str(self.index),'--project',str(self.game),'--spec',str(spec),'--output']
        self.assertEqual(subprocess.run(plan+[str(self.base/'plan')],capture_output=True).returncode,0)
        planned=json.loads((self.base/'plan/plan.json').read_text())['changes'][0]
        self.assertEqual((planned['kind'],planned['event_shape'],len(planned['goods'])),('map_shop',"blank",3))
        self.assertIn('shop',' '.join(json.loads((self.base/'plan/plan.json').read_text())['regression_checks']).lower())
        done=subprocess.run([sys.executable,str(ROOT/'tools/vxace_impact.py'),str(self.index),'--spec',str(spec),'--json',str(self.base/'impact.json')],capture_output=True,text=True)
        self.assertEqual(done.returncode,0,done.stderr)
        for field in ('expected_event_sha256','expected_armors_sha256'):
            bad=json.loads(json.dumps(value));bad['changes'][0]['mutation'][field]='0'*64;spec.write_text(json.dumps(bad))
            self.assertNotEqual(subprocess.run(plan+[str(self.base/('bad-'+field))],capture_output=True).returncode,0)
        bad=json.loads(json.dumps(value));bad['changes'][0]['locator']={'map_id':1,'event_id':1,'page':1};spec.write_text(json.dumps(bad))
        self.assertNotEqual(subprocess.run(plan+[str(self.base/'bad-locator')],capture_output=True).returncode,0)
        bad=json.loads(json.dumps(value));bad['changes'].append(bad['changes'][0]);spec.write_text(json.dumps(bad))
        self.assertNotEqual(subprocess.run(plan+[str(self.base/'bad-two')],capture_output=True).returncode,0)

    def test_python_backend_reindex_one_shop_and_no_combined_changes(self):
        spec,value=self.spec();common=[sys.executable,str(ROOT/'tools/vxace_copy_patcher.py'),str(self.index),'--project',str(self.game),'--spec',str(spec),'--copy',str(self.base/'copy'),'--audit',str(self.base/'audit')]
        for extra in (['--backend','ruby'],['--backend','python','--no-reindex']):
            self.assertNotEqual(subprocess.run(common+extra,capture_output=True).returncode,0);self.assertFalse((self.base/'copy').exists())
            shutil.rmtree(self.base/'audit',ignore_errors=True)
        def attempt(changes,expect):
            spec.write_text(json.dumps({'changes':changes}))
            done=subprocess.run(common+['--backend','python'],capture_output=True,text=True)
            self.assertNotEqual(done.returncode,0);self.assertIn(expect,done.stderr);self.assertFalse((self.base/'copy').exists())
            shutil.rmtree(self.base/'audit',ignore_errors=True)
        first=value['changes'][0]
        second_mutation=self.make(event_id=2)
        second={'kind':'map_shop','locator':{'map_id':1,'event_id':2},'proposal':'Second shop.','mutation':second_mutation}
        attempt([first,second],'one shop append per transaction')
        attempt([first,first],'one shop append per transaction')
        event_change={'kind':'map_event','locator':{'map_id':1},'proposal':'Add dialogue.','mutation':{
            'action':'append_dialogue_event','template_id':1,'new_id':3,'name':'Sign','x':1,'y':1,'text':['Hi'],
            'expected_map_sha256':'0'*64,'expected_template_sha256':'0'*64}}
        attempt([first,event_change],'cannot be combined')
        weapon={'kind':'database','locator':{'table':'weapons','id':1},'proposal':'Rename.','mutation':{'field':'name','value':'Blade'}}
        attempt([first,weapon],'cannot be combined')

    def test_final_goods_tampering_rolls_back_whole_copy(self):
        original=patcher.current_inventory;before=original(self.game);injected=False
        def altered(root):
            nonlocal injected
            if Path(root)==self.base/'copy' and (self.base/'audit/post-validation/validation.json').exists() and not injected:
                path=Path(root)/'Data/Armors.rvdata2';native,_=load(path);native[1].set('name',text('Forged'));path.write_bytes(marshal_rb.dump(native));injected=True
            return original(root)
        with patch.object(patcher,'current_inventory',side_effect=altered),self.assertRaises(RuntimeError):self.build()
        self.assertTrue(injected);self.assertFalse((self.base/'copy').exists());self.assertEqual(original(self.game),before)
        self.assertTrue(json.loads((self.base/'audit/failure.json').read_text())['staged_copy_removed'])

    def test_stale_source_map_refuses_without_creating_copy(self):
        spec,_=self.spec();root=clone(self.root);root.set('disable_dashing',True);self.path.write_bytes(marshal_rb.dump(root))
        with self.assertRaises(RuntimeError):
            patcher.build(self.index,self.game,spec,self.base/'copy',self.base/'audit',shutil.which('ruby'),ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')
        self.assertFalse((self.base/'copy').exists())


if __name__=='__main__':unittest.main()
