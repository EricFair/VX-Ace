#!/usr/bin/env python3
"""Generate reversible, project-aware VX Ace patch plans without writing source data."""
from __future__ import annotations
import argparse, difflib, hashlib, json, sys
from pathlib import Path

VERSION = "1.0.0"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_rel(value: str) -> str:
    p = Path(value)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"Unsafe relative path: {value}")
    return p.as_posix()


def validate_index(index: Path) -> dict:
    manifest = index / "manifest.json"
    if not manifest.is_file():
        raise ValueError(f"Missing manifest.json in index: {index}")
    data = load_json(manifest)
    if not data.get("read_only"):
        raise ValueError("Index manifest is not marked read-only")
    if not isinstance(data.get("files"), list):
        raise ValueError("Index manifest has no file inventory")
    return data


def verify_freshness(manifest: dict, project: Path) -> dict:
    project = project.resolve()
    problems = []
    checked = 0
    for entry in manifest.get("files", []):
        rel = safe_rel(str(entry.get("path", "")))
        src = project / rel
        expected = str(entry.get("sha256") or "")
        if not src.is_file():
            problems.append({"path": rel, "reason": "missing"})
            continue
        checked += 1
        actual = sha256(src)
        if expected and actual != expected:
            problems.append({"path": rel, "reason": "hash_mismatch", "expected": expected, "actual": actual})
    return {"status": "fresh" if not problems else "stale", "checked": checked, "problems": problems}


