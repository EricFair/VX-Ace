#!/usr/bin/env python3
"""Bounded map layouts for fresh blank maps (v1.31) and a tile-passage reachability check. Not level design.

A layout paints a bordered rectangle with plain A5 tiles on layer 0 (floor, wall border, L-shaped paths) and optional ordinary B-E landmark tiles on
upper layer 1 or 2. Every tile kind is one the map tile audit and the upper-tile code already verify: no autotile shape is ever computed."""
from __future__ import annotations
from collections import deque
from vxace_map_audit import tile_info, tile_passage, DIRECTIONS

A5_BASE, A5_COUNT = 1536, 128
MAX_SIZE = 500
MAX_PATHS, MAX_LANDMARKS = 64, 256
LAYOUT_KEYS = {'style', 'floor', 'wall', 'path', 'border', 'paths', 'anchor', 'landmarks', 'preset'}
LANDMARK_KEYS = {'x', 'y', 'tile', 'layer'}
STYLES = ('room',)

# Stock RTP tilesets, chosen from their A5 / B sheet images, the tile name lists shipped beside them (Graphics/Tilesets/*.txt) and the
# stock passage flags. A preset only applies when the tileset name and its A5 and B sheet names match; otherwise explicit indexes are required.
PRESETS = {
    'exterior': {'tileset': 'Exterior', 'a5': 'Outside_A5', 'b': 'Outside_B', 'floor': 16, 'wall': 112, 'path': 17,
                 'look': {'floor': 'green meadow grass', 'wall': 'brown rocky cliff face', 'path': 'tan dirt'},
                 'landmarks': {'tree': 94, 'bush': 102, 'boulder': 95, 'stump': 92, 'barrel': 77, 'sign': 73, 'well': 75, 'log': 100, 'flowers': 96, 'rocks': 107},
                 'landmark_look': {'tree': 'round leafy tree', 'bush': 'green bush', 'boulder': 'grey boulder', 'stump': 'tree stump', 'barrel': 'wooden barrel',
                                   'sign': 'wooden signpost', 'well': 'stone well', 'log': 'fallen log', 'flowers': 'yellow flowers (passable)', 'rocks': 'small rocks (passable)'}},
    'interior': {'tileset': 'Interior', 'a5': 'Inside_A5', 'b': 'Inside_B', 'floor': 16, 'wall': 24, 'path': 81,
                 'look': {'floor': 'light wood plank floor', 'wall': 'dark wood panel wall', 'path': 'red carpet runner'},
                 'landmarks': {'table': 96, 'white_table': 98, 'stool': 104, 'cushion': 105, 'chair': 176, 'barrel': 209, 'crate': 224, 'vase': 200, 'counter': 114},
                 'landmark_look': {'table': 'round wooden table', 'white_table': 'round table with a white cloth', 'stool': 'wooden stool (passable)',
                                   'cushion': 'red cushioned stool (passable)', 'chair': 'wooden chair', 'barrel': 'wooden barrel', 'crate': 'wooden crate',
                                   'vase': 'clay vase', 'counter': 'kitchen counter with a marble top'}},
    'dungeon': {'tileset': 'Dungeon', 'a5': 'Dungeon_A5', 'b': 'Dungeon_B', 'floor': 16, 'wall': 0, 'path': 32,
                'look': {'floor': 'tan dirt-cave ground', 'wall': 'black "Darkness" void', 'path': 'grey cobblestones'},
                'landmarks': {'boulder': 56, 'rock': 57, 'crystal': 61, 'rubble': 104, 'bones': 240, 'barrel': 238, 'crate': 220},
                'landmark_look': {'boulder': 'brown rocky boulder', 'rock': 'grey rocky boulder', 'crystal': 'pale blue crystal', 'rubble': 'pile of grey rubble',
                                  'bones': 'scattered bones', 'barrel': 'wooden barrel', 'crate': 'wooden crate of ore'}},
}


def is_int(value):
    return type(value) is int


def int_pair(value, label, limit=MAX_SIZE):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(is_int(item) and 0 <= item < limit for item in value):
        raise ValueError(f'layout {label} must be [x, y] with integers 0..{limit - 1}')
    return (value[0], value[1])


