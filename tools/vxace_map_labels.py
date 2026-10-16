#!/usr/bin/env python3
"""Read-only map-tree name evidence and one guarded native label replacement."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
from vxace_index_query import execute,unlinked
from vxace_maps import info_table,inventory,digest,plain
from vxace_map_names import name
from vxace_map_regions import integer

VERSION='1.6.0'
FIELDS={'action','map_id','expected_infos_sha256','expected_entry_sha256','expected_inventory_sha256','expected_name','value'}


def context(infos,project,map_id):
    from vxace_python_mutator import load
    project=unlinked(project);actual,raw=load(unlinked(project/'Data/MapInfos.rvdata2'))
    if digest(actual)!=digest(infos):raise ValueError('Actual native map tree disagrees with label candidate context')
    lookup=info_table(infos);mid=integer(map_id,'map ID',1,999)
    if mid not in lookup:raise ValueError('Selected map is missing from native tree')
    rows,inventory_hash=inventory(project)
    if {row['id'] for row in rows}!=set(lookup):raise ValueError('Native map files/tree disagree; label editing refuses missing/orphan maps')
    for info in lookup.values():
        value=info.get('name')
        if value.ivars.get('E') is False and not value.data.decode('utf-8','strict').isascii():
            raise ValueError('Non-ASCII bytes in an ASCII native map label')
    old=name(lookup[mid].get('name').data.decode('utf-8','strict'))
    return lookup,{'expected_infos_sha256':hashlib.sha256(raw).hexdigest(),
                   'expected_entry_sha256':digest(lookup[mid]),'expected_inventory_sha256':inventory_hash,'expected_name':old}


def validate(infos,mutation,project):
    if not isinstance(mutation,dict) or set(mutation)!=FIELDS or mutation.get('action')!='set_tree_name':
        raise ValueError('Exact set_tree_name schema required')
    lookup,guard=context(infos,project,mutation['map_id'])
    for field,value in guard.items():
        if not isinstance(mutation[field],str) or mutation[field]!=value:raise ValueError('Stale native map-tree/name/inventory guard')
    value=name(mutation['value'])
    if value==guard['expected_name']:raise ValueError('No-op map-tree name edit refused')
    return lookup,value


def apply(infos,mutation,project):
    from vxace_python_mutator import RubyString
    lookup,value=validate(infos,mutation,project)
    # Labels are not identifiers; duplicate names are valid, shared old strings stay intact.
    lookup[mutation['map_id']].set('name',RubyString(value.encode('utf-8'),{'E':True}))


def verify_transition(before,after,mutation,project):
    from vxace_python_mutator import marshal_rb
    expected=marshal_rb.load(marshal_rb.dump(before));apply(expected,mutation,project)
    if marshal_rb.dump(after)!=marshal_rb.dump(expected):raise ValueError('Map-tree label candidate changed unapproved fields, entries or aliases')


def indexed_snapshot(data,project,map_id):
    from vxace_python_mutator import load
    root,_=load(unlinked(Path(project)/'Data/MapInfos.rvdata2'));lookup,guard=context(root,project,map_id)
    if json.dumps(data.json('database/map-infos.json'),sort_keys=True)!=json.dumps(plain(root),sort_keys=True):
        raise ValueError('Native/indexed map-tree name context disagrees')
    info=lookup[map_id]
    return {'version':VERSION,'map_id':map_id,'name':guard['expected_name'],'parent_id':info.get('parent_id'),
            'order':info.get('order'),'guard':guard,
            'limits':['One editor/tree name only; IDs, parent/order/scroll metadata and all map files stay unchanged.',
                      'Default MapInfos reloads on process startup; custom name caches/map/save consumers require review.',
                      'Display name and System/version do not change; no resize/delete/reparent or general property editor.']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('index');parser.add_argument('--project',required=True)
    parser.add_argument('--map',type=int,required=True);parser.add_argument('--output',required=True);args=parser.parse_args(argv)
    try:result=execute(args.index,args.project,args.output,lambda data:indexed_snapshot(data,args.project,args.map),'map-label-snapshot')
    except Exception as error:print('Map label snapshot refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({'status':'ok','map_id':result['map_id'],'mutation_authorized':False}));return 0


if __name__=='__main__':raise SystemExit(main())
