#!/usr/bin/env python3
"""Stage a disposable VX Ace copy with a smoke-test harness slot, launch it and report nonce-bound results."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
from vxace_copy_patcher import current_inventory
from vxace_index_query import unlinked

VERSION='1.8.0'
ROOT=Path(__file__).resolve().parent
RUNTIME=ROOT/'smoke'/'vxa_smoke_runtime.rb'
SLOT_NAME='VXA Smoke Harness'
MAX_SLOT_BYTES=256*1024
MAX_RESULT_BYTES=4*1024*1024
STAGE_FILE='smoke-stage.json'
RECORD_TYPES=('PASS','FAIL','ERROR','INFO')
NONCE_PATTERN=re.compile('[a-f0-9]{32}')
STEP_TIMEOUT=900


def sha256(raw):return hashlib.sha256(raw).hexdigest()


def file_sha256(path):return sha256(Path(path).read_bytes())


def project_root(project):
    project=unlinked(project)
    if project.is_file() and project.suffix.lower()=='.rvproj2':project=project.parent
    if not (project/'Data'/'Scripts.rvdata2').is_file():raise ValueError('Expected a VX Ace project with Data/Scripts.rvdata2')
    return project


def inside(path,parent):return path==parent or parent in path.parents


def slot_source(suite):
    runtime=RUNTIME.read_bytes().decode('utf-8','strict');suite_bytes=b''
    if suite is not None:
        suite=unlinked(suite)
        if not suite.is_file():raise ValueError('Suite must be a regular file')
        with suite.open('rb') as stream:suite_bytes=stream.read(MAX_SLOT_BYTES+1)
        suite_bytes.decode('utf-8','strict')
    source=runtime+('\r\n' if suite_bytes else '')+suite_bytes.decode('utf-8','strict')
    raw=source.encode('utf-8')
    if len(raw)>MAX_SLOT_BYTES or b'\0' in raw:raise ValueError('Harness plus suite must be <=256 KiB UTF-8 without NUL')
    return source,raw,sha256(suite_bytes) if suite is not None else None


def step(work,name,args):
    logs=work/'logs';logs.mkdir(exist_ok=True)
    try:
        proc=subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=STEP_TIMEOUT)
    except subprocess.TimeoutExpired:raise ValueError('Staging step timed out: '+name)
    (logs/(name+'.stdout.log')).write_text(proc.stdout,encoding='utf-8');(logs/(name+'.stderr.log')).write_text(proc.stderr,encoding='utf-8')
    if proc.returncode!=0:
        tail=(proc.stderr.strip() or proc.stdout.strip()).splitlines()[-1:] or ['no output']
        raise ValueError('Staging step '+name+' failed (exit '+str(proc.returncode)+'): '+tail[0])


def stage(project,work,suite=None,ruby=None):
    project=project_root(project);work=unlinked(work)
    if work.exists() or inside(work,project) or inside(project,work):
        raise ValueError('Use a new work directory outside the original project')
    ruby=ruby or shutil.which('ruby')
    if not ruby:raise ValueError('Ruby is required for extraction and staging')
    source,raw,suite_hash=slot_source(suite);before=current_inventory(project)
    work.mkdir(parents=True);tools=ROOT
    step(work,'validation',[tools/'vxace_project_validator.py',project,'--output',work/'validation','--ruby',ruby,'--backend','python'])
    step(work,'index',[tools/'vxace_project_reader.py',project,'--output',work/'index','--ruby',ruby])
    order=json.loads((work/'index/scripts/order.json').read_text(encoding='utf-8')).get('scripts')
    mains=[row['index'] for row in order if isinstance(row,dict) and row.get('name')=='Main']
    if len(mains)!=1:raise ValueError('Expected exactly one Main script to anchor the harness')
    if any(row.get('name')==SLOT_NAME for row in order):raise ValueError('Project already has a '+SLOT_NAME+' script')
    step(work,'snapshot',[tools/'vxace_script_slots.py',work/'index','--project',project,'--before-index',mains[0],'--output',work/'snapshot'])
    snapshot=json.loads((work/'snapshot/script-slot-snapshot.json').read_text(encoding='utf-8'))
    spec={'title':'Insert VXA smoke harness before Main','changes':[{'kind':'script_slot','locator':{'before_index':snapshot['before_index']},
          'proposal':'Insert the reviewed smoke-test harness before canonical Main in a disposable copy.',
          'mutation':{'action':'insert_before_main','new_id':snapshot['unused_id_candidate'],'name':SLOT_NAME,'source':source,
                      'expected_archive_sha256':snapshot['archive_sha256'],'expected_anchor_sha256':snapshot['anchor_sha256']}}]}
    (work/'spec.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
    step(work,'plan',[tools/'vxace_patch_planner.py',work/'index','--project',project,'--spec',work/'spec.json','--output',work/'plan'])
    step(work,'impact',[tools/'vxace_impact.py',work/'index','--spec',work/'spec.json','--json',work/'impact.json','--markdown',work/'impact.md'])
    step(work,'copy',[tools/'vxace_copy_patcher.py',work/'index','--project',project,'--spec',work/'spec.json','--copy',work/'copy','--audit',work/'audit','--backend','python','--ruby',ruby])
    if current_inventory(project)!=before:raise ValueError('Original project changed during staging')
    from vxace_python_mutator import load
    root,_=load(work/'copy/Data/Scripts.rvdata2')
    names=[entry[1].data.decode('utf-8','replace') for entry in root]
    slot=[n for n,name in enumerate(names) if name==SLOT_NAME]
    if len(slot)!=1 or names[slot[0]+1:slot[0]+2]!=['Main']:raise ValueError('Harness slot is not immediately before Main in the copy')
    import zlib
    if zlib.decompress(root[slot[0]][2].data)!=raw:raise ValueError('Staged harness source differs from approved source')
    record={'version':VERSION,'project':str(project),'copy':str(work/'copy'),'slot_name':SLOT_NAME,'slot_index':slot[0],
            'script_names':names,'scripts_sha256':file_sha256(work/'copy/Data/Scripts.rvdata2'),'slot_source_sha256':sha256(raw),
            'suite_sha256':suite_hash,'mutation_authorized':False,'runtime_compatibility_proven':False}
    (work/STAGE_FILE).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return record


def load_stage(work):
    work=unlinked(work);path=work/STAGE_FILE
    if not path.is_file():raise ValueError('Not a staged smoke work directory (missing '+STAGE_FILE+')')
    record=json.loads(path.read_text(encoding='utf-8'))
    need=('version','project','copy','scripts_sha256','slot_source_sha256','script_names','slot_index')
    if not isinstance(record,dict) or any(key not in record for key in need):raise ValueError('Stage record is incomplete')
    copy=unlinked(record['copy'])
    if copy!=unlinked(work/'copy') or not copy.is_dir():raise ValueError('Staged copy is missing or not the expected work/copy')
    scripts=copy/'Data/Scripts.rvdata2'
    if not scripts.is_file() or file_sha256(scripts)!=record['scripts_sha256']:
        raise ValueError('Staged Scripts.rvdata2 changed since staging; stage again')
    return work,record,copy,scripts


def new_output(path,*forbidden):
    path=unlinked(path)
    if path.exists() or any(inside(path,item) for item in forbidden):
        raise ValueError('Use a new output path outside the original project and staged copy')
    if not path.parent.is_dir():raise ValueError('Output parent directory must exist')
    return path


def parse_results(raw,nonce,complete=True):
    problems=[];records=[];header=None;footer=None
    if len(raw)>MAX_RESULT_BYTES:return {'problems':['results file exceeds 4 MiB'],'header':None,'footer':None,'records':[]}
    try:text=raw.decode('utf-8','strict')
    except UnicodeError:return {'problems':['results file is not valid UTF-8'],'header':None,'footer':None,'records':[]}
    lines=text.split('\n')
    if lines and lines[-1]=='':lines.pop()
    elif lines and lines[-1]!='':problems.append('results file does not end with a newline')
    for number,line in enumerate(lines,1):
        parts=line.split('\t')
        if header is None:
            if len(parts)!=5 or parts[0]!='VXA_SMOKE':problems.append('missing or malformed header');break
            if parts[1]!=nonce:problems.append('header nonce does not match this run');break
            if parts[3] not in ('true','false') or parts[4] not in ('true','false') or not parts[2]:
                problems.append('malformed header fields');break
            header={'ruby_version':parts[2],'test':parts[3]=='true','btest':parts[4]=='true'};continue
        if footer is not None:problems.append('records after footer (line '+str(number)+')');break
        if parts[0]=='END':
            if len(parts)!=3 or parts[1]!=nonce or not parts[2].isdigit():problems.append('malformed or mismatched footer');break
            footer={'count':int(parts[2])};continue
        if parts[0]=='VXA_SMOKE':problems.append('duplicate header (line '+str(number)+')');break
        if parts[0] not in RECORD_TYPES or len(parts)!=3 or not parts[1]:
            problems.append('unknown or malformed record on line '+str(number));break
        records.append({'type':parts[0],'name':parts[1],'detail':parts[2]})
    if header is None and not problems:problems.append('results file is empty or has no header')
    if complete and header is not None and not problems:
        if footer is None:problems.append('missing footer (run did not finish)')
        elif footer['count']!=len(records):problems.append('footer record count '+str(footer['count'])+' does not match '+str(len(records))+' records')
        elif not records:problems.append('results contain no records')
    return {'problems':problems,'header':header,'footer':footer,'records':records}


def script_refs(records,names):
    refs=[]
    for record in records:
        for match in re.finditer(r'\{(\d{4})\}',record['detail']):
            number=int(match.group(1))
            refs.append({'record':record['name'],'id':match.group(1),'script':names[number] if number<len(names) else None})
    return refs


def kill_tree(proc):
    try:
        if sys.platform=='win32':subprocess.run(['taskkill','/F','/T','/PID',str(proc.pid)],capture_output=True,timeout=30)
        else:os.killpg(proc.pid,9)
    except Exception:pass
    try:proc.kill()
    except Exception:pass
    try:proc.wait(timeout=30)
    except Exception:pass


def run(work,mode,start,frames,auto_confirm,timeout,json_out,markdown_out,launcher=None):
    if mode not in ('test','normal'):raise ValueError('--mode must be test or normal')
    if start!='new' and not re.fullmatch('save:(?:[1-9]|1[0-6])',start):raise ValueError('--start must be new or save:1..save:16')
    if type(frames) is not int or not 1<=frames<=1000000:raise ValueError('--frames must be 1..1000000')
    if type(auto_confirm) is not int or not 0<=auto_confirm<=1000000:raise ValueError('--auto-confirm must be 0..1000000')
    if not 0<timeout<=3600:raise ValueError('--timeout must be >0 and <=3600 seconds')
    work,stage_record,copy,scripts=load_stage(work);project=unlinked(stage_record['project'])
    json_out=new_output(json_out,project,copy);markdown_out=new_output(markdown_out,project,copy)
    if json_out==markdown_out:raise ValueError('JSON and Markdown outputs must differ')
    if launcher is None:
        if sys.platform!='win32':raise ValueError('Launching Game.exe is Windows-only')
        game=copy/'Game.exe'
        if not game.is_file():raise ValueError('Staged copy has no Game.exe')
        argv=[str(game)]
    else:
        if not isinstance(launcher,list) or not launcher or not all(isinstance(item,str) for item in launcher):raise ValueError('Launcher must be a JSON argv list')
        argv=list(launcher)
    if mode=='test':argv.append('test')
    nonce=secrets.token_hex(16);out_name='vxa_smoke_'+nonce+'.txt';result_path=copy/out_name
    if result_path.exists():raise ValueError('Results file already exists')
    env={key:value for key,value in os.environ.items() if not key.startswith('VXA_SMOKE_')}
    env.update({'VXA_SMOKE_NONCE':nonce,'VXA_SMOKE_OUT':out_name,'VXA_SMOKE_START':start,'VXA_SMOKE_FRAMES':str(frames),'VXA_SMOKE_AUTO_CONFIRM':str(auto_confirm)})
    options={'cwd':str(copy),'env':env,'stdin':subprocess.DEVNULL,'stdout':subprocess.DEVNULL,'stderr':subprocess.DEVNULL}
    if sys.platform!='win32':options['start_new_session']=True
    started=time.monotonic();timed_out=False
    try:proc=subprocess.Popen(argv,**options)
    except OSError as error:raise ValueError('Could not launch the staged game: '+str(error))
    try:proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out=True;kill_tree(proc)
    duration=round(time.monotonic()-started,3)
    problems=[];parsed={'problems':[],'header':None,'footer':None,'records':[]}
    if not result_path.is_file():problems.append('results file was not written')
    else:
        with result_path.open('rb') as stream:raw=stream.read(MAX_RESULT_BYTES+1)
        parsed=parse_results(raw,nonce,complete=not timed_out);problems=list(parsed['problems'])
        if mode=='test' and parsed['header'] and not parsed['header']['test']:problems.append('header reports $TEST false in test mode')
        if mode=='normal' and parsed['header'] and parsed['header']['test']:problems.append('header reports $TEST true in normal mode')
    unchanged=scripts.is_file() and file_sha256(scripts)==stage_record['scripts_sha256']
    records=parsed['records'];counts={kind:sum(r['type']==kind for r in records) for kind in RECORD_TYPES}
    uncaught=sum(r['type']=='ERROR' and r['name']=='uncaught' for r in records)
    if not unchanged:status='integrity_failure'
    elif timed_out:status='timeout'
    elif problems:status='incomplete'
    elif counts['FAIL'] or counts['ERROR']:status='failed'
    else:status='pass'
    report={'version':VERSION,'status':status,'mode':mode,'start':start,'frames':frames,'auto_confirm':auto_confirm,'timeout_seconds':timeout,
            'nonce':nonce,'results_file':out_name,'runtime':parsed['header'],'records':records,'counts':counts,'uncaught':uncaught,
            'problems':problems,'timed_out':timed_out,'duration_seconds':duration,'process_exit_code':proc.returncode,
            'script_refs':script_refs(records,stage_record['script_names']),'copy':str(copy),'project':str(project),
            'scripts_unchanged_after_run':unchanged,'slot_source_sha256':stage_record['slot_source_sha256'],'suite_sha256':stage_record.get('suite_sha256'),
            'runtime_compatibility_proven':False,'mutation_authorized':False,
            'limits':['Results are evidence from one timing-dependent run, not proof; they do not replace manual testing.',
                      'The staged copy ran the project\'s own game code; never ship it.']}
    json_out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    markdown_out.write_text(markdown(report),encoding='utf-8')
    return report


def markdown(report):
    def cell(text):return str(text).replace('|','\\|').replace('\n',' ')
    lines=['# VX Ace smoke test report','',f"Status: **{report['status']}**",
           f"Mode: {report['mode']} / start: {report['start']} / frames: {report['frames']} / auto-confirm: {report['auto_confirm']}",
           f"Duration: {report['duration_seconds']} s, process exit code: {report['process_exit_code']}",
           'Counts: '+', '.join(f'{key} {value}' for key,value in report['counts'].items()),
           f"Runtime: {cell(report['runtime'])}",'']
    if report['problems']:lines+=['## Problems','']+['- '+cell(p) for p in report['problems']]+['']
    lines+=['## Records','','| Type | Name | Detail |','| --- | --- | --- |']
    lines+=[f"| {r['type']} | {cell(r['name'])} | {cell(r['detail'])} |" for r in report['records']]
    if report['script_refs']:
        lines+=['','## Script references','']+[f"- {cell(r['record'])}: {{{r['id']}}} -> {cell(r['script'])}" for r in report['script_refs']]
    lines+=['','Runtime compatibility proven: **False**. Mutation authorized: **False**.']
    lines+=['- '+text for text in report['limits']]
    return '\n'.join(lines)+'\n'


def json_argv(text):
    value=json.loads(text)
    if not isinstance(value,list) or not value or not all(isinstance(i,str) for i in value):raise argparse.ArgumentTypeError('expected a JSON list of strings')
    return value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    item=commands.add_parser('stage');item.add_argument('project');item.add_argument('--work',required=True);item.add_argument('--suite');item.add_argument('--ruby')
    item=commands.add_parser('run');item.add_argument('work');item.add_argument('--mode',choices=['test','normal'],required=True)
    item.add_argument('--start',default='new');item.add_argument('--frames',type=int,default=600);item.add_argument('--auto-confirm',type=int,default=0)
    item.add_argument('--timeout',type=float,default=120);item.add_argument('--json',required=True);item.add_argument('--markdown',required=True)
    item.add_argument('--launcher',type=json_argv,help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    try:
        if args.command=='stage':
            record=stage(args.project,args.work,args.suite,args.ruby)
            print(json.dumps({k:record[k] for k in ('version','copy','slot_index','scripts_sha256','slot_source_sha256')}));return 0
        report=run(args.work,args.mode,args.start,args.frames,args.auto_confirm,args.timeout,args.json,args.markdown,args.launcher)
    except Exception as error:print('Smoke test refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({k:report[k] for k in ('version','status','counts','duration_seconds','runtime_compatibility_proven')}))
    if report['status']=='integrity_failure':return 2
    return 0 if report['status']=='pass' else 3


if __name__=='__main__':raise SystemExit(main())
