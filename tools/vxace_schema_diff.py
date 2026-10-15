#!/usr/bin/env python3
"""Bounded read-only comparison of observed shapes against a chosen baseline."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
from vxace_index_query import Index,unlinked

VERSION='1.3.0'
MAX_CLASSES=2048
MAX_FIELDS=50000
MAX_REPORT_BYTES=2*1024*1024
MAX_EVIDENCE_BYTES=512*1024
MAX_SOURCE_ENTRIES=20000
MAX_SOURCE_BYTES=512*1024*1024
MAX_SOURCE_FILE_BYTES=64*1024*1024
SAMPLES=3
LIMITS=[
    'Baseline-relative observations only: new classes/fields are not automatically invalid or safe to mutate.',
    'An absent class/field can reflect content coverage, not schema removal; selected baselines need human review.',
    'Types describe normalized JSON values, not complete native serialized Ruby types or runtime semantics.',
    'Only decoded database/maps are compared; scripts, dynamic fields, opaque data and runtime save state are excluded.',
    'Counts are descriptive; no script execution, mutation permission, automatic repair or universal engine-schema claim.',
    'Freshness and before/after hashes detect changes but do not lock files against concurrent writers.'
]


def inventory(project):
    """Refuse links before opening files; bound full source integrity reads."""
    result={};total=0
    for number,path in enumerate(project.rglob('*'),1):
        if number>MAX_SOURCE_ENTRIES:raise ValueError('Source entry budget exceeded')
        path=unlinked(path)
        if not path.is_file():continue
        size=path.stat().st_size
        if size>MAX_SOURCE_FILE_BYTES or total+size>MAX_SOURCE_BYTES:raise ValueError('Source byte budget exceeded')
        digest=hashlib.sha256();read=0
        with path.open('rb') as stream:
            while True:
                chunk=stream.read(1024*1024)
                if not chunk:break
                read+=len(chunk)
                if read>MAX_SOURCE_FILE_BYTES or total+read>MAX_SOURCE_BYTES:raise ValueError('Source grew beyond byte budget')
                digest.update(chunk)
        if read!=size:raise ValueError('Source changed during inventory')
        total+=read;result[path.relative_to(project).as_posix()]=digest.hexdigest()
    return result


def observed(data):
    classes={};field_count=0;evidence_bytes=0
    def sample(bucket,location):
        nonlocal evidence_bytes
        if len(bucket)>=SAMPLES:return
        evidence_bytes+=len(json.dumps(location,ensure_ascii=False).encode('utf-8'))
        if evidence_bytes>MAX_EVIDENCE_BYTES:raise ValueError('Schema evidence byte budget exceeded')
        bucket.append(location)
    for directory in ('database','maps'):
        for file in data.paths(directory):
            stack=[(data.json(file),())]
            while stack:
                value,path=stack.pop();data.spend()
                if len(path)>128:raise ValueError('Schema nesting budget exceeded')
                if isinstance(value,dict):
                    if any(len(key)>256 for key in value):raise ValueError('Oversized schema/evidence key')
                    name=value.get('__class__')
                    if name is not None:
                        if not isinstance(name,str) or not name or len(name)>256:raise ValueError('Invalid normalized class name')
                        if name not in classes:
                            if len(classes)>=MAX_CLASSES:raise ValueError('Schema class budget exceeded')
                            classes[name]={'objects':0,'evidence':[],'fields':{}}
                        entry=classes[name];entry['objects']+=1
                        evidence={'file':file,'path':list(path)}
                        sample(entry['evidence'],evidence)
                        for key,item in sorted(value.items()):
                            if key.startswith('__'):continue
                            if key not in entry['fields']:
                                field_count+=1
                                if field_count>MAX_FIELDS:raise ValueError('Schema field budget exceeded')
                                entry['fields'][key]={'observations':0,'types':{},'evidence':[]}
                            field=entry['fields'][key];field['observations']+=1
                            kind=type(item).__name__;typed=field['types'].setdefault(kind,{'count':0,'evidence':[]});typed['count']+=1
                            location={'file':file,'path':[*path,key]}
                            sample(typed['evidence'],location)
                            sample(field['evidence'],location)
                    data.spend(len(value))
                    stack.extend((item,(*path,key)) for key,item in reversed(sorted(value.items())))
                elif isinstance(value,list):
                    data.spend(len(value))
                    stack.extend((value[n],(*path,n)) for n in range(len(value)-1,-1,-1))
    return classes


def compare(baseline,target):
    before=observed(baseline);after=observed(target);rows=[]
    counts={'classes_only_in_target':0,'classes_only_in_baseline':0,'fields_only_in_target':0,'fields_only_in_baseline':0,'field_type_sets_changed':0}
    for name in sorted(set(before)|set(after)):
        left=before.get(name);right=after.get(name)
        status='shared' if left is not None and right is not None else ('only_in_target' if right is not None else 'only_in_baseline')
        if status!='shared':counts['classes_'+status]+=1
        fields=[]
        for key in sorted(set((left or {}).get('fields',{}))|set((right or {}).get('fields',{}))):
            a=(left or {}).get('fields',{}).get(key);b=(right or {}).get('fields',{}).get(key)
            state='same_type_set' if a is not None and b is not None else ('only_in_target' if b is not None else 'only_in_baseline')
            if a is not None and b is not None and set(a['types'])!=set(b['types']):state='type_set_changed'
            # Class-only fields are recorded but not counted again as shared-class drift.
            if status=='shared' and state!='same_type_set':
                counts['field_type_sets_changed' if state=='type_set_changed' else 'fields_'+state]+=1
            fields.append({'field':key,'status':state,'baseline':a,'target':b})
        rows.append({'class':name,'status':status,'baseline_objects':left['objects'] if left else 0,'target_objects':right['objects'] if right else 0,
                     'baseline_evidence':left['evidence'] if left else [],'target_evidence':right['evidence'] if right else [],'fields':fields})
    return {'version':VERSION,'comparison':'explicit-baseline-relative','counts':counts,'classes':rows,'limits':LIMITS}


def source_context(index,project):
    project=unlinked(project)
    if project.is_file() and project.suffix.lower()=='.rvproj2':project=project.parent
    if not (project/'Data').is_dir():raise ValueError('Expected a VX Ace project for each index')
    data=Index(index);manifest=data.json('manifest.json')
    files=manifest.get('files') if isinstance(manifest,dict) else None
    import re
    if not files or manifest.get('read_only') is not True or any(not isinstance(row,dict) or not re.fullmatch('[a-fA-F0-9]{64}',str(row.get('sha256',''))) for row in files):
        raise ValueError('Both indexes require hashed read-only manifests')
    before=inventory(project)
    # Compare the bounded inventory directly rather than reading source twice.
    from vxace_copy_patcher import safe_rel
    expected={safe_rel(str(row['path'])):row['sha256'].lower() for row in files}
    if before!=expected:raise ValueError('Stale baseline or target; re-index the actual project')
    return data,project,before


def workflow(baseline_index,baseline_project,target_index,target_project,output):
    baseline,bp,bi=source_context(baseline_index,baseline_project)
    target,tp,ti=source_context(target_index,target_project)
    output=unlinked(output)
    if output.exists() or any(output==root or root in output.parents for root in (baseline.root,bp,target.root,tp)):
        raise ValueError('Use a new output directory outside both projects and indexes')
    result=compare(baseline,target)
    result.update(read_only=True,mutation_authorized=False,source_freshness='fresh',both_sources_unchanged=True,both_read_indexes_unchanged=True)
    result['snapshots']={label:{'manifest_sha256':data.hashes[data.path('manifest.json')],
                              'project_inventory_sha256':hashlib.sha256(json.dumps(inv,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                              'project_file_count':len(inv)} for label,data,inv in (('baseline',baseline,bi),('target',target,ti))}
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    if len(raw)>MAX_REPORT_BYTES:raise ValueError('Schema report byte budget exceeded; no partial report produced')
    baseline.unchanged();target.unchanged()
    if inventory(bp)!=bi or inventory(tp)!=ti:raise ValueError('Baseline or target project changed during comparison')
    # Recheck linked paths as well as bytes immediately before publishing evidence.
    for project,inv in ((bp,bi),(tp,ti)):
        for relative in inv:unlinked(project/relative)
    unlinked(output)
    output.mkdir(parents=True)
    try:
        (output/'schema-diff.json').write_bytes(raw)
        lines=['# Observed schema comparison','','Read-only; relative to the explicitly selected baseline.','']
        lines += [f'- {key}: {value}' for key,value in result['counts'].items()]
        lines += ['','Exact class/field/type evidence is in schema-diff.json.','','## Limits','']+['- '+line for line in LIMITS]
        (output/'schema-diff.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    except Exception:
        # Only newly created report files can be removed; no input path is touched.
        for name in ('schema-diff.json','schema-diff.md'):
            file=output/name
            if file.is_file():file.unlink()
        output.rmdir();raise
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline_index');parser.add_argument('target_index')
    parser.add_argument('--baseline-project',required=True);parser.add_argument('--project',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    try:result=workflow(args.baseline_index,args.baseline_project,args.target_index,args.project,args.output)
    except Exception as error:print('Schema comparison refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({'status':'ok','counts':result['counts'],'mutation_authorized':False}));return 0


if __name__=='__main__':raise SystemExit(main())
