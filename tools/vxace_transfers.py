#!/usr/bin/env python3
"""Read-only evidence and native guards for one direct transfer in a blank event."""
from __future__ import annotations
import argparse,json,re,sys
from pathlib import Path
from vxace_index_query import execute,unlinked
from vxace_map_events import template,digest
from vxace_map_regions import integer

VERSION='1.4.0'
GUARD_FIELDS={'expected_source_sha256','expected_event_sha256','expected_destination_sha256',
              'expected_infos_sha256','expected_inventory_sha256','expected_tilesets_sha256'}
LIMITS=['One direct201 command in an existing blank stationary unconditional action-button event, targeting a different inert empty static map.',
        'No variable designation, touch/repeating/common/troop events, mixed command batches or general transfer authoring.',
        'Static bounds/tiles cannot prove runtime movement, assets, custom transfer hooks or reachability; review native editor, old save, actual event execution, movement, saving and restart.',
        'System/version advances to reload edited source-map events in default older saves; custom save/map loaders require separate review.']


def has_transfers(mutation):
    rows=mutation.get('commands',[]) if isinstance(mutation,dict) else []
    return isinstance(rows,list) and any(isinstance(row,dict) and type(row.get('code')) is int and row['code']==201 for row in rows)


def transfer_rows(rows):
    if not isinstance(rows,list) or len(rows)!=1:raise ValueError('Exactly one direct transfer command required')
    row=rows[0]
    if not isinstance(row,dict) or set(row)!={'code','indent','parameters'} or type(row['code']) is not int or row['code']!=201 or type(row['indent']) is not int or row['indent']!=0:
        raise ValueError('Exact root201 transfer row required')
    p=row['parameters']
    if not isinstance(p,list) or len(p)!=6 or any(type(v) is not int for v in p) or p[0]!=0:raise ValueError('Only six native integer direct-designation parameters are enabled')
    integer(p[1],'destination map ID',1,999);integer(p[2],'destination x',0,9999);integer(p[3],'destination y',0,9999)
    if p[4] not in (0,2,4,6,8) or p[5] not in (0,1,2):raise ValueError('Native retain/cardinal direction and normal/white/none fade required')
    return {'map_id':p[1],'x':p[2],'y':p[3],'direction':p[4],'fade':p[5]}


def validate_locator(loc):
    if not isinstance(loc,dict) or set(loc)!={'map_id','event_id','page','command_index'} or type(loc['page']) is not int or loc['page']!=1 or type(loc['command_index']) is not int or loc['command_index']!=0:
        raise ValueError('Exact blank map-event transfer locator required')
    integer(loc['map_id'],'source map ID',1,999);integer(loc['event_id'],'source event ID',1,999)


def destination_context(project,identifier):
    from vxace_python_mutator import load
    from vxace_maps import context
    infos,_=load(unlinked(Path(project)/'Data/MapInfos.rvdata2'))
    native,guards,_=context(infos,project,identifier)
    if native.get('events').pairs:raise ValueError('First transfer subset requires an empty inert destination map')
    return native,{'expected_destination_sha256':guards.pop('expected_template_sha256'),**guards}


def validate(root,mutation,source_path):
    from vxace_python_mutator import load,marshal_rb
    if mutation.get('scope')!='map' or mutation.get('action')!='insert_commands' or type(mutation.get('page')) is not int or mutation['page']!=1 or type(mutation.get('command_index')) is not int or mutation['command_index']!=0:
        raise ValueError('Transfers only insert at root zero on the blank single map page')
    if source_path is None:raise ValueError('Actual native source project is required for transfers')
    source=unlinked(source_path)
    match=re.fullmatch(r'Map([0-9]{3})\.rvdata2',source.name)
    if source.parent.name!='Data' or not match or not source.is_file():raise ValueError('Canonical native source map required')
    source_id=integer(int(match[1]),'source map ID',1,999)
    if source.name!=f'Map{source_id:03d}.rvdata2':raise ValueError('Canonical source ID required')
    actual,raw=load(source)
    if marshal_rb.dump(actual)!=raw or marshal_rb.dump(root)!=raw:raise ValueError('Actual source map bytes disagree or fail immediate round trip')
    target=transfer_rows(mutation.get('commands'))
    if target['map_id']==source_id:raise ValueError('Select a different destination map')
    selected=template(root,mutation.get('event_id'));destination,guards=destination_context(source.parent.parent,target['map_id'])
    if mutation.get('expected_list_sha256')!=digest(selected.get('pages')[0].get('list')):raise ValueError('Stale blank native transfer list guard')
    if target['x']>=destination.get('width') or target['y']>=destination.get('height'):raise ValueError('Direct destination lies outside actual native map dimensions')
    guard=mutation.get('transfer_guard')
    if not isinstance(guard,dict) or set(guard)!=GUARD_FIELDS:raise ValueError('Exact native transfer guards required')
    expected={'expected_source_sha256':digest(root),'expected_event_sha256':digest(selected),**guards}
    if guard!=expected:raise ValueError('Stale native source/event/destination/tree/inventory/tileset transfer guard')
    return {'source_map_id':source_id,'event_id':mutation['event_id'],'destination':target,'guard':expected}


