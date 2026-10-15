#!/usr/bin/env python3
"""Evidence-first dependency impact analysis for VX Ace patch specs."""
from __future__ import annotations
import argparse, json
from pathlib import Path

VERSION = "0.20.0"
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
        return {"kind":"event","scope":"map","target":exact,"graph_node":node,"dependencies":graph_neighbors(graph,node),"severity":"high" if mutation.get('action') in {'insert_page','delete_page'} else "medium",'structural_action':mutation.get('action'),'requested_locator':change.get('locator')}
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
