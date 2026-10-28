#!/usr/bin/env python3
"""Guarded append-only native template clones for Enemies, Skills, States, Weapons and Armors."""
from __future__ import annotations
import hashlib
import math
import re

VERSION = '1.9.0'
ACTION = 'append_database_entry'
MUTATION_FIELDS = {'action','template_id','new_id','expected_array_sha256','expected_template_sha256','overrides'}
BASE = {'id','name','icon_index','description','features','note'}
USABLE = {'scope','occasion','speed','success_rate','repeats','tp_gain','hit_type','animation_id','damage','effects'}
# Field sets observed in editor-saved VX Ace data: RPG::Enemy has no icon_index/description but
# keeps the legacy hit/eva integers; RPG::State has no description but keeps a legacy release_by_damage boolean.
TABLES = {
    'enemies': ('RPG::Enemy', {'id','name','features','note','battler_name','battler_hue','params','exp','gold',
                               'drop_items','actions','hit','eva'}),
    'skills': ('RPG::Skill', BASE | USABLE | {'stype_id','mp_cost','tp_cost','message1','message2','required_wtype_id1','required_wtype_id2'}),
    'states': ('RPG::State', (BASE - {'description'}) | {'restriction','priority','remove_at_battle_end','remove_by_restriction','auto_removal_timing',
                                     'min_turns','max_turns','remove_by_damage','release_by_damage','chance_by_damage','remove_by_walking',
                                     'steps_to_remove','message1','message2','message3','message4'}),
    'weapons': ('RPG::Weapon', BASE | {'price','etype_id','params','wtype_id','animation_id'}),
    'armors': ('RPG::Armor', BASE | {'price','etype_id','params','atype_id'}),
}
TEXT = {'name','description','note','battler_name','message1','message2','message3','message4'}
BOOLS = {'remove_at_battle_end','remove_by_restriction','remove_by_damage','release_by_damage','remove_by_walking'}
LISTS = {'features','effects','drop_items','actions','params'}
NESTED = {'damage'}
FEATURE_FIELDS = {'code','data_id','value'}
EFFECT_FIELDS = {'code','data_id','value1','value2'}
DAMAGE_FIELDS = {'type','element_id','formula','variance','critical'}
DROP_FIELDS = {'kind','data_id','denominator'}
ACTION_FIELDS = {'condition_type','condition_param1','condition_param2','skill_id','rating'}
# Whitelisted overrides per table (note is deliberately never overridable).
OVERRIDES = {
    'enemies': ('name','params','exp','gold','battler_name','battler_hue'),
    'skills': ('name','description','icon_index','mp_cost','tp_cost','message1','message2','damage_formula','damage_variance','damage_critical'),
    'states': ('name','icon_index','message1','message2','message3','message4','priority','min_turns','max_turns','auto_removal_timing'),
    'weapons': ('name','description','icon_index','price','params'),
    'armors': ('name','description','icon_index','price','params'),
}
INT_RANGES = {'icon_index':(0,4095),'exp':(0,9999999),'gold':(0,9999999),'battler_hue':(0,360),
              'mp_cost':(0,9999),'tp_cost':(0,100),'damage_variance':(0,100),'priority':(0,100),
              'min_turns':(0,9999),'max_turns':(0,9999),'auto_removal_timing':(0,2),'price':(0,9999999)}
BATTLER_NAME = re.compile(r'[^\x00-\x1f\\/:*?"<>|]{0,100}')
PARAM_COUNT = 8
LIST_BUDGET = 256


def integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(label + ' outside integer bounds')
    return value


def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def table_spec(table):
    if table not in TABLES:
        raise ValueError('Unsupported database append table; supported: ' + ', '.join(sorted(TABLES)))
    return TABLES[table]


def table_for_class(root):
    """Infer the table from a native array (used by the Python mutator, which only sees the file root)."""
    classes = {name: table for table, (name, _) in TABLES.items()}
    if isinstance(root, list) and len(root) > 1 and getattr(root[1], 'cls', None) in classes:
        return classes[root[1].cls]
    raise ValueError('Native array is not a supported database append table')


