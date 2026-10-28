from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import vxace_text_export as te


def cmd(code,p=None,indent=0):
    return {'__class__':'RPG::EventCommand','code':code,'indent':indent,'parameters':p or []}


class Codes(unittest.TestCase):
    def test_strip_all_known_codes(self):
        text='\\C[2]Hi\\C[0] \\I[5]\\V[1]\\N[2]\\P[1]\\G\\{\\}\\$\\.\\|\\!\\>\\<\\^ end'
        visible,refs,problems=te.strip_codes(text)
        self.assertEqual(visible,'Hi  end');self.assertEqual(problems,[])
        self.assertEqual(refs,[('C',2),('C',0),('I',5),('V',1),('N',2),('P',1)])

    def test_escaped_backslash_is_visible_and_lowercase_accepted(self):
        self.assertEqual(te.strip_codes('a\\\\b')[0],'a\\b')
        self.assertEqual(te.strip_codes('\\c[3]x\\g')[0],'x')

    def test_unknown_and_malformed(self):
        _,_,problems=te.strip_codes('\\Z \\V \\C[x] tail\\')
        self.assertEqual([p[0] for p in problems],['unknown_control_code','malformed_control_code','malformed_control_code','malformed_control_code'])

    def test_width_counts_after_stripping_and_wide_chars(self):
        self.assertEqual(te.visible_width(te.strip_codes('\\C[2]abc\\C[0]')[0]),3)
        self.assertEqual(te.visible_width('あいa'),5)
        self.assertEqual(te.word_count('\\C[2]one two\\C[0] three'),3)

    def test_fingerprint_stable_and_sensitive(self):
        a=[cmd(101,['Actor1',0,0,2]),cmd(401,['Hello'])]
        self.assertEqual(te.fingerprint(a),te.fingerprint([dict(c) for c in a]))
        self.assertEqual(len(te.fingerprint(a)),64)
        b=[cmd(101,['Actor1',0,0,2]),cmd(401,['Hello '])]
        self.assertNotEqual(te.fingerprint(a),te.fingerprint(b))
        self.assertNotEqual(te.fingerprint(a),te.fingerprint(a[:1]))


if __name__=='__main__': unittest.main()
