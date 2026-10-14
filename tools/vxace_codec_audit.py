#!/usr/bin/env python3
"""Experimental, read-only Python Marshal audit; never grants mutation readiness."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

VERSION = "0.1.0-experimental"
UPSTREAM_COMMIT = "75d7360fc12eda3046881e0424f136a9a5c01487"
MAX_FILE_BYTES = 64 * 1024 * 1024


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inventory(data):
    result = {}
    for path in sorted(data.glob("*.rvdata2")):
        if path.resolve().parent != data.resolve() or path.is_symlink():
            raise ValueError("Linked data files are refused by the experimental audit")
        if path.is_file():
            result[path.name] = digest(path)
    return result


def worker(path):
    # Only these inert codec modules are vendored. No MCP server, project writer,
    # script loader or extracted script source is imported or executed.
    sys.path.insert(0, str(Path(__file__).resolve().parent / "_vendor"))
    from rpgvxace_mcp import marshal_rb

    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("file exceeds the experimental 64 MiB audit limit")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("file exceeds the experimental 64 MiB audit limit")
    value, warnings = marshal_rb.load_with_warnings(raw)
    candidate = marshal_rb.dump(value)
    return {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "roundtrip_sha256": hashlib.sha256(candidate).hexdigest(),
        "byte_identical": raw == candidate,
        "warnings": [str(x)[:2048] for x in warnings[:40]],
        "warning_count": len(warnings),
    }


def audit_file(path, expected_hash, timeout):
    row = {"path": path.name, "source_sha256": expected_hash, "status": "failed"}
    if path.stat().st_size > MAX_FILE_BYTES:
        return {**row, "reason": "size_limit"}
    try:
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--_worker", str(path)],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout,
        )
        if proc.returncode:
            return {**row, "reason": "codec_error",
                    "error": proc.stderr.strip().replace(str(path), path.name)[:2048]}
        result = json.loads(proc.stdout)
        row.update(result)
        if result["source_sha256"] != expected_hash:
            row["reason"] = "source_changed_during_audit"
        elif result["warning_count"]:
            row["reason"] = "codec_warnings"
        elif not result["byte_identical"]:
            row["reason"] = "byte_mismatch"
        else:
            row.update(status="pass", reason="byte_identical")
        return row
    except subprocess.TimeoutExpired:
        return {**row, "reason": "timeout"}
    except (OSError, ValueError, KeyError) as exc:
        return {**row, "reason": "audit_error",
                "error": str(exc).replace(str(path), path.name)[:2048]}


def audit(project, output, timeout=30):
    project = Path(project).expanduser().resolve()
    if project.is_file() and project.suffix.lower() == ".rvproj2":
        project = project.parent
    data = project / "Data"
    if not data.is_dir():
        raise ValueError("Expected a VX Ace project with Data/")
    if data.resolve().parent != project or data.is_symlink():
        raise ValueError("Linked Data directories are refused by the experimental audit")
    output = Path(output).expanduser().resolve()
    if output == project or project in output.parents:
        raise ValueError("Audit output must be outside the source project")
    if output.exists():
        raise ValueError("Use a new external output directory")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be finite and positive")
    before = inventory(data)
    if not before:
        raise ValueError("No Data/*.rvdata2 files found")
    rows = [audit_file(data / name, sha, timeout) for name, sha in before.items()]
    after = inventory(data)
    unchanged = before == after
    passed = unchanged and all(row["status"] == "pass" for row in rows)
    report = {
        "audit_version": VERSION, "backend": "experimental_python",
        "upstream_commit": UPSTREAM_COMMIT,
        "experimental_codec_pass": passed,
        "mutation_authorized": False, "production_gate_satisfied": False,
        "source_data_unchanged": unchanged, "source_path_omitted": True,
        "checked": len(rows), "failed": sum(row["status"] != "pass" for row in rows),
        "files": rows,
        "limitations": [
            "This audit does not replace vxace_project_validator.py or its current Ruby mutator gate.",
            "No script syntax, RGSS3 runtime, gameplay or mutation compatibility is established.",
            "Only immediate Data/*.rvdata2 files are audited; no project scripts are executed.",
            "Files over 64 MiB are refused; each codec subprocess has a timeout.",
            "Source hashes compare before/after content, not a lock against concurrent edits.",
        ],
    }
    lines = ["# Experimental Python Marshal audit", "",
             f"Experimental codec result: **{'PASS' if passed else 'REFUSED'}**",
             f"Files checked: {len(rows)}; failed: {report['failed']}",
             f"Source Data inventory unchanged: {unchanged}", "",
             "**Mutation remains disabled by this audit. Run the existing production validator separately.**", ""]
    lines += [f"- {r['status'].upper()} `{r['path']}`: {r['reason']}" for r in rows]
    lines += ["", "## Limits", ""] + [f"- {x}" for x in report["limitations"]]
    # New directory required. No candidates or decoded game content are saved.
    output.mkdir(parents=True, exist_ok=False)
    (output / "codec-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "codec-audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?")
    parser.add_argument("--output")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--_worker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args._worker:
            print(json.dumps(worker(args._worker)))
            return 0
        if not args.project or not args.output:
            parser.error("project and --output are required")
        report = audit(args.project, args.output, args.timeout)
        print(json.dumps({k: report[k] for k in (
            "experimental_codec_pass", "mutation_authorized", "checked", "failed")}))
        return 0 if report["experimental_codec_pass"] else 3
    except Exception as exc:
        print(f"error: {str(exc)[:2048]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