def database_array(root, table):
    from vxace_python_mutator import RubyObject
    cls, _ = table_spec(table)
    if not isinstance(root, list) or not 2 <= len(root) <= 1000 or root[0] is not None:
        raise ValueError('Expected native ' + table + ' array with nil slot zero; supported array limit is 1000')
    for number, entry in enumerate(root[1:], 1):
        if not isinstance(entry, RubyObject) or entry.cls != cls or type(entry.get('id')) is not int or entry.get('id') != number:
            raise ValueError('Every existing ' + table + ' entry must be ' + cls + ' with its exact array-slot ID')
    if len({id(entry) for entry in root[1:]}) != len(root) - 1:
        raise ValueError('Aliased ' + table + ' entries are unsupported')
    return root


def finite_number(value):
    return type(value) is not bool and isinstance(value, (int, float)) and math.isfinite(value)


def check_objects(entry, objects, cls, fields, label):
    from vxace_python_mutator import RubyObject
    if not isinstance(objects, list) or len(objects) > LIST_BUDGET:
        raise ValueError('Template ' + label + ' are opaque or exceed budget')
    for obj in objects:
        if not isinstance(obj, RubyObject) or obj.cls != cls or set(obj.ivars) != {'@' + k for k in fields}:
            raise ValueError('Template has unknown ' + label + ' schema')


def template(root, table, template_id):
    """Return the validated selected template; any schema deviation refuses."""
    from vxace_python_mutator import RubyObject, RubyString
    database_array(root, table)
    _, fields = table_spec(table)
    identifier = integer(template_id, 'template ID', 1, len(root) - 1)
    entry = root[identifier]
    if set(entry.ivars) != {'@' + k for k in fields}:
        raise ValueError('Selected ' + table + ' template has unknown or missing native fields')
    for key in fields:
        value = entry.get(key)
        if key in TEXT:
            ok = isinstance(value, RubyString)
        elif key in BOOLS:
            ok = type(value) is bool
        elif key in LISTS or key in NESTED:
            ok = True
        else:
            ok = type(value) is int
        if not ok:
            raise ValueError('Selected template field types are unsupported')
    check_objects(entry, entry.get('features'), 'RPG::BaseItem::Feature', FEATURE_FIELDS, 'features')
    for feature in entry.get('features'):
        if any(type(feature.get(k)) is not int for k in ('code', 'data_id')) or not finite_number(feature.get('value')):
            raise ValueError('Selected feature field types are unsupported')
    if 'effects' in fields:
        check_objects(entry, entry.get('effects'), 'RPG::UsableItem::Effect', EFFECT_FIELDS, 'effects')
        for effect in entry.get('effects'):
            if any(type(effect.get(k)) is not int for k in ('code', 'data_id')) or not all(finite_number(effect.get(k)) for k in ('value1', 'value2')):
                raise ValueError('Selected effect field types are unsupported')
        damage = entry.get('damage')
        if not isinstance(damage, RubyObject) or damage.cls != 'RPG::UsableItem::Damage' or set(damage.ivars) != {'@' + k for k in DAMAGE_FIELDS}:
            raise ValueError('Selected template has unknown damage schema')
        if any(type(damage.get(k)) is not int for k in ('type', 'element_id', 'variance')) or not isinstance(damage.get('formula'), RubyString) or type(damage.get('critical')) is not bool:
            raise ValueError('Selected damage field types are unsupported')
    if 'params' in fields:
        params = entry.get('params')
        if not isinstance(params, list) or len(params) != PARAM_COUNT or any(type(p) is not int for p in params):
            raise ValueError('Selected template params must be eight native integers')
    if 'drop_items' in fields:
        check_objects(entry, entry.get('drop_items'), 'RPG::Enemy::DropItem', DROP_FIELDS, 'drop items')
        check_objects(entry, entry.get('actions'), 'RPG::Enemy::Action', ACTION_FIELDS, 'actions')
        if any(type(o.get(k)) is not int for o in entry.get('drop_items') for k in DROP_FIELDS) or \
           any(type(o.get(k)) is not int for o in entry.get('actions') for k in ACTION_FIELDS):
            raise ValueError('Selected enemy drop/action field types are unsupported')
    return entry


def text(value, label, minimum, maximum, newline=False):
    if not isinstance(value, str) or not minimum <= len(value) <= maximum or any(ord(c) < 32 and not (newline and c == '\n') for c in value):
        raise ValueError(label + ' must be ' + str(minimum) + '..' + str(maximum) + ' characters without control codes')
    return value


