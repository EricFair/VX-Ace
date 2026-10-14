import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MUT=ROOT/'tools'/'rvdata2_mutator.rb'
PATCH=ROOT/'tools'/'vxace_copy_patcher.py'
DIFF=ROOT/'tools'/'vxace_index_diff.py'
FIX=ROOT/'tests'/'project_reader'/'make_fixture.rb'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*args):
    command = list(map(str, args))
    if command[0] == 'python3':
        command[0] = sys.executable
    return subprocess.run(command, capture_output=True, text=True)
def inspect(path):
    p=run('ruby',MUT,'inspect',path); assert p.returncode==0,p.stderr; return json.loads(p.stdout)
def find_class(node,name):
    if isinstance(node,dict):
        if node.get('__class__')==name: return node
        for v in node.values():
            r=find_class(v,name)
            if r: return r
    elif isinstance(node,list):
        for v in node:
            r=find_class(v,name)
            if r: return r
    return None
def script_source(path,index=0):
    code="require 'zlib'; x=Marshal.load(File.binread(ARGV[0])); STDOUT.write(Zlib::Inflate.inflate(x[ARGV[1].to_i][2]))"
    p=run('ruby','-e',code,path,str(index)); assert p.returncode==0,p.stderr; return p.stdout

class MutationV08Tests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.base=Path(self.t.name); self.project=self.base/'Project'
        p=run('ruby',FIX,self.project); self.assertEqual(p.returncode,0,p.stderr)
        self.index=self.base/'index'; (self.index/'scripts').mkdir(parents=True)
        files=[]
        for pth in sorted(self.project.rglob('*')):
            if pth.is_file(): files.append({'path':pth.relative_to(self.project).as_posix(),'size':pth.stat().st_size,'sha256':sha(pth)})
        (self.index/'manifest.json').write_text(json.dumps({'read_only':True,'files':files}),encoding='utf-8')
        names=['Core Battle','Alias Extension','Destructive Extension']
        order=[]
        for i,name in enumerate(names):
            rel=f'{i:03d}_{name.replace(" ","_")}.rb'; (self.index/'scripts'/rel).write_text(script_source(self.project/'Data'/'Scripts.rvdata2',i),encoding='utf-8'); order.append({'index':i,'path':rel,'name':name})
        (self.index/'scripts'/'order.json').write_text(json.dumps({'scripts':order}),encoding='utf-8')
        self.before={p.relative_to(self.project).as_posix():sha(p) for p in self.project.rglob('*') if p.is_file()}
    def tearDown(self): self.t.cleanup()

    def test_fixture_data_roundtrips_byte_identically(self):
        for src in (self.project/'Data').glob('*.rvdata2'):
            out=self.base/('rt-'+src.name); p=run('ruby',MUT,'roundtrip',src,out); self.assertEqual(p.returncode,0,p.stderr); self.assertEqual(sha(src),sha(out),src.name); self.assertEqual(inspect(src)['semantic_sha256'],inspect(out)['semantic_sha256'])

    def test_copy_patch_applies_script_database_event_without_touching_source(self):
        spec={'title':'fixture patch','changes':[
          {'kind':'script','script_path':'000_Core_Battle.rb','search':'  def item_apply(user, item)\n  end','replace':'  def item_apply(user, item)\n    @patched = true\n  end'},
          {'kind':'database','locator':{'table':'actors','id':1},'mutation':{'field':'name','value':'Alicia Prime'}},
          {'kind':'event','locator':{'map_id':1,'event_id':1,'page':1,'command_index':0},'mutation':{'action':'set_parameter','parameter_index':2,'value':1}}]}
        sp=self.base/'spec.json'; sp.write_text(json.dumps(spec)); copy=self.base/'Patched'; audit=self.base/'audit'
        p=run('python3',PATCH,self.index,'--project',self.project,'--spec',sp,'--copy',copy,'--audit',audit,'--no-reindex'); self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(self.before,{x.relative_to(self.project).as_posix():sha(x) for x in self.project.rglob('*') if x.is_file()})
        actor=find_class(inspect(copy/'Data'/'Actors.rvdata2')['data'],'RPG::Actor'); self.assertEqual(actor['name']['__string__'],'Alicia Prime')
        cmd=find_class(inspect(copy/'Data'/'Map001.rvdata2')['data'],'RPG::EventCommand'); self.assertEqual(cmd['parameters']['__array__'][2],1)
        self.assertIn('@patched = true',script_source(copy/'Data'/'Scripts.rvdata2',0))
        a=json.loads((audit/'audit.json').read_text()); self.assertEqual(a['source_integrity_after']['status'],'unchanged'); self.assertTrue(all(x['binary_identical'] for x in a['roundtrip_preflight']))

    def test_stale_index_refused_before_copy(self):
        (self.project/'Game.rvproj2').write_text('changed')
        sp=self.base/'spec.json'; sp.write_text(json.dumps({'changes':[{'kind':'database','locator':{'table':'actors','id':1},'mutation':{'field':'name','value':'X'}}]}))
        copy=self.base/'Patched'; p=run('python3',PATCH,self.index,'--project',self.project,'--spec',sp,'--copy',copy,'--audit',self.base/'audit','--no-reindex'); self.assertEqual(p.returncode,3); self.assertFalse(copy.exists()); self.assertIn('stale_index',p.stderr)

    def test_copy_inside_source_refused(self):
        sp=self.base/'spec.json'; sp.write_text(json.dumps({'changes':[{'kind':'database','locator':{'table':'actors','id':1},'mutation':{'field':'name','value':'X'}}]}))
        p=run('python3',PATCH,self.index,'--project',self.project,'--spec',sp,'--copy',self.project/'Patched','--audit',self.base/'audit','--no-reindex'); self.assertEqual(p.returncode,2); self.assertIn('may not be inside source',p.stderr)

    def test_audit_inside_source_refused(self):
        sp=self.base/'spec.json'; sp.write_text(json.dumps({'changes':[{'kind':'database','locator':{'table':'actors','id':1},'mutation':{'field':'name','value':'X'}}]}))
        p=run('python3',PATCH,self.index,'--project',self.project,'--spec',sp,'--copy',self.base/'Patched','--audit',self.project/'audit','--no-reindex'); self.assertEqual(p.returncode,2); self.assertIn('audit destination may not be inside source',p.stderr)

    def test_database_cannot_create_unknown_field(self):
        sp=self.base/'spec.json'; sp.write_text(json.dumps({'changes':[{'kind':'database','locator':{'table':'actors','id':1},'mutation':{'field':'new_unknown_field','value':1}}]}))
        p=run('python3',PATCH,self.index,'--project',self.project,'--spec',sp,'--copy',self.base/'Patched','--audit',self.base/'audit','--no-reindex'); self.assertEqual(p.returncode,3); self.assertIn('does not already exist',p.stderr); self.assertFalse((self.base/'Patched').exists())

    def test_index_diff(self):
        a=self.base/'a'; b=self.base/'b'; (a/'database').mkdir(parents=True); (b/'database').mkdir(parents=True); (a/'scripts').mkdir(); (b/'scripts').mkdir(); (a/'database'/'actors.json').write_text('A'); (b/'database'/'actors.json').write_text('B'); (a/'scripts'/'x.rb').write_text('same'); (b/'scripts'/'x.rb').write_text('same')
        p=run('python3',DIFF,a,b); self.assertEqual(p.returncode,0,p.stderr); r=json.loads(p.stdout); self.assertEqual(r['changed'],['database/actors.json']); self.assertEqual(r['unchanged_count'],1)

if __name__=='__main__': unittest.main()
