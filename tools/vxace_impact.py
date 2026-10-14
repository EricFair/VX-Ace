#!/usr/bin/env python3
"""Evidence-first dependency impact analysis for VX Ace patch specs."""
from __future__ import annotations
import argparse, json
from pathlib import Path

VERSION = "0.12.0"
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
