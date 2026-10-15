#!/usr/bin/env python3
"""Native script archive snapshots and one guarded insertion before canonical Main."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zlib
from vxace_index_query import execute, unlinked

VERSION='0.24.0'
MAX_ENTRIES=4096
MAX_SOURCE_BYTES=16*1024*1024
MAX_TOTAL_BYTES=64*1024*1024
MAX_NEW_SOURCE_BYTES=256*1024
MAIN_CALL='rgss_main { SceneManager.run }'


def integer(value,label,minimum,maximum):
    if type(value) is not int or not minimum<=value<=maximum:raise ValueError(label+' outside integer bounds')
    return value


def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def inflate(value):
    inflater=zlib.decompressobj()
    try:raw=inflater.decompress(value,MAX_SOURCE_BYTES+1)
    except zlib.error as error:raise ValueError('Invalid compressed script source') from error
    if len(raw)>MAX_SOURCE_BYTES or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise ValueError('Incomplete/trailing/oversized script source')
    raw.decode('utf-8','strict')
    return raw


def archive(root):
    from vxace_python_mutator import RubyString
    if not isinstance(root,list) or not 1<=len(root)<=MAX_ENTRIES:raise ValueError('Expected bounded native script archive array')
    names=[];sources=[];seen=set();total=0
    for entry in root:
        if not isinstance(entry,list) or len(entry)!=3:raise ValueError('Each script entry must have exactly three native fields')
        identifier=integer(entry[0],'existing script ID',0,2**31-1)
        if identifier in seen:raise ValueError('Existing script IDs must be unique')
        seen.add(identifier)
        for value in entry[1:]:
            if not isinstance(value,RubyString) or (value.ivars!={} and not (set(value.ivars)=={'E'} and type(value.ivars['E']) is bool)):
                raise ValueError('Unsupported native script string metadata')
        names.append(entry[1].data.decode('utf-8','strict'))
        if len(entry[2].data)>MAX_SOURCE_BYTES:raise ValueError('Compressed script byte budget exceeded')
        raw=inflate(entry[2].data);total+=len(raw)
        if total>MAX_TOTAL_BYTES:raise ValueError('Total script source budget exceeded')
        sources.append(raw)
    return names,sources


def anchor(root,before_index):
    names,sources=archive(root)
    index=integer(before_index,'before script index',0,len(root)-1)
    if names[index]!='Main' or names.count('Main')!=1:
        raise ValueError('Insertion requires the unique Main entry')
    active=[line.strip() for line in sources[index].decode('utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if active!=[MAIN_CALL]:raise ValueError('Customized Main source is not a supported insertion anchor')
    if any(value.ivars!={'E':True} for value in root[index][1:]):
        raise ValueError('Selected Main requires verified native UTF-8 string metadata')
    return index,names,sources


def snapshot(root,before_index):
    index,names,sources=anchor(root,before_index)
    used={entry[0] for entry in root};candidate=max(used)+1
    if candidate>2**31-1:candidate=next((number for number in range(1,len(used)+2) if number not in used),None)
    return {'archive_sha256':digest(root),'anchor_sha256':digest(root[index]),'before_index':index,
            'anchor_id':root[index][0],'anchor_name':names[index],
            'anchor_source_sha256':hashlib.sha256(sources[index]).hexdigest(),
            'existing_entries':len(root),'insertion_supported':len(root)<MAX_ENTRIES,
            'unused_id_candidate':candidate,
            'entries':[{'index':n,'id':entry[0],'name':names[n],'entry_sha256':digest(entry),
                        'source_sha256':hashlib.sha256(sources[n]).hexdigest(),'source_bytes':len(sources[n])} for n,entry in enumerate(root)],
            'scope':'one insertion before unique canonical Main; no reordering/deletion or source replacement'}


def new_slot(root,mutation):
    from vxace_python_mutator import RubyString
    fields={'action','before_index','expected_archive_sha256','expected_anchor_sha256','new_id','name','source'}
    if not isinstance(mutation,dict) or set(mutation)!=fields or mutation.get('action')!='insert_before_main':
        raise ValueError('Only the exact insert_before_main schema is supported')
    index,names,sources=anchor(root,mutation['before_index'])
    if len(root)>=MAX_ENTRIES:raise ValueError('Native script entry capacity reached')
    for field in ('expected_archive_sha256','expected_anchor_sha256'):
        if not isinstance(mutation[field],str) or not re.fullmatch('[a-f0-9]{64}',mutation[field]):raise ValueError('Exact script SHA-256 preconditions required')
    if mutation['expected_archive_sha256']!=digest(root) or mutation['expected_anchor_sha256']!=digest(root[index]):
        raise ValueError('Script archive/anchor fingerprint is stale')
    identifier=integer(mutation['new_id'],'new script ID',1,2**31-1)
    if identifier in {entry[0] for entry in root}:raise ValueError('New script ID already exists')
    name=mutation['name'];source=mutation['source']
    if not isinstance(name,str) or not 1<=len(name)<=80 or name!=name.strip() or any(ord(c)<32 or ord(c)==127 for c in name) or name in names:
        raise ValueError('New script name must be unique bounded text without control codes')
    if not isinstance(source,str):raise ValueError('New script source must be exact UTF-8 text')
    raw=source.encode('utf-8','strict');label=name.encode('utf-8','strict')
    if not 1<=len(raw)<=MAX_NEW_SOURCE_BYTES or b'\0' in raw or sum(map(len,sources))+len(raw)>MAX_TOTAL_BYTES:
        raise ValueError('New script source exceeds supported byte range or contains NUL')
    return [identifier,RubyString(label,{'E':True}),RubyString(zlib.compress(raw),{'E':True})]


def apply(root,mutation):
    entry=new_slot(root,mutation)
    root.insert(mutation['before_index'],entry)


def verify_transition(before,after,mutation):
    expected=new_slot(before,mutation);index=mutation['before_index']
    archive(after)
    if len(after)!=len(before)+1 or digest(after[:index]+after[index+1:])!=digest(before):
        raise ValueError('Script slot candidate changed existing entries or their order')
    if digest(after[index])!=digest(expected):raise ValueError('Script slot candidate differs from the approved native entry')
    existing_strings={id(value) for entry in after[:index]+after[index+1:] for value in entry[1:]}
    if any(id(value) in existing_strings for value in after[index][1:]):raise ValueError('Inserted script strings must not alias existing entries')


def indexed_snapshot(data,project,before_index):
    from vxace_python_mutator import load
    project=unlinked(project)
    if project.is_file() and project.suffix.lower()=='.rvproj2':project=project.parent
    root,_=load(unlinked(project/'Data/Scripts.rvdata2'))
    result=snapshot(root,before_index);order=data.json('scripts/order.json').get('scripts')
    if not isinstance(order,list) or len(order)!=len(root):raise ValueError('Native/indexed script counts disagree')
    seen=set()
    for observed,entry in zip(order,result['entries']):
        if not isinstance(observed,dict) or any(observed.get(key)!=entry[key] for key in ('index','id','name','source_sha256','source_bytes')):
            raise ValueError('Native/indexed script identity or source metadata disagree')
        path=observed.get('path')
        if not isinstance(path,str) or not path or any(c in path for c in '/\\:') or path in ('.','..') or path in seen:
            raise ValueError('Unsafe or duplicate indexed script path')
        seen.add(path);raw=data.text('scripts/'+path).encode('utf-8','strict')
        if hashlib.sha256(raw).hexdigest()!=entry['source_sha256'] or len(raw)!=entry['source_bytes']:
            raise ValueError('Indexed script bytes differ from native archive')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('index');parser.add_argument('--project',required=True)
    parser.add_argument('--before-index',type=int,required=True);parser.add_argument('--output',required=True);args=parser.parse_args(argv)
    try:
        result=execute(args.index,args.project,args.output,lambda data:indexed_snapshot(data,args.project,args.before_index),'script-slot-snapshot')
    except Exception as error:print('Script slot snapshot refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({'version':VERSION,'existing_entries':result['existing_entries'],'insertion_supported':result['insertion_supported']}));return 0


if __name__=='__main__':raise SystemExit(main())
