#!/usr/bin/env python3
"""Read-only RPG Maker VX Ace project indexer (v0.5)."""
from __future__ import annotations
import argparse, hashlib, json, re, shutil, subprocess, sys
from collections import defaultdict
from pathlib import Path

VERSION = "0.5.0"
DB_FILES = {"Actors.rvdata2":"actors.json","Classes.rvdata2":"classes.json","Skills.rvdata2":"skills.json","Items.rvdata2":"items.json","Weapons.rvdata2":"weapons.json","Armors.rvdata2":"armors.json","Enemies.rvdata2":"enemies.json","Troops.rvdata2":"troops.json","States.rvdata2":"states.json","Animations.rvdata2":"animations.json","Tilesets.rvdata2":"tilesets.json","CommonEvents.rvdata2":"common-events.json","System.rvdata2":"system.json","MapInfos.rvdata2":"map-infos.json"}
MAP_RE = re.compile(r"^Map(\d{3})\.rvdata2$", re.I)

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def dump_json(path,obj):
    Path(path).parent.mkdir(parents=True,exist_ok=True); Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def project_dirs(path):
    p=Path(path).expanduser().resolve(); root=p.parent if p.is_file() and p.suffix.lower()==".rvproj2" else p; data=root/"Data"
    if not root.is_dir() or not data.is_dir(): raise ValueError(f"Not a VX Ace project (missing Data/): {root}")
    return root,data

def ruby_path(explicit=None):
    r=explicit or shutil.which("ruby")
    if r and Path(r).exists(): return str(r)
    raise RuntimeError("Ruby not found. v0.5 requires Ruby for read-only Marshal decoding; pass --ruby PATH.")

def run_bridge(ruby,bridge,mode,src):
    p=subprocess.run([ruby,str(bridge),mode,str(src)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout).decode("utf-8","replace").strip())
    return json.loads(p.stdout.decode("utf-8","replace"))

def key(v):
    if isinstance(v,str): return v
    if isinstance(v,(int,float,bool)) or v is None: return str(v).lower() if v is not None else "null"
    if isinstance(v,dict) and "__symbol__" in v: return str(v["__symbol__"])
    return json.dumps(v,ensure_ascii=False,sort_keys=True)

def normalize(v):
    if isinstance(v,list): return [normalize(x) for x in v]
    if not isinstance(v,dict): return v
    if "__array__" in v: return [normalize(x) for x in v["__array__"]]
    if "__hash__" in v: return {key(normalize(k)):normalize(x) for k,x in v["__hash__"]}
    if set(v)=={"__symbol__"} or set(v)=={"__ref__"}: return v
    return {k:normalize(x) for k,x in v.items() if k!="__id__"}

def walk(v,path=()):
    yield path,v
    if isinstance(v,dict):
        for k,x in v.items(): yield from walk(x,path+(k,))
    elif isinstance(v,list):
        for i,x in enumerate(v): yield from walk(x,path+(i,))

def commands(v):
    out=[]
    for p,x in walk(v):
        if isinstance(x,dict) and x.get("__class__")=="RPG::EventCommand": out.append({"path":list(p),"code":x.get("code"),"indent":x.get("indent"),"parameters":x.get("parameters",[])})
    return out

def ctx(kind,file,c):
    p=c["path"]; d={"kind":kind,"file":file,"command_path":p,"command_code":c.get("code")}
    if kind=="map":
        m=re.search(r"map-(\d{3})\.json$",file,re.I)
        if m: d["map_id"]=int(m.group(1))
        for marker,name,add in (("events","event_id",0),("pages","page",1),("list","command_index",0)):
            try: d[name]=int(p[p.index(marker)+1])+add
            except (ValueError,IndexError,TypeError): pass
    elif kind=="common_event":
        if p and isinstance(p[0],int): d["common_event_id"]=p[0]
        try: d["command_index"]=int(p[p.index("list")+1])
        except (ValueError,IndexError,TypeError): pass
    return d

def ip(params,i):
    try: return int(params[i]) if isinstance(params[i],(int,float)) else None
    except (IndexError,TypeError,ValueError): return None

