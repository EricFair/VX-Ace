#!/usr/bin/env python3
"""Guarded common event append (v1.21): one new RPG::CommonEvent at the next id of Data/CommonEvents.rvdata2.

The commands are the v1.19 staged-command language (vxace_staged_commands), reused unchanged. The entry is built from the editor-saved
RPG::CommonEvent layout (there is no template); referenced databases and System are only read, each bound by its own expected hash."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from vxace_index_query import execute, unlinked
from vxace_staged_commands import (commands_shape, iter_ops, staged_ids, ref_fields, check_references, native_rows, structure_check,
                                   reference_snapshot, check_text, sha_text, plain_int, describe_route, command_notes)

VERSION = '1.21.0'
ACTION = 'append_common_event'
BASE_FIELDS = {'action', 'new_id', 'name', 'trigger', 'commands', 'expected_common_events_sha256', 'expected_system_sha256'}
# Editor-saved RPG::CommonEvent (Project3, 10 entries): ivars in this order, name a UTF-8 string, trigger/switch_id/id integers.
# The editor keeps unused slots as empty common events (name '', trigger 0, switch_id 1, list = terminator), never nil.
IVAR_ORDER = ('trigger', 'name', 'switch_id', 'list', 'id')
TRIGGERS = {'none': 0, 'parallel': 2}
NONE_SWITCH_ID = 1      # what the editor stores for a call-only common event (its switch is unused)
MAX_ID = 999
MAX_ARRAY = 5001


def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def wrap(commands):
    """The staged helpers work on pages; a common event is one unconditional page."""
    return [{'condition': {}, 'commands': commands}]


# ------------------------------------------------------------------ schema (no files)

def schema(mutation):
    """Pure shape and semantic validation of the spec. Raises ValueError."""
    if not isinstance(mutation, dict) or mutation.get('action') != ACTION:
        raise ValueError('Exact ' + ACTION + ' schema required')
    trigger = mutation.get('trigger')
    if not isinstance(trigger, str) or trigger not in TRIGGERS:
        raise ValueError('trigger must be "none" (call only) or "parallel"; autorun is refused because it has no termination proof')
    commands = mutation.get('commands')
    commands_shape(commands)
    wanted = BASE_FIELDS | ref_fields(wrap(commands)) | ({'switch_id'} if trigger == 'parallel' else set())
    if set(mutation) != wanted:
        raise ValueError('Exact append_common_event schema required (switch_id only for parallel, plus one expected hash per referenced database)')
    plain_int(mutation['new_id'], 'new common event ID', 1, MAX_ID)
    check_text(mutation['name'], 'common event name', 100)
    sha_text(mutation['expected_common_events_sha256'], 'expected_common_events_sha256')
    sha_text(mutation['expected_system_sha256'], 'expected_system_sha256')
    if trigger == 'parallel':
        plain_int(mutation['switch_id'], 'parallel switch_id', 1, 2**31 - 1)
        if not any('wait' in op for op in iter_ops(commands)):
            raise ValueError('A parallel common event needs at least one wait command (it repeats every frame while its switch is ON)')
    for op in iter_ops(commands):
        if 'set_self_switch' in op:
            raise ValueError('set_self_switch is refused in a common event: self switches need an owning map event')
        if isinstance(op.get('if'), dict) and 'self_switch' in op['if']:
            raise ValueError('The self_switch condition is refused in a common event: self switches need an owning map event')
        if 'erase_event' in op:
            raise ValueError('erase_event is refused in a common event: there is no owning event to erase')
        if isinstance(op.get('move_route'), dict) and op['move_route'].get('target') == 'this':
            raise ValueError('A move_route targeting "this" is refused in a common event: there is no owning event (target the player instead)')
        if 'common_event' in op and op['common_event'] == mutation['new_id']:
            raise ValueError('A common event cannot call its own new id (direct recursion)')


# ------------------------------------------------------------------ native array

def common_event_array(root):
    """Validated native CommonEvents array: nil slot zero, every non-nil entry an editor-layout RPG::CommonEvent with its slot id."""
    from vxace_python_mutator import RubyObject, RubyString
    if not isinstance(root, list) or not 2 <= len(root) <= MAX_ARRAY or root[0] is not None:
        raise ValueError('Native CommonEvents must be an array with nil slot zero')
    wanted = {'@' + key for key in IVAR_ORDER}
    for slot, entry in enumerate(root[1:], 1):
        if entry is None:
            continue
        if not isinstance(entry, RubyObject) or entry.cls != 'RPG::CommonEvent' or set(entry.ivars) != wanted:
            raise ValueError(f'Native CommonEvents entry {slot} is not an RPG::CommonEvent with the editor field set')
        if any(type(entry.get(key)) is not int for key in ('trigger', 'switch_id', 'id')) or entry.get('id') != slot:
            raise ValueError(f'Native CommonEvents entry {slot} has an unsupported id/trigger/switch_id')
        if not isinstance(entry.get('name'), RubyString) or not isinstance(entry.get('list'), list):
            raise ValueError(f'Native CommonEvents entry {slot} has an unsupported name or list')
    if len({id(entry) for entry in root[1:] if entry is not None}) != sum(entry is not None for entry in root[1:]):
        raise ValueError('Aliased CommonEvents entries are unsupported')
    return root


def entry_name(entry):
    return entry.get('name').data.decode('utf-8', 'replace')


def is_blank(entry):
    commands = entry.get('list')
    return entry_name(entry) == '' and len(commands) == 1 and getattr(commands[0], 'ivars', {}).get('@code') == 0


def project_system(project, expected=None):
    from vxace_map_events import system_info
    return system_info(project, expected)


# ------------------------------------------------------------------ construction

def new_common_event(root, mutation, project):
    """The exact factory result for a validated spec against the pre-append array `root`."""
    from vxace_python_mutator import RubyObject, RubyString
    schema(mutation)
    common_event_array(root)
    new_id = mutation['new_id']
    if new_id != len(root):
        raise ValueError('New common event ID must append at the exact next array slot')
    if mutation['expected_common_events_sha256'] != digest(root):
        raise ValueError('Native CommonEvents is stale')
    if project is None:
        raise ValueError('Common event appends need the native project to read System and the referenced databases')
    info = project_system(project, mutation['expected_system_sha256'])
    commands = mutation['commands'];pages = wrap(commands)
    staged_ids(pages, len(info['switches']), len(info['variables']))
    if mutation['trigger'] == 'parallel' and not 1 <= mutation['switch_id'] <= len(info['switches']) - 1:
        raise ValueError(f'parallel switch_id {mutation["switch_id"]} is outside the native System switches 1..{len(info["switches"]) - 1}')
    name = mutation['name']
    for entry in root[1:]:
        if entry is not None and entry_name(entry) == name:
            raise ValueError('New common event name must be unique')
    check_references({**mutation, 'pages': pages}, project)   # common events are checked against the pre-append array

    def literal(value):
        return RubyString(value.encode('utf-8'), {'E': True})

    def command(code, indent, parameters):
        return RubyObject('RPG::EventCommand', {'@indent': indent, '@code': code, '@parameters': parameters})
    rows = native_rows(commands, command, literal)
    structure_check(rows)
    values = {'trigger': TRIGGERS[mutation['trigger']], 'name': literal(name),
              'switch_id': mutation['switch_id'] if mutation['trigger'] == 'parallel' else NONE_SWITCH_ID, 'list': rows, 'id': new_id}
    return RubyObject('RPG::CommonEvent', {'@' + key: values[key] for key in IVAR_ORDER})


def apply(root, mutation, project=None):
    root.append(new_common_event(root, mutation, project))


def verify_transition(before, after, mutation, project):
    common_event_array(before);common_event_array(after)
    if len(after) != len(before) + 1 or digest(after[:-1]) != digest(before):
        raise ValueError('Common event candidate changed existing entries or array shape')
    if digest(after[-1]) != digest(new_common_event(before, mutation, project)):
        raise ValueError('Common event candidate differs from the approved factory result')
    from vxace_event_structure import validate_list
    validate_list(after[-1].get('list'))


# ------------------------------------------------------------------ snapshot

def snapshot(root, project, transfer_maps=()):
    common_event_array(root)
    info = project_system(project)
    entries = [entry for entry in root[1:] if entry is not None]
    result = {'next_id': len(root), 'existing_entries': len(root) - 1, 'append_slot_supported': len(root) <= MAX_ID,
              'empty_slot_ids': [entry.get('id') for entry in entries if is_blank(entry)],
              'named_events': [{'id': entry.get('id'), 'name': entry_name(entry), 'trigger': entry.get('trigger'), 'switch_id': entry.get('switch_id')}
                               for entry in entries if entry_name(entry)],
              'trigger_values': dict(TRIGGERS), 'none_switch_id': NONE_SWITCH_ID, 'field_order': list(IVAR_ORDER),
              'system_sha256': info['system_sha256'], 'switch_count': len(info['switches']) - 1, 'variable_count': len(info['variables']) - 1,
              'switch_names': info['switches'][1:], 'variable_names': info['variables'][1:]}
    result.update(reference_snapshot(project, transfer_maps))
    result['common_events_sha256'] = digest(root)
    return result


def indexed_snapshot(data, project, transfer_maps=()):
    from vxace_python_mutator import load
    root, _ = load(unlinked(Path(project) / 'Data/CommonEvents.rvdata2'))
    result = snapshot(root, project, transfer_maps)
    indexed = data.json('database/common-events.json')
    if not isinstance(indexed, list) or len(indexed) != len(root) or indexed[0] is not None:
        raise ValueError('Indexed/native CommonEvents array sizes disagree')
    for slot, (row, entry) in enumerate(zip(indexed, root)):
        if slot and (row is None) != (entry is None):
            raise ValueError('Indexed/native CommonEvents slots disagree')
        if slot and entry is not None and (not isinstance(row, dict) or row.get('__class__') != 'RPG::CommonEvent' or row.get('id') != slot or row.get('name') != entry_name(entry)):
            raise ValueError('Indexed/native CommonEvents identities disagree')
    return {'version': VERSION, **result,
            'limits': ['Appends one call-only or parallel-process common event at the next id; existing entries (including the editor\'s empty placeholder slots) are never reused or edited.',
                       'Commands are the staged-event command language; switch/variable ids are bound by system_sha256 and every referenced database by its own hash (common_events_sha256 is the target array itself).',
                       'No autorun, no self switches, no scripts, no calls to the new event\'s own id. A parallel event needs a wait and a switch; review when that switch is turned OFF.',
                       'Nothing calls the new event yet; wire it from an event, item/skill effect 44 or a recipe from_step reference. System is not written.']}


# ------------------------------------------------------------------ human description (impact)

def describe(commands, lookup, depth=0):
    """Plain-language lines for a validated command list; `lookup(kind, id)` returns a database name or None."""
    pad = '  ' * depth

    def named(kind, number):
        label = lookup(kind, number)
        return f'{kind} {number} "{label}"' if label else f'{kind} {number} (unnamed)'

    def condition(cond):
        if 'switch' in cond:
            return f'{named("switch", cond["switch"])} is {"ON" if cond["is"] else "OFF"}'
        if 'variable' in cond:
            return f'{named("variable", cond["variable"])} {cond["op"]} {cond["value"]}'
        if 'gold_at_least' in cond:
            return f'the party has at least {cond["gold_at_least"]} gold'
        return f'the party has {named("item", cond["has_item"])}'
    lines = []
    for op in commands:
        if 'text' in op:
            lines.append(pad + 'Show text: ' + ' / '.join('"' + line + '"' for line in op['text']))
        elif 'set_switch' in op:
            lines.append(pad + f'Turn {named("switch", op["set_switch"])} {"ON" if op["value"] else "OFF"}')
        elif 'set_variable' in op:
            target = named('variable', op['set_variable'])
            lines.append(pad + {'set': f'Set {target} to {op["value"]}', 'add': f'Add {op["value"]} to {target}', 'sub': f'Subtract {op["value"]} from {target}'}[op['op']])
        elif 'choices' in op:
            cancel = 'cannot be cancelled' if op['cancel'] is None else f'cancel picks "{op["choices"][op["cancel"]]}"'
            lines.append(pad + 'Ask: ' + ' / '.join('"' + choice + '"' for choice in op['choices']) + f' ({cancel})')
            for choice, branch in zip(op['choices'], op['branches']):
                lines.append(pad + f'  When "{choice}":')
                lines += describe(branch, lookup, depth + 2) or [pad + '    (nothing)']
        elif 'if' in op:
            lines.append(pad + 'If ' + condition(op['if']) + ':')
            lines += describe(op['then'], lookup, depth + 1)
            if 'else' in op:
                lines.append(pad + 'Otherwise:')
                lines += describe(op['else'], lookup, depth + 1)
        elif 'battle' in op:
            flags = [text for flag, text in (('can_escape', 'can escape'), ('can_lose', 'can lose')) if op[flag]]
            lines.append(pad + f'Battle {named("troop", op["battle"])} ({", ".join(flags) if flags else "no escape, defeat is Game Over"})')
            for key, label in (('win', 'On victory'), ('escape', 'On escape'), ('lose', 'On defeat')):
                if key in op:
                    lines.append(pad + f'  {label}:')
                    lines += describe(op[key], lookup, depth + 2) or [pad + '    (nothing)']
        elif 'party' in op:
            lines.append(pad + ('Add ' if op['party'] == 'add' else 'Remove ') + named('actor', op['actor']) + (' to the party' if op['party'] == 'add' else ' from the party')
                         + (' (reset to initial state)' if op['initialize'] else ''))
        elif 'common_event' in op:
            lines.append(pad + 'Call ' + named('common event', op['common_event']))
        elif 'gold' in op:
            lines.append(pad + (f'Give {op["gold"]} gold' if op['gold'] > 0 else f'Take {-op["gold"]} gold'))
        elif any(kind in op for kind in ('item', 'weapon', 'armor')):
            kind = next(kind for kind in ('item', 'weapon', 'armor') if kind in op)
            lines.append(pad + (f'Give {op["amount"]} x ' if op['amount'] > 0 else f'Take {-op["amount"]} x ') + named(kind, op[kind]))
        elif 'transfer' in op:
            move = op['transfer']
            facing = {0: 'keeping the facing', 2: 'facing down', 4: 'facing left', 6: 'facing right', 8: 'facing up'}[move['direction']]
            fade = {0: 'black fade', 1: 'white fade', 2: 'no fade'}[move['fade']]
            lines.append(pad + f'Transfer the player to {named("map", move["map_id"])} at ({move["x"]},{move["y"]}), {facing}, {fade}')
        elif 'wait' in op:
            lines.append(pad + f'Wait {op["wait"]} frames')
        elif 'erase_event' in op:
            lines.append(pad + 'Erase this event (temporary until the map is reloaded)')
        elif 'move_route' in op:
            spec = op['move_route']
            flags = [text for flag, text, default in (('repeat', 'repeating', False), ('skippable', 'skips blocked steps', False), ('wait', 'waits until it finishes', True)) if spec.get(flag, default)]
            lines.append(pad + f'Move {"the player" if spec["target"] == "player" else "this event"}: {describe_route(spec["route"])}' + (f' ({", ".join(flags)})' if flags else ' (does not wait)'))
    return lines


def analyse(mutation, lookup):
    """Summary lines, called common events and warnings for a validated spec; `lookup(kind, id)` returns a name or None."""
    commands = mutation['commands'];warnings = []
    ops = list(iter_ops(commands))
    parallel = mutation['trigger'] == 'parallel'

    def label(kind, number):
        return bool(lookup(kind, number))

    def unnamed(kind, number, verb):
        if not label(kind, number):
            warnings.append(f'{verb} unnamed {kind} {number}.')
    if parallel:
        switch = mutation['switch_id']
        named_switch = f'switch {switch} "{lookup("switch", switch)}"' if label('switch', switch) else f'switch {switch}'
        warnings.append(f'Parallel process: it repeats every frame while {named_switch} is ON; an untouched ON switch keeps it running for the whole play session.')
        unnamed('switch', switch, 'The trigger switch is an')
        if not any(op.get('set_switch') == switch and op.get('value') is False for op in ops):
            warnings.append(f'No command turns trigger switch {switch} OFF; something else must stop the parallel process.')
        if not any('wait' in op for op in commands):
            warnings.append('Every wait is inside a branch, so a frame that takes another path runs with no wait; put a wait at the top level.')
    for op in ops:
        if 'set_switch' in op:
            unnamed('switch', op['set_switch'], 'Sets an')
        elif 'set_variable' in op:
            unnamed('variable', op['set_variable'], 'Sets an')
        elif isinstance(op.get('if'), dict):
            if 'switch' in op['if']:
                unnamed('switch', op['if']['switch'], 'Tests an')
            elif 'variable' in op['if']:
                unnamed('variable', op['if']['variable'], 'Tests an')
        if 'battle' in op:
            warnings.append(f'Starts a battle (troop {op["battle"]}): check escape/lose branches and that the player cannot soft-lock.')
        if 'transfer' in op:
            warnings.append(f'Transfers the player to map {op["transfer"]["map_id"]}: check the destination cell is passable.')
        if 'gold' in op and op['gold'] < 0:
            warnings.append('Removes gold; the engine clamps at zero without a branch, so guard it with a gold_at_least condition.')
        for kind in ('weapon', 'armor'):
            if kind in op and op['amount'] < 0:
                warnings.append(f'Removes {kind} {op[kind]}; the engine clamps at zero, so the party may not own it. Equipped copies are not removed.')
    for op in ops:
        for note in command_notes(op):
            if note not in warnings:
                warnings.append(note)
    calls = []
    for op in ops:
        if 'common_event' in op and op['common_event'] not in [call['id'] for call in calls]:
            calls.append({'id': op['common_event'], 'name': lookup('common event', op['common_event'])})
    for call in calls:
        warnings.append(f'Calls common event {call["id"]}' + (f' "{call["name"]}"' if call['name'] else ' (unnamed)') + '; review what it does.')
    return {'summary': describe(commands, lookup), 'calls': calls, 'warnings': warnings}


def call_edges(rows, ids, spend=lambda: None):
    """Direct 117 call edges (source, target) between common events, from indexed common-events.json rows (targets in `ids` only)."""
    edges = []
    for slot, row in enumerate(rows):
        if slot == 0 or not isinstance(row, dict) or not isinstance(row.get('list'), list):
            continue
        for command in row['list']:
            spend()
            parameters = command.get('parameters') if isinstance(command, dict) else None
            if isinstance(command, dict) and command.get('code') == 117 and isinstance(parameters, list) and len(parameters) == 1 \
               and type(parameters[0]) is int and parameters[0] in ids:
                edges.append((slot, parameters[0]))
    return edges


# ------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description='Read-only snapshot for the guarded common event append (append_common_event).')
    ap.add_argument('index');ap.add_argument('--project', required=True);ap.add_argument('--output', required=True)
    ap.add_argument('--transfer-map', type=int, action='append', default=[], help='Also report the hash and size of a transfer destination map')
    args = ap.parse_args(argv)
    try:
        project = unlinked(args.project)
        if project.is_file() and project.suffix.lower() == '.rvproj2':
            project = project.parent
        result = execute(args.index, project, args.output, lambda data: indexed_snapshot(data, project, tuple(args.transfer_map)), 'common-event-snapshot')
    except Exception as error:
        print('Common event snapshot refused: ' + str(error), file=sys.stderr);return 2
    print(json.dumps({'version': VERSION, 'next_id': result['next_id']}));return 0


if __name__ == '__main__':
    raise SystemExit(main())
