#!/usr/bin/env python3
"""Export exact structural preconditions from a read-only native event."""
import argparse
import json
from pathlib import Path
from vxace_python_mutator import load, object_by_id
from vxace_event_structure import snapshot, native_int


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project'); parser.add_argument('--output',required=True)
    scopes=parser.add_mutually_exclusive_group(required=True)
    scopes.add_argument('--map-id',type=int); scopes.add_argument('--common-event-id',type=int); scopes.add_argument('--troop-id',type=int)
    parser.add_argument('--event-id',type=int); parser.add_argument('--page',type=int,default=1)
    args=parser.parse_args(argv)
    try:
        project=Path(args.project).resolve()
        if project.is_file() and project.suffix.lower()=='.rvproj2': project=project.parent
        output=Path(args.output).resolve()
        if output==project or project in output.parents or output.exists(): raise ValueError('Use a new external output directory')
        if args.map_id is not None:
            native_int(args.map_id,'map id',1,999); native_int(args.event_id,'event id',1)
            mutation={'scope':'map','event_id':args.event_id,'page':args.page}; file=f'Map{args.map_id:03d}.rvdata2'
        elif args.common_event_id is not None:
            mutation={'scope':'common_event','common_event_id':args.common_event_id}; file='CommonEvents.rvdata2'
        else:
            mutation={'scope':'troop','troop_id':args.troop_id,'page':args.page}; file='Troops.rvdata2'
        root,raw=load(project/'Data'/file)
        result={'version':'0.12.0','read_only':True,'source_file':file,'locator':mutation,**snapshot(root,mutation,object_by_id)}
        output.mkdir(parents=True)
        (output/'event-snapshot.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':'ok','command_count':result['command_count']}))
        return 0
    except Exception as exc:
        print(f'Snapshot refused: {exc}',file=__import__('sys').stderr); return 2


if __name__=='__main__': raise SystemExit(main())
