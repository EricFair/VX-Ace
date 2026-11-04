#!/usr/bin/env python3
"""Staged-event command language (v1.19): bounded shape validation, id/reference checks and native command generation.

Used by vxace_map_events.append_staged_event, the impact report and the recipe runner. Nothing here writes files;
referenced database files are only read, and each one is bound by its own expected SHA-256 in the mutation."""
from __future__ import annotations
import hashlib
from collections import namedtuple
from pathlib import Path

MAX_COMMANDS = 40          # operations per command list (page or branch body)
MAX_DEPTH = 4              # deepest block indent
MAX_ROWS = 200             # generated native commands per page (terminator excluded)
VALUE_LIMIT = 99999999
VARIABLE_OPS = {'set': 0, 'add': 1, 'sub': 2}
CONDITION_OPS = {'==': 0, '>=': 1, '<=': 2, '>': 3, '<': 4, '!=': 5}
KINDS = ('text', 'set_switch', 'set_variable', 'set_self_switch', 'choices', 'if', 'battle', 'party',
         'common_event', 'gold', 'item', 'weapon', 'armor', 'transfer', 'wait', 'erase_event', 'move_route')
# Event page triggers (RPG::Event::Page#trigger). Autorun (3) is refused: it has no termination proof.
PAGE_TRIGGERS = {'action': 0, 'player_touch': 1, 'event_touch': 2, 'parallel': 4}
TOUCH_TRIGGERS = ('player_touch', 'event_touch')
# Autonomous movement (RPG::Event::Page#move_type) and the bounded move-route language, codes as in Game_Character#process_move_command.
MOVE_TYPES = {'fixed': 0, 'random': 1, 'approach': 2, 'custom': 3}
ROUTE_MOVES = {'down': 1, 'left': 2, 'right': 3, 'up': 4, 'random': 9, 'toward_player': 10, 'away_from_player': 11, 'forward': 12, 'backward': 13}
ROUTE_TURNS = {'down': 16, 'left': 17, 'right': 18, 'up': 19, 'random': 24, 'toward_player': 25, 'away_from_player': 26}
ROUTE_WAIT_CODE = 15
MAX_ROUTE = 40
ROUTE_TARGETS = {'player': -1, 'this': 0}      # Game_Interpreter#get_character: negative = player, 0 = this event
# Plain (not yet native) move route objects carried inside plain_rows parameters.
PlainMoveCommand = namedtuple('PlainMoveCommand', 'code parameters')
PlainMoveRoute = namedtuple('PlainMoveRoute', 'repeat skippable wait list')
# kind -> (database file, native class, mutation hash field)
REF_FILES = {'troops': ('Troops', 'RPG::Troop', 'expected_troops_sha256'),
             'actors': ('Actors', 'RPG::Actor', 'expected_actors_sha256'),
             'common_events': ('CommonEvents', 'RPG::CommonEvent', 'expected_common_events_sha256'),
             'items': ('Items', 'RPG::Item', 'expected_items_sha256'),
             'weapons': ('Weapons', 'RPG::Weapon', 'expected_weapons_sha256'),
             'armors': ('Armors', 'RPG::Armor', 'expected_armors_sha256')}
# goods commands: key -> (REF_FILES kind, native command code, label)
GOODS = {'item': ('items', 126), 'weapon': ('weapons', 127), 'armor': ('armors', 128)}
MAPINFOS_FIELD = 'expected_mapinfos_sha256'
MAPS_FIELD = 'expected_destination_maps_sha256'


def plain_int(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label} must be an integer {low}..{high}')
    return value


def check_text(value, label, limit, empty=False):
    if not isinstance(value, str) or not (0 if empty else 1) <= len(value) <= limit or any(ord(c) < 32 or c == '\\' or ord(c) == 127 for c in value):
        raise ValueError(label + ' must be bounded literal text without control/escape codes')
    value.encode('utf-8', 'strict')
    return value


def boolean(value, label):
    if type(value) is not bool:
        raise ValueError(label + ' must be true or false')
    return value


def exact_keys(op, required, optional=()):
    keys = set(op)
    if not set(required) <= keys <= set(required) | set(optional):
        raise ValueError('Unsupported staged command keys ' + str(sorted(keys)))


# ------------------------------------------------------------------ shape

def body(value, indent, label, low):
    """A nested command list whose commands sit at `indent`."""
    if indent > MAX_DEPTH:
        raise ValueError(f'Nesting deeper than {MAX_DEPTH} levels is refused')
    if not isinstance(value, list) or not low <= len(value) <= MAX_COMMANDS:
        raise ValueError(f'{label} needs {low}..{MAX_COMMANDS} commands')
    for op in value:
        op_shape(op, indent)


