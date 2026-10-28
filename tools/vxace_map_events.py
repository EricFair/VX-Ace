#!/usr/bin/env python3
"""Read-only native event snapshots and guarded stationary dialogue-event append."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from vxace_index_query import execute, unlinked
from vxace_map_regions import integer, table_for

VERSION = '0.27.0'
FIELDS = {'action','template_id','new_id','name','x','y','text',
          'expected_map_sha256','expected_template_sha256'}
EVENT_FIELDS = {'id','name','x','y','pages'}
PAGE_FIELDS = {'condition','graphic','move_type','move_speed','move_frequency','move_route',
               'walk_anime','step_anime','direction_fix','through','priority_type','trigger','list'}
CONDITION_FLAGS = {'switch1_valid','switch2_valid','variable_valid','self_switch_valid','item_valid','actor_valid'}
CONDITION_INTS = {'switch1_id','switch2_id','variable_id','variable_value','item_id','actor_id'}
GRAPHIC_FIELDS = {'tile_id','character_name','character_index','direction','pattern'}


def schema(mutation):
    if not isinstance(mutation,dict) or set(mutation) not in (FIELDS,FIELDS|{'graphic','expected_asset'}) or mutation.get('action')!='append_dialogue_event':
        raise ValueError('Exact append_dialogue_event schema required; optional graphic and expected_asset must appear together')
    if 'graphic' in mutation:
        from vxace_character_graphics import graphic_schema
        graphic_schema(mutation['graphic'])


def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def exact(value, cls, fields):
    from vxace_python_mutator import RubyObject
    if not isinstance(value,RubyObject) or value.cls!=cls or set(value.ivars)!={'@'+field for field in fields}:
        raise ValueError('Unsupported native schema for '+cls)
    return value


def text(value,label,limit,empty=False):
    if not isinstance(value,str) or not (0 if empty else 1)<=len(value)<=limit or any(ord(c)<32 or c=='\\' or ord(c)==127 for c in value):
        raise ValueError(label+' must be bounded literal text without control/escape codes')
    value.encode('utf-8','strict')
    return value


def events_for(root):
    from vxace_python_mutator import RubyObject, RubyHash, RubyString
    table_for(root)
    events=root.get('events')
    if not isinstance(events,RubyHash) or events.default is not None or len(events.pairs)>999:
        raise ValueError('Native bounded event hash with nil default required')
    seen=set();owners=set()
    for key,event in events.pairs:
        integer(key,'event hash ID',1,999)
        if key in seen or id(event) in owners or not isinstance(event,RubyObject) or event.cls!='RPG::Event' or type(event.get('id')) is not int or event.get('id')!=key:
            raise ValueError('Existing map event identities are ambiguous')
        if not isinstance(event.get('name'),RubyString):raise ValueError('Existing event name is opaque')
        integer(event.get('x'),'existing event x',0,root.get('width')-1)
        integer(event.get('y'),'existing event y',0,root.get('height')-1)
        seen.add(key);owners.add(id(event))
    return events


def template(root,template_id,blank_list=True):
    from vxace_python_mutator import RubyString
    events=events_for(root);integer(template_id,'template event ID',1,999)
    selected=next((event for key,event in events.pairs if key==template_id),None)
    event=exact(selected,'RPG::Event',EVENT_FIELDS)
    name=event.get('name')
    if not isinstance(name,RubyString) or name.ivars!={'E':True}:raise ValueError('Native UTF-8 event name required')
    name.data.decode('utf-8','strict')
    integer(event.get('x'),'template x',0,root.get('width')-1);integer(event.get('y'),'template y',0,root.get('height')-1)
    pages=event.get('pages')
    if not isinstance(pages,list) or len(pages)!=1:raise ValueError('Select a one-page blank stationary event template')
    page=exact(pages[0],'RPG::Event::Page',PAGE_FIELDS)
    for key in ('walk_anime','step_anime','direction_fix','through'):
        if type(page.get(key)) is not bool:raise ValueError('Native page flags required')
    if type(page.get('trigger')) is not int or page.get('trigger')!=0 or type(page.get('move_type')) is not int or page.get('move_type')!=0:
        raise ValueError('Template must be stationary and action-button triggered')
    integer(page.get('move_speed'),'move speed',1,6);integer(page.get('move_frequency'),'move frequency',1,5)
    integer(page.get('priority_type'),'priority',0,2)
    condition=exact(page.get('condition'),'RPG::Event::Page::Condition',CONDITION_FLAGS|CONDITION_INTS|{'self_switch_ch'})
    if any(type(condition.get(key)) is not bool or condition.get(key) for key in CONDITION_FLAGS):raise ValueError('Template conditions must all be disabled')
    for key in CONDITION_INTS:integer(condition.get(key),key,0 if key=='variable_value' else 1,2**31-1)
    ch=condition.get('self_switch_ch')
    if not isinstance(ch,RubyString) or ch.ivars not in ({},{'E':True},{'E':False}) or ch.data not in (b'A',b'B',b'C',b'D'):raise ValueError('Native self-switch letter required')
    graphic=exact(page.get('graphic'),'RPG::Event::Page::Graphic',GRAPHIC_FIELDS)
    empty=graphic.get('character_name')
    if type(graphic.get('tile_id')) is not int or graphic.get('tile_id')!=0 or not isinstance(empty,RubyString) or empty.data or empty.ivars not in ({},{'E':True},{'E':False}):
        raise ValueError('Only blank native graphics are enabled for new dialogue events')
    integer(graphic.get('character_index'),'character index',0,7);integer(graphic.get('pattern'),'pattern',0,2)
    if type(graphic.get('direction')) is not int or graphic.get('direction') not in (2,4,6,8):raise ValueError('Native graphic direction required')
    route=exact(page.get('move_route'),'RPG::MoveRoute',{'repeat','skippable','wait','list'})
    if any(type(route.get(key)) is not bool for key in ('repeat','skippable','wait')):raise ValueError('Native route flags required')
    route_list=route.get('list')
    if not isinstance(route_list,list) or len(route_list)!=1:raise ValueError('Template route must be empty')
    command=exact(route_list[0],'RPG::MoveCommand',{'code','parameters'})
    if type(command.get('code')) is not int or command.get('code')!=0 or command.get('parameters')!=[]:raise ValueError('Template route terminator required')
    if not blank_list:return event
    commands=page.get('list')
    if not isinstance(commands,list) or len(commands)!=1:raise ValueError('Template event command list must be empty')
    command=exact(commands[0],'RPG::EventCommand',{'code','indent','parameters'})
    if any(type(command.get(key)) is not int or command.get(key)!=0 for key in ('code','indent')) or command.get('parameters')!=[]:
        raise ValueError('Template native event terminator required')
    return event


def snapshot(root,template_id):
    events=events_for(root);selected=template(root,template_id)
    return {'version':VERSION,'map_sha256':digest(root),'template_sha256':digest(selected),
            'template_id':template_id,'next_event_id':max((key for key,_ in events.pairs),default=0)+1,
            'event_count':len(events.pairs),'width':root.get('width'),'height':root.get('height'),
            'occupied_cells':[{'x':e.get('x'),'y':e.get('y'),'event_id':key} for key,e in events.pairs],
            'template_priority':selected.get('pages')[0].get('priority_type'),
            'limits':['One blank-graphic stationary literal-dialogue event; no copied logic, conditions, routes or assets.',
                      'Next maximum ID only; review runtime-created IDs, coordinate consumers and native action-button access.']}


def new_event(root,mutation,project=None,rtp=None):
    from vxace_python_mutator import RubyString, RubyObject, convert, marshal_rb
    schema(mutation)
    for field in ('expected_map_sha256','expected_template_sha256'):
        if not isinstance(mutation[field],str) or not re.fullmatch('[a-f0-9]{64}',mutation[field]):raise ValueError('Exact native map/template SHA required')
    selected=template(root,mutation['template_id']);events=events_for(root)
    identifier=integer(mutation['new_id'],'new event ID',1,999)
    if identifier!=max((key for key,_ in events.pairs),default=0)+1:raise ValueError('Append at the next maximum event ID; never reuse holes')
    if mutation['expected_map_sha256']!=digest(root) or mutation['expected_template_sha256']!=digest(selected):raise ValueError('Native map/template is stale')
    name=text(mutation['name'],'new event name',100)
    for _,event in events.pairs:
        if event.get('name').data.decode('utf-8','strict')==name:raise ValueError('New event name must be unique')
    x=integer(mutation['x'],'new event x',0,root.get('width')-1);y=integer(mutation['y'],'new event y',0,root.get('height')-1)
    if any(event.get('x')==x and event.get('y')==y for _,event in events.pairs):raise ValueError('New event cell must be unoccupied by existing events')
    lines=mutation['text']
    if not isinstance(lines,list) or not 1<=len(lines)<=4:raise ValueError('Dialogue requires one to four literal lines')
    lines=[text(line,'dialogue line',500,True) for line in lines]
    if not any(lines):raise ValueError('Dialogue must contain text')
    event=marshal_rb.load(marshal_rb.dump(selected))
    event.set('id',identifier);event.set('name',convert(name,selected.get('name')));event.set('x',x);event.set('y',y)
    def command(code,parameters):return RubyObject('RPG::EventCommand',{'@code':code,'@indent':0,'@parameters':parameters})
    event.get('pages')[0].set('list',[command(101,[RubyString(b'',{'E':True}),0,0,2])]+[command(401,[RubyString(line.encode('utf-8'),{'E':True})]) for line in lines]+[command(0,[])])
    if 'graphic' in mutation:
        from vxace_character_graphics import set_graphic
        set_graphic(event.get('pages')[0],mutation['graphic'],mutation['expected_asset'],project,rtp)
    return event


def apply(root,mutation,project=None,rtp=None):
    from vxace_python_mutator import RubyHash
    added=new_event(root,mutation,project,rtp);events=events_for(root)
    root.set('events',RubyHash([*events.pairs,(mutation['new_id'],added)],default=None))


def verify_transition(before,after,mutation,project=None,rtp=None):
    from vxace_python_mutator import RubyHash, RubyObject
    old=events_for(before);new=events_for(after)
    if len(new.pairs)!=len(old.pairs)+1 or digest(RubyHash(new.pairs[:-1],default=None))!=digest(old):raise ValueError('Candidate changed old event hash entries/order/bytes')
    if new.pairs[-1][0]!=mutation['new_id'] or digest(new.pairs[-1][1])!=digest(new_event(before,mutation,project,rtp)):raise ValueError('Candidate differs from approved dialogue event')
    def unrelated(root):return digest(RubyObject(root.cls,{key:value for key,value in root.ivars.items() if key!='@events'}))
    if unrelated(before)!=unrelated(after):raise ValueError('Candidate changed unrelated map fields or unknown aliases')


def indexed_snapshot(data,project,map_id,template_id,graphic=None,rtp=None):
    from vxace_python_mutator import load, RubyObject, RubyString
    integer(map_id,'map ID',1,999999)
    root,_=load(unlinked(Path(project)/f'Data/Map{map_id:03d}.rvdata2'))
    indexed=data.json(f'maps/map-{map_id:03d}.json')
    events=events_for(root);selected=template(root,template_id)
    def plain(value):
        if isinstance(value,RubyString):return value.data.decode('utf-8','strict')
        if isinstance(value,RubyObject):return {'__class__':value.cls,**{key[1:]:plain(item) for key,item in value.ivars.items()}}
        if isinstance(value,list):return [plain(item) for item in value]
        if value is None or type(value) in (int,bool):return value
        raise ValueError('Opaque selected template value')
    if not isinstance(indexed,dict) or indexed.get('__class__')!='RPG::Map' or indexed.get('width')!=root.get('width') or indexed.get('height')!=root.get('height'):
        raise ValueError('Native/indexed map dimensions disagree')
    table=table_for(root)
    if indexed.get('data')!={'__class__':'Table','dimensions':3,'xsize':table.xsize,'ysize':table.ysize,'zsize':4,'data':list(table.data)}:
        raise ValueError('Native/indexed map Table disagrees')
    indexed_events=indexed.get('events')
    if not isinstance(indexed_events,dict) or set(indexed_events)!={str(key) for key,_ in events.pairs} or indexed_events.get(str(template_id))!=plain(selected):
        raise ValueError('Native/indexed event identities or selected template disagree')
    for key,event in events.pairs:
        observed=indexed_events[str(key)]
        if not isinstance(observed,dict) or any(observed.get(field)!=plain(event.get(field)) for field in ('id','name','x','y')):
            raise ValueError('Native/indexed existing event identity/position disagrees')
    result={'map_id':map_id,**snapshot(root,template_id)}
    if graphic is not None:
        from vxace_character_graphics import binding
        result.update(proposed_graphic=graphic,asset=binding(project,rtp,graphic))
        result['limits'][0]='Blank native template, stationary literal dialogue and a separately bound proposed character graphic only.'
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('index');parser.add_argument('--project',required=True)
    parser.add_argument('--map',dest='map_id',type=int,required=True);parser.add_argument('--template-event',type=int,required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--character');parser.add_argument('--character-index',type=int);parser.add_argument('--direction',type=int,default=2);parser.add_argument('--pattern',type=int,default=1);parser.add_argument('--rtp')
    args=parser.parse_args(argv)
    try:
        project=unlinked(args.project)
        if project.is_file() and project.suffix.lower()=='.rvproj2':project=project.parent
        if (args.character is None)!=(args.character_index is None):raise ValueError('Character name/index must be supplied together')
        rtp=unlinked(args.rtp) if args.rtp else None
        output=unlinked(args.output)
        if rtp is not None and (output==rtp or rtp in output.parents):raise ValueError('Snapshot output must be outside read-only RTP')
        graphic={'character_name':args.character,'character_index':args.character_index,'direction':args.direction,'pattern':args.pattern} if args.character is not None else None
        if graphic is None and (args.rtp or args.direction!=2 or args.pattern!=1):raise ValueError('Graphic-only options require a selected character')
        result=execute(args.index,project,output,lambda data:indexed_snapshot(data,project,args.map_id,args.template_event,graphic,rtp),'map-event-snapshot')
    except Exception as error:print('Event snapshot refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({'version':VERSION,'next_event_id':result['next_event_id']}));return 0


if __name__=='__main__':raise SystemExit(main())
