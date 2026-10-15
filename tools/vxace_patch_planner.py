#!/usr/bin/env python3
"""Generate reversible, project-aware VX Ace patch plans without writing source data."""
from __future__ import annotations
import argparse, difflib, hashlib, json, sys
from pathlib import Path

VERSION = "0.19.0"


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
        if kind not in {"script", "event", "database", "map_region"}:
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
        elif kind == 'map_region':
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
    original = src.read_text(encoding="utf-8")
    count = original.count(change["search"])
    if count != 1:
        raise ValueError(f"Expected search block exactly once in {rel}; found {count}")
    proposed = original.replace(change["search"], change["replace"], 1)
    diff = "".join(difflib.unified_diff(original.splitlines(True), proposed.splitlines(True), fromfile=f"a/scripts/{rel}", tofile=f"b/scripts/{rel}", n=3))
    return {"kind":"script","script_path":rel,"description":str(change.get("description") or ""),"risk":str(change.get("risk") or "medium"),"diff":diff,"original_sha256":sha256(src),"apply_mode":"proposal_only"}


def structural_change(change: dict) -> dict:
    return {"kind":change["kind"],"locator":change["locator"],"description":str(change.get("description") or ""),"proposal":change.get("proposal"),"evidence":change.get("evidence",[]),"risk":str(change.get("risk") or "medium"),"apply_mode":"manual_or_future_verified_writer"}


def regression_checks(changes: list[dict]) -> list[str]:
    checks=["Verify the source project still matches the indexed manifest before applying anything.","Apply changes to a copy or with a restorable backup first.","Launch the project and reproduce the original scenario before testing the change."]
    kinds={c["kind"] for c in changes}
    if "script" in kinds:
        checks += ["Check Script Editor load order and overlapping aliases/overrides for every touched method.","Start a new game and load at least one existing save if the script touches persistent state."]
    if "event" in kinds:
        checks += ["Test the affected event from a fresh map entry, repeated interaction, map transfer away/back, and save/load.","Confirm active event page/trigger and that autoruns terminate or parallels yield as designed."]
    if "database" in kinds:
        checks += ["Test every database object changed in the editor and in-game, including actor/enemy variants where applicable.","Confirm the change does not duplicate native trait/effect or damage-pipeline behavior."]
    if 'map_region' in kinds:
        checks += ['Review native encounter region sets and custom region consumers before staging.',
                   'Verify the region overlay in VX Ace; test new game, older-save map reload and restart-based save/load.',
                   'Confirm graphic layers and all lower metadata bytes are unchanged; no tile/region resizing is enabled.']
    checks.append("Re-run the Project Reader and compare the new index/codex against the pre-change snapshot.")
    return checks


def render_markdown(plan: dict) -> str:
    lines=[f"# {plan['title']}","",plan.get("summary",""),"","## Safety status","",f"- Index freshness: **{plan['freshness']['status']}**","- Source mutation by this planner: **none**","- `.rvdata2` binary writing: **disabled**","","## Proposed changes",""]
    for i,change in enumerate(plan["changes"],1):
        lines.append(f"### {i}. {change['kind'].title()} change")
        if change.get("description"): lines.append(change["description"])
        if change["kind"]=="script":
            lines += ["",f"Target: `scripts/{change['script_path']}`","","```diff",change["diff"].rstrip(),"```",""]
        else:
            lines += ["","Locator:","","```json",json.dumps(change["locator"],ensure_ascii=False,indent=2),"```","","Proposal:","","```json",json.dumps(change["proposal"],ensure_ascii=False,indent=2),"```",""]
    lines += ["## Regression checklist",""]+[f"- {x}" for x in plan["regression_checks"]]+["","## Rollback","","This planner does not modify the source project. If a human or later verified writer applies the plan, preserve the pre-change project/script files and restore them if any regression fails.",""]
    return "\n".join(lines)


def build_plan(index: Path, project: Path, spec_path: Path, output: Path) -> dict:
    index=index.resolve(); project=project.resolve(); output=output.resolve()
    manifest=validate_index(index); freshness=verify_freshness(manifest,project)
    if freshness["status"]!="fresh":
        raise RuntimeError("STALE_INDEX:"+json.dumps(freshness,ensure_ascii=False))
    spec=normalize_spec(load_json(spec_path)); changes=[]
    for change in spec["changes"]:
        changes.append(script_diff(index,change) if change["kind"]=="script" else structural_change(change))
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