def condition_shape(cond):
    if not isinstance(cond, dict):
        raise ValueError('if condition must be an object')
    keys = set(cond)
    if 'switch' in keys:
        exact_keys(cond, {'switch', 'is'});plain_int(cond['switch'], 'if switch id', 1, 2**31 - 1);boolean(cond['is'], 'if switch is')
    elif 'variable' in keys:
        exact_keys(cond, {'variable', 'op', 'value'});plain_int(cond['variable'], 'if variable id', 1, 2**31 - 1)
        if not isinstance(cond['op'], str) or cond['op'] not in CONDITION_OPS:
            raise ValueError('if variable op must be one of ' + ', '.join(CONDITION_OPS))
        plain_int(cond['value'], 'if variable value', -VALUE_LIMIT, VALUE_LIMIT)
    elif 'self_switch' in keys:
        exact_keys(cond, {'self_switch', 'is'})
        if not isinstance(cond['self_switch'], str) or cond['self_switch'] not in ('A', 'B', 'C', 'D'):
            raise ValueError('if self_switch must be A, B, C or D')
        boolean(cond['is'], 'if self_switch is')
    elif 'gold_at_least' in keys:
        exact_keys(cond, {'gold_at_least'});plain_int(cond['gold_at_least'], 'gold_at_least', 0, VALUE_LIMIT)
    elif 'has_item' in keys:
        exact_keys(cond, {'has_item'});plain_int(cond['has_item'], 'has_item id', 1, 2**31 - 1)
    else:
        raise ValueError('Unsupported if condition; use switch, variable, self_switch, gold_at_least or has_item')


def route_shape(route, label='move route'):
    """Validate a move-route command list (1..40 commands of the bounded language). Raises ValueError."""
    if not isinstance(route, list) or not 1 <= len(route) <= MAX_ROUTE:
        raise ValueError(f'{label} needs 1..{MAX_ROUTE} route commands')
    for item in route:
        if isinstance(item, str):
            if item not in ROUTE_MOVES:
                raise ValueError(f'{label} command "{item}" is unsupported; use ' + ', '.join(ROUTE_MOVES) + ' or {"wait": n} / {"turn": direction}')
        elif isinstance(item, dict) and set(item) == {'wait'}:
            plain_int(item['wait'], label + ' wait frames', 1, 999)
        elif isinstance(item, dict) and set(item) == {'turn'}:
            if not isinstance(item['turn'], str) or item['turn'] not in ROUTE_TURNS:
                raise ValueError(label + ' turn must be one of ' + ', '.join(ROUTE_TURNS))
        else:
            raise ValueError(f'{label} command is unsupported (jump, graphic, script, switch, speed/frequency and other route commands are refused)')


def route_commands(route):
    """Native (code, parameters) pairs of a validated route, without the terminator."""
    rows = []
    for item in route:
        if isinstance(item, str):
            rows.append((ROUTE_MOVES[item], []))
        elif 'wait' in item:
            rows.append((ROUTE_WAIT_CODE, [item['wait']]))
        else:
            rows.append((ROUTE_TURNS[item['turn']], []))
    return rows


def plain_route(route, repeat, skippable, wait):
    """A plain move route (editor layout: repeat, skippable, wait, list ending in the code-0 terminator)."""
    return PlainMoveRoute(repeat, skippable, wait, tuple(PlainMoveCommand(code, params) for code, params in route_commands(route) + [(0, [])]))


def describe_route(route):
    """One line for a validated route."""
    parts = []
    for item in route:
        parts.append(item if isinstance(item, str) else f'wait {item["wait"]}' if 'wait' in item else 'turn ' + item['turn'])
    return ', '.join(parts)


def command_notes(op):
    """Advisory sentences for a validated erase_event / move_route command (shared by the staged and common-event impact)."""
    notes = []
    if 'erase_event' in op:
        notes.append('Erases this event; the erase is temporary and the event returns when the map is reloaded (leaving and re-entering the map). Use a self-switch page for a permanent disappearance.')
    if 'move_route' in op:
        spec = op['move_route'];who = 'the player' if spec['target'] == 'player' else 'this event'
        moves = [item for item in spec['route'] if isinstance(item, str)]
        if spec['target'] == 'player':
            notes.append('Forces the player along a move route: the player cannot move or open the menu until it ends.')
        if spec.get('repeat', False):
            notes.append(f'The move route of {who} repeats and never ends on its own' + (' (a forced player route would lock the player permanently).' if spec['target'] == 'player' else '.'))
        if moves and not spec.get('skippable', False):
            notes.append(f'A blocked step stalls the route of {who} (it retries the same step) and' + (', with wait, the event never continues.' if spec.get('wait', True) else ' keeps it from finishing.')
                         + ' Set skippable true if the path may be blocked.')
    return notes


