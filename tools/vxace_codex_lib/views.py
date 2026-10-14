from __future__ import annotations
from collections import defaultdict
from .common import VERSION, load, ctx_key

def build_map_codex(project, catalog, switches, variables, callers, battles, transfers, script_calls):
    out = []
    maps = {m.get("map_id"): dict(m) for m in project.get("maps", []) if isinstance(m, dict)}
    event_ids = defaultdict(set)
    for mid, eid in catalog["event_names"]:
        event_ids[mid].add(eid)
    for mid in sorted(set(maps) | set(event_ids)):
        entry = {"map_id": mid, "name": catalog["map_names"].get(mid, maps.get(mid, {}).get("name", "")), "events": []}
        for eid in sorted(event_ids.get(mid, set())):
            ev = {"event_id": eid, "name": catalog["event_names"].get((mid, eid), ""), "pages": []}
            pages = sorted(p for (m, e, p) in catalog["page_meta"] if m == mid and e == eid)
            for page in pages:
                key = ("map", mid, eid, page)
                pg = {"page": page, **catalog["page_meta"].get((mid, eid, page), {}), "switches": [], "variables": [], "common_events": [], "battles": [], "transfers": [], "script_blocks": []}
                for sw in switches:
                    roles = []
                    for x in sw.get("reads", []):
                        if ctx_key(x) == key: roles.append("read")
                    for x in sw.get("writes", []):
                        if ctx_key(x) == key: roles.append("write")
                    if roles: pg["switches"].append({"id": sw.get("id"), "name": sw.get("name", ""), "roles": sorted(set(roles))})
                for var in variables:
                    roles = []
                    for x in var.get("reads", []):
                        if ctx_key(x) == key: roles.append("read")
                    for x in var.get("writes", []):
                        if ctx_key(x) == key: roles.append("write")
                    if roles: pg["variables"].append({"id": var.get("id"), "name": var.get("name", ""), "roles": sorted(set(roles))})
                for ce in callers:
                    if any(ctx_key(x) == key for x in ce.get("callers", [])):
                        pg["common_events"].append({"id": ce.get("common_event_id"), "name": ce.get("name", "")})
                for b in battles:
                    if ctx_key(b) == key: pg["battles"].append({"troop_id": b.get("troop_id"), "troop_name": b.get("troop_name", "")})
                for t in transfers:
                    if ctx_key(t) == key: pg["transfers"].append({"map_id": t.get("map_id"), "map_name": t.get("map_name", ""), "x": t.get("x"), "y": t.get("y")})
                for sc in script_calls:
                    if ctx_key(sc) == key: pg["script_blocks"].append({"command_index": sc.get("command_index"), "text": sc.get("text", "")})
                ev["pages"].append(pg)
            entry["events"].append(ev)
        out.append(entry)
    return out


def build_script_codex(root):
    order = load(root / "scripts" / "order.json", {}) or {}
    compatibility = load(root / "analysis" / "script-compatibility.json", {}) or {}
    event_blocks = load(root / "analysis" / "script-calls-from-events.json", []) or []
    analyzed = {x.get("path"): x for x in compatibility.get("scripts", []) if isinstance(x, dict)}
    collisions_by_path = defaultdict(list)
    for c in compatibility.get("method_collisions", []):
        for occ in c.get("occurrences", []):
            collisions_by_path[occ.get("path")].append({"method": c.get("method"), "severity": c.get("severity"), "reasons": c.get("reasons", [])})
    scripts = []
    for item in order.get("scripts", []):
        path = item.get("path"); detail = analyzed.get(path, {})
        scripts.append({
            "index": item.get("index"), "id": item.get("id"), "name": item.get("name", ""), "path": path,
            "classes": detail.get("classes", []), "modules": detail.get("modules", []), "methods": detail.get("methods", []),
            "aliases": detail.get("aliases", []), "imported_sets": detail.get("imported_sets", []), "imported_reads": detail.get("imported_reads", []),
            "save_hooks": detail.get("save_hooks", []), "note_parser_lines": detail.get("note_parser_lines", []),
            "collision_candidates": collisions_by_path.get(path, []),
        })
    return {"scripts": scripts, "event_script_blocks": event_blocks, "compatibility_summary": compatibility.get("summary", {}), "limitations": compatibility.get("limitations", [])}


