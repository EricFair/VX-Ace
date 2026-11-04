#!/usr/bin/env python3
"""Run a recipe: a list of high-level steps, each applied as its own guarded single-change transaction, either on a chain of disposable copies
(default) or, with --in-place, directly in a designated project (one start backup, undo record).

Adds no mutation logic. Every step runs the existing Project Reader, the operation's read-only snapshot CLI, builds the exact spec
from that snapshot, then runs the patch planner, impact report and the Python copy patcher. The original project is never written."""
from __future__ import annotations
import argparse
import copy as copymod
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from vxace_copy_patcher import current_inventory
from vxace_database_append import LIST_TABLES, DROP_TABLES, ref_field, required_refs
from vxace_index_query import unlinked
import vxace_adopt as adopt

VERSION = '1.30.0'
ROOT = Path(__file__).resolve().parent
STEP_TIMEOUT = 1800
MAX_STEPS = 50
TABLES = ('actors', 'classes', 'enemies', 'items', 'skills', 'states', 'weapons', 'armors', 'troops')
STEP_KEYS = {
    'append_entry': ({'type', 'table', 'template_id', 'overrides'}, {'type', 'table', 'template_id', 'overrides'}),
    'append_key_item': ({'type', 'template_item', 'name', 'description'}, {'type', 'template_item', 'name', 'description'}),
    'append_learning': ({'type', 'class_id', 'skill_id', 'level'}, {'type', 'class_id', 'skill_id', 'level'}),
    'append_encounter': ({'type', 'map_id', 'troop_id', 'weight'}, {'type', 'map_id', 'troop_id', 'weight', 'region_ids', 'encounter_step'}),
    'append_dialogue_event': ({'type', 'map_id', 'template_event', 'x', 'y', 'name', 'lines'}, {'type', 'map_id', 'template_event', 'x', 'y', 'name', 'lines'}),
    'append_staged_event': ({'type', 'map_id', 'template_event', 'x', 'y', 'name', 'pages'}, {'type', 'map_id', 'template_event', 'x', 'y', 'name', 'pages'}),
    'append_common_event': ({'type', 'name', 'trigger', 'commands'}, {'type', 'name', 'trigger', 'commands', 'switch_id'}),
    'append_blank_event': ({'type', 'map_id', 'donor_event', 'x', 'y'}, {'type', 'map_id', 'donor_event', 'x', 'y', 'name', 'donor_map_id'}),
    'append_blank_map': ({'type', 'template_map_id', 'name'}, {'type', 'template_map_id', 'name', 'width', 'height', 'tileset_id', 'parent_id', 'fill_floor'}),
    'add_area': ({'type', 'template_map_id', 'name', 'door', 'arrival', 'return_door', 'back_to'},
                 {'type', 'template_map_id', 'name', 'door', 'arrival', 'return_door', 'back_to', 'width', 'height', 'tileset_id', 'parent_id', 'fill_floor', 'donor_event'}),
    'add_treasure_chest': ({'type', 'map_id', 'x', 'y', 'name', 'contents'},
                           {'type', 'map_id', 'x', 'y', 'name', 'contents', 'graphic', 'template_event', 'donor_event', 'blank_x', 'blank_y'}),
    'add_touch_trigger': ({'type', 'map_id', 'x', 'y', 'name', 'commands'},
                          {'type', 'map_id', 'x', 'y', 'name', 'commands', 'repeatable', 'template_event', 'donor_event', 'blank_x', 'blank_y'}),
    'add_monster': ({'type', 'map_id', 'x', 'y', 'name', 'troop', 'graphic'},
                    {'type', 'map_id', 'x', 'y', 'name', 'troop', 'graphic', 'move', 'can_escape', 'can_lose', 'intro_text', 'win', 'escape', 'lose', 'condition', 'respawn',
                     'template_event', 'donor_event', 'blank_x', 'blank_y'}),
    'add_shop': ({'type', 'map_id', 'event_id', 'goods', 'purchase_only'}, {'type', 'map_id', 'event_id', 'goods', 'purchase_only'}),
    'insert_script': ({'type', 'name', 'source_file'}, {'type', 'name', 'source_file'}),
    'set_map_display_name': ({'type', 'map_id', 'name'}, {'type', 'map_id', 'name'}),
    'text_import': ({'type', 'csv'}, {'type', 'csv', 'allow_shorter'}),
    'set_system_fields': ({'type'}, {'type', 'game_title', 'currency_unit', 'party_members', 'start', 'terms'}),
}


class RecipeError(ValueError):
    pass


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def is_int(value):
    return type(value) is int


def is_ref(value):
    return isinstance(value, dict) and 'from_step' in value


# ---------------------------------------------------------------- validation

def check_ref(value, number, steps, want_table, where):
    """A reference is exactly {"from_step": k} with k an earlier step that created an id of the wanted table."""
    if set(value) != {'from_step'} or not is_int(value['from_step']):
        raise RecipeError(f'step {number}: {where} reference must be exactly {{"from_step": N}}')
    k = value['from_step']
    if not 1 <= k < number:
        raise RecipeError(f'step {number}: {where} from_step {k} must refer to an earlier step')
    earlier = steps[k - 1]
    if want_table == 'maps':
        if earlier.get('type') not in MAP_STEPS:
            raise RecipeError(f'step {number}: {where} from_step {k} must be an append_blank_map or add_area step')
        return
    if want_table == 'common_events':
        if earlier.get('type') != 'append_common_event':
            raise RecipeError(f'step {number}: {where} from_step {k} must be an append_common_event step')
        return
    if earlier.get('type') != 'append_entry' or earlier.get('table') != want_table:
        raise RecipeError(f'step {number}: {where} from_step {k} must be an append_entry step on table {want_table}')


GOODS_TABLE = {'weapon': ('append_entry', 'weapons'), 'armor': ('append_entry', 'armors'), 'item': ('append_key_item', None)}
# Database ids inside an effects / features override may be {"from_step": k}: code -> table the referenced step must have appended to.
EFFECT_REF_TABLE = {21: 'states', 22: 'states', 43: 'skills', 44: 'common_events'}
FEATURE_REF_TABLE = {13: 'states', 14: 'states', 32: 'states', 43: 'skills'}


MAP_STEPS = ('append_blank_map', 'add_area')


def check_map_id(value, number, steps, where='map_id'):
    """A map id is an integer 1..999 or {"from_step": k} naming an earlier append_blank_map / add_area step (the id that step will create)."""
    if is_ref(value):
        check_ref(value, number, steps, 'maps', where)
    elif not is_int(value) or not 1 <= value <= 999:
        raise RecipeError(f'step {number}: {where} must be an integer 1..999 or {{"from_step": N}} of an append_blank_map / add_area step')


def strip_map_ref(step):
    """Shallow copy with a map_id reference replaced by 0 (map references are validated by check_map_id)."""
    return {**step, 'map_id': 0} if is_ref(step.get('map_id')) else step


def check_goods_ref(value, number, steps, goods_type):
    """A goods reference must name an earlier step that appends an entry of the same goods type (items via append_key_item)."""
    if set(value) != {'from_step'} or not is_int(value['from_step']):
        raise RecipeError(f'step {number}: goods id reference must be exactly {{"from_step": N}}')
    k = value['from_step']
    if not 1 <= k < number:
        raise RecipeError(f'step {number}: goods id from_step {k} must refer to an earlier step')
    kind, table = GOODS_TABLE[goods_type]
    earlier = steps[k - 1]
    if goods_type == 'item' and earlier.get('type') == 'append_entry' and earlier.get('table') == 'items':
        return
    if earlier.get('type') != kind or (table is not None and earlier.get('table') != table):
        raise RecipeError(f'step {number}: goods id from_step {k} must be an {kind} step'
                          + (f' on table {table}' if table else '') + f' for a {goods_type}'
                          + (' (or an append_entry step on table items)' if goods_type == 'item' else ''))


def check_event_ref(value, number, steps, map_id):
    if set(value) != {'from_step'} or not is_int(value['from_step']):
        raise RecipeError(f'step {number}: event_id reference must be exactly {{"from_step": N}}')
    k = value['from_step']
    if not 1 <= k < number:
        raise RecipeError(f'step {number}: event_id from_step {k} must refer to an earlier step')
    earlier = steps[k - 1]
    if earlier.get('type') != 'append_dialogue_event':
        raise RecipeError(f'step {number}: event_id from_step {k} must be an append_dialogue_event step')
    if earlier.get('map_id') != map_id:
        raise RecipeError(f'step {number}: event_id from_step {k} creates its event on a different map')


def check_template_ref(value, number, steps, map_id):
    if set(value) != {'from_step'} or not is_int(value['from_step']):
        raise RecipeError(f'step {number}: template_event reference must be exactly {{"from_step": N}}')
    k = value['from_step']
    if not 1 <= k < number:
        raise RecipeError(f'step {number}: template_event from_step {k} must refer to an earlier step')
    earlier = steps[k - 1]
    if earlier.get('type') != 'append_blank_event':
        raise RecipeError(f'step {number}: template_event from_step {k} must be an append_blank_event step')
    if earlier.get('map_id') != map_id:
        raise RecipeError(f'step {number}: template_event from_step {k} creates its event on a different map')