def move_route_shape(spec):
    if not isinstance(spec, dict) or not {'target', 'route'} <= set(spec) <= {'target', 'route', 'repeat', 'skippable', 'wait'}:
        raise ValueError('move_route needs target and route (optional repeat, skippable, wait)')
    if not isinstance(spec['target'], str) or spec['target'] not in ROUTE_TARGETS:
        raise ValueError('move_route target must be player or this')
    route_shape(spec['route'])
    for key in ('repeat', 'skippable', 'wait'):
        if key in spec:
            boolean(spec[key], 'move_route ' + key)
    if spec.get('repeat', False) and spec.get('wait', True):
        raise ValueError('A repeating move route cannot be waited for (the event would never continue); use wait false')


def op_shape(op, indent=0):
    """Pure validation of one staged command at block indent `indent`. Raises ValueError."""
    if not isinstance(op, dict):
        raise ValueError('Staged command must be an object')
    kinds = [kind for kind in KINDS if kind in op]
    if len(kinds) != 1:
        raise ValueError('Unsupported staged command; use text, set_switch, set_variable, set_self_switch, choices, if, battle, party, common_event, gold, item, weapon, armor, transfer, wait, erase_event or move_route with exact keys')
    kind = kinds[0]
    if kind == 'text':
        exact_keys(op, {'text'});lines = op['text']
        if not isinstance(lines, list) or not 1 <= len(lines) <= 4:
            raise ValueError('Dialogue requires one to four literal lines')
        if not any([check_text(line, 'dialogue line', 500, True) for line in lines]):
            raise ValueError('Dialogue must contain text')
    elif kind == 'set_switch':
        exact_keys(op, {'set_switch', 'value'});plain_int(op['set_switch'], 'set_switch id', 1, 2**31 - 1)
        boolean(op['value'], 'set_switch value')
    elif kind == 'set_variable':
        exact_keys(op, {'set_variable', 'op', 'value'});plain_int(op['set_variable'], 'set_variable id', 1, 2**31 - 1)
        if not isinstance(op['op'], str) or op['op'] not in VARIABLE_OPS:
            raise ValueError('set_variable op must be set, add or sub')
        plain_int(op['value'], 'set_variable value', -VALUE_LIMIT, VALUE_LIMIT)
    elif kind == 'set_self_switch':
        exact_keys(op, {'set_self_switch', 'value'})
        if not isinstance(op['set_self_switch'], str) or op['set_self_switch'] not in ('A', 'B', 'C', 'D'):
            raise ValueError('set_self_switch must be A, B, C or D')
        boolean(op['value'], 'set_self_switch value')
    elif kind == 'choices':
        exact_keys(op, {'choices', 'cancel', 'branches'});choices = op['choices']
        if not isinstance(choices, list) or not 2 <= len(choices) <= 4:
            raise ValueError('choices needs 2..4 literal choice texts')
        for choice in choices:
            check_text(choice, 'choice text', 50)
        cancel = op['cancel']
        if cancel is not None:
            plain_int(cancel, 'choices cancel', 0, len(choices) - 1)
        if not isinstance(op['branches'], list) or len(op['branches']) != len(choices):
            raise ValueError('choices needs exactly one branch list per choice')
        for branch in op['branches']:
            body(branch, indent + 1, 'choice branch', 0)
    elif kind == 'if':
        exact_keys(op, {'if', 'then'}, {'else'});condition_shape(op['if']);body(op['then'], indent + 1, 'if then branch', 1)
        if 'else' in op:
            body(op['else'], indent + 1, 'if else branch', 1)
    elif kind == 'battle':
        exact_keys(op, {'battle', 'can_escape', 'can_lose'}, {'win', 'escape', 'lose'})
        plain_int(op['battle'], 'battle troop id', 1, 2**31 - 1);boolean(op['can_escape'], 'can_escape');boolean(op['can_lose'], 'can_lose')
        if 'escape' in op and not op['can_escape']:
            raise ValueError('battle escape branch needs can_escape true')
        if 'lose' in op and not op['can_lose']:
            raise ValueError('battle lose branch needs can_lose true')
        for key in ('win', 'escape', 'lose'):
            if key in op:
                body(op[key], indent + 1, 'battle ' + key + ' branch', 0)
    elif kind == 'party':
        exact_keys(op, {'party', 'actor', 'initialize'})
        if not isinstance(op['party'], str) or op['party'] not in ('add', 'remove'):
            raise ValueError('party must be add or remove')
        plain_int(op['actor'], 'party actor id', 1, 2**31 - 1);boolean(op['initialize'], 'party initialize')
        if op['party'] == 'remove' and op['initialize']:
            raise ValueError('party remove cannot initialize the actor')
    elif kind == 'common_event':
        exact_keys(op, {'common_event'});plain_int(op['common_event'], 'common_event id', 1, 2**31 - 1)
    elif kind == 'gold':
        exact_keys(op, {'gold'});amount = plain_int(op['gold'], 'gold amount', -VALUE_LIMIT, VALUE_LIMIT)
        if amount == 0:
            raise ValueError('gold amount must not be zero')
    elif kind in GOODS:
        exact_keys(op, {kind, 'amount'});plain_int(op[kind], kind + ' id', 1, 2**31 - 1)
        amount = plain_int(op['amount'], kind + ' amount', -99, 99)
        if amount == 0:
            raise ValueError(kind + ' amount must not be zero')
    elif kind == 'transfer':
        exact_keys(op, {'transfer'});move = op['transfer']
        if not isinstance(move, dict) or set(move) != {'map_id', 'x', 'y', 'direction', 'fade'}:
            raise ValueError('transfer needs exactly map_id, x, y, direction and fade')
        plain_int(move['map_id'], 'transfer map_id', 1, 999999);plain_int(move['x'], 'transfer x', 0, 999);plain_int(move['y'], 'transfer y', 0, 999)
        if type(move['direction']) is not int or move['direction'] not in (0, 2, 4, 6, 8):
            raise ValueError('transfer direction must be 0, 2, 4, 6 or 8')
        plain_int(move['fade'], 'transfer fade', 0, 2)
    elif kind == 'erase_event':
        exact_keys(op, {'erase_event'})
        if op['erase_event'] is not True:
            raise ValueError('erase_event must be true')
    elif kind == 'move_route':
        exact_keys(op, {'move_route'});move_route_shape(op['move_route'])
    else:
        exact_keys(op, {'wait'});plain_int(op['wait'], 'wait frames', 1, 999)


