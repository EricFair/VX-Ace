#!/usr/bin/env python3
"""Compare Project Codex outputs semantically instead of only by changed files."""
from __future__ import annotations
import argparse, json
from pathlib import Path
VERSION="0.10.0"

def load(p,d):
    try:
        with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
    except FileNotFoundError:return d

def canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def keyed(items,key="id"):
    return {str(x.get(key)):x for x in items if isinstance(x,dict) and x.get(key) is not None}

def diff_keyed(before,after):
    b,a=keyed(before),keyed(after); bk,ak=set(b),set(a)
    changed=[{"id":k,"before":b[k],"after":a[k]} for k in sorted(bk&ak) if canon(b[k])!=canon(a[k])]
    return {"added":[a[k] for k in sorted(ak-bk)],"removed":[b[k] for k in sorted(bk-ak)],"changed":changed}

def edge_key(e): return (str(e.get("from")),str(e.get("relation")),str(e.get("to")))
def diff_edges(before,after):
    b={edge_key(x):x for x in before if isinstance(x,dict)}; a={edge_key(x):x for x in after if isinstance(x,dict)}
    return {"added":[a[k] for k in sorted(set(a)-set(b))],"removed":[b[k] for k in sorted(set(b)-set(a))]}

def build(before:Path,after:Path):
    bs=load(before/"codex"/"systems.json",[]); ass=load(after/"codex"/"systems.json",[])
    bst=load(before/"codex"/"state-machines.json",[]); ast=load(after/"codex"/"state-machines.json",[])
    bg=load(before/"codex"/"graph.json",{}); ag=load(after/"codex"/"graph.json",{})
    bsc=load(before/"codex"/"scripts.json",{}); asc=load(after/"codex"/"scripts.json",{})
    if not isinstance(bs,list) or not isinstance(ass,list): raise ValueError("codex systems.json missing or invalid")
    systems=diff_keyed(bs,ass); states=diff_keyed(bst,ast)
    nodes=diff_keyed(bg.get("nodes",[]),ag.get("nodes",[])); edges=diff_edges(bg.get("edges",[]),ag.get("edges",[]))
    sb={str(x.get("path")):x for x in bsc.get("scripts",[]) if isinstance(x,dict) and x.get("path")}; sa={str(x.get("path")):x for x in asc.get("scripts",[]) if isinstance(x,dict) and x.get("path")}
    scripts={"added":[sa[k] for k in sorted(set(sa)-set(sb))],"removed":[sb[k] for k in sorted(set(sb)-set(sa))],
             "changed":[{"path":k,"before":sb[k],"after":sa[k]} for k in sorted(set(sb)&set(sa)) if canon(sb[k])!=canon(sa[k])]}
    sections={"systems":systems,"state_machines":states,"graph_nodes":nodes,"graph_edges":edges,"scripts":scripts}
    count=0
    for sec in sections.values(): count += sum(len(sec.get(k,[])) for k in ("added","removed","changed"))
    return {"semantic_diff_version":VERSION,"meaningful_change_count":count,"changed":count>0,"sections":sections,
            "interpretation":"These are changes in normalized Codex evidence/inferences. A changed heuristic inference still requires source verification."}

def dump(p,o): Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def markdown(r):
    lines=["# VX Ace Semantic Codex Diff","",f"Meaningful changes: **{r['meaningful_change_count']}**","",r["interpretation"],""]
    for name,sec in r["sections"].items():
        lines += [f"## {name.replace('_',' ').title()}","",f"- Added: {len(sec.get('added',[]))}",f"- Removed: {len(sec.get('removed',[]))}",f"- Changed: {len(sec.get('changed',[]))}",""]
    return "\n".join(lines)
def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("before"); ap.add_argument("after"); ap.add_argument("--json"); ap.add_argument("--markdown")
    a=ap.parse_args(argv)
    try:r=build(Path(a.before),Path(a.after))
    except Exception as e: print(f"error: {e}",file=__import__('sys').stderr); return 2
    if a.json: dump(a.json,r)
    if a.markdown: Path(a.markdown).write_text(markdown(r),encoding="utf-8")
    print(json.dumps({"status":"ok","meaningful_change_count":r["meaningful_change_count"]})); return 0
if __name__=="__main__": raise SystemExit(main())