def shape(layout):
    """Structural rules (no project needed). Raises ValueError."""
    if not isinstance(layout, dict) or not layout:
        raise ValueError('layout must be a non-empty object')
    unknown = set(layout) - LAYOUT_KEYS
    if unknown:
        raise ValueError(f'layout has unknown keys {sorted(unknown)}')
    if 'style' in layout and layout['style'] not in STYLES:
        raise ValueError('layout style must be "room" (the only style)')
    if 'preset' in layout and (not isinstance(layout['preset'], str) or layout['preset'] not in PRESETS):
        raise ValueError(f'layout preset must be one of {sorted(PRESETS)}')
    for key in ('floor', 'wall', 'path'):
        if key in layout and (not is_int(layout[key]) or not 0 <= layout[key] < A5_COUNT):
            raise ValueError(f'layout {key} must be an A5 tile index 0..{A5_COUNT - 1}')
    if 'border' in layout and (not is_int(layout['border']) or layout['border'] not in (0, 1)):
        raise ValueError('layout border must be 1 (default) or 0 (no border)')
    if 'anchor' in layout:
        int_pair(layout['anchor'], 'anchor')
    if 'paths' in layout:
        if not isinstance(layout['paths'], list) or len(layout['paths']) > MAX_PATHS:
            raise ValueError(f'layout paths must be a list of at most {MAX_PATHS} [x, y] points')
        for point in layout['paths']:
            int_pair(point, 'path point')
    if 'landmarks' in layout:
        landmarks = layout['landmarks']
        if not isinstance(landmarks, list) or len(landmarks) > MAX_LANDMARKS:
            raise ValueError(f'layout landmarks must be a list of at most {MAX_LANDMARKS} objects')
        seen = set()
        for item in landmarks:
            if not isinstance(item, dict) or not {'x', 'y', 'tile'} <= set(item) or set(item) - LANDMARK_KEYS:
                raise ValueError('a landmark needs x, y and tile (optional layer 1 or 2)')
            cell = int_pair([item['x'], item['y']], 'landmark cell')
            if cell in seen:
                raise ValueError(f'two landmarks share the cell {list(cell)}')
            seen.add(cell)
            tile = item['tile']
            if is_int(tile):
                if not 1 <= tile <= 1023:
                    raise ValueError('a landmark tile id must be an ordinary B-E tile 1..1023 (0 is the empty tile)')
            elif not isinstance(tile, str) or not tile:
                raise ValueError('a landmark tile must be a B-E tile id 1..1023 or a preset landmark name')
            if 'layer' in item and (not is_int(item['layer']) or item['layer'] not in (1, 2)):
                raise ValueError('a landmark layer must be 1 (default) or 2')


def sheet_names_ok(preset, tileset_name, names):
    spec = PRESETS[preset]
    return tileset_name == spec['tileset'] and names[4] == spec['a5'] and names[5] == spec['b']


def a5_tile(names, flags, index, label, want):
    """Tile id of an A5 index after the passage checks; `want` is 'passable' (floor, path) or 'wall' (impassable in all four directions)."""
    if not names[4]:
        raise ValueError(f'layout {label} needs a tileset whose A5 sheet (tileset_names[4]) is set')
    tile_id = A5_BASE + index
    star = bool(flags[tile_id] & 16)
    passage = tile_passage([tile_id], flags)
    if want == 'passable':
        if star or not all(passage.values()):
            raise ValueError(f'layout {label} tile (A5 index {index}) is not passable in every direction (or carries the star flag) in this tileset')
    elif star or any(passage.values()) or flags[tile_id] & 15 != 15:
        raise ValueError(f'layout {label} tile (A5 index {index}) must be impassable in all four directions (and not a star tile) in this tileset')
    return tile_id


def route(anchor, point, width, height, border):
    """L-shaped path cells from the anchor to a point. A point on a vertical border goes vertical first, anything else horizontal first, so a
    route never runs along the border and only its end may be a border cell."""
    (ax, ay), (px, py) = anchor, point
    cells = []
    step = lambda a, b: range(a, b + 1) if b >= a else range(a, b - 1, -1)
    if border and px in (0, width - 1) and py not in (0, height - 1):
        cells += [(ax, y) for y in step(ay, py)] + [(x, py) for x in step(ax, px)]
    else:
        cells += [(x, ay) for x in step(ax, px)] + [(px, y) for y in step(ay, py)]
    return list(dict.fromkeys(cells))