def commands_shape(commands):
    """Validate one page's command list (1..40 operations, nesting <= 4, <= 200 native commands)."""
    body(commands, 0, 'Each page', 1)
    if len(plain_rows(commands)) > MAX_ROWS:
        raise ValueError(f'A page may generate at most {MAX_ROWS} native commands')


# ------------------------------------------------------------------ walking

def iter_ops(commands):
    """Every operation of a (possibly nested) command list; tolerant of malformed input."""
    if not isinstance(commands, list):
        return
    for op in commands:
        if not isinstance(op, dict):
            continue
        yield op
        for key in ('then', 'else', 'win', 'escape', 'lose'):
            yield from iter_ops(op.get(key))
        if isinstance(op.get('branches'), list):
            for branch in op['branches']:
                yield from iter_ops(branch)


def page_ops(pages):
    for page in pages if isinstance(pages, list) else []:
        if isinstance(page, dict):
            yield from iter_ops(page.get('commands'))


def staged_refs(pages):
    """Database ids referenced by the pages: {'troops','actors','common_events','items': set(ids), 'maps': set(ids)}."""
    refs = {kind: set() for kind in REF_FILES}
    refs['maps'] = set()
    def add(kind, value):
        if type(value) is int:refs[kind].add(value)
    for op in page_ops(pages):
        if 'battle' in op:add('troops', op['battle'])
        elif 'party' in op:add('actors', op.get('actor'))
        elif 'common_event' in op:add('common_events', op['common_event'])
        elif 'item' in op:add('items', op['item'])
        elif 'weapon' in op:add('weapons', op['weapon'])
        elif 'armor' in op:add('armors', op['armor'])
        elif isinstance(op.get('if'), dict) and 'has_item' in op['if']:add('items', op['if']['has_item'])
        elif isinstance(op.get('transfer'), dict):add('maps', op['transfer'].get('map_id'))
    return refs


