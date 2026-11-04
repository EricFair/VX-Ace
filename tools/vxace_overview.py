#!/usr/bin/env python3
"""One-page project overview (maps, events, custom scripts, switch/variable use, database counts) from a normalized VX Ace index."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

VERSION = '1.0.0'
MAX_MAP_EVENTS = 60        # events listed per map in overview.md (the JSON keeps them all)
MAX_PAGES = 8
MAX_LINE = 200
MAX_STEPS = 6              # command summaries per page
MAX_WHERE = 5
MAX_SWITCH_ROWS = 150
MAX_SCRIPT_ROWS = 60
# Slot counts of an unedited new VX Ace project (project2.zip in the editor install): entries above these ids were added by the author.
STOCK_SLOTS = {'actors': 10, 'classes': 10, 'skills': 126, 'items': 16, 'weapons': 60, 'armors': 60, 'enemies': 30, 'troops': 30,
               'states': 25, 'animations': 110, 'tilesets': 4, 'common-events': 10}
TRIGGERS = {0: 'action', 1: 'player touch', 2: 'event touch', 3: 'autorun', 4: 'parallel'}
PRIORITY = {0: 'below', 1: 'same', 2: 'above'}
DIRECTIONS = {0: 'keep facing', 2: 'down', 4: 'left', 6: 'right', 8: 'up'}
SELF = 'ABCD'


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def clip(text, limit=MAX_LINE):
    text = re.sub(r'\s+', ' ', str(text)).strip()
    return text if len(text) <= limit else text[:limit - 3] + '...'


def cell(text):
    return clip(text).replace('|', '\\|')


class Names:
    """id -> name lookups from the index database files."""
    def __init__(self, root):
        self.tables = {}
        for key, file in (('actor', 'actors'), ('item', 'items'), ('weapon', 'weapons'), ('armor', 'armors'), ('skill', 'skills'),
                          ('troop', 'troops'), ('common', 'common-events'), ('enemy', 'enemies'), ('tileset', 'tilesets')):
            rows = load(root / 'database' / (file + '.json'), []) or []
            self.tables[key] = {r['id']: r.get('name') or '' for r in rows if isinstance(r, dict) and isinstance(r.get('id'), int)} if isinstance(rows, list) else {}
        system = load(root / 'database' / 'system.json', {}) or {}
        self.switches = system.get('switches') if isinstance(system.get('switches'), list) else []
        self.variables = system.get('variables') if isinstance(system.get('variables'), list) else []
        self.system = system if isinstance(system, dict) else {}
        infos = load(root / 'database' / 'map-infos.json', {}) or {}
        self.maps = {int(k): v.get('name') or '' for k, v in infos.items() if isinstance(v, dict) and str(k).isdigit()} if isinstance(infos, dict) else {}

    def get(self, kind, number):
        return self.tables.get(kind, {}).get(number) if isinstance(number, int) else None

    def label(self, kind, number):
        name = self.get(kind, number)
        return '%s %s%s' % (kind, number, ' "%s"' % name if name else '')

    def switch(self, number):
        name = self.switches[number] if isinstance(number, int) and 0 <= number < len(self.switches) and isinstance(self.switches[number], str) else ''
        return 'S%s%s' % (number, ' "%s"' % name if name else '')

    def variable(self, number):
        name = self.variables[number] if isinstance(number, int) and 0 <= number < len(self.variables) and isinstance(self.variables[number], str) else ''
        return 'V%s%s' % (number, ' "%s"' % name if name else '')

    def map(self, number):
        name = self.maps.get(number)
        return 'map %s%s' % (number, ' "%s"' % name if name else '')


def arg(params, i, default=None):
    return params[i] if isinstance(params, list) and len(params) > i else default


def condition_text(cond, names):
    if not isinstance(cond, dict):
        return 'always'
    parts = []
    if cond.get('switch1_valid'): parts.append(names.switch(cond.get('switch1_id')) + ' ON')
    if cond.get('switch2_valid'): parts.append(names.switch(cond.get('switch2_id')) + ' ON')
    if cond.get('variable_valid'): parts.append('%s >= %s' % (names.variable(cond.get('variable_id')), cond.get('variable_value')))
    if cond.get('self_switch_valid'): parts.append('self-switch %s ON' % cond.get('self_switch_ch'))
    if cond.get('item_valid'): parts.append('has ' + names.label('item', cond.get('item_id')))
    if cond.get('actor_valid'): parts.append('in party: ' + names.label('actor', cond.get('actor_id')))
    return ' & '.join(parts) or 'always'


def graphic_text(graphic):
    if not isinstance(graphic, dict):
        return '-'
    if graphic.get('tile_id'):
        return 'tile %s' % graphic['tile_id']
    if graphic.get('character_name'):
        return '%s[%s] %s' % (graphic['character_name'], graphic.get('character_index', 0), DIRECTIONS.get(graphic.get('direction'), graphic.get('direction')))
    return '-'


def operand_text(p, names):
    """Control Variables operand (parameters 3..) in a few words."""
    kind = arg(p, 3)
    if kind == 0: return str(arg(p, 4))
    if kind == 1: return names.variable(arg(p, 4))
    if kind == 2: return 'random %s..%s' % (arg(p, 4), arg(p, 5))
    if kind == 4: return 'script'
    return 'game data'


def summarize_command(cmd, nxt, names):
    """One short phrase for an event command, or None for structural/noise commands. `nxt` is the list of following commands."""
    code = cmd.get('code'); p = cmd.get('parameters') or []
    if code in (101,):
        taken = []
        for q in nxt:
            if isinstance(q, dict) and q.get('code') == 401 and q.get('parameters'): taken.append(str(q['parameters'][0]))
            else: break
        first = taken[0] if taken else ''
        return 'text "%s"' % clip(first, 60) if first else 'text (empty)'
    if code == 102: return 'choices ' + ' / '.join('"%s"' % clip(c, 20) for c in (arg(p, 0) or []) if isinstance(c, str))
    if code == 103: return 'input number -> ' + names.variable(arg(p, 0))
    if code == 111:
        kind = arg(p, 0)
        if kind == 0: return 'if ' + names.switch(arg(p, 1)) + (' ON' if arg(p, 2) == 0 else ' OFF')
        if kind == 1:
            right = 'V%s' % arg(p, 3) if arg(p, 2) == 1 else str(arg(p, 3))
            return 'if %s %s %s' % (names.variable(arg(p, 1)), {0: '==', 1: '>=', 2: '<=', 3: '>', 4: '<', 5: '!='}.get(arg(p, 4), '?'), right)
        if kind == 2: return 'if self-switch %s %s' % (arg(p, 1), 'ON' if arg(p, 2) == 0 else 'OFF')
        if kind == 4: return 'if ' + names.label('actor', arg(p, 1)) + ' in party/has state'
        if kind == 7: return 'if gold >= %s' % arg(p, 1)
        if kind == 8: return 'if has ' + names.label('item', arg(p, 1))
        return 'if (condition %s)' % kind
    if code == 117: return 'call ' + names.label('common', arg(p, 0))
    if code == 121:
        a, b = arg(p, 0), arg(p, 1)
        who = names.switch(a) if a == b else 'S%s-%s' % (a, b)
        return '%s %s' % (who, 'ON' if arg(p, 2) == 0 else 'OFF')
    if code == 122:
        a, b = arg(p, 0), arg(p, 1)
        who = names.variable(a) if a == b else 'V%s-%s' % (a, b)
        op = {0: '=', 1: '+=', 2: '-=', 3: '*=', 4: '/=', 5: '%='}.get(arg(p, 2), '?')
        return '%s %s %s' % (who, op, operand_text(p, names))
    if code == 123: return 'self-switch %s %s' % (arg(p, 0), 'ON' if arg(p, 1) == 0 else 'OFF')
    if code == 125: return '%s gold' % (('give %s' % arg(p, 2)) if arg(p, 0) == 0 else ('take %s' % arg(p, 2)))
    if code in (126, 127, 128):
        kind = {126: 'item', 127: 'weapon', 128: 'armor'}[code]
        return '%s %s x%s' % ('give' if arg(p, 1) == 0 else 'take', names.label(kind, arg(p, 0)), arg(p, 3))
    if code == 129: return '%s %s %s' % ('add' if arg(p, 1) == 0 else 'remove', 'actor', names.label('actor', arg(p, 0)).replace('actor ', '', 1))
    if code == 201:
        if arg(p, 0) == 0:
            return 'transfer -> %s (%s,%s)' % (names.map(arg(p, 1)), arg(p, 2), arg(p, 3))
        return 'transfer -> map V%s (%s,%s) (variables)' % (arg(p, 1), 'V%s' % arg(p, 2), 'V%s' % arg(p, 3))
    if code == 301:
        if arg(p, 0) == 0:
            return 'battle ' + names.label('troop', arg(p, 1))
        return 'battle (troop from V%s)' % arg(p, 1)
    if code == 302:
        goods = [p]
        for q in nxt:
            if isinstance(q, dict) and q.get('code') == 605: goods.append(q.get('parameters') or [])
            else: break
        kinds = {0: 'item', 1: 'weapon', 2: 'armor'}
        shown = []
        for g in goods[:4]:
            kind = kinds.get(arg(g, 0))
            if kind: shown.append((names.get(kind, arg(g, 1)) or '%s %s' % (kind, arg(g, 1))) + ('@%s' % arg(g, 3) if arg(g, 2) == 1 else ''))
        more = len(goods) - 4
        return 'shop: ' + ', '.join(shown) + (' +%d more' % more if more > 0 else '')
    if code == 303: return 'name input ' + names.label('actor', arg(p, 0))
    if code == 311: return 'heal HP'
    if code == 314: return 'recover all'
    if code == 230: return 'wait %s' % arg(p, 0)
    if code == 235 or code == 231: return 'picture'
    if code in (241, 132): return 'BGM ' + str((arg(p, 0) or {}).get('name', '') if isinstance(arg(p, 0), dict) else '')
    if code == 250: return 'SE ' + str((arg(p, 0) or {}).get('name', '') if isinstance(arg(p, 0), dict) else '')
    if code == 355:
        lines = [str(arg(p, 0, ''))]
        for q in nxt:
            if isinstance(q, dict) and q.get('code') == 655 and q.get('parameters'): lines.append(str(q['parameters'][0]))
            else: break
        return 'script: ' + clip(' ; '.join(lines), 60)
    if code == 116: return 'erase event'
    if code == 115: return 'exit event'
    if code == 205: return 'move route'
    if code == 353: return 'game over'
    if code == 354: return 'to title'
    if code == 352: return 'save screen'
    if code == 351: return 'menu'
    if code == 281: return 'map name display'
    if code in (108, 408): return None
    return None


def page_steps(page, names):
    commands = [c for c in page.get('list') or [] if isinstance(c, dict)]
    out = []
    for i, cmd in enumerate(commands):
        text = summarize_command(cmd, commands[i + 1:], names)
        if text:
            out.append(text)
    shown = out[:MAX_STEPS]
    return '; '.join(shown) + ('; ... +%d' % (len(out) - MAX_STEPS) if len(out) > MAX_STEPS else '') if shown else '(no actions)'


def build_maps(root, names, project):
    maps = []
    listed = {m['map_id']: m for m in (project.get('maps') or []) if isinstance(m, dict) and isinstance(m.get('map_id'), int)}
    for file in sorted((root / 'maps').glob('map-*.json')):
        m = re.match(r'map-(\d+)\.json$', file.name)
        data = load(file)
        if not m or not isinstance(data, dict): continue
        mid = int(m.group(1)); events = []
        raw = data.get('events') if isinstance(data.get('events'), dict) else {}
        for key in sorted(raw, key=lambda k: int(k) if str(k).isdigit() else 0):
            ev = raw[key]
            if not isinstance(ev, dict): continue
            pages = []
            for n, page in enumerate(ev.get('pages') or [], 1):
                if not isinstance(page, dict): continue
                pages.append({'page': n, 'trigger': TRIGGERS.get(page.get('trigger'), page.get('trigger')), 'priority': PRIORITY.get(page.get('priority_type'), page.get('priority_type')),
                              'graphic': graphic_text(page.get('graphic')), 'condition': condition_text(page.get('condition'), names), 'summary': page_steps(page, names)})
            events.append({'id': ev.get('id'), 'name': ev.get('name') or '', 'x': ev.get('x'), 'y': ev.get('y'), 'pages': pages})
        maps.append({'map_id': mid, 'name': names.maps.get(mid) or (listed.get(mid) or {}).get('name', ''), 'display_name': data.get('display_name') or '',
                     'width': data.get('width'), 'height': data.get('height'), 'tileset_id': data.get('tileset_id'),
                     'tileset': names.get('tileset', data.get('tileset_id')) or '', 'event_count': len(events), 'events': events})
    return maps


def build_scripts(root):
    order = (load(root / 'scripts' / 'order.json', {}) or {}).get('scripts') or []
    start = next((r['index'] for r in order if isinstance(r, dict) and 'materials' in str(r.get('name', '')).lower()), None)
    end = next((r['index'] for r in order if isinstance(r, dict) and 'main process' in str(r.get('name', '')).lower()), None)
    out = []
    if start is None:
        return {'materials_marker_found': False, 'scripts': out}
    for row in order:
        if not isinstance(row, dict) or not isinstance(row.get('index'), int) or row['index'] <= start or (end is not None and row['index'] >= end):
            continue
        try:
            source = (root / 'scripts' / row['path']).read_text(encoding='utf-8')
        except (OSError, KeyError):
            source = ''
        if not source.strip():
            continue
        classes = re.findall(r'^\s*(?:class|module)\s+([A-Z][\w:]*)', source, re.M)
        aliases = re.findall(r'^\s*alias_method\s+[:\'"]?(\w+[?!=]?)[\'"]?\s*,\s*[:\'"]?(\w+[?!=]?)', source, re.M) + \
                  re.findall(r'^\s*alias\s+:?(\w+[?!=]?)\s+:?(\w+[?!=]?)', source, re.M)
        out.append({'index': row['index'], 'name': row.get('name') or '', 'lines': source.count('\n') + 1, 'classes': sorted(set(classes)),
                    'aliases': ['%s <- %s' % pair for pair in aliases]})
    return {'materials_marker_found': True, 'scripts': out}


def where(entries):
    seen, out = set(), []
    for e in entries:
        kind = e.get('kind')
        key = ('map %s ev %s' % (e.get('map_id'), e.get('event_id')) if kind == 'map' else 'CE %s' % e.get('common_event_id') if kind == 'common_event'
               else 'troop %s' % e.get('troop_id') if kind == 'troop' else str(kind))
        if key not in seen:
            seen.add(key); out.append(key)
    return out


def build_flags(root):
    rows = {}
    for kind, file in (('switch', 'switches.json'), ('variable', 'variables.json')):
        entries = load(root / 'analysis' / file, []) or []
        rows[kind] = [{'id': r.get('id'), 'name': r.get('name') or '', 'read_in': where(r.get('reads') or []), 'written_in': where(r.get('writes') or [])}
                      for r in entries if isinstance(r, dict)]
    return rows


def build_database(root):
    out = []
    for file, stock in STOCK_SLOTS.items():
        rows = load(root / 'database' / (file + '.json'))
        if not isinstance(rows, list):
            continue
        real = [r for r in rows if isinstance(r, dict)]
        new = [{'id': r.get('id'), 'name': r.get('name') or ''} for r in real if isinstance(r.get('id'), int) and r['id'] > stock]
        out.append({'table': file, 'entries': len(real), 'stock_slots': stock, 'new_entries': new})
    return out


def build(index_dir):
    root = Path(index_dir).expanduser().resolve()
    project = load(root / 'project.json', {}) or {}
    names = Names(root)
    system = names.system
    return {'overview_version': VERSION, 'project_name': project.get('project_name', root.name),
            'start': {'map_id': system.get('start_map_id'), 'x': system.get('start_x'), 'y': system.get('start_y'), 'party': [names.label('actor', a) for a in system.get('party_members') or []]},
            'maps': build_maps(root, names, project), 'scripts': build_scripts(root), 'flags': build_flags(root), 'database': build_database(root),
            'common_events': [{'id': k, 'name': v} for k, v in sorted(names.tables['common'].items()) if v],
            'limits': ['Static summary of the decoded index; command lines show the first %d actions of a page and are not a full behaviour proof.' % MAX_STEPS,
                       'Switch/variable "where" lists come from the reader (conditions, control commands, transfers); script-set values are not seen.',
                       'Stock ids are the slot counts of an unedited new project; a project started from another template shows its own entries as new.']}


def render(o, max_events=MAX_MAP_EVENTS):
    out = ['# Project overview: ' + str(o['project_name']), '']
    st = o['start']
    out += ['Start: map %s at (%s,%s); party: %s' % (st['map_id'], st['x'], st['y'], ', '.join(st['party']) or 'none'), '']
    out += ['## Maps (%d)' % len(o['maps']), '', '| id | name | display | size | tileset | events |', '|---|---|---|---|---|---|']
    out += ['| %s | %s | %s | %sx%s | %s %s | %s |' % (m['map_id'], cell(m['name']), cell(m['display_name']), m['width'], m['height'], m['tileset_id'], cell(m['tileset']), m['event_count']) for m in o['maps']]
    out += ['', '## Events per map', '']
    for m in o['maps']:
        out.append('### Map %s %s' % (m['map_id'], m['name']))
        if not m['events']:
            out += ['', '(no events)', '']; continue
        out.append('')
        for ev in m['events'][:max_events]:
            out.append('- **%s** `%s` (%s,%s)' % (ev['id'], clip(ev['name'], 40), ev['x'], ev['y']))
            for pg in ev['pages'][:MAX_PAGES]:
                out.append('  - p%s [%s, %s] %s | when: %s | %s' % (pg['page'], pg['trigger'], pg['priority'], pg['graphic'], pg['condition'], pg['summary']))
            if len(ev['pages']) > MAX_PAGES: out.append('  - ... %d more pages' % (len(ev['pages']) - MAX_PAGES))
        if len(m['events']) > max_events: out.append('- ... %d more events (see overview.json)' % (len(m['events']) - max_events))
        out.append('')
    s = o['scripts']
    out += ['## Custom scripts (after "Materials")', '']
    if not s['materials_marker_found']: out.append('No "Materials" marker script found.')
    elif not s['scripts']: out.append('None.')
    for r in s['scripts'][:MAX_SCRIPT_ROWS]:
        out.append('- [%s] %s (%s lines): classes %s; aliases %s' % (r['index'], r['name'], r['lines'], ', '.join(r['classes'][:8]) or '-', '; '.join(r['aliases'][:6]) or '-'))
    out += ['', '## Switches and variables in use', '']
    for kind, label in (('switch', 'S'), ('variable', 'V')):
        rows = o['flags'][kind]
        out.append('%s (%d referenced)' % (kind.capitalize() + 'es' if kind == 'switch' else 'Variables', len(rows)))
        out.append('')
        for r in rows[:MAX_SWITCH_ROWS]:
            def short(items):
                return ', '.join(items[:MAX_WHERE]) + (' +%d' % (len(items) - MAX_WHERE) if len(items) > MAX_WHERE else '') if items else '-'
            out.append('- %s%s %s: read in %s; written in %s' % (label, r['id'], clip(r['name'], 40) or '(unnamed)', short(r['read_in']), short(r['written_in'])))
        if len(rows) > MAX_SWITCH_ROWS: out.append('- ... %d more (see overview.json)' % (len(rows) - MAX_SWITCH_ROWS))
        out.append('')
    out += ['## Database', '', '| table | entries | stock slots | new above stock |', '|---|---|---|---|']
    for r in o['database']:
        added = ', '.join('%s %s' % (n['id'], clip(n['name'], 24)) for n in r['new_entries'][:12]) + (' +%d' % (len(r['new_entries']) - 12) if len(r['new_entries']) > 12 else '')
        out.append('| %s | %s | %s | %s |' % (r['table'], r['entries'], r['stock_slots'], cell(added or '-')))
    out += ['', '## Limits', ''] + ['- ' + x for x in o['limits']]
    return '\n'.join(out) + '\n'


def generate(index_dir, output=None):
    root = Path(index_dir).expanduser().resolve()
    out = Path(output).expanduser().resolve() if output else root
    overview = build(root)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'overview.json').write_text(json.dumps(overview, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'overview.md').write_text(render(overview), encoding='utf-8')
    return {'maps': len(overview['maps']), 'events': sum(m['event_count'] for m in overview['maps']), 'custom_scripts': len(overview['scripts']['scripts'])}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--output', help='Folder for overview.md and overview.json (default: the index folder)')
    a = ap.parse_args(argv)
    try:
        print(json.dumps({'status': 'ok', **generate(a.index, a.output)}))
        return 0
    except Exception as exc:
        print('error: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
