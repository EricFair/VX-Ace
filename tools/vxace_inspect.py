#!/usr/bin/env python3
"""Observed schema and conservative reference linting from our read-only index."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path


def read(path, fallback=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback


def inspect(index):
    index = Path(index).resolve()
    project = read(index / "project.json")
    if not isinstance(project, dict):
        raise ValueError("Missing project.json; generate a fresh Project Reader index")
    classes, findings, maps = {}, [], {}
    visited = 0
    for directory in ("database", "maps"):
        for file in sorted((index / directory).glob("*.json")):
            root = read(file)
            if directory == "maps" and isinstance(root, dict):
                maps[int(file.stem.split("-")[-1])] = root
            stack = [(root, [])]
            while stack:
                value, path = stack.pop()
                visited += 1
                if visited > 500000 or len(path) > 192:
                    raise ValueError("Index walk budget exceeded")
                if isinstance(value, dict):
                    name = value.get("__class__")
                    if isinstance(name, str):
                        item = classes.setdefault(name, {"objects": 0, "fields": {}, "evidence": []})
                        item["objects"] += 1
                        if len(item["evidence"]) < 3:
                            item["evidence"].append({"file": file.relative_to(index).as_posix(), "path": path})
                        for key, field in value.items():
                            if not key.startswith("__"):
                                types = item["fields"].setdefault(key, [])
                                kind = type(field).__name__
                                if kind not in types:
                                    types.append(kind)
                    stack.extend((v, path + [k]) for k, v in value.items())
                elif isinstance(value, list):
                    stack.extend((v, path + [i]) for i, v in enumerate(value))
    def finding(code, evidence, detail):
        if len(findings) >= 5000:
            raise ValueError("Finding budget exceeded")
        findings.append({"severity": "error", "code": code, "evidence": evidence, "detail": detail})
    references = read(index / "analysis/event-references.json", {})
    for transfer in references.get("map_transfers", []):
        if transfer.get("designation") != "direct":
            continue
        target = maps.get(transfer.get("map_id"))
        if target is None:
            finding("missing_transfer_map", transfer, "Direct transfer target is absent from decoded maps")
        else:
            x, y, width, height = (transfer.get("x"), transfer.get("y"), target.get("width"), target.get("height"))
            if all(type(v) is int for v in (x, y, width, height)) and not (0 <= x < width and 0 <= y < height):
                finding("transfer_out_of_bounds", transfer, "Direct transfer coordinates exceed target dimensions")
    tables = {
        "common_event_callers": ("common-events.json", "common_event_id"),
        "battle_troop_links": ("troops.json", "troop_id"),
    }
    for relation, (filename, key) in tables.items():
        table = read(index / "database" / filename, [])
        ids = {x.get("id") for x in table if isinstance(x, dict)} if isinstance(table, list) else set()
        for reference in references.get(relation, []):
            if key in reference and reference[key] not in ids:
                finding("missing_" + key, reference, "Referenced database object was not decoded")
    for error in project.get("errors", []):
        finding("extraction_error", error, "Partial extraction limits every derived result")
    return {"version": "0.11.0", "read_only": True, "classes": classes, "findings": findings,
            "counts": dict(Counter(x["severity"] for x in findings)),
            "limits": ["Observed field types are evidence, not a complete schema or permission to add fields.",
                       "Lint coverage: direct transfers, common-event/troop references and extraction errors only.",
                       "Variable-designated destinations need runtime evidence; asset/RTP and full event-logic lint remain future work."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        index, output = Path(args.index).resolve(), Path(args.output).resolve()
        if output == index or index in output.parents:
            raise ValueError("Inspection output must be outside the input index")
        if output.exists():
            raise ValueError("Use a new output directory")
        result = inspect(index)
        output.mkdir(parents=True)
        (output / "inspection.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        lines = ["# VX Ace observed schema and reference inspection", "",
                 f"Classes observed: {len(result['classes'])}; findings: {len(result['findings'])}", ""]
        lines += [f"- **{x['code']}**: {x['detail']}" for x in result["findings"]]
        lines += ["", "## Coverage limits", ""] + [f"- {x}" for x in result["limits"]]
        (output / "inspection.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 3 if result["findings"] else 0
    except Exception as exc:
        print(f"Inspection error: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
