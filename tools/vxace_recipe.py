#!/usr/bin/env python3
"""Run a recipe: a list of high-level steps, each applied as its own guarded single-change transaction on a chain of disposable copies.

Adds no mutation logic. Every step runs the existing Project Reader, the operation's read-only snapshot CLI, builds the exact spec
from that snapshot, then runs the patch planner, impact report and the Python copy patcher. The original project is never written."""
from __future__ import annotations
import argparse
import copy as copymod
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from vxace_copy_patcher import current_inventory
from vxace_database_append import LIST_TABLES, ref_field, required_refs
from vxace_index_query import unlinked

VERSION = '1.22.0'
ROOT = Path(__file__).resolve().parent
STEP_TIMEOUT = 1800
MAX_STEPS = 50
TABLES = ('enemies', 'items', 'skills', 'states', 'weapons', 'armors', 'troops')
STEP_KEYS = {
    'append_entry': ({'type', 'table', 'template_id', 'overrides'}, {'type', 'table', 'template_id', 'overrides'}),
    'append_key_item': ({'type', 'template_item', 'name', 'description'}, {'type', 'template_item', 'name', 'description'}),
    'append_learning': ({'type', 'class_id', 'skill_id', 'level'}, {'type', 'class_id', 'skill_id', 'level'}),
    'append_encounter': ({'type', 'map_id', 'troop_id', 'weight'}, {'type', 'map_id', 'troop_id', 'weight', 'region_ids', 'encounter_step'}),
    'append_dialogue_event': ({'type', 'map_id', 'template_event', 'x', 'y', 'name', 'lines'}, {'type', 'map_id', 'template_event', 'x', 'y', 'name', 'lines'}),
    'append_staged_event': ({'type', 'map_id', 'template_event', 'x', 'y', 'name', 'pages'}, {'type', 'map_id', 'template_event', 'x', 'y', 'name', 'pages'}),
    'append_common_event': ({'type', 'name', 'trigger', 'commands'}, {'type', 'name', 'trigger', 'commands', 'switch_id'}),
    'append_blank_event': ({'type', 'map_id', 'donor_event', 'x', 'y'}, {'type', 'map_id', 'donor_event', 'x', 'y', 'name'}),
    'add_treasure_chest': ({'type', 'map_id', 'x', 'y', 'name', 'contents'},
                           {'type', 'map_id', 'x', 'y', 'name', 'contents', 'graphic', 'template_event', 'donor_event', 'blank_x', 'blank_y'}),
    'add_shop': ({'type', 'map_id', 'event_id', 'goods', 'purchase_only'}, {'type', 'map_id', 'event_id', 'goods', 'purchase_only'}),
    'insert_script': ({'type', 'name', 'source_file'}, {'type', 'name', 'source_file'}),
    'set_map_display_name': ({'type', 'map_id', 'name'}, {'type', 'map_id', 'name'}),
    'text_import': ({'type', 'csv'}, {'type', 'csv', 'allow_shorter'}),
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
        if is_ref(op.get('common_event')):
            check_ref(op['common_event'], number, steps, 'common_events', 'common_event id')
            op['common_event'] = 0
        for holder, key, goods in ((op, 'item', 'item'), (op['if'] if isinstance(op.get('if'), dict) else {}, 'has_item', 'item'),
                                   (op, 'weapon', 'weapon'), (op, 'armor', 'armor')):
            if is_ref(holder.get(key)):
                check_goods_ref(holder[key], number, steps, goods)
                holder[key] = 0


CHEST_KINDS = ('item', 'weapon', 'armor')
CHEST_GRAPHIC = {'character_name': '!Chest', 'character_index': 0, 'direction': 2, 'pattern': 0}
CHEST_OPTIONS = {'direction_fix': True, 'walk_anime': False, 'priority': 'same'}
CHEST_TABLES = {'item': 'items', 'weapon': 'weapons', 'armor': 'armors'}


def validate_chest(step, number, steps):
    """Structural rules of the add_treasure_chest macro (the guarded tools re-check everything it expands to)."""
    if not is_int(step['map_id']) or not 1 <= step['map_id'] <= 999:
        raise RecipeError(f'step {number}: map_id must be an integer 1..999')
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
    shadow = copymod.deepcopy(step)
    if is_ref(shadow.get('template_event')):
        shadow['template_event'] = 0
    for kind in CHEST_KINDS:
        if is_ref(shadow['contents'].get(kind)):
            shadow['contents'][kind] = 0
    if contains_ref_key(shadow):
        raise RecipeError(f'step {number}: from_step is only allowed for template_event and the contents id')


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
            if contains_ref_key(shadow):
                raise RecipeError(f'step {number}: from_step is only allowed for troop members enemy_id and effects/features data_id')
        elif kind == 'append_key_item':
            if not is_int(step['template_item']) or step['template_item'] < 1:
                raise RecipeError(f'step {number}: template_item must be a positive integer')
            for key in ('name', 'description'):
                if not isinstance(step[key], str):
                    raise RecipeError(f'step {number}: {key} must be a string')
        elif kind == 'append_learning':
            if not is_int(step['class_id']) or step['class_id'] < 1:
                raise RecipeError(f'step {number}: class_id must be a positive integer')
            if is_ref(step['skill_id']):
                check_ref(step['skill_id'], number, steps, 'skills', 'skill_id')
            elif not is_int(step['skill_id']) or step['skill_id'] < 1:
                raise RecipeError(f'step {number}: skill_id must be a positive integer or {{"from_step": N}}')
            if not is_int(step['level']):
                raise RecipeError(f'step {number}: level must be an integer')
        elif kind == 'append_encounter':
            if not is_int(step['map_id']) or not 1 <= step['map_id'] <= 999:
                raise RecipeError(f'step {number}: map_id must be an integer 1..999')
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
            if not is_int(step['map_id']) or not 1 <= step['map_id'] <= 999:
                raise RecipeError(f'step {number}: map_id must be an integer 1..999')
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
            if contains_ref_key({k: v for k, v in step.items() if k != 'template_event'}):
                raise RecipeError(f'step {number}: from_step is only allowed for template_event')
        elif kind == 'append_staged_event':
            if not is_int(step['map_id']) or not 1 <= step['map_id'] <= 999:
                raise RecipeError(f'step {number}: map_id must be an integer 1..999')
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
            if contains_ref_key({**{k: v for k, v in step.items() if k not in ('template_event', 'pages')}, 'pages': shadow}):
                raise RecipeError(f'step {number}: from_step is only allowed for template_event, battle troop ids, item/weapon/armor ids and common event ids in pages')
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
            if not is_int(step['map_id']) or not 1 <= step['map_id'] <= 999:
                raise RecipeError(f'step {number}: map_id must be an integer 1..999')
            if not is_int(step['donor_event']) or not 1 <= step['donor_event'] <= 999:
                raise RecipeError(f'step {number}: donor_event must be an integer 1..999')
            for key in ('x', 'y'):
                if not is_int(step[key]) or not 0 <= step[key] <= 9999:
                    raise RecipeError(f'step {number}: {key} must be a non-negative integer')
            if 'name' in step and (not isinstance(step['name'], str) or not 1 <= len(step['name']) <= 100):
                raise RecipeError(f'step {number}: name must be a string of 1..100 characters')
        elif kind == 'add_treasure_chest':
            validate_chest(step, number, steps)
        elif kind == 'add_shop':
            if not is_int(step['map_id']) or not 1 <= step['map_id'] <= 999:
                raise RecipeError(f'step {number}: map_id must be an integer 1..999')
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
            shadow = copymod.deepcopy(step)
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
            if not is_int(step['map_id']) or not 1 <= step['map_id'] <= 999:
                raise RecipeError(f'step {number}: map_id must be an integer 1..999')
            if not isinstance(step['name'], str):
                raise RecipeError(f'step {number}: name must be a string')
        elif kind == 'text_import':
            if not isinstance(step['csv'], str) or not step['csv']:
                raise RecipeError(f'step {number}: csv must be a non-empty string')
            if 'allow_shorter' in step and type(step['allow_shorter']) is not bool:
                raise RecipeError(f'step {number}: allow_shorter must be a boolean')
        if kind not in ('append_entry', 'append_encounter', 'append_learning', 'add_shop', 'append_dialogue_event', 'append_staged_event', 'append_common_event', 'add_treasure_chest') and contains_ref_key(step):
            raise RecipeError(f'step {number}: from_step is not allowed in a {kind} step')
        if kind == 'append_encounter' and contains_ref_key({k: v for k, v in step.items() if k != 'troop_id'}):
            raise RecipeError(f'step {number}: from_step is only allowed for troop_id')
        if kind == 'append_learning' and contains_ref_key({k: v for k, v in step.items() if k != 'skill_id'}):
            raise RecipeError(f'step {number}: from_step is only allowed for skill_id')
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
        mutation['overrides'] = step['overrides']
        change = {'kind': 'database_entry', 'locator': {'table': step['table']},
                  'proposal': f'Recipe step {number}: append one {step["table"]} entry cloned from template {step["template_id"]}.',
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
    elif kind == 'append_blank_event':
        change = {'kind': 'map_event', 'locator': {'map_id': step['map_id']},
                  'proposal': f'Recipe step {number}: append one blank event "{step.get("name", snapshot["default_name"])}" to map {step["map_id"]} using donor event {step["donor_event"]} for schema only.',
                  'mutation': {'action': 'append_blank_event', 'donor_event_id': step['donor_event'], 'new_id': snapshot['next_event_id'],
                               'name': step.get('name', snapshot['default_name']), 'x': step['x'], 'y': step['y'],
                               'expected_map_sha256': snapshot['map_sha256'], 'expected_donor_sha256': snapshot['donor_sha256']}}
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


def execute_step(number, step, title, source, work, ruby, created, recipe_dir, records, tag='', rtp=None):
    """Run one step as a normal transaction. Returns its report record; raises StepFailure after filling the record.
    `tag` ('a', 'b') names the sub-steps of a macro step; `rtp` is the optional explicit RTP root for page graphics."""
    directory = work / f'step-{number:02d}{tag}'
    directory.mkdir()
    logs = directory / 'logs'
    index, copy, audit = directory / 'index', directory / 'copy', directory / 'audit'
    record = {'step': number, 'type': step['type'], 'status': 'running', **({'macro': 'add_treasure_chest', 'part': tag} if tag else {}), 'source': str(source), 'directory': str(directory),
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
                script, args, name = 'vxace_database_entries.py', [index, '--project', source, *table_args], 'item-entry-snapshot'
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
                                                              '--donor-event', resolved['donor_event']], 'map-event-snapshot')
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
                                                  *(['--rtp', rtp] if rtp and kind == 'append_staged_event' and graphic_names(resolved['pages']) else [])])
        record['audit'] = str(audit / 'audit.json')
        record['copy'] = str(copy)
        if not copy.is_dir():
            fail('copy patcher reported success but the copy is missing')
        if record['created_id'] is not None:
            try:
                audit_change = read_json(audit / 'audit.json')['changes'][0]
                audited = (audit_change['map_event']['new_id'] if kind in ('append_dialogue_event', 'append_blank_event', 'append_staged_event')
                           else audit_change['common_event']['new_id'] if kind == 'append_common_event' else audit_change['entry']['created_id'])
            except (OSError, KeyError, IndexError, ValueError):
                audited = None
            if audited != record['created_id']:
                fail(f'audit created_id {audited!r} does not match the snapshot id {record["created_id"]!r}')
        record['status'] = 'ok'
        return record
    except StepFailure:
        raise
    except Exception as error:  # unexpected tool-side problem: still a failed step with a record
        record['status'] = 'failed'
        record['error'] = f'{type(error).__name__}: {error}'
        raise StepFailure(record['error'])


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


