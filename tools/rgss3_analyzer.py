#!/usr/bin/env python3
"""Static compatibility analyzer for extracted RPG Maker VX Ace RGSS3 scripts.

The analyzer intentionally uses conservative lexical analysis instead of executing
or importing project code. It is designed for Ruby 1.9.2-era RGSS3 scripts and
focuses on the kinds of cross-script interactions that commonly matter in VX Ace:
class/module reopenings, method redefinitions, aliases, $imported dependency keys,
load-order sensitivity, save hooks, and note-tag parsing.

It does not claim to be a full Ruby parser. Findings are collision candidates that
should be reviewed by a developer or agent with the actual project context.
"""
from __future__ import print_function

import argparse
import io
import json
import os
import re
import sys
from collections import defaultdict

VERSION = "0.4.0"

CLASS_RE = re.compile(r"^\s*class\s+([A-Z]\w*(?:::[A-Z]\w*)*)(?:\s*<\s*([^#]+?))?\s*(?:#.*)?$")
MODULE_RE = re.compile(r"^\s*module\s+([A-Z]\w*(?:::[A-Z]\w*)*)\s*(?:#.*)?$")
CLASS_SINGLETON_RE = re.compile(r"^\s*class\s+<<\s*self\b")
DEF_RE = re.compile(r"^\s*def\s+([^\s(;]+)")
END_RE = re.compile(r"^\s*end\b")
ALIAS_RE = re.compile(r"^\s*alias\s+(?::)?([A-Za-z_]\w*[!?=]?)\s+(?::)?([A-Za-z_]\w*[!?=]?)")
ALIAS_METHOD_RE = re.compile(
    r"\balias_method\s*(?:\(\s*)?(?::|['\"])([A-Za-z_]\w*[!?=]?)(?:['\"])?\s*,\s*(?::|['\"])([A-Za-z_]\w*[!?=]?)(?:['\"])?"
)
IMPORTED_SET_RE = re.compile(r"\$imported\s*\[\s*(['\"])(.+?)\1\s*\]\s*=\s*(.+?)(?:\s*#.*)?$")
IMPORTED_READ_RE = re.compile(r"\$imported\s*\[\s*(['\"])(.+?)\1\s*\]")
REQUIRE_RE = re.compile(r"^\s*(?:require|load)\s*(?:\(\s*)?['\"]([^'\"]+)['\"]")
CONST_ASSIGN_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(?!=)")
GLOBAL_ASSIGN_RE = re.compile(r"^\s*(\$[a-zA-Z_]\w*)\s*=")
NOTE_ACCESS_RE = re.compile(r"(?:\.note\b|\bnote\s*=|\bnote\s*=~|\bnote\.scan\b|\bnotetag\b|\bnote_tag\b)", re.I)
DATA_MANAGER_HOOKS = set([
    "make_save_contents", "extract_save_contents", "save_game", "load_game",
    "create_game_objects", "setup_new_game", "load_database", "load_normal_database"
])
HIGH_RISK_METHODS = set([
    "initialize", "update", "refresh", "start", "terminate", "main",
    "item_apply", "make_damage_value", "execute_damage", "use_item",
    "make_targets", "setup", "setup_page", "conditions_met?",
    "make_save_contents", "extract_save_contents", "create_game_objects"
])

CONTROL_OPEN_RE = re.compile(
    r"^\s*(if|unless|case|while|until|for|begin)\b|\bdo\s*(?:\|[^|]*\|)?\s*(?:#.*)?$"
)
ONE_LINE_CONTROL_RE = re.compile(r"^\s*(return|next|break|redo|retry)\b")


def strip_inline_comment(line):
    """Remove a simple trailing comment while preserving quoted # when possible."""
    out = []
    quote = None
    escape = False
    for ch in line:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            out.append(ch)
            escape = True
            continue
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out)


def normalize_method_name(name):
    if name.startswith("self."):
        return name[5:], True
    if name.startswith("self::"):
        return name[6:], True
    return name, False


def qualified_scope(stack):
    names = [frame["name"] for frame in stack if frame["kind"] in ("class", "module")]
    return "::".join(names) if names else "<top-level>"


