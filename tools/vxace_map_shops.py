#!/usr/bin/env python3
"""Read-only shop evidence and one guarded Shop Processing append on an existing map event (copy staging only)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys
from vxace_index_query import execute, unlinked
from vxace_map_regions import integer
from vxace_map_events import events_for, template, text, exact, digest
from vxace_maps import plain

VERSION = '1.15.0'
ACTION = 'add_shop'
FIELDS = {'action', 'expected_map_sha256', 'expected_event_sha256', 'expected_list_sha256',
          'expected_items_sha256', 'expected_weapons_sha256', 'expected_armors_sha256', 'goods', 'purchase_only'}
GOODS = {'item': (0, 'items', 'RPG::Item', 'Items.rvdata2'),
         'weapon': (1, 'weapons', 'RPG::Weapon', 'Weapons.rvdata2'),
         'armor': (2, 'armors', 'RPG::Armor', 'Armors.rvdata2')}
HASH_FIELD = {'item': 'expected_items_sha256', 'weapon': 'expected_weapons_sha256', 'armor': 'expected_armors_sha256'}
MAX_GOODS = 32
MAX_PRICE = 9999999
LIMITS = ['One Shop Processing block (302 plus 605 rows) inserted before the terminator of an existing exact blank or single-literal-dialogue, '
          'one-page, stationary, unconditional action-button map event with a blank graphic.',
          'Goods come from the static Items/Weapons/Armors arrays, which are read-only; no price/stock/shop-sprite editing, no variable shops.',
          'Prices are the native database price (price_type 0) or a constant 0..9999999; custom shop scenes/scripts can change what is shown.',
          'System/version advances so default older saves reload the edited map; custom loaders need separate review.']


def sha(value, label):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError(label + ' must be a lowercase SHA-256')
    return value


def schema(mutation, native=False):
    """Exact public (or native: plus event_id) add_shop schema; returns nothing, raises ValueError."""
    expected = FIELDS | ({'event_id'} if native else set())
    if not isinstance(mutation, dict) or set(mutation) != expected or mutation.get('action') != ACTION:
        raise ValueError('Exact add_shop schema required')
    for field in FIELDS:
        if field.endswith('_sha256'):
            sha(mutation[field], field)
    if native:
        integer(mutation['event_id'], 'shop event ID', 1, 999)
    if type(mutation['purchase_only']) is not bool:
        raise ValueError('purchase_only must be a boolean')
    goods = mutation['goods']
    if not isinstance(goods, list) or not 1 <= len(goods) <= MAX_GOODS:
        raise ValueError('One to 32 goods required')
    seen = set()
    for good in goods:
        if not isinstance(good, dict) or set(good) != {'type', 'id', 'price'} or good['type'] not in GOODS:
            raise ValueError('Each good needs exactly type (item/weapon/armor), id and price')
        integer(good['id'], 'goods ID', 1, 999)
        if good['price'] is not None:
            integer(good['price'], 'specified price', 0, MAX_PRICE)
        key = (good['type'], good['id'])
        if key in seen:
            raise ValueError('Duplicate goods entry refused')
        seen.add(key)


def goods_rows(goods, purchase_only):
    """Native command rows: 302 [type,id,price_type,price,purchase_only] then 605 [type,id,price_type,price]."""
    rows = []
    for number, good in enumerate(goods):
        price_type = 0 if good['price'] is None else 1
        params = [GOODS[good['type']][0], good['id'], price_type, 0 if good['price'] is None else good['price']]
        rows.append((302, params + [purchase_only]) if number == 0 else (605, params))
    return rows


def shop_commands(rows):
    from vxace_python_mutator import RubyObject
    return [RubyObject('RPG::EventCommand', {'@code': code, '@indent': 0, '@parameters': list(params)}) for code, params in rows]


def goods_array(root, kind):
    from vxace_python_mutator import RubyObject, RubyString
    _, label, cls, _ = GOODS[kind]
    if not isinstance(root, list) or not 2 <= len(root) <= 1000 or root[0] is not None:
        raise ValueError('Expected native ' + label + ' array with nil slot zero (at most 999 entries)')
    for number, entry in enumerate(root[1:], 1):
        if not isinstance(entry, RubyObject) or entry.cls != cls or type(entry.get('id')) is not int or entry.get('id') != number \
                or not isinstance(entry.get('name'), RubyString):
            raise ValueError('Every ' + label + ' entry must be a static non-nil ' + cls + ' with its exact slot ID and a name')
        entry.get('name').data.decode('utf-8', 'strict')
    if len({id(entry) for entry in root[1:]}) != len(root) - 1:
        raise ValueError('Aliased ' + label + ' entries are unsupported')
    return root


def goods_arrays(path):
    """Read-only load of Items/Weapons/Armors beside a native Data file (same snapshot/copy)."""
    return arrays_in(unlinked(path).parent)


def arrays_in(data_dir):
    from vxace_python_mutator import load
    if Path(data_dir).name != 'Data':
        raise ValueError('Shop append requires a native project Data path to read Items/Weapons/Armors')
    return {kind: goods_array(load(unlinked(Path(data_dir) / GOODS[kind][3]))[0], kind) for kind in GOODS}


def locate(root, event_id):
    events = events_for(root)
    integer(event_id, 'shop event ID', 1, 999)
    matches = [event for key, event in events.pairs if key == event_id]
    if len(matches) != 1:
        raise ValueError('Shop event is absent from the native map')
    return matches[0]


def event_shape(root, event_id):
    """Validate the source event; return (event, 'blank'|'dialogue', literal lines)."""
    from vxace_python_mutator import RubyString
    event = locate(root, event_id)
    pages = event.get('pages')
    if not isinstance(pages, list) or len(pages) != 1:
        raise ValueError('Shop event must have exactly one page')
    commands = pages[0].get('list')
    if not isinstance(commands, list) or not 1 <= len(commands) <= 6:
        raise ValueError('Shop event list must be blank or exactly one literal Show Text block')
    terminator = exact(commands[-1], 'RPG::EventCommand', {'code', 'indent', 'parameters'})
    if (terminator.get('code'), terminator.get('indent'), terminator.get('parameters')) != (0, 0, []) \
            or type(terminator.get('code')) is not int or type(terminator.get('indent')) is not int:
        raise ValueError('Native root terminator required')
    if len(commands) == 1:
        template(root, event_id)
        return event, 'blank', []
    template(root, event_id, blank_list=False)
    head = exact(commands[0], 'RPG::EventCommand', {'code', 'indent', 'parameters'})
    header = head.get('parameters')
    if type(head.get('code')) is not int or head.get('code') != 101 or type(head.get('indent')) is not int or head.get('indent') != 0 \
            or not isinstance(header, list) or len(header) != 4 or not isinstance(header[0], RubyString) or header[0].data or header[0].ivars != {'E': True} \
            or any(type(value) is not int for value in header[1:]) or header[1:] != [0, 0, 2]:
        raise ValueError('Dialogue shape needs the fixed asset-free Show Text header')
    lines = []
    for command in commands[1:-1]:
        exact(command, 'RPG::EventCommand', {'code', 'indent', 'parameters'})
        params = command.get('parameters')
        if type(command.get('code')) is not int or command.get('code') != 401 or type(command.get('indent')) is not int or command.get('indent') != 0 \
                or not isinstance(params, list) or len(params) != 1 or not isinstance(params[0], RubyString) or params[0].ivars != {'E': True}:
            raise ValueError('Dialogue shape allows only literal 401 text lines after the header')
        lines.append(text(params[0].data.decode('utf-8', 'strict'), 'dialogue line', 500, True))
    if not 1 <= len(lines) <= 4 or not any(lines):
        raise ValueError('Dialogue shape needs one to four lines with text')
    return event, 'dialogue', lines


def validate(root, mutation, arrays):
    """Check every precondition; return (new command rows, evidence)."""
    schema(mutation, native=True)
    event, shape, lines = event_shape(root, mutation['event_id'])
    if mutation['expected_map_sha256'] != digest(root) or mutation['expected_event_sha256'] != digest(event) \
            or mutation['expected_list_sha256'] != digest(event.get('pages')[0].get('list')):
        raise ValueError('Stale native map/event/list guard')
    if not isinstance(arrays, dict) or set(arrays) != set(GOODS):
        raise ValueError('Items, Weapons and Armors arrays are required')
    for kind in GOODS:
        goods_array(arrays[kind], kind)
        if mutation[HASH_FIELD[kind]] != digest(arrays[kind]):
            raise ValueError('Stale native ' + GOODS[kind][1] + ' array guard')
    evidence = []
    for good in mutation['goods']:
        array = arrays[good['type']]
        if good['id'] >= len(array):
            raise ValueError('Goods ID ' + str(good['id']) + ' is absent from native ' + GOODS[good['type']][1])
        evidence.append({'type': good['type'], 'id': good['id'], 'name': array[good['id']].get('name').data.decode('utf-8', 'strict'),
                         'price': good['price']})
    return goods_rows(mutation['goods'], mutation['purchase_only']), {'event_shape': shape, 'dialogue_lines': lines, 'goods': evidence,
                                                                       'purchase_only': mutation['purchase_only']}


def apply(root, mutation, arrays):
    rows, _ = validate(root, mutation, arrays)
    page = locate(root, mutation['event_id']).get('pages')[0]
    old = page.get('list')
    new = list(old[:-1]) + shop_commands(rows) + [old[-1]]
    from vxace_event_structure import validate_list
    validate_list(new)
    page.set('list', new)  # detached list: aliases keep the original container


def verify_transition(before, after, mutation, arrays):
    """Prove the candidate is the old map plus exactly the approved shop rows in that one list."""
    from vxace_python_mutator import marshal_rb
    rows, _ = validate(before, mutation, arrays)
    old = locate(before, mutation['event_id']).get('pages')[0].get('list')
    new = locate(after, mutation['event_id']).get('pages')[0].get('list')
    if len(new) != len(old) + len(rows) or marshal_rb.dump(new[:len(old) - 1]) != marshal_rb.dump(old[:-1]) \
            or marshal_rb.dump(new[-1]) != marshal_rb.dump(old[-1]):
        raise ValueError('Shop candidate changed the existing command prefix or terminator')
    inserted = new[len(old) - 1:-1]
    if marshal_rb.dump(inserted) != marshal_rb.dump(shop_commands(rows)):
        raise ValueError('Inserted commands differ from the approved factory result')
    def masked(root):
        copy = marshal_rb.load(marshal_rb.dump(root))
        locate(copy, mutation['event_id']).get('pages')[0].set('list', [])
        return marshal_rb.dump(copy)
    if masked(before) != masked(after):
        raise ValueError('Shop candidate changed something other than the one event page list')
    expected = marshal_rb.load(marshal_rb.dump(before))
    apply(expected, mutation, arrays)
    if marshal_rb.dump(expected) != marshal_rb.dump(after):
        raise ValueError('Shop candidate differs from the independently rebuilt result')


def final_context(mutation, project):
    """Items/Weapons/Armors bytes must remain exactly the approved ones in the final copy."""
    arrays = arrays_in(Path(project) / 'Data')
    for kind in GOODS:
        if digest(arrays[kind]) != mutation[HASH_FIELD[kind]]:
            raise ValueError('Goods arrays changed during final verification')


def indexed_snapshot(data, project, map_id, event_id):
    from vxace_python_mutator import load
    mid = integer(map_id, 'map ID', 1, 999)
    eid = integer(event_id, 'event ID', 1, 999)
    target = f'Data/Map{mid:03d}.rvdata2'
    source = unlinked(Path(project) / target)
    root, raw = load(source)
    events_for(root)
    if json.dumps(data.json(f'maps/map-{mid:03d}.json'), sort_keys=True) != json.dumps(plain(root), sort_keys=True):
        raise ValueError('Native/indexed map shop context disagrees')
    arrays = goods_arrays(source)
    ranges = {}
    for kind, (_, label, cls, _) in GOODS.items():
        indexed = data.json(f'database/{label}.json')
        array = arrays[kind]
        if not isinstance(indexed, list) or len(indexed) != len(array) or indexed[0] is not None or any(
                not isinstance(row, dict) or row.get('__class__') != cls or row.get('id') != number
                or row.get('name') != array[number].get('name').data.decode('utf-8', 'strict') for number, row in enumerate(indexed) if number):
            raise ValueError('Indexed/native ' + label + ' disagree')
        ranges[kind] = {'min_id': 1, 'max_id': len(array) - 1, 'count': len(array) - 1}
    event = locate(root, eid)
    shape, lines, reason = None, [], None
    try:
        _, shape, lines = event_shape(root, eid)
    except ValueError as error:
        reason = str(error)
    page = event.get('pages')[0] if isinstance(event.get('pages'), list) and len(event.get('pages')) == 1 else None
    return {'version': VERSION, 'map_id': mid, 'event_id': eid, 'target': target,
            'event_name': event.get('name').data.decode('utf-8', 'replace'),
            'map_sha256': digest(root), 'event_sha256': digest(event),
            'list_sha256': digest(page.get('list')) if page is not None and isinstance(page.get('list'), list) else None,
            'items_sha256': digest(arrays['item']), 'weapons_sha256': digest(arrays['weapon']), 'armors_sha256': digest(arrays['armor']),
            'event_shape': shape, 'dialogue_lines': lines, 'id_ranges': ranges,
            'max_goods': MAX_GOODS, 'append_supported': shape is not None, 'unsupported_reason': reason, 'limits': LIMITS}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--map', dest='map_id', type=int, required=True); ap.add_argument('--event', dest='event_id', type=int, required=True)
    args = ap.parse_args(argv)
    try:
        project = unlinked(args.project)
        if project.is_file() and project.suffix.lower() == '.rvproj2':
            project = project.parent
        result = execute(args.index, project, args.output,
                         lambda data: indexed_snapshot(data, project, args.map_id, args.event_id), 'map-shop-snapshot')
    except Exception as error:
        print('Shop snapshot refused: ' + str(error), file=sys.stderr)
        return 2
    print(json.dumps({'status': 'ok', 'map_id': result['map_id'], 'event_id': result['event_id'], 'event_shape': result['event_shape'],
                      'append_supported': result['append_supported'], 'mutation_authorized': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