def strip_refs(value):
    """Return a deep copy in which every reference dict is replaced by 0 (used to find stray references)."""
    if is_ref(value):
        return 0
    if isinstance(value, dict):
        return {k: strip_refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [strip_refs(v) for v in value]
    return value


def contains_ref_key(value):
    if isinstance(value, dict):
        return 'from_step' in value or any(contains_ref_key(v) for v in value.values())
    if isinstance(value, list):
        return any(contains_ref_key(v) for v in value)
    return False


def shadow_command_refs(ops, number, steps):
    """Check every allowed {"from_step": k} in staged commands (battle troop, item / has_item id, common_event id) and replace it with 0."""
    for op in ops:
        if is_ref(op.get('battle')):
            check_ref(op['battle'], number, steps, 'troops', 'battle troop_id')
            op['battle'] = 0
        if isinstance(op.get('transfer'), dict) and is_ref(op['transfer'].get('map_id')):
            check_ref(op['transfer']['map_id'], number, steps, 'maps', 'transfer map_id')
            op['transfer']['map_id'] = 0
        if is_ref(op.get('common_event')):
            check_ref(op['common_event'], number, steps, 'common_events', 'common_event id')
            op['common_event'] = 0
        if 'party' in op and is_ref(op.get('actor')):
            check_ref(op['actor'], number, steps, 'actors', 'party actor')
            op['actor'] = 0
        for holder, key, goods in ((op, 'item', 'item'), (op['if'] if isinstance(op.get('if'), dict) else {}, 'has_item', 'item'),
                                   (op, 'weapon', 'weapon'), (op, 'armor', 'armor')):
            if is_ref(holder.get(key)):
                check_goods_ref(holder[key], number, steps, goods)
                holder[key] = 0


CHEST_KINDS = ('item', 'weapon', 'armor')
CHEST_GRAPHIC = {'character_name': '!Chest', 'character_index': 0, 'direction': 2, 'pattern': 0}
CHEST_OPTIONS = {'direction_fix': True, 'walk_anime': False, 'priority': 'same'}
CHEST_TABLES = {'item': 'items', 'weapon': 'weapons', 'armor': 'armors'}


def validate_placement(step, number, steps):
    """Shared rules of the event macros: map, cell, unique name and exactly one template source (existing/from_step blank event, or a donor for a new one)."""
    check_map_id(step['map_id'], number, steps)
    for key in ('x', 'y'):
        if not is_int(step[key]) or not 0 <= step[key] <= 9999:
            raise RecipeError(f'step {number}: {key} must be a non-negative integer')
    if not isinstance(step['name'], str) or not 1 <= len(step['name']) <= 100:
        raise RecipeError(f'step {number}: name must be a string of 1..100 characters')
    if ('template_event' in step) == ('donor_event' in step):
        raise RecipeError(f'step {number}: give exactly one of template_event (an existing blank event, or {{"from_step": N}}) and donor_event (a schema donor for a new blank event)')
    if 'donor_event' in step and (not is_int(step['donor_event']) or not 1 <= step['donor_event'] <= 999):
        raise RecipeError(f'step {number}: donor_event must be an integer 1..999')
    if ('donor_event' in step) != ('blank_x' in step) or ('blank_x' in step) != ('blank_y' in step):
        raise RecipeError(f'step {number}: donor_event needs blank_x and blank_y (the free cell for the blank template event that stays on the map); they are not allowed otherwise')
    for key in ('blank_x', 'blank_y'):
        if key in step and (not is_int(step[key]) or not 0 <= step[key] <= 9999):
            raise RecipeError(f'step {number}: {key} must be a non-negative integer')
    if 'template_event' in step:
        if is_ref(step['template_event']):
            check_template_ref(step['template_event'], number, steps, step['map_id'])
        elif not is_int(step['template_event']) or not 1 <= step['template_event'] <= 999:
            raise RecipeError(f'step {number}: template_event must be an integer 1..999 or {{"from_step": N}}')


def validate_chest(step, number, steps):
    """Structural rules of the add_treasure_chest macro (the guarded tools re-check everything it expands to)."""
    validate_placement(step, number, steps)
    contents = step['contents']
    if not isinstance(contents, dict):
        raise RecipeError(f'step {number}: contents must be {{"gold": n}} or {{"item"|"weapon"|"armor": id, "amount": n}}')
    if set(contents) == {'gold'}:
        if not is_int(contents['gold']) or not 1 <= contents['gold'] <= 99999999:
            raise RecipeError(f'step {number}: contents gold must be an integer 1..99999999')
    else:
        kinds = [kind for kind in CHEST_KINDS if kind in contents]
        if len(kinds) != 1 or set(contents) != {kinds[0], 'amount'}:
            raise RecipeError(f'step {number}: contents must be {{"gold": n}} or exactly one of item/weapon/armor with amount')
        kind = kinds[0]
        if is_ref(contents[kind]):
            check_goods_ref(contents[kind], number, steps, kind)
        elif not is_int(contents[kind]) or not 1 <= contents[kind] <= 999:
            raise RecipeError(f'step {number}: contents {kind} id must be an integer 1..999 or {{"from_step": N}}')
        if not is_int(contents['amount']) or not 1 <= contents['amount'] <= 99:
            raise RecipeError(f'step {number}: contents amount must be an integer 1..99')
    if 'graphic' in step:
        from vxace_character_graphics import graphic_schema
        try:
            graphic_schema(step['graphic'])
        except ValueError as error:
            raise RecipeError(f'step {number}: graphic: {error}')
    shadow = strip_map_ref(copymod.deepcopy(step))
    if is_ref(shadow.get('template_event')):
        shadow['template_event'] = 0
    for kind in CHEST_KINDS:
        if is_ref(shadow['contents'].get(kind)):
            shadow['contents'][kind] = 0
    if contains_ref_key(shadow):
        raise RecipeError(f'step {number}: from_step is only allowed for template_event and the contents id')


def validate_touch_trigger(step, number, steps):
    """Structural rules of the add_touch_trigger macro: placement plus 1..40 commands (39 when the self-switch command is appended)."""
    validate_placement(step, number, steps)
    if 'repeatable' in step and type(step['repeatable']) is not bool:
        raise RecipeError(f'step {number}: repeatable must be a boolean')
    limit = 40 if step.get('repeatable') else 39
    if not isinstance(step['commands'], list) or not 1 <= len(step['commands']) <= limit:
        raise RecipeError(f'step {number}: commands must be a list of 1..{limit} operations' + ('' if step.get('repeatable') else ' (one more is added to turn self switch A ON)'))
    from vxace_staged_commands import iter_ops
    shadow = copymod.deepcopy(step['commands'])
    shadow_command_refs(iter_ops(shadow), number, steps)
    if contains_ref_key({**{k: v for k, v in step.items() if k not in ('template_event', 'commands', 'map_id')}, 'commands': shadow}):
        raise RecipeError(f'step {number}: from_step is only allowed for map_id, template_event, battle troop ids, item/weapon/armor ids, transfer maps and common event ids in commands')


MONSTER_MOVE = {'type': 'random', 'speed': 3, 'frequency': 3}


def validate_monster(step, number, steps):
    """Structural rules of the add_monster macro: placement, a troop, a character graphic and the optional move / battle options / branches / condition.
    The expansion is built with a stand-in troop id and checked with the staged-event page validator, so every page rule applies here too."""
    from vxace_map_events import staged_shape, page_move_shape
    from vxace_staged_commands import body, check_text, iter_ops
    validate_placement(step, number, steps)
    if is_ref(step['troop']):
        check_ref(step['troop'], number, steps, 'troops', 'troop')
    elif not is_int(step['troop']) or step['troop'] < 1:
        raise RecipeError(f'step {number}: troop must be a positive integer or {{"from_step": N}} of a troops append_entry step')
    from vxace_character_graphics import graphic_schema
    try:
        graphic_schema(step['graphic'])
    except ValueError as error:
        raise RecipeError(f'step {number}: graphic: {error}')
    for key in ('can_escape', 'can_lose', 'respawn'):
        if key in step and type(step[key]) is not bool:
            raise RecipeError(f'step {number}: {key} must be a boolean')
    if 'move' in step:
        try:
            page_move_shape(step['move'])
        except ValueError as error:
            raise RecipeError(f'step {number}: move: {error}')
    if 'intro_text' in step:
        lines = step['intro_text']
        if not isinstance(lines, list) or not 1 <= len(lines) <= 4:
            raise RecipeError(f'step {number}: intro_text must be a list of 1..4 literal lines')
        try:
            if not any([check_text(line, 'intro text line', 500, True) for line in lines]):
                raise ValueError('intro text must contain text')
        except ValueError as error:
            raise RecipeError(f'step {number}: intro_text: {error}')
    if 'escape' in step and not step.get('can_escape', True):
        raise RecipeError(f'step {number}: an escape branch needs can_escape true')
    if 'lose' in step and not step.get('can_lose', False):
        raise RecipeError(f'step {number}: a lose branch needs can_lose true (without can_lose a defeat is Game Over)')
    limit = 40 if step.get('respawn') else 39
    for key in ('win', 'escape', 'lose'):
        if key in step:
            if not isinstance(step[key], list):
                raise RecipeError(f'step {number}: {key} must be a list of commands')
            if key == 'win' and len(step['win']) > limit:
                raise RecipeError(f'step {number}: win may hold at most {limit} commands' + ('' if step.get('respawn') else ' (one more is added to turn self switch A ON)'))
            try:
                body(step[key], 1, f'battle {key} branch', 0)
            except ValueError as error:
                raise RecipeError(f'step {number}: {key}: {error}')
    condition = step.get('condition', {})
    if isinstance(condition, dict) and condition.get('self_switch') == 'A':
        raise RecipeError(f'step {number}: condition may not test self switch A (the macro uses it for the defeated page)')
    shadow = strip_map_ref(copymod.deepcopy(step))
    if is_ref(shadow.get('template_event')):
        shadow['template_event'] = 0
    if is_ref(shadow['troop']):
        shadow['troop'] = 1
    holder = {key: shadow[key] for key in ('win', 'escape', 'lose') if key in shadow}
    shadow_command_refs(iter_ops([{'battle_holder': 1, **holder}]), number, steps)
    if contains_ref_key(shadow):
        raise RecipeError(f'step {number}: from_step is only allowed for map_id, template_event, troop and ids inside win / escape / lose')
    try:
        staged_shape(expand_monster(shadow, None)[1]['pages'])
    except ValueError as error:
        raise RecipeError(f'step {number}: {error}')


BLANK_MAP_LIMITS = {'width': (17, 500), 'height': (13, 500), 'tileset_id': (1, 999), 'parent_id': (0, 999), 'fill_floor': (0, 127)}
AREA_TRIGGERS = ('player_touch', 'action')
DIRECTIONS = (0, 2, 4, 6, 8)


def validate_blank_map(step, number):
    """Structural rules of append_blank_map (the guarded map tool re-checks everything against the native files)."""
    if not is_int(step['template_map_id']) or not 1 <= step['template_map_id'] <= 999:
        raise RecipeError(f'step {number}: template_map_id must be an integer 1..999')
    if not isinstance(step['name'], str) or not 1 <= len(step['name']) <= 100:
        raise RecipeError(f'step {number}: name must be a string of 1..100 characters')
    for key, (low, high) in BLANK_MAP_LIMITS.items():
        if key in step and (not is_int(step[key]) or not low <= step[key] <= high):
            raise RecipeError(f'step {number}: {key} must be an integer {low}..{high}')


def cell_of(value, number, where, extra=()):
    if not isinstance(value, dict) or not {'x', 'y'} <= set(value):
        raise RecipeError(f'step {number}: {where} must be an object with x and y')
    for key in ('x', 'y'):
        if not is_int(value[key]) or not 0 <= value[key] <= 9999:
            raise RecipeError(f'step {number}: {where} {key} must be a non-negative integer')
    return value


def facing_of(value, number, where):
    cell_of(value, number, where)
    if set(value) != {'x', 'y', 'direction'} or not is_int(value['direction']) or value['direction'] not in DIRECTIONS:
        raise RecipeError(f'step {number}: {where} must be exactly x, y and direction (0 keep, 2 down, 4 left, 6 right, 8 up)')


def door_trigger(door):
    """Effective trigger of an add_area door: the explicit one, else action for a door with a graphic (solid, same priority) and player_touch for a plain floor door."""
    return door.get('trigger') or ('action' if door.get('graphic') else 'player_touch')


def validate_door(value, number, where, allowed):
    cell_of(value, number, where)
    unknown = set(value) - allowed
    if unknown:
        raise RecipeError(f'step {number}: {where} has unknown keys {sorted(unknown)}')
    if 'trigger' in value and (not isinstance(value['trigger'], str) or value['trigger'] not in AREA_TRIGGERS):
        raise RecipeError(f'step {number}: {where} trigger must be "player_touch" (default) or "action"')
    if 'name' in value and (not isinstance(value['name'], str) or not 1 <= len(value['name']) <= 100):
        raise RecipeError(f'step {number}: {where} name must be a string of 1..100 characters')
    if 'graphic' in value:
        from vxace_character_graphics import graphic_schema
        try:
            graphic_schema(value['graphic'])
        except ValueError as error:
            raise RecipeError(f'step {number}: {where} graphic: {error}')
    if ('blank_x' in value) != ('blank_y' in value):
        raise RecipeError(f'step {number}: {where} needs blank_x and blank_y together')
    for key in ('blank_x', 'blank_y'):
        if key in value and (not is_int(value[key]) or not 0 <= value[key] <= 9999):
            raise RecipeError(f'step {number}: {where} {key} must be a non-negative integer')


def validate_area(step, number, steps):
    """Structural rules of the add_area macro: a new blank map, a door on a source map and a return door on the new map."""
    validate_blank_map({**step, 'template_map_id': step['template_map_id']}, number)
    door, ret = step['door'], step['return_door']
    if not isinstance(door, dict) or 'map_id' not in door:
        raise RecipeError(f'step {number}: door must be an object with map_id, x and y')
    check_map_id(door['map_id'], number, steps, 'door map_id')
    validate_door(door, number, 'door', {'map_id', 'x', 'y', 'template_event', 'blank_x', 'blank_y', 'trigger', 'graphic', 'name', 'condition', 'locked_text'})
    shadow_condition = None
    if 'condition' in door:
        from vxace_staged_commands import condition_shape
        if not isinstance(door['condition'], dict):
            raise RecipeError(f'step {number}: door condition must be an object')
        shadow_condition = {'if': copymod.deepcopy(door['condition'])}
        shadow_command_refs([shadow_condition], number, steps)
        stand_in = {key: (1 if key == 'has_item' and value == 0 and is_ref(door['condition'].get(key)) else value) for key, value in shadow_condition['if'].items()}
        try:
            condition_shape(stand_in)
        except ValueError as error:
            raise RecipeError(f'step {number}: door condition: {error}')
        if 'self_switch' in door['condition']:
            raise RecipeError(f'step {number}: door condition cannot test a self switch (a door has no self switch state)')
    if 'locked_text' in door:
        from vxace_staged_commands import check_text
        lines = door['locked_text']
        if 'condition' not in door:
            raise RecipeError(f'step {number}: door locked_text needs a door condition')
        if not isinstance(lines, list) or not 1 <= len(lines) <= 4:
            raise RecipeError(f'step {number}: door locked_text must be a list of 1..4 literal lines')
        try:
            if not any([check_text(line, 'locked text line', 500, True) for line in lines]):
                raise ValueError('locked text must contain text')
        except ValueError as error:
            raise RecipeError(f'step {number}: door locked_text: {error}')
    validate_door(ret, number, 'return_door', {'x', 'y', 'blank_x', 'blank_y', 'trigger', 'graphic', 'name'})
    facing_of(step['arrival'], number, 'arrival')
    facing_of(step['back_to'], number, 'back_to')
    if 'donor_event' in step and (not is_int(step['donor_event']) or not 1 <= step['donor_event'] <= 999):
        raise RecipeError(f'step {number}: donor_event must be an integer 1..999')
    if 'template_event' in door:
        if 'blank_x' in door:
            raise RecipeError(f'step {number}: door blank_x / blank_y are only for a door built from donor_event, not with template_event')
        if is_ref(door['template_event']):
            check_template_ref(door['template_event'], number, steps, door['map_id'])
        elif not is_int(door['template_event']) or not 1 <= door['template_event'] <= 999:
            raise RecipeError(f'step {number}: door template_event must be an integer 1..999 or {{"from_step": N}}')
    elif 'donor_event' not in step or 'blank_x' not in door:
        raise RecipeError(f'step {number}: give door template_event (an existing blank event), or donor_event with door blank_x and blank_y (the free cell for the blank template event that stays on the door map)')
    # A touch door that sends the player back onto its own cell (or a touch return door that receives the player on its cell) would bounce forever.
    if door_trigger(door) == 'player_touch' and (step['back_to']['x'], step['back_to']['y']) == (door['x'], door['y']):
        raise RecipeError(f'step {number}: back_to is the door cell: a player_touch door would bounce the player straight back into the new area')
    if door_trigger(ret) == 'player_touch' and (step['arrival']['x'], step['arrival']['y']) == (ret['x'], ret['y']):
        raise RecipeError(f'step {number}: arrival is the return_door cell: a player_touch return door would bounce the player straight back out')
    for key, (cx, cy) in (('arrival', (step['arrival']['x'], step['arrival']['y'])), ('return_door', (ret['x'], ret['y']))):
        for axis, size in (('x', cx), ('y', cy)):
            limit = step.get('width' if axis == 'x' else 'height')
            if limit is not None and size >= limit:
                raise RecipeError(f'step {number}: {key} {axis} {size} lies outside the new {limit}-wide/high map')
    checked_door = {k: v for k, v in door.items() if k not in ('map_id', 'template_event', 'condition')}
    if shadow_condition is not None:
        checked_door['condition'] = shadow_condition['if']
    if contains_ref_key({**step, 'door': checked_door}):
        raise RecipeError(f'step {number}: from_step is only allowed for door map_id, door template_event and a has_item id in the door condition')


def validate_recipe(recipe):
    """Strict structural validation. Operation-level rules (ranges, whitelists) stay with the existing guarded tools."""
    if not isinstance(recipe, dict) or set(recipe) - {'title', 'steps'} or 'steps' not in recipe:
        raise RecipeError('recipe must be an object with only "title" and "steps"')
    if 'title' in recipe and (not isinstance(recipe['title'], str) or not 1 <= len(recipe['title']) <= 200):
        raise RecipeError('title must be a string of 1..200 characters')
    steps = recipe['steps']
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise RecipeError(f'steps must be a list of 1..{MAX_STEPS} steps')
    for number, step in enumerate(steps, 1):
        if not isinstance(step, dict) or step.get('type') not in STEP_KEYS:
            raise RecipeError(f'step {number}: unknown or missing type (known: {", ".join(STEP_KEYS)})')
        required, allowed = STEP_KEYS[step['type']]
        unknown = set(step) - allowed
        if unknown:
            raise RecipeError(f'step {number}: unknown keys {sorted(unknown)}')
        missing = required - set(step)
        if missing:
            raise RecipeError(f'step {number}: missing keys {sorted(missing)}')
        kind = step['type']
        if kind == 'append_entry':
            if step['table'] not in TABLES:
                raise RecipeError(f'step {number}: table must be one of {", ".join(TABLES)}')
            if not is_int(step['template_id']) or step['template_id'] < 1:
                raise RecipeError(f'step {number}: template_id must be a positive integer')
            if not isinstance(step['overrides'], dict):
                raise RecipeError(f'step {number}: overrides must be an object')
            shadow = copymod.deepcopy(step['overrides'])
            members = shadow.get('members')
            if step['table'] == 'troops' and isinstance(members, list):
                for member in members:
                    if isinstance(member, dict) and is_ref(member.get('enemy_id')):
                        check_ref(member['enemy_id'], number, steps, 'enemies', 'members enemy_id')
                        member['enemy_id'] = 0
            equips = shadow.get('equips')
            if step['table'] == 'actors' and isinstance(equips, list):
                for slot, item in enumerate(equips):
                    if is_ref(item):
                        check_goods_ref(item, number, steps, 'weapon' if slot == 0 else 'armor')
                        equips[slot] = 0
            if step['table'] == 'actors' and is_ref(shadow.get('class_id')):
                check_ref(shadow['class_id'], number, steps, 'classes', 'class_id')
                shadow['class_id'] = 0
            if step['table'] == 'classes':
                learned = shadow.get('learnings')
                for row in learned if isinstance(learned, list) else []:
                    if isinstance(row, dict) and is_ref(row.get('skill_id')):
                        check_ref(row['skill_id'], number, steps, 'skills', 'learnings skill_id')
                        row['skill_id'] = 0
                curves = shadow.get('params')
                if isinstance(curves, dict) and is_ref(curves.get('copy_from_class')):
                    check_ref(curves['copy_from_class'], number, steps, 'classes', 'params copy_from_class')
                    curves['copy_from_class'] = 0
            for key, rules in (('effects', EFFECT_REF_TABLE), ('features', FEATURE_REF_TABLE)):
                rows = shadow.get(key)
                if step['table'] in LIST_TABLES[key] and isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, dict) and is_ref(row.get('data_id')):
                            want = rules.get(row.get('code')) if is_int(row.get('code')) else None
                            if want is None:
                                raise RecipeError(f'step {number}: {key} data_id from_step is only allowed for codes {sorted(rules)}')
                            check_ref(row['data_id'], number, steps, want, f'{key} data_id (code {row["code"]})')
                            row['data_id'] = 0
            if step['table'] == 'enemies':
                actions = shadow.get('actions')
                for row in actions if isinstance(actions, list) else []:
                    if isinstance(row, dict) and is_ref(row.get('skill_id')):
                        check_ref(row['skill_id'], number, steps, 'skills', 'actions skill_id')
                        row['skill_id'] = 0
                drops = shadow.get('drop_items')
                for slot in drops if isinstance(drops, list) else []:
                    if isinstance(slot, dict) and is_ref(slot.get('id')):
                        drop_kind = slot.get('kind')
                        want = DROP_TABLES.get(drop_kind) if isinstance(drop_kind, str) else None
                        if want is None:
                            raise RecipeError(f'step {number}: drop_items id from_step needs kind item, weapon or armor')
                        check_ref(slot['id'], number, steps, want, f'drop_items id (kind {drop_kind})')
                        slot['id'] = 0
            if contains_ref_key(shadow):
                raise RecipeError(f'step {number}: from_step is only allowed for troop members enemy_id, actor equips and class_id, class learnings skill_id and params copy_from_class, effects/features data_id, enemy action skill_id and enemy drop item id')
        elif kind == 'append_key_item':
            if not is_int(step['template_item']) or step['template_item'] < 1:
                raise RecipeError(f'step {number}: template_item must be a positive integer')
            for key in ('name', 'description'):
                if not isinstance(step[key], str):
                    raise RecipeError(f'step {number}: {key} must be a string')
        elif kind == 'append_learning':
            if is_ref(step['class_id']):
                check_ref(step['class_id'], number, steps, 'classes', 'class_id')
            elif not is_int(step['class_id']) or step['class_id'] < 1:
                raise RecipeError(f'step {number}: class_id must be a positive integer or {{"from_step": N}}')
            if is_ref(step['skill_id']):
                check_ref(step['skill_id'], number, steps, 'skills', 'skill_id')
            elif not is_int(step['skill_id']) or step['skill_id'] < 1:
                raise RecipeError(f'step {number}: skill_id must be a positive integer or {{"from_step": N}}')
            if not is_int(step['level']):
                raise RecipeError(f'step {number}: level must be an integer')
        elif kind == 'append_encounter':
            check_map_id(step['map_id'], number, steps)
            if is_ref(step['troop_id']):
                check_ref(step['troop_id'], number, steps, 'troops', 'troop_id')
            elif not is_int(step['troop_id']) or step['troop_id'] < 1:
                raise RecipeError(f'step {number}: troop_id must be a positive integer or {{"from_step": N}}')
            if not is_int(step['weight']):
                raise RecipeError(f'step {number}: weight must be an integer')
            regions = step.get('region_ids', [])
            if not isinstance(regions, list) or not all(is_int(r) for r in regions):
                raise RecipeError(f'step {number}: region_ids must be a list of integers')
            if step.get('encounter_step') is not None and not is_int(step['encounter_step']):
                raise RecipeError(f'step {number}: encounter_step must be an integer or null')
        elif kind == 'append_dialogue_event':
            check_map_id(step['map_id'], number, steps)
            if is_ref(step['template_event']):
                check_template_ref(step['template_event'], number, steps, step['map_id'])
            elif not is_int(step['template_event']) or not 1 <= step['template_event'] <= 999:
                raise RecipeError(f'step {number}: template_event must be an integer 1..999 or {{"from_step": N}}')
            for key in ('x', 'y'):
                if not is_int(step[key]) or not 0 <= step[key] <= 9999:
                    raise RecipeError(f'step {number}: {key} must be a non-negative integer')
            if not isinstance(step['name'], str) or not 1 <= len(step['name']) <= 100:
                raise RecipeError(f'step {number}: name must be a string of 1..100 characters')
            if not isinstance(step['lines'], list) or not 1 <= len(step['lines']) <= 4 or not all(isinstance(line, str) for line in step['lines']):
                raise RecipeError(f'step {number}: lines must be a list of 1..4 strings')
            if contains_ref_key({k: v for k, v in step.items() if k not in ('template_event', 'map_id')}):
                raise RecipeError(f'step {number}: from_step is only allowed for map_id and template_event')
        elif kind == 'append_staged_event':
            check_map_id(step['map_id'], number, steps)
            if is_ref(step['template_event']):
                check_template_ref(step['template_event'], number, steps, step['map_id'])
            elif not is_int(step['template_event']) or not 1 <= step['template_event'] <= 999:
                raise RecipeError(f'step {number}: template_event must be an integer 1..999 or {{"from_step": N}}')
            for key in ('x', 'y'):
                if not is_int(step[key]) or not 0 <= step[key] <= 9999:
                    raise RecipeError(f'step {number}: {key} must be a non-negative integer')
            if not isinstance(step['name'], str) or not 1 <= len(step['name']) <= 100:
                raise RecipeError(f'step {number}: name must be a string of 1..100 characters')
            if not isinstance(step['pages'], list) or not 1 <= len(step['pages']) <= 8:
                raise RecipeError(f'step {number}: pages must be a list of 1..8 page objects')
            from vxace_staged_commands import page_ops
            shadow = copymod.deepcopy(step['pages'])
            shadow_command_refs(page_ops(shadow), number, steps)
            if contains_ref_key({**{k: v for k, v in step.items() if k not in ('template_event', 'pages', 'map_id')}, 'pages': shadow}):
                raise RecipeError(f'step {number}: from_step is only allowed for map_id, template_event, battle troop ids, item/weapon/armor ids, transfer maps and common event ids in pages')
        elif kind == 'append_common_event':
            if not isinstance(step['name'], str) or not 1 <= len(step['name']) <= 100:
                raise RecipeError(f'step {number}: name must be a string of 1..100 characters')
            if not isinstance(step['trigger'], str) or step['trigger'] not in ('none', 'parallel'):
                raise RecipeError(f'step {number}: trigger must be "none" or "parallel"')
            if (step['trigger'] == 'parallel') != ('switch_id' in step):
                raise RecipeError(f'step {number}: switch_id is required for a parallel common event and not allowed otherwise')
            if 'switch_id' in step and (not is_int(step['switch_id']) or step['switch_id'] < 1):
                raise RecipeError(f'step {number}: switch_id must be a positive integer')
            if not isinstance(step['commands'], list) or not 1 <= len(step['commands']) <= 40:
                raise RecipeError(f'step {number}: commands must be a list of 1..40 operations')
            from vxace_staged_commands import iter_ops
            shadow = copymod.deepcopy(step['commands'])
            shadow_command_refs(iter_ops(shadow), number, steps)
            if contains_ref_key({**{k: v for k, v in step.items() if k != 'commands'}, 'commands': shadow}):
                raise RecipeError(f'step {number}: from_step is only allowed for battle troop ids, item/weapon/armor ids and common event ids in commands')
        elif kind == 'append_blank_event':
            check_map_id(step['map_id'], number, steps)
            if not is_int(step['donor_event']) or not 1 <= step['donor_event'] <= 999:
                raise RecipeError(f'step {number}: donor_event must be an integer 1..999')
            for key in ('x', 'y'):
                if not is_int(step[key]) or not 0 <= step[key] <= 9999:
                    raise RecipeError(f'step {number}: {key} must be a non-negative integer')
            if 'name' in step and (not isinstance(step['name'], str) or not 1 <= len(step['name']) <= 100):
                raise RecipeError(f'step {number}: name must be a string of 1..100 characters')
            if 'donor_map_id' in step and (not is_int(step['donor_map_id']) or not 1 <= step['donor_map_id'] <= 999 or step['donor_map_id'] == step['map_id']):
                raise RecipeError(f'step {number}: donor_map_id must be an integer 1..999 naming a different map than map_id')
        elif kind == 'append_blank_map':
            validate_blank_map(step, number)
        elif kind == 'add_area':
            validate_area(step, number, steps)
        elif kind == 'add_treasure_chest':
            validate_chest(step, number, steps)
        elif kind == 'add_touch_trigger':
            validate_touch_trigger(step, number, steps)
        elif kind == 'add_monster':
            validate_monster(step, number, steps)
        elif kind == 'add_shop':
            check_map_id(step['map_id'], number, steps)
            if is_ref(step['event_id']):
                check_event_ref(step['event_id'], number, steps, step['map_id'])
            elif not is_int(step['event_id']) or not 1 <= step['event_id'] <= 999:
                raise RecipeError(f'step {number}: event_id must be an integer 1..999 or {{"from_step": N}}')
            if type(step['purchase_only']) is not bool:
                raise RecipeError(f'step {number}: purchase_only must be a boolean')
            goods = step['goods']
            if not isinstance(goods, list) or not 1 <= len(goods) <= 32:
                raise RecipeError(f'step {number}: goods must be a list of 1..32 entries')
            literal = set()
            for good in goods:
                if not isinstance(good, dict) or set(good) != {'type', 'id', 'price'} or good['type'] not in GOODS_TABLE:
                    raise RecipeError(f'step {number}: each good needs exactly type (item/weapon/armor), id and price')
                if is_ref(good['id']):
                    check_goods_ref(good['id'], number, steps, good['type'])
                elif not is_int(good['id']) or not 1 <= good['id'] <= 999:
                    raise RecipeError(f'step {number}: goods id must be an integer 1..999 or {{"from_step": N}}')
                else:
                    if (good['type'], good['id']) in literal:
                        raise RecipeError(f'step {number}: duplicate goods entry')
                    literal.add((good['type'], good['id']))
                if good['price'] is not None and (not is_int(good['price']) or not 0 <= good['price'] <= 9999999):
                    raise RecipeError(f'step {number}: goods price must be null or an integer 0..9999999')
            shadow = strip_map_ref(copymod.deepcopy(step))
            if is_ref(shadow['event_id']):
                shadow['event_id'] = 0
            for good in shadow['goods']:
                if is_ref(good['id']):
                    good['id'] = 0
            if contains_ref_key(shadow):
                raise RecipeError(f'step {number}: from_step is only allowed for event_id and goods id')
        elif kind == 'insert_script':
            for key in ('name', 'source_file'):
                if not isinstance(step[key], str) or not step[key]:
                    raise RecipeError(f'step {number}: {key} must be a non-empty string')
        elif kind == 'set_map_display_name':
            check_map_id(step['map_id'], number, steps)
            if not isinstance(step['name'], str):
                raise RecipeError(f'step {number}: name must be a string')
        elif kind == 'set_system_fields':
            if len(step) < 2:
                raise RecipeError(f'step {number}: give at least one of game_title, currency_unit, party_members, start, terms')
            if 'party_members' in step:
                members = step['party_members']
                if not isinstance(members, list) or not 1 <= len(members) <= 8:
                    raise RecipeError(f'step {number}: party_members must list 1..8 actors')
                for member in members:
                    if is_ref(member):
                        check_ref(member, number, steps, 'actors', 'party_members actor')
                    elif not is_int(member) or member < 1:
                        raise RecipeError(f'step {number}: party_members entries must be positive integers or {{"from_step": N}}')
            start = step.get('start')
            shadow = {key: value for key, value in step.items() if key != 'party_members'}
            if isinstance(start, dict) and is_ref(start.get('map_id')):
                check_ref(start['map_id'], number, steps, 'maps', 'start map_id')
                shadow['start'] = {**start, 'map_id': 0}
            if contains_ref_key(shadow):
                raise RecipeError(f'step {number}: from_step is only allowed for party_members and start map_id')
        elif kind == 'text_import':
            if not isinstance(step['csv'], str) or not step['csv']:
                raise RecipeError(f'step {number}: csv must be a non-empty string')
            if 'allow_shorter' in step and type(step['allow_shorter']) is not bool:
                raise RecipeError(f'step {number}: allow_shorter must be a boolean')
        if kind not in ('append_entry', 'append_encounter', 'append_learning', 'add_shop', 'append_dialogue_event', 'append_staged_event', 'append_common_event', 'add_treasure_chest', 'add_touch_trigger', 'add_monster', 'set_system_fields', 'add_area') \
                and contains_ref_key(strip_map_ref(step)):
            raise RecipeError(f'step {number}: from_step is not allowed in a {kind} step')
        if kind == 'append_encounter' and contains_ref_key({k: v for k, v in step.items() if k not in ('troop_id', 'map_id')}):
            raise RecipeError(f'step {number}: from_step is only allowed for map_id and troop_id')
        if kind == 'append_learning' and contains_ref_key({k: v for k, v in step.items() if k not in ('skill_id', 'class_id')}):
            raise RecipeError(f'step {number}: from_step is only allowed for class_id and skill_id')
    return steps