def resolve(layout, tileset_name, names, flags, width, height):
    """Validate a layout against a tileset and return the resolved plan (tile ids, path cells, landmark cells). Raises ValueError."""
    shape(layout)
    layout = dict(layout)
    border = layout.get('border', 1)
    preset = layout.get('preset')
    landmark_names = {}
    if preset:
        if not sheet_names_ok(preset, tileset_name, names):
            spec = PRESETS[preset]
            raise ValueError(f'layout preset "{preset}" only applies to the stock {spec["tileset"]} tileset (sheets {spec["a5"]}, {spec["b"]}); this tileset is '
                             f'"{tileset_name}" with sheets "{names[4]}", "{names[5]}": give floor, wall and path A5 indexes explicitly')
        spec = PRESETS[preset]
        for key in ('floor', 'wall', 'path'):
            layout.setdefault(key, spec[key])
        landmark_names = spec['landmarks']
    if 'floor' not in layout:
        raise ValueError('layout needs a floor A5 index (or a preset)')
    if border and 'wall' not in layout:
        raise ValueError('layout needs a wall A5 index (or a preset), or "border": 0')
    floor_tile = a5_tile(names, flags, layout['floor'], 'floor', 'passable')
    wall_tile = a5_tile(names, flags, layout['wall'], 'wall', 'wall') if border else None
    anchor = tuple(layout['anchor']) if 'anchor' in layout else None
    points = [tuple(point) for point in layout.get('paths', [])]
    if points and anchor is None:
        raise ValueError('layout paths need an anchor (add_area uses the arrival cell)')
    path_tile = None
    if points:
        if 'path' not in layout:
            raise ValueError('layout paths need a path A5 index (or a preset)')
        path_tile = a5_tile(names, flags, layout['path'], 'path', 'passable')
        if layout['path'] == layout['floor']:
            raise ValueError('layout path must differ from the floor so the path is visible')
        if border and layout['path'] == layout['wall']:
            raise ValueError('layout path must differ from the wall')
    if border and layout['wall'] == layout['floor']:
        raise ValueError('layout wall must differ from the floor')

    def on_border(cell):
        return cell[0] in (0, width - 1) or cell[1] in (0, height - 1)

    def inside(cell, label):
        if not (0 <= cell[0] < width and 0 <= cell[1] < height):
            raise ValueError(f'layout {label} {list(cell)} lies outside the {width}x{height} map')
    if anchor is not None:
        inside(anchor, 'anchor')
        if border and on_border(anchor):
            raise ValueError(f'layout anchor {list(anchor)} lies on the border wall; the arrival/start cell must be inside the room')
    path_cells = set()
    for point in points:
        inside(point, 'path point')
        if border and point[0] in (0, width - 1) and point[1] in (0, height - 1):
            raise ValueError(f'layout path point {list(point)} is a corner of the border')
        path_cells.update(route(anchor, point, width, height, border))
    if points:
        path_cells.add(anchor)
    placed = []
    for item in layout.get('landmarks', []):
        cell = (item['x'], item['y'])
        inside(cell, 'landmark')
        tile = item['tile']
        if isinstance(tile, str):
            if tile not in landmark_names:
                raise ValueError(f'landmark tile name "{tile}" is not defined' + (f' by the {preset} preset (names: {sorted(landmark_names)})' if preset else ' (names need a preset; give a B-E tile id)'))
            tile = landmark_names[tile]
        if border and on_border(cell):
            raise ValueError(f'landmark {list(cell)} lies on the border wall')
        if cell in path_cells:
            raise ValueError(f'landmark {list(cell)} lies on a path cell')
        if cell == anchor:
            raise ValueError(f'landmark {list(cell)} lies on the anchor cell')
        info = tile_info(tile)
        if info.get('unsupported_gap') or info['autotile'] or info['sheet'] not in ('B', 'C', 'D', 'E'):
            raise ValueError('a landmark must be an ordinary B-E tile')
        if not names[info['sheet_slot']]:
            raise ValueError(f'landmark tile {tile} is on an empty tileset sheet (tileset_names[{info["sheet_slot"]}])')
        layer = item.get('layer', 1)
        layers = [floor_tile, tile if layer == 1 else 0, tile if layer == 2 else 0]
        passage = tile_passage(layers, flags)
        placed.append({'x': cell[0], 'y': cell[1], 'tile': tile, 'layer': layer, 'blocks': not all(passage.values())})
    return {'style': 'room', 'preset': preset, 'border': border, 'floor': layout['floor'], 'wall': layout.get('wall') if border else None,
            'path': layout.get('path') if points else None, 'floor_tile_id': floor_tile, 'wall_tile_id': wall_tile, 'path_tile_id': path_tile,
            'anchor': list(anchor) if anchor else None, 'paths': [list(point) for point in points],
            'path_cells': sorted([cell[0], cell[1]] for cell in path_cells), 'landmarks': placed}


def summary(plan):
    """Compact JSON-able description (no cell lists) for snapshots and plan summaries."""
    return {'preset': plan['preset'], 'border': plan['border'], 'floor_tile_id': plan['floor_tile_id'], 'wall_tile_id': plan['wall_tile_id'],
            'path_tile_id': plan['path_tile_id'], 'anchor': plan['anchor'], 'path_cell_count': len(plan['path_cells']),
            'landmarks': [{'x': item['x'], 'y': item['y'], 'tile': item['tile'], 'layer': item['layer']} for item in plan['landmarks']]}