def validated_overrides(table, selected, overrides):
    """Return the strictly validated override dict; includes cross-field checks against inherited values."""
    from vxace_balance import parse, Opaque, MAX_FORMULA
    if not isinstance(overrides, dict) or 'name' not in overrides:
        raise ValueError('overrides must be an object that includes a name')
    allowed = OVERRIDES[table]
    for key in overrides:
        if key not in allowed:
            raise ValueError('Unsupported override key for ' + table + ': ' + str(key))
    out = {}
    for key, value in overrides.items():
        if key == 'name':
            out[key] = text(value, 'name', 1, 100)
        elif key == 'description':
            out[key] = text(value, 'description', 0, 1000, True)
        elif key in ('message1', 'message2', 'message3', 'message4'):
            out[key] = text(value, key, 0, 200)
        elif key == 'battler_name':
            if not isinstance(value, str) or not BATTLER_NAME.fullmatch(value) or '..' in value:
                raise ValueError('battler_name must be at most 100 characters without path or control characters')
            out[key] = value
        elif key == 'damage_critical':
            if type(value) is not bool:
                raise ValueError('damage_critical must be boolean')
            out[key] = value
        elif key == 'damage_formula':
            if not isinstance(value, str) or not 1 <= len(value) <= MAX_FORMULA:
                raise ValueError('damage_formula must be 1..' + str(MAX_FORMULA) + ' characters')
            try:
                parse(value)
            except Opaque as exc:
                raise ValueError('damage_formula is not evaluable by the balance parser: ' + str(exc))
            out[key] = value
        elif key == 'params':
            if not isinstance(value, list) or len(value) != PARAM_COUNT:
                raise ValueError('params must contain exactly eight integers')
            if table == 'enemies':
                ranges = [(1, 999999), (0, 9999)] + [(1, 999)] * 6
            else:
                ranges = [(-999, 999)] * PARAM_COUNT
            out[key] = [integer(v, 'params[' + str(n) + ']', *ranges[n]) for n, v in enumerate(value)]
        else:
            low, high = INT_RANGES[key]
            out[key] = integer(value, key, low, high)
    if table == 'skills' and any(k.startswith('damage_') for k in out) and selected.get('damage').get('type') == 0:
        raise ValueError('Damage overrides require a template with a native damage type')
    if table == 'states':
        low = out.get('min_turns', selected.get('min_turns'))
        high = out.get('max_turns', selected.get('max_turns'))
        if low > high:
            raise ValueError('min_turns must not exceed max_turns')
    return out


def summarize(selected, table):
    """Bounded description of what a clone inherits as-is."""
    summary = {'features': [[f.get('code'), f.get('data_id'), f.get('value')] for f in selected.get('features')[:LIST_BUDGET]]}
    if table == 'skills':
        summary['effects'] = [[e.get('code'), e.get('data_id'), e.get('value1'), e.get('value2')] for e in selected.get('effects')]
        d = selected.get('damage')
        summary['damage'] = {'type': d.get('type'), 'element_id': d.get('element_id'),
                             'formula': d.get('formula').data.decode('utf-8', 'replace'), 'variance': d.get('variance'), 'critical': d.get('critical')}
    if table == 'enemies':
        summary['drop_items'] = [[o.get('kind'), o.get('data_id'), o.get('denominator')] for o in selected.get('drop_items')]
        summary['actions'] = [[o.get('condition_type'), o.get('condition_param1'), o.get('condition_param2'), o.get('skill_id'), o.get('rating')] for o in selected.get('actions')]
    if table == 'states':
        summary['removal'] = {k: selected.get(k) for k in ('restriction','auto_removal_timing','min_turns','max_turns','remove_by_damage','release_by_damage','chance_by_damage','remove_by_walking','steps_to_remove')}
    if table in ('weapons', 'armors'):
        summary['equipment'] = {k: selected.get(k) for k in ('etype_id','wtype_id','atype_id','animation_id') if '@' + k in selected.ivars}
    return summary


def scalar_summary(selected, table):
    from vxace_python_mutator import RubyString
    _, fields = table_spec(table)
    out = {}
    for key in sorted(fields):
        value = selected.get(key)
        if isinstance(value, RubyString):
            out[key] = value.data.decode('utf-8', 'replace')
        elif type(value) in (int, bool) or (isinstance(value, list) and key == 'params'):
            out[key] = value
    return out