def index_commands(sets,switch_names,variable_names,map_names,ce_names,troop_names):
    sr,sw,vr,vw=defaultdict(list),defaultdict(list),defaultdict(list),defaultdict(list); selfw=[]; callers=defaultdict(list); transfers=[]; battles=[]; scripts=[]
    for kind,file,cs in sets:
        i=0
        while i<len(cs):
            c=cs[i]; code=c.get("code"); p=c.get("parameters") or []; base=ctx(kind,file,c)
            if code==117:
                n=ip(p,0)
                if n is not None: callers[n].append(base)
            elif code==121:
                a,b=ip(p,0),ip(p,1)
                if a is not None and b is not None:
                    for n in range(a,b+1): sw[n].append({**base,"value":ip(p,2)})
            elif code==122:
                a,b=ip(p,0),ip(p,1)
                if a is not None and b is not None:
                    for n in range(a,b+1): vw[n].append({**base,"operation":ip(p,2)})
                if ip(p,3)==1 and ip(p,4) is not None: vr[ip(p,4)].append({**base,"role":"operand"})
            elif code==123: selfw.append({**base,"letter":p[0] if p else None,"value":p[1] if len(p)>1 else None})
            elif code==111:
                typ=ip(p,0)
                if typ==0 and ip(p,1) is not None: sr[ip(p,1)].append({**base,"role":"conditional"})
                elif typ==1:
                    if ip(p,1) is not None: vr[ip(p,1)].append({**base,"role":"conditional-left"})
                    if ip(p,2)==1 and ip(p,3) is not None: vr[ip(p,3)].append({**base,"role":"conditional-right"})
            elif code==201:
                direct=ip(p,0)==0; item={**base,"designation":"direct" if direct else "variables","parameters":p}
                if direct:
                    mid=ip(p,1); item.update(map_id=mid,map_name=map_names.get(mid,""),x=ip(p,2),y=ip(p,3))
                else:
                    item.update(map_variable_id=ip(p,1),x_variable_id=ip(p,2),y_variable_id=ip(p,3))
                    for role,j in (("map",1),("x",2),("y",3)):
                        n=ip(p,j)
                        if n is not None: vr[n].append({**base,"role":"transfer-"+role})
                transfers.append(item)
            elif code==301:
                typ=ip(p,0); item={**base,"designation":typ,"parameters":p}
                if typ==0:
                    tid=ip(p,1); item.update(troop_id=tid,troop_name=troop_names.get(tid,""))
                elif typ==1:
                    n=ip(p,1); item["troop_variable_id"]=n
                    if n is not None: vr[n].append({**base,"role":"battle-troop"})
                battles.append(item)
            elif code==355:
                lines=[str(p[0])] if p else []; j=i+1
                while j<len(cs) and cs[j].get("code")==655:
                    q=cs[j].get("parameters") or []
                    if q: lines.append(str(q[0]))
                    j+=1
                scripts.append({**base,"text":"\n".join(lines)}); i=j-1
            i+=1
    def named(reads,writes,names): return [{"id":n,"name":names[n] if n<len(names) and names[n] else "","reads":reads.get(n,[]),"writes":writes.get(n,[])} for n in sorted(set(reads)|set(writes))]
    return {"switches":named(sr,sw,switch_names),"variables":named(vr,vw,variable_names),"self_switch_writes":selfw,"common_event_callers":[{"common_event_id":n,"name":ce_names.get(n,""),"callers":x} for n,x in sorted(callers.items())],"map_transfers":transfers,"battle_troop_links":battles,"script_calls_from_events":scripts}

def names_array(v):
    out={}
    if isinstance(v,list):
        for i,x in enumerate(v):
            if isinstance(x,dict):
                try: n=int(x.get("id",i))
                except Exception: n=i
                out[n]=str(x.get("name") or "")
    return out

def names_maps(v):
    out={}
    if isinstance(v,dict):
        for k,x in v.items():
            if isinstance(x,dict):
                try: out[int(k)]=str(x.get("name") or "")
                except Exception: pass
    return out

def compatibility(tools,scripts,order,analysis):
    analyzer=tools/"rgss3_analyzer.py"
    if not analyzer.is_file(): return {"status":"skipped","reason":"analyzer missing"}
    jo=analysis/"script-compatibility.json"; md=analysis/"script-compatibility.md"
    p=subprocess.run([sys.executable,str(analyzer),str(scripts),"--order",str(order),"--json",str(jo),"--markdown",str(md)],capture_output=True,text=True)
    return {"status":"ok","json":jo.name,"markdown":md.name} if p.returncode==0 else {"status":"failed","returncode":p.returncode,"stderr":p.stderr.strip()}

