from __future__ import annotations
import re
from .common import (QUEST_RE, STATE_RE, BOSS_RE, CUTSCENE_RE, SYSTEM_RE, matches, tokens, slug, confidence, ctx_key, location, related_by_context, observed_values)

def build_state_machines(variables, switches, catalog):
    out = []
    for var in variables:
        name = str(var.get("name") or "")
        evidence = var.get("reads", []) + var.get("writes", [])
        values = observed_values(var)
        score = 0
        reasons = []
        if matches(STATE_RE, name):
            score += 3; reasons.append("variable name suggests staged/progression state")
        if matches(QUEST_RE, name):
            score += 2; reasons.append("variable name suggests quest/story ownership")
        if len({ctx_key(x) for x in evidence}) >= 2:
            score += 1; reasons.append("variable participates in multiple event contexts")
        if len(values) >= 2:
            score += 1; reasons.append("multiple explicit constant values are observed")
        if score < 2:
            continue
        related_switches = related_by_context(evidence, switches)
        out.append({
            "id": f"variable-{var.get('id')}",
            "type": "state_machine_candidate",
            "variable_id": var.get("id"),
            "name": name,
            "confidence": confidence(score),
            "reasons": reasons,
            "observed_values": values,
            "value_meanings": {},
            "note": "Observed values are evidence. Meanings are intentionally left blank unless supported by project text/logic.",
            "related_switches": [{"id": x["id"], "name": x["name"]} for x in related_switches],
            "evidence": [location(x, catalog) for x in evidence],
        })
    return out


def build_quests(variables, switches, callers, catalog):
    out = []
    quest_ces = [c for c in callers if matches(QUEST_RE, c.get("name")) or re.search(r"\b(advance|complete|finish)\b", tokens(c.get("name")), re.I)]
    quest_switches = [s for s in switches if matches(QUEST_RE, s.get("name"))]
    for var in variables:
        name = str(var.get("name") or "")
        if not (matches(QUEST_RE, name) or matches(STATE_RE, name) and quest_ces):
            continue
        evidence = list(var.get("reads", [])) + list(var.get("writes", []))
        keys = {ctx_key(x) for x in evidence}
        related_ces = []
        for ce in quest_ces:
            ce_context = ("common_event", ce.get("common_event_id"))
            caller_keys = {ctx_key(x) for x in ce.get("callers", [])}
            if ce_context in keys or keys & caller_keys or not evidence:
                related_ces.append(ce)
        related_switches = related_by_context(evidence, switches)
        for s in quest_switches:
            if not any(x["id"] == s.get("id") for x in related_switches):
                related_switches.append({"id": s.get("id"), "name": s.get("name", ""), "evidence": []})
        score = 1
        reasons = []
        if matches(QUEST_RE, name):
            score += 3; reasons.append("state variable name explicitly looks quest/story-related")
        elif matches(STATE_RE, name):
            score += 1; reasons.append("state variable name looks like progression state")
        if related_ces:
            score += 2; reasons.append("related common-event name/call flow looks quest-related")
        if related_switches:
            score += 1; reasons.append("related named switch(es) provide quest/gating context")
        locations = []
        for x in evidence:
            locations.append(location(x, catalog))
        for ce in related_ces:
            for x in ce.get("callers", []):
                locations.append(location(x, catalog))
        out.append({
            "id": f"quest-{var.get('id')}-{slug(name)}",
            "type": "quest_candidate",
            "title": name or f"Quest candidate using Variable {var.get('id')}",
            "confidence": confidence(score),
            "reasons": reasons,
            "state_variable": {"id": var.get("id"), "name": name, "observed_values": observed_values(var)},
            "related_switches": [{"id": x.get("id"), "name": x.get("name", "")} for x in related_switches],
            "related_common_events": [{"id": x.get("common_event_id"), "name": x.get("name", "")} for x in related_ces],
            "stage_meanings": {},
            "evidence": locations,
        })
    return out


def build_boss_gates(switches, battles, catalog):
    out = []
    for battle in battles:
        key0 = ctx_key(battle)
        related = []
        for sw in switches:
            ev = [x for x in sw.get("reads", []) + sw.get("writes", []) if ctx_key(x) == key0]
            if ev:
                related.append((sw, ev))
        score = 1
        reasons = ["battle-processing command is present"]
        boss_related = [(s, ev) for s, ev in related if matches(BOSS_RE, s.get("name"))]
        if boss_related:
            score += 4; reasons.append("same event context uses a boss/defeat-named switch")
        elif related:
            score += 1; reasons.append("same event context also uses gating switch(es)")
        troop_name = str(battle.get("troop_name") or "")
        if matches(BOSS_RE, troop_name):
            score += 2; reasons.append("troop name looks boss-related")
        if score < 3:
            continue
        selected = boss_related or related
        out.append({
            "id": f"battle-gate-{battle.get('map_id','x')}-{battle.get('event_id','x')}-{battle.get('command_index','x')}",
            "type": "boss_or_battle_gate_candidate",
            "confidence": confidence(score),
            "reasons": reasons,
            "troop": {"id": battle.get("troop_id"), "name": troop_name},
            "related_switches": [{"id": s.get("id"), "name": s.get("name", "")} for s, _ in selected],
            "evidence": [location(battle, catalog)] + [location(x, catalog) for _, ev in selected for x in ev],
        })
    return out


def build_cutscenes(catalog):
    out = []
    for (mid, eid), name in sorted(catalog["event_names"].items()):
        page_items = [(p, meta) for (m, e, p), meta in catalog["page_meta"].items() if m == mid and e == eid]
        name_hit = matches(CUTSCENE_RE, name)
        autorun = [p for p, meta in page_items if meta.get("trigger") == 3]
        if not name_hit and not autorun:
            continue
        score = (3 if name_hit else 0) + (3 if autorun else 0)
        reasons = []
        if name_hit: reasons.append("event name suggests a cutscene/cinematic sequence")
        if autorun: reasons.append("event contains autorun page(s)")
        out.append({
            "id": f"cutscene-{mid}-{eid}", "type": "cutscene_candidate", "confidence": confidence(score),
            "reasons": reasons, "map_id": mid, "map_name": catalog["map_names"].get(mid, ""),
            "event_id": eid, "event_name": name, "autorun_pages": autorun,
            "evidence": [{"kind": "map_event", "map_id": mid, "map_name": catalog["map_names"].get(mid, ""), "event_id": eid, "event_name": name, "page": p} for p, _ in page_items],
        })
    return out


def build_common_event_systems(callers, catalog):
    out = []
    for ce in callers:
        name = str(ce.get("name") or "")
        calls = ce.get("callers", [])
        score = 0; reasons = []
        if matches(SYSTEM_RE, name): score += 2; reasons.append("common-event name suggests reusable subsystem logic")
        if len(calls) >= 2: score += 2; reasons.append("common event has multiple callers")
        if len({ctx_key(x) for x in calls}) >= 2: score += 1; reasons.append("callers span multiple event contexts")
        if score < 2: continue
        out.append({
            "id": f"common-event-{ce.get('common_event_id')}", "type": "common_event_subsystem_candidate",
            "common_event_id": ce.get("common_event_id"), "name": name, "confidence": confidence(score),
            "reasons": reasons, "caller_count": len(calls), "evidence": [location(x, catalog) for x in calls],
        })
    return out
