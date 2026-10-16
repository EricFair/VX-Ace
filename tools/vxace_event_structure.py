"""Guarded event structure operations; used only by the Python copy backend."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / '_vendor'))
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject, RubyHash, RubyString

ACTIONS = {"insert_commands", "delete_commands", "insert_page", "delete_page"}
CONTINUATIONS = {401: 101, 405: 105, 408: 108, 505: 205, 605: 302, 655: 355}
OPENERS = {111: 412, 102: 404, 112: 413, 301: 604}
BRANCHES = {411: 111, 402: 102, 403: 102, 601: 301, 602: 301, 603: 301}
MAX_COMMANDS, MAX_INSERT, MAX_PAGES = 10000, 500, 32


def validate_project_references(index, mutation, source_path=None):
    """Verify newly supplied cross-file references against the fresh index."""
    index = Path(index)
    def data(name):
        path = index/'database'/name
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None
    system = data('system.json') or {}
    switches = system.get('switches', [])
    commons = data('common-events.json') or []
    common_ids = {x.get('id') for x in commons if isinstance(x,dict)}
    from vxace_transfers import has_transfers,validate as validate_transfer,snapshot as transfer_snapshot
    if has_transfers(mutation):
        from vxace_python_mutator import load
        from vxace_index_query import Index,unlinked
        if source_path is None:raise ValueError('Transfers require actual native source context')
        source=unlinked(source_path);evidence=validate_transfer(load(source)[0],mutation,source)
        target=evidence['destination'];observed=Index(index)
        transfer_snapshot(observed,source.parent.parent,evidence['source_map_id'],mutation['event_id'],target['map_id'],target['x'],target['y'],target['direction'],target['fade'])
        observed.unchanged()
    from vxace_event_rewards import has_rewards,reward_rows
    if has_rewards(mutation):
        from vxace_event_rewards import validate,snapshot
        from vxace_python_mutator import load
        from vxace_index_query import Index,unlinked
        if source_path is None:raise ValueError('Rewards require actual native map context')
        source=unlinked(source_path);native,_=load(source)
        validate(native,mutation,source)
        proposed=reward_rows(mutation['commands']);observed=Index(index)
        snapshot(observed,source.parent.parent,int(source.stem[3:]),mutation['event_id'],proposed.get('item_id'))
        observed.unchanged()
    for row in mutation.get('commands', []):
        code, p = row.get('code'), row.get('parameters')
        if code == 117 and (not isinstance(p,list) or len(p)!=1 or type(p[0]) is not int or p[0] not in common_ids):
            raise ValueError('New common-event reference is not present in the fresh index')
        if code == 121 and (not isinstance(p,list) or len(p)!=3 or any(type(x) is not int for x in p[:2]) or not 1 <= p[0] <= p[1] < len(switches)):
            raise ValueError('New switch range is not present in the fresh index')
    for field, value in mutation.get('conditions',{}).items():
        if field in ('switch1_id','switch2_id','switch_id') and (type(value) is not int or not 1 <= value < len(switches)):
            raise ValueError('New page switch reference is not present in the fresh index')


def fingerprint(value):
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def require_hash(value, expected, label):
    if not isinstance(expected, str) or len(expected) != 64 or fingerprint(value) != expected:
        raise ValueError(f"{label} fingerprint mismatch; obtain a fresh event snapshot")


def native_int(value, label, minimum=0, maximum=2**31-1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def plain(value):
    if isinstance(value, RubyString):
        return value.data.decode("utf-8", "strict")
    if isinstance(value, list):
        return [plain(x) for x in value]
    if value is None or type(value) in (int, float, bool, str):
        return value
    return {"opaque_type": getattr(value, "cls", type(value).__name__), "sha256": fingerprint(value)}


def command_rows(commands):
    return [{"code": c.get("code"), "indent": c.get("indent"), "parameters": plain(c.get("parameters"))}
            for c in commands]


def validate_list(commands):
    if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_COMMANDS:
        raise ValueError("Invalid or oversized command list")
    stack, starts, previous, labels, jumps = [], [], None, set(), []
    for i, cmd in enumerate(commands):
        if not isinstance(cmd, RubyObject) or cmd.cls != "RPG::EventCommand":
            raise ValueError("List contains a non-event-command object")
        code, indent, params = cmd.get("code"), cmd.get("indent"), cmd.get("parameters")
        native_int(code, "command code", 0, 9999)
        native_int(indent, "indent", 0, 64)
        if not isinstance(params, list):
            raise ValueError("Command parameters must be an array")
        if i == len(commands) - 1:
            if code != 0 or indent != 0 or params or stack:
                raise ValueError("List needs one final root terminator and closed blocks")
            break
        if code == 0 and indent == 0:
            raise ValueError("Premature root terminator")
        if code in OPENERS.values():
            if not stack or stack[-1][1] != code or indent != len(stack) - 1:
                raise ValueError("Unmatched branch/loop terminator")
            stack.pop()
        elif code in BRANCHES:
            if not stack or stack[-1][0] != BRANCHES[code] or indent != len(stack) - 1:
                raise ValueError("Orphan branch marker")
            if code in (411, 403) and code in stack[-1][2]:
                raise ValueError("Duplicate else/cancel branch")
            stack[-1][2].add(code)
        else:
            if indent != len(stack):
                raise ValueError("Invalid command indentation")
            if code in CONTINUATIONS:
                if previous is None or previous[1] != indent or previous[0] not in (code, CONTINUATIONS[code]):
                    raise ValueError("Orphan message/comment/script/route continuation")
            elif not stack and code != 0:
                starts.append(i)
            # Some battle calls have no outcome branches and are atomic.
            opens = code in OPENERS and (code != 301 or
                    i + 1 < len(commands) and commands[i+1].get("code") in (601, 602, 603))
            if opens:
                stack.append((code, OPENERS[code], set()))
            if code in (118, 119):
                if len(params) != 1 or not isinstance(params[0], RubyString):
                    raise ValueError("Invalid label/jump")
                text = params[0].data
                if code == 118:
                    if text in labels:
                        raise ValueError("Ambiguous duplicate labels")
                    labels.add(text)
                else:
                    jumps.append(text)
        previous = (code, indent)
    if any(label not in labels for label in jumps):
        raise ValueError("Jump target label is missing")
    return set(starts + [len(commands) - 1])


def new_commands(rows, convert, scope, terminal=False):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_INSERT:
        raise ValueError("Insert requires 1..500 explicitly described commands")
    result = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"code", "indent", "parameters"} or row["indent"] != 0 or type(row["indent"]) is not int:
            raise ValueError("New commands require exact code/indent/parameters fields at root indent")
        code, p = row["code"], row["parameters"]
        if type(code) is not int or not isinstance(p, list):
            raise ValueError("Invalid command code or parameters")
        if code == 0 and terminal and row is rows[-1] and not p:
            pass
        elif code == 101:
            if len(p) != 4 or not isinstance(p[0], str): raise ValueError("Invalid Show Text header")
            native_int(p[1], "face index", 0, 7); native_int(p[2], "background", 0, 2); native_int(p[3], "position", 0, 2)
        elif code in (401, 108, 408, 118, 119):
            if len(p) != 1 or not isinstance(p[0], str) or len(p[0]) > 2000:
                raise ValueError("Invalid text/comment/label parameter")
        elif code == 121:
            if len(p) != 3: raise ValueError("Invalid switch operation")
            native_int(p[0], "first switch", 1, 5000); native_int(p[1], "last switch", p[0], 5000); native_int(p[2], "switch value", 0, 1)
        elif code == 123:
            if scope != "map" or len(p) != 2 or p[0] not in ("A", "B", "C", "D"):
                raise ValueError("Self switches require a map event and A/B/C/D")
            native_int(p[1], "self switch value", 0, 1)
        elif code == 117:
            if len(p) != 1: raise ValueError("Invalid common event call")
            native_int(p[0], "common event id", 1)
        elif code == 230:
            if len(p) != 1: raise ValueError("Invalid wait")
            native_int(p[0], "wait frames", 1, 3600)
        elif code == 201:
            from vxace_transfers import transfer_rows
            if scope!='map':raise ValueError('New transfers are map-event only')
            transfer_rows([row])
        elif code == 125:
            if scope!='map' or len(p)!=3 or any(type(value) is not int for value in p) or p[:2]!=[0,0]:raise ValueError('Only constant positive map gold additions are enabled')
            native_int(p[2],'gold addition',1,99999999)
        elif code == 126:
            if scope!='map' or len(p)!=4 or any(type(value) is not int for value in p) or p[1:3]!=[0,0]:raise ValueError('Only constant positive map item additions are enabled')
            native_int(p[0],'reward item ID',1,999);native_int(p[3],'item addition',1,99)
        else:
            raise ValueError(f"New command code {code} is outside the validated native subset")
        result.append(RubyObject("RPG::EventCommand", {"@code": code, "@indent": 0, "@parameters": convert(p)}))
    if not terminal:
        validate_list(result + [RubyObject("RPG::EventCommand", {"@code": 0, "@indent": 0, "@parameters": []})])
    else:
        validate_list(result)
    return result


def owner_for(root, mutation, object_by_id):
    if mutation["scope"] == "map":
        if not isinstance(root, RubyObject) or root.cls != "RPG::Map" or not isinstance(root.get("events"), RubyHash):
            raise ValueError("Expected native map/event hash")
        identifier = native_int(mutation["event_id"], "event id", 1)
        matches = [v for k, v in root.get("events").pairs if type(k) is int and k == identifier]
        if len(matches) != 1 or not isinstance(matches[0], RubyObject) or matches[0].cls != "RPG::Event" or matches[0].get("id") != identifier:
            raise ValueError("Map event identity is ambiguous or missing")
        owner = matches[0]
        if sum(v is owner for k, v in root.get("events").pairs) != 1:
            raise ValueError("Aliased map event owner is refused")
        return owner
    if mutation["scope"] in ("troop", "common_event"):
        owner = object_by_id(root, mutation["troop_id"] if mutation["scope"] == "troop" else mutation["common_event_id"])
        if owner.cls != ("RPG::Troop" if mutation["scope"] == "troop" else "RPG::CommonEvent"):
            raise ValueError("Native event owner class required")
        return owner
    raise ValueError("Unsupported scope")


def snapshot(root, mutation, object_by_id):
    owner = owner_for(root, mutation, object_by_id)
    if mutation["scope"] == "common_event":
        holder = owner
        result = {}
    else:
        pages = owner.get("pages")
        if not isinstance(pages, list): raise ValueError("Missing page array")
        page = native_int(mutation.get("page", 1), "page", 1, len(pages))
        holder = pages[page - 1]
        result = {"pages_sha256": fingerprint(pages), "page_count": len(pages),
                  "page_sha256": fingerprint(holder), "page_hashes": [fingerprint(x) for x in pages],
                  "conditions": {
                      k.lstrip("@"): plain(v) for k, v in holder.get("condition").ivars.items()
                  } if isinstance(holder.get("condition"), RubyObject) else {}}
    commands = holder.get("list")
    boundaries = validate_list(commands)
    result.update(list_sha256=fingerprint(commands), command_count=len(commands),
                  boundaries=sorted(boundaries), commands=command_rows(commands))
    return result


def apply(root, mutation, convert, object_by_id, *, source_path=None):
    action, scope = mutation["action"], mutation["scope"]
    common = {"scope", "event_id", "troop_id", "common_event_id", "page", "command_index", "action"}
    specific = {"insert_commands": {"expected_list_sha256", "commands", "reward_guard", "transfer_guard"},
                "delete_commands": {"expected_list_sha256", "count"},
                "insert_page": {"expected_pages_sha256", "expected_template_sha256", "template_page", "conditions", "commands", "acknowledge_page_priority_change"},
                "delete_page": {"expected_pages_sha256", "expected_page_sha256", "acknowledge_page_priority_change"}}
    if action not in specific or set(mutation) - common - specific[action]:
        raise ValueError("Unknown structural mutation fields")
    from vxace_transfers import has_transfers,validate as validate_transfers
    if has_transfers(mutation):validate_transfers(root,mutation,source_path)
    elif 'transfer_guard' in mutation:raise ValueError('Transfer guard requires an actual direct transfer')
    from vxace_event_rewards import has_rewards,validate as validate_rewards
    if has_rewards(mutation):validate_rewards(root,mutation,source_path)
    elif 'reward_guard' in mutation:raise ValueError('Reward guard requires actual reward commands')
    owner = owner_for(root, mutation, object_by_id)
    pages = owner.get("pages") if scope != "common_event" else None
    if action in ("insert_page", "delete_page"):
        if scope == "common_event" or not isinstance(pages, list) or not pages:
            raise ValueError("Page edits require existing map/troop pages")
        if any(not isinstance(p, RubyObject) or
               (scope == "map" and (type(p.get("trigger")) is not int or p.get("trigger") not in (0,1,2))) or
               (scope == "troop" and (type(p.get("span")) is not int or p.get("span") not in (0,1))) for p in pages):
            raise ValueError("Repeating-trigger page structure changes are refused")
        for p in pages: validate_list(p.get('list'))
        require_hash(pages, mutation.get("expected_pages_sha256"), "Page array")
        if mutation.get("acknowledge_page_priority_change") is not True:
            raise ValueError("Page priority change must be explicitly acknowledged")
        position = native_int(mutation["page"], "page", 1, len(pages) + (action == "insert_page")) - 1
        updated = list(pages)
        if action == "delete_page":
            if len(pages) == 1: raise ValueError("Cannot delete the final page")
            require_hash(pages[position], mutation.get("expected_page_sha256"), "Deleted page")
            updated.pop(position)
        else:
            if len(pages) >= MAX_PAGES: raise ValueError("Tool page limit exceeded")
            template = pages[native_int(mutation["template_page"], "template page", 1, len(pages)) - 1]
            require_hash(template, mutation.get("expected_template_sha256"), "Template page")
            page = marshal_rb.load(marshal_rb.dump(template))
            expected_class = "RPG::Event::Page" if scope == "map" else "RPG::Troop::Page"
            if not isinstance(page, RubyObject) or page.cls != expected_class:
                raise ValueError("Native page class required")
            if scope == "map": page.set("trigger", 0)
            else: page.set("span", 0)
            condition = page.get("condition")
            patch = mutation.get("conditions")
            if not isinstance(condition, RubyObject) or not isinstance(patch, dict) or not patch:
                raise ValueError("Explicit native page conditions required")
            allowed = ({"switch1_valid", "switch1_id", "switch2_valid", "switch2_id", "self_switch_valid", "self_switch_ch"}
                       if scope == "map" else {"turn_valid", "turn_a", "turn_b", "switch_valid", "switch_id"})
            for field, value in patch.items():
                key = "@" + field
                if field not in allowed or key not in condition.ivars:
                    raise ValueError("Unsupported or unobserved page condition field")
                old = condition.ivars[key]
                if type(old) is bool:
                    if type(value) is not bool: raise ValueError("Condition requires a boolean")
                elif type(old) is int:
                    native_int(value, "condition value", 1 if field.endswith("_id") else 0)
                elif isinstance(old, RubyString):
                    if value not in ("A", "B", "C", "D"): raise ValueError("Invalid self switch")
                else: raise ValueError("Unsupported condition type")
                condition.ivars[key] = convert(value, old)
            if not any(value is True for field, value in patch.items() if field.endswith("_valid")):
                raise ValueError("New page needs an explicitly enabled native condition")
            page.set("list", new_commands(mutation.get("commands"), convert, scope, terminal=True))
            updated.insert(position, page)
        owner.set("pages", updated)
        return
    if scope == "common_event":
        if type(owner.get("trigger")) is not int or owner.get("trigger") != 0: raise ValueError("Repeating common event edits are refused")
        holder = owner
    else:
        if not isinstance(pages, list): raise ValueError("Missing pages")
        position = native_int(mutation["page"], "page", 1, len(pages)) - 1
        holder = pages[position]
        if (scope == "map" and (type(holder.get("trigger")) is not int or holder.get("trigger") not in (0,1,2)) or
            scope == "troop" and (type(holder.get("span")) is not int or holder.get("span") not in (0,1))):
            raise ValueError("Repeating-trigger structural edits are refused")
    commands = holder.get("list")
    require_hash(commands, mutation.get("expected_list_sha256"), "Command list")
    boundaries = validate_list(commands)
    index = native_int(mutation["command_index"], "command index", 0, len(commands)-1)
    if index not in boundaries: raise ValueError("Edit would split a compound command/block")
    if action == "insert_commands":
        inserted = new_commands(mutation.get("commands"), convert, scope)
        updated = commands[:index] + inserted + commands[index:]
    elif action == "delete_commands":
        end = index + native_int(mutation["count"], "delete count", 1, MAX_COMMANDS)
        if end not in boundaries or end > len(commands)-1:
            raise ValueError("Deletion would split a group or remove the final terminator")
        updated = commands[:index] + commands[end:]
    else: raise ValueError("Unsupported structural action")
    validate_list(updated)
    if scope != "common_event":
        holder = marshal_rb.load(marshal_rb.dump(holder))
        replacement = list(pages)
        replacement[position] = holder
        owner.set("pages", replacement)
    holder.set("list", updated)