def ref_fields(pages):
    """Extra hash fields the mutation must carry (exactly) for the databases the pages reference."""
    refs = staged_refs(pages);fields = {REF_FILES[kind][2] for kind in REF_FILES if refs[kind]}
    if refs['maps']:
        fields |= {MAPINFOS_FIELD, MAPS_FIELD}
    return fields


def graphic_names(pages):
    """Distinct character sheet names used by the pages' optional graphics (tolerant of malformed input)."""
    names = set()
    for page in pages if isinstance(pages, list) else []:
        graphic = page.get('graphic') if isinstance(page, dict) else None
        if isinstance(graphic, dict) and isinstance(graphic.get('character_name'), str):
            names.add(graphic['character_name'])
    return names


def chest_summary(pages):
    """Treasure-chest pages: a page whose top-level commands give gold/items/weapons/armors and then turn self switch L ON,
    followed by a later page conditioned on that self switch. Returns [{page, self_switch, gives, opened_page}]."""
    chests = []
    for number, page in enumerate(pages if isinstance(pages, list) else [], 1):
        ops = page.get('commands') if isinstance(page, dict) else None
        if not isinstance(ops, list):
            continue
        gives = [op for op in ops if isinstance(op, dict) and any(key in op for key in ('gold', 'item', 'weapon', 'armor'))
                 and (op.get('gold', op.get('amount', 0)) or 0) > 0]
        letters = [op['set_self_switch'] for op in ops if isinstance(op, dict) and op.get('set_self_switch') and op.get('value') is True]
        if not gives or not letters:
            continue
        opened = [later for later, other in enumerate(pages, 1) if later > number and isinstance(other, dict)
                  and isinstance(other.get('condition'), dict) and other['condition'].get('self_switch') == letters[0]]
        if opened:
            chests.append({'page': number, 'self_switch': letters[0], 'gives': gives, 'opened_page': opened[0]})
    return chests


def effective_priority(page):
    """Priority a staged page will have: its explicit option, else Same as Characters for a page with a character graphic or a touch trigger
    (the v1.30 / v1.25 defaults), else None (the template's own priority is kept)."""
    options = page.get('options') if isinstance(page.get('options'), dict) else {}
    if 'priority' in options:
        return options['priority']
    if page.get('graphic') or page.get('trigger') in TOUCH_TRIGGERS:
        return 'same'
    return None


def monster_summary(pages):
    """Map-monster pages: a page with a character graphic and a touch trigger whose top-level commands start a battle. `disappears` is true
    when the win branch turns a self switch ON that a later page tests. Returns [{page, troop, trigger, move, disappears, self_switch}]."""
    monsters = []
    for number, page in enumerate(pages if isinstance(pages, list) else [], 1):
        ops = page.get('commands') if isinstance(page, dict) else None
        if not isinstance(ops, list) or not page.get('graphic') or page.get('trigger') not in TOUCH_TRIGGERS:
            continue
        battles = [op for op in ops if isinstance(op, dict) and isinstance(op.get('battle'), int)]
        if not battles:
            continue
        battle = battles[0]
        letters = [op['set_self_switch'] for op in iter_ops(battle.get('win')) if op.get('set_self_switch') and op.get('value') is True]
        gone = [later for later, other in enumerate(pages, 1) if later > number and isinstance(other, dict) and letters
                and isinstance(other.get('condition'), dict) and other['condition'].get('self_switch') == letters[0]]
        move = page.get('move') if isinstance(page.get('move'), dict) else {}
        monsters.append({'page': number, 'troop': battle['battle'], 'trigger': page['trigger'], 'move': move.get('type', 'fixed'),
                         'disappears': bool(gone), 'self_switch': letters[0] if gone else None})
    return monsters


def describe_monster(monster, troop_name=None):
    """One human sentence for a monster_summary row."""
    kind = {'random': 'Wandering', 'approach': 'Chasing', 'custom': 'Patrolling'}.get(monster['move'], 'Stationary')
    troop = f'troop {monster["troop"]}' + (f' "{troop_name}"' if troop_name else '')
    end = f'disappears after victory (self switch {monster["self_switch"]})' if monster['disappears'] else 'stays after victory (the battle can start again)'
    return f'{kind} monster, battles {troop} on touch, {end}.'