def script_name(path):
    return os.path.basename(path)


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def discover_scripts(root, order_path=None):
    root = os.path.abspath(root)
    if os.path.isfile(root):
        return [root]

    scripts = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            if filename.lower().endswith(".rb"):
                scripts.append(os.path.join(dirpath, filename))

    scripts.sort(key=lambda p: os.path.relpath(p, root).lower())

    if order_path:
        with io.open(order_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            raw = raw.get("scripts", raw.get("order", []))
        wanted = []
        by_rel = {os.path.relpath(p, root).replace("\\", "/"): p for p in scripts}
        by_base = defaultdict(list)
        for p in scripts:
            by_base[os.path.basename(p)].append(p)
        seen = set()
        for item in raw:
            if isinstance(item, dict):
                key = item.get("path") or item.get("file") or item.get("name")
            else:
                key = item
            if not key:
                continue
            key = str(key).replace("\\", "/")
            p = by_rel.get(key)
            if not p and len(by_base.get(os.path.basename(key), [])) == 1:
                p = by_base[os.path.basename(key)][0]
            if p and p not in seen:
                wanted.append(p)
                seen.add(p)
        wanted.extend([p for p in scripts if p not in seen])
        scripts = wanted
    return scripts


def analyze_script(path, order_index=0, root=None):
    text = read_text(path)
    lines = text.splitlines()
    result = {
        "path": os.path.relpath(path, root) if root and os.path.isdir(root) else path,
        "name": script_name(path),
        "order": order_index,
        "classes": [],
        "modules": [],
        "methods": [],
        "aliases": [],
        "imported_sets": [],
        "imported_reads": [],
        "requires": [],
        "constants": [],
        "globals": [],
        "save_hooks": [],
        "note_parser_lines": [],
        "warnings": [],
    }

    block_stack = []
    namespace_stack = []

    for lineno, raw in enumerate(lines, 1):
        line = strip_inline_comment(raw).rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        m = CLASS_SINGLETON_RE.match(line)
        if m:
            block_stack.append({"kind": "singleton", "name": "self", "line": lineno})
            continue

        m = CLASS_RE.match(line)
        if m:
            name = m.group(1)
            parent = (m.group(2) or "").strip() or None
            scope_before = qualified_scope(namespace_stack)
            full_name = name if "::" in name or scope_before == "<top-level>" else scope_before + "::" + name
            result["classes"].append({"name": full_name, "short_name": name, "parent": parent, "line": lineno})
            frame = {"kind": "class", "name": name, "full_name": full_name, "line": lineno}
            block_stack.append(frame)
            namespace_stack.append(frame)
            continue

        m = MODULE_RE.match(line)
        if m:
            name = m.group(1)
            scope_before = qualified_scope(namespace_stack)
            full_name = name if "::" in name or scope_before == "<top-level>" else scope_before + "::" + name
            result["modules"].append({"name": full_name, "short_name": name, "line": lineno})
            frame = {"kind": "module", "name": name, "full_name": full_name, "line": lineno}
            block_stack.append(frame)
            namespace_stack.append(frame)
            continue

        m = DEF_RE.match(line)
        if m:
            raw_name = m.group(1)
            method_name, explicit_singleton = normalize_method_name(raw_name)
            in_singleton = any(f["kind"] == "singleton" for f in block_stack)
            singleton = explicit_singleton or in_singleton
            scope = qualified_scope(namespace_stack)
            entry = {
                "scope": scope,
                "name": method_name,
                "singleton": singleton,
                "line": lineno,
                "high_risk": method_name in HIGH_RISK_METHODS,
            }
            result["methods"].append(entry)
            if scope == "DataManager" and method_name in DATA_MANAGER_HOOKS:
                result["save_hooks"].append({"method": method_name, "line": lineno})
            block_stack.append({"kind": "def", "name": method_name, "line": lineno})
            continue

        m = ALIAS_RE.match(line)
        if m:
            result["aliases"].append({
                "scope": qualified_scope(namespace_stack),
                "new": m.group(1), "old": m.group(2), "line": lineno, "form": "alias",
            })
        for am in ALIAS_METHOD_RE.finditer(line):
            result["aliases"].append({
                "scope": qualified_scope(namespace_stack),
                "new": am.group(1), "old": am.group(2), "line": lineno, "form": "alias_method",
            })

        m = IMPORTED_SET_RE.search(line)
        if m:
            result["imported_sets"].append({"key": m.group(2), "value": m.group(3).strip(), "line": lineno})
        for im in IMPORTED_READ_RE.finditer(line):
            key = im.group(2)
            if not (m and key == m.group(2)):
                result["imported_reads"].append({"key": key, "line": lineno, "text": stripped[:200]})

        m_req = REQUIRE_RE.match(line)
        if m_req:
            result["requires"].append({"target": m_req.group(1), "line": lineno})
        m_const = CONST_ASSIGN_RE.match(line)
        if m_const:
            result["constants"].append({"scope": qualified_scope(namespace_stack), "name": m_const.group(1), "line": lineno})
        m_global = GLOBAL_ASSIGN_RE.match(line)
        if m_global and not stripped.startswith("$imported"):
            result["globals"].append({"name": m_global.group(1), "line": lineno})
        if NOTE_ACCESS_RE.search(line):
            result["note_parser_lines"].append({"line": lineno, "text": stripped[:220]})

        if END_RE.match(line):
            if block_stack:
                frame = block_stack.pop()
                if frame["kind"] in ("class", "module"):
                    if namespace_stack and namespace_stack[-1] is frame:
                        namespace_stack.pop()
                    else:
                        for i in range(len(namespace_stack) - 1, -1, -1):
                            if namespace_stack[i].get("line") == frame.get("line"):
                                del namespace_stack[i]
                                break
            continue

        if not ONE_LINE_CONTROL_RE.match(stripped) and CONTROL_OPEN_RE.search(line):
            starts_control = re.match(r"^\s*(if|unless|case|while|until|for|begin)\b", line)
            trailing_do = re.search(r"\bdo\s*(?:\|[^|]*\|)?\s*$", line)
            if starts_control or trailing_do:
                block_stack.append({"kind": "control", "name": None, "line": lineno})

    if namespace_stack:
        result["warnings"].append("Lexical scope stack was not fully closed; metaprogramming or one-line Ruby syntax may have reduced parser accuracy.")
    return result


def method_key(method):
    prefix = "self." if method.get("singleton") else ""
    return "%s#%s%s" % (method["scope"], prefix, method["name"])


def alias_targets_for_script(script):
    by_scope_old = defaultdict(list)
    for alias in script["aliases"]:
        by_scope_old[(alias["scope"], alias["old"])].append(alias)
    return by_scope_old


def build_report(scripts):
    report = {
        "analyzer_version": VERSION,
        "script_count": len(scripts),
        "scripts": scripts,
        "summary": {},
        "class_reopenings": [], "module_reopenings": [], "method_collisions": [],
        "imported_keys": [], "dependency_findings": [], "constant_collisions": [],
        "global_writes": [], "save_hook_scripts": [], "note_parser_scripts": [],
        "limitations": [
            "Lexical/static analysis only; it does not execute Ruby.",
            "Metaprogramming, eval/class_eval/module_eval, define_method, dynamic alias names, and generated code may be missed.",
            "A collision candidate is not automatic proof of incompatibility.",
            "Method compatibility still depends on script order, control flow, and whether aliases call the prior implementation.",
        ],
    }

    class_occ = defaultdict(list); module_occ = defaultdict(list); method_occ = defaultdict(list)
    const_occ = defaultdict(list); imported_sets = defaultdict(list); imported_reads = defaultdict(list)
    global_occ = defaultdict(list)

    for script in scripts:
        for c in script["classes"]:
            class_occ[c["name"]].append({"script": script["name"], "path": script["path"], "order": script["order"], "line": c["line"], "parent": c.get("parent")})
        for m in script["modules"]:
            module_occ[m["name"]].append({"script": script["name"], "path": script["path"], "order": script["order"], "line": m["line"]})
        alias_map = alias_targets_for_script(script)
        for meth in script["methods"]:
            method_occ[method_key(meth)].append({"script": script["name"], "path": script["path"], "order": script["order"], "line": meth["line"], "method": meth, "aliases": alias_map.get((meth["scope"], meth["name"]), [])})
        for const in script["constants"]:
            const_occ["%s::%s" % (const["scope"], const["name"])].append({"script": script["name"], "path": script["path"], "order": script["order"], "line": const["line"]})
        for imp in script["imported_sets"]:
            imported_sets[imp["key"]].append({"script": script["name"], "path": script["path"], "order": script["order"], "line": imp["line"], "value": imp["value"]})
        for imp in script["imported_reads"]:
            imported_reads[imp["key"]].append({"script": script["name"], "path": script["path"], "order": script["order"], "line": imp["line"], "text": imp["text"]})
        for glob in script["globals"]:
            global_occ[glob["name"]].append({"script": script["name"], "path": script["path"], "order": script["order"], "line": glob["line"]})
        if script["save_hooks"]:
            report["save_hook_scripts"].append({"script": script["name"], "path": script["path"], "hooks": script["save_hooks"]})
        if script["note_parser_lines"]:
            report["note_parser_scripts"].append({"script": script["name"], "path": script["path"], "matches": script["note_parser_lines"]})

    for name, occ in sorted(class_occ.items()):
        if len(set(x["path"] for x in occ)) > 1:
            report["class_reopenings"].append({"class": name, "occurrences": sorted(occ, key=lambda x: (x["order"], x["line"]))})
    for name, occ in sorted(module_occ.items()):
        if len(set(x["path"] for x in occ)) > 1:
            report["module_reopenings"].append({"module": name, "occurrences": sorted(occ, key=lambda x: (x["order"], x["line"]))})

    for key, occ in sorted(method_occ.items()):
        if len(occ) < 2:
            continue
        occ = sorted(occ, key=lambda x: (x["order"], x["line"]))
        high_risk = any(x["method"].get("high_risk") for x in occ)
        preserving_later = 0
        for item in occ[1:]:
            script = next(s for s in scripts if s["path"] == item["path"])
            scope = item["method"]["scope"]; name = item["method"]["name"]
            if [a for a in script["aliases"] if a["scope"] == scope and a["old"] == name]:
                preserving_later += 1
        reasons = []
        if high_risk:
            reasons.append("core/high-frequency lifecycle method")
        if preserving_later == len(occ) - 1:
            severity = "medium" if high_risk else "low"
            reasons.append("later definitions appear to alias the prior method")
        else:
            severity = "high" if len(occ) >= 3 or high_risk else "medium"
            reasons.append("one or more later definitions do not visibly alias the prior method")
        report["method_collisions"].append({
            "method": key, "severity": severity, "reasons": reasons,
            "occurrences": [{k: v for k, v in item.items() if k != "method"} for item in occ],
        })

    for key, occ in sorted(imported_sets.items()):
        report["imported_keys"].append({"key": key, "definitions": sorted(occ, key=lambda x: (x["order"], x["line"])), "duplicate_definition": len(occ) > 1})
    for key, reads in sorted(imported_reads.items()):
        defs = sorted(imported_sets.get(key, []), key=lambda x: (x["order"], x["line"]))
        for read in sorted(reads, key=lambda x: (x["order"], x["line"])):
            previous_defs = [d for d in defs if d["order"] < read["order"] or (d["order"] == read["order"] and d["line"] < read["line"])]
            if not defs:
                status, severity = "missing_definition", "medium"
            elif not previous_defs:
                status, severity = "defined_later", "medium"
            else:
                status, severity = "satisfied_before_use", "info"
            report["dependency_findings"].append({"key": key, "severity": severity, "status": status, "read": read, "definitions": defs})

    for key, occ in sorted(const_occ.items()):
        if len(occ) > 1:
            report["constant_collisions"].append({"constant": key, "occurrences": sorted(occ, key=lambda x: (x["order"], x["line"]))})
    for name, occ in sorted(global_occ.items()):
        if len(occ) > 1:
            report["global_writes"].append({"global": name, "occurrences": sorted(occ, key=lambda x: (x["order"], x["line"]))})

    sev_counts = defaultdict(int)
    for item in report["method_collisions"]:
        sev_counts[item["severity"]] += 1
    for item in report["dependency_findings"]:
        sev_counts[item["severity"]] += 1
    report["summary"] = {
        "classes_reopened": len(report["class_reopenings"]),
        "modules_reopened": len(report["module_reopenings"]),
        "method_collision_candidates": len(report["method_collisions"]),
        "high_severity_findings": sev_counts["high"],
        "medium_severity_findings": sev_counts["medium"],
        "low_severity_findings": sev_counts["low"],
        "missing_or_late_imported_dependencies": sum(1 for x in report["dependency_findings"] if x["status"] != "satisfied_before_use"),
        "duplicate_imported_keys": sum(1 for x in report["imported_keys"] if x["duplicate_definition"]),
        "constant_collision_candidates": len(report["constant_collisions"]),
        "multi_script_global_writes": len(report["global_writes"]),
        "save_hook_scripts": len(report["save_hook_scripts"]),
        "note_parser_scripts": len(report["note_parser_scripts"]),
    }
    return report


def markdown_report(report):
    s = report["summary"]
    lines = [
        "# RGSS3 Compatibility Analysis", "", "Analyzer version: `%s`" % report["analyzer_version"],
        "Scripts analyzed: **%d**" % report["script_count"], "", "## Summary", "",
        "- Class reopenings: **%d**" % s["classes_reopened"],
        "- Method collision candidates: **%d**" % s["method_collision_candidates"],
        "- High-severity findings: **%d**" % s["high_severity_findings"],
        "- Medium-severity findings: **%d**" % s["medium_severity_findings"],
        "- Missing/late `$imported` dependencies: **%d**" % s["missing_or_late_imported_dependencies"],
        "- Duplicate `$imported` keys: **%d**" % s["duplicate_imported_keys"],
        "- Constant collision candidates: **%d**" % s["constant_collision_candidates"],
        "- Save-hook scripts: **%d**" % s["save_hook_scripts"],
        "- Note-parser scripts: **%d**" % s["note_parser_scripts"], "",
        "> These are static-analysis candidates, not automatic proof of incompatibility.", "",
    ]
    if report["method_collisions"]:
        lines += ["## Method collision candidates", ""]
        for item in report["method_collisions"]:
            lines += ["### `%s` — %s" % (item["method"], item["severity"].upper()), ""]
            lines.extend("- %s" % reason for reason in item["reasons"])
            lines.append("")
            lines.extend("- `%s` line %s (load order %s)" % (o["path"], o["line"], o["order"]) for o in item["occurrences"])
            lines.append("")
    dep_bad = [x for x in report["dependency_findings"] if x["status"] != "satisfied_before_use"]
    if dep_bad:
        lines += ["## `$imported` dependency findings", ""]
        for item in dep_bad:
            r = item["read"]
            lines.append("- **%s** `%s` at `%s:%s` — `%s`" % (item["severity"].upper(), item["key"], r["path"], r["line"], item["status"]))
        lines.append("")
    if report["constant_collisions"]:
        lines += ["## Constant collision candidates", ""]
        for item in report["constant_collisions"]:
            locs = ", ".join("%s:%s" % (o["path"], o["line"]) for o in item["occurrences"])
            lines.append("- `%s` — %s" % (item["constant"], locs))
        lines.append("")
    if report["save_hook_scripts"]:
        lines += ["## Save/load hook review", ""]
        for item in report["save_hook_scripts"]:
            hooks = ", ".join("%s@%s" % (h["method"], h["line"]) for h in item["hooks"])
            lines.append("- `%s`: %s" % (item["path"], hooks))
        lines.append("")
    lines += ["## Limitations", ""]
    lines.extend("- %s" % x for x in report["limitations"])
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze extracted RPG Maker VX Ace RGSS3 scripts for compatibility risks.")
    parser.add_argument("input", help="Directory containing extracted .rb scripts, or a single .rb file")
    parser.add_argument("--order", help="Optional JSON file defining script load order")
    parser.add_argument("--json", dest="json_path", help="Write full JSON report to this path")
    parser.add_argument("--markdown", dest="md_path", help="Write human-readable Markdown report to this path")
    parser.add_argument("--fail-on-high", action="store_true", help="Exit with code 2 if high-severity findings exist")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.input)
    scripts_paths = discover_scripts(root, args.order)
    if not scripts_paths:
        parser.error("no .rb scripts found")
    scripts = [analyze_script(path, i, root=root) for i, path in enumerate(scripts_paths)]
    report = build_report(scripts)
    if args.json_path:
        with io.open(args.json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True, ensure_ascii=False); f.write("\n")
    if args.md_path:
        with io.open(args.md_path, "w", encoding="utf-8") as f:
            f.write(markdown_report(report))
    print(markdown_report(report))
    if args.fail_on_high and report["summary"]["high_severity_findings"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
