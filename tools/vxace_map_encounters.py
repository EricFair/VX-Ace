#!/usr/bin/env python3
"""Read-only native map encounter evidence and guarded single-encounter appends for copy staging."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from vxace_index_query import execute, unlinked
from vxace_map_regions import integer, table_for
from vxace_maps import MAP_FIELDS, plain
from vxace_map_events import exact
from vxace_map_names import fingerprint

VERSION = '1.12.0'
ACTION = 'append_encounter'
FIELDS = {'action', 'expected_map_sha256', 'expected_encounter_count', 'expected_troops_sha256',
          'troop_id', 'weight', 'region_ids', 'encounter_step'}
ENCOUNTER_CLASS = 'RPG::Map::Encounter'
ENCOUNTER_FIELDS = {'troop_id', 'weight', 'region_set'}
MAX_ENCOUNTERS = 1000
MAX_REGIONS = 32


def sha(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError(label + ' must be a lowercase SHA-256')
    return value


def troops_digest(troops):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(troops)).hexdigest()


def troops_for(path):
    """Read-only load of Data/Troops.rvdata2 beside a native Data file (same snapshot/copy); returns the dense array."""
    from vxace_python_mutator import load
    from vxace_database_append import database_array
    file = unlinked(path)
    if file.parent.name != 'Data':
        raise ValueError('Encounter append requires a native project Data path to read Troops')
    root, _ = load(unlinked(file.parent / 'Troops.rvdata2'))
    return database_array(root, 'troops')


def region_set(value, label='region set'):
    if not isinstance(value, list) or len(value) > MAX_REGIONS:
        raise ValueError(label + ' must be a list of at most 32 editor regions')
    ids = [integer(x, 'region ID', 1, 63) for x in value]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate region ID')
    return sorted(ids)


def existing(root):
    """Validate the whole native map and its encounter list; return [(troop_id, weight, sorted regions)]."""
    from vxace_python_mutator import RubyObject
    exact(root, 'RPG::Map', MAP_FIELDS)
    table_for(root)
    entries = root.get('encounter_list')
    if not isinstance(entries, list) or len(entries) > MAX_ENCOUNTERS:
        raise ValueError('Native encounter list missing/opaque or exceeds budget')
    if len({id(x) for x in entries}) != len(entries):
        raise ValueError('Aliased encounter entries are unsupported')
    rows = []
    for entry in entries:
        if not isinstance(entry, RubyObject) or entry.cls != ENCOUNTER_CLASS or set(entry.ivars) != {'@' + k for k in ENCOUNTER_FIELDS}:
            raise ValueError('Existing encounter entry has an unsupported schema; only exact troop_id/weight/region_set entries are admitted')
        rows.append((integer(entry.get('troop_id'), 'existing troop ID', 0, 2**31 - 1),
                     integer(entry.get('weight'), 'existing weight', 1, 100),
                     region_set(entry.get('region_set'), 'existing region set')))
    step = root.get('encounter_step')
    if type(step) is not int:
        raise ValueError('Native encounter_step integer required')
    return rows


def validate(root, mutation, troops):
    """Check every precondition; return (new_row, new_step_or_None)."""
    if not isinstance(mutation, dict) or set(mutation) != FIELDS or mutation.get('action') != ACTION:
        raise ValueError('Exact append_encounter schema required')
    rows = existing(root)
    if sha(mutation['expected_map_sha256'], 'expected_map_sha256') != fingerprint(root):
        raise ValueError('Stale native map fingerprint')
    if type(mutation['expected_encounter_count']) is not int or mutation['expected_encounter_count'] != len(rows):
        raise ValueError('Stale encounter count precondition')
    from vxace_database_append import database_array
    database_array(troops, 'troops')
    if sha(mutation['expected_troops_sha256'], 'expected_troops_sha256') != troops_digest(troops):
        raise ValueError('Stale native troops fingerprint')
    troop_id = integer(mutation['troop_id'], 'troop ID', 1, len(troops) - 1)
    weight = integer(mutation['weight'], 'encounter weight', 1, 100)
    regions = region_set(mutation['region_ids'], 'region_ids')
    step = mutation['encounter_step']
    if step is not None:
        integer(step, 'encounter step', 1, 999)
    if len(rows) >= MAX_ENCOUNTERS:
        raise ValueError('Encounter list budget exhausted')
    if any(row[0] == troop_id and row[2] == regions for row in rows):
        raise ValueError('Duplicate troop/region-set encounter refused')
    return (troop_id, weight, regions), step


def new_encounter(row):
    from vxace_python_mutator import RubyObject
    troop_id, weight, regions = row
    return RubyObject(ENCOUNTER_CLASS, {'@troop_id': troop_id, '@weight': weight, '@region_set': list(regions)})


def apply(root, mutation, troops):
    row, step = validate(root, mutation, troops)
    # Detach the list so unknown aliases keep the original container; old entries stay shared.
    root.set('encounter_list', list(root.get('encounter_list')) + [new_encounter(row)])
    if step is not None:
        root.set('encounter_step', step)


def verify_transition(before, after, mutation, troops):
    """Prove the candidate is the old map plus exactly the approved encounter (and optional step)."""
    from vxace_python_mutator import marshal_rb
    old = existing(before)
    new = existing(after)
    if len(new) != len(old) + 1 or new[:len(old)] != old:
        raise ValueError('Encounter candidate changed the existing encounter list prefix')
    row, step = validate(before, mutation, troops)
    if new[-1] != row:
        raise ValueError('Encounter candidate differs from the approved encounter')
    if marshal_rb.dump(after.get('encounter_list')[-1]) != marshal_rb.dump(new_encounter(row)):
        raise ValueError('Appended encounter object differs from the approved factory result')
    expected = marshal_rb.load(marshal_rb.dump(before))
    apply(expected, mutation, troops)
    if marshal_rb.dump(after) != marshal_rb.dump(expected):
        raise ValueError('Encounter candidate changed unapproved native map fields or aliases')


def name_of(value):
    return value.data.decode('utf-8', 'replace') if hasattr(value, 'data') else None


def indexed_snapshot(data, project, map_id):
    from vxace_python_mutator import load
    mid = integer(map_id, 'map ID', 1, 999)
    target = f'Data/Map{mid:03d}.rvdata2'
    root, raw = load(unlinked(Path(project) / target))
    rows = existing(root)
    if json.dumps(data.json(f'maps/map-{mid:03d}.json'), sort_keys=True) != json.dumps(plain(root), sort_keys=True):
        raise ValueError('Native/indexed map encounter context disagrees')
    troops = troops_for(unlinked(Path(project) / target))
    table = table_for(root)
    layer = table.xsize * table.ysize
    painted = Counter(x >> 8 for x in table.data[3 * layer:] if x >> 8)
    return {'version': VERSION, 'map_id': mid, 'target': target, 'map_sha256': fingerprint(root),
            'raw_file_sha256': hashlib.sha256(raw).hexdigest(), 'width': table.xsize, 'height': table.ysize,
            'encounter_count': len(rows),
            'encounters': [{'index': i, 'troop_id': t, 'weight': w, 'region_set': r} for i, (t, w, r) in enumerate(rows)],
            'encounter_step': root.get('encounter_step'),
            'troops_sha256': troops_digest(troops), 'troop_id_range': [1, len(troops) - 1],
            'troops': [{'id': i, 'name': name_of(t.get('name'))} for i, t in enumerate(troops) if i],
            'painted_region_counts': dict(sorted(painted.items())),
            'limits': ['Only this map\'s encounter_list (and optionally encounter_step); troops are read-only.',
                       'Snapshot is not mutation permission; use the Python guarded copy chain and native tests.',
                       'Random battles also need encounters not disabled by events/scripts and the player walking on the map.']}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--map', dest='map_id', type=int, required=True)
    args = ap.parse_args(argv)
    try:
        project = unlinked(args.project)
        if project.is_file() and project.suffix.lower() == '.rvproj2':
            project = project.parent
        result = execute(args.index, project, args.output,
                         lambda data: indexed_snapshot(data, project, args.map_id), 'map-encounter-snapshot')
    except Exception as exc:
        print('Encounter snapshot refused: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps({'status': 'ok', 'map_id': result['map_id'], 'encounter_count': result['encounter_count'],
                      'mutation_authorized': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
