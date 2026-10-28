#!/usr/bin/env python3
"""Evidence-first dependency impact analysis for VX Ace patch specs."""
from __future__ import annotations
import argparse, json
from pathlib import Path

VERSION = "1.0.0"
DB_FILES = {
    "actors":"actors.json","classes":"classes.json","skills":"skills.json","items":"items.json",
    "weapons":"weapons.json","armors":"armors.json","enemies":"enemies.json","troops":"troops.json",
    "states":"states.json","animations":"animations.json","tilesets":"tilesets.json",
    "common-events":"common-events.json","common_events":"common-events.json","system":"system.json",
}

def load(path, default=None):
    try:
        with Path(path).open("r", encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError:
        return default

def dump(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

def graph_neighbors(graph, node_id):
    nodes={n.get("id"):n for n in graph.get("nodes",[]) if isinstance(n,dict)}
    out=[]
    for edge in graph.get("edges",[]):
        if edge.get("from")==node_id:
            out.append({"direction":"outgoing","relation":edge.get("relation"),"node":nodes.get(edge.get("to"),{"id":edge.get("to")})})
        elif edge.get("to")==node_id:
            out.append({"direction":"incoming","relation":edge.get("relation"),"node":nodes.get(edge.get("from"),{"id":edge.get("from")})})
    return out

def map_page(maps, mid, eid, page):
    m=next((x for x in maps if x.get("map_id")==mid),None)
    if not m: return None
    e=next((x for x in m.get("events",[]) if x.get("event_id")==eid),None)
    if not e: return None
    p=next((x for x in e.get("pages",[]) if x.get("page")==page),None)
    if not p: return None
    return {"map":{"id":mid,"name":m.get("name","")},"event":{"id":eid,"name":e.get("name","")},"page":p}

def database_object(index, table, obj_id):
    fn=DB_FILES.get(str(table).lower())
    if not fn: return None, f"unsupported database table: {table}"
    data=load(index/"database"/fn)
    if data is None: return None, f"database file missing: {fn}"
    candidates=[]
    if isinstance(data,list): candidates=[x for x in data if isinstance(x,dict)]
    elif isinstance(data,dict): candidates=[x for x in data.values() if isinstance(x,dict)]
    for obj in candidates:
        try: oid=int(obj.get("id"))
        except Exception: continue
        if oid==int(obj_id):
            return {"table":table,"id":oid,"name":obj.get("name","")}, None
    return None, f"database object not found: {table} #{obj_id}"

def script_impact(index, scripts, change):
    path=change.get("script_path")
    item=next((x for x in scripts.get("scripts",[]) if x.get("path")==path),None)
    if not item:
        raise ValueError(f"script target not found in codex: {path}")
    collisions=item.get("collision_candidates",[])
    severity="high" if any(x.get("severity")=="high" for x in collisions) or item.get("save_hooks") else ("medium" if collisions else "low")
    return {
        "kind":"script","target":{"path":path,"index":item.get("index"),"name":item.get("name","")},
        "severity":severity,"classes":item.get("classes",[]),"methods":item.get("methods",[]),
        "aliases":item.get("aliases",[]),"save_hooks":item.get("save_hooks",[]),
        "collision_candidates":collisions,"imported_reads":item.get("imported_reads",[]),"imported_sets":item.get("imported_sets",[]),
        "limitations":["Static ownership/collision evidence may miss metaprogramming and dynamic dispatch."],
    }

def event_impact(graph, maps, change, index=None):
    loc=change.get("locator") or {}
    mutation=change.get('mutation') or {}
    if mutation.get('action')=='insert_page':
        loc=dict(loc); loc['page']=mutation.get('template_page')
    if all(k in loc for k in ("map_id","event_id","page")):
        mid,eid,page=(int(loc[k]) for k in ("map_id","event_id","page"))
        exact=map_page(maps,mid,eid,page)
        if not exact: raise ValueError(f"map event page not found: map {mid}, event {eid}, page {page}")
        node=f"map:{mid}:event:{eid}:page:{page}"
        result={"kind":"event","scope":"map","target":exact,"graph_node":node,"dependencies":graph_neighbors(graph,node),"severity":"high" if mutation.get('action') in {'insert_page','delete_page'} else "medium",'structural_action':mutation.get('action'),'requested_locator':change.get('locator')}
        rows=mutation.get('commands',[])
        if isinstance(rows,list) and any(isinstance(row,dict) and type(row.get('code')) is int and row['code'] in (125,126) for row in rows):
            if index is None:raise ValueError('Reward impact requires the complete source index')
            result.update(severity='high',one_time_rewards=reward_impact(index,change))
        if isinstance(rows,list) and any(isinstance(row,dict) and type(row.get('code')) is int and row['code']==201 for row in rows):
            if index is None:raise ValueError('Transfer impact requires a complete source index')
            result.update(severity='high',direct_transfer=transfer_impact(index,change))
        return result
    if "common_event_id" in loc:
        cid=int(loc["common_event_id"]); node=f"common_event:{cid}"
        nodes={n.get("id"):n for n in graph.get("nodes",[]) if isinstance(n,dict)}
        target=nodes.get(node)
        if not target and index is not None: target,error=database_object(index,'common-events',cid)
        if not target: raise ValueError(f"common event not found in project evidence: {cid}")
        return {"kind":"event","scope":"common_event","target":target,"graph_node":node,"dependencies":graph_neighbors(graph,node),"severity":"medium"}
    if "troop_id" in loc:
        tid=int(loc["troop_id"]); node=f"troop:{tid}"
        nodes={n.get("id"):n for n in graph.get("nodes",[]) if isinstance(n,dict)}
        target=nodes.get(node)
        if not target and index is not None: target,error=database_object(index,'troops',tid)
        if not target: raise ValueError(f"troop not found in project evidence: {tid}")
        return {"kind":"event","scope":"troop","target":target,"graph_node":node,"dependencies":graph_neighbors(graph,node),"severity":"high" if mutation.get('action') in {'insert_page','delete_page'} else "medium",
                "limitations":["Troop page/command dependency extraction is less complete than map-event dependency extraction."]}
    raise ValueError("event locator requires map_id/event_id/page, common_event_id, or troop_id")

def transfer_impact(index,change):
    from vxace_transfers import transfer_rows,GUARD_FIELDS,validate_locator
    from vxace_index_query import Index
    from vxace_search import search
    import re
    loc=change.get('locator');mutation=change.get('mutation')
    validate_locator(loc)
    if mutation.get('action')!='insert_commands':raise ValueError('Transfer command insertion required')
    target=transfer_rows(mutation.get('commands'));guard=mutation.get('transfer_guard')
    if not isinstance(guard,dict) or set(guard)!=GUARD_FIELDS or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in guard.values()):raise ValueError('Exact native transfer bindings required')
    data=Index(index);native=data.json(f"maps/map-{target['map_id']:03d}.json")
    if target['map_id']==loc['map_id'] or type(native.get('width')) is not int or type(native.get('height')) is not int or target['x']>=native['width'] or target['y']>=native['height']:raise ValueError('Indexed transfer bounds/source disagree')
    mentions=[]
    for marker in ('command_201','reserve_transfer','perform_transfer','setup','DataManager','load_data'):
        found=search(data,query=marker,scopes=('scripts','events'),limit=10)
        mentions.append({'literal':marker,'matches':found['matches'],'evidence':found['hits'],'truncated':found['truncated']})
    data.unchanged()
    return {'destination':target,'guard':guard,'consumer_mentions':mentions,
            'limitations':['Actual native blank-event/destination/tree/inventory/tileset bindings run independently in the Python copy chain.',
                          'Static direct coordinates cannot prove runtime passability, assets, custom loader/transfer hooks or save migration.',
                          'Verify native editor, older-save source-map reconstruction, actual event transfer, movement, saving and process restart.']}


def reward_impact(index,change):
    from vxace_event_rewards import reward_rows,GUARD_FIELDS,integer
    from vxace_index_query import Index
    from vxace_search import search
    import re
    loc=change.get('locator')
    if not isinstance(loc,dict) or set(loc)!={'map_id','event_id','page','command_index'} or type(loc['page']) is not int or loc['page']!=1 or type(loc['command_index']) is not int or loc['command_index']!=0:raise ValueError('Exact lower map-page/root reward locator required')
    integer(loc['map_id'],'reward map ID',1,999);integer(loc['event_id'],'reward event ID',1,999)
    mutation=change['mutation'];rewards=reward_rows(mutation['commands']);guard=mutation.get('reward_guard')
    if not isinstance(guard,dict) or set(guard)!=GUARD_FIELDS or guard['self_switch']!=rewards['self_switch'] or not isinstance(guard['expected_pages_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',guard['expected_pages_sha256']):raise ValueError('Exact reward page/self-switch binding required')
    if 'item_id' in rewards:
        if not isinstance(guard['expected_items_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',guard['expected_items_sha256']):raise ValueError('Exact native Items hash required')
        target,error=database_object(index,'items',rewards['item_id'])
        if error:raise ValueError(error)
    else:
        target=None
        if guard['expected_items_sha256'] is not None:raise ValueError('Gold-only reward cannot claim an item binding')
    data=Index(index);mentions=[]
    for marker in ('gain_gold','gain_item','max_gold','max_item_number','$game_self_switches','conditions_met?'):
        found=search(data,query=marker,scopes=('scripts','events'),limit=10)
        mentions.append({'literal':marker,'matches':found['matches'],'evidence':found['hits'],'truncated':found['truncated']})
    data.unchanged()
    return {'proposed':rewards,'item_target':target,'guard':guard,'consumer_mentions':mentions,
            'limitations':['Actual native two-page/blank-list/Items/hash and candidate preservation checks run separately in the Python copy chain.',
                          'Default native inventory/gold caps can truncate grants while the self switch still completes the reward.',
                          'Other events/scripts/save state can reset or pre-enable a self switch; literal evidence cannot prove global uniqueness.',
                          'Review custom gain/cap/condition/save hooks and test initial reward, repeat interaction, inventory, old save and restart.']}


def database_impact(index, change):
    loc=change.get("locator") or {}
    if "table" not in loc or "id" not in loc: raise ValueError("database locator requires table and id")
    target,err=database_object(index,loc["table"],loc["id"])
    if err: raise ValueError(err)
    return {"kind":"database","target":target,"severity":"medium","dependencies":[],
            "limitations":["Current Project Codex does not yet build full database-object dependency edges; this is a verified direct target only."]}

def region_impact(index, change):
    from vxace_index_query import Index
    from vxace_map_audit import audit
    from vxace_map_regions import integer
    loc=change.get('locator')
    if not isinstance(loc,dict) or set(loc) != {'map_id'}:
        raise ValueError('Region impact requires exact map_id locator')
    mid=integer(loc['map_id'],'map ID',1,999999)
    data=Index(index)
    report=audit(data,mid)
    if report['findings']:
        raise ValueError('Region impact requires a clean selected-map tile audit')
    root=data.json(f'maps/map-{mid:03d}.json')
    from vxace_python_mutator import RubyObject, Table
    from vxace_map_regions import apply as validate_regions
    normalized=Table(root['width'],root['height'],4,dim=3,data=root['data']['data'])
    validate_regions(RubyObject('RPG::Map',{'@width':root['width'],'@height':root['height'],'@data':normalized}),change.get('mutation'))
    encounters=root.get('encounter_list')
    if not isinstance(encounters,list) or len(encounters)>1000:
        raise ValueError('Native encounter list missing/opaque or exceeds budget')
    encounter_rows=[]
    for number, encounter in enumerate(encounters):
        if not isinstance(encounter,dict) or encounter.get('__class__')!='RPG::Map::Encounter':
            raise ValueError('Opaque native encounter entry')
        regions=encounter.get('region_set')
        if not isinstance(regions,list) or len(regions)>256 or any(type(x) is not int or not 0<=x<=255 for x in regions):
            raise ValueError('Opaque encounter region_set')
        encounter_rows.append({'index':number,'troop_id':encounter.get('troop_id'),
                               'weight':encounter.get('weight'),'region_set':regions})
    evidence=[]; mentions=0
    order=data.json('scripts/order.json')
    if not isinstance(order,dict) or not isinstance(order.get('scripts'),list):
        raise ValueError('Ordered script evidence required for region impact')
    if 'script_count' in data.project and data.project['script_count']!=len(order['scripts']):
        raise ValueError('Incomplete script order')
    seen=set()
    for script in order['scripts']:
        if not isinstance(script,dict) or not isinstance(script.get('path'),str) or script['path'] in seen:
            raise ValueError('Opaque/duplicate script order')
        seen.add(script['path'])
        file='scripts/'+script['path']
        for line,text in enumerate(data.text(file).splitlines(),1):
            data.spend()
            if 'region_id' in text or 'region_set' in text:
                mentions+=1
                if len(evidence)<40:
                    evidence.append({'file':file,'line':line,'excerpt':text[:200]})
    data.unchanged()
    return {'kind':'map_region','target':{'map_id':mid,'width':root['width'],'height':root['height']},
            'severity':'high','requested_cells':change.get('mutation',{}).get('cells'),
            'encounters':encounter_rows,'script_region_mentions':mentions,'script_evidence':evidence,
            'script_evidence_truncated':mentions>len(evidence),
            'limitations':['Region changes may change native encounter eligibility; review every region_set and custom region consumer.',
                          'Literal script mentions include definitions/comments and may miss dynamic calls, note tags and external/custom region logic.',
                          'Native old-save map reload and restart-based persistence testing remain required.']}


APPEND_MARKERS = {
    'enemies': ('$data_enemies','enemy_id','Enemy'), 'skills': ('$data_skills','learn_skill','skill_id','use_item'),
    'states': ('$data_states','add_state','remove_state','state_id'), 'weapons': ('$data_weapons','gain_item','equip'),
    'armors': ('$data_armors','gain_item','equip'),
    'troops': ('$data_troops','troop_id','BattleManager.setup','battle_start'),
}


def append_entry_impact(index, change):
    """Impact for append_database_entry; lists what the clone inherits and where the template is referenced."""
    from vxace_index_query import Index
    from vxace_search import search
    from vxace_database_append import integer, table_spec, OVERRIDES, ACTION
    table=change['locator'].get('table')
    cls,fields=table_spec(table)
    mutation=change.get('mutation')
    if not isinstance(mutation,dict) or mutation.get('action')!=ACTION:
        raise ValueError('Expected append_database_entry impact')
    data=Index(index);rows=data.json('database/'+table+'.json')
    if not isinstance(rows,list) or not 2<=len(rows)<=999 or rows[0] is not None:
        raise ValueError('A supported native '+table+' array with append capacity is required')
    for number,row in enumerate(rows[1:],1):
        if not isinstance(row,dict) or row.get('__class__')!=cls or type(row.get('id')) is not int or row['id']!=number:
            raise ValueError('Indexed '+table+' IDs must match native array slots')
    identifier=integer(mutation.get('new_id'),'new ID',1,999)
    template_id=integer(mutation.get('template_id'),'template ID',1,len(rows)-1)
    if identifier!=len(rows):raise ValueError('Append ID must be the next array slot')
    selected=rows[template_id]
    if set(selected)!=(fields|{'__class__'}):
        raise ValueError('Selected indexed template has unknown native fields')
    overrides=mutation.get('overrides')
    if not isinstance(overrides,dict) or any(k not in OVERRIDES[table] for k in overrides):
        raise ValueError('Overrides contain keys outside the supported whitelist')
    inherited={k:selected.get(k) for k in sorted(fields-{'id','note'}) if k not in overrides and not (k=='damage' and any(o.startswith('damage_') for o in overrides))}
    if 'damage' in selected and any(o.startswith('damage_') for o in overrides):
        damage=dict(selected['damage']) if isinstance(selected['damage'],dict) else {}
        for key,name in (('damage_formula','formula'),('damage_variance','variance'),('damage_critical','critical')):
            if key in overrides: damage.pop(name,None)
        inherited['damage (non-overridden parts)']=damage
    references={}
    troops=data.json('database/troops.json')
    troop_info={}
    if table=='troops':
        enemy_rows=data.json('database/enemies.json')
        members=overrides.get('members')
        if not isinstance(enemy_rows,list) or not isinstance(members,list) or not 1<=len(members)<=8:
            raise ValueError('Troop impact requires an indexed Enemies array and 1..8 members')
        used=[]
        for member in members:
            eid=member.get('enemy_id') if isinstance(member,dict) else None
            if type(eid) is not int or not 0<eid<len(enemy_rows) or not isinstance(enemy_rows[eid],dict):
                raise ValueError('Troop member references an enemy missing from the indexed Enemies array')
            used.append({'enemy_id':eid,'enemy':enemy_rows[eid].get('name'),'x':member.get('x'),'y':member.get('y'),'hidden':member.get('hidden')})
        pages=selected.get('pages') if isinstance(selected.get('pages'),list) else []
        troop_info={'template_troop':{'id':template_id,'name':selected.get('name'),'page_count':len(pages),
                                      'member_count':len(selected.get('members') or []),
                                      'members_copied':False,'battle_events_copied':False},
                    'referenced_enemies':used,
                    'enemies_sha256_required':mutation.get('expected_enemies_sha256')}
    if table=='enemies' and isinstance(troops,list):
        references['troops_using_template']=[t.get('id') for t in troops if isinstance(t,dict) and any(isinstance(m,dict) and m.get('enemy_id')==template_id for m in (t.get('members') or []))][:50]
    mentions=[]
    for marker in APPEND_MARKERS[table]:
        result=search(data,query=marker,scopes=('scripts','events'),limit=20)
        mentions.append({'literal':marker,'matches':result['matches'],'evidence':result['hits'],'evidence_truncated':result['truncated']})
    data.unchanged()
    return {'kind':'database_entry','target':{'table':table,'new_id':identifier,'template_id':template_id,'template_name':selected.get('name')},
            'severity':'high','action':ACTION,'overridden_fields':sorted(overrides),
            'inherited_from_template':inherited,'template_note_present':bool(selected.get('note')),
            'new_note_forced_empty':table!='troops','template_references':references,'consumer_mentions':mentions,
            **({'troop':troop_info} if table=='troops' else {}),
            'limitations':['Every inherited field above is copied as-is; features/effects/drops/actions/damage type and element need reviewer approval.',
                          'The template note is not copied; notetag-driven behavior of the template will not exist on the new entry.',
                          'An appended static ID can collide with runtime-created IDs; literal mentions do not prove freedom from dynamic consumers.',
                          'New entries are not added to troops, shops, drop tables, class learnings or encounters automatically.',
                          *(['A new troop is only reachable via Battle Processing events or encounter-list edits done separately; encounter lists and battle-processing events are not wired. Troops have no note field, and the template battle page is blank so no battle-event logic is copied.'] if table=='troops' else []),
                          'battler_name is only charset/length checked; run the asset audit for missing Graphics/Battlers files.',
                          'Exact native array/template hashes and schema are enforced separately by the snapshot/copy backend.']}


LEARNING_MARKERS = ('learn_skill','forget_skill','learnings','$data_classes','change_class','level_up')


def class_learning_impact(index, change):
    """Impact for append_class_learning; shows the class, its existing learnings and the skill."""
    from vxace_index_query import Index
    from vxace_search import search
    from vxace_class_learning import native_mutation, LEVEL_RANGE, MAX_LEARNINGS
    mutation=native_mutation(change.get('locator'),change.get('mutation'))
    class_id=mutation['class_id']
    data=Index(index);classes=data.json('database/classes.json');skills=data.json('database/skills.json')
    if not isinstance(classes,list) or not 2<=len(classes)<=1000 or classes[0] is not None or not isinstance(skills,list) or len(skills)<2 or skills[0] is not None:
        raise ValueError('Indexed Classes and Skills arrays are required')
    for number,row in enumerate(classes[1:],1):
        if not isinstance(row,dict) or row.get('__class__')!='RPG::Class' or type(row.get('id')) is not int or row['id']!=number:
            raise ValueError('Indexed class IDs must match native array slots')
    if type(class_id) is not int or not 0<class_id<len(classes):raise ValueError('class ID outside the indexed Classes array')
    skill_id=mutation['skill_id']
    if type(skill_id) is not int or not 0<skill_id<len(skills) or not isinstance(skills[skill_id],dict):
        raise ValueError('skill_id is not an existing indexed skill')
    level=mutation['level']
    if type(level) is not int or not LEVEL_RANGE[0]<=level<=LEVEL_RANGE[1]:raise ValueError('level outside 1..99')
    selected=classes[class_id];learned=selected.get('learnings')
    existing=[{'level':x.get('level'),'skill_id':x.get('skill_id'),'skill':skills[x['skill_id']].get('name') if type(x.get('skill_id')) is int and 0<x['skill_id']<len(skills) and isinstance(skills[x['skill_id']],dict) else None}
              for x in (learned if isinstance(learned,list) else []) if isinstance(x,dict)]
    if isinstance(learned,list) and mutation['expected_learning_count']!=len(learned):
        raise ValueError('expected_learning_count disagrees with the indexed class learnings')
    if any(x['skill_id']==skill_id for x in existing):raise ValueError('The class already learns this skill')
    mentions=[]
    for marker in LEARNING_MARKERS:
        result=search(data,query=marker,scopes=('scripts','events'),limit=20)
        mentions.append({'literal':marker,'matches':result['matches'],'evidence':result['hits'],'evidence_truncated':result['truncated']})
    data.unchanged()
    return {'kind':'database_entry','severity':'medium','action':mutation['action'],
            'target':{'table':'classes','class_id':class_id,'class_name':selected.get('name'),'skill_id':skill_id,'skill_name':skills[skill_id].get('name'),'level':level},
            'existing_learnings':existing,'learning_count_after':len(existing)+1,'learning_budget':MAX_LEARNINGS,
            'new_learning_note':'','consumer_mentions':mentions,
            'limitations':['The learning is appended last with an empty note; existing learnings are not edited, removed or reordered.',
                           'Actors already in old saves only learn the skill on a later level-up to or past that level (Game_Actor#level_up); nothing is learned retroactively and already-reached levels are not back-filled.',
                           'Actor initial levels, class-change scripts and custom skill-learning scripts are not analysed; literal mentions do not prove freedom from dynamic consumers.',
                           'The skill is not checked for cost, scope or battle suitability; review it in the editor.',
                           'Exact native array/class/skills hashes and schema are enforced separately by the snapshot/copy backend.']}


def entry_impact(index, change):
    if isinstance(change.get('mutation'),dict) and change['mutation'].get('action')=='append_class_learning':
        return class_learning_impact(index,change)
    if isinstance(change.get('mutation'),dict) and change['mutation'].get('action')=='append_database_entry':
        return append_entry_impact(index,change)
    from vxace_index_query import Index
    from vxace_search import search
    from vxace_database_entries import integer, ITEM_FIELDS
    if change.get('locator')!={'table':'items'}:
        raise ValueError('Only native key-item append impact is supported')
    mutation=change.get('mutation')
    if not isinstance(mutation,dict) or mutation.get('action')!='append_key_item':
        raise ValueError('Expected append_key_item impact')
    data=Index(index);items=data.json('database/items.json')
    if not isinstance(items,list) or not 2<=len(items)<=999 or items[0] is not None:
        raise ValueError('A supported native Items array with append capacity is required')
    for number,item in enumerate(items[1:],1):
        if not isinstance(item,dict) or item.get('__class__')!='RPG::Item' or type(item.get('id')) is not int or item['id']!=number:
            raise ValueError('Indexed item IDs must match native array slots')
    identifier=integer(mutation.get('new_id'),'new item ID',1,999)
    template_id=integer(mutation.get('template_id'),'template item ID',1,len(items)-1)
    if identifier!=len(items):raise ValueError('Append ID must be the next array slot')
    selected=items[template_id]
    if set(selected)!=(ITEM_FIELDS|{'__class__'}):
        raise ValueError('Selected indexed template has unknown native fields')
    mentions=[]
    for marker in ('$data_items','gain_item','lose_item','item_number','has_item?'):
        result=search(data,query=marker,scopes=('scripts','events'),limit=20)
        mentions.append({'literal':marker,'matches':result['matches'],'evidence':result['hits'],
                         'evidence_truncated':result['truncated']})
    data.unchanged()
    return {'kind':'database_entry','target':{'table':'items','new_id':identifier,'template_id':template_id,
                                            'template_name':selected.get('name')},'severity':'high',
            'template_note_present':bool(selected.get('note')),'new_note_and_effects_cleared':True,
            'item_consumer_mentions':mentions,
            'limitations':['An appended static ID can collide with runtime-created IDs; literal mentions do not prove freedom from dynamic consumers.',
                          'Search includes editor scripts and event text, not complete note-tag/custom inventory analysis.',
                          'Exact native array/template hashes and schema are enforced separately by the snapshot/copy backend, not reconstructed from normalized JSON.',
                          'Review template and native inventory/save behavior; deletion, ID reuse/reordering and general object creation are not enabled.']}


def slot_impact(index,change):
    import copy
    import tempfile
    from vxace_index_query import Index
    from vxace_script_slots import integer,MAX_NEW_SOURCE_BYTES,MAIN_CALL
    from rgss3_analyzer import analyze_script,build_report
    locator=change.get('locator');mutation=change.get('mutation')
    fields={'action','expected_archive_sha256','expected_anchor_sha256','new_id','name','source'}
    if not isinstance(locator,dict) or set(locator)!={'before_index'} or not isinstance(mutation,dict) or set(mutation)!=fields or mutation.get('action')!='insert_before_main':
        raise ValueError('Expected exact script slot locator and insert_before_main mutation')
    data=Index(index);order=data.json('scripts/order.json').get('scripts')
    if not isinstance(order,list) or not 1<=len(order)<4096:raise ValueError('Supported ordered script evidence required')
    before=integer(locator['before_index'],'before script index',0,len(order)-1)
    identifier=integer(mutation['new_id'],'new script ID',1,2**31-1)
    name=mutation['name']
    if identifier in {row.get('id') for row in order} or not isinstance(name,str) or not 1<=len(name)<=80 or name!=name.strip() or any(ord(c)<32 or ord(c)==127 for c in name) or name in {row.get('name') for row in order}:
        raise ValueError('Proposed script ID/name must be valid and unique')
    import re
    if any(not isinstance(mutation[key],str) or not re.fullmatch('[a-f0-9]{64}',mutation[key]) for key in ('expected_archive_sha256','expected_anchor_sha256')):
        raise ValueError('Exact native archive/anchor hash preconditions required')
    selected=order[before]
    if selected.get('name')!='Main' or sum(row.get('name')=='Main' for row in order)!=1:
        raise ValueError('Unique indexed Main insertion anchor required')
    text=data.text('scripts/'+selected['path'])
    if [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]!=[MAIN_CALL]:
        raise ValueError('Customized Main cannot anchor script slot impact')
    source=mutation.get('source')
    if not isinstance(source,str) or '\0' in source or not 1<=len(source.encode('utf-8','strict'))<=MAX_NEW_SOURCE_BYTES:
        raise ValueError('Bounded UTF-8 proposed script source required')
    compatibility=data.json('analysis/script-compatibility.json')
    existing=copy.deepcopy(compatibility.get('scripts'))
    if not isinstance(existing,list) or len(existing)!=len(order):raise ValueError('Complete ordered script compatibility evidence required')
    for number,item in enumerate(existing):
        if item.get('order')!=number or item.get('path')!=order[number].get('path'):raise ValueError('Ambiguous compatibility script order/path')
        if number>=before:item['order']+=1
    with tempfile.TemporaryDirectory(prefix='vxace-slot-impact-') as directory:
        proposed=Path(directory)/'ProposedSlot.rb';proposed.write_bytes(source.encode('utf-8','strict'))
        new=analyze_script(str(proposed),before,str(directory))
    marker='<proposed-script-slot>';new.update(path=marker,name=mutation.get('name'))
    report=build_report(existing[:before]+[new]+existing[before:])
    def related(value):
        if isinstance(value,dict):return value.get('path')==marker or any(related(v) for v in value.values())
        if isinstance(value,list):return any(related(v) for v in value)
        return False
    evidence={}
    for key in ('method_collisions','constant_collisions','imported_keys','dependency_findings'):
        found=[row for row in report[key] if related(row)]
        bounded=[]
        for row in found[:100]:
            item=copy.deepcopy(row)
            for field in ('occurrences','definitions'):
                if isinstance(item.get(field),list) and len(item[field])>20:
                    item[field+'_total']=len(item[field]);item[field]=item[field][:20]
            bounded.append(item)
        evidence[key]={'total':len(found),'findings':bounded,'truncated':len(found)>len(bounded)}
    data.unchanged()
    return {'kind':'script_slot','severity':'high','target':{'before_index':before,'anchor_id':selected.get('id'),'anchor_name':'Main','new_id':mutation.get('new_id'),'name':mutation.get('name')},
            'new_script':{key:new[key] for key in ('classes','modules','methods','aliases','save_hooks','imported_reads','imported_sets','requires','warnings')},
            'ordered_compatibility_evidence':evidence,
            'limitations':['Proposed startup code can change game behavior; static analysis never executes it or establishes compatibility.',
                          'Native archive/anchor/ID/schema preservation is enforced separately by the snapshot/copy backend.',
                          'Metaprogramming, attribute-generated methods and dynamic dependencies may be missed.',
                          'Review native compilation, editor order, new game, unchanged older saves and restart-based persistence.']}


def upper_tile_impact(index,change):
    from vxace_index_query import Index
    from vxace_upper_tiles import schema,coordinates
    from vxace_search import search
    locator=change.get('locator');mutation=change.get('mutation');schema(mutation)
    if not isinstance(locator,dict) or set(locator)!={'map_id'}:raise ValueError('Upper tile impact requires exact map_id locator')
    from vxace_map_regions import integer
    mid=integer(locator['map_id'],'map ID',1,999999)
    data=Index(index);native=data.json(f'maps/map-{mid:03d}.json')
    if not isinstance(native,dict) or native.get('__class__')!='RPG::Map':raise ValueError('Indexed native map required')
    width=integer(native.get('width'),'map width',1,500);height=integer(native.get('height'),'map height',1,500)
    table=native.get('data')
    if not isinstance(table,dict) or table.get('__class__')!='Table' or (table.get('dimensions'),table.get('xsize'),table.get('ysize'),table.get('zsize'))!=(3,width,height,4) or len(table.get('data',[]))!=width*height*4:
        raise ValueError('Complete indexed native map Table required')
    rows=[];seen=set()
    for cell in mutation['cells']:
        if not isinstance(cell,dict) or set(cell)!={'x','y','expected_tile','value'}:raise ValueError('Unsupported upper tile impact cell')
        x=integer(cell['x'],'cell x',0,width-1);y=integer(cell['y'],'cell y',0,height-1)
        if (x,y) in seen:raise ValueError('Duplicate upper tile impact cell')
        seen.add((x,y));old=integer(cell['expected_tile'],'expected B-E tile',0,1023);value=integer(cell['value'],'new B-E tile',0,1023)
        if table['data'][x+y*width+2*width*height]!=old or old==value:raise ValueError('Stale or no-op upper tile impact precondition')
        rows.append({'x':x,'y':y,'layer':2,'before':old,'after':value})
    if not 1<=len(rows)<=256:raise ValueError('Upper tile impact cell budget exceeded')
    mentions=[]
    for marker in ('$data_map','tile_id','layered_tiles','passable?','check_passage','terrain_tag','ladder?','bush?','counter?','damage_floor?'):
        result=search(data,query=marker,scopes=('scripts','events'),limit=10)
        mentions.append({'literal':marker,'matches':result['matches'],'evidence':result['hits'],'truncated':result['truncated']})
    data.unchanged()
    return {'kind':'map_tile','severity':'high','target':{'map_id':mid,'tileset_id':native.get('tileset_id'),'layer':2},
            'cells':rows,'tile_consumer_mentions':mentions,
            'limitations':['Terrain/passability/star/ladder/bush/counter/damage-floor semantics depend on selected native tileset flags and runtime consumers.',
                          'Literal mentions include definitions/comments and can miss dynamic map replacement or event collision effects.',
                          'Native Table/tileset/asset hashes and image layout are checked separately by the guarded copy backend.',
                          'Review native editor rendering, actor passage, old-save map reload and restart-based persistence.']}


def map_event_impact(index,change):
    from vxace_index_query import Index
    from vxace_map_events import schema,integer,text
    from vxace_search import search
    locator=change.get('locator');mutation=change.get('mutation')
    schema(mutation)
    blank=mutation['action']=='append_blank_event'
    staged=mutation['action']=='append_staged_event'
    if not isinstance(locator,dict) or set(locator)!={'map_id'}:
        raise ValueError('Exact map-event append proposal required')
    mid=integer(locator['map_id'],'map ID',1,999999);data=Index(index);native=data.json(f'maps/map-{mid:03d}.json')
    if not isinstance(native,dict) or native.get('__class__')!='RPG::Map' or not isinstance(native.get('events'),dict):raise ValueError('Indexed native map events required')
    old=native['events'];identifier=integer(mutation['new_id'],'new event ID',1,999)
    if any(not key.isdigit() or str(int(key))!=key for key in old) or identifier!=max((int(key) for key in old),default=0)+1:raise ValueError('New event must append after existing IDs')
    template_id=integer(mutation['donor_event_id' if blank else 'template_id'],'donor event ID' if blank else 'template event ID',1,999)
    if str(template_id) not in old:raise ValueError('Template event absent from index')
    width=integer(native.get('width'),'map width',1,500);height=integer(native.get('height'),'map height',1,500)
    x=integer(mutation['x'],'new event x',0,width-1);y=integer(mutation['y'],'new event y',0,height-1)
    if any(not isinstance(event,dict) or (event.get('x'),event.get('y'))==(x,y) for event in old.values()):raise ValueError('Occupied or opaque event position')
    name=text(mutation['name'],'new event name',100)
    lines=[] if blank or staged else mutation['text']
    if not blank and not staged:
        if not isinstance(lines,list) or not 1<=len(lines)<=4 or not any(lines):raise ValueError('One to four literal dialogue lines required')
        for line in lines:text(line,'dialogue line',500,True)
    mentions=[]
    for marker in ('$data_map','$game_map.events','Game_Event','event_id','self_switches','setup_events'):
        result=search(data,query=marker,scopes=('scripts','events'),limit=10)
        mentions.append({'literal':marker,'matches':result['matches'],'evidence':result['hits'],'truncated':result['truncated']})
    staged_report=None
    if staged:
        from vxace_map_events import staged_ids
        system=data.json('database/system.json')
        if not isinstance(system,dict) or not isinstance(system.get('switches'),list) or not isinstance(system.get('variables'),list) or len(system['switches'])<2 or len(system['variables'])<2:
            raise ValueError('Indexed native System switches/variables required')
        pages=mutation['pages'];staged_ids(pages,len(system['switches']),len(system['variables']))
        def label(names,number):
            return names[number] if isinstance(names[number],str) and names[number] else None
        warnings=[];rows=[]
        for number,page in enumerate(pages,1):
            condition=page['condition']
            rows.append({'page':number,'condition':condition,'commands':len(page['commands']),'trigger':'action'})
            if not condition and number<len(pages):
                warnings.append(f'Page {number} has no conditions but is not the last page: the engine checks pages highest-number first, so it only runs when no later page condition holds.')
            for key in ('switch1','switch2'):
                if key in condition and not label(system['switches'],condition[key]):warnings.append(f'Page {number} condition {key} {condition[key]} is an unnamed switch.')
            if 'variable' in condition and not label(system['variables'],condition['variable']['id']):warnings.append(f'Page {number} condition variable {condition["variable"]["id"]} is an unnamed variable.')
            for op in page['commands']:
                if 'set_switch' in op and not label(system['switches'],op['set_switch']):warnings.append(f'Page {number} sets unnamed switch {op["set_switch"]}.')
                if 'set_variable' in op and not label(system['variables'],op['set_variable']):warnings.append(f'Page {number} sets unnamed variable {op["set_variable"]}.')
        staged_report={'page_count':len(pages),'pages':rows,'priority_note':'The engine runs the highest-numbered page whose conditions are all met; verify the page order against the quest state machine.',
                       'warnings':warnings}
    data.unchanged()
    return {'kind':'map_event','severity':'high','target':{'map_id':mid,'new_id':identifier,'name':name,'x':x,'y':y,('donor_event_id' if blank else 'template_id'):template_id},
            **({'staged':staged_report} if staged_report else {}),'literal_dialogue':lines,'event_consumer_mentions':mentions,'proposed_graphic':mutation.get('graphic'),
            'limitations':['Native exact template/map/schema preservation gates are enforced separately by the Python copy chain.',
                          'An appended static ID can collide with runtime-created events or pre-existing orphan self-switch/save state.',
                          'Literal consumers miss dynamic ownership; inspect custom map/save hooks and action-button accessibility.',
                          'Stationary, one unconditional action-button page; optional character assets require independent native/header/hash checks.',
                          'Review character/object prefix semantics, native rendering, old-save reload, dialogue and restart.',
                          *(['Staged pages: conditions use only switch/variable/self-switch; no branches, autorun, parallel or item/actor conditions. Self-switch state of the new event id may pre-exist in saves.'] if staged else [])]}


def map_entry_impact(index,change):
    from vxace_maps import FIELDS,integer
    from vxace_index_query import Index
    from vxace_search import search
    import re
    loc=change.get('locator');mutation=change.get('mutation')
    if not isinstance(loc,dict) or set(loc)!={'template_map_id'} or not isinstance(mutation,dict) or set(mutation)!=FIELDS-{'template_map_id'} or mutation.get('action')!='append_blank_map':raise ValueError('Exact map append proposal required')
    tid=integer(loc['template_map_id'],'template map ID',1,999);identifier=integer(mutation['new_id'],'new map ID',1,999)
    data=Index(index);infos=data.json('database/map-infos.json')
    if not isinstance(infos,dict) or str(tid) not in infos or identifier!=max(int(key) for key in infos)+1:raise ValueError('Indexed next map ID/template disagree')
    for field in ('expected_infos_sha256','expected_template_sha256','expected_inventory_sha256','expected_tilesets_sha256'):
        if not isinstance(mutation[field],str) or not re.fullmatch('[a-f0-9]{64}',mutation[field]):raise ValueError('Exact native map append guards required')
    evidence=[]
    for query in ('MapInfos','reserve_transfer','load_data','$game_map','region_id','DataManager'):
        found=search(data,query=query,scopes=('scripts','events'),limit=10)
        evidence.append({'literal':query,'matches':found['matches'],'evidence':found['hits'],'truncated':found['truncated']})
    data.unchanged()
    return {'kind':'map_entry','severity':'high','target':{'template_map_id':tid,'new_id':identifier,'name':mutation['name']},'consumer_mentions':evidence,
            'limitations':['Actual native tree/file inventory/tileset/template hashes and empty-map construction run separately in the Python copy chain.',
                          'Next static ID can collide with runtime-created maps, custom loaders or old save state; literal search cannot establish absence.',
                          'Adds one root map with inherited dimensions/tiles and no events; no transfers are authored and existing maps/System remain unchanged.',
                          'Review native editor tree/map, real transfer/render/passability, old save and native save/process restart.']}


def map_name_impact(index,change):
    from vxace_map_names import FIELDS,integer,name
    from vxace_index_query import Index
    from vxace_search import search
    import re
    loc=change.get('locator');mutation=change.get('mutation')
    if not isinstance(loc,dict) or set(loc)!={'map_id'} or not isinstance(mutation,dict) or set(mutation)!=FIELDS or mutation.get('action')!='set_display_name':
        raise ValueError('Exact native display-name proposal required')
    mid=integer(loc['map_id'],'map ID',1,999);data=Index(index);root=data.json(f'maps/map-{mid:03d}.json')
    if not isinstance(root,dict) or root.get('__class__')!='RPG::Map' or root.get('display_name')!=mutation['expected_display_name']:
        raise ValueError('Indexed map/display-name precondition disagrees')
    if not isinstance(mutation['expected_map_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',mutation['expected_map_sha256']):
        raise ValueError('Exact native map fingerprint required')
    old=name(mutation['expected_display_name']);value=name(mutation['value'])
    if old==value:raise ValueError('No-op display-name proposal')
    evidence=[]
    for query in ('display_name','Window_MapName','Game_Map','DataManager'):
        found=search(data,query=query,scopes=('scripts','events'),limit=10)
        evidence.append({'literal':query,'matches':found['matches'],'evidence':found['hits'],'truncated':found['truncated']})
    data.unchanged()
    return {'kind':'map_name','severity':'high','target':{'map_id':mid,'before':old,'after':value},'consumer_mentions':evidence,
            'limitations':['Native map fingerprint and all-other-field preservation are separately enforced by the Python copy chain.',
                          'Literal mentions cannot resolve custom name windows, dynamic map replacement, old saves or hidden consumers.',
                          'Only display_name changes; MapInfos/editor name, tree, tiles, events and resources remain unchanged.',
                          'Verify the native name window, older-save map reload, movement and full-process save/restart.']}


def map_encounter_impact(index,change):
    from vxace_map_encounters import FIELDS,ACTION,integer,region_set,sha
    from vxace_index_query import Index
    from vxace_search import search
    loc=change.get('locator');mutation=change.get('mutation')
    if not isinstance(loc,dict) or set(loc)!={'map_id'} or not isinstance(mutation,dict) or set(mutation)!=FIELDS or mutation.get('action')!=ACTION:
        raise ValueError('Exact native encounter proposal required')
    mid=integer(loc['map_id'],'map ID',1,999);data=Index(index);root=data.json(f'maps/map-{mid:03d}.json')
    if not isinstance(root,dict) or root.get('__class__')!='RPG::Map':raise ValueError('Indexed native map required')
    for field in ('expected_map_sha256','expected_troops_sha256'):sha(mutation[field],field)
    entries=root.get('encounter_list')
    if not isinstance(entries,list) or len(entries)>1000 or mutation['expected_encounter_count']!=len(entries):
        raise ValueError('Indexed encounter list disagrees with the expected count')
    rows=[]
    for number,entry in enumerate(entries):
        if not isinstance(entry,dict) or entry.get('__class__')!='RPG::Map::Encounter' or set(entry)!={'__class__','troop_id','weight','region_set'}:
            raise ValueError('Opaque native encounter entry')
        rows.append({'index':number,'troop_id':entry['troop_id'],'weight':entry['weight'],'region_set':entry['region_set']})
    troop_id=integer(mutation['troop_id'],'troop ID',1,999);regions=region_set(mutation['region_ids'],'region_ids')
    troops=data.json('database/troops.json');enemies=data.json('database/enemies.json')
    troop=next((t for t in troops if isinstance(t,dict) and t.get('id')==troop_id),None) if isinstance(troops,list) else None
    if troop is None:raise ValueError('Indexed troop not found: '+str(troop_id))
    names={e.get('id'):e.get('name') for e in enemies if isinstance(e,dict)} if isinstance(enemies,list) else {}
    members=[{'enemy_id':m.get('enemy_id'),'name':names.get(m.get('enemy_id')),'hidden':m.get('hidden')} for m in troop.get('members') or [] if isinstance(m,dict)]
    table=root.get('data') if isinstance(root.get('data'),dict) else {}
    values=table.get('data') if isinstance(table.get('data'),list) else []
    layer=(root.get('width') or 0)*(root.get('height') or 0)
    painted={}
    for value in values[3*layer:]:
        if type(value) is int and value>>8:painted[value>>8]=painted.get(value>>8,0)+1
    region_rows=[{'region':r,'painted_cells':painted.get(r,0)} for r in regions]
    mentions=[]
    for query in ('encounter_list','make_encounter_list','encounter_step','BattleManager','Game_Player'):
        found=search(data,query=query,scopes=('scripts','events'),limit=10)
        mentions.append({'literal':query,'matches':found['matches'],'evidence':found['hits'],'truncated':found['truncated']})
    data.unchanged()
    return {'kind':'map_encounter','severity':'high','target':{'map_id':mid,'troop_id':troop_id,'weight':mutation['weight'],'region_set':regions,'encounter_step':mutation['encounter_step']},
            'existing_encounters':rows,'troop':{'id':troop_id,'name':troop.get('name'),'members':members,'page_count':len(troop.get('pages') or [])},
            'region_usage':{'scope':'selected regions only' if regions else 'whole map','regions':region_rows,
                            'unpainted_regions':[r['region'] for r in region_rows if not r['painted_cells']]},
            'consumer_mentions':mentions,
            'limitations':['Native map/troops fingerprints and exact-prefix preservation are enforced separately by the Python copy chain.',
                           'A random battle also needs the player to walk on the map with encounters enabled; events or scripts may disable them (Game_System#encounter_disabled / custom hooks).',
                           'A region-restricted encounter never fires on a map without cells painted with those region IDs; region_set 0/empty means the whole map.',
                           'The troop is unchanged, including its battle events and member escape/hidden behavior; review its pages and enemies.',
                           'Literal script mentions cannot resolve dynamic or custom encounter logic.',
                           'Native old-save map reload (System.version_id advance) and restart-based persistence testing remain required.']}


def map_shop_impact(index,change):
    from vxace_map_shops import schema,GOODS,MAX_GOODS
    from vxace_map_regions import integer
    from vxace_index_query import Index
    from vxace_search import search
    loc=change.get('locator');mutation=change.get('mutation')
    if not isinstance(loc,dict) or set(loc)!={'map_id','event_id'}:raise ValueError('Exact native shop proposal required')
    schema(mutation)
    mid=integer(loc['map_id'],'map ID',1,999);eid=integer(loc['event_id'],'event ID',1,999)
    data=Index(index);root=data.json(f'maps/map-{mid:03d}.json')
    events=root.get('events') if isinstance(root,dict) else None
    event=events.get(str(eid)) if isinstance(events,dict) else None
    if not isinstance(event,dict) or not isinstance(event.get('pages'),list) or len(event['pages'])!=1:raise ValueError('Indexed one-page shop event required')
    page=event['pages'][0];commands=page.get('list') if isinstance(page,dict) else None
    if not isinstance(commands,list) or not commands:raise ValueError('Indexed shop event command list required')
    codes=[c.get('code') for c in commands if isinstance(c,dict)]
    if codes[-1:]!=[0] or any(code not in (0,101,401) for code in codes):raise ValueError('Indexed shop event must be blank or literal dialogue')
    goods=[]
    for good in mutation['goods']:
        label=GOODS[good['type']][1];table=data.json(f'database/{label}.json')
        entry=table[good['id']] if isinstance(table,list) and good['id']<len(table) else None
        if not isinstance(entry,dict) or entry.get('id')!=good['id']:raise ValueError('Indexed '+label+' entry absent: '+str(good['id']))
        goods.append({'type':good['type'],'id':good['id'],'name':entry.get('name'),'database_price':entry.get('price'),
                      'effective_price':entry.get('price') if good['price'] is None else good['price'],
                      'price_type':0 if good['price'] is None else 1})
    mentions=[]
    for query in ('Scene_Shop','command_302','Window_ShopBuy','buying_price','selling_price'):
        found=search(data,query=query,scopes=('scripts','events'),limit=10)
        mentions.append({'literal':query,'matches':found['matches'],'evidence':found['hits'],'truncated':found['truncated']})
    data.unchanged()
    return {'kind':'map_shop','severity':'high','target':{'map_id':mid,'event_id':eid,'event_name':event.get('name'),
                                                          'event_shape':'blank' if len(commands)==1 else 'dialogue','good_count':len(goods),
                                                          'purchase_only':mutation['purchase_only']},
            'goods':goods,'consumer_mentions':mentions,
            'limitations':['Native map/event/list and Items/Weapons/Armors fingerprints and exact candidate preservation are enforced separately by the Python copy chain.',
                           'Items, Weapons and Armors are read-only; only the one event page list gains Shop Processing rows before its terminator.',
                           'Shop menus honor the native database price unless a specified price is set; custom shop scenes or price/tax scripts can change what is shown or charged.',
                           'Unless purchase-only is set the shop also offers selling, which follows the native database sell rules.',
                           'Literal script mentions cannot resolve dynamic or custom shop logic.',
                           'Native old-save map reload (System.version_id advance) and restart-based persistence testing remain required.'],
            'max_goods':MAX_GOODS}


def map_label_impact(index,change):
    from vxace_map_labels import FIELDS,integer,name
    from vxace_index_query import Index
    from vxace_search import search
    import re
    loc=change.get('locator');mutation=change.get('mutation')
    if not isinstance(loc,dict) or set(loc)!={'map_id'} or not isinstance(mutation,dict) or set(mutation)!=FIELDS-{'map_id'} or mutation.get('action')!='set_tree_name':
        raise ValueError('Exact map-tree name proposal required')
    mid=integer(loc['map_id'],'map ID',1,999);data=Index(index);infos=data.json('database/map-infos.json')
    entry=infos.get(str(mid)) if isinstance(infos,dict) else None
    if not isinstance(entry,dict) or entry.get('__class__')!='RPG::MapInfo' or entry.get('name')!=mutation['expected_name']:
        raise ValueError('Indexed map-tree/name precondition disagrees')
    for field in ('expected_infos_sha256','expected_entry_sha256','expected_inventory_sha256'):
        if not isinstance(mutation[field],str) or not re.fullmatch('[a-f0-9]{64}',mutation[field]):raise ValueError('Exact native map-tree/entry/inventory guards required')
    old=name(mutation['expected_name']);value=name(mutation['value'])
    if old==value:raise ValueError('No-op map-tree name proposal')
    evidence=[]
    for query in ('$data_mapinfos','MapInfo','DataManager',*([old] if old else [])):
        found=search(data,query=query,scopes=('scripts','events'),limit=10)
        evidence.append({'literal':query,'matches':found['matches'],'evidence':found['hits'],'truncated':found['truncated']})
    graph=data.json('codex/graph.json');data.unchanged()
    return {'kind':'map_label','severity':'high','target':{'map_id':mid,'before':old,'after':value},'consumer_mentions':evidence,
            'dependencies':graph_neighbors(graph,f'map:{mid}'),
            'limitations':['Exact native whole-tree/entry/map inventory and candidate preservation are enforced separately by the Python copy chain.',
                          'Names are labels rather than IDs; duplicate labels are valid and literal searches cannot resolve hidden name-based consumers/caches.',
                          'All native maps, display_name, parent/order/scroll metadata and System/version remain unchanged.',
                          'Default MapInfos reloads on process startup; review custom caches and verify editor/window/older-save/movement/save/restart.']}


def build(index: Path, spec_path: Path):
    spec=load(spec_path)
    if not isinstance(spec,dict) or not isinstance(spec.get("changes"),list) or not spec["changes"]:
        raise ValueError("patch spec requires non-empty changes array")
    graph=load(index/"codex"/"graph.json",{}) or {}
    maps=load(index/"codex"/"maps.json",[]) or []
    scripts=load(index/"codex"/"scripts.json",{}) or {}
    if not graph or not isinstance(maps,list) or not scripts:
        raise ValueError("project index is missing required codex graph/maps/scripts outputs")
    impacts=[]
    for change in spec["changes"]:
        kind=change.get("kind")
        if kind=="script": impacts.append(script_impact(index,scripts,change))
        elif kind=="event": impacts.append(event_impact(graph,maps,change,index))
        elif kind=="database": impacts.append(database_impact(index,change))
        elif kind=='map_region': impacts.append(region_impact(index,change))
        elif kind=='database_entry': impacts.append(entry_impact(index,change))
        elif kind=='script_slot': impacts.append(slot_impact(index,change))
        elif kind=='map_tile': impacts.append(upper_tile_impact(index,change))
        elif kind=='map_event': impacts.append(map_event_impact(index,change))
        elif kind=='map_entry': impacts.append(map_entry_impact(index,change))
        elif kind=='map_name': impacts.append(map_name_impact(index,change))
        elif kind=='map_label': impacts.append(map_label_impact(index,change))
        elif kind=='map_encounter': impacts.append(map_encounter_impact(index,change))
        elif kind=='map_shop': impacts.append(map_shop_impact(index,change))
        else: raise ValueError(f"unsupported change kind: {kind}")
    high=sum(1 for x in impacts if x.get("severity")=="high")
    return {"impact_version":VERSION,"title":str(spec.get("title") or "VX Ace impact analysis"),"impact_count":len(impacts),
            "high_risk_count":high,"review_required":True,"impacts":impacts,
            "limitations":["Impact relationships are evidence from the current normalized Project Codex, not proof that no hidden/dynamic dependency exists."]}

def markdown(report):
    lines=[f"# {report['title']}","",f"Impacts: **{report['impact_count']}**  ",f"High-risk findings: **{report['high_risk_count']}**","","## Findings",""]
    for i,x in enumerate(report["impacts"],1):
        lines += [f"### {i}. {x['kind'].title()} — {x.get('severity','unknown')} risk",""]
        lines += ["```json",json.dumps(x.get("target",{}),ensure_ascii=False,indent=2),"```",""]
        deps=x.get("dependencies",[])
        if deps:
            lines += ["Dependencies / relationships:",""]
            for d in deps: lines.append(f"- {d.get('direction')} `{d.get('relation')}` → `{d.get('node',{}).get('id')}` ({d.get('node',{}).get('label','')})")
            lines.append("")
        for lim in x.get("limitations",[]): lines.append(f"- Limitation: {lim}")
        if x.get("limitations"): lines.append("")
    lines += ["## Global limitations","",*[f"- {x}" for x in report.get("limitations",[])],""]
    return "\n".join(lines)

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("index"); ap.add_argument("--spec",required=True); ap.add_argument("--json"); ap.add_argument("--markdown")
    args=ap.parse_args(argv)
    try: report=build(Path(args.index).resolve(),Path(args.spec).resolve())
    except Exception as e:
        print(f"error: {e}",file=__import__('sys').stderr); return 2
    if args.json: dump(args.json,report)
    if args.markdown: Path(args.markdown).write_text(markdown(report),encoding="utf-8")
    print(json.dumps({"status":"ok","impact_count":report["impact_count"],"high_risk_count":report["high_risk_count"]}))
    return 0
if __name__=="__main__": raise SystemExit(main())
