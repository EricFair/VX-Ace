#!/usr/bin/env python3
"""Bounded read-only map tile/tileset diagnostics; never a movement or asset proof."""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from vxace_index_query import Index, execute

VERSION = '0.14.0'
DIRECTIONS = {'down': 1, 'left': 2, 'right': 4, 'up': 8}
LIMITS = [
    'Editor map data only; runtime map/tileset changes and save contents are not evaluated.',
    'Cell passage uses only the three static tile layers and default VX Ace flag ordering.',
    'Tile events, event page selection, characters, vehicles, through/debug-through and custom movement hooks are excluded.',
    'This is not a pathfinding/reachability proof or a validation of RTP/image existence or dimensions.',
    'Autotile sheet/kind/shape are reported, not rendered; unusual data is diagnostic and never authorizes mutation.',
]


def integer(value, lower, upper, label):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError('Invalid ' + label)
    return value


def table(value, dimensions, sizes, data):
    if not isinstance(value, dict) or value.get('__class__') != 'Table':
        raise ValueError('Expected fully decoded native Table')
    if type(value.get('dimensions')) is not int or value['dimensions'] != dimensions:
        raise ValueError('Unexpected Table dimensions')
    if any(type(value.get(k)) is not int or value[k] != n for k, n in zip(('xsize', 'ysize', 'zsize'), sizes)):
        raise ValueError('Table shape differs from its owner')
    cells = value.get('data')
    count = sizes[0] * sizes[1] * sizes[2]
    if not isinstance(cells, list) or len(cells) != count:
        raise ValueError('Incomplete Table cells')
    data.spend(count)
    if any(type(x) is not int or not 0 <= x <= 65535 for x in cells):
        raise ValueError('Invalid unsigned Table cell')
    return cells


