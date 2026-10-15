import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_script_slots as slots
import vxace_python_mutator as backend
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyString


def entry(identifier,name,source):
    return [identifier,RubyString(name.encode('utf-8'),{'E':True}),RubyString(zlib.compress(source),{'E':True})]


def fixture():
    return [entry(10,'Core',b'# authored core\r\n'),entry(20,'Main',b'# owned header\r\nrgss_main { SceneManager.run }\r\n'),entry(30,'',b'')]


def mutation(root,before=1):
    snapshot=slots.snapshot(root,before)
    return {'action':'insert_before_main','before_index':before,'new_id':snapshot['unused_id_candidate'],
            'name':'Authored New Slot','source':'# é exact\r\nmodule AuthoredSlot\r\nend\r\n',
            'expected_archive_sha256':snapshot['archive_sha256'],'expected_anchor_sha256':snapshot['anchor_sha256']}


class SlotUnitTests(unittest.TestCase):
    def test_insert_preserves_complete_old_archive_order_ids_metadata_and_bytes(self):
        root=fixture();before=marshal_rb.load(marshal_rb.dump(root));raw=marshal_rb.dump(root);spec=mutation(root)
        backend.apply(root,{'type':'script_slot','mutation':spec})
        slots.verify_transition(before,root,spec)
        self.assertEqual(marshal_rb.dump(root[:1]+root[2:]),raw)
        self.assertEqual([item[0] for item in root],[10,31,20,30])
        self.assertEqual(zlib.decompress(root[1][2].data),spec['source'].encode('utf-8'))
        self.assertEqual(root[1][1].ivars,{'E':True});self.assertEqual(root[1][2].ivars,{'E':True})

    def test_new_entry_strings_are_independent_of_all_existing_values(self):
        root=fixture();spec=mutation(root);slots.apply(root,spec)
        self.assertIsNot(root[1][1],root[2][1]);self.assertIsNot(root[1][2],root[2][2])
        root[1][1].data=b'changed';self.assertEqual(root[2][1].data,b'Main')

    def test_candidate_verifier_rejects_old_change_reorder_wrong_new_slot_or_alias(self):
        before=fixture()
        for change in ('old','order','new','alias','extra'):
            spec=mutation(before)
            if change=='alias':spec['source']=slots.inflate(before[0][2].data).decode('utf-8')
            after=marshal_rb.load(marshal_rb.dump(before));slots.apply(after,spec)
            if change=='old':after[0][1].data=b'altered'
            elif change=='order':after[0],after[-1]=after[-1],after[0]
            elif change=='new':after[1][0]=99
            elif change=='alias':after[1][2]=after[0][2]
            else:after.append(entry(99,'Extra',b'# extra'))
            with self.assertRaises(ValueError):slots.verify_transition(before,after,spec)

    def test_customized_missing_duplicate_main_or_unsupported_anchor_metadata_refuse(self):
        for change in ('custom','missing','duplicate','encoding'):
            root=fixture()
            if change=='custom':root[1][2].data=zlib.compress(b'puts "custom"\nrgss_main { SceneManager.run }\n')
            elif change=='missing':root[1][1].data=b'Other'
            elif change=='duplicate':root[0][1].data=b'Main'
            else:root[1][2].ivars={}
            with self.assertRaises(ValueError):slots.snapshot(root,1)

    def test_stale_hash_duplicate_id_unknown_action_and_locator_override_refuse_immutably(self):
        for field,value in (('expected_archive_sha256','0'*64),('expected_anchor_sha256','0'*64),('new_id',10),('action','delete'),('before_index',True),('unexpected',1)):
            root=fixture();before=marshal_rb.dump(root);spec={**mutation(root),field:value}
            with self.assertRaises(ValueError):slots.apply(root,spec)
            self.assertEqual(marshal_rb.dump(root),before)

    def test_unknown_archive_fields_ids_string_metadata_and_legacy_names_refuse(self):
        for change in ('fields','duplicate_id','boolean_id','metadata','legacy_name'):
            root=fixture()
            if change=='fields':root[0].append('unknown')
            elif change=='duplicate_id':root[0][0]=20
            elif change=='boolean_id':root[0][0]=True
            elif change=='metadata':root[0][2].ivars['custom']=1
            else:root[0][1].data=b'\xff'
            with self.assertRaises((ValueError,UnicodeError)):slots.snapshot(root,1)

    def test_corrupt_trailing_and_oversized_source_or_entry_capacity_refuse(self):
        for bad in (b'bad',zlib.compress(b'# valid')+b'trailing',zlib.compress(b'\xff')):
            root=fixture();root[0][2].data=bad
            with self.assertRaises((ValueError,UnicodeError)):slots.snapshot(root,1)
        root=fixture();spec=mutation(root)
        with patch.object(slots,'MAX_ENTRIES',len(root)),self.assertRaises(ValueError):slots.new_slot(root,spec)
        with patch.object(slots,'MAX_SOURCE_BYTES',1),self.assertRaises(ValueError):slots.snapshot(root,1)

    def test_new_name_source_and_id_limits_refuse_without_mutation(self):
        values=(('name','Main'),('name',' bad '),('name','bad\nname'),('name','x'*81),('new_id',0),('new_id',2**31),
                ('source',''),('source','\0'),('source','\ud800'),('source','x'*(slots.MAX_NEW_SOURCE_BYTES+1)))
        for field,value in values:
            root=fixture();before=marshal_rb.dump(root);spec={**mutation(root),field:value}
            with self.assertRaises((ValueError,UnicodeError)):slots.apply(root,spec)
            self.assertEqual(marshal_rb.dump(root),before)


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent archive fixtures')
class SlotCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.game=self.base/'game';self.index=self.base/'index';self.specfile=self.base/'spec.json'
        subprocess.run(['ruby',str(ROOT/'tests/project_reader/make_fixture.rb'),str(self.game)],check=True,capture_output=True)
        ruby=self.base/'main.rb';ruby.write_text("require 'zlib'\np=ARGV[0]+'/Data/Scripts.rvdata2'\ns=Marshal.load(File.binread(p))\ns << [104,'Main',Zlib::Deflate.deflate(\"# owned header\\r\\nrgss_main { SceneManager.run }\\r\\n\").force_encoding('UTF-8')]\nFile.binwrite(p,Marshal.dump(s))\n",encoding='utf-8')
        subprocess.run(['ruby',str(ruby),str(self.game)],check=True,capture_output=True)
        subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.game),'--output',str(self.index)],check=True,capture_output=True)
        self.before,_=backend.load(self.game/'Data/Scripts.rvdata2')
        full=mutation(self.before,3);full.pop('before_index')
        self.spec={'changes':[{'kind':'script_slot','locator':{'before_index':3},'proposal':'Insert one authored script before Main.','mutation':full}]}
        self.specfile.write_text(json.dumps(self.spec),encoding='utf-8')

    def full_mutation(self):return {'before_index':3,**self.spec['changes'][0]['mutation']}

    def stage(self,backend_name='python',extra=()):
        return subprocess.run([sys.executable,str(ROOT/'tools/vxace_copy_patcher.py'),str(self.index),'--project',str(self.game),
                               '--spec',str(self.specfile),'--copy',str(self.base/'copy'),'--audit',str(self.base/'audit'),
                               '--backend',backend_name,*extra],capture_output=True,text=True)

    def test_complete_copy_chain_preserves_existing_archive_system_and_postgates(self):
        from vxace_copy_patcher import current_inventory
        before=current_inventory(self.game);result=self.stage();self.assertEqual(result.returncode,0,result.stderr)
        final,_=backend.load(self.base/'copy/Data/Scripts.rvdata2');slots.verify_transition(self.before,final,self.full_mutation())
        self.assertEqual(current_inventory(self.game),before)
        self.assertEqual((self.base/'copy/Data/System.rvdata2').read_bytes(),(self.game/'Data/System.rvdata2').read_bytes())
        audit=json.loads((self.base/'audit/audit.json').read_text())
        self.assertEqual(len(audit['changes']),1);self.assertTrue(audit['changes'][0]['script_slot']['existing_entries_order_and_bytes_unchanged'])
        for name in ('post-validation/validation.json','structural-impact.json','semantic-diff.json'):
            self.assertTrue((self.base/'audit'/name).is_file())
        verify=subprocess.run(['ruby','-rzlib','-rjson','-e','s=Marshal.load(File.binread(ARGV[0])); puts JSON.generate(s.map{|x| [x[0],x[1],Zlib::Inflate.inflate(x[2])]})',str(self.base/'copy/Data/Scripts.rvdata2')],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(verify.returncode,0,verify.stderr)
        entries=json.loads(verify.stdout);self.assertEqual(entries[3][2],self.full_mutation()['source'])

    def test_python_reindex_single_slot_and_no_other_scripts_mutation_are_mandatory(self):
        for backend_name,extra in (('ruby',()),('python',('--no-reindex',))):
            result=self.stage(backend_name,extra);self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())
        original=json.loads(json.dumps(self.spec))
        for other in (original['changes'][0],{'kind':'script','script_path':'000_Core Battle.rb','search':'class','replace':'class'}):
            self.spec['changes']=original['changes']+[other];self.specfile.write_text(json.dumps(self.spec))
            result=self.stage();self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())

    def test_source_index_tamper_stale_native_hash_and_locator_override_refuse_before_copy(self):
        original=json.loads(json.dumps(self.spec))
        for update in ({'expected_archive_sha256':'0'*64},{'before_index':0}):
            self.spec=json.loads(json.dumps(original));self.spec['changes'][0]['mutation'].update(update)
            self.specfile.write_text(json.dumps(self.spec));result=self.stage()
            self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())
        self.specfile.write_text(json.dumps(original))
        order=json.loads((self.index/'scripts/order.json').read_text());path=self.index/'scripts'/order['scripts'][0]['path']
        path.write_bytes(path.read_bytes()+b'# altered index\n');result=self.stage()
        self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())

    def test_new_source_impact_reports_collisions_dependencies_and_never_executes_it(self):
        marker=self.base/'must-not-execute'
        source='class Game_Battler\n  def item_apply(user, item)\n  end\nend\n$imported["MissingDependency"]\nFile.write('+json.dumps(marker.as_posix())+', "bad")\n'
        self.spec['changes'][0]['mutation']['source']=source;self.specfile.write_text(json.dumps(self.spec))
        result=self.stage();self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(marker.exists())
        impact=json.loads((self.base/'audit/structural-impact.json').read_text())['impacts'][0]
        self.assertEqual(impact['severity'],'high')
        self.assertGreater(impact['ordered_compatibility_evidence']['method_collisions']['total'],0)
        self.assertGreater(impact['ordered_compatibility_evidence']['dependency_findings']['total'],0)

    def test_planner_and_snapshot_cli_produce_external_review_evidence(self):
        planned=subprocess.run([sys.executable,str(ROOT/'tools/vxace_patch_planner.py'),str(self.index),'--project',str(self.game),'--spec',str(self.specfile),'--output',str(self.base/'plan')],capture_output=True,text=True)
        self.assertEqual(planned.returncode,0,planned.stderr)
        plan=json.loads((self.base/'plan/plan.json').read_text())['changes'][0]
        self.assertEqual(plan['apply_mode'],'proposal_only');self.assertIn('+module AuthoredSlot',plan['diff'])
        self.assertEqual(plan['source_sha256'],slots.hashlib.sha256(self.full_mutation()['source'].encode('utf-8')).hexdigest())
        snapped=subprocess.run([sys.executable,str(ROOT/'tools/vxace_script_slots.py'),str(self.index),'--project',str(self.game/'Game.rvproj2'),'--before-index','3','--output',str(self.base/'snapshot')],capture_output=True,text=True)
        self.assertEqual(snapped.returncode,0,snapped.stderr)
        report=json.loads((self.base/'snapshot/script-slot-snapshot.json').read_text());self.assertFalse(report['mutation_authorized'])
        self.assertEqual(report['anchor_id'],104)

    def test_failed_post_reindex_removes_entire_copy_and_keeps_failure_audit(self):
        failing=self.base/'reader.py';failing.write_text('raise SystemExit(8)\n')
        result=self.stage(extra=('--reader',str(failing)))
        self.assertNotEqual(result.returncode,0);self.assertFalse((self.base/'copy').exists())
        failure=json.loads((self.base/'audit/failure.json').read_text());self.assertTrue(failure['staged_copy_removed'])


if __name__=='__main__':unittest.main()
