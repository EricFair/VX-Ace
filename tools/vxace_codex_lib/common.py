from __future__ import annotations
import json
import re
from pathlib import Path

VERSION = "0.6.0"
QUEST_RE = re.compile(r"\b(quest|mission|objective|chapter|story)\b", re.I)
STATE_RE = re.compile(r"\b(stage|state|phase|step|progress|chapter)\b", re.I)
BOSS_RE = re.compile(r"\b(boss|defeat(?:ed)?|slain|victory)\b", re.I)
CUTSCENE_RE = re.compile(r"\b(cutscene|cinematic|intro|opening|ending|scene)\b", re.I)
SYSTEM_RE = re.compile(r"\b(system|manager|update|advance|quest|battle|menu|reputation|craft|journal)\b", re.I)

def tokens(text):
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(text or ""))
    return re.sub(r"[^A-Za-z0-9]+", " ", text).strip()


def matches(pattern, text):
    return bool(pattern.search(tokens(text)))


def load(path, default=None):
    p = Path(path)
    if not p.is_file():
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "unnamed"


def confidence(score):
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def ctx_key(ctx):
    if not isinstance(ctx, dict):
        return ("unknown",)
    if ctx.get("kind") == "map":
        return ("map", ctx.get("source_map_id", ctx.get("map_id")), ctx.get("event_id"), ctx.get("page"))
    if ctx.get("kind") == "common_event":
        return ("common_event", ctx.get("common_event_id"))
    if ctx.get('kind') == 'troop':
        return ('troop',ctx.get('troop_id'),ctx.get('page'))
    return (ctx.get("kind", "unknown"), ctx.get("file"))


def location(ctx, catalog):
    d = dict(ctx) if isinstance(ctx, dict) else {"raw": ctx}
    if d.get("kind") == "map":
        mid, eid = d.get("map_id"), d.get("event_id")
        d["map_name"] = catalog["map_names"].get(mid, "")
        d["event_name"] = catalog["event_names"].get((mid, eid), "")
    elif d.get("kind") == "common_event":
        cid = d.get("common_event_id")
        d["common_event_name"] = catalog["common_event_names"].get(cid, "")
    return d


def source_catalog(root):
    project = load(root / "project.json", {}) or {}
    map_names = {m.get("map_id"): m.get("name", "") for m in project.get("maps", []) if isinstance(m, dict)}
    event_names = {}
    page_meta = {}
    for mp in sorted((root / "maps").glob("map-*.json")):
        try:
            mid = int(mp.stem.split("-")[-1])
        except Exception:
            continue
        obj = load(mp, {}) or {}
        if obj.get("display_name") and not map_names.get(mid):
            map_names[mid] = str(obj.get("display_name"))
        events = obj.get("events", {})
        if isinstance(events, dict):
            for raw_id, ev in events.items():
                if not isinstance(ev, dict):
                    continue
                try:
                    eid = int(ev.get("id", raw_id))
                except Exception:
                    continue
                event_names[(mid, eid)] = str(ev.get("name") or "")
                pages = ev.get("pages", [])
                if isinstance(pages, list):
                    for i, pg in enumerate(pages, 1):
                        if isinstance(pg, dict):
                            page_meta[(mid, eid, i)] = {
                                "trigger": pg.get("trigger"),
                                "condition": pg.get("condition"),
                            }
    ce_names = {}
    ce = load(root / "database" / "common-events.json", []) or []
    if isinstance(ce, list):
        for i, item in enumerate(ce):
            if isinstance(item, dict):
                try:
                    cid = int(item.get("id", i))
                except Exception:
                    cid = i
                ce_names[cid] = str(item.get("name") or "")
    return {
        "map_names": map_names,
        "event_names": event_names,
        "page_meta": page_meta,
        "common_event_names": ce_names,
    }


def related_by_context(seed_contexts, resources):
    keys = {ctx_key(x) for x in seed_contexts}
    found = []
    for resource in resources:
        evidence = []
        for x in resource.get("reads", []) + resource.get("writes", []):
            if ctx_key(x) in keys:
                evidence.append(x)
        if evidence:
            found.append({"id": resource.get("id"), "name": resource.get("name", ""), "evidence": evidence})
    return found


def observed_values(variable):
    vals = []
    for w in variable.get("writes", []):
        if w.get("operation") == 0 and w.get("operand_type") == 0 and "operand" in w:
            vals.append(w.get("operand"))
    for r in variable.get("reads", []):
        if r.get("role", "").startswith("conditional") and r.get("operand_type") == 0 and "operand" in r:
            vals.append(r.get("operand"))
    out = []
    for v in vals:
        if v not in out:
            out.append(v)
    return out
