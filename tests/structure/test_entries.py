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
import vxace_database_entries as entries
import vxace_python_mutator as backend
import test_regions as region_fixtures
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject, RubyString


def item(identifier=1):
    values={key:0 for key in entries.ITEM_INTS}
    values.update(id=identifier,itype_id=1,scope=7,occasion=0,consumable=True,price=50,
                  success_rate=100,repeats=1,name=backend.convert('Potion'),description=backend.convert('Heal'),
                  note=backend.convert('<original fixture tag>'),features=[])
    values['effects']=[RubyObject('RPG::UsableItem::Effect',{'@code':11,'@data_id':0,'@value1':0.5,'@value2':0.0})]
    values['damage']=RubyObject('RPG::UsableItem::Damage',{'@type':0,'@element_id':0,'@formula':backend.convert('0'),
                                                        '@variance':20,'@critical':False})
    return RubyObject('RPG::Item',{'@'+key:value for key,value in values.items()})


def fixture():
    second=item(2);second.set('custom_existing_field',backend.convert('preserve'))
    return [None,item(),second]


def mutation(root):
    snap=entries.snapshot(root,1)
    return {'action':'append_key_item','template_id':1,'new_id':len(root),
            'expected_array_sha256':snap['array_sha256'],'expected_template_sha256':snap['template_sha256'],
            'name':'Village Relic','description':'Return it to the village elder.'}