def failed_record(number, step_type, message, records):
    record = {'step': number, 'type': step_type, 'status': 'failed', 'source': None, 'directory': None, 'resolved_parameters': None, 'created_id': None,
              'spec': None, 'snapshot': None, 'plan': None, 'impact': None, 'audit': None, 'copy': None, 'exit_codes': {}, 'error': message}
    records.append(record)
    raise StepFailure(message)


def execute_chest(number, step, title, source, work, ruby, created, recipe_dir, records, rtp):
    """Run an add_treasure_chest step as its normal transactions: an optional append_blank_event, then one append_staged_event.
    Returns the staged step's record (its created id is the chest event id and its copy the new current project)."""
    try:
        blank, staged = expand_chest(resolve_refs(step, created), source)
    except (RecipeError, ValueError) as error:
        failed_record(number, 'add_treasure_chest', str(error), records)
    current = source
    if blank is not None:
        record = execute_step(number, blank, title, current, work, ruby, created, recipe_dir, records, 'a', rtp)
        staged['template_event'] = record['created_id']
        current = Path(record['copy'])
    return execute_step(number, staged, title, current, work, ruby, created, recipe_dir, records, 'b' if blank is not None else 'a', rtp)


def markdown_report(report):
    lines = ['# VX Ace recipe report', '', f'Recipe: {report.get("title") or "(untitled)"}', f'Status: **{report["status"]}**',
             f'Original unchanged: **{report["original_unchanged"]}**', 'Mutation performed on original: **False**',
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
        lines.append(f'- Copy: {s["copy"]}')
        if s.get('note'):
            lines.append(f'- Note: {s["note"]}')
        if s['error']:
            lines.append(f'- Error: {s["error"]}')
        lines.append('')
    if report['smoke']:
        lines += ['## Smoke', '', f'`{json.dumps(report["smoke"])}`', '']
    lines += ['Review every step\'s plan and impact before using the final copy. A pass is not runtime proof.']
    return '\n'.join(lines) + '\n'


def run_recipe(recipe_path, project, work, ruby=None, smoke=None, rtp=None):
    """Execute the recipe. Returns the report dict; its status is 'pass', 'step_failed', 'validation_refused', 'smoke_failed' or 'error'."""
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
    before = current_inventory(project)
    work.mkdir(parents=True)
    records = []
    report = {'version': VERSION, 'title': recipe.get('title'), 'recipe': str(recipe_path), 'status': 'error', 'error': None,
              'project': str(project), 'work': str(work), 'validation': None, 'steps': records, 'final_copy': None,
              'smoke': None, 'original_unchanged': None, 'original_files_checked': len(before),
              'mutation_performed_on_original': False}
    created = {}
    current = project
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
            report['status'] = 'pass'
            for number, step in enumerate(steps, 1):
                try:
                    if step['type'] == 'add_treasure_chest':
                        record = execute_chest(number, step, recipe.get('title'), current, work, ruby, created, recipe_path.parent, records, rtp)
                    else:
                        record = execute_step(number, step, recipe.get('title'), current, work, ruby, created, recipe_path.parent, records, rtp=rtp)
                except StepFailure as failure:
                    report['status'] = 'step_failed'
                    report['error'] = f'step {number} ({step["type"]}): {failure}'
                    break
                if record['created_id'] is not None:
                    created[number] = record['created_id']
                current = Path(record['copy'])
                report['final_copy'] = str(current)
            if report['status'] == 'pass' and smoke:
                report['smoke'] = run_smoke(current, work, ruby, smoke)
                if report['smoke']['status'] != 'pass':
                    report['status'] = 'smoke_failed'
                    report['error'] = 'smoke run did not pass: ' + str(report['smoke'].get('status'))
    except Exception as error:
        report['status'] = 'error'
        report['error'] = f'{type(error).__name__}: {error}'
    finally:
        report['original_unchanged'] = current_inventory(project) == before
        if not report['original_unchanged']:
            report['status'] = 'error'
            report['error'] = 'ORIGINAL PROJECT FILES CHANGED'
        (work / 'recipe-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        (work / 'recipe-report.md').write_text(markdown_report(report), encoding='utf-8')
    return report


def run_smoke(last_copy, work, ruby, options):
    """Stage and run the existing smoke harness on the last copy (the copy itself is left untouched; staging clones it)."""
    smoke_work = work / 'smoke'
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
    item = commands.add_parser('run')
    item.add_argument('recipe')
    item.add_argument('--project', required=True)
    item.add_argument('--work', required=True)
    item.add_argument('--ruby', default=shutil.which('ruby'))
    item.add_argument('--rtp', help='explicit read-only RTP root, used only to bind page character graphics that are not in the project')
    item.add_argument('--smoke-suite')
    item.add_argument('--smoke-mode', choices=['test', 'normal'])
    item.add_argument('--smoke-frames', type=int, default=600)
    item.add_argument('--smoke-auto-confirm', type=int, default=0)
    item.add_argument('--smoke-launcher', type=json_argv, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate':
            steps = load_recipe(args.recipe)['steps']
            print(json.dumps({'status': 'ok', 'steps': len(steps)}))
            return 0
        if (args.smoke_suite or args.smoke_launcher) and not args.smoke_mode:
            raise RecipeError('--smoke-suite requires --smoke-mode')
        smoke = None
        if args.smoke_mode:
            smoke = {'suite': args.smoke_suite, 'mode': args.smoke_mode, 'frames': args.smoke_frames,
                     'auto_confirm': args.smoke_auto_confirm, 'launcher': args.smoke_launcher}
        report = run_recipe(args.recipe, args.project, args.work, args.ruby, smoke, args.rtp)
    except Exception as error:
        print('Recipe refused: ' + str(error), file=sys.stderr)
        return 2
    print(json.dumps({'version': VERSION, 'status': report['status'], 'steps_completed': sum(s['status'] == 'ok' for s in report['steps']),
                      'final_copy': report['final_copy'], 'original_unchanged': report['original_unchanged'],
                      'report': str(Path(report['work']) / 'recipe-report.json')}))
    if report['status'] == 'error':
        print('Recipe error: ' + str(report['error']), file=sys.stderr)
        return 2
    if report['status'] != 'pass':
        print('Recipe stopped: ' + str(report['error']), file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