def read_project(project,output,ruby=None,bridge=None,run_compat=True):
    root,data=project_dirs(project); tools=Path(__file__).resolve().parent; rb=Path(bridge or tools/"rvdata2_bridge.rb").resolve(); r=ruby_path(ruby); out=Path(output).expanduser().resolve()
    if out==root or root in out.parents: raise RuntimeError("Refusing output inside source project; choose a separate directory.")
    out.mkdir(parents=True,exist_ok=True); files=[]
    for p in sorted((x for x in root.rglob("*") if x.is_file()),key=lambda x:str(x).lower()): files.append({"path":p.relative_to(root).as_posix(),"size":p.stat().st_size,"sha256":sha256(p)})
    dump_json(out/"manifest.json",{"reader_version":VERSION,"project_name":root.name,"source_file_count":len(files),"files":files,"read_only":True,"source_path_omitted":True})
    dbdir,mapsdir,scriptsdir,adir=[out/x for x in ("database","maps","scripts","analysis")]
    for d in (dbdir,mapsdir,scriptsdir,adir): d.mkdir(exist_ok=True)
    decoded={}; errors=[]
    for src,dst in DB_FILES.items():
        p=data/src
        if p.is_file():
            try: decoded[src]=normalize(run_bridge(r,rb,"dump",p)); dump_json(dbdir/dst,decoded[src])
            except Exception as e: errors.append({"file":src,"error":str(e)})
    sets=[]; maps=[]
    for p in sorted((x for x in data.iterdir() if x.is_file() and MAP_RE.match(x.name)),key=lambda x:x.name.lower()):
        mid=int(MAP_RE.match(p.name).group(1))
        try:
            obj=normalize(run_bridge(r,rb,"dump",p)); dest=mapsdir/f"map-{mid:03d}.json"; dump_json(dest,obj); cs=commands(obj); sets.append(("map",dest.name,cs)); maps.append({"map_id":mid,"file":dest.name,"event_command_count":len(cs)})
        except Exception as e: errors.append({"file":p.name,"error":str(e)})
    if "CommonEvents.rvdata2" in decoded: sets.append(("common_event","common-events.json",commands(decoded["CommonEvents.rvdata2"])))
    order=[]; sp=data/"Scripts.rvdata2"
    if sp.is_file():
        try:
            for e in run_bridge(r,rb,"scripts",sp).get("scripts",[]):
                i=int(e.get("index",len(order))); name=re.sub(r'[\\/:*?"<>|\x00-\x1f]+','_',str(e.get("name","")).strip()) or "unnamed"; fn=f"{i:03d}_{name[:80]}.rb"; (scriptsdir/fn).write_text(str(e.get("source","")),encoding="utf-8"); order.append({"index":i,"id":e.get("id"),"name":e.get("name",""),"path":fn})
            dump_json(scriptsdir/"order.json",{"scripts":order})
        except Exception as e: errors.append({"file":"Scripts.rvdata2","error":str(e)})
    system=decoded.get("System.rvdata2",{}); sw=system.get("switches",[]) if isinstance(system,dict) else []; vr=system.get("variables",[]) if isinstance(system,dict) else []; sw=[str(x or "") if not isinstance(x,dict) else "" for x in sw] if isinstance(sw,list) else []; vr=[str(x or "") if not isinstance(x,dict) else "" for x in vr] if isinstance(vr,list) else []
    mn=names_maps(decoded.get("MapInfos.rvdata2",{})); cen=names_array(decoded.get("CommonEvents.rvdata2",[])); tn=names_array(decoded.get("Troops.rvdata2",[])); [m.__setitem__("name",mn.get(m["map_id"],"")) for m in maps]
    a=index_commands(sets,sw,vr,mn,cen,tn); mapping={"switches":"switches.json","variables":"variables.json","self_switch_writes":"self-switch-writes.json","common_event_callers":"common-event-callers.json","map_transfers":"map-transfers.json","battle_troop_links":"battle-troop-links.json","script_calls_from_events":"script-calls-from-events.json"}
    for k,f in mapping.items(): dump_json(adir/f,a[k])
    dump_json(adir/"event-references.json",a); comp=compatibility(tools,scriptsdir,scriptsdir/"order.json",adir) if run_compat and order else {"status":"skipped","reason":"disabled or no scripts"}
    summary={"reader_version":VERSION,"project_name":root.name,"database_files_decoded":sorted(decoded),"map_count":len(maps),"maps":maps,"script_count":len(order),"switches_referenced":len(a["switches"]),"variables_referenced":len(a["variables"]),"common_event_links":len(a["common_event_callers"]),"map_transfers":len(a["map_transfers"]),"battle_links":len(a["battle_troop_links"]),"event_script_blocks":len(a["script_calls_from_events"]),"compatibility_analysis":comp,"errors":errors,"read_only":True}; dump_json(out/"project.json",summary); return summary

def main(argv=None):
    p=argparse.ArgumentParser(description="Create a read-only normalized index of an RPG Maker VX Ace project."); p.add_argument("project"); p.add_argument("--output"); p.add_argument("--ruby"); p.add_argument("--bridge"); p.add_argument("--no-compat",action="store_true"); p.add_argument("--version",action="version",version=f"%(prog)s {VERSION}"); a=p.parse_args(argv)
    try: root,_=project_dirs(a.project); out=Path(a.output) if a.output else root.parent/f"{root.name}-project-index"; s=read_project(a.project,out,a.ruby,a.bridge,not a.no_compat)
    except Exception as e: print(f"VX Ace project reader error: {e}",file=sys.stderr); return 1
    print(json.dumps({"status":"ok" if not s["errors"] else "partial","output":str(Path(out).resolve()),"maps":s["map_count"],"scripts":s["script_count"],"errors":len(s["errors"])},ensure_ascii=False)); return 0 if not s["errors"] else 3

if __name__=="__main__": raise SystemExit(main())