def tile_info(tile_id):
    """Default native slots. Coordinates are 32px cells only for B–E/A5."""
    integer(tile_id, 0, 8191, 'tile ID')
    if tile_id < 1024:
        slot, local = divmod(tile_id, 256)
        return {'sheet': 'BCDE'[slot], 'sheet_slot': slot + 5,
                'column': local % 8 + (local // 128) * 8,
                'row': (local % 128) // 8, 'autotile': False}
    if tile_id < 1536:
        return {'sheet': None, 'sheet_slot': None, 'unsupported_gap': True}
    if tile_id < 2048:
        local = tile_id - 1536
        return {'sheet': 'A5', 'sheet_slot': 4, 'column': local % 8,
                'row': local // 8, 'autotile': False}
    for end, name, slot, start in ((2816, 'A1', 0, 2048), (4352, 'A2', 1, 2816),
                                   (5888, 'A3', 2, 4352), (8192, 'A4', 3, 5888)):
        if tile_id < end:
            return {'sheet': name, 'sheet_slot': slot, 'autotile': True,
                    'kind_on_sheet': (tile_id - start) // 48, 'shape': (tile_id - start) % 48}
    raise ValueError('Unclassified tile')


def tile_passage(layers, flags):
    """Static-layer estimate only; the real engine also prepends tile events."""
    if any(tile_info(t).get('unsupported_gap') for t in layers):
        return {name: None for name in DIRECTIONS}
    answer = {}
    for name, bit in DIRECTIONS.items():
        answer[name] = False
        for tile_id in reversed(layers):
            flag = flags[tile_id]
            if flag & 16:
                continue
            answer[name] = not bool(flag & bit)
            break
    return answer


def audit(index, map_id=None, cell=None):
    data = index if isinstance(index, Index) else Index(index)
    if map_id is not None:
        integer(map_id, 1, 999999, 'map selection')
    if cell is not None and (map_id is None or not isinstance(cell, (list, tuple)) or len(cell) != 2):
        raise ValueError('Cell selection requires a map ID and two coordinates')
    raw = data.json('database/tilesets.json')
    if not isinstance(raw, list):
        raise ValueError('Expected native tileset array')
    tilesets = {}
    for slot, ts in enumerate(raw):
        data.spend()
        if ts is None:
            continue
        if not isinstance(ts, dict) or ts.get('__class__') != 'RPG::Tileset' or type(ts.get('id')) is not int or ts['id'] != slot or slot == 0:
            raise ValueError('Ambiguous tileset identity')
        names = ts.get('tileset_names')
        if not isinstance(names, list) or len(names) != 9 or any(not isinstance(x, str) for x in names):
            raise ValueError('Incomplete tileset sheet names')
        tilesets[slot] = (ts, table(ts.get('flags'), 1, (8192, 1, 1), data))
    reports, findings = [], []
    tile_rows = 0
    for file in data.paths('maps', 'map-*.json'):
        match = re.fullmatch(r'maps/map-(\d+)\.json', file)
        if not match:
            raise ValueError('Unexpected map filename')
        mid = int(match[1])
        integer(mid, 1, 999999, 'map filename ID')
        if map_id is not None and mid != map_id:
            continue
        m = data.json(file)
        if not isinstance(m, dict) or m.get('__class__') != 'RPG::Map':
            raise ValueError('Opaque map')
        w = integer(m.get('width'), 1, 4096, 'map width')
        h = integer(m.get('height'), 1, 4096, 'map height')
        tsid = integer(m.get('tileset_id'), 1, 999999, 'map tileset ID')
        if tsid not in tilesets:
            raise ValueError('Map references an absent tileset')
        ts, flags = tilesets[tsid]
        values = table(m.get('data'), 3, (w, h, 4), data)
        plane = w * h
        usage = Counter(values[:3 * plane])
        tile_rows += len(usage)
        if tile_rows > 10000:
            raise ValueError('Tile report budget exceeded; no complete result produced')
        rows = []
        for tile_id, count in sorted(usage.items()):
            if tile_id >= 8192:
                raise ValueError('Map tile ID exceeds native flag array')
            info = tile_info(tile_id)
            info.update(tile_id=tile_id, count=count, flag=flags[tile_id], star=bool(flags[tile_id] & 16))
            sheet = info['sheet_slot']
            info['sheet_name'] = ts['tileset_names'][sheet] if sheet is not None else None
            if info.get('unsupported_gap'):
                findings.append({'code': 'unsupported_tile_id', 'map_id': mid, 'tile_id': tile_id, 'evidence_file': file})
            elif not info['sheet_name'] and tile_id != 0:
                findings.append({'code': 'empty_tileset_sheet', 'map_id': mid, 'tile_id': tile_id, 'evidence_file': file})
            rows.append(info)
            if len(findings) > 5000:
                raise ValueError('Finding budget exceeded; no complete result produced')
        packed = values[3 * plane:]
        report = {'map_id': mid, 'evidence_file': file, 'width': w, 'height': h, 'tileset_id': tsid,
                  'tileset_name': ts.get('name'), 'tiles': rows,
                  'regions': {str(k): v for k, v in sorted(Counter(x >> 8 for x in packed).items())},
                  'shadow_cells': sum(bool(x & 15) for x in packed),
                  'reserved_metadata_cells': sum(bool(x & 240) for x in packed)}
        if cell is not None:
            x = integer(cell[0], 0, w - 1, 'cell x')
            y = integer(cell[1], 0, h - 1, 'cell y')
            pos = x + y * w
            layers = [values[pos + z * plane] for z in range(3)]
            report['cell'] = {'x': x, 'y': y, 'layers_bottom_to_top': layers,
                              'region': packed[pos] >> 8, 'shadow_bits': packed[pos] & 15,
                              'static_tile_passage_only': tile_passage(layers, flags)}
        reports.append(report)
    if map_id is not None and not reports:
        raise ValueError('Selected map is absent')
    data.unchanged()
    return {'version': VERSION, 'read_only': True, 'mutation_authorized': False,
            'maps': reports, 'findings': findings, 'limits': LIMITS}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--map', type=int, dest='map_id'); ap.add_argument('--cell', type=int, nargs=2)
    a = ap.parse_args(argv)
    try:
        result = execute(a.index, a.project, a.output, lambda data: audit(data, a.map_id, a.cell), 'map-audit')
        lines = ['# VX Ace map audit', '', 'Static editor data only; this is not a movement or asset proof.', '']
        for m in result['maps']:
            lines.append(f"- Map {m['map_id']}: {m['width']}×{m['height']}; tileset {m['tileset_id']}; {len(m['tiles'])} distinct tile IDs")
            if 'cell' in m:
                lines.append('  Cell: ' + json.dumps(m['cell'], ensure_ascii=False))
        lines += ['', f"Findings: {len(result['findings'])}", '', '## Limits', ''] + ['- ' + x for x in LIMITS]
        (Path(a.output) / 'map-audit.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(json.dumps({'status': 'review_required' if result['findings'] else 'ok',
                          'maps': len(result['maps']), 'findings': len(result['findings'])}))
        return 3 if result['findings'] else 0
    except Exception as exc:
        print('Map audit refused: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
