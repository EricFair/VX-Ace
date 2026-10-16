#!/usr/bin/env python3
"""Read-only native display-name evidence and guarded detached string changes."""
from __future__ import annotations
import argparse,hashlib,json,sys,unicodedata
from pathlib import Path
from vxace_index_query import execute,unlinked
from vxace_map_regions import integer,table_for
from vxace_maps import MAP_FIELDS,plain
from vxace_map_events import exact

VERSION='1.5.0'
FIELDS={'action','expected_map_sha256','expected_display_name','value'}


def name(value):
    if not isinstance(value,str) or len(value)>64 or len(value.encode('utf-8','strict'))>256:
        raise ValueError('Display name requires at most64 UTF-8 characters/256 bytes')
    if value!=value.strip() or any(unicodedata.category(c).startswith('C') or c in '\u2028\u2029' for c in value):
        raise ValueError('Display name must be plain single-line text without controls or surrounding whitespace')
    return value


def current(root):
    from vxace_python_mutator import RubyString
    exact(root,'RPG::Map',MAP_FIELDS);table_for(root)
    old=root.get('display_name')
    if not isinstance(old,RubyString) or old.ivars not in ({},{'E':True},{'E':False}):
        raise ValueError('Native UTF-8 display-name string required; legacy encodings need separate review')
    value=old.data.decode('utf-8','strict')
    if old.ivars.get('E') is False and not value.isascii():raise ValueError('Non-ASCII bytes in an ASCII native display name')
    return name(value)


def fingerprint(root):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(root)).hexdigest()


def validate(root,mutation):
    if not isinstance(mutation,dict) or set(mutation)!=FIELDS or mutation.get('action')!='set_display_name':
        raise ValueError('Exact set_display_name schema required')
    old=current(root)
    if not isinstance(mutation['expected_map_sha256'],str) or mutation['expected_map_sha256']!=fingerprint(root):
        raise ValueError('Stale native map fingerprint')
    if not isinstance(mutation['expected_display_name'],str) or mutation['expected_display_name']!=old:
        raise ValueError('Stale native display-name precondition')
    value=name(mutation['value'])
    if value==old:raise ValueError('No-op display-name edit refused')
    return value


def apply(root,mutation):
    from vxace_python_mutator import RubyString
    value=validate(root,mutation)
    # Detach instead of mutating a string which another native field may share.
    root.set('display_name',RubyString(value.encode('utf-8'),{'E':True}))


def verify_transition(before,after,mutation):
    from vxace_python_mutator import marshal_rb
    expected=marshal_rb.load(marshal_rb.dump(before));apply(expected,mutation)
    if marshal_rb.dump(after)!=marshal_rb.dump(expected):
        raise ValueError('Display-name candidate changed unapproved native fields or aliases')


def indexed_snapshot(data,project,map_id):
    from vxace_python_mutator import load
    mid=integer(map_id,'map ID',1,999)
    root,raw=load(unlinked(Path(project)/f'Data/Map{mid:03d}.rvdata2'))
    old=current(root)
    if json.dumps(data.json(f'maps/map-{mid:03d}.json'),sort_keys=True)!=json.dumps(plain(root),sort_keys=True):
        raise ValueError('Native/indexed map display-name context disagrees')
    return {'version':VERSION,'map_id':mid,'display_name':old,'map_sha256':hashlib.sha256(raw).hexdigest(),
            'width':root.get('width'),'height':root.get('height'),
            'limits':['Only this map display_name; no tree/editor name or other property changes.',
                      'Custom display-name, map-loading and save hooks require project-specific native review.']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('index');parser.add_argument('--project',required=True)
    parser.add_argument('--map',type=int,required=True);parser.add_argument('--output',required=True);args=parser.parse_args(argv)
    try:result=execute(args.index,args.project,args.output,lambda data:indexed_snapshot(data,args.project,args.map),'map-name-snapshot')
    except Exception as error:print('Map-name snapshot refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({'status':'ok','map_id':result['map_id'],'mutation_authorized':False}));return 0


if __name__=='__main__':raise SystemExit(main())
