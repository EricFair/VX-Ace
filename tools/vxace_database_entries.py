#!/usr/bin/env python3
"""Verified native Items snapshots and narrow append-only key-item construction."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from vxace_index_query import execute, unlinked

VERSION = '0.20.0'
ITEM_INTS = {'id','icon_index','price','scope','occasion','animation_id','speed',
             'success_rate','hit_type','itype_id','repeats','tp_gain'}
ITEM_TEXT = {'name','description','note'}
ITEM_FIELDS = ITEM_INTS | ITEM_TEXT | {'consumable','features','effects','damage'}
DAMAGE_FIELDS = {'type','element_id','formula','variance','critical'}


def integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(label + ' outside integer bounds')
    return value


def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def item_array(root):
    from vxace_python_mutator import RubyObject
    if not isinstance(root,list) or not 2 <= len(root) <= 1000 or root[0] is not None:
        raise ValueError('Expected native Items array with nil slot zero; supported array limit is 1000')
    for number,item in enumerate(root[1:],1):
        if not isinstance(item,RubyObject) or item.cls!='RPG::Item' or type(item.get('id')) is not int or item.get('id')!=number:
            raise ValueError('Every existing item must have its exact native array-slot ID')
    return root


def template(root, template_id):
    from vxace_python_mutator import RubyObject, RubyString
    item_array(root)
    identifier=integer(template_id,'template ID',1,len(root)-1)
    item=root[identifier]
    if set(item.ivars)!={'@'+key for key in ITEM_FIELDS}:
        raise ValueError('Selected item template has unknown or missing native fields')
    if any(type(item.get(key)) is not int for key in ITEM_INTS) or any(not isinstance(item.get(key),RubyString) for key in ITEM_TEXT):
        raise ValueError('Selected item template field types are unsupported')
    if type(item.get('consumable')) is not bool or item.get('features')!=[]:
        raise ValueError('Selected template requires native consumable flag and empty item features')
    effects=item.get('effects')
    if not isinstance(effects,list) or len(effects)>256:
        raise ValueError('Selected template effects are opaque or exceed budget')
    for effect in effects:
        if not isinstance(effect,RubyObject) or effect.cls!='RPG::UsableItem::Effect' or set(effect.ivars)!={'@code','@data_id','@value1','@value2'}:
            raise ValueError('Selected template has unknown effect schema')
        if any(type(effect.get(k)) is not int for k in ('code','data_id')) or any(type(effect.get(k)) is bool or not isinstance(effect.get(k),(int,float)) for k in ('value1','value2')):
            raise ValueError('Selected effect field types are unsupported')
        if any(not math.isfinite(effect.get(k)) for k in ('value1','value2')):
            raise ValueError('Non-finite native effect values are unsupported')
    damage=item.get('damage')
    if not isinstance(damage,RubyObject) or damage.cls!='RPG::UsableItem::Damage' or set(damage.ivars)!={'@'+key for key in DAMAGE_FIELDS}:
        raise ValueError('Selected template has unknown damage schema')
    if any(type(damage.get(k)) is not int for k in ('type','element_id','variance')) or not isinstance(damage.get('formula'),RubyString) or type(damage.get('critical')) is not bool:
        raise ValueError('Selected damage field types are unsupported')
    if damage.get('type')!=0:
        raise ValueError('Select an existing native no-damage item template')
    return item


def snapshot(root, template_id):
    selected=template(root,template_id)
    return {'array_sha256':digest(root),'template_sha256':digest(selected),
            'template_id':template_id,'next_item_id':len(root),'existing_items':len(root)-1,
            'append_slot_supported':len(root)<=999,
            'template_name':selected.get('name').data.decode('utf-8','strict'),
            'scope':'append-only inert native key item; no deletion/reuse/reorder or arbitrary object creation'}


def new_key_item(root, mutation):
    from vxace_python_mutator import RubyString, convert, marshal_rb
    fields={'action','template_id','new_id','expected_array_sha256','expected_template_sha256','name','description'}
    if not isinstance(mutation,dict) or set(mutation)!=fields or mutation.get('action')!='append_key_item':
        raise ValueError('Only the exact append_key_item schema is supported')
    item_array(root)
    new_id=integer(mutation['new_id'],'new key item ID',1,999)
    if new_id!=len(root):
        raise ValueError('New item ID must append at the exact next array slot')
    selected=template(root,mutation['template_id'])
    if mutation['expected_array_sha256']!=digest(root) or mutation['expected_template_sha256']!=digest(selected):
        raise ValueError('Item array/template fingerprint is stale')
    name,description=mutation['name'],mutation['description']
    if not isinstance(name,str) or not 1<=len(name)<=100 or any(ord(c)<32 for c in name):
        raise ValueError('New key item name must be 1..100 characters without control codes')
    if not isinstance(description,str) or len(description)>1000 or any(ord(c)<32 and c!='\n' for c in description):
        raise ValueError('New key item description exceeds the supported text range')
    item=marshal_rb.load(marshal_rb.dump(selected))
    values={'id':new_id,'name':name,'description':description,'note':'','icon_index':0,
            'itype_id':2,'scope':0,'occasion':3,'consumable':False,'price':0,
            'animation_id':0,'speed':0,'success_rate':100,'hit_type':0,'repeats':1,'tp_gain':0}
    for key,value in values.items():
        item.set(key,convert(value,item.get(key)) if isinstance(item.get(key),RubyString) else value)
    item.set('effects',[]);item.set('features',[])
    damage=item.get('damage')
    for key,value in {'type':0,'element_id':0,'formula':'0','variance':0,'critical':False}.items():
        damage.set(key,convert(value,damage.get(key)) if isinstance(damage.get(key),RubyString) else value)
    return item


def apply(root, mutation):
    item=new_key_item(root,mutation)
    root.append(item)


def verify_transition(before,after,mutation):
    item_array(before);item_array(after)
    if len(after)!=len(before)+1 or digest(after[:-1])!=digest(before):
        raise ValueError('Key-item candidate changed existing entries or array shape')
    if digest(after[-1])!=digest(new_key_item(before,mutation)):
        raise ValueError('Key-item candidate differs from the approved inert native record')


def indexed_snapshot(data,project,template_id):
    from vxace_python_mutator import load
    root,_=load(unlinked(Path(project)/'Data/Items.rvdata2'))
    result=snapshot(root,template_id)
    indexed=data.json('database/items.json')
    if not isinstance(indexed,list) or len(indexed)!=len(root) or indexed[0] is not None:
        raise ValueError('Indexed/native Items array sizes disagree')
    for number,item in enumerate(indexed[1:],1):
        if not isinstance(item,dict) or item.get('__class__')!='RPG::Item' or type(item.get('id')) is not int or item['id']!=number:
            raise ValueError('Indexed/native item identities disagree')
    if indexed[template_id].get('name')!=result['template_name']:
        raise ValueError('Indexed/native template names disagree')
    return {'version':VERSION,'table':'items',**result,
            'limits':['Only existing native no-damage templates with supported exact schema are admitted.',
                      'A new static ID can still collide with runtime-created IDs or custom consumers; review scripts/events/notes.',
                      'Snapshot is not mutation permission; use the reviewed Python disposable-copy workflow and native inventory/save tests.']}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index');ap.add_argument('--project',required=True);ap.add_argument('--output',required=True)
    ap.add_argument('--template-item',type=int,required=True)
    args=ap.parse_args(argv)
    try:
        project=unlinked(args.project)
        if project.is_file() and project.suffix.lower()=='.rvproj2':project=project.parent
        result=execute(args.index,project,args.output,lambda data:indexed_snapshot(data,project,args.template_item),'item-entry-snapshot')
        (Path(args.output)/'item-entry-snapshot.md').write_text('# VX Ace key-item append preconditions\n\nRead-only; no mutation authorized.\n\n```json\n'+json.dumps(result,indent=2)+'\n```\n',encoding='utf-8')
        print(json.dumps({'status':'ok','template_id':args.template_item,'next_item_id':result['next_item_id']}))
        return 0
    except Exception as exc:
        print('Item entry snapshot refused: '+str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