def build_graph(switches, variables, callers, battles, transfers, catalog):
    nodes = {}; edges = []
    def node(nid, typ, label, **extra):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": typ, "label": label, **extra}
        else:
            if label and (not nodes[nid].get("label") or nodes[nid].get("label")==nid): nodes[nid]["label"] = label
            nodes[nid].update({k:v for k,v in extra.items() if v is not None})
    def context_node(ctx):
        k = ctx_key(ctx)
        if k[0] == "map":
            nid = f"map:{k[1]}:event:{k[2]}:page:{k[3]}"
            label = catalog["event_names"].get((k[1], k[2]), "") or nid
            node(nid, "event_page", label, map_id=k[1], event_id=k[2], page=k[3], map_name=catalog["map_names"].get(k[1], "")); return nid
        if k[0] == "common_event":
            nid = f"common_event:{k[1]}"; node(nid, "common_event", catalog["common_event_names"].get(k[1], "") or nid, common_event_id=k[1]); return nid
        if k[0] == 'troop':
            nid=f'troop:{k[1]}:page:{k[2]}'; node(nid,'troop_page',nid,troop_id=k[1],page=k[2]); return nid
        nid = ":".join(str(x) for x in k); node(nid, "context", nid); return nid
    for s in switches:
        rid=f"switch:{s.get('id')}"; node(rid,"switch",s.get("name") or rid,id_number=s.get("id"))
        for x in s.get("reads",[]): edges.append({"from":rid,"to":context_node(x),"relation":"read_by"})
        for x in s.get("writes",[]): edges.append({"from":context_node(x),"to":rid,"relation":"writes"})
    for v in variables:
        rid=f"variable:{v.get('id')}"; node(rid,"variable",v.get("name") or rid,id_number=v.get("id"))
        for x in v.get("reads",[]): edges.append({"from":rid,"to":context_node(x),"relation":"read_by"})
        for x in v.get("writes",[]): edges.append({"from":context_node(x),"to":rid,"relation":"writes"})
    for ce in callers:
        cid=f"common_event:{ce.get('common_event_id')}"; node(cid,"common_event",ce.get("name") or cid,common_event_id=ce.get("common_event_id"))
        for x in ce.get("callers",[]): edges.append({"from":context_node(x),"to":cid,"relation":"calls"})
    for b in battles:
        tid=f"troop:{b.get('troop_id')}"; node(tid,"troop",b.get("troop_name") or tid,troop_id=b.get("troop_id")); edges.append({"from":context_node(b),"to":tid,"relation":"starts_battle"})
    for t in transfers:
        if t.get("designation") == "direct" and t.get("map_id") is not None:
            mid=f"map:{t.get('map_id')}"; node(mid,"map",t.get("map_name") or mid,map_id=t.get("map_id")); edges.append({"from":context_node(t),"to":mid,"relation":"transfers_to"})
    return {"nodes": sorted(nodes.values(), key=lambda x:x["id"]), "edges": edges}


def markdown_summary(project, systems, state_machines):
    lines = [f"# Project Codex — {project.get('project_name','VX Ace Project')}", "", f"Generated by v{VERSION}. Inferences are evidence-based candidates, not guaranteed design intent.", ""]
    by_type = defaultdict(list)
    for s in systems: by_type[s.get("type","other")].append(s)
    lines += ["## Overview", "", f"- Systems inferred: **{len(systems)}**", f"- State-machine candidates: **{len(state_machines)}**", f"- Maps indexed: **{project.get('map_count',0)}**", f"- Scripts indexed: **{project.get('script_count',0)}**", ""]
    labels = {"quest_candidate":"Quest candidates","boss_or_battle_gate_candidate":"Boss / battle gates","cutscene_candidate":"Cutscene candidates","common_event_subsystem_candidate":"Common-event subsystems"}
    for typ,label in labels.items():
        items=by_type.get(typ,[])
        if not items: continue
        lines += [f"## {label}", ""]
        for item in items:
            title=item.get("title") or item.get("name") or item.get("event_name") or item.get("id")
            lines += [f"### {title}", "", f"Confidence: **{item.get('confidence','low')}**", ""]
            for r in item.get("reasons",[]): lines.append(f"- {r}")
            lines.append("")
    if state_machines:
        lines += ["## State-machine candidates", ""]
        for s in state_machines:
            vals=", ".join(str(x) for x in s.get("observed_values",[])) or "none observed"
            lines += [f"### {s.get('name') or s.get('id')}", "", f"Confidence: **{s.get('confidence')}**  ", f"Observed values: `{vals}`", "", "Stage/value meanings are not invented; inspect linked evidence before assigning semantics.", ""]
    return "\n".join(lines).rstrip()+"\n"