class EntryUnitTests(unittest.TestCase):
    def test_append_inert_native_key_item_preserves_entire_existing_array_prefix(self):
        root=fixture(); before=marshal_rb.dump(root); spec=mutation(root)
        backend.apply(root,{'type':'database_entry','mutation':spec})
        self.assertEqual(marshal_rb.dump(root[:-1]),before)
        created=root[-1]
        self.assertEqual((created.cls,created.get('id'),created.get('itype_id')),('RPG::Item',3,2))
        self.assertEqual(created.get('name').data,b'Village Relic')
        self.assertEqual((created.get('scope'),created.get('occasion'),created.get('price'),created.get('icon_index')),(0,3,0,0))
        self.assertFalse(created.get('consumable'))
        self.assertEqual(created.get('effects'),[]);self.assertEqual(created.get('features'),[])
        self.assertEqual(created.get('note').data,b'')
        self.assertEqual(created.get('damage').get('variance'),0)
        self.assertEqual(root[1].get('effects')[0].get('value1'),0.5)
        self.assertEqual(root[2].get('custom_existing_field').data,b'preserve')

    def test_new_item_nested_objects_are_independent_of_template(self):
        root=fixture(); spec=mutation(root);entries.apply(root,spec)
        self.assertIsNot(root[1].get('damage'),root[-1].get('damage'))
        root[-1].get('damage').set('variance',99)
        self.assertEqual(root[1].get('damage').get('variance'),20)

    def test_candidate_verifier_rejects_old_entry_new_record_or_shape_tampering(self):
        before=fixture();spec=mutation(before)
        for bad in ('prefix','new_effect','new_name','extra_entry','missing'):
            after=marshal_rb.load(marshal_rb.dump(before));entries.apply(after,spec)
            entries.verify_transition(before,after,spec)
            if bad=='prefix':after[2].set('custom_existing_field',backend.convert('changed'))
            elif bad=='new_effect':after[-1].set('effects',after[1].get('effects'))
            elif bad=='new_name':after[-1].set('name',backend.convert('Different'))
            elif bad=='extra_entry':after.append(item(4))
            else:after.pop()
            with self.subTest(bad=bad),self.assertRaises(ValueError):entries.verify_transition(before,after,spec)

    def test_hashes_id_reuse_skip_unknown_actions_and_fields_refuse_without_changes(self):
        for key,value in (('expected_array_sha256','0'*64),('expected_template_sha256','0'*64),
                          ('new_id',1),('new_id',4),('new_id',True),('new_id',1000),('template_id',0),
                          ('template_id',True),('action','delete_item'),('field','price')):
            root=fixture();spec=mutation(root);spec[key]=value;before=marshal_rb.dump(root)
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):entries.apply(root,spec)
            self.assertEqual(marshal_rb.dump(root),before)

    def test_sparse_misaligned_non_native_arrays_and_identity_types_refuse(self):
        cases=[[],[None],{},[item(),item()], [None,None,item(2)], [None,item(2)],
               [None,RubyObject('RPG::Skill',{'@id':1})]]
        boolean=item();boolean.set('id',True);cases.append([None,boolean])
        for root in cases:
            with self.subTest(root=str(root)[:80]),self.assertRaises(ValueError):entries.item_array(root)

    def test_unknown_missing_or_custom_template_schema_is_not_cloned(self):
        for bad in ('extra','missing','features','damage_class','damage_field','damage_type','effect_class','effect_field','effect_value'):
            root=fixture();selected=root[1]
            if bad=='extra':selected.set('custom',True)
            elif bad=='missing':del selected.ivars['@scope']
            elif bad=='features':selected.set('features',[1])
            elif bad=='damage_class':selected.get('damage').cls='CustomDamage'
            elif bad=='damage_field':selected.get('damage').set('unknown',1)
            elif bad=='damage_type':selected.get('damage').set('type',1)
            elif bad=='effect_class':selected.get('effects')[0].cls='CustomEffect'
            elif bad=='effect_field':selected.get('effects')[0].set('extra',1)
            else:selected.get('effects')[0].set('value1',float('nan'))
            with self.subTest(bad=bad),self.assertRaises(ValueError):entries.snapshot(root,1)

    def test_text_bounds_controls_unicode_and_legacy_encoding_refusal(self):
        for key,value in (('name',''),('name','x'*101),('name','line\nname'),('name','nul\x00name'),
                          ('description','x'*1001),('description','nul\x00description')):
            root=fixture();spec=mutation(root);spec[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):entries.apply(root,spec)
        root=fixture();spec=mutation(root);spec['name']='Relic é';entries.apply(root,spec)
        self.assertEqual(root[-1].get('name').data,'Relic é'.encode('utf-8'))
        root=fixture();root[1].set('name',RubyString(b'Potion',{'E':False}));spec=mutation(root);spec['name']='Relic é'
        before=marshal_rb.dump(root)
        with self.assertRaises(ValueError):entries.apply(root,spec)
        self.assertEqual(marshal_rb.dump(root),before)

    def test_full_supported_array_snapshot_does_not_authorize_another_slot(self):
        root=[None]+[item(i) for i in range(1,1000)]
        snap=entries.snapshot(root,1)
        self.assertEqual(snap['next_item_id'],1000);self.assertFalse(snap['append_slot_supported'])
        with self.assertRaises(ValueError):entries.apply(root,mutation(root))

    def test_backend_write_and_reload_preserve_existing_records_and_new_key_item(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'items.rvdata2';candidate=Path(folder)/'new.rvdata2'
            file.write_bytes(marshal_rb.dump(fixture()));before=file.read_bytes()
            root,_=backend.load(file);spec=mutation(root);entries.apply(root,spec);backend.write(root,candidate)
            after,_=backend.load(candidate)
            self.assertEqual(marshal_rb.dump(after[:-1]),before)
            self.assertEqual(after[-1].get('id'),3)
            self.assertEqual(file.read_bytes(),before)


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent native Items fixture and extraction')
class EntryCopyTests(unittest.TestCase):
    def setUp(self):
        region_fixtures.RegionCopyTests.setUp(self)
        ruby='''module RPG
  class Item; end
  class Troop; end
  class UsableItem; class Damage; end; class Effect; end; end
end
def make_item(id)
  obj=RPG::Item.new
  values={id:id,name:"Potion",description:"Original fixture",note:"",consumable:true,
          icon_index:0,price:50,scope:7,occasion:0,animation_id:0,speed:0,success_rate:100,
          hit_type:0,itype_id:1,repeats:1,tp_gain:0,features:[]}
  effect=RPG::UsableItem::Effect.new
  {code:11,data_id:0,value1:0.5,value2:0.0}.each{|k,v|effect.instance_variable_set("@#{k}",v)}
  damage=RPG::UsableItem::Damage.new
  {type:0,element_id:0,formula:"0",variance:20,critical:false}.each{|k,v|damage.instance_variable_set("@#{k}",v)}
  values[:effects]=[effect];values[:damage]=damage
  values.each{|k,v|obj.instance_variable_set("@#{k}",v)}
  obj
end
File.binwrite(ARGV[0]+"/Data/Items.rvdata2",Marshal.dump([nil,make_item(1),make_item(2)]))
troops=Marshal.load(File.binread(ARGV[0]+"/Data/Troops.rvdata2"))
troops.compact.each{|troop|troop.instance_variable_set(:@pages,[])}
File.binwrite(ARGV[0]+"/Data/Troops.rvdata2",Marshal.dump(troops))
'''
        script=self.base/'items.rb';script.write_text(ruby,encoding='utf-8')
        subprocess.run(['ruby',str(script),str(self.game)],check=True,capture_output=True)
        self.index=self.base/'item-index'
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)
        self.items,_=backend.load(self.game/'Data/Items.rvdata2')
        self.spec={'changes':[{'kind':'database_entry','locator':{'table':'items'},'proposal':'Append one inert quest key item.',
                              'mutation':mutation(self.items)}]}
        self.specfile.write_text(json.dumps(self.spec))

    stage=region_fixtures.RegionCopyTests.stage

    def test_complete_copy_chain_preserves_prefix_system_and_emits_postgates(self):
        from vxace_copy_patcher import current_inventory
        before=current_inventory(self.game);result=self.stage()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(current_inventory(self.game),before)
        final,_=backend.load(self.base/'copy/Data/Items.rvdata2')
        entries.verify_transition(self.items,final,self.spec['changes'][0]['mutation'])
        self.assertEqual((self.base/'copy/Data/System.rvdata2').read_bytes(),(self.game/'Data/System.rvdata2').read_bytes())
        audit=json.loads((self.base/'audit/audit.json').read_text())
        self.assertEqual(len(audit['changes']),1)
        self.assertTrue(audit['changes'][0]['entry']['existing_entries_unchanged'])
        self.assertTrue((self.base/'audit/post-validation/validation.json').is_file())
        self.assertTrue((self.base/'audit/semantic-diff.json').is_file())
        impact=json.loads((self.base/'audit/structural-impact.json').read_text())
        self.assertEqual(impact['impacts'][0]['target']['new_id'],3)

    def test_entry_copy_requires_python_reindex_single_append_and_no_other_items_edit(self):
        for backend_name,extra in (('ruby',()),('python',('--no-reindex',))):
            result=self.stage(backend_name,extra)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((self.base/'copy').exists());self.assertFalse((self.base/'audit').exists())
        self.spec['changes']*=2;self.specfile.write_text(json.dumps(self.spec))
        self.assertNotEqual(self.stage().returncode,0)
        self.spec['changes']=self.spec['changes'][:1]+[{'kind':'database','locator':{'table':'items','id':1},'mutation':{'field':'price','value':1}}]
        self.specfile.write_text(json.dumps(self.spec));self.assertNotEqual(self.stage().returncode,0)
        self.assertFalse((self.base/'copy').exists())

    def test_snapshot_cli_refuses_stale_source_and_keeps_reports_external(self):
        output=self.base/'snapshot'
        args=[str(self.index),'--project',str(self.game),'--template-item','1','--output',str(output)]
        self.assertEqual(entries.main(args),0)
        result=json.loads((output/'item-entry-snapshot.json').read_text())
        self.assertEqual(result['next_item_id'],3)
        args[-1]=str(self.game/'report');self.assertEqual(entries.main(args),2)
        self.assertFalse((self.game/'report').exists())
        (self.game/'Data/new.rvdata2').write_bytes(b'new')
        args[-1]=str(self.base/'stale');self.assertEqual(entries.main(args),2)
        self.assertFalse((self.base/'stale').exists())

    def test_failed_postcopy_extraction_removes_append_copy_and_preserves_source(self):
        import vxace_copy_patcher as patcher
        before=patcher.current_inventory(self.game);original=patcher.run
        def fail_reader(command,**kwargs):
            if len(command)>1 and Path(command[1]).name=='vxace_project_reader.py':
                return subprocess.CompletedProcess(command,1,'','injected append verification failure')
            return original(command,**kwargs)
        with patch.object(patcher,'run',side_effect=fail_reader),self.assertRaisesRegex(RuntimeError,'re-index failed'):
            patcher.build(self.index,self.game,self.specfile,self.base/'copy',self.base/'audit',shutil.which('ruby'),
                          ROOT/'tools/vxace_python_mutator.py',ROOT/'tools/vxace_project_reader.py',ROOT/'tools/vxace_index_diff.py')
        self.assertFalse((self.base/'copy').exists())
        self.assertTrue(json.loads((self.base/'audit/failure.json').read_text())['staged_copy_removed'])
        self.assertEqual(patcher.current_inventory(self.game),before)


if __name__=='__main__':unittest.main()
