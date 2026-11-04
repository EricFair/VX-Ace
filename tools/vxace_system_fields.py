#!/usr/bin/env python3
"""Guarded System fields edit (v1.23): set_system_fields changes a bounded subset of Data/System.rvdata2 and nothing else.

Editable: game_title, currency_unit, party_members (starting party), start (start map and position) and the first terms
(basic 0..7, params 0..7, etypes 0..4, commands 0..22). Every other System ivar, including version_id, is preserved exactly.
Referenced databases are only read, each bound by its own expected SHA-256; the System itself is bound by expected_system_sha256."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from vxace_index_query import execute, unlinked
from vxace_staged_commands import check_text, plain_int, sha_text, load_array, load_mapinfos, load_map_size

VERSION = '1.33.0'
ACTION = 'set_system_fields'
FIELDS = ('game_title', 'currency_unit', 'party_members', 'start', 'terms', 'switch_names', 'variable_names')
NAME_FIELDS = {'switch_names': 'switches', 'variable_names': 'variables'}
MAX_NAME_ID = 5000
MAX_NAME = 32
BASE_FIELDS = {'action', 'expected_system_sha256'}
# Editable term indices per group and the native array length (Project3, editor-saved RPG::System::Terms: basic 8, params 8, etypes 5, commands 24).
TERM_COUNTS = {'basic': 8, 'params': 8, 'etypes': 5, 'commands': 23}
TERM_LENGTHS = {'basic': 8, 'params': 8, 'etypes': 5, 'commands': 24}
TERM_LABELS = {'basic': ['Level', 'Level (short)', 'HP', 'HP (short)', 'MP', 'MP (short)', 'TP', 'TP (short)'],
               'params': ['Max HP', 'Max MP', 'Attack', 'Defense', 'M.Attack', 'M.Defense', 'Agility', 'Luck'],
               'etypes': ['Weapon', 'Shield', 'Head', 'Body', 'Accessory'],
               'commands': ['Fight', 'Escape', 'Attack', 'Guard', 'Items', 'Skills', 'Equip', 'Status', 'Formation', 'Save', 'Game End', '(unused)',
                            'Weapons', 'Armor', 'Key Items', 'Equip command', 'Optimize', 'Clear', 'New Game', 'Continue', 'Shut Down', 'To Title', 'Cancel']}
MAX_PARTY = 8
MAX_MAP_ID = 999
MAX_CELL = 999
NATIVE_STRINGS = ('game_title', 'currency_unit')


def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def given_fields(mutation):
    return [name for name in FIELDS if name in mutation]


def term_index(group, key):
    """Canonical decimal index string within the editable range of the group."""
    if not isinstance(key, str) or not re.fullmatch('0|[1-9][0-9]?', key) or int(key) >= TERM_COUNTS[group]:
        raise ValueError(f'terms.{group} index must be a decimal string 0..{TERM_COUNTS[group] - 1}')
    return int(key)


def name_id(field, key):
    """Canonical decimal id of a switch / variable name entry."""
    if not isinstance(key, str) or not re.fullmatch('[1-9][0-9]{0,3}', key) or int(key) > MAX_NAME_ID:
        raise ValueError(f'{field} keys must be decimal id strings 1..{MAX_NAME_ID}')
    return int(key)


# ------------------------------------------------------------------ schema (no files)

def schema(mutation):
    """Pure shape and semantic validation of the spec. Raises ValueError."""
    if not isinstance(mutation, dict) or mutation.get('action') != ACTION:
        raise ValueError('Exact ' + ACTION + ' schema required')
    given = given_fields(mutation)
    if not given:
        raise ValueError('set_system_fields needs at least one of: ' + ', '.join(FIELDS))
    wanted = BASE_FIELDS | set(given) | ({'expected_actors_sha256'} if 'party_members' in given else set()) \
        | ({'expected_mapinfos_sha256', 'expected_start_map_sha256'} if 'start' in given else set())
    if set(mutation) != wanted:
        raise ValueError('Exact set_system_fields schema required: only ' + ', '.join(FIELDS) + ' with expected_system_sha256, plus expected_actors_sha256 for party_members '
                         'and expected_mapinfos_sha256 + expected_start_map_sha256 for start (no other keys)')
    for key in sorted(wanted - set(FIELDS) - {'action'}):
        sha_text(mutation[key], key)
    if 'game_title' in given:
        check_text(mutation['game_title'], 'game_title', 100)
    if 'currency_unit' in given:
        check_text(mutation['currency_unit'], 'currency_unit', 10)
    if 'party_members' in given:
        members = mutation['party_members']
        if not isinstance(members, list) or not 1 <= len(members) <= MAX_PARTY:
            raise ValueError(f'party_members must list 1..{MAX_PARTY} actor ids')
        for number in members:
            plain_int(number, 'party_members actor id', 1, 999)
        if len(set(members)) != len(members):
            raise ValueError('party_members must not repeat an actor')
    if 'start' in given:
        start = mutation['start']
        if not isinstance(start, dict) or set(start) != {'map_id', 'x', 'y'}:
            raise ValueError('start must be exactly {"map_id", "x", "y"}')
        plain_int(start['map_id'], 'start map_id', 1, MAX_MAP_ID);plain_int(start['x'], 'start x', 0, MAX_CELL);plain_int(start['y'], 'start y', 0, MAX_CELL)
    for field in NAME_FIELDS:
        if field in given:
            names = mutation[field]
            if not isinstance(names, dict) or not names:
                raise ValueError(f'{field} must be a non-empty object of id -> name')
            for key, value in names.items():
                name_id(field, key)
                check_text(value, f'{field}.{key}', MAX_NAME, True)
    if 'terms' in given:
        terms = mutation['terms']
        if not isinstance(terms, dict) or not terms or set(terms) - set(TERM_COUNTS):
            raise ValueError('terms must be a non-empty object whose keys are among: ' + ', '.join(TERM_COUNTS))
        for group, rows in terms.items():
            if not isinstance(rows, dict) or not rows:
                raise ValueError(f'terms.{group} must be a non-empty object of index -> text')
            for key, value in rows.items():
                term_index(group, key)
                check_text(value, f'terms.{group}.{key}', 32)


# ------------------------------------------------------------------ native System (read, validated)

def native_system(root):
    """Validated RPG::System root with the fields this operation edits; returns the Terms object."""
    from vxace_python_mutator import RubyObject, RubyString
    if not isinstance(root, RubyObject) or root.cls != 'RPG::System':
        raise ValueError('Native System must be an RPG::System')
    for key in NATIVE_STRINGS:
        value = root.get(key)
        if not isinstance(value, RubyString) or value.ivars not in ({}, {'E': True}, {'E': False}):
            raise ValueError(f'Native System {key} must be a plain string')
    members = root.get('party_members')
    if not isinstance(members, list) or any(type(number) is not int for number in members):
        raise ValueError('Native System party_members must be a list of integers')
    for key in ('start_map_id', 'start_x', 'start_y', 'version_id'):
        if type(root.get(key)) is not int:
            raise ValueError(f'Native System {key} must be an integer')
    terms = root.get('terms')
    if not isinstance(terms, RubyObject) or terms.cls != 'RPG::System::Terms':
        raise ValueError('Native System terms must be an RPG::System::Terms')
    for group, length in TERM_LENGTHS.items():
        values = terms.get(group)
        if not isinstance(values, list) or len(values) != length or any(not isinstance(item, RubyString) for item in values):
            raise ValueError(f'Native System terms.{group} must be {length} strings')
    return terms


def names_array(root, field):
    """The native switches / variables array (slot 0 nil or empty, one plain string per id) behind a name field."""
    from vxace_python_mutator import RubyString
    names = root.get(NAME_FIELDS[field])
    if not isinstance(names, list) or not 2 <= len(names) <= MAX_NAME_ID + 1 or (names[0] is not None and not isinstance(names[0], RubyString)):
        raise ValueError(f'Native System {NAME_FIELDS[field]} must be an array of 1..{MAX_NAME_ID} ids')
    for item in names[1:]:
        if not isinstance(item, RubyString) or item.ivars not in ({}, {'E': True}, {'E': False}):
            raise ValueError(f'Native System {NAME_FIELDS[field]} must hold plain strings')
    return names


def text_of(value):
    return value.data.decode('utf-8', 'replace') if value is not None else ''


def current(root):
    """Plain-Python view of the editable fields of a native System."""
    terms = native_system(root)
    return {'game_title': text_of(root.get('game_title')), 'currency_unit': text_of(root.get('currency_unit')),
            'party_members': list(root.get('party_members')),
            'start': {'map_id': root.get('start_map_id'), 'x': root.get('start_x'), 'y': root.get('start_y')},
            'terms': {group: [text_of(item) for item in terms.get(group)] for group in TERM_COUNTS},
            'version_id': root.get('version_id'),
            'switch_count': len(root.get('switches')) - 1, 'variable_count': len(root.get('variables')) - 1,
            'switch_names': {str(n): text_of(v) for n, v in enumerate(root.get('switches')) if n and text_of(v)},
            'variable_names': {str(n): text_of(v) for n, v in enumerate(root.get('variables')) if n and text_of(v)}}


# ------------------------------------------------------------------ references (read-only, hash-bound)

def reference_checks(mutation, project):
    """Bind party_members to the Actors array and start to MapInfos + the start map; returns evidence for the audit."""
    evidence = {}
    if 'party_members' in mutation:
        actors = load_array(project, 'actors')
        if mutation['expected_actors_sha256'] != digest(actors):
            raise ValueError('Native Actors is stale (expected_actors_sha256)')
        for number in mutation['party_members']:
            if not 1 <= number < len(actors) or actors[number] is None:
                raise ValueError(f'party_members actor {number} does not exist in the fingerprinted Actors array')
        evidence['actors_sha256'] = mutation['expected_actors_sha256']
    if 'start' in mutation:
        infos = load_mapinfos(project)
        if mutation['expected_mapinfos_sha256'] != digest(infos):
            raise ValueError('Native MapInfos is stale (expected_mapinfos_sha256)')
        start = mutation['start']
        if start['map_id'] not in {key for key, _ in infos.pairs}:
            raise ValueError(f'start map {start["map_id"]} does not exist in MapInfos')
        root, width, height = load_map_size(project, start['map_id'])
        if mutation['expected_start_map_sha256'] != digest(root):
            raise ValueError('Native start map is stale (expected_start_map_sha256)')
        if start['x'] >= width or start['y'] >= height:
            raise ValueError(f'start ({start["x"]},{start["y"]}) lies outside map {start["map_id"]} ({width}x{height})')
        evidence.update(mapinfos_sha256=mutation['expected_mapinfos_sha256'], start_map_sha256=mutation['expected_start_map_sha256'], start_map_size=[width, height])
    return evidence


def validate(root, mutation, project):
    """Everything that must hold before the write; returns the old plain view. Refuses stale hashes and no-op fields."""
    schema(mutation)
    old = current(root)
    if mutation['expected_system_sha256'] != digest(root):
        raise ValueError('Native System is stale (expected_system_sha256)')
    if project is None:
        raise ValueError('set_system_fields needs the native project to check the referenced databases and maps')
    reference_checks(mutation, project)
    for key in ('game_title', 'currency_unit', 'party_members', 'start'):
        if key in mutation and mutation[key] == old[key]:
            raise ValueError(f'{key} already has this value; remove it from the spec')
    for group, rows in mutation.get('terms', {}).items():
        for key, value in rows.items():
            if old['terms'][group][int(key)] == value:
                raise ValueError(f'terms.{group}.{key} already has this value; remove it from the spec')
    for field, native in NAME_FIELDS.items():
        if field in mutation:
            names_array(root, field)
            count = len(root.get(native)) - 1
            for key, value in mutation[field].items():
                if int(key) > count:
                    raise ValueError(f'{field} id {key} is outside the {count} {native} of the fingerprinted System')
                if old[field].get(key, '') == value:
                    raise ValueError(f'{field}.{key} already has this value; remove it from the spec')
    return old


# ------------------------------------------------------------------ construction

def write(root, mutation):
    """Set exactly the requested fields; strings and the party list become new objects (nothing shared is edited in place)."""
    from vxace_python_mutator import convert
    terms = native_system(root)
    for key in NATIVE_STRINGS:
        if key in mutation:
            root.set(key, convert(mutation[key], root.get(key)))
    if 'party_members' in mutation:
        root.set('party_members', list(mutation['party_members']))
    if 'start' in mutation:
        start = mutation['start']
        root.set('start_map_id', start['map_id']);root.set('start_x', start['x']);root.set('start_y', start['y'])
    for group, rows in mutation.get('terms', {}).items():
        values = terms.get(group)
        for key, value in rows.items():
            values[int(key)] = convert(value, values[int(key)])
    for field, native in NAME_FIELDS.items():
        if field in mutation:
            names = names_array(root, field)
            for key, value in mutation[field].items():
                names[int(key)] = convert(value, names[int(key)])


def apply(root, mutation, project=None):
    validate(root, mutation, project)
    write(root, mutation)


def changed_ivars(mutation):
    names = {'game_title': 'game_title', 'currency_unit': 'currency_unit', 'party_members': 'party_members', 'terms': 'terms',
             'switch_names': 'switches', 'variable_names': 'variables'}
    out = {names[key] for key in names if key in mutation}
    if 'start' in mutation:
        out |= {'start_map_id', 'start_x', 'start_y'}
    return out


def verify_transition(before, after, mutation, project):
    """The candidate equals the approved result, version_id is unchanged and every other System ivar is deep-equal."""
    from vxace_python_mutator import marshal_rb
    native_system(before);native_system(after)
    if list(before.ivars) != list(after.ivars):
        raise ValueError('System candidate changed the ivar set or order')
    allowed = changed_ivars(mutation)
    for key in before.ivars:
        if key[1:] in allowed:
            continue
        if marshal_rb.dump(before.ivars[key]) != marshal_rb.dump(after.ivars[key]):
            raise ValueError(f'System candidate changed unapproved field {key[1:]}')
    if before.get('version_id') != after.get('version_id'):
        raise ValueError('System candidate changed version_id')
    expected = marshal_rb.load(marshal_rb.dump(before))
    apply(expected, mutation, project)
    if digest(after) != digest(expected):
        raise ValueError('System candidate differs from the approved result')
    for field, native in NAME_FIELDS.items():
        if len(before.get(native)) != len(after.get(native)):
            raise ValueError(f'System candidate changed the length of {native}')
        wanted_names = {int(key) for key in mutation.get(field, {})}
        for number, (old, new) in enumerate(zip(before.get(native), after.get(native))):
            if number not in wanted_names and marshal_rb.dump(old) != marshal_rb.dump(new):
                raise ValueError(f'System candidate changed unapproved {native}[{number}]')
    # terms: only the approved indices differ
    wanted = {(group, int(key)) for group, rows in mutation.get('terms', {}).items() for key in rows}
    for group in TERM_COUNTS:
        for number, (old, new) in enumerate(zip(before.get('terms').get(group), after.get('terms').get(group))):
            if (group, number) not in wanted and marshal_rb.dump(old) != marshal_rb.dump(new):
                raise ValueError(f'System candidate changed unapproved term {group}[{number}]')


# ------------------------------------------------------------------ plain-language description (impact)

def describe(mutation, old, actor_names, map_names, map_size=None, options=None):
    """(rows, warnings) for the report. `old` is `current()`-shaped; `actor_names` {id: name}; `map_names` {id: name}."""
    options = options or {}
    rows, warnings = [], []
    if 'game_title' in mutation:
        rows.append({'field': 'game_title', 'old': old['game_title'], 'new': mutation['game_title']})
        warnings.append('game_title is only drawn on the title screen (and only while the System option "draw game title" is on, '
                        'opt_draw_title=' + str(options.get('opt_draw_title')) + '); the window caption comes from Game.ini, which is not changed.')
    if 'currency_unit' in mutation:
        rows.append({'field': 'currency_unit', 'old': old['currency_unit'], 'new': mutation['currency_unit']})
        warnings.append('currency_unit is read live by Vocab::currency_unit (\\G in messages, the gold and shop windows): old saves show the new unit; '
                        'event texts that hard-code the old unit are not rewritten, and a longer unit can clip the gold window.')
    if 'party_members' in mutation:
        label = lambda number: f'{number} "{actor_names.get(number)}"' if actor_names.get(number) else str(number)
        rows.append({'field': 'party_members', 'old': [label(n) for n in old['party_members']], 'new': [label(n) for n in mutation['party_members']]})
        warnings.append('The starting party changes: new games start with these actors (Game_Party#setup_starting_members); old saves keep the party stored in the save.')
        if len(mutation['party_members']) > 4:
            warnings.append('More than 4 starting members: only the first 4 fight in battle (the rest wait in reserve).')
        if mutation['party_members'][:1] != old['party_members'][:1]:
            warnings.append('The first member is the leader shown on the map: check its walking graphic.')
    if 'start' in mutation:
        new, before = mutation['start'], old['start']
        label = lambda s: f'map {s["map_id"]}' + (f' "{map_names.get(s["map_id"])}"' if map_names.get(s['map_id']) else '') + f' at ({s["x"]},{s["y"]})'
        rows.append({'field': 'start', 'old': label(before), 'new': label(new)})
        warnings.append('The start position moves: new games begin at the new place; old saves keep their saved map and position. '
                        'Passability, events on the start cell and the BGM of the start map are not checked here.')
        if map_size:
            rows[-1]['start_map_size'] = list(map_size)
    for group, entries in mutation.get('terms', {}).items():
        for key in sorted(entries, key=int):
            index = int(key)
            rows.append({'field': f'terms.{group}[{index}]', 'meaning': TERM_LABELS[group][index], 'old': old['terms'][group][index], 'new': entries[key]})
    for field, label in (('switch_names', 'switch'), ('variable_names', 'variable')):
        if field in mutation:
            for key in sorted(mutation[field], key=int):
                rows.append({'field': f'{field}[{key}]', 'meaning': f'{label} {key}', 'old': old[field].get(key, ''), 'new': mutation[field][key]})
            warnings.append(f'{label.title()} names are editor labels only: they are not stored in saves and change no behavior; an empty name clears the label. '
                            f'Impact and plan reports stop calling these ids unnamed once the names are set.')
    if 'terms' in mutation:
        warnings.append('Terms are read live by Vocab (menus, battle, equipment and shop windows): old saves show the new text; long words can clip their window, and scripts that compare term strings are not analysed.')
    warnings.append('System version_id is not advanced: none of these fields is stored in saves, and a version change would only force old saves to rebuild their current map.')
    return rows, warnings


# ------------------------------------------------------------------ snapshot

def snapshot(root, project, start_map=None):
    from vxace_python_mutator import RubyString
    old = current(root)
    result = {'system_sha256': digest(root), **{key: old[key] for key in ('game_title', 'currency_unit', 'start', 'version_id', 'switch_count', 'variable_count', 'switch_names', 'variable_names')},
              'terms': {group: [{'index': number, 'meaning': TERM_LABELS[group][number], 'text': old['terms'][group][number]} for number in range(TERM_COUNTS[group])]
                        for group in TERM_COUNTS},
              'options': {'opt_draw_title': root.get('opt_draw_title')}}
    actors = load_array(project, 'actors')
    names = {number: (text_of(entry.get('name')) if isinstance(entry.get('name'), RubyString) else '') for number, entry in enumerate(actors) if entry is not None}
    result.update(actors_sha256=digest(actors), actors_count=len(actors) - 1, actor_names={str(number): name for number, name in names.items()},
                  party_members=[{'id': number, 'name': names.get(number)} for number in old['party_members']])
    infos = load_mapinfos(project)
    result['mapinfos_sha256'] = digest(infos)
    map_names = {key: text_of(value.get('name')) for key, value in infos.pairs if isinstance(value.get('name'), RubyString)}
    result['map_ids'] = sorted(map_names)
    result['map_names'] = {str(key): map_names[key] for key in sorted(map_names)}
    if start_map is not None:
        map_root, width, height = load_map_size(project, start_map)
        if start_map not in map_names:
            raise ValueError(f'Map {start_map} is not in MapInfos')
        result['start_map'] = {'map_id': start_map, 'sha256': digest(map_root), 'width': width, 'height': height, 'name': map_names[start_map]}
    return result


def indexed_snapshot(data, project, start_map=None):
    from vxace_python_mutator import load
    root, _ = load(unlinked(Path(project) / 'Data/System.rvdata2'))
    result = snapshot(root, project, start_map)
    indexed = data.json('database/system.json')
    if not isinstance(indexed, dict) or indexed.get('__class__') != 'RPG::System' or indexed.get('game_title') != result['game_title'] \
       or indexed.get('currency_unit') != result['currency_unit'] or indexed.get('party_members') != [m['id'] for m in result['party_members']] \
       or indexed.get('version_id') != result['version_id']:
        raise ValueError('Indexed/native System disagree')
    return {'version': VERSION, **result,
            'limits': ['Edits only game_title (1..100), currency_unit (1..10), party_members (1..8 unique existing actors), start (existing map + in-bounds cell) and terms basic 0..7, params 0..7, etypes 0..4, commands 0..22 (1..32 characters each).',
                       'switch_names / variable_names set the editor label of switch / variable ids 1..N (decimal id string -> literal name of 0..32 characters, empty clears it); only the listed array slots change.',
                       'Every other System ivar, including version_id, sounds and option flags, is preserved; no other file changes.',
                       'version_id is not advanced: these fields are not stored in saves, so old saves keep their party, map and position; terms and currency_unit show the new text on load; game_title shows on the title screen only.',
                       'party_members is bound by expected_actors_sha256; start by expected_mapinfos_sha256 and expected_start_map_sha256 (pass --start-map to this snapshot to get the map hash and size); the start cell is not checked for passability.',
                       'Texts are literal (no escape codes); the spec may not contain fields outside this list. Snapshot is not mutation permission.']}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Read-only snapshot for the guarded System fields edit (set_system_fields).')
    ap.add_argument('index');ap.add_argument('--project', required=True);ap.add_argument('--output', required=True)
    ap.add_argument('--start-map', type=int, help='Also report the hash and size of this map (the start map to bind)')
    args = ap.parse_args(argv)
    try:
        project = unlinked(args.project)
        if project.is_file() and project.suffix.lower() == '.rvproj2':
            project = project.parent
        result = execute(args.index, project, args.output, lambda data: indexed_snapshot(data, project, args.start_map), 'system-fields-snapshot')
    except Exception as error:
        print('System fields snapshot refused: ' + str(error), file=sys.stderr);return 2
    print(json.dumps({'version': VERSION, 'system_sha256': result['system_sha256']}));return 0


if __name__ == '__main__':
    raise SystemExit(main())
