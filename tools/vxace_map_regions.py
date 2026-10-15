#!/usr/bin/env python3
"""Native region snapshots and guarded existing-map region edits for copy staging."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from vxace_index_query import Index, execute, unlinked

VERSION = '0.19.0'
MAX_CELLS = 256


def integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(label + ' outside integer bounds')
    return value


def table_for(root):
    from vxace_python_mutator import RubyObject, Table
    if not isinstance(root, RubyObject) or root.cls != 'RPG::Map':
        raise ValueError('Expected native RPG::Map')
    width = integer(root.get('width'), 'map width', 1, 500)
    height = integer(root.get('height'), 'map height', 1, 500)
    table = root.get('data')
    if not isinstance(table, Table) or (table.dim, table.xsize, table.ysize, table.zsize) != (3, width, height, 4):
        raise ValueError('Expected exact native width × height × 4 map Table')
    if len(table.data) != width * height * 4:
        raise ValueError('Incomplete native map Table')
    return table


def fingerprint(table):
    return hashlib.sha256(table.to_payload()).hexdigest()


def coordinates(cells, table):
    if not isinstance(cells, list) or not 1 <= len(cells) <= MAX_CELLS:
        raise ValueError('Select 1..256 unique region cells')
    seen = set()
    for cell in cells:
        if not isinstance(cell, dict):
            raise ValueError('Region cell must be an object')
        x = integer(cell.get('x'), 'cell x', 0, table.xsize - 1)
        y = integer(cell.get('y'), 'cell y', 0, table.ysize - 1)
        if (x, y) in seen:
            raise ValueError('Duplicate region cell')
        seen.add((x, y))
        yield cell, x + y * table.xsize + 3 * table.xsize * table.ysize


def snapshot(root, cells):
    table = table_for(root)
    rows = []
    for cell, pos in coordinates(cells, table):
        if set(cell) != {'x', 'y'}:
            raise ValueError('Snapshot cells accept only x/y')
        packed = table.data[pos]
        rows.append({'x': cell['x'], 'y': cell['y'], 'region': packed >> 8,
                     'lower_metadata_byte': packed & 255})
    return {'width': table.xsize, 'height': table.ysize, 'layers': 4,
            'table_sha256': fingerprint(table), 'cells': rows,
            'region_counts': dict(sorted(Counter(x >> 8 for x in table.data[3*table.xsize*table.ysize:]).items()))}


def apply(root, mutation):
    from vxace_python_mutator import Table
    if not isinstance(mutation, dict) or set(mutation) != {'action', 'expected_table_sha256', 'cells'} or mutation.get('action') != 'set_regions':
        raise ValueError('Only the exact set_regions schema is supported')
    table = table_for(root)
    if mutation['expected_table_sha256'] != fingerprint(table):
        raise ValueError('Native map Table fingerprint is stale')
    changes = []
    for cell, pos in coordinates(mutation['cells'], table):
        if set(cell) != {'x', 'y', 'expected_region', 'value'}:
            raise ValueError('Region cells require exactly x/y/expected_region/value')
        expected = integer(cell['expected_region'], 'expected editor region', 0, 63)
        value = integer(cell['value'], 'new editor region', 0, 63)
        packed = table.data[pos]
        if packed >> 8 != expected:
            raise ValueError('Native region precondition is stale')
        if value == expected:
            raise ValueError('No-op region cell refused')
        changes.append((pos, (packed & 255) | value << 8))
    # Detach the map's Table so aliases in unknown fields retain original data.
    updated = Table.from_payload(table.to_payload())
    for pos, value in changes:
        updated.data[pos] = value
    root.set('data', updated)


def indexed_snapshot(data, project, map_id, cells):
    from vxace_python_mutator import load
    integer(map_id, 'map ID', 1, 999999)
    relative = f'maps/map-{map_id:03d}.json'
    indexed = data.json(relative)
    target = f'Data/Map{map_id:03d}.rvdata2'
    root, _ = load(unlinked(Path(project) / target))
    table = table_for(root)
    native = {'__class__': 'Table', 'dimensions': table.dim, 'xsize': table.xsize,
              'ysize': table.ysize, 'zsize': table.zsize, 'data': list(table.data)}
    if not isinstance(indexed, dict) or indexed.get('width') != table.xsize or indexed.get('height') != table.ysize or indexed.get('data') != native:
        raise ValueError('Indexed/native map Table disagree')
    return {'version': VERSION, 'map_id': map_id, 'target': target, **snapshot(root, cells),
            'limits': ['Only editor map region metadata; custom/runtime maps and region consumers may differ.',
                       'Snapshot is not mutation permission; use the Python guarded copy chain and native save tests.']}


def verify_transition(before, after, mutation):
    """Prove the candidate differs only at approved region bytes, conservatively."""
    from vxace_python_mutator import RubyObject, marshal_rb
    previous=table_for(before); current=table_for(after)
    if (previous.dim,previous.xsize,previous.ysize,previous.zsize)!=(current.dim,current.xsize,current.ysize,current.zsize):
        raise ValueError('Region candidate changed map Table shape')
    expected=bytearray(previous.to_payload())
    for cell,pos in coordinates(mutation['cells'],previous):
        expected[20+pos*2+1]=cell['value']
    if bytes(expected)!=current.to_payload():
        raise ValueError('Region candidate changed unapproved Table bytes')
    def unrelated(root):
        return marshal_rb.dump(RubyObject(root.cls,{key:value for key,value in root.ivars.items() if key!='@data'}))
    if unrelated(before)!=unrelated(after):
        raise ValueError('Region candidate changed other native map fields or unknown aliases')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--map', dest='map_id', type=int, required=True)
    ap.add_argument('--cell', type=int, nargs=2, action='append', required=True)
    args = ap.parse_args(argv)
    try:
        cells = [{'x': x, 'y': y} for x, y in args.cell]
        project = unlinked(args.project)
        if project.is_file() and project.suffix.lower() == '.rvproj2': project = project.parent
        result = execute(args.index, project, args.output,
                         lambda data: indexed_snapshot(data, project, args.map_id, cells), 'region-snapshot')
        lines = ['# VX Ace native region snapshot', '', 'Read-only preconditions; no mutation authorized.', '',
                 'Map: ' + str(result['map_id']), 'Table SHA-256: `' + result['table_sha256'] + '`', '',
                 '```json', json.dumps(result['cells'], indent=2), '```', '']
        (Path(args.output) / 'region-snapshot.md').write_text('\n'.join(lines), encoding='utf-8')
        print(json.dumps({'status': 'ok', 'map_id': args.map_id, 'cells': len(cells)}))
        return 0
    except Exception as exc:
        print('Region snapshot refused: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
