#!/usr/bin/env python3
"""Evidence-first Project Codex generator for RPG Maker VX Ace normalized indexes."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from vxace_codex_lib.common import VERSION, load, dump, source_catalog
from vxace_codex_lib.inference import build_state_machines, build_quests, build_boss_gates, build_cutscenes, build_common_event_systems
from vxace_codex_lib.views import build_graph, build_map_codex, build_script_codex, markdown_summary

def generate(index_dir, output=None):
    root=Path(index_dir).expanduser().resolve(); out=Path(output).expanduser().resolve() if output else root/"codex"
    project=load(root/"project.json",{}) or {}; catalog=source_catalog(root)
    switches=load(root/"analysis"/"switches.json",[]) or []; variables=load(root/"analysis"/"variables.json",[]) or []
    callers=load(root/"analysis"/"common-event-callers.json",[]) or []; battles=load(root/"analysis"/"battle-troop-links.json",[]) or []; transfers=load(root/"analysis"/"map-transfers.json",[]) or []; script_calls=load(root/"analysis"/"script-calls-from-events.json",[]) or []
    state_machines=build_state_machines(variables,switches,catalog)
    systems=[]
    systems.extend(build_quests(variables,switches,callers,catalog)); systems.extend(build_boss_gates(switches,battles,catalog)); systems.extend(build_cutscenes(catalog)); systems.extend(build_common_event_systems(callers,catalog))
    graph=build_graph(switches,variables,callers,battles,transfers,catalog)
    maps=build_map_codex(project,catalog,switches,variables,callers,battles,transfers,script_calls); scripts=build_script_codex(root)
    index={"codex_version":VERSION,"project_name":project.get("project_name",root.name),"system_count":len(systems),"state_machine_count":len(state_machines),"map_entry_count":len(maps),"script_entry_count":len(scripts.get("scripts",[])),"systems":systems,"state_machines":state_machines,"principles":{"evidence_first":True,"invented_stage_meanings":False,"confidence_is_heuristic":True}}
    dump(out/"index.json",index); dump(out/"systems.json",systems); dump(out/"state-machines.json",state_machines); dump(out/"graph.json",graph); dump(out/"maps.json",maps); dump(out/"scripts.json",scripts)
    (out/"summary.md").write_text(markdown_summary(project,systems,state_machines),encoding="utf-8")
    return index


def main(argv=None):
    p=argparse.ArgumentParser(description="Generate an evidence-first Project Codex from a VX Ace normalized project index."); p.add_argument("index"); p.add_argument("--output"); p.add_argument("--version",action="version",version=f"%(prog)s {VERSION}"); a=p.parse_args(argv)
    try:
        result=generate(a.index,a.output); print(json.dumps({"status":"ok","codex_version":VERSION,"system_count":result["system_count"],"state_machine_count":result["state_machine_count"]}))
        return 0
    except Exception as e:
        print(f"error: {e}",file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
