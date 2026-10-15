#!/usr/bin/env python3
"""Run the configured read-only VX Ace validation and understanding workflow."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
from vxace_copy_patcher import current_inventory
from vxace_index_query import unlinked

ROOT = Path(__file__).resolve().parents[1]
SAFE_POLICY = {
    "original_project_writes": False, "mutation_mode": "disposable-copy-only",
    "project_wide_byte_gate": True, "immediate_target_byte_gate": True,
    "fresh_index_required": True, "structural_writes": "guarded-events-only", "runtime_review_required": True,
}


def settings(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("engine") != "VX Ace" or json.dumps(value.get("safety"),sort_keys=True) != json.dumps(SAFE_POLICY,sort_keys=True):
        raise ValueError("Master settings cannot weaken the fixed VX Ace safety contract")
    if value.get("validation_backend") not in ("ruby", "python"):
        raise ValueError("Unsupported validation backend")
    for feature in ("python_codec_audit", "observed_schema_and_reference_lint", "event_logic_lint"):
        if type(value.get(feature)) is not bool:
            raise ValueError("Feature flags must be booleans")
    if type(value.get('map_tile_audit', False)) is not bool:
        raise ValueError('Map audit feature flag must be boolean')
    if type(value.get('asset_audit', False)) is not bool:
        raise ValueError('Asset audit feature flag must be boolean')
    if type(value.get('image_headers', False)) is not bool:
        raise ValueError('Image header feature flag must be boolean')
    if value.get('image_headers', False) and not value.get('asset_audit', False):
        raise ValueError('Image header checks require the asset audit stage')
    return value


def workflow(project, output, ruby, config, rtp=None):
    config = settings(config)
    project, output = Path(project).resolve(), Path(output).resolve()
    if rtp is not None:
        rtp = unlinked(rtp)
        if output == rtp or rtp in output.parents:
            raise ValueError('Master reports must be outside the read-only RTP root')
    if project.is_file() and project.suffix.lower() == ".rvproj2":
        project = project.parent
    if not (project / "Data").is_dir():
        raise ValueError("Expected a VX Ace project with Data/")
    if output == project or project in output.parents or output.exists():
        raise ValueError("Use a new output directory outside the original project")
    before = current_inventory(project)
    output.mkdir(parents=True)
    stages = []
    def stage(name, tool, args):
        proc = subprocess.run([sys.executable, str(ROOT / "tools" / tool), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        (output / (name + ".stdout.log")).write_text(proc.stdout, encoding="utf-8")
        (output / (name + ".stderr.log")).write_text(proc.stderr, encoding="utf-8")
        stages.append({"name": name, "exit_code": proc.returncode})
        return proc.returncode
    completed = False
    try:
        stage("validation", "vxace_project_validator.py", [project, "--output", output / "validation",
              "--ruby", ruby, "--backend", config["validation_backend"]])
        if config["python_codec_audit"]:
            stage("codec-audit", "vxace_codec_audit.py", [project, "--output", output / "codec-audit"])
        reader = stage("reader", "vxace_project_reader.py", [project, "--output", output / "index", "--ruby", ruby])
        if reader == 0 and config["observed_schema_and_reference_lint"]:
            stage("inspection", "vxace_inspect.py", [output / "index", "--output", output / "inspection"])
        if reader == 0 and config['event_logic_lint']:
            stage('event-lint','vxace_event_lint.py',[output/'index','--project',project,'--output',output/'event-lint'])
        if reader == 0 and config.get('map_tile_audit', False):
            stage('map-audit','vxace_map_audit.py',[output/'index','--project',project,'--output',output/'map-audit'])
        if reader == 0 and config.get('asset_audit', False):
            args = [output/'index','--project',project,'--output',output/'asset-audit']
            if rtp is not None: args += ['--rtp', rtp]
            if config.get('image_headers', False): args += ['--image-headers']
            stage('asset-audit','vxace_asset_audit.py',args)
        completed = True
    finally:
        unchanged = current_inventory(project) == before
        validation = output / "validation/validation.json"
        ready = validation.is_file() and json.loads(validation.read_text(encoding="utf-8"))["copy_mutation_ready"]
        ok = completed and unchanged and ready and all(s["exit_code"] == 0 for s in stages)
        summary = {"version": "0.17.0", "status": "pass" if ok else "review_required", "stages": stages,
                   "source_unchanged": unchanged, "selected_backend": config["validation_backend"],
                   "copy_mutation_ready": bool(ready and unchanged), "mutation_performed": False,
                   "runtime_compatibility_proven": False}
        (output / "master-report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        lines = ["# VX Ace master report", "", f"Status: **{summary['status']}**",
                 f"Original files unchanged: **{unchanged}**", "Mutation performed: **False**", ""]
        lines += [f"- {s['name']}: exit {s['exit_code']}" for s in stages]
        lines += ["", "See validation/, codec-audit/, index/codex/, inspection/, event-lint/, map-audit/ and asset-audit/ for enabled evidence.",
                  "A pass does not authorize mutation or prove RGSS3 runtime behavior."]
        (output / "master-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--output", required=True)
    parser.add_argument("--ruby", default=__import__("shutil").which("ruby"))
    parser.add_argument("--config", default=str(ROOT / "vxace-master.json"))
    parser.add_argument('--rtp', help='Explicit unpacked RTP root for the optional asset audit')
    args = parser.parse_args(argv)
    try:
        if not args.ruby:
            raise ValueError("Ruby is required for extraction and separate syntax diagnostics")
        result = workflow(args.project, args.output, args.ruby, args.config, args.rtp)
        print(json.dumps(result))
        return 0 if result["status"] == "pass" else 3
    except Exception as exc:
        print(f"Master workflow error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