def snapshot(data,project,map_id,event_id,destination_id,x,y,direction=2,fade=0):
    from vxace_python_mutator import load
    from vxace_maps import plain
    from vxace_event_structure import fingerprint
    integer(map_id,'source map ID',1,999);integer(event_id,'source event ID',1,999)
    rows=[{'code':201,'indent':0,'parameters':[0,destination_id,x,y,direction,fade]}]
    target=transfer_rows(rows)
    source=unlinked(Path(project)/f'Data/Map{map_id:03d}.rvdata2');root,_=load(source);event=template(root,event_id)
    destination,guards=destination_context(project,destination_id)
    guard={'expected_source_sha256':digest(root),'expected_event_sha256':digest(event),**guards}
    mutation={'scope':'map','event_id':event_id,'page':1,'command_index':0,'action':'insert_commands',
              'expected_list_sha256':fingerprint(event.get('pages')[0].get('list')),'commands':rows,'transfer_guard':guard}
    validate(root,mutation,source)
    infos,_=load(unlinked(Path(project)/'Data/MapInfos.rvdata2'));tilesets,_=load(unlinked(Path(project)/'Data/Tilesets.rvdata2'))
    for relative,native in ((f'maps/map-{map_id:03d}.json',root),(f'maps/map-{destination_id:03d}.json',destination),('database/map-infos.json',infos),('database/tilesets.json',tilesets)):
        if json.dumps(data.json(relative),sort_keys=True)!=json.dumps(plain(native),sort_keys=True):raise ValueError('Actual native source/destination/tree disagrees with indexed evidence')
    from vxace_map_audit import audit
    report=audit(data,destination_id,(x,y))
    if report['findings']:raise ValueError('Destination native tile diagnostics require resolution')
    return {'version':VERSION,'source_map_id':map_id,'event_id':event_id,'page':1,'command_index':0,
            'expected_list_sha256':mutation['expected_list_sha256'],'commands':rows,'transfer_guard':guard,
            'destination':target,'destination_tile_evidence':report['maps'][0]['cell'],'limits':LIMITS}


def verify_transition(before,after,mutation,source_path):
    from vxace_python_mutator import marshal_rb,convert,object_by_id
    from vxace_event_structure import apply
    expected=marshal_rb.load(marshal_rb.dump(before));apply(expected,mutation,convert,object_by_id,source_path=source_path)
    if marshal_rb.dump(expected)!=marshal_rb.dump(after):raise ValueError('Transfer candidate changed unapproved native source-map bytes/fields')


def final_context(mutation,project):
    """Destination/tree/tileset bytes stay fixed; source map legitimately changed."""
    from vxace_python_mutator import load
    guard=mutation['transfer_guard'];target=transfer_rows(mutation['commands']);project=Path(project)
    for relative,key in ((f"Map{target['map_id']:03d}.rvdata2",'expected_destination_sha256'),('MapInfos.rvdata2','expected_infos_sha256'),('Tilesets.rvdata2','expected_tilesets_sha256')):
        root,raw=load(unlinked(project/'Data'/relative))
        import hashlib
        if hashlib.sha256(raw).hexdigest()!=guard[key] or digest(root)!=guard[key]:raise ValueError('Transfer destination context changed during final verification')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('index');parser.add_argument('--project',required=True)
    for name in ('map','event','destination','x','y'):parser.add_argument('--'+name,type=int,required=True)
    parser.add_argument('--direction',type=int,default=2);parser.add_argument('--fade',type=int,default=0);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    try:result=execute(args.index,args.project,args.output,lambda data:snapshot(data,args.project,args.map,args.event,args.destination,args.x,args.y,args.direction,args.fade),'transfer-snapshot')
    except Exception as error:print('Transfer snapshot refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({'status':'ok','destination':result['destination'],'mutation_authorized':False}));return 0


if __name__=='__main__':raise SystemExit(main())