def staged_ids(pages, switch_count, variable_count):
    """Every switch/variable id referenced by the pages (conditions, commands, nested branches) must exist in the native System."""
    def switch(value, label):
        if not 1 <= value <= switch_count - 1:
            raise ValueError(f'{label} {value} is outside the native System switches 1..{switch_count-1}')
    def variable(value, label):
        if not 1 <= value <= variable_count - 1:
            raise ValueError(f'{label} {value} is outside the native System variables 1..{variable_count-1}')
    for page in pages:
        condition = page['condition']
        for key in ('switch1', 'switch2'):
            if key in condition:switch(condition[key], 'condition ' + key)
        if 'variable' in condition:variable(condition['variable']['id'], 'condition variable')
        for op in iter_ops(page['commands']):
            if 'set_switch' in op:switch(op['set_switch'], 'set_switch')
            elif 'set_variable' in op:variable(op['set_variable'], 'set_variable')
            elif isinstance(op.get('if'), dict):
                if 'switch' in op['if']:switch(op['if']['switch'], 'if switch')
                elif 'variable' in op['if']:variable(op['if']['variable'], 'if variable')


# ------------------------------------------------------------------ native generation

def plain_rows(commands, indent=0):
    """Native (code, indent, parameters) tuples for a validated command list; strings stay python str."""
    rows = []
    for op in commands:
        if 'text' in op:
            rows.append((101, indent, ['', 0, 0, 2]));rows += [(401, indent, [line]) for line in op['text']]
        elif 'set_switch' in op:rows.append((121, indent, [op['set_switch'], op['set_switch'], 0 if op['value'] else 1]))
        elif 'set_variable' in op:rows.append((122, indent, [op['set_variable'], op['set_variable'], VARIABLE_OPS[op['op']], 0, op['value']]))
        elif 'set_self_switch' in op:rows.append((123, indent, [op['set_self_switch'], 0 if op['value'] else 1]))
        elif 'choices' in op:
            cancel = 0 if op['cancel'] is None else op['cancel'] + 1
            rows.append((102, indent, [list(op['choices']), cancel]))
            for number, (choice, branch) in enumerate(zip(op['choices'], op['branches'])):
                rows.append((402, indent, [number, choice]));rows += plain_rows(branch, indent + 1)
            rows.append((404, indent, []))
        elif 'if' in op:
            cond = op['if']
            if 'switch' in cond:params = [0, cond['switch'], 0 if cond['is'] else 1]
            elif 'variable' in cond:params = [1, cond['variable'], 0, cond['value'], CONDITION_OPS[cond['op']]]
            elif 'self_switch' in cond:params = [2, cond['self_switch'], 0 if cond['is'] else 1]
            elif 'gold_at_least' in cond:params = [7, cond['gold_at_least'], 0]
            else:params = [8, cond['has_item']]
            rows.append((111, indent, params));rows += plain_rows(op['then'], indent + 1)
            if 'else' in op:
                rows.append((411, indent, []));rows += plain_rows(op['else'], indent + 1)
            rows.append((412, indent, []))
        elif 'battle' in op:
            rows.append((301, indent, [0, op['battle'], op['can_escape'], op['can_lose']]))
            if op['can_escape'] or op['can_lose'] or 'win' in op:
                # Editor layout: 601 win block always, then 602 / 603 only for the enabled outcomes, then 604.
                rows.append((601, indent, []));rows += plain_rows(op.get('win', []), indent + 1)
                if op['can_escape']:
                    rows.append((602, indent, []));rows += plain_rows(op.get('escape', []), indent + 1)
                if op['can_lose']:
                    rows.append((603, indent, []));rows += plain_rows(op.get('lose', []), indent + 1)
                rows.append((604, indent, []))
        elif 'party' in op:rows.append((129, indent, [op['actor'], 0 if op['party'] == 'add' else 1, 1 if op['initialize'] else 0]))
        elif 'common_event' in op:rows.append((117, indent, [op['common_event']]))
        elif 'gold' in op:rows.append((125, indent, [0 if op['gold'] > 0 else 1, 0, abs(op['gold'])]))
        elif 'item' in op:rows.append((126, indent, [op['item'], 0 if op['amount'] > 0 else 1, 0, abs(op['amount'])]))
        # Weapons / armors: [id, gain 0 / lose 1, constant operand 0, amount, include_equipment]; the editor stores include_equipment false.
        elif 'weapon' in op:rows.append((127, indent, [op['weapon'], 0 if op['amount'] > 0 else 1, 0, abs(op['amount']), False]))
        elif 'armor' in op:rows.append((128, indent, [op['armor'], 0 if op['amount'] > 0 else 1, 0, abs(op['amount']), False]))
        elif 'transfer' in op:
            move = op['transfer'];rows.append((201, indent, [0, move['map_id'], move['x'], move['y'], move['direction'], move['fade']]))
        elif 'erase_event' in op:rows.append((214, indent, []))
        # Set Move Route: 205 [character id, RPG::MoveRoute] then one 505 [RPG::MoveCommand] per route command (the terminator has no line).
        elif 'move_route' in op:
            spec = op['move_route'];route = plain_route(spec['route'], spec.get('repeat', False), spec.get('skippable', False), spec.get('wait', True))
            rows.append((205, indent, [ROUTE_TARGETS[spec['target']], route]));rows += [(505, indent, [command]) for command in route.list[:-1]]
        else:rows.append((230, indent, [op['wait']]))
    return rows


