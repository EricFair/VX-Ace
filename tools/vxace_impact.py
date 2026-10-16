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


def entry_impact(index, change):
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
    if not isinstance(locator,dict) or set(locator)!={'map_id'}:
        raise ValueError('Exact map-event append proposal required')
    mid=integer(locator['map_id'],'map ID',1,999999);data=Index(index);native=data.json(f'maps/map-{mid:03d}.json')
    if not isinstance(native,dict) or native.get('__class__')!='RPG::Map' or not isinstance(native.get('events'),dict):raise ValueError('Indexed native map events required')
    old=native['events'];identifier=integer(mutation['new_id'],'new event ID',1,999)
    if any(not key.isdigit() or str(int(key))!=key for key in old) or identifier!=max((int(key) for key in old),default=0)+1:raise ValueError('New event must append after existing IDs')
    template_id=integer(mutation['template_id'],'template event ID',1,999)
    if str(template_id) not in old:raise ValueError('Template event absent from index')
    width=integer(native.get('width'),'map width',1,500);height=integer(native.get('height'),'map height',1,500)
    x=integer(mutation['x'],'new event x',0,width-1);y=integer(mutation['y'],'new event y',0,height-1)
    if any(not isinstance(event,dict) or (event.get('x'),event.get('y'))==(x,y) for event in old.values()):raise ValueError('Occupied or opaque event position')
    name=text(mutation['name'],'new event name',100)
    lines=mutation['text']
    if not isinstance(lines,list) or not 1<=len(lines)<=4 or not any(lines):raise ValueError('One to four literal dialogue lines required')
    for line in lines:text(line,'dialogue line',500,True)
    mentions=[]
    for marker in ('$data_map','$game_map.events','Game_Event','event_id','self_switches','setup_events'):
        result=search(data,query=marker,scopes=('scripts','events'),limit=10)
        mentions.append({'literal':marker,'matches':result['matches'],'evidence':result['hits'],'truncated':result['truncated']})
    data.unchanged()
    return {'kind':'map_event','severity':'high','target':{'map_id':mid,'new_id':identifier,'name':name,'x':x,'y':y,'template_id':template_id},
            'literal_dialogue':lines,'event_consumer_mentions':mentions,'proposed_graphic':mutation.get('graphic'),
            'limitations':['Native exact template/map/schema preservation gates are enforced separately by the Python copy chain.',
                          'An appended static ID can collide with runtime-created events or pre-existing orphan self-switch/save state.',
                          'Literal consumers miss dynamic ownership; inspect custom map/save hooks and action-button accessibility.',
                          'Stationary, one unconditional action-button page; optional character assets require independent native/header/hash checks.',
                          'Review character/object prefix semantics, native rendering, old-save reload, dialogue and restart.']}


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