def normalize_spec(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise ValueError("Patch spec must be a JSON object")
    changes = spec.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("Patch spec requires a non-empty changes array")
    out = {"title": str(spec.get("title") or "VX Ace patch plan"), "summary": str(spec.get("summary") or ""), "changes": []}
    for i, raw in enumerate(changes, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"Change #{i} must be an object")
        kind = raw.get("kind")
        if kind not in {"script", "script_slot", "event", "database", "map_region", "map_tile", "map_event", "map_entry", "database_entry", "map_name", "map_label", "map_encounter", "map_shop"}:
            raise ValueError(f"Change #{i} has unsupported kind: {kind}")
        item = dict(raw)
        if kind == "script":
            item["script_path"] = safe_rel(str(item.get("script_path") or ""))
            if not item["script_path"]:
                raise ValueError(f"Script change #{i} requires script_path")
            if "search" not in item or "replace" not in item:
                raise ValueError(f"Script change #{i} requires search and replace")
            item["search"] = str(item["search"]); item["replace"] = str(item["replace"])
            if not item["search"]:
                raise ValueError(f"Script change #{i} search block cannot be empty")
        elif kind == 'script_slot':
            locator=item.get('locator')
            if not isinstance(locator,dict) or set(locator)!={'before_index'} or type(locator['before_index']) is not int or not 0<=locator['before_index']<=4095 or not item.get('proposal'):
                raise ValueError('Script slot proposal requires exact before_index locator and proposal')
        elif kind == 'map_entry':
            locator=item.get('locator')
            if not isinstance(locator,dict) or set(locator)!={'template_map_id'} or type(locator['template_map_id']) is not int or not 1<=locator['template_map_id']<=999 or not item.get('proposal'):
                raise ValueError('Map append proposal requires template_map_id and proposal')
        elif kind == 'database_entry':
            locator=item.get('locator');mutation=item.get('mutation')
            if isinstance(locator,dict) and locator.get('table')=='classes':
                from vxace_class_learning import native_mutation
                native_mutation(locator,mutation)
                if not item.get('proposal'):raise ValueError('Class learning requires a proposal')
            else:
                if not isinstance(locator,dict) or set(locator)!={'table'} or locator['table'] not in ('items','enemies','skills','states','weapons','armors','troops') or not item.get('proposal'):
                    raise ValueError('Database entry proposal requires an exact supported table locator and proposal')
                action=mutation.get('action') if isinstance(mutation,dict) else None
                if (locator['table']=='items',action) not in ((True,'append_key_item'),(False,'append_database_entry')):
                    raise ValueError('Entry action does not match the table (items: append_key_item; others: append_database_entry)')
        elif kind == 'map_shop':
            locator=item.get('locator')
            if not isinstance(locator,dict) or set(locator)!={'map_id','event_id'} or any(type(locator[k]) is not int or not 1<=locator[k]<=999 for k in locator):
                raise ValueError('Shop proposal requires exact map_id and event_id locator')
            if not item.get('proposal'):
                raise ValueError('Shop proposal requires proposal')
        elif kind in ('map_region','map_tile','map_event','map_name','map_label','map_encounter'):
            locator=item.get('locator')
            if not isinstance(locator,dict) or set(locator) != {'map_id'} or type(locator['map_id']) is not int or not 1 <= locator['map_id'] <= 999999:
                raise ValueError('Region change requires exact map_id locator')
            if not item.get('proposal'):
                raise ValueError('Region change requires proposal')
        elif kind == "event":
            locator = item.get("locator")
            if not isinstance(locator, dict) or not any(k in locator for k in ("map_id", "common_event_id", "troop_id")):
                raise ValueError(f"Event change #{i} requires locator with map_id/common_event_id/troop_id")
            if not item.get("proposal"):
                raise ValueError(f"Event change #{i} requires proposal")
        else:
            locator = item.get("locator")
            if not isinstance(locator, dict) or not locator.get("table"):
                raise ValueError(f"Database change #{i} requires locator.table")
            if "id" not in locator:
                raise ValueError(f"Database change #{i} requires locator.id")
            if not item.get("proposal"):
                raise ValueError(f"Database change #{i} requires proposal")
        out["changes"].append(item)
    return out


def script_diff(index: Path, change: dict) -> dict:
    rel = change["script_path"]
    src = (index / "scripts" / rel).resolve()
    scripts_root = (index / "scripts").resolve()
    if scripts_root not in src.parents:
        raise ValueError(f"Script path escapes scripts/: {rel}")
    if not src.is_file():
        raise ValueError(f"Indexed script not found: scripts/{rel}")
    original = src.read_bytes().decode('utf-8','strict')
    count = original.count(change["search"])
    if count != 1:
        raise ValueError(f"Expected search block exactly once in {rel}; found {count}")
    proposed = original.replace(change["search"], change["replace"], 1)
    diff = "".join(difflib.unified_diff(original.splitlines(True), proposed.splitlines(True), fromfile=f"a/scripts/{rel}", tofile=f"b/scripts/{rel}", n=3))
    return {"kind":"script","script_path":rel,"description":str(change.get("description") or ""),"risk":str(change.get("risk") or "medium"),"diff":diff,"original_sha256":sha256(src),"apply_mode":"proposal_only"}


def structural_change(change: dict) -> dict:
    return {"kind":change["kind"],"locator":change["locator"],"description":str(change.get("description") or ""),"proposal":change.get("proposal"),"evidence":change.get("evidence",[]),"risk":str(change.get("risk") or "medium"),"apply_mode":"manual_or_future_verified_writer"}


def script_slot_plan(index,project,change):
    from vxace_index_query import Index,unlinked
    from vxace_script_slots import indexed_snapshot,new_slot
    from vxace_python_mutator import load
    locator=change['locator'];mutation=change.get('mutation')
    if not isinstance(mutation,dict) or 'before_index' in mutation:raise ValueError('Script slot mutation cannot override locator')
    data=Index(index);snapshot=indexed_snapshot(data,project,locator['before_index'])
    new_slot(load(unlinked(project/'Data/Scripts.rvdata2'))[0],{'before_index':locator['before_index'],**mutation})
    data.unchanged()
    raw=mutation['source'].encode('utf-8','strict')
    result=structural_change(change)
    result.update(apply_mode='proposal_only',risk='high',new_id=mutation['new_id'],name=mutation['name'],
                  source_sha256=hashlib.sha256(raw).hexdigest(),source_bytes=len(raw),
                  archive_sha256=snapshot['archive_sha256'],anchor_sha256=snapshot['anchor_sha256'],
                  diff=''.join(difflib.unified_diff([],mutation['source'].splitlines(True),fromfile='/dev/null',tofile='new-script-slot-source')))
    return result


def regression_checks(changes: list[dict]) -> list[str]:
    checks=["Verify the source project still matches the indexed manifest before applying anything.","Apply changes to a copy or with a restorable backup first.","Launch the project and reproduce the original scenario before testing the change."]
    kinds={c["kind"] for c in changes}
    if "script" in kinds or 'script_slot' in kinds:
        checks += ["Check Script Editor load order and overlapping aliases/overrides for every touched method.","Start a new game and load at least one existing save if the script touches persistent state."]
    if "event" in kinds:
        checks += ["Test the affected event from a fresh map entry, repeated interaction, map transfer away/back, and save/load.","Confirm active event page/trigger and that autoruns terminate or parallels yield as designed."]
    if "database" in kinds:
        checks += ["Test every database object changed in the editor and in-game, including actor/enemy variants where applicable.","Confirm the change does not duplicate native trait/effect or damage-pipeline behavior."]
    if 'map_region' in kinds:
        checks += ['Review native encounter region sets and custom region consumers before staging.',
                   'Verify the region overlay in VX Ace; test new game, older-save map reload and restart-based save/load.',
                   'Confirm graphic layers and all lower metadata bytes are unchanged; no tile/region resizing is enabled.']
    if 'database_entry' in kinds:
        checks += ['Review dynamic item IDs, inventory extensions and template/note consumers before appending a key item.',
                   'Verify the new ID/Key Item entry in VX Ace, native inventory categorization and engine save/restart-load.',
                   'Confirm every existing Items entry is unchanged; deletion/reuse/reordering remain disabled.']
    if any(i.get('kind')=='database_entry' and i.get('mutation',{}).get('action')=='append_database_entry' for i in changes):
        checks += ['Review every inherited feature, effect, drop, action and damage element/type of the template clone; the note is forced empty (troops have no note and copy only a blank battle page).',
                   'Review troops, shops, drops, dynamic IDs and notetag consumers; check battler_name against the asset audit.',
                   'Verify the new entry in the VX Ace editor, a battle test or smoke test, and engine save/full-process restart.']
    if any(i.get('kind')=='database_entry' and i.get('mutation',{}).get('action')=='append_class_learning' for i in changes):
        checks += ['Review the class existing learnings, the skill (cost, scope, damage) and the level; the new learning has an empty note and is appended last.',
                   'Check actor initial levels, class-change scripts and custom skill-learning scripts; old saves learn the skill only on a later level-up (no retroactive learning).',
                   'Verify the class in the VX Ace editor and level an actor of that class to or past the level in a new game and an older save.']
    if 'script_slot' in kinds:
        checks += ['Insert only one exact byte-verified native slot before unique canonical Main through the explicit Python copy workflow.',
                   'Verify every existing script ID/name/source/order is preserved; no reordering/deletion or other Scripts edits in the transaction.',
                   'Review new source collisions/dependencies, native compilation, editor order and old-save/restart-based behavior.']
    if 'map_entry' in kinds:
        checks += ['Review dynamic map IDs/loaders, old save state and existing tile/region consumers before appending a static map.',
                   'Verify the new root map and empty event list in VX Ace, native transfer/render/movement and save/full-process restart.',
                   'Confirm all existing maps, old tree entries, System/version and other copied files are unchanged.']
    if 'map_name' in kinds:
        checks += ['Review custom display_name, map-loading and save hooks; native map-name windows are project-specific.',
                   'Verify the display name in VX Ace, actual map-name window, older-save reload, movement and save/full-process restart.',
                   'Confirm only the native display_name and reload version changed; editor/tree names and all other copied files stay unchanged.']
    if 'map_encounter' in kinds:
        checks += ['Review the referenced troop, its enemies and battle events, plus custom encounter/region consumers, before staging.',
                   'Verify the new entry in the VX Ace map properties, a random battle on the intended area (encounters enabled), older-save map reload and restart-based save/load.',
                   'Confirm only encounter_list (and an optional encounter_step) changed; the map Table, events, Troops and all other copied files stay unchanged.']
    if 'map_shop' in kinds:
        checks += ['Review custom shop scenes/scripts, price or stock consumers and the chosen goods (names, database prices, key-item status) before staging.',
                   'Verify the Shop Processing command in the VX Ace editor, open the shop in play (buy and, unless purchase-only, sell), test an older save (map reload) and restart-based save/load.',
                   'Confirm only that event page list gained the shop rows; Items/Weapons/Armors, every other map field and event, and all other copied files stay unchanged.']
    if 'map_label' in kinds:
        checks += ['Review custom MapInfos/name caches/map/save consumers; labels are not map IDs or display names.',
                   'Verify the native editor tree/Name field, unchanged display-name window and new-process older-save/movement/save/restart behavior.',
                   'Confirm only the selected MapInfo.name changed; all maps, System/version, other metadata and prior saves stay unchanged.']
    checks.append("Re-run the Project Reader and compare the new index/codex against the pre-change snapshot.")
    return checks


def render_markdown(plan: dict) -> str:
    lines=[f"# {plan['title']}","",plan.get("summary",""),"","## Safety status","",f"- Index freshness: **{plan['freshness']['status']}**","- Source mutation by this planner: **none**","- `.rvdata2` binary writing: **disabled**","","## Proposed changes",""]
    for i,change in enumerate(plan["changes"],1):
        lines.append(f"### {i}. {change['kind'].title()} change")
        if change.get("description"): lines.append(change["description"])
        if change["kind"] in ("script",'script_slot'):
            target='scripts/'+change['script_path'] if change['kind']=='script' else 'New slot '+change['name']+' before index '+str(change['locator']['before_index'])
            lines += ["",f"Target: `{target}`","","```diff",change["diff"].rstrip(),"```",""]
        else:
            lines += ["","Locator:","","```json",json.dumps(change["locator"],ensure_ascii=False,indent=2),"```","","Proposal:","","```json",json.dumps(change["proposal"],ensure_ascii=False,indent=2),"```",""]
    lines += ["## Regression checklist",""]+[f"- {x}" for x in plan["regression_checks"]]+["","## Rollback","","This planner does not modify the source project. If a human or later verified writer applies the plan, preserve the pre-change project/script files and restore them if any regression fails.",""]
    return "\n".join(lines)


def build_plan(index: Path, project: Path, spec_path: Path, output: Path) -> dict:
    from vxace_index_query import unlinked
    index=unlinked(index);project=unlinked(project);output=unlinked(output)
    if project.is_file() and project.suffix.lower()=='.rvproj2':project=project.parent
    if not (project/'Data').is_dir():raise ValueError('Expected a VX Ace project with Data/')
    if output.exists() or any(output==root or root in output.parents for root in (index,project)):
        raise ValueError('Use a new plan directory outside the source project and index')
    manifest=validate_index(index); freshness=verify_freshness(manifest,project)
    if freshness["status"]!="fresh":
        raise RuntimeError("STALE_INDEX:"+json.dumps(freshness,ensure_ascii=False))
    spec=normalize_spec(load_json(spec_path)); changes=[]
    for change in spec["changes"]:
        rows=(change.get('mutation') or {}).get('commands',[])
        if change['kind']=='event' and isinstance(rows,list) and any(isinstance(row,dict) and type(row.get('code')) is int and row['code']==201 for row in rows):
            from vxace_copy_patcher import normalize_changes
            from vxace_event_structure import validate_project_references
            proposed=normalize_changes(index,{'changes':[change]})[0]
            validate_project_references(index,proposed['ruby_spec']['mutation'],project/proposed['target'])
            changes.append(structural_change(change))
        elif change['kind']=='script':changes.append(script_diff(index,change))
        elif change['kind']=='script_slot':changes.append(script_slot_plan(index,project,change))
        elif change['kind']=='map_label':
            if len(spec['changes'])!=1:raise ValueError('Map-tree name edit requires its own single-change plan')
            from vxace_map_labels import indexed_snapshot,validate as validate_label
            from vxace_index_query import Index,unlinked
            from vxace_python_mutator import load
            from vxace_copy_patcher import normalize_changes
            proposed=normalize_changes(index,{'changes':[change]})[0]
            data=Index(index);snap=indexed_snapshot(data,project,proposed['locator']['map_id']);data.unchanged()
            _,value=validate_label(load(unlinked(project/proposed['target']))[0],proposed['mutation'],project)
            planned=structural_change(change)
            planned.update(apply_mode='proposal_only',risk='high',before=snap['name'],after=value,guard=snap['guard'])
            changes.append(planned)
        elif change['kind']=='map_name':
            if len(spec['changes'])!=1:raise ValueError('Display-name edit requires its own single-change plan')
            from vxace_map_names import indexed_snapshot,validate as validate_name
            from vxace_index_query import Index,unlinked
            from vxace_python_mutator import load
            from vxace_copy_patcher import normalize_changes
            proposed=normalize_changes(index,{'changes':[change]})[0]
            data=Index(index);snap=indexed_snapshot(data,project,proposed['locator']['map_id']);data.unchanged()
            value=validate_name(load(unlinked(project/proposed['target']))[0],proposed['mutation'])
            planned=structural_change(change)
            planned.update(apply_mode='proposal_only',risk='high',before=snap['display_name'],after=value,map_sha256=snap['map_sha256'])
            changes.append(planned)
        elif change['kind']=='map_shop':
            if len(spec['changes'])!=1:raise ValueError('Shop append requires its own single-change plan')
            from vxace_map_shops import indexed_snapshot,validate as validate_shop,goods_arrays
            from vxace_index_query import Index,unlinked
            from vxace_python_mutator import load
            from vxace_copy_patcher import normalize_changes
            proposed=normalize_changes(index,{'changes':[change]})[0]
            data=Index(index);snap=indexed_snapshot(data,project,proposed['locator']['map_id'],proposed['locator']['event_id']);data.unchanged()
            _,evidence=validate_shop(load(unlinked(project/proposed['target']))[0],proposed['ruby_spec']['mutation'],goods_arrays(project/proposed['target']))
            planned=structural_change(change)
            planned.update(apply_mode='proposal_only',risk='high',event_shape=evidence['event_shape'],goods=evidence['goods'],
                           purchase_only=evidence['purchase_only'],map_sha256=snap['map_sha256'],event_sha256=snap['event_sha256'])
            changes.append(planned)
        elif change['kind']=='map_encounter':
            if len(spec['changes'])!=1:raise ValueError('Encounter append requires its own single-change plan')
            from vxace_map_encounters import indexed_snapshot,validate as validate_encounter,troops_for
            from vxace_index_query import Index,unlinked
            from vxace_python_mutator import load
            from vxace_copy_patcher import normalize_changes
            proposed=normalize_changes(index,{'changes':[change]})[0]
            data=Index(index);snap=indexed_snapshot(data,project,proposed['locator']['map_id']);data.unchanged()
            row,step=validate_encounter(load(unlinked(project/proposed['target']))[0],proposed['mutation'],troops_for(project/proposed['target']))
            planned=structural_change(change)
            planned.update(apply_mode='proposal_only',risk='high',before={'encounters':snap['encounters'],'encounter_step':snap['encounter_step']},
                           added={'troop_id':row[0],'weight':row[1],'region_set':row[2]},encounter_step=step,
                           map_sha256=snap['map_sha256'],troops_sha256=snap['troops_sha256'])
            changes.append(planned)
        elif change['kind']=='map_entry':
            from vxace_maps import snapshot as map_snapshot,candidates as map_candidates
            from vxace_index_query import Index
            from vxace_python_mutator import load
            from vxace_copy_patcher import normalize_changes
            proposed=normalize_changes(index,{'changes':[change]})[0]
            data=Index(index);map_snapshot(data,project,proposed['mutation']['template_map_id']);data.unchanged()
            map_candidates(load(project/'Data/MapInfos.rvdata2')[0],proposed['mutation'],project)
            changes.append(structural_change(change))
        else:changes.append(structural_change(change))
    plan={"planner_version":VERSION,"title":spec["title"],"summary":spec["summary"],"index":str(index),"source_path_omitted_from_persistent_output":True,"freshness":freshness,"changes":changes,"regression_checks":regression_checks(changes),"rollback":{"source_modified":False,"strategy":"restore pre-change backup or script copy if later applied"},"binary_writer_enabled":False}
    output.mkdir(parents=True,exist_ok=True); dump_json(output/"plan.json",plan); (output/"plan.md").write_text(render_markdown(plan),encoding="utf-8")
    return plan


def main(argv=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("index",help="Project Reader index directory")
    ap.add_argument("--project",required=True,help="Current source VX Ace project directory for freshness verification")
    ap.add_argument("--spec",required=True,help="JSON patch specification")
    ap.add_argument("--output",required=True,help="Output directory for proposal-only patch plan")
    args=ap.parse_args(argv)
    try:
        plan=build_plan(Path(args.index),Path(args.project),Path(args.spec),Path(args.output))
    except RuntimeError as e:
        msg=str(e)
        if msg.startswith("STALE_INDEX:"):
            print(json.dumps({"status":"refused","reason":"stale_index","details":json.loads(msg.split(":",1)[1])},ensure_ascii=False),file=sys.stderr); return 3
        print(f"error: {e}",file=sys.stderr); return 2
    except Exception as e:
        print(f"error: {e}",file=sys.stderr); return 2
    print(json.dumps({"status":"ok","change_count":len(plan["changes"]),"output":str(Path(args.output).resolve())},ensure_ascii=False)); return 0


if __name__=="__main__":
    raise SystemExit(main())