def native_move_command(command):
    """A fresh RPG::MoveCommand (ivars code, parameters)."""
    from vxace_python_mutator import RubyObject
    return RubyObject('RPG::MoveCommand', {'@code': command.code, '@parameters': list(command.parameters)})


def native_route(route):
    """A fresh RPG::MoveRoute (ivars repeat, skippable, wait, list; commands code, parameters) from a PlainMoveRoute, as the editor saves it."""
    from vxace_python_mutator import RubyObject
    return RubyObject('RPG::MoveRoute', {'@repeat': route.repeat, '@skippable': route.skippable, '@wait': route.wait,
                                         '@list': [native_move_command(c) for c in route.list]})


def native_rows(commands, make_command, literal):
    """RPG::EventCommand objects (including the final terminator); strings (also inside the choices array) become native strings."""
    def convert(value):
        if isinstance(value, str):return literal(value)
        if isinstance(value, PlainMoveRoute):return native_route(value)
        if isinstance(value, PlainMoveCommand):return native_move_command(value)
        if isinstance(value, list):return [convert(v) for v in value]
        return value
    rows = [make_command(code, indent, convert(params)) for code, indent, params in plain_rows(commands)]
    return rows + [make_command(0, 0, [])]


def structure_check(rows):
    """Reuse the guarded-edit pairing checker: balanced blocks, matching indent, one final terminator."""
    from vxace_event_structure import validate_list
    validate_list(rows)


# ------------------------------------------------------------------ database / map references (read-only)

def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def load_native(project, relative):
    from vxace_index_query import unlinked
    from vxace_python_mutator import load
    if project is None:
        raise ValueError('Staged commands that reference the database need the native project')
    path = unlinked(Path(project) / 'Data' / relative)
    if not path.is_file():
        raise ValueError(f'Native Data/{relative} is required by the staged commands but is missing')
    return load(path)[0]


def load_array(project, kind):
    from vxace_python_mutator import RubyObject
    name, cls, _ = REF_FILES[kind];root = load_native(project, name + '.rvdata2')
    if not isinstance(root, list) or not 2 <= len(root) <= 5001 or root[0] is not None:
        raise ValueError(f'Native {name} must be an array with nil slot zero')
    for slot, entry in enumerate(root[1:], 1):
        if entry is not None and (not isinstance(entry, RubyObject) or entry.cls != cls or type(entry.get('id')) is not int or entry.get('id') != slot):
            raise ValueError(f'Native {name} entry {slot} is not a {cls} with its slot id')
    return root


def load_mapinfos(project):
    from vxace_python_mutator import RubyHash
    root = load_native(project, 'MapInfos.rvdata2')
    if not isinstance(root, RubyHash):
        raise ValueError('Native MapInfos hash required')
    return root


def load_map_size(project, map_id):
    from vxace_python_mutator import RubyObject
    root = load_native(project, f'Map{map_id:03d}.rvdata2')
    if not isinstance(root, RubyObject) or root.cls != 'RPG::Map' or type(root.get('width')) is not int or type(root.get('height')) is not int:
        raise ValueError(f'Native Map{map_id:03d} must be an RPG::Map with integer size')
    return root, root.get('width'), root.get('height')


def sha_text(value, label):
    import re
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError(label + ' must be a lowercase SHA-256')
    return value