def snapshot(root, table, template_id):
    selected = template(root, table, template_id)
    return {'array_sha256': digest(root), 'template_sha256': digest(selected), 'template_id': template_id,
            'next_id': len(root), 'existing_entries': len(root) - 1, 'append_slot_supported': len(root) <= 999,
            'template_name': selected.get('name').data.decode('utf-8', 'strict'),
            'template_fields': scalar_summary(selected, table), 'inherited': summarize(selected, table),
            'template_note_present': bool(selected.get('note').data),
            'supported_overrides': list(OVERRIDES[table]),
            'forced_values': {'id': 'new_id', 'note': ''},
            'scope': 'append-only native template clone; no deletion/reuse/reorder or arbitrary object creation'}


def new_entry(root, table, mutation):
    from vxace_python_mutator import RubyString, convert, marshal_rb
    if not isinstance(mutation, dict) or set(mutation) != MUTATION_FIELDS or mutation.get('action') != ACTION:
        raise ValueError('Only the exact ' + ACTION + ' schema is supported')
    database_array(root, table)
    new_id = integer(mutation['new_id'], 'new ' + table + ' ID', 1, 999)
    if new_id != len(root):
        raise ValueError('New ID must append at the exact next array slot')
    selected = template(root, table, mutation['template_id'])
    if mutation['expected_array_sha256'] != digest(root) or mutation['expected_template_sha256'] != digest(selected):
        raise ValueError('Database array/template fingerprint is stale')
    overrides = validated_overrides(table, selected, mutation['overrides'])
    entry = marshal_rb.load(marshal_rb.dump(selected))

    def put(owner, key, value):
        owner.set(key, convert(value, owner.get(key)) if isinstance(owner.get(key), RubyString) else value)
    put(entry, 'id', new_id)
    put(entry, 'note', '')
    damage = {'damage_formula': 'formula', 'damage_variance': 'variance', 'damage_critical': 'critical'}
    for key, value in overrides.items():
        if key in damage:
            put(entry.get('damage'), damage[key], value)
        else:
            put(entry, key, value)
    return entry


def apply(root, mutation):
    root.append(new_entry(root, table_for_class(root), mutation))


def verify_transition(before, after, table, mutation):
    database_array(before, table);database_array(after, table)
    if len(after) != len(before) + 1 or digest(after[:-1]) != digest(before):
        raise ValueError('Database-entry candidate changed existing entries or array shape')
    if digest(after[-1]) != digest(new_entry(before, table, mutation)):
        raise ValueError('Database-entry candidate differs from the approved template-clone record')


def indexed_check(data, table, result):
    """Verify normalized indexed identities agree with the native array; returns the indexed template dict."""
    cls, fields = table_spec(table)
    indexed = data.json('database/' + table + '.json')
    if not isinstance(indexed, list) or len(indexed) != result['next_id'] or indexed[0] is not None:
        raise ValueError('Indexed/native ' + table + ' array sizes disagree')
    for number, entry in enumerate(indexed[1:], 1):
        if not isinstance(entry, dict) or entry.get('__class__') != cls or type(entry.get('id')) is not int or entry['id'] != number:
            raise ValueError('Indexed/native ' + table + ' identities disagree')
    if indexed[result['template_id']].get('name') != result['template_name']:
        raise ValueError('Indexed/native template names disagree')
    return indexed[result['template_id']]


def indexed_snapshot(data, project, table, template_id):
    from pathlib import Path
    from vxace_index_query import unlinked
    from vxace_python_mutator import load
    cls, _ = table_spec(table)
    file = {'enemies': 'Enemies', 'skills': 'Skills', 'states': 'States', 'weapons': 'Weapons', 'armors': 'Armors'}[table]
    root, _ = load(unlinked(Path(project) / 'Data' / (file + '.rvdata2')))
    result = snapshot(root, table, template_id)
    indexed_check(data, table, result)
    return {'version': VERSION, 'table': table, **result,
            'limits': ['Only templates whose exact native field set, nested schemas and types are supported are admitted.',
                       'Features, effects, drops, actions and damage type/element are inherited as-is; note is forced empty. Review the inherited lists.',
                       'battler_name is only charset/length checked; the asset audit must confirm Graphics/Battlers files exist.',
                       'A new static ID can still collide with runtime-created IDs or custom consumers; review scripts/events/notes.',
                       'Snapshot is not mutation permission; use the reviewed Python disposable-copy workflow and native battle/save tests.']}
