"""Public authored fixtures only; actual RGSS3 evidence remains private."""
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
import vxace_native_syntax as native


def source_row(source,index=0):
    raw=source.encode('utf-8')
    return {'index':index,'name':'Authored fixture','source_sha256':native.digest(raw),'source_bytes':len(raw),'hex':raw.hex()}


def result_bytes(manifest,status='pass'):
    lines=['\t'.join(['VXACE_NATIVE_SYNTAX','1',manifest['token'],'1.9.2','true'])]
    for row in manifest['scripts']:
        error='syntax rejected'.encode().hex() if status!='pass' else ''
        lines.append('\t'.join(map(str,[row['index'],row['source_sha256'],row['source_bytes'],status,error])))
    lines.append('COMPLETE\t'+str(len(manifest['scripts'])))
    return ('\n'.join(lines)+'\n').encode('ascii')


class NativeProtocolTests(unittest.TestCase):
    def setUp(self):
        row=source_row('# é\r\nvalue = 1\n')
        self.rows=[row];self.manifest={'token':'a'*32,'scripts':[{k:v for k,v in row.items() if k!='hex'}]}

    def test_complete_pass_keeps_hash_bytes_and_no_runtime_claim(self):
        rows=native.parse_result(result_bytes(self.manifest),self.manifest)
        self.assertEqual(rows[0]['source_sha256'],self.rows[0]['source_sha256'])
        self.assertEqual(rows[0]['status'],'pass')

    def test_syntax_and_compiler_errors_remain_distinct(self):
        for status in ('syntax_error','compiler_error'):
            rows=native.parse_result(result_bytes(self.manifest,status),self.manifest)
            self.assertEqual(rows[0]['status'],status)
            self.assertEqual(rows[0]['diagnostic'],'syntax rejected')

    def test_wrong_runtime_token_and_missing_compiler_refuse(self):
        raw=result_bytes(self.manifest)
        for changed in (raw.replace(b'1.9.2',b'3.2.11'),raw.replace(b'a'*32,b'b'*32),raw.replace(b'true',b'false')):
            with self.assertRaises(ValueError):native.parse_result(changed,self.manifest)

    def test_truncated_duplicate_extra_and_wrong_footer_refuse(self):
        raw=result_bytes(self.manifest)
        for changed in (raw.split(b'COMPLETE')[0],raw+raw,raw+b'EXTRA\n',raw.replace(b'COMPLETE\t1',b'COMPLETE\t2')):
            with self.assertRaises(ValueError):native.parse_result(changed,self.manifest)

    def test_source_hash_size_order_or_unrecognized_status_refuse(self):
        raw=result_bytes(self.manifest)
        for changed in (raw.replace(self.rows[0]['source_sha256'].encode(),b'0'*64),raw.replace(b'\n0\t',b'\n1\t'),
                        raw.replace(('\t'+str(self.rows[0]['source_bytes'])+'\t').encode(),b'\t999\t'),raw.replace(b'\tpass\t',b'\tunknown\t')):
            with self.assertRaises(ValueError):native.parse_result(changed,self.manifest)

    def test_unbounded_or_nonhex_error_and_nonascii_report_refuse(self):
        raw=result_bytes(self.manifest,'syntax_error')
        error=b'syntax rejected'.hex().encode()
        for changed in (raw.replace(error,b'0'*4098),raw.replace(error,b'zz'),raw.replace(error,b'0'),raw+b'\xff'):
            with self.assertRaises(ValueError):native.parse_result(changed,self.manifest)

    def test_source_and_name_metacharacters_are_data_in_generated_harness(self):
        source='END { File.write("must-not-run", "bad") }\n# "\\\n__VXACE_TOKEN__\n'
        rows=[{**source_row(source),'name':'"; raise "name executed'}]
        raw=native.render_harness('b'*32,rows)
        self.assertIn(source.encode().hex().encode(),raw)
        self.assertNotIn(b'raise "name executed',raw)
        self.assertNotIn(b'File.write("must-not-run"',raw)

    def test_unsafe_literal_inputs_and_budgets_refuse_before_harness(self):
        for token in ('../outside',None,'0'*31):
            with self.assertRaises(ValueError):native.render_harness(token,self.rows)
        for changed in ({**self.rows[0],'hex':'"; exit; "'},{**self.rows[0],'index':True},
                        {**self.rows[0],'source_bytes':native.MAX_SOURCE_BYTES+1}):
            with self.assertRaises(ValueError):native.render_harness('b'*32,[changed])
        with patch.object(native,'MAX_TOTAL_BYTES',1),self.assertRaises(ValueError):
            native.render_harness('b'*32,self.rows)

    @unittest.skipUnless(shutil.which('ruby'),'Ruby required')
    def test_actual_compile_does_not_evaluate_begin_end_or_regular_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            source='BEGIN { File.write("begin-marker", "bad") }\nEND { File.write("end-marker", "bad") }\nFile.write("regular-marker", "bad")\nraise "must not execute"\n'
            rows=[source_row(source),source_row('class Broken\n',1)]
            harness=base/'harness.rb';harness.write_bytes(native.render_harness('c'*32,rows))
            proc=subprocess.run([shutil.which('ruby'),str(harness)],cwd=base,capture_output=True,text=True,timeout=30)
            self.assertEqual(proc.returncode,0,proc.stderr)
            for name in ('begin-marker','end-marker','regular-marker'):self.assertFalse((base/name).exists())
            result=(base/('vxace-native-syntax-'+'c'*32+'.tsv')).read_bytes()
            # A host run is useful for scaffold regression only, never accepted as native proof.
            self.assertIn(b'\tpass\t',result);self.assertIn(b'\tsyntax_error\t',result)
            with self.assertRaises(ValueError):native.parse_result(result,{'token':'c'*32,'scripts':[{k:v for k,v in row.items() if k!='hex'} for row in rows]})
            repeat=subprocess.run([shutil.which('ruby'),str(harness)],cwd=base,capture_output=True,timeout=30)
            self.assertNotEqual(repeat.returncode,0)
            self.assertEqual((base/('vxace-native-syntax-'+'c'*32+'.tsv')).read_bytes(),result)


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent archives')
class NativeBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.project=self.base/'game';self.index=self.base/'index';self.bundle=self.base/'bundle'
        subprocess.run(['ruby',str(ROOT/'tests/project_reader/make_fixture.rb'),str(self.project)],check=True,capture_output=True)
        proc=subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.project),'--output',str(self.index)],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)

    def prepare(self):return native.prepare(self.index,self.project,self.bundle)

    def write_result(self,manifest,status='pass'):
        path=self.base/'native-host'/manifest['result_filename'];path.parent.mkdir(exist_ok=True)
        path.write_bytes(result_bytes(manifest,status));return path

    def test_independent_archive_bundle_and_collection_are_source_immutable(self):
        before=native.inventory(self.project);manifest=self.prepare()
        result=self.write_result(manifest)
        report=native.collect(self.index,self.project,self.bundle,result,self.base/'collected')
        self.assertEqual(report['checked'],3);self.assertEqual(report['failed'],0)
        self.assertFalse(report['runtime_compatibility_proven']);self.assertFalse(report['engine_launch_observed_by_tool'])
        self.assertEqual(native.inventory(self.project),before)
        self.assertTrue((self.bundle/'PRIVATE_README.txt').exists())

    def test_failed_native_result_is_collected_without_enabling_mutations(self):
        manifest=self.prepare();result=self.write_result(manifest,'syntax_error')
        report=native.collect(self.index,self.project,self.bundle,result,self.base/'collected')
        self.assertEqual(report['failed'],3);self.assertEqual(report['status'],'failed')
        self.assertFalse(report['mutation_authorized'])

    def test_stale_source_and_partial_index_refuse_before_output(self):
        (self.project/'new.txt').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.bundle.exists())
        (self.project/'new.txt').unlink()
        summary=json.loads((self.index/'project.json').read_text());summary['errors']=[{'file':'Scripts.rvdata2'}]
        (self.index/'project.json').write_text(json.dumps(summary))
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.bundle.exists())

    def test_tampered_index_source_and_matching_fake_metadata_still_refuse_native_mismatch(self):
        order=json.loads((self.index/'scripts/order.json').read_text())
        row=order['scripts'][0];raw=b'# tampered source\n'
        (self.index/'scripts'/row['path']).write_bytes(raw)
        row.update(source_sha256=native.digest(raw),source_bytes=len(raw))
        (self.index/'scripts/order.json').write_text(json.dumps(order))
        with self.assertRaisesRegex(ValueError,'integrity mismatch'):self.prepare()
        self.assertFalse(self.bundle.exists())

    def test_harness_manifest_and_result_tampering_refuse_collection_output(self):
        manifest=self.prepare();result=self.write_result(manifest);output=self.base/'collected'
        harness=self.bundle/'native-syntax-harness.rb';original=harness.read_bytes();harness.write_bytes(original+b'\nraise "tampered"')
        with self.assertRaises(ValueError):native.collect(self.index,self.project,self.bundle,result,output)
        self.assertFalse(output.exists());harness.write_bytes(original)
        result.write_bytes(result.read_bytes()+b'EXTRA\n')
        with self.assertRaises(ValueError):native.collect(self.index,self.project,self.bundle,result,output)
        self.assertFalse(output.exists())

    def test_nested_and_existing_output_paths_are_refused(self):
        for output in (self.project/'bundle',self.index/'bundle',self.base):
            with self.assertRaises(ValueError):native.prepare(self.index,self.project,output)
        self.assertFalse((self.project/'bundle').exists());self.assertFalse((self.index/'bundle').exists())

    def test_source_change_during_preparation_refuses_output(self):
        original=native.render_harness
        def changed(*args):
            harness=original(*args);(self.project/'changed.txt').write_bytes(b'change');return harness
        with patch.object(native,'render_harness',side_effect=changed),self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.bundle.exists())

    def test_native_source_budget_refuses_before_any_bundle_files(self):
        with patch.object(native,'MAX_SOURCE_BYTES',1),self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.bundle.exists())
        order_path=self.index/'scripts/order.json';order=json.loads(order_path.read_text())
        order['scripts'][0]['name']='x'*513;order_path.write_text(json.dumps(order))
        with self.assertRaisesRegex(ValueError,'labels exceed'):self.prepare()
        self.assertFalse(self.bundle.exists())


if __name__=='__main__':unittest.main()