def paint(plan, width, height):
    """Table data (z-major: layers 0, 1, 2, then the region/shadow layer, all 0) of a resolved layout."""
    cells = width * height
    data = [plan['floor_tile_id']] * cells + [0] * (cells * 3)
    if plan['border']:
        for x in range(width):
            data[x] = data[(height - 1) * width + x] = plan['wall_tile_id']
        for y in range(height):
            data[y * width] = data[y * width + width - 1] = plan['wall_tile_id']
    for x, y in plan['path_cells']:
        data[y * width + x] = plan['path_tile_id']
    for item in plan['landmarks']:
        data[item['layer'] * cells + item['y'] * width + item['x']] = item['tile']
    return data


# ---------------------------------------------------------------- reachability

OPPOSITE = {'down': 'up', 'up': 'down', 'left': 'right', 'right': 'left'}
STEP = {'down': (0, 1), 'up': (0, -1), 'left': (-1, 0), 'right': (1, 0)}


def passage_grid(width, height, data, flags):
    """Per cell {direction: bool} from the three static layers (the map tile audit's estimate; unknown/gap tiles count as blocked). Cached by tile triple."""
    cells = width * height
    cache, grid = {}, []
    for position in range(cells):
        key = (data[position], data[cells + position], data[2 * cells + position])
        if key not in cache:
            answer = tile_passage(list(key), flags)
            cache[key] = {name: bool(value) for name, value in answer.items()}
        grid.append(cache[key])
    return grid


def reachable(width, height, data, flags, anchors):
    """Cells the player can walk to from the anchor cells (4-way breadth-first search over passable cells, tile layers only). Returns (visited, grid)."""
    if width * height > MAX_SIZE * MAX_SIZE or len(data) < width * height * 3:
        raise ValueError('map too large or its Table is incomplete for the reachability check')
    grid = passage_grid(width, height, data, flags)
    visited = bytearray(width * height)
    queue = deque()
    for x, y in anchors:
        if 0 <= x < width and 0 <= y < height and not visited[y * width + x]:
            visited[y * width + x] = 1
            queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for name, (dx, dy) in STEP.items():
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height) or visited[ny * width + nx]:
                continue
            if grid[y * width + x][name] and grid[ny * width + nx][OPPOSITE[name]]:
                visited[ny * width + nx] = 1
                queue.append((nx, ny))
    return visited, grid


def event_reachable(visited, width, height, x, y, solid):
    """A solid (same-priority) event can be reached from any reachable neighbour cell, any other event only from its own cell."""
    if 0 <= x < width and 0 <= y < height and visited[y * width + x]:
        return True
    if not solid:
        return False
    return any(0 <= x + dx < width and 0 <= y + dy < height and visited[(y + dy) * width + x + dx] for dx, dy in STEP.values())


def transfer_targets(commands, map_id):
    """Cells of direct-designation Transfer Player commands (code 201) aimed at `map_id`; commands are (code, parameters) pairs."""
    found = []
    for code, params in commands:
        if code == 201 and isinstance(params, (list, tuple)) and len(params) >= 4 and params[0] == 0 and params[1] == map_id \
                and is_int(params[2]) and is_int(params[3]):
            found.append((params[2], params[3]))
    return found


def unreachable_message(name, x, y, solid, anchors, stuck, map_id):
    where = ', '.join(f'({ax},{ay})' for ax, ay in anchors)
    why = ' (the player cannot move off the arrival/start cell: it and its neighbours are impassable)' if stuck else ''
    need = 'no reachable neighbouring cell' if solid else 'an unreachable cell'
    return (f'Event "{name}" at ({x},{y}) on map {map_id} has {need} from the arrival/start cell {where}{why}: the player may not be able to reach it '
            f'(tile layers only; other events and scripts are not considered).')


def check_events(width, height, data, flags, anchors, events, map_id):
    """Warnings for placed events. `events` is a list of (name, x, y, solid). Returns [] when there is no anchor to start from."""
    anchors = sorted({(x, y) for x, y in anchors if 0 <= x < width and 0 <= y < height})
    if not anchors:
        return []
    visited, _ = reachable(width, height, data, flags, anchors)
    stuck = sum(visited) == len(anchors)
    return [unreachable_message(name, x, y, solid, anchors, stuck, map_id) for name, x, y, solid in events
            if not event_reachable(visited, width, height, x, y, solid)]
