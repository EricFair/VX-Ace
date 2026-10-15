import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from vxace_patch_planner import script_diff


@unittest.skipUnless(shutil.which('ruby'),'Ruby required for independent compressed-script fixtures')
class ScriptByteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.project=self.base/'game';self.index=self.base/'index'
        subprocess.run(['ruby',str(ROOT/'tests/project_reader/make_fixture.rb'),str(self.project)],check=True,capture_output=True)

    def archive(self, raw, compressed=False):
        source=self.base/'source.bin';source.write_bytes(raw)
        script=self.base/'scripts.rb'
        script.write_text("require 'zlib'\nraw=File.binread(ARGV[1])\n"+
                          ("compressed=raw\n" if compressed else "compressed=Zlib::Deflate.deflate(raw)\n")+
                          "File.binwrite(ARGV[0]+'/Data/Scripts.rvdata2',Marshal.dump([[1,'Byte Fixture',compressed]]))\n",encoding='utf-8')
        subprocess.run(['ruby',str(script),str(self.project),str(source)],check=True,capture_output=True)

    def read(self):
        return subprocess.run([sys.executable,str(ROOT/'tools/vxace_project_reader.py'),str(self.project),
                               '--output',str(self.index)],capture_output=True,text=True)

    def test_crlf_lf_mixed_and_utf8_source_bytes_are_exact(self):
        sources=[b'# comment\r\nvalue = 1\r\n',b'# comment\nvalue = 1\n',
                 '# é\r\nvalue = "村の遺物"\n# tail\r'.encode('utf-8')]
        for number,raw in enumerate(sources):
            with self.subTest(number=number):
                self.index=self.base/('index-'+str(number));self.archive(raw)
                before=(self.project/'Data/Scripts.rvdata2').read_bytes()
                result=self.read();self.assertEqual(result.returncode,0,result.stderr)
                order=json.loads((self.index/'scripts/order.json').read_text())['scripts'][0]
                exported=(self.index/'scripts'/order['path']).read_bytes()
                self.assertEqual(exported,raw)
                self.assertEqual(order['source_sha256'],hashlib.sha256(raw).hexdigest())
                self.assertEqual(order['source_bytes'],len(raw))
                self.assertTrue(order['utf8_decodable'])
                self.assertEqual(order['newlines']['crlf'],raw.count(b'\r\n'))
                self.assertEqual((self.project/'Data/Scripts.rvdata2').read_bytes(),before)

    def test_multiline_crlf_planner_requires_exact_bytes_and_preserves_diff(self):
        raw=b'# anchor first\r\n# anchor second\r\nvalue = 1\r\n';self.archive(raw)
        self.assertEqual(self.read().returncode,0)
        path=json.loads((self.index/'scripts/order.json').read_text())['scripts'][0]['path']
        change={'script_path':path,'search':'# anchor first\r\n# anchor second','replace':'# changed\r\n# still exact'}
        result=script_diff(self.index,change)
        self.assertIn('# changed',result['diff'])
        with self.assertRaises(ValueError):script_diff(self.index,{**change,'search':'# anchor first\n# anchor second'})
        spec=self.base/'patch.json';spec.write_text(json.dumps({'changes':[{'kind':'script',**change}]}))
        result=subprocess.run([sys.executable,str(ROOT/'tools/vxace_copy_patcher.py'),str(self.index),'--project',str(self.project),
                               '--spec',str(spec),'--copy',str(self.base/'copy'),'--audit',str(self.base/'audit'),'--backend','python'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        import zlib
        sys.path.insert(0,str(ROOT/'tools'))
        from vxace_python_mutator import load
        archive,_=load(self.base/'copy/Data/Scripts.rvdata2')
        self.assertEqual(zlib.decompress(archive[0][2].data),raw.replace(change['search'].encode(),change['replace'].encode()))

    def test_bad_deflate_or_trailing_streams_make_reader_partial_not_fake_source(self):
        import zlib
        for number,compressed in enumerate((b'not zlib',zlib.compress(b'# code\n')+b'trailing',zlib.compress(b'# code\n')[:-2])):
            self.index=self.base/('invalid-'+str(number));self.archive(compressed,compressed=True)
            result=self.read();self.assertNotEqual(result.returncode,0)
            summary=json.loads((self.index/'project.json').read_text())
            self.assertTrue(any(row['file']=='Scripts.rvdata2' for row in summary['errors']))
            self.assertEqual(list((self.index/'scripts').glob('*.rb')),[])

    def test_non_utf8_source_refuses_lossy_transcoding_and_copy_admission(self):
        self.archive(b'# legacy\nvalue = "\x82\xa0"\n')
        result=self.read();self.assertNotEqual(result.returncode,0)
        summary=json.loads((self.index/'project.json').read_text())
        self.assertIn('code-page review',summary['errors'][0]['error'])
        self.assertEqual(list((self.index/'scripts').glob('*.rb')),[])
        spec=self.base/'spec.json';spec.write_text(json.dumps({'changes':[{'kind':'database','locator':{'table':'actors','id':1},
                                                                       'mutation':{'field':'name','value':'Changed'}}]}))
        result=subprocess.run([sys.executable,str(ROOT/'tools/vxace_copy_patcher.py'),str(self.index),'--project',str(self.project),
                               '--spec',str(spec),'--copy',str(self.base/'copy'),'--audit',str(self.base/'audit'),'--backend','python'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.base/'copy').exists());self.assertFalse((self.base/'audit').exists())

    def test_inflation_source_budget_refuses_without_placeholder(self):
        import zlib
        self.archive(zlib.compress(b'#'+b'x'*(16*1024*1024)),compressed=True)
        result=self.read();self.assertNotEqual(result.returncode,0)
        self.assertEqual(list((self.index/'scripts').glob('*.rb')),[])


if __name__=='__main__':unittest.main()
