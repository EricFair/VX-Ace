"""Host parsing must inspect exact source bytes without evaluating the source."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_project_validator as validator


def entry(source):
    raw=source.encode('utf-8')
    return {'index':0,'name':'Byte fixture','source':source,'source_bytes':len(raw),
            'source_sha256':hashlib.sha256(raw).hexdigest(),'utf8_decodable':True}


class SyntaxByteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)

    def check(self, rows, runner):
        with patch.object(validator,'extract_scripts',return_value=rows),patch.object(validator,'run',side_effect=runner):
            return validator.syntax_check_scripts('ruby','bridge','archive',self.base/'syntax',0.5)

    def test_exact_crlf_lf_mixed_utf8_and_empty_bytes_reach_parser(self):
        for source in ('# CRLF\r\nx = 1\r\n','# LF\nx = 1\n','# 村\r\nx = "é"\n# tail\r',''):
            row=entry(source)
            def runner(command, timeout):
                self.assertEqual(timeout,0.5)
                self.assertEqual(command[:2],['ruby','-c'])
                self.assertEqual(Path(command[2]).read_bytes(),source.encode('utf-8'))
                return subprocess.CompletedProcess(command,0,'Syntax OK','')
            report=self.check([row],runner)
            self.assertEqual(report['status'],'pass')
            self.assertEqual(report['scripts'][0]['source_sha256'],row['source_sha256'])
            self.assertTrue(report['scripts'][0]['exact_source_bytes'])
            self.assertFalse(report['ruby_19_compatibility_proven'])

    def test_source_metadata_mismatch_never_reaches_parser(self):
        for key,value in (('source_bytes',999),('source_sha256','0'*64),('utf8_decodable',False)):
            row=entry('value = 1\n');row[key]=value
            report=self.check([row],lambda *args,**kwargs:self.fail('Parser must not run'))
            self.assertEqual(report['scripts'][0]['reason'],'source_integrity_failed')

    def test_invalid_source_or_index_refuses_without_parser_or_path_escape(self):
        for row in ({**entry('x=1'),'index':'../outside'}, {**entry('x=1'),'index':True},
                    {**entry('x=1'),'source':None}, {**entry('x=1'),'source':'\ud800'}):
            report=self.check([row],lambda *args,**kwargs:self.fail('Parser must not run'))
            self.assertEqual(report['failed'],1)
            self.assertFalse((self.base/'outside.rb').exists())

    def test_parser_timeout_is_failed_diagnostic_and_later_scripts_are_checked(self):
        rows=[entry('x=1'),{**entry('x=2'),'index':1}]
        calls=[]
        def runner(command,timeout):
            calls.append(command)
            if len(calls)==1:raise subprocess.TimeoutExpired(command,timeout)
            return subprocess.CompletedProcess(command,0,'Syntax OK','')
        report=self.check(rows,runner)
        self.assertEqual(report['failed'],1)
        self.assertEqual(len(calls),2)
        self.assertEqual(report['scripts'][0]['reason'],'host_parse_timeout')
        self.assertEqual(report['scripts'][1]['status'],'pass')

    def test_bridge_deadline_failure_is_extraction_diagnostic(self):
        def runner(command,timeout):
            self.assertEqual(timeout,30)
            raise subprocess.TimeoutExpired(command,timeout)
        with patch.object(validator,'run',side_effect=runner):
            report=validator.syntax_check_scripts('ruby','bridge','archive',self.base/'syntax')
        self.assertEqual(report['reason'],'script_extraction_failed')
        self.assertFalse((self.base/'syntax').exists())

    def test_invalid_timeout_is_refused_before_project_or_output_access(self):
        for timeout in (True,None,0,61,float('nan'),float('inf')):
            with self.assertRaisesRegex(ValueError,'Syntax timeout'):
                validator.validate('absent',self.base/'report',syntax_timeout=timeout)
        self.assertFalse((self.base/'report').exists())

    @unittest.skipUnless(shutil.which('ruby'),'Ruby required')
    def test_real_host_parse_does_not_execute_script_side_effect(self):
        marker=self.base/'must-not-exist.txt'
        source='File.binwrite('+repr(marker.as_posix())+', "executed")\r\nraise "must not run"\r\n'
        with patch.object(validator,'extract_scripts',return_value=[entry(source)]):
            report=validator.syntax_check_scripts(shutil.which('ruby'),'bridge','archive',self.base/'syntax')
        self.assertEqual(report['status'],'pass')
        self.assertFalse(marker.exists())


if __name__=='__main__':unittest.main()