def load_recipe(path):
    path = Path(path)
    try:
        recipe = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise RecipeError(f'cannot read recipe: {error}')
    validate_recipe(recipe)
    return recipe


def resolve_refs(value, created):
    """Replace every {"from_step": k} with the id created by step k (a second line of defence; ids come from audited steps)."""
    if is_ref(value):
        k = value['from_step']
        if created.get(k) is None:
            raise RecipeError(f'from_step {k} has no created id')
        return created[k]
    if isinstance(value, dict):
        return {key: resolve_refs(item, created) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_refs(item, created) for item in value]
    return value


# ---------------------------------------------------------------- spec building (snapshot + parameters only)

def build_spec(title, number, step, snapshot, source=None):
    """Build the exact spec for one step. Hashes, next ids and counts come only from the snapshot."""
    kind = step['type']
    label = f'{title} / step {number}' if title else f'Recipe step {number}'
    if kind == 'append_entry':
        if not snapshot.get('append_slot_supported'):
            raise RecipeError('table has no supported append slot')
        mutation = {'action': 'append_database_entry', 'template_id': step['template_id'], 'new_id': snapshot['next_id'],
                    'expected_array_sha256': snapshot['array_sha256'], 'expected_template_sha256': snapshot['template_sha256']}
        # Referenced-database hashes come only from the snapshot and only for the databases the overrides reference.
        for name in sorted(required_refs(step['table'], step['overrides'])):
            if snapshot.get(name + '_sha256') is None:
                raise RecipeError(f'snapshot has no {name} hash')
            mutation[ref_field(name)] = snapshot[name + '_sha256']
        if step['table'] == 'actors':
            from vxace_database_append import actor_graphics
            characters, faces = actor_graphics(step['overrides'])
            if characters or faces:
                assets = snapshot.get('assets')
                wanted = {**({'characters': characters} if characters else {}), **({'faces': faces} if faces else {})}
                if not isinstance(assets, dict) or set(assets) != set(wanted) or any(not isinstance(assets[group], dict) or set(assets[group]) != names for group, names in wanted.items()):
                    raise RecipeError('snapshot lacks the character/face sheet bindings of the actor graphics')
                mutation['expected_assets'] = assets
        mutation['overrides'] = step['overrides']
        change = {'kind': 'database_entry', 'locator': {'table': step['table']},
                  'proposal': f'Recipe step {number}: append one {step["table"]} entry cloned from template {step["template_id"]}.',
                  'mutation': mutation}
    elif kind == 'set_system_fields':
        mutation = {'action': 'set_system_fields', 'expected_system_sha256': snapshot['system_sha256']}
        mutation.update({key: step[key] for key in ('game_title', 'currency_unit', 'party_members', 'start', 'terms') if key in step})
        if 'party_members' in step:
            mutation['expected_actors_sha256'] = snapshot['actors_sha256']
        if 'start' in step:
            start_map = snapshot.get('start_map')
            if not isinstance(step['start'], dict) or not isinstance(start_map, dict) or start_map.get('map_id') != step['start'].get('map_id'):
                raise RecipeError('snapshot lacks the start map binding')
            mutation['expected_mapinfos_sha256'] = snapshot['mapinfos_sha256']
            mutation['expected_start_map_sha256'] = start_map['sha256']
        change = {'kind': 'system_fields', 'locator': {'table': 'system'},
                  'proposal': f'Recipe step {number}: edit System fields ({", ".join(key for key in ("game_title", "currency_unit", "party_members", "start", "terms") if key in step)}).',
                  'mutation': mutation}
    elif kind == 'append_key_item':
        if not snapshot.get('append_slot_supported'):
            raise RecipeError('Items table has no supported append slot')
        change = {'kind': 'database_entry', 'locator': {'table': 'items'},
                  'proposal': f'Recipe step {number}: append one inert key item cloned from template {step["template_item"]}.',
                  'mutation': {'action': 'append_key_item', 'template_id': step['template_item'], 'new_id': snapshot['next_item_id'],
                               'expected_array_sha256': snapshot['array_sha256'], 'expected_template_sha256': snapshot['template_sha256'],
                               'name': step['name'], 'description': step['description']}}
    elif kind == 'append_learning':
        if not snapshot.get('append_supported'):
            raise RecipeError('class has no supported learning append slot')
        change = {'kind': 'database_entry', 'locator': {'table': 'classes', 'id': step['class_id']},
                  'proposal': f'Recipe step {number}: class {step["class_id"]} learns skill {step["skill_id"]} at level {step["level"]}.',
                  'mutation': {'action': 'append_class_learning', 'expected_array_sha256': snapshot['array_sha256'],
                               'expected_class_sha256': snapshot['class_sha256'], 'expected_learning_count': snapshot['learning_count'],
                               'expected_skills_sha256': snapshot['skills_sha256'], 'skill_id': step['skill_id'], 'level': step['level']}}
    elif kind == 'append_encounter':
        change = {'kind': 'map_encounter', 'locator': {'map_id': step['map_id']},
                  'proposal': f'Recipe step {number}: append one random encounter to map {step["map_id"]}.',
                  'mutation': {'action': 'append_encounter', 'expected_map_sha256': snapshot['map_sha256'],
                               'expected_encounter_count': snapshot['encounter_count'], 'expected_troops_sha256': snapshot['troops_sha256'],
                               'troop_id': step['troop_id'], 'weight': step['weight'], 'region_ids': step.get('region_ids', []),
                               'encounter_step': step.get('encounter_step')}}
    elif kind == 'append_dialogue_event':
        change = {'kind': 'map_event', 'locator': {'map_id': step['map_id']},
                  'proposal': f'Recipe step {number}: append one literal dialogue event "{step["name"]}" to map {step["map_id"]}.',
                  'mutation': {'action': 'append_dialogue_event', 'template_id': step['template_event'], 'new_id': snapshot['next_event_id'],
                               'name': step['name'], 'x': step['x'], 'y': step['y'], 'text': step['lines'],
                               'expected_map_sha256': snapshot['map_sha256'], 'expected_template_sha256': snapshot['template_sha256']}}
    elif kind == 'append_staged_event':
        change = {'kind': 'map_event', 'locator': {'map_id': step['map_id']},
                  'proposal': f'Recipe step {number}: append one {len(step["pages"])}-page staged event "{step["name"]}" to map {step["map_id"]}.',
                  'mutation': {'action': 'append_staged_event', 'template_id': step['template_event'], 'new_id': snapshot['next_event_id'],
                               'name': step['name'], 'x': step['x'], 'y': step['y'], 'pages': step['pages'],
                               'expected_map_sha256': snapshot['map_sha256'], 'expected_template_sha256': snapshot['template_sha256'],
                               'expected_system_sha256': snapshot['system_sha256']}}
        from vxace_staged_commands import bind_fields, graphic_names
        try:
            change['mutation'].update(bind_fields(step['pages'], snapshot))
        except ValueError as error:
            raise RecipeError(str(error))
        names = graphic_names(step['pages'])
        if names:
            assets = snapshot.get('assets')
            if not isinstance(assets, dict) or set(assets) != names:
                raise RecipeError('snapshot lacks the character sheet bindings of the page graphics')
            change['mutation']['expected_assets'] = {name: assets[name] for name in sorted(names)}
    elif kind == 'append_common_event':
        if not snapshot.get('append_slot_supported'):
            raise RecipeError('CommonEvents has no supported append slot')
        mutation = {'action': 'append_common_event', 'new_id': snapshot['next_id'], 'name': step['name'], 'trigger': step['trigger'],
                    **({'switch_id': step['switch_id']} if step['trigger'] == 'parallel' else {}), 'commands': step['commands'],
                    'expected_common_events_sha256': snapshot['common_events_sha256'], 'expected_system_sha256': snapshot['system_sha256']}
        change = {'kind': 'common_event', 'locator': {'table': 'common_events'},
                  'proposal': f'Recipe step {number}: append {step["trigger"]} common event "{step["name"]}" (id {snapshot["next_id"]}).',
                  'mutation': mutation}
        from vxace_staged_commands import bind_fields
        try:
            mutation.update(bind_fields([{'condition': {}, 'commands': step['commands']}], snapshot))
        except ValueError as error:
            raise RecipeError(str(error))
    elif kind == 'append_blank_map':
        mutation = {'action': 'append_blank_map', 'new_id': snapshot['new_id'], 'name': step['name'],
                    **{field: snapshot['guard'][field] for field in sorted(snapshot['guard'])},
                    **{key: step[key] for key in ('width', 'height', 'tileset_id', 'parent_id', 'fill_floor') if key in step}}
        change = {'kind': 'map_entry', 'locator': {'template_map_id': step['template_map_id']},
                  'proposal': f'Recipe step {number}: append map {snapshot["new_id"]} "{step["name"]}" from the inert template map {step["template_map_id"]}'
                              + (f' with an A5 floor fill (tile {snapshot["planned_map"]["floor_tile_id"]})' if step.get('fill_floor') is not None else '') + '.',
                  'mutation': mutation}
    elif kind == 'append_blank_event':
        change = {'kind': 'map_event', 'locator': {'map_id': step['map_id']},
                  'proposal': f'Recipe step {number}: append one blank event "{step.get("name", snapshot["default_name"])}" to map {step["map_id"]} using donor event {step["donor_event"]} for schema only.',
                  'mutation': {'action': 'append_blank_event', 'donor_event_id': step['donor_event'], 'new_id': snapshot['next_event_id'],
                               'name': step.get('name', snapshot['default_name']), 'x': step['x'], 'y': step['y'],
                               'expected_map_sha256': snapshot['map_sha256'], 'expected_donor_sha256': snapshot['donor_sha256'],
                               **({'donor_map_id': step['donor_map_id']} if 'donor_map_id' in step else {})}}
    elif kind == 'add_shop':
        if not snapshot.get('append_supported'):
            raise RecipeError('event has no supported shop slot: ' + str(snapshot.get('unsupported_reason')))
        change = {'kind': 'map_shop', 'locator': {'map_id': step['map_id'], 'event_id': step['event_id']},
                  'proposal': f'Recipe step {number}: add a {len(step["goods"])}-item shop to event {step["event_id"]} on map {step["map_id"]}.',
                  'mutation': {'action': 'add_shop', 'expected_map_sha256': snapshot['map_sha256'], 'expected_event_sha256': snapshot['event_sha256'],
                               'expected_list_sha256': snapshot['list_sha256'], 'expected_items_sha256': snapshot['items_sha256'],
                               'expected_weapons_sha256': snapshot['weapons_sha256'], 'expected_armors_sha256': snapshot['armors_sha256'],
                               'goods': step['goods'], 'purchase_only': step['purchase_only']}}
    elif kind == 'insert_script':
        change = {'kind': 'script_slot', 'locator': {'before_index': snapshot['before_index']},
                  'proposal': f'Recipe step {number}: insert the reviewed script "{step["name"]}" before canonical Main.',
                  'mutation': {'action': 'insert_before_main', 'new_id': snapshot['unused_id_candidate'], 'name': step['name'], 'source': source,
                               'expected_archive_sha256': snapshot['archive_sha256'], 'expected_anchor_sha256': snapshot['anchor_sha256']}}
    elif kind == 'set_map_display_name':
        change = {'kind': 'map_name', 'locator': {'map_id': snapshot['map_id']},
                  'proposal': f'Recipe step {number}: set the display name of map {snapshot["map_id"]}.',
                  'mutation': {'action': 'set_display_name', 'expected_map_sha256': snapshot['map_sha256'],
                               'expected_display_name': snapshot['display_name'], 'value': step['name']}}
    else:
        raise RecipeError(f'step type {kind} has no spec builder')
    return {'title': label, 'changes': [change]}


