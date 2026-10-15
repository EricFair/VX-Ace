#!/usr/bin/env python3
"""Native one-time constant map-event rewards; read-only evidence and copy guards."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys
from vxace_index_query import execute,unlinked
from vxace_map_regions import integer
from vxace_map_events import exact,CONDITION_FLAGS,CONDITION_INTS,PAGE_FIELDS,text

VERSION='1.0.0'
GUARD_FIELDS={'expected_pages_sha256','self_switch','expected_items_sha256'}


def has_rewards(mutation):
    rows=mutation.get('commands',[]) if isinstance(mutation,dict) else []
    return isinstance(rows,list) and any(isinstance(row,dict) and type(row.get('code')) is int and row['code'] in (125,126) for row in rows)


def reward_rows(rows):
    if not isinstance(rows,list) or not 2<=len(rows)<=500:raise ValueError('Bounded reward command batch required')
    found={};letter=None
    for number,row in enumerate(rows):
        if not isinstance(row,dict) or set(row)!={'code','indent','parameters'} or type(row['code']) is not int or type(row['indent']) is not int or row['indent']!=0 or not isinstance(row['parameters'],list):
            raise ValueError('Exact root native reward rows required')
        code,p=row['code'],row['parameters']
        if code==125:
            if 'gold' in found or len(p)!=3 or any(type(value) is not int for value in p) or p[:2]!=[0,0]:raise ValueError('One constant positive gold addition only')
            found['gold']=integer(p[2],'gold addition',1,99999999)
        elif code==126:
            if 'item_id' in found or len(p)!=4 or any(type(value) is not int for value in p) or p[1:3]!=[0,0]:raise ValueError('One constant positive item addition only')
            found['item_id']=integer(p[0],'reward item ID',1,999);found['quantity']=integer(p[3],'item quantity',1,99)
        elif code==123:
            if number!=len(rows)-1 or len(p)!=2 or p[0] not in ('A','B','C','D') or type(p[1]) is not int or p[1]!=0:raise ValueError('Final command must enable the reviewed self switch')
            letter=p[0]
        elif code==101:
            if p!=['',0,0,2] or any(type(value) is not int for value in p[1:]):raise ValueError('Reward messages use a fixed asset-free native header')
        elif code in (401,108,408):
            if len(p)!=1:raise ValueError('Literal reward message/comment required')
            text(p[0],'reward text',500,True)
        else:raise ValueError('Command outside the one-time reward subset')
    if not found or letter is None:raise ValueError('Reward and final self-switch gate required')
    from vxace_event_structure import validate_list,new_commands
    from vxace_python_mutator import convert,RubyObject
    # Group and native-type validation remain shared with the structural writer.
    commands=new_commands(rows,convert,'map')
    validate_list(commands+[RubyObject('RPG::EventCommand',{'@code':0,'@indent':0,'@parameters':[]})])
    return {'self_switch':letter,**found}


def guard_pages(root,event_id):
    from vxace_event_structure import owner_for,validate_list,command_rows,fingerprint
    from vxace_python_mutator import object_by_id,RubyString
    integer(event_id,'reward event ID',1,999)
    owner=owner_for(root,{'scope':'map','event_id':event_id},object_by_id)
    pages=owner.get('pages')
    if not isinstance(pages,list) or len(pages)!=2:raise ValueError('One-time rewards require exactly two existing native pages')
    conditions=[]
    for page in pages:
        exact(page,'RPG::Event::Page',PAGE_FIELDS)
        if type(page.get('trigger')) is not int or page.get('trigger')!=0 or type(page.get('move_type')) is not int or page.get('move_type')!=0:
            raise ValueError('Reward pages must be stationary action-button pages')
        condition=exact(page.get('condition'),'RPG::Event::Page::Condition',CONDITION_FLAGS|CONDITION_INTS|{'self_switch_ch'})
        if any(type(condition.get(key)) is not bool for key in CONDITION_FLAGS):raise ValueError('Native reward condition flags required')
        for key in CONDITION_INTS:integer(condition.get(key),key,0 if key=='variable_value' else 1,2**31-1)
        ch=condition.get('self_switch_ch')
        if not isinstance(ch,RubyString) or ch.data not in (b'A',b'B',b'C',b'D') or ch.ivars not in ({},{'E':True},{'E':False}):raise ValueError('Native reward self switch required')
        conditions.append(condition)
        validate_list(page.get('list'))
    if any(conditions[0].get(key) for key in CONDITION_FLAGS) or any(conditions[1].get(key)!=(key=='self_switch_valid') for key in CONDITION_FLAGS):
        raise ValueError('Lower page must be unconditional; higher page must have only the reviewed self-switch condition')
    initial=pages[0].get('list')
    if len(initial)!=1:raise ValueError('Reward insertion requires a blank lower command list')
    exact(initial[0],'RPG::EventCommand',{'code','indent','parameters'})
    if (initial[0].get('code'),initial[0].get('indent'),initial[0].get('parameters'))!=(0,0,[]):raise ValueError('Blank native root terminator required')
    followup=command_rows(pages[1].get('list'))
    from vxace_python_mutator import convert
    from vxace_event_structure import new_commands
    if any(row['code'] not in (0,101,401,108,408) for row in followup):raise ValueError('Higher page may contain only literal text/comments and the final terminator')
    for row in followup:
        if row['code']==101 and row['parameters']!=['',0,0,2]:raise ValueError('Higher page uses an unsupported message header')
        if row['code'] in (401,108,408):
            if len(row['parameters'])!=1:raise ValueError('Higher page text is opaque')
            text(row['parameters'][0],'follow-up text',500,True)
    new_commands(followup,convert,'map',terminal=True)
    return pages,{'self_switch':conditions[1].get('self_switch_ch').data.decode('ascii'),
                  'expected_pages_sha256':fingerprint(pages),'expected_list_sha256':fingerprint(initial)}


def item_context(mutation,source_path):
    from vxace_python_mutator import load,RubyObject,RubyString
    from vxace_event_structure import fingerprint
    if source_path is None:raise ValueError('Native reward writes require an actual project map path')
    source=unlinked(source_path)
    if source.parent.name!='Data' or not re.fullmatch(r'Map\d{3,6}\.rvdata2',source.name) or not source.is_file():raise ValueError('Canonical native map source context required')
    rows=reward_rows(mutation.get('commands'));guard=mutation.get('reward_guard')
    if not isinstance(guard,dict) or set(guard)!=GUARD_FIELDS:raise ValueError('Exact reward guard fields required')
    if 'item_id' not in rows:
        if guard['expected_items_sha256'] is not None:raise ValueError('Gold-only rewards must not claim an item binding')
        return rows,[]
    items,_=load(unlinked(source.parent/'Items.rvdata2'))
    if not isinstance(items,list) or not 2<=len(items)<=1000 or items[0] is not None or guard['expected_items_sha256']!=fingerprint(items):raise ValueError('Native reward Items array binding is stale or unsupported')
    identifier=rows['item_id']
    if identifier>=len(items):raise ValueError('Reward item is absent from actual native Items')
    item=items[identifier]
    if not isinstance(item,RubyObject) or item.cls!='RPG::Item' or type(item.get('id')) is not int or item.get('id')!=identifier or not isinstance(item.get('name'),RubyString):raise ValueError('Reward item native identity is ambiguous')
    name=item.get('name').data.decode('utf-8','strict')
    if not name:raise ValueError('Select a named native reward item')
    return rows,[{'id':identifier,'name':name,'quantity':rows['quantity'],'native_sha256':fingerprint(item)}]


def validate(root,mutation,source_path):
    if mutation.get('scope')!='map' or mutation.get('action')!='insert_commands' or type(mutation.get('page')) is not int or mutation['page']!=1 or type(mutation.get('command_index')) is not int or mutation['command_index']!=0:
        raise ValueError('Rewards only insert into the blank lower map page at root index zero')
    rows,items=item_context(mutation,source_path)
    pages,observed=guard_pages(root,mutation.get('event_id'));guard=mutation['reward_guard']
    if guard['expected_pages_sha256']!=observed['expected_pages_sha256'] or guard['self_switch']!=observed['self_switch'] or rows['self_switch']!=observed['self_switch']:
        raise ValueError('Reward higher-page/self-switch guard is stale or inconsistent')
    return {'guard':observed,'rewards':rows,'items':items}


def verify_transition(before,after,mutation,source_path):
    from vxace_python_mutator import marshal_rb,convert,object_by_id
    from vxace_event_structure import apply
    expected=marshal_rb.load(marshal_rb.dump(before))
    apply(expected,mutation,convert,object_by_id,source_path=source_path)
    if marshal_rb.dump(expected)!=marshal_rb.dump(after):raise ValueError('Reward candidate changed unapproved native map bytes/fields')


def snapshot(data,project,map_id,event_id,item_id=None):
    from vxace_python_mutator import load,RubyObject,RubyString
    from vxace_event_structure import fingerprint,command_rows
    integer(map_id,'map ID',1,999999);integer(event_id,'event ID',1,999)
    source=unlinked(Path(project)/f'Data/Map{map_id:03d}.rvdata2');root,_=load(source)
    pages,guard=guard_pages(root,event_id)
    indexed=data.json(f'maps/map-{map_id:03d}.json')
    owner=indexed.get('events',{}).get(str(event_id)) if isinstance(indexed,dict) else None
    if not isinstance(owner,dict) or type(owner.get('id')) is not int or owner['id']!=event_id or not isinstance(owner.get('pages'),list) or len(owner['pages'])!=2:raise ValueError('Indexed reward page identity disagrees')
    for number,page in enumerate(pages):
        observed=owner['pages'][number];condition=page.get('condition')
        expected={'__class__':condition.cls,**{key[1:]:value.data.decode('ascii') if isinstance(value,RubyString) else value for key,value in condition.ivars.items()}}
        commands=observed.get('list')
        if not isinstance(commands,list) or any(not isinstance(command,dict) or set(command)!={'__class__','code','indent','parameters'} or command['__class__']!='RPG::EventCommand' for command in commands):raise ValueError('Indexed reward command schema disagrees')
        rows=[{key:command[key] for key in ('code','indent','parameters')} for command in commands]
        if type(observed.get('trigger')) is not int or observed['trigger']!=0 or type(observed.get('move_type')) is not int or observed['move_type']!=0 or observed.get('condition')!=expected or rows!=command_rows(page.get('list')):raise ValueError('Indexed/native reward conditions or commands disagree')
    items_hash=None;selected=None
    if item_id is not None:
        integer(item_id,'reward item ID',1,999);items,_=load(unlinked(source.parent/'Items.rvdata2'))
        items_hash=fingerprint(items)
        mutation={'commands':[{'code':126,'indent':0,'parameters':[item_id,0,0,1]},{'code':123,'indent':0,'parameters':[guard['self_switch'],0]}],
                  'reward_guard':{'expected_pages_sha256':guard['expected_pages_sha256'],'self_switch':guard['self_switch'],'expected_items_sha256':items_hash}}
        _,selected=item_context(mutation,source)
        native=data.json('database/items.json')
        if not isinstance(native,list) or len(native)!=len(items) or not isinstance(native[item_id],dict) or native[item_id].get('__class__')!='RPG::Item' or native[item_id].get('id')!=item_id or native[item_id].get('name')!=selected[0]['name']:
            raise ValueError('Indexed/native reward item disagrees')
    return {'version':VERSION,'map_id':map_id,'event_id':event_id,'page':1,'command_index':0,
            'expected_list_sha256':guard.pop('expected_list_sha256'),
            'reward_guard':{**guard,'expected_items_sha256':items_hash},'item_evidence':selected,
            'limits':['One constant gold and/or item addition, followed by enabling the exact higher-page self switch.',
                      'Native inventory caps/custom gain hooks and existing save/self-switch state require review; no save editing.']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('index');parser.add_argument('--project',required=True)
    parser.add_argument('--map',dest='map_id',type=int,required=True);parser.add_argument('--event',dest='event_id',type=int,required=True)
    parser.add_argument('--item',dest='item_id',type=int);parser.add_argument('--output',required=True);args=parser.parse_args(argv)
    try:
        project=unlinked(args.project)
        if project.is_file() and project.suffix.lower()=='.rvproj2':project=project.parent
        result=execute(args.index,project,args.output,lambda data:snapshot(data,project,args.map_id,args.event_id,args.item_id),'event-reward-snapshot')
    except Exception as error:print('Reward snapshot refused: '+str(error),file=sys.stderr);return 2
    print(json.dumps({'version':VERSION,'map_id':args.map_id,'event_id':args.event_id}));return 0


if __name__=='__main__':raise SystemExit(main())
