#!/usr/bin/env python3
"""Prepare/collect compile-only Ruby 1.9.2 diagnostics; never launch or edit a game."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys
from vxace_index_query import Index, unlinked
from vxace_mcp_api import fresh, inventory
from vxace_project_validator import extract_scripts, find_ruby

VERSION='0.23.0'
MAX_SCRIPTS=4096
MAX_SOURCE_BYTES=256*1024
MAX_TOTAL_BYTES=4*1024*1024
MAX_HARNESS_BYTES=9*1024*1024
MAX_REPORT_BYTES=16*1024*1024
ROOT=Path(__file__).resolve().parent


def digest(raw):return hashlib.sha256(raw).hexdigest()


def bounded(path, maximum):
    path=unlinked(path)
    if not path.is_file():raise ValueError('Expected a regular native diagnostic file')
    with path.open('rb') as stream:raw=stream.read(maximum+1)
    if len(raw)>maximum:raise ValueError('Native diagnostic file byte budget exceeded')
    return raw


def snapshot(index, project, ruby):
    project=unlinked(project)
    if project.is_file() and project.suffix.lower()=='.rvproj2':project=project.parent
    data=Index(index); before=fresh(data,project)
    order=data.json('scripts/order.json').get('scripts')
    if not isinstance(order,list) or not 1<=len(order)<=MAX_SCRIPTS:
        raise ValueError('Native diagnostics require 1..4096 indexed scripts')
    actual=extract_scripts(ruby,ROOT/'rvdata2_bridge.rb',unlinked(project/'Data/Scripts.rvdata2'))
    if len(actual)!=len(order):raise ValueError('Native/indexed script counts disagree')
    rows=[];total=0;seen=set()
    for number,(entry,native) in enumerate(zip(order,actual)):
        if not isinstance(entry,dict) or type(entry.get('index')) is not int or entry['index']!=number or native.get('index')!=number:
            raise ValueError('Script indices must match exact native archive order')
        if not isinstance(entry.get('name'),str) or len(entry['name'])>512:
            raise ValueError('Native diagnostic script labels exceed the supported range')
        path=entry.get('path')
        if not isinstance(path,str) or not path or any(c in path for c in '/\\:') or path in ('.','..') or path in seen:
            raise ValueError('Unsafe or duplicate indexed script path')
        seen.add(path)
        raw=data.text('scripts/'+path).encode('utf-8','strict')
        if len(raw)>MAX_SOURCE_BYTES or total+len(raw)>MAX_TOTAL_BYTES:
            raise ValueError('Native compile source budget exceeded (256 KiB each / 4 MiB total)')
        total+=len(raw); sha=digest(raw)
        for observed in (entry,native):
            if observed.get('source_sha256')!=sha or type(observed.get('source_bytes')) is not int or observed['source_bytes']!=len(raw) or observed.get('utf8_decodable') is not True:
                raise ValueError('Indexed/native script source integrity mismatch')
        if native.get('source','').encode('utf-8','strict')!=raw or entry.get('name')!=native.get('name') or entry.get('id')!=native.get('id'):
            raise ValueError('Indexed script does not match the native archive')
        rows.append({'index':number,'name':entry.get('name'),'source_sha256':sha,'source_bytes':len(raw),'hex':raw.hex()})
    data.unchanged()
    if inventory(project)!=before:raise ValueError('Source changed during native diagnostic preparation')
    fingerprint=digest(json.dumps(before,sort_keys=True,separators=(',',':')).encode('utf-8'))
    return data,project,before,fingerprint,rows


def render_harness(token,rows):
    if not isinstance(token,str) or not re.fullmatch('[a-f0-9]{32}',token):raise ValueError('Invalid native diagnostic token')
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_SCRIPTS:raise ValueError('Invalid harness script count')
    total=0
    for number,row in enumerate(rows):
        if type(row.get('index')) is not int or row['index']!=number or type(row.get('source_bytes')) is not int or not 0<=row['source_bytes']<=MAX_SOURCE_BYTES:
            raise ValueError('Invalid harness source index/size')
        encoded=row.get('hex');sha=row.get('source_sha256')
        if not isinstance(encoded,str) or len(encoded)!=row['source_bytes']*2 or not re.fullmatch('(?:[0-9a-f]{2})*',encoded) or sha!=digest(bytes.fromhex(encoded)):
            raise ValueError('Invalid harness source hex/hash')
        total+=row['source_bytes']
        if total>MAX_TOTAL_BYTES:raise ValueError('Native compile total source budget exceeded')
    template=(ROOT/'native_syntax_harness.rb').read_text(encoding='utf-8')
    # Only fixed integers, validated hex and digests enter Ruby literals. Names/code
    # are never interpolated into executable Ruby; source bytes are packed as data.
    literals=',\n'.join('[%d,"%s",%d,"%s"]'%(r['index'],r['source_sha256'],r['source_bytes'],r['hex']) for r in rows)
    raw=template.replace('__VXACE_TOKEN__',token).replace('__VXACE_ROWS__',literals).encode('ascii')
    if len(raw)>MAX_HARNESS_BYTES:raise ValueError('Native harness byte budget exceeded')
    return raw


def external_output(output,*inputs):
    output=unlinked(output)
    if output.exists() or any(output==p or p in output.parents for p in inputs):
        raise ValueError('Use a new diagnostic output outside project, index and bundle')
    return output


def prepare(index,project,output,ruby=None):
    data,project,before,fingerprint,rows=snapshot(index,project,find_ruby(ruby))
    output=external_output(output,project,data.root)
    token=secrets.token_hex(16);harness=render_harness(token,rows)
    manifest={'version':VERSION,'token':token,'source_inventory_sha256':fingerprint,
              'harness_sha256':digest(harness),'result_filename':'vxace-native-syntax-'+token+'.tsv',
              'scripts':[{k:v for k,v in row.items() if k!='hex'} for row in rows],
              'source_unchanged':True,'mutation_performed':False,'runtime_compatibility_proven':False}
    manifest_bytes=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    if len(manifest_bytes)>4*1024*1024:raise ValueError('Native manifest byte budget exceeded')
    data.unchanged()
    if inventory(project)!=before:raise ValueError('Source changed before bundle output')
    output.mkdir(parents=True)
    (output/'native-syntax-harness.rb').write_bytes(harness)
    (output/'manifest.json').write_bytes(manifest_bytes)
    (output/'PRIVATE_README.txt').write_text(
        'PRIVATE: harness contains exact project script bytes. Never publish this bundle.\n'
        'Use only a separate trusted blank VX Ace host on a disposable copy.\n'
        'Stage the exact harness immediately before Main through the normal guarded copy workflow.\n'
        'It compiles embedded sources without evaluating them, writes '+manifest['result_filename']+' and exits.\n'
        'Do not use the inspected custom game as the host: earlier scripts would execute.\n'
        'Read references/native-syntax-diagnostics.md for staging, collection and limits.\n',encoding='utf-8')
    return manifest


def parse_result(raw,manifest):
    try:lines=raw.decode('ascii','strict').splitlines()
    except UnicodeError as error:raise ValueError('Native result is not bounded ASCII TSV') from error
    expected_header=['VXACE_NATIVE_SYNTAX','1',manifest['token'],'1.9.2','true']
    if not lines or lines[0].split('\t')!=expected_header:
        raise ValueError('Native report token/version/compiler header mismatch or compiler unavailable')
    scripts=manifest['scripts']
    if len(lines)!=len(scripts)+2 or lines[-1].split('\t')!=['COMPLETE',str(len(scripts))]:
        raise ValueError('Native report is incomplete, duplicated or has trailing records')
    results=[]
    for line,source in zip(lines[1:-1],scripts):
        parts=line.split('\t')
        if len(parts)!=5 or parts[:3]!=[str(source['index']),source['source_sha256'],str(source['source_bytes'])] or parts[3] not in ('pass','syntax_error','compiler_error'):
            raise ValueError('Native report source/order/status mismatch')
        if len(parts[4])>4096 or not re.fullmatch('(?:[0-9a-f]{2})*',parts[4]) or (parts[3]=='pass' and parts[4]):
            raise ValueError('Native report error text is malformed or exceeds budget')
        results.append({**source,'status':parts[3],'diagnostic':bytes.fromhex(parts[4]).decode('utf-8','replace')})
    return results


def collect(index,project,bundle,result,output,ruby=None):
    data,project,before,fingerprint,rows=snapshot(index,project,find_ruby(ruby))
    bundle=unlinked(bundle);result=unlinked(result)
    output=external_output(output,project,data.root,bundle,result.parent)
    manifest_raw=bounded(bundle/'manifest.json',4*1024*1024)
    manifest=json.loads(manifest_raw.decode('utf-8','strict'))
    summaries=[{k:v for k,v in row.items() if k!='hex'} for row in rows]
    if manifest.get('version')!=VERSION or manifest.get('source_inventory_sha256')!=fingerprint or manifest.get('scripts')!=summaries:
        raise ValueError('Native bundle is stale or does not match source scripts')
    token=manifest.get('token');harness=render_harness(token,rows)
    if manifest.get('harness_sha256')!=digest(harness) or bounded(bundle/'native-syntax-harness.rb',MAX_HARNESS_BYTES)!=harness:
        raise ValueError('Native harness differs from exact generated compile-only scaffold')
    if manifest.get('result_filename')!='vxace-native-syntax-'+token+'.tsv' or result.name!=manifest['result_filename']:
        raise ValueError('Native report filename does not match this bundle')
    raw=bounded(result,MAX_REPORT_BYTES);results=parse_result(raw,manifest)
    data.unchanged()
    if inventory(project)!=before or bounded(result,MAX_REPORT_BYTES)!=raw or bounded(bundle/'manifest.json',4*1024*1024)!=manifest_raw or bounded(bundle/'native-syntax-harness.rb',MAX_HARNESS_BYTES)!=harness:
        raise ValueError('Native diagnostic inputs changed during collection')
    failed=sum(row['status']!='pass' for row in results)
    report={'version':VERSION,'status':'failed' if failed else 'pass','checked':len(results),'failed':failed,
            'native_ruby_version':'1.9.2','native_parse_report_validated':True,'compile_only':True,
            'source_unchanged':True,'mutation_authorized':False,'runtime_compatibility_proven':False,
            'engine_launch_observed_by_tool':False,'scripts':results,
            'limits':['Compilation does not evaluate source or prove runtime behavior, load order or save compatibility.',
                      'Operator must observe the actual VX Ace launch on a separate trusted disposable host.',
                      'Local report validation is not a cryptographic attestation or an OS sandbox.']}
    output.mkdir(parents=True)
    (output/'native-syntax.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','collect'):
        item=commands.add_parser(name);item.add_argument('index');item.add_argument('--project',required=True)
        item.add_argument('--output',required=True);item.add_argument('--ruby')
        if name=='collect':item.add_argument('--bundle',required=True);item.add_argument('--result',required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='prepare':report=prepare(args.index,args.project,args.output,args.ruby)
        else:report=collect(args.index,args.project,args.bundle,args.result,args.output,args.ruby)
    except Exception as error:print('Native syntax diagnostic refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({k:report[k] for k in ('version','status','checked','failed','runtime_compatibility_proven') if k in report}))
    return 3 if report.get('failed') else 0


if __name__=='__main__':raise SystemExit(main())