def created_id(step, snapshot):
    """Id that a step creates, taken from its snapshot (cross-checked against the copy patcher audit afterwards)."""
    if step['type'] == 'append_entry':
        return snapshot['next_id']
    if step['type'] == 'append_key_item':
        return snapshot['next_item_id']
    if step['type'] in ('append_dialogue_event', 'append_blank_event', 'append_staged_event'):
        return snapshot['next_event_id']
    if step['type'] == 'append_common_event':
        return snapshot['next_id']
    if step['type'] == 'append_blank_map':
        return snapshot['new_id']
    return None


# ---------------------------------------------------------------- orchestration

def run_tool(log_dir, name, tool, args, timeout=STEP_TIMEOUT):
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run([sys.executable, str(ROOT / tool), *map(str, args)], capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=timeout)
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        code, out, err = 124, '', 'timed out'
    (log_dir / (name + '.stdout.log')).write_text(out, encoding='utf-8')
    (log_dir / (name + '.stderr.log')).write_text(err, encoding='utf-8')
    return code, out, err


def last_line(*texts):
    for text in texts:
        lines = [line for line in (text or '').strip().splitlines() if line.strip()]
        if lines:
            return lines[-1][:500]
    return 'no output'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class StepFailure(Exception):
    pass


def main_index(index):
    order = read_json(Path(index) / 'scripts/order.json').get('scripts')
    mains = [row['index'] for row in order if isinstance(row, dict) and row.get('name') == 'Main']
    if len(mains) != 1:
        raise StepFailure('Expected exactly one Main script to anchor the insertion')
    return mains[0]


