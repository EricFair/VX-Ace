#!/usr/bin/env python3
"""Read-only validation harness for real RPG Maker VX Ace projects.

Validates .rvdata2 byte-identical round-trip safety using rvdata2_mutator.rb and
optionally checks extracted RGSS3 script syntax with the selected host Ruby.
Never writes into the source project.
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
VERSION = "0.9.0"

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def find_ruby(explicit):
    candidate=explicit or shutil.which('ruby')
    if not candidate: raise RuntimeError('Ruby executable not found; pass --ruby PATH')
    resolved=Path(candidate).expanduser().resolve()
    if not resolved.is_file(): raise RuntimeError(f'Ruby executable not found: {resolved}')
    return str(resolved)

def project_root(path):
    p=Path(path).expanduser().resolve()
    if p.is_file() and p.suffix.lower()=='.rvproj2': p=p.parent
    if not p.is_dir() or not (p/'Data').is_dir(): raise ValueError(f'Not a VX Ace project (missing Data/): {p}')
    return p

def ensure_external_output(project, output):
    output=output.expanduser().resolve()
    if output==project or project in output.parents: raise ValueError('Validation output must be outside the source project')
    return output

def run(cmd): return subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=False)
def parse_json_stdout(proc):
    if proc.returncode: raise RuntimeError((proc.stderr or proc.stdout or 'tool failed').strip())
    try: return json.loads(proc.stdout or '{}')
    except json.JSONDecodeError as e: raise RuntimeError(f'Tool returned invalid JSON: {e}') from e

def roundtrip_file(ruby, mutator, source, temp_dir):
    temp_dir.mkdir(parents=True,exist_ok=True); candidate=temp_dir/source.name
    proc=run([ruby,str(mutator),'roundtrip',str(source),str(candidate)])
    if proc.returncode:
        return {'path':source.name,'status':'failed','reason':'roundtrip_tool_error','stderr':(proc.stderr or proc.stdout).strip(),'source_sha256':sha256(source)}
    if not candidate.is_file(): return {'path':source.name,'status':'failed','reason':'roundtrip_output_missing','source_sha256':sha256(source)}
    src_hash,out_hash=sha256(source),sha256(candidate)
    return {'path':source.name,'status':'pass' if src_hash==out_hash else 'failed','reason':'byte_identical' if src_hash==out_hash else 'byte_mismatch','source_sha256':src_hash,'roundtrip_sha256':out_hash,'byte_identical':src_hash==out_hash,'size':source.stat().st_size}

def extract_scripts(ruby,bridge,scripts_file):
    payload=parse_json_stdout(run([ruby,str(bridge),'scripts',str(scripts_file)])); scripts=payload.get('scripts')
    if not isinstance(scripts,list): raise RuntimeError('Bridge response has no scripts array')
    return scripts

def syntax_check_scripts(ruby,bridge,scripts_file,temp_dir):
    try: scripts=extract_scripts(ruby,bridge,scripts_file)
    except Exception as e: return {'status':'failed','reason':'script_extraction_failed','error':str(e),'scripts':[]}
    temp_dir.mkdir(parents=True,exist_ok=True); results=[]; failures=0
    for item in scripts:
        index=item.get('index'); name=str(item.get('name') or ''); source=str(item.get('source') or '')
        if item.get('invalid_entry'):
            failures+=1; results.append({'index':index,'name':name,'status':'failed','reason':'invalid_archive_entry'}); continue
        script_path=temp_dir/f'script-{int(index):04d}.rb'; script_path.write_text(source,encoding='utf-8')
        proc=run([ruby,'-c',str(script_path)]); ok=proc.returncode==0
        failures += 0 if ok else 1
        results.append({'index':index,'name':name,'status':'pass' if ok else 'failed','stdout':proc.stdout.strip(),'stderr':proc.stderr.strip()})
    return {'status':'pass' if failures==0 else 'failed','checked':len(results),'failed':failures,'host_ruby_parse_only':True,'ruby_19_compatibility_proven':False,'scripts':results}

def render_markdown(report):
    lines=['# VX Ace Project Validation Report','',f"Validator version: `{report['validator_version']}`",'','## Verdict','',f"- Copy-mutation readiness: **{'PASS' if report['copy_mutation_ready'] else 'REFUSED'}**",f"- `.rvdata2` files checked: **{report['roundtrip']['checked']}**",f"- Byte-identical round-trip failures: **{report['roundtrip']['failed']}**"]
    syntax=report.get('script_syntax')
    if syntax:
        lines += [f"- Host-Ruby script syntax check: **{syntax['status'].upper()}**",f"- Scripts checked: **{syntax.get('checked',0)}**",'', '> Host-Ruby parsing is a diagnostic only. It does not prove RGSS3/Ruby 1.9.2 runtime compatibility.']
    lines += ['','## Round-trip files','']
    for item in report['roundtrip']['files']:
        lines.append(f"- **{'PASS' if item['status']=='pass' else 'FAIL'}** `{item['path']}` — {item.get('reason','')}")
    if syntax:
        failed=[x for x in syntax.get('scripts',[]) if x.get('status')!='pass']
        if failed:
            lines += ['','## Script syntax findings','']
            for item in failed:
                lines.append(f"- Script {item.get('index')} `{item.get('name','')}` — {item.get('stderr') or item.get('reason') or 'parse failed'}")
    lines += ['','## Safety interpretation','', 'A project is copy-mutation-ready only when every discovered `.rvdata2` file round-trips byte-for-byte identically with the current mutator. This report never modifies the source project.','']
    return '\n'.join(lines)

def validate(project_arg,output_arg,ruby_arg=None,mutator_arg=None,bridge_arg=None,skip_script_syntax=False):
    project=project_root(project_arg); output=ensure_external_output(project,Path(output_arg)); ruby=find_ruby(ruby_arg); tools=Path(__file__).resolve().parent
    mutator=Path(mutator_arg).expanduser().resolve() if mutator_arg else tools/'rvdata2_mutator.rb'; bridge=Path(bridge_arg).expanduser().resolve() if bridge_arg else tools/'rvdata2_bridge.rb'
    if not mutator.is_file(): raise RuntimeError(f'Mutator not found: {mutator}')
    if not skip_script_syntax and not bridge.is_file(): raise RuntimeError(f'Bridge not found: {bridge}')
    files=sorted((project/'Data').glob('*.rvdata2'),key=lambda p:p.name.lower())
    if not files: raise RuntimeError('No .rvdata2 files found in Data/')
    with tempfile.TemporaryDirectory(prefix='vxace-validate-') as td:
        temp=Path(td); file_results=[roundtrip_file(ruby,mutator,source,temp/'roundtrip') for source in files]; failures=[x for x in file_results if x['status']!='pass']; script_syntax=None; scripts_file=project/'Data'/'Scripts.rvdata2'
        if not skip_script_syntax and scripts_file.is_file(): script_syntax=syntax_check_scripts(ruby,bridge,scripts_file,temp/'syntax')
    report={'validator_version':VERSION,'source_path_omitted':True,'source_project_modified':False,'copy_mutation_ready':len(failures)==0,'roundtrip':{'checked':len(file_results),'failed':len(failures),'files':file_results},'script_syntax':script_syntax,'limitations':['Host-Ruby syntax validation is not proof of RGSS3/Ruby 1.9.2 runtime behavior.','Byte-identical round-trip success applies only to files checked by this validator version.','Real VX Ace runtime playtesting remains mandatory after any staged copy mutation.']}
    output.mkdir(parents=True,exist_ok=True); (output/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); (output/'validation.md').write_text(render_markdown(report),encoding='utf-8'); return report

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('project'); ap.add_argument('--output',required=True); ap.add_argument('--ruby'); ap.add_argument('--mutator'); ap.add_argument('--bridge'); ap.add_argument('--skip-script-syntax',action='store_true'); args=ap.parse_args(argv)
    try: report=validate(args.project,args.output,args.ruby,args.mutator,args.bridge,args.skip_script_syntax)
    except Exception as e: print(f'error: {e}',file=sys.stderr); return 2
    print(json.dumps({'status':'ready' if report['copy_mutation_ready'] else 'refused','checked':report['roundtrip']['checked'],'failed':report['roundtrip']['failed'],'output':str(Path(args.output).expanduser().resolve())}))
    return 0 if report['copy_mutation_ready'] else 3
if __name__=='__main__': raise SystemExit(main())