def check_references(mutation, project):
    """Bind every referenced database to its expected hash and require each referenced id to exist."""
    pages = mutation['pages'];refs = staged_refs(pages)
    for kind, (name, _, field) in REF_FILES.items():
        if not refs[kind]:
            continue
        root = load_array(project, kind)
        if sha_text(mutation[field], field) != digest(root):
            raise ValueError(f'Native {name} is stale')
        for number in sorted(refs[kind]):
            if not 1 <= number < len(root) or root[number] is None:
                raise ValueError(f'{kind} id {number} does not exist in native {name}')
    if refs['maps']:
        infos = load_mapinfos(project)
        if sha_text(mutation[MAPINFOS_FIELD], MAPINFOS_FIELD) != digest(infos):
            raise ValueError('Native MapInfos is stale')
        wanted = mutation[MAPS_FIELD]
        if not isinstance(wanted, dict) or set(wanted) != {str(m) for m in refs['maps']}:
            raise ValueError(MAPS_FIELD + ' must hold exactly one hash per transfer destination map')
        known = {key for key, _ in infos.pairs}
        sizes = {}
        for number in sorted(refs['maps']):
            if number not in known:
                raise ValueError(f'Transfer map {number} does not exist in MapInfos')
            root, width, height = load_map_size(project, number)
            if sha_text(wanted[str(number)], MAPS_FIELD + ' entry') != digest(root):
                raise ValueError(f'Native Map{number:03d} is stale')
            sizes[number] = (width, height)
        for op in page_ops(pages):
            if 'transfer' in op:
                move = op['transfer'];width, height = sizes[move['map_id']]
                if move['x'] >= width or move['y'] >= height:
                    raise ValueError(f'Transfer target ({move["x"]},{move["y"]}) lies outside map {move["map_id"]} ({width}x{height})')


def reference_snapshot(project, transfer_maps=()):
    """Read-only evidence for the snapshot: current hashes of every database a staged command may reference."""
    result = {}
    for kind, (name, _, _) in REF_FILES.items():
        try:root = load_array(project, kind)
        except ValueError:result[kind + '_sha256'] = None;continue
        result[kind + '_sha256'] = digest(root);result[kind + '_count'] = len(root) - 1
    try:result['mapinfos_sha256'] = digest(load_mapinfos(project))
    except ValueError:result['mapinfos_sha256'] = None
    maps = {}
    for number in transfer_maps:
        root, width, height = load_map_size(project, number)
        maps[str(number)] = {'sha256': digest(root), 'width': width, 'height': height}
    result['destination_maps'] = maps
    return result


def bind_fields(pages, snapshot):
    """Mutation hash fields for a recipe step, taken only from the snapshot and only for what the pages reference."""
    refs = staged_refs(pages);fields = {}
    for kind, (_, _, field) in REF_FILES.items():
        if refs[kind]:
            if snapshot.get(kind + '_sha256') is None:
                raise ValueError(f'snapshot has no {kind} hash')
            fields[field] = snapshot[kind + '_sha256']
    if refs['maps']:
        if snapshot.get('mapinfos_sha256') is None:
            raise ValueError('snapshot has no MapInfos hash')
        maps = snapshot.get('destination_maps', {})
        if set(maps) != {str(m) for m in refs['maps']}:
            raise ValueError('snapshot lacks the transfer destination maps')
        fields[MAPINFOS_FIELD] = snapshot['mapinfos_sha256'];fields[MAPS_FIELD] = {key: maps[key]['sha256'] for key in sorted(maps, key=int)}
    return fields


def index_check(read, pages):
    """Impact-time existence check of the referenced ids against the fresh index (`read(relative)` returns indexed JSON)."""
    refs = staged_refs(pages)
    files = {'troops': 'database/troops.json', 'actors': 'database/actors.json', 'common_events': 'database/common-events.json', 'items': 'database/items.json',
             'weapons': 'database/weapons.json', 'armors': 'database/armors.json'}
    for kind, relative in files.items():
        if not refs[kind]:
            continue
        try:rows = read(relative)
        except Exception:raise ValueError(f'Indexed {relative} is required to check the {kind} referenced by the staged commands')
        for number in sorted(refs[kind]):
            if not isinstance(rows, list) or not 1 <= number < len(rows) or rows[number] is None:
                raise ValueError(f'{kind} id {number} is absent from the indexed {relative}')
    if refs['maps']:
        infos = read('database/map-infos.json')
        sizes = {}
        for number in sorted(refs['maps']):
            if not isinstance(infos, dict) or str(number) not in infos:
                raise ValueError(f'Transfer map {number} is absent from the indexed MapInfos')
            native = read(f'maps/map-{number:03d}.json')
            if not isinstance(native, dict) or type(native.get('width')) is not int or type(native.get('height')) is not int:
                raise ValueError(f'Indexed map {number} has no size')
            sizes[number] = (native['width'], native['height'])
        for op in page_ops(pages):
            if 'transfer' in op:
                move = op['transfer'];width, height = sizes[move['map_id']]
                if move['x'] >= width or move['y'] >= height:
                    raise ValueError(f'Transfer target ({move["x"]},{move["y"]}) lies outside map {move["map_id"]}')