def remove_tree(path):
    """Delete a folder tree, clearing read-only flags that copied project files may carry."""
    def clear(function, target, _error):
        try:
            os.chmod(target, 0o700)
            function(target)
        except OSError:
            pass
    path = Path(path)
    if path.exists():
        shutil.rmtree(path, onerror=clear)


class Session:
    """In-place mode (v1.29): the designated project is written directly. One start backup, then each step's verified changed files are promoted
    from the step's single temp copy into the project through adopt's atomic writer, with rollback. `files` is the cumulative change set and is
    saved after every promoted step as an adopt-compatible undo record (backup_dir/adopt-record.json), so `undo` works at any point."""

    def __init__(self, project, work, backup_dir, recipe_path):
        self.project, self.work, self.backup_dir, self.recipe_path = project, work, backup_dir, recipe_path
        self.tmp_copy = work / 'tmp-copy'
        self.record_path = backup_dir / 'adopt-record.json'
        self.manifest = {}
        self.files = {}
        self.created_dirs = set()
        self.record_id = None
        self.promoted = 0

    def back_up_start(self):
        """Copy every Data/*.rvdata2 and Game.ini into the backup folder with a hash manifest (verified after copying)."""
        data = self.project / 'Data'
        rels = sorted([p.relative_to(self.project).as_posix() for p in data.glob('*.rvdata2') if p.is_file()]
                      + [p.name for p in (self.project / 'Game.ini',) if p.is_file()])
        for rel in rels:
            self.back_up_file(rel)
        adopt.dump_json(self.backup_dir / 'manifest.json', {'version': VERSION, 'project': str(self.project), 'created_utc': adopt.utc_now().isoformat(),
                                                            'files': self.manifest})
        self.save_record()

    def back_up_file(self, rel):
        raw = (self.project / rel).read_bytes()
        digest = adopt.sha256_bytes(raw)
        adopt.write_atomic(self.backup_dir / 'files' / rel, raw)
        if adopt.sha256_file(self.backup_dir / 'files' / rel) != digest:
            raise RecipeError(f'backup verification failed for {rel}')
        self.manifest[rel] = digest

    def save_record(self, files=None, created_dirs=None, promoted=None):
        files = self.files if files is None else files
        created_dirs = self.created_dirs if created_dirs is None else created_dirs
        body = {'version': adopt.VERSION, 'kind': 'recipe_in_place', 'project': str(self.project), 'plan_id': None, 'recipe': str(self.recipe_path),
                'created_utc': adopt.utc_now().isoformat(), 'backup_dir': str(self.backup_dir), 'plan': None,
                'steps_promoted': self.promoted if promoted is None else promoted, 'created_dirs': sorted(created_dirs),
                'files': [files[rel] for rel in sorted(files)]}
        record = {'record_id': adopt.digest(body), **body}
        adopt.write_atomic(self.record_path, (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        self.record_id = record['record_id']

    def promote(self, copy, audit_path):
        """Verify the step's copy against its audit and the project, then write only the changed files into the project. Raises StepFailure."""
        try:
            adopt.refuse_if_running()
            path, audit = adopt.load_audit(audit_path)
            state = adopt.declared_state([(path, audit)])
            declared = {rel: s for rel, s in state.items() if s['before'] != s['after']}
            project_inv, copy_inv = adopt.inventory(self.project), adopt.inventory(copy)
        except (adopt.Refused, ValueError, OSError) as error:
            raise StepFailure(f'promotion refused: {error}')
        problems = [f'{rel}: project is {"absent" if project_inv.get(rel) is None else project_inv[rel][:12]}, audit expected {"absent" if s["before"] is None else s["before"][:12]}'
                    for rel, s in sorted(declared.items()) if project_inv.get(rel) != s['before']]
        differing = sorted(rel for rel in set(project_inv) | set(copy_inv) if project_inv.get(rel) != copy_inv.get(rel))
        problems += [f'{rel}: differs between project and temp copy but the audit does not declare it' for rel in differing if rel not in declared]
        problems += [f'{rel}: declared by the audit but identical in the temp copy' for rel in sorted(declared) if rel not in differing]
        problems += [f'{rel}: temp copy {copy_inv.get(rel, "absent")[:12]}, audit recorded {declared[rel]["after"][:12]}' for rel in sorted(declared) if copy_inv.get(rel) != declared[rel]['after']]
        if problems:
            raise StepFailure('promotion refused, project untouched: ' + '; '.join(problems[:5]))
        files = [{'path': rel, 'action': 'create' if declared[rel]['before'] is None else 'replace', 'project_sha256': declared[rel]['before'],
                  'copy_sha256': declared[rel]['after']} for rel in sorted(declared)]
        payloads = {f['path']: (copy / f['path']).read_bytes() for f in files}
        backups = {f['path']: (self.project / f['path']).read_bytes() for f in files if f['action'] == 'replace'}
        new_dirs = {Path(f['path']).parent.as_posix() for f in files if f['action'] == 'create' and not (self.project / Path(f['path']).parent).is_dir()}
        merged = {rel: dict(row) for rel, row in self.files.items()}
        for f in files:
            row = merged.get(f['path'])
            if row is None:
                merged[f['path']] = {'path': f['path'], 'action': f['action'], 'before_sha256': f['project_sha256'], 'after_sha256': f['copy_sha256']}
            else:
                row['after_sha256'] = f['copy_sha256']
        written = []
        try:
            for f in files:
                if f['action'] == 'replace' and f['path'] not in self.manifest:
                    self.back_up_file(f['path'])
            for f in files:
                adopt.write_atomic(self.project / f['path'], payloads[f['path']])
                written.append(f)
            bad = [f['path'] for f in files if adopt.current_hash(self.project, f['path']) != f['copy_sha256']]
            if bad:
                raise RuntimeError('post-write verification failed: ' + ', '.join(bad))
            self.save_record(merged, self.created_dirs | new_dirs, self.promoted + 1)
        except BaseException as error:
            failures = adopt.rollback(self.project, files, written, backups, new_dirs)
            raise StepFailure(f'promotion failed and was rolled back ({"clean" if not failures else "INCOMPLETE: " + "; ".join(failures)}): {error}')
        self.files, self.created_dirs, self.promoted = merged, self.created_dirs | new_dirs, self.promoted + 1
        return [f['path'] for f in files]

    def verify_expected(self, rolled_back):
        """Every backed-up file and every promoted file must hold exactly the expected bytes now. Returns a list of problems."""
        problems = []
        for rel, digest in sorted(self.manifest.items()):
            expected = digest if rolled_back or rel not in self.files else self.files[rel]['after_sha256']
            if adopt.current_hash(self.project, rel) != expected:
                problems.append(rel)
        if not rolled_back:
            problems += [rel for rel, row in sorted(self.files.items()) if rel not in self.manifest and adopt.current_hash(self.project, rel) != row['after_sha256']]
        return problems


def shed_step(directory, index, audit, session):
    """After a step's gates pass: delete the pre index and the post index (and, in place, the snapshot); the per-step evidence files stay."""
    remove_tree(index)
    remove_tree(audit / 'post-index')
    if session:
        remove_tree(directory / 'snapshot')


def execute_step(number, step, title, source, work, ruby, created, recipe_dir, records, tag='', rtp=None, macro='add_treasure_chest', session=None, cleanup=False):
    """Run one step as a normal transaction. Returns its report record; raises StepFailure after filling the record.
    `tag` ('a', 'b') names the sub-steps of a macro step; `rtp` is the optional explicit RTP root for page graphics.
    With a `session` (in-place mode) `source` is the live project, the patcher clones it into the session's single temp copy and, once every gate
    passed, only the changed files are promoted into the project; the temp copy and both indexes are deleted. With `cleanup` the copy-chain run
    deletes the pre and post index folders once the step has passed."""
    directory = work / f'step-{number:02d}{tag}'
    directory.mkdir()
    logs = directory / 'logs'
    index, copy, audit = directory / 'index', (session.tmp_copy if session else directory / 'copy'), directory / 'audit'
    record = {'step': number, 'type': step['type'], 'status': 'running', **({'macro': macro, 'part': tag} if tag else {}), 'source': str(source), 'directory': str(directory),
              'resolved_parameters': None, 'created_id': None, 'spec': None, 'snapshot': None, 'plan': None, 'impact': None,
              'audit': None, 'copy': None, 'exit_codes': {}, 'error': None}
    records.append(record)

    def fail(message):
        record['status'] = 'failed'
        record['error'] = message
        raise StepFailure(message)

    def tool(name, script, args):
        code, out, err = run_tool(logs, name, script, args)
        record['exit_codes'][name] = code
        if code != 0:
            fail(f'{name} failed (exit {code}): {last_line(err, out)}')
        return out

    try:
        kind = step['type']
        resolved = resolve_refs(step, created)
        from vxace_staged_commands import staged_refs, graphic_names
        from vxace_database_append import actor_graphics
        resolved_record = dict(resolved)
        source_text = None
        csv_path = None
        if kind == 'insert_script':
            path = (recipe_dir / resolved['source_file']).resolve()
            if not path.is_file():
                fail(f'source_file not found: {path}')
            raw = path.read_bytes()
            source_text = raw.decode('utf-8', 'strict')
            resolved_record = {**resolved, 'source_file': str(path), 'source_sha256': sha256(raw), 'source_bytes': len(raw)}
        elif kind == 'text_import':
            csv_path = (recipe_dir / resolved['csv']).resolve()
            if not csv_path.is_file():
                fail(f'csv not found: {csv_path}')
            resolved_record = {**resolved, 'csv': str(csv_path), 'csv_sha256': sha256(csv_path.read_bytes())}
        record['resolved_parameters'] = resolved_record

        tool('reader', 'vxace_project_reader.py', [source, '--output', index, *(['--ruby', ruby] if ruby else [])])
        spec = directory / 'spec.json'
        snapshot = None
        if kind == 'text_import':
            args = [index, '--project', source, '--csv', csv_path, '--spec-out', spec, '--report', directory / 'import.md',
                    '--json', directory / 'import.json']
            if resolved.get('allow_shorter'):
                args.append('--allow-shorter')
            tool('text-import', 'vxace_text_import.py', args)
            if not spec.is_file():
                fail('text import produced no ordinary change (no main spec was written)')
            side = [s for s in read_json(directory / 'import.json').get('specs', []) if Path(s['file']).resolve() != spec.resolve()]
            if side:
                record['skipped_side_specs'] = [{'file': s['file'], 'note': s.get('note')} for s in side]
                record['note'] = 'Map display-name side specs were not applied; each needs its own set_map_display_name step.'
        else:
            if kind in ('append_entry', 'append_key_item'):
                table_args = (['--table', resolved['table'], '--template-id', resolved['template_id']] if kind == 'append_entry'
                              else ['--template-item', resolved['template_item']])
                if kind == 'append_entry' and resolved['table'] == 'actors':
                    from vxace_database_append import actor_graphics
                    characters, faces = actor_graphics(resolved['overrides'])
                    table_args += [arg for sheet in sorted(characters) for arg in ('--character-sheet', sheet)]
                    table_args += [arg for sheet in sorted(faces) for arg in ('--face-sheet', sheet)]
                    if (characters or faces) and rtp:
                        table_args += ['--rtp', rtp]
                script, args, name = 'vxace_database_entries.py', [index, '--project', source, *table_args], 'item-entry-snapshot'
            elif kind == 'set_system_fields':
                start = resolved.get('start')
                script, args, name = ('vxace_system_fields.py', [index, '--project', source,
                                                                 *(['--start-map', start['map_id']] if isinstance(start, dict) and is_int(start.get('map_id')) else [])],
                                      'system-fields-snapshot')
            elif kind == 'append_learning':
                script, args, name = ('vxace_database_entries.py', [index, '--project', source, '--table', 'classes', '--class-id', resolved['class_id']],
                                      'item-entry-snapshot')
            elif kind == 'append_dialogue_event':
                script, args, name = ('vxace_map_events.py', [index, '--project', source, '--map', resolved['map_id'],
                                                              '--template-event', resolved['template_event']], 'map-event-snapshot')
            elif kind == 'append_staged_event':
                sheets = sorted(graphic_names(resolved['pages']))
                script, args, name = ('vxace_map_events.py', [index, '--project', source, '--map', resolved['map_id'],
                                                              '--template-event', resolved['template_event'], '--staged',
                                                              *[arg for m in sorted(staged_refs(resolved['pages'])['maps']) for arg in ('--transfer-map', m)],
                                                              *[arg for sheet in sheets for arg in ('--asset', sheet)],
                                                              *(['--rtp', rtp] if sheets and rtp else [])], 'map-event-snapshot')
            elif kind == 'append_common_event':
                script, args, name = ('vxace_common_event_append.py', [index, '--project', source,
                                                                       *[arg for m in sorted(staged_refs([{'condition': {}, 'commands': resolved['commands']}])['maps']) for arg in ('--transfer-map', m)]],
                                      'common-event-snapshot')
            elif kind == 'append_blank_event':
                script, args, name = ('vxace_map_events.py', [index, '--project', source, '--map', resolved['map_id'],
                                                              '--donor-event', resolved['donor_event'],
                                                              *(['--donor-map', resolved['donor_map_id']] if 'donor_map_id' in resolved else [])], 'map-event-snapshot')
            elif kind == 'append_blank_map':
                script, args, name = ('vxace_maps.py', [index, '--project', source, '--template-map', resolved['template_map_id'],
                                                        *[arg for key, flag in (('width', '--width'), ('height', '--height'), ('tileset_id', '--tileset-id'),
                                                                                ('parent_id', '--parent-id'), ('fill_floor', '--fill-floor')) if key in resolved
                                                          for arg in (flag, resolved[key])]], 'map-append-snapshot')
            elif kind == 'add_shop':
                script, args, name = ('vxace_map_shops.py', [index, '--project', source, '--map', resolved['map_id'],
                                                             '--event', resolved['event_id']], 'map-shop-snapshot')
            elif kind == 'append_encounter':
                script, args, name = 'vxace_map_encounters.py', [index, '--project', source, '--map', resolved['map_id']], 'map-encounter-snapshot'
            elif kind == 'set_map_display_name':
                script, args, name = 'vxace_map_names.py', [index, '--project', source, '--map', resolved['map_id']], 'map-name-snapshot'
            else:
                script, args, name = ('vxace_script_slots.py', [index, '--project', source, '--before-index', main_index(index)],
                                      'script-slot-snapshot')
            snap_dir = directory / 'snapshot'
            tool('snapshot', script, [*args, '--output', snap_dir])
            snapshot = read_json(snap_dir / (name + '.json'))
            record['snapshot'] = str(snap_dir / (name + '.json'))
            try:
                spec_obj = build_spec(title, number, resolved, snapshot, source_text)
            except (KeyError, RecipeError) as error:
                fail(f'cannot build spec from snapshot: {error}')
            spec.write_text(json.dumps(spec_obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            record['created_id'] = created_id(resolved, snapshot)
        record['spec'] = str(spec)

        tool('plan', 'vxace_patch_planner.py', [index, '--project', source, '--spec', spec, '--output', directory / 'plan'])
        record['plan'] = str(directory / 'plan')
        tool('impact', 'vxace_impact.py', [index, '--spec', spec, '--json', directory / 'impact.json', '--markdown', directory / 'impact.md'])
        record['impact'] = str(directory / 'impact.json')
        tool('patcher', 'vxace_copy_patcher.py', [index, '--project', source, '--spec', spec, '--copy', copy, '--audit', audit,
                                                  '--backend', 'python', *(['--ruby', ruby] if ruby else []),
                                                  *(['--rtp', rtp] if rtp and ((kind == 'append_staged_event' and graphic_names(resolved['pages']))
                                                                               or (kind == 'append_entry' and resolved['table'] == 'actors' and any(actor_graphics(resolved['overrides'])))) else [])])
        record['audit'] = str(audit / 'audit.json')
        if not copy.is_dir():
            fail('copy patcher reported success but the copy is missing')
        if not session:
            record['copy'] = str(copy)
        if record['created_id'] is not None:
            try:
                audit_change = read_json(audit / 'audit.json')['changes'][0]
                audited = (audit_change['map_event']['new_id'] if kind in ('append_dialogue_event', 'append_blank_event', 'append_staged_event')
                           else audit_change['common_event']['new_id'] if kind == 'append_common_event'
                           else audit_change['new_map']['new_id'] if kind == 'append_blank_map' else audit_change['entry']['created_id'])
            except (OSError, KeyError, IndexError, ValueError):
                audited = None
            if audited != record['created_id']:
                fail(f'audit created_id {audited!r} does not match the snapshot id {record["created_id"]!r}')
        if session:
            try:
                record['promoted_files'] = session.promote(copy, audit / 'audit.json')
            except StepFailure as failure:
                fail(str(failure))
            record['snapshot'] = None
        if session or cleanup:
            shed_step(directory, index, audit, session)
        record['status'] = 'ok'
        return record
    except StepFailure:
        raise
    except Exception as error:  # unexpected tool-side problem: still a failed step with a record
        record['status'] = 'failed'
        record['error'] = f'{type(error).__name__}: {error}'
        raise StepFailure(record['error'])
    finally:
        if session:
            remove_tree(copy)


def chest_message(contents, project):
    """(gain command, literal message) for a chest. Names and the currency unit are read from the step's source project, never guessed."""
    from vxace_staged_commands import check_text, load_array, load_native
    if 'gold' in contents:
        unit = 'G'
        try:
            value = load_native(project, 'System.rvdata2').get('currency_unit')
            candidate = value.data.decode('utf-8') if hasattr(value, 'data') else None
            if candidate:
                check_text(candidate, 'currency unit', 20)
                unit = candidate
        except (ValueError, UnicodeDecodeError, AttributeError):
            pass
        return {'gold': contents['gold']}, f'Obtained {contents["gold"]} {unit}!'
    kind = next(kind for kind in CHEST_KINDS if kind in contents)
    table = CHEST_TABLES[kind]
    try:
        root = load_array(project, table)
    except ValueError as error:
        raise RecipeError(f'treasure chest cannot read the {table}: {error}')
    number = contents[kind]
    if not 1 <= number < len(root) or root[number] is None:
        raise RecipeError(f'treasure chest {kind} id {number} does not exist in the {table}')
    name = root[number].get('name')
    try:
        label = check_text(name.data.decode('utf-8'), f'{kind} name', 100)
    except (ValueError, UnicodeDecodeError, AttributeError):
        raise RecipeError(f'{kind} {number} has a name that cannot be shown as plain literal text (empty, control codes or a backslash)')
    text = f'Obtained {label}!' if contents['amount'] == 1 else f'Obtained {label} x{contents["amount"]}!'
    return {kind: number, 'amount': contents['amount']}, text


def expand_chest(step, project):
    """Expand a resolved add_treasure_chest step into its two concrete steps: (blank-event step or None, staged-event step).
    The staged step's template_event is filled in by the caller when a blank event had to be appended first."""
    command, message = chest_message(step['contents'], project)
    graphic = dict(step.get('graphic') or CHEST_GRAPHIC)
    pages = [{'condition': {}, 'graphic': graphic, 'options': dict(CHEST_OPTIONS),
              'commands': [command, {'text': [message]}, {'set_self_switch': 'A', 'value': True}]},
             {'condition': {'self_switch': 'A'}, 'graphic': {**graphic, 'direction': 8}, 'options': dict(CHEST_OPTIONS), 'commands': []}]
    blank = None
    if 'donor_event' in step:
        blank = {'type': 'append_blank_event', 'map_id': step['map_id'], 'donor_event': step['donor_event'], 'x': step['blank_x'], 'y': step['blank_y']}
    staged = {'type': 'append_staged_event', 'map_id': step['map_id'], 'template_event': step.get('template_event'), 'x': step['x'], 'y': step['y'],
              'name': step['name'], 'pages': pages}
    return blank, staged


TOUCH_OPTIONS = {'priority': 'below'}


def expand_touch_trigger(step, project):
    """Expand a resolved add_touch_trigger step into (blank-event step or None, staged-event step). Page 1 is the player-touch trigger with
    priority below the characters (the player steps onto it); unless repeatable, it ends by turning self switch A ON and page 2 (self switch A) is empty."""
    commands = list(step['commands'])
    if step.get('repeatable'):
        pages = [{'condition': {}, 'trigger': 'player_touch', 'options': dict(TOUCH_OPTIONS), 'commands': commands}]
    else:
        pages = [{'condition': {}, 'trigger': 'player_touch', 'options': dict(TOUCH_OPTIONS), 'commands': commands + [{'set_self_switch': 'A', 'value': True}]},
                 {'condition': {'self_switch': 'A'}, 'options': dict(TOUCH_OPTIONS), 'commands': []}]
    blank = None
    if 'donor_event' in step:
        blank = {'type': 'append_blank_event', 'map_id': step['map_id'], 'donor_event': step['donor_event'], 'x': step['blank_x'], 'y': step['blank_y']}
    staged = {'type': 'append_staged_event', 'map_id': step['map_id'], 'template_event': step.get('template_event'), 'x': step['x'], 'y': step['y'],
              'name': step['name'], 'pages': pages}
    return blank, staged


LOCKED_TEXT = ["It's locked."]


def expand_monster(step, project):
    """Expand a resolved add_monster step into (blank-event step or None, staged-event step). Page 1 carries the condition, the character graphic, priority
    same (the monster collides, so the player bumps into it) and the trigger: event touch when it moves, player touch when it is fixed in place.
    Its commands are the optional intro text and one battle; unless respawn, the win branch ends by turning self switch A ON and page 2 (self switch A only,
    no graphic, priority below, no commands) takes over, because page conditions are ANDed and page 1 may already use a switch. `project` is unused."""
    move = dict(step.get('move') or MONSTER_MOVE)
    trigger = 'player_touch' if move['type'] == 'fixed' else 'event_touch'
    respawn = bool(step.get('respawn'))
    battle = {'battle': step['troop'], 'can_escape': step.get('can_escape', True), 'can_lose': step.get('can_lose', False)}
    win = list(step.get('win', [])) + ([] if respawn else [{'set_self_switch': 'A', 'value': True}])
    if win:
        battle['win'] = win
    for key in ('escape', 'lose'):
        if key in step:
            battle[key] = list(step[key])
    commands = ([{'text': list(step['intro_text'])}] if step.get('intro_text') else []) + [battle]
    pages = [{'condition': copymod.deepcopy(step.get('condition', {})), 'graphic': dict(step['graphic']), 'move': move, 'trigger': trigger,
              'options': {'priority': 'same'}, 'commands': commands}]
    if not respawn:
        pages.append({'condition': {'self_switch': 'A'}, 'options': {'priority': 'below'}, 'commands': []})
    blank = None
    if 'donor_event' in step:
        blank = {'type': 'append_blank_event', 'map_id': step['map_id'], 'donor_event': step['donor_event'], 'x': step['blank_x'], 'y': step['blank_y']}
    staged = {'type': 'append_staged_event', 'map_id': step['map_id'], 'template_event': step.get('template_event'), 'x': step['x'], 'y': step['y'],
              'name': step['name'], 'pages': pages}
    return blank, staged


def door_page(trigger, graphic, target, condition=None, locked_text=None):
    """One page, no self switch (a door works every time): a transfer to `target` {map_id, x, y, direction}. Touch doors sit below the characters so the
    player steps onto them; action doors are solid (same as characters) so the player faces them and presses the action button.
    With a `condition` (v1.30) the command is `if condition then transfer else text locked_text` (default text "It's locked.")."""
    transfer = {'transfer': {**target, 'fade': 0}}
    commands = [transfer] if condition is None else [{'if': copymod.deepcopy(condition), 'then': [transfer], 'else': [{'text': list(locked_text or LOCKED_TEXT)}]}]
    page = {'condition': {}, 'trigger': trigger, 'options': {'priority': 'below' if trigger == 'player_touch' else 'same'},
            'commands': commands}
    if graphic:
        page['graphic'] = dict(graphic)
    return page


def free_cell(taken):
    """First cells of the minimum 17x13 map (always inside any map) that are not in `taken`."""
    return next((x, y) for y in range(13) for x in range(17) if (x, y) not in taken)


def expand_area(step, project=None):
    """Expand a resolved add_area step into its ordinary transactions as a list of concrete steps. They reference each other with local
    {"from_step": k} numbers (1 = the new map), resolved against the macro's own created ids. Order: new map, [door blank event], door, blank event
    on the new map (schema donor from the door map), return door."""
    door, ret, arrival, back = step['door'], step['return_door'], step['arrival'], step['back_to']
    trigger, ret_trigger = door_trigger(door), door_trigger(ret)
    if trigger == 'player_touch' and (back['x'], back['y']) == (door['x'], door['y']):
        raise RecipeError('back_to is the door cell: a player_touch door would bounce the player straight back into the new area')
    if ret_trigger == 'player_touch' and (arrival['x'], arrival['y']) == (ret['x'], ret['y']):
        raise RecipeError('arrival is the return_door cell: a player_touch return door would bounce the player straight back out')
    blank_map = {'type': 'append_blank_map', 'template_map_id': step['template_map_id'], 'name': step['name'],
                 **{key: step[key] for key in ('width', 'height', 'tileset_id', 'parent_id', 'fill_floor') if key in step}}
    steps = [blank_map]
    donor = step.get('donor_event', door.get('template_event'))
    if donor is None:
        raise RecipeError('add_area needs donor_event or door template_event')
    if 'template_event' in door:
        template = door['template_event']
    else:
        steps.append({'type': 'append_blank_event', 'map_id': door['map_id'], 'donor_event': donor, 'x': door['blank_x'], 'y': door['blank_y']})
        template = {'from_step': len(steps)}
    steps.append({'type': 'append_staged_event', 'map_id': door['map_id'], 'template_event': template, 'x': door['x'], 'y': door['y'],
                  'name': door.get('name', f'{step["name"]} Door'[:100]),
                  'pages': [door_page(trigger, door.get('graphic'), {'map_id': {'from_step': 1}, 'x': arrival['x'], 'y': arrival['y'], 'direction': arrival['direction']},
                                      door.get('condition'), door.get('locked_text'))]})
    bx, by = (ret['blank_x'], ret['blank_y']) if 'blank_x' in ret else free_cell({(ret['x'], ret['y']), (arrival['x'], arrival['y'])})
    steps.append({'type': 'append_blank_event', 'map_id': {'from_step': 1}, 'donor_event': donor, 'donor_map_id': door['map_id'], 'x': bx, 'y': by})
    steps.append({'type': 'append_staged_event', 'map_id': {'from_step': 1}, 'template_event': {'from_step': len(steps)}, 'x': ret['x'], 'y': ret['y'],
                  'name': ret.get('name', f'{step["name"]} Exit'[:100]),
                  'pages': [door_page(ret_trigger, ret.get('graphic'), {'map_id': door['map_id'], 'x': back['x'], 'y': back['y'], 'direction': back['direction']})]})
    return steps


MACROS = {'add_treasure_chest': expand_chest, 'add_touch_trigger': expand_touch_trigger, 'add_monster': expand_monster, 'add_area': expand_area}


def failed_record(number, step_type, message, records):
    record = {'step': number, 'type': step_type, 'status': 'failed', 'source': None, 'directory': None, 'resolved_parameters': None, 'created_id': None,
              'spec': None, 'snapshot': None, 'plan': None, 'impact': None, 'audit': None, 'copy': None, 'exit_codes': {}, 'error': message}
    records.append(record)
    raise StepFailure(message)


def execute_area(number, step, title, source, work, ruby, created, recipe_dir, records, rtp, session=None, cleanup=False):
    """Run add_area as its ordinary transactions (new map, door, return door; see expand_area). Sub-steps refer to each other by local numbers.
    Returns a record whose created_id is the new map id and whose copy is the new current project."""
    try:
        sub_steps = expand_area(resolve_refs(step, created), source)
    except (RecipeError, ValueError) as error:
        failed_record(number, 'add_area', str(error), records)
    local, current, record = {}, source, None
    for position, sub in enumerate(sub_steps, 1):
        record = execute_step(number, sub, title, current, work, ruby, local, recipe_dir, records, 'abcdefgh'[position - 1], rtp, 'add_area', session, cleanup)
        local[position] = record['created_id']
        current = source if session else Path(record['copy'])
    return {'copy': None if session else str(current), 'created_id': local[1]}


def execute_chest(number, step, title, source, work, ruby, created, recipe_dir, records, rtp, session=None, cleanup=False):
    """Run a macro step (add_treasure_chest, add_touch_trigger) as its normal transactions: an optional append_blank_event, then one append_staged_event.
    Returns the staged step's record (its created id is the new event id and its copy the new current project)."""
    macro = step['type']
    if macro == 'add_area':
        return execute_area(number, step, title, source, work, ruby, created, recipe_dir, records, rtp, session, cleanup)
    try:
        blank, staged = MACROS[macro](resolve_refs(step, created), source)
    except (RecipeError, ValueError) as error:
        failed_record(number, macro, str(error), records)
    current = source
    if blank is not None:
        record = execute_step(number, blank, title, current, work, ruby, created, recipe_dir, records, 'a', rtp, macro, session, cleanup)
        staged['template_event'] = record['created_id']
        current = source if session else Path(record['copy'])
    return execute_step(number, staged, title, current, work, ruby, created, recipe_dir, records, 'b' if blank is not None else 'a', rtp, macro, session, cleanup)


def markdown_report(report):
    place = report.get('in_place')
    lines = ['# VX Ace recipe report', '', f'Recipe: {report.get("title") or "(untitled)"}', f'Status: **{report["status"]}**']
    if place:
        lines += ['Mode: **in place** (the project was written directly; there is no staged copy)',
                  f'Transactions promoted into the project: **{place["steps_promoted"]}**' + (f' (failed at step {place["failed_step"]})' if place.get('failed_step') else ''),
                  f'Rolled back to the start backup: **{place["rolled_back"]}**' + (f' ({place["rollback_note"]})' if place.get('rollback_note') else ''),
                  f'Backup: `{place["backup_dir"]}`', f'Undo record: `{place["record"]}`' + (f' (record_id `{place["record_id"]}`)' if place.get('record_id') else ''),
                  'Undo: `python tools/vxace_recipe.py undo --record <record> --confirm-in-place <project folder name>`', '']
    else:
        lines += [f'Original unchanged: **{report["original_unchanged"]}**', 'Mutation performed on original: **False**',
                  f'Final copy: `{report["final_copy"]}`' if report['final_copy'] else 'Final copy: none', '']
    if report.get('error'):
        lines += [f'Error: {report["error"]}', '']
    lines += ['## Steps', '']
    for s in report['steps']:
        lines.append(f'### Step {s["step"]}{s.get("part", "")}: {s["type"]} ({s["status"]})' + (f' [{s["macro"]}]' if s.get('macro') else ''))
        lines.append(f'- Resolved parameters: `{json.dumps(s["resolved_parameters"], ensure_ascii=False)[:400]}`')
        lines.append(f'- Created id: {s["created_id"]}')
        lines.append(f'- Spec: {s["spec"]}')
        lines.append('- Exit codes: ' + ', '.join(f'{k} {v}' for k, v in s['exit_codes'].items()))
        lines.append(f'- Audit: {s["audit"]}')
        lines.append(f'- Promoted files: {", ".join(s["promoted_files"])}' if 'promoted_files' in s else f'- Copy: {s["copy"]}' + (' (deleted by cleanup)' if s.get('copy_removed') else ''))
        if s.get('note'):
            lines.append(f'- Note: {s["note"]}')
        if s['error']:
            lines.append(f'- Error: {s["error"]}')
        lines.append('')
    if report['smoke']:
        lines += ['## Smoke', '', f'`{json.dumps(report["smoke"])}`', '']
    lines += ['Review every step\'s plan and impact before using the final copy. A pass is not runtime proof.']
    return '\n'.join(lines) + '\n'


STEP_PATH_FIELDS = ('source', 'directory', 'spec', 'snapshot', 'plan', 'impact', 'audit', 'copy')


def map_report_paths(report, convert):
    """Copy of a report with `convert` applied to every file or folder path field (the step records, final copy, validation and smoke outputs)."""
    out = copymod.deepcopy(report)
    if out.get('final_copy'):
        out['final_copy'] = convert(out['final_copy'])
    for block, keys in (('validation', ('output',)), ('smoke', ('json', 'markdown'))):
        if isinstance(out.get(block), dict):
            for key in keys:
                if out[block].get(key):
                    out[block][key] = convert(out[block][key])
    for record in out.get('steps') or []:
        for key in STEP_PATH_FIELDS:
            if record.get(key):
                record[key] = convert(record[key])
        for side in record.get('skipped_side_specs') or []:
            if side.get('file'):
                side['file'] = convert(side['file'])
    return out


def report_for_disk(report, work):
    """Portable form of the report: paths below the work folder become relative to it (the top-level `work` stays absolute, for information only)."""
    def relative(value):
        try:
            return Path(value).relative_to(work).as_posix()
        except ValueError:
            return value
    out = map_report_paths(report, relative)
    out['paths'] = 'relative'
    return out


def load_report(path):
    """Read a recipe-report.json and make every path absolute: relative paths resolve against the report file's own folder, absolute paths (older reports) are kept."""
    path = Path(path)
    base = path.resolve().parent

    def absolute(value):
        return value if Path(value).is_absolute() else str(base / value)
    return map_report_paths(read_json(path), absolute)


def run_recipe(recipe_path, project, work, ruby=None, smoke=None, rtp=None, in_place=None, cleanup=True):
    """Execute the recipe. Returns the report dict; its status is 'pass', 'step_failed', 'validation_refused', 'smoke_failed' or 'error'.
    `in_place` (None, or {'backup_root', 'confirm', 'rollback_on_failure'}) selects in-place mode; `cleanup` (copy-chain mode) deletes each passed
    step's index folders and, at the end, every intermediate step copy except the final one."""
    recipe_path = Path(recipe_path).resolve()
    recipe = load_recipe(recipe_path)
    steps = recipe['steps']
    project, work = unlinked(project), unlinked(work).resolve()
    if rtp is not None:
        rtp = unlinked(rtp).resolve()
        if not rtp.is_dir() or rtp == work or work in rtp.parents or rtp in work.parents:
            raise RecipeError('--rtp must be an existing directory outside the work directory')
    if project.is_file() and project.suffix.lower() == '.rvproj2':
        project = project.parent
    project = project.resolve()
    if not (project / 'Data').is_dir():
        raise RecipeError('Expected a VX Ace project with Data/')
    if work.exists() or work == project or project in work.parents or work in project.parents:
        raise RecipeError('Use a new work directory outside the original project')
    ruby = ruby or shutil.which('ruby')
    session = None
    if in_place:
        if in_place.get('confirm') != project.name:
            raise RecipeError(f'--in-place writes into the project itself: pass --confirm-in-place {project.name} (the project folder name) to confirm')
        backup_root = unlinked(in_place['backup_root']).resolve()
        if backup_root == work or work in backup_root.parents or backup_root in work.parents:
            raise RecipeError('--backup-root must be outside the work directory')
        try:
            adopt.check_project(project)
            adopt.check_backup_root(backup_root, project)
            adopt.refuse_if_running()
        except adopt.Refused as refusal:
            raise RecipeError(f'in-place run refused ({refusal.reason}): {refusal}')
        except ValueError as error:
            raise RecipeError(f'in-place run refused: {error}')
        before = None
    else:
        before = current_inventory(project)
    work.mkdir(parents=True)
    records = []
    report = {'version': VERSION, 'title': recipe.get('title'), 'recipe': str(recipe_path), 'status': 'error', 'error': None,
              'project': str(project), 'work': str(work), 'validation': None, 'steps': records, 'final_copy': None,
              'smoke': None, 'original_unchanged': None, 'original_files_checked': len(before) if before is not None else None,
              'mutation_performed_on_original': False}
    if in_place:
        report['mode'] = 'in_place'
        report['in_place'] = {'project': str(project), 'backup_root': str(backup_root), 'backup_dir': None, 'record': None, 'record_id': None,
                              'rollback_on_failure': bool(in_place.get('rollback_on_failure')), 'rolled_back': False, 'rollback_note': None,
                              'steps_promoted': 0, 'failed_step': None, 'files_changed': [], 'verified': None, 'final_index': None}
    else:
        report['mode'] = 'copy_chain'
    created = {}
    current = project
    cleanup_copies = bool(cleanup) and not in_place
    try:
        code, out, err = run_tool(work / 'logs', 'validation', 'vxace_project_validator.py',
                                  [project, '--output', work / 'validation', '--backend', 'python', *(['--ruby', ruby] if ruby else [])])
        ready = False
        if code == 0:
            ready = bool(read_json(work / 'validation/validation.json').get('copy_mutation_ready'))
        report['validation'] = {'exit_code': code, 'copy_mutation_ready': ready, 'output': str(work / 'validation')}
        if not ready:
            report['status'] = 'validation_refused'
            report['error'] = f'original project is not copy-mutation ready: {last_line(err, out)}'
        else:
            if in_place:
                backup_dir = backup_root / f'{adopt.utc_now().strftime("%Y%m%dT%H%M%SZ")}-recipe-{sha256(recipe_path.read_bytes())[:12]}'
                if backup_dir.exists():
                    raise RecipeError(f'backup folder already exists: {backup_dir}')
                session = Session(project, work, backup_dir, recipe_path)
                session.back_up_start()
                report['in_place'].update(backup_dir=str(backup_dir), record=str(session.record_path), record_id=session.record_id)
            report['status'] = 'pass'
            for number, step in enumerate(steps, 1):
                try:
                    if step['type'] in MACROS:
                        record = execute_chest(number, step, recipe.get('title'), current, work, ruby, created, recipe_path.parent, records, rtp, session, cleanup_copies)
                    else:
                        record = execute_step(number, step, recipe.get('title'), current, work, ruby, created, recipe_path.parent, records, rtp=rtp,
                                              session=session, cleanup=cleanup_copies)
                except StepFailure as failure:
                    report['status'] = 'step_failed'
                    report['error'] = f'step {number} ({step["type"]}): {failure}'
                    if in_place:
                        report['in_place']['failed_step'] = number
                    break
                if record['created_id'] is not None:
                    created[number] = record['created_id']
                if not in_place:
                    current = Path(record['copy'])
                    report['final_copy'] = str(current)
            if in_place and report['status'] == 'pass':
                final_index = work / 'final-index'
                code, out, err = run_tool(work / 'logs', 'final-index', 'vxace_project_reader.py', [project, '--output', final_index, *(['--ruby', ruby] if ruby else [])])
                report['in_place']['final_index'] = {'exit_code': code, 'output': str(final_index)}
                if code != 0:
                    report['status'] = 'error'
                    report['error'] = f'final re-index of the project failed (exit {code}): {last_line(err, out)}'
            if report['status'] == 'pass' and smoke:
                report['smoke'] = run_smoke(project if in_place else current, work, ruby, smoke, delete_stage=bool(in_place))
                if report['smoke']['status'] != 'pass':
                    report['status'] = 'smoke_failed'
                    report['error'] = 'smoke run did not pass: ' + str(report['smoke'].get('status'))
    except Exception as error:
        report['status'] = 'error'
        report['error'] = f'{type(error).__name__}: {error}'
    finally:
        if in_place:
            finish_in_place(report, session)
        else:
            report['original_unchanged'] = current_inventory(project) == before
            if not report['original_unchanged']:
                report['status'] = 'error'
                report['error'] = 'ORIGINAL PROJECT FILES CHANGED'
            if cleanup_copies:
                # Keep the final copy and, when a macro step failed part-way, the last good sub-step copy (the state the failure started from).
                last_ok = next((r['copy'] for r in reversed(records) if r['status'] == 'ok' and r.get('copy')), None)
                for record in records:
                    if record.get('copy') and record['copy'] not in (report['final_copy'], last_ok) and Path(record['copy']).is_dir():
                        remove_tree(record['copy'])
                        record['copy_removed'] = True
        saved = report_for_disk(report, work)
        (work / 'recipe-report.json').write_text(json.dumps(saved, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        (work / 'recipe-report.md').write_text(markdown_report(saved), encoding='utf-8')
    return report


def finish_in_place(report, session):
    """Roll back when asked and the run failed, then check that the project holds exactly the expected bytes and fill the in-place report block."""
    place = report['in_place']
    if session is None:
        return
    remove_tree(session.tmp_copy)
    failed = report['status'] in ('step_failed', 'error')
    if failed and place['rollback_on_failure'] and session.files:
        try:
            result = adopt.undo(session.project, session.record_path, session.record_id)
            place['rolled_back'] = True
            place['rollback_note'] = f'restored {result["files"]} file(s) from the start backup'
        except (adopt.Refused, ValueError, OSError, KeyError) as error:
            place['rollback_note'] = f'ROLLBACK FAILED, the project keeps the promoted steps; undo manually with the record ({error})'
            report['error'] = f'{report["error"]}; {place["rollback_note"]}'
    elif failed and place['rollback_on_failure']:
        place['rolled_back'] = True
        place['rollback_note'] = 'no step had been promoted; the project was never changed'
    place['steps_promoted'] = 0 if place['rolled_back'] else session.promoted
    place['files_changed'] = [] if place['rolled_back'] else sorted(session.files)
    problems = session.verify_expected(place['rolled_back'])
    place['verified'] = not problems
    report['mutation_performed_on_original'] = bool(session.files)
    place['record_id'] = session.record_id
    if problems:
        report['status'] = 'error'
        report['error'] = 'PROJECT DIFFERS FROM THE EXPECTED STATE: ' + ', '.join(problems)


def run_smoke(last_copy, work, ruby, options, delete_stage=False):
    """Stage and run the existing smoke harness on the last copy (the copy itself is left untouched; staging clones it).
    In-place mode passes the project itself and `delete_stage`: the single staged copy is deleted afterwards, the results are kept."""
    smoke_work = work / 'smoke'
    try:
        return run_smoke_staged(last_copy, work, ruby, options, smoke_work)
    finally:
        if delete_stage:
            remove_tree(smoke_work)


def run_smoke_staged(last_copy, work, ruby, options, smoke_work):
    stage_args = ['stage', last_copy, '--work', smoke_work, *(['--ruby', ruby] if ruby else [])]
    if options.get('suite'):
        stage_args += ['--suite', options['suite']]
    result = {'status': 'error', 'stage_exit_code': None, 'run_exit_code': None, 'json': None, 'markdown': None}
    code, out, err = run_tool(work / 'logs', 'smoke-stage', 'vxace_smoke.py', stage_args)
    result['stage_exit_code'] = code
    if code != 0:
        result['error'] = last_line(err, out)
        return result
    run_args = ['run', smoke_work, '--mode', options['mode'], '--frames', options['frames'], '--auto-confirm', options['auto_confirm'],
                '--json', work / 'smoke-result.json', '--markdown', work / 'smoke-result.md']
    if options.get('launcher'):
        run_args += ['--launcher', json.dumps(options['launcher'])]
    code, out, err = run_tool(work / 'logs', 'smoke-run', 'vxace_smoke.py', run_args)
    result['run_exit_code'] = code
    result['json'], result['markdown'] = str(work / 'smoke-result.json'), str(work / 'smoke-result.md')
    if (work / 'smoke-result.json').is_file():
        data = read_json(work / 'smoke-result.json')
        result.update(status=data['status'], counts=data['counts'], problems=data['problems'], result=data)
    else:
        result['error'] = last_line(err, out)
    return result


def json_argv(text):
    value = json.loads(text)
    if not isinstance(value, list) or not value or not all(isinstance(i, str) for i in value):
        raise argparse.ArgumentTypeError('expected a JSON list of strings')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    item = commands.add_parser('validate', help='validate a recipe file without touching any project')
    item.add_argument('recipe')
    item = commands.add_parser('plan', help='dry-run: predict what run would do, without creating any project copy')
    item.add_argument('recipe')
    item.add_argument('--project', required=True)
    item.add_argument('--output', required=True)
    item.add_argument('--ruby', default=shutil.which('ruby'))
    item.add_argument('--rtp', help='explicit read-only RTP root, used only to bind page character graphics that are not in the project')
    item.add_argument('--in-place', action='store_true', help='predict an in-place run (no project copies are kept; the backup is reported)')
    item.add_argument('--backup-root', help='with --in-place: where the start backup would go')
    item = commands.add_parser('run')
    item.add_argument('recipe')
    item.add_argument('--project', required=True)
    item.add_argument('--work', required=True)
    item.add_argument('--ruby', default=shutil.which('ruby'))
    item.add_argument('--rtp', help='explicit read-only RTP root, used only to bind page character graphics that are not in the project')
    item.add_argument('--in-place', action='store_true', help='write the steps directly into --project (one start backup, undo record); needs --backup-root and --confirm-in-place')
    item.add_argument('--backup-root', help='in-place: folder (outside the project) that receives the timestamped start backup')
    item.add_argument('--confirm-in-place', help='in-place: must equal the project folder name, e.g. Project3')
    item.add_argument('--rollback-on-failure', action=argparse.BooleanOptionalAction, default=True,
                      help='in-place: restore the start backup when a step fails (default on; --no-rollback-on-failure keeps the verified steps before the failure)')
    item.add_argument('--cleanup', action=argparse.BooleanOptionalAction, default=True,
                      help='copy-chain: delete each passed step\'s index folders and, at the end, every intermediate step copy except the final one (default on)')
    item.add_argument('--keep-intermediate', action='store_true', help='copy-chain: keep every step copy and index (same as --no-cleanup)')
    item.add_argument('--smoke-suite')
    item.add_argument('--smoke-mode', choices=['test', 'normal'])
    item.add_argument('--smoke-frames', type=int, default=600)
    item.add_argument('--smoke-auto-confirm', type=int, default=0)
    item.add_argument('--smoke-launcher', type=json_argv, help=argparse.SUPPRESS)
    item = commands.add_parser('undo', help='revert an in-place run completely from its undo record (restores the start backup)')
    item.add_argument('--record', required=True, help='adopt-record.json inside the in-place run\'s backup folder')
    item.add_argument('--confirm-in-place', required=True, help='the project folder name, e.g. Project3')
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate':
            steps = load_recipe(args.recipe)['steps']
            print(json.dumps({'status': 'ok', 'steps': len(steps)}))
            return 0
        if args.command == 'undo':
            try:
                record = adopt.load_record(args.record)
                if args.confirm_in_place != Path(record['project']).name:
                    raise adopt.Refused('wrong_confirm', '--confirm-in-place must equal the project folder name: ' + Path(record['project']).name)
                print(json.dumps(adopt.undo(record['project'], args.record, record['record_id'])))
                return 0
            except adopt.Refused as refusal:
                print(json.dumps({'status': 'refused', 'reason': refusal.reason, 'detail': str(refusal), 'items': refusal.details}), file=sys.stderr)
                return 3
        if args.command == 'plan':
            import vxace_recipe_plan
            if args.backup_root and not args.in_place:
                raise RecipeError('--backup-root belongs to --in-place')
            plan = vxace_recipe_plan.plan_recipe(args.recipe, args.project, args.output, args.ruby, args.rtp, args.in_place, args.backup_root)
            summary = plan['summary']
            print(json.dumps({'version': vxace_recipe_plan.VERSION, 'status': plan['status'], 'steps_planned': summary['steps_planned'], 'refused_step': plan['refused_step'],
                              'transactions': summary['transactions'], 'files_changed': summary['files_changed'], 'original_unchanged': plan['original_unchanged'],
                              'plan': str(Path(plan['output']) / 'recipe-plan.json')}))
            if plan['status'] == 'error':
                print('Plan error: ' + str(plan['error']), file=sys.stderr)
                return 2
            if plan['status'] != 'ok':
                print('Plan stopped: ' + str(plan['error']), file=sys.stderr)
                return 3
            return 0
        if (args.smoke_suite or args.smoke_launcher) and not args.smoke_mode:
            raise RecipeError('--smoke-suite requires --smoke-mode')
        smoke = None
        if args.smoke_mode:
            smoke = {'suite': args.smoke_suite, 'mode': args.smoke_mode, 'frames': args.smoke_frames,
                     'auto_confirm': args.smoke_auto_confirm, 'launcher': args.smoke_launcher}
        in_place = None
        if args.in_place:
            if not args.backup_root or not args.confirm_in_place:
                raise RecipeError('--in-place needs --backup-root and --confirm-in-place <project folder name>')
            in_place = {'backup_root': args.backup_root, 'confirm': args.confirm_in_place, 'rollback_on_failure': args.rollback_on_failure}
        elif args.backup_root or args.confirm_in_place:
            raise RecipeError('--backup-root and --confirm-in-place belong to --in-place')
        report = run_recipe(args.recipe, args.project, args.work, args.ruby, smoke, args.rtp, in_place, args.cleanup and not args.keep_intermediate)
    except Exception as error:
        print('Recipe refused: ' + str(error), file=sys.stderr)
        return 2
    summary = {'version': VERSION, 'status': report['status'], 'steps_completed': sum(s['status'] == 'ok' for s in report['steps']),
               'final_copy': report['final_copy'], 'original_unchanged': report['original_unchanged'],
               'report': str(Path(report['work']) / 'recipe-report.json')}
    if report['mode'] == 'in_place':
        place = report['in_place']
        summary.update(mode='in_place', failed_step=place['failed_step'], rolled_back=place['rolled_back'], backup_dir=place['backup_dir'], record=place['record'], record_id=place['record_id'])
    print(json.dumps(summary))
    if report['status'] == 'error':
        print('Recipe error: ' + str(report['error']), file=sys.stderr)
        return 2
    if report['status'] != 'pass':
        print('Recipe stopped: ' + str(report['error']), file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
