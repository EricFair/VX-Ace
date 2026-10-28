#!/usr/bin/env python3
"""Guarded append-only native template clones for Enemies, Skills, States, Weapons, Armors and blank-page Troops."""
from __future__ import annotations
import hashlib
import math
import re

VERSION = '1.11.0'
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
    # Editor-saved RPG::Troop has no note/features; only a blank-page template is admitted and members are rebuilt.
    'troops': ('RPG::Troop', {'id','name','members','pages'}),
}
TROOP_MEMBER_FIELDS = ('enemy_id','x','y','hidden')
CONDITION_BOOLS = ('turn_ending','turn_valid','enemy_valid','actor_valid','switch_valid')
CONDITION_INTS = ('turn_a','turn_b','enemy_index','enemy_hp','actor_id','actor_hp','switch_id')
MEMBER_RANGES = {'x':(0,544),'y':(0,416)}
MAX_MEMBERS = 8
TEXT = {'name','description','note','battler_name','message1','message2','message3','message4'}
BOOLS = {'remove_at_battle_end','remove_by_restriction','remove_by_damage','release_by_damage','remove_by_walking'}
LISTS = {'features','effects','drop_items','actions','params','members','pages'}
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
    'troops': ('name','members'),
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


def mutation_fields(table):
    return MUTATION_FIELDS | ({'expected_enemies_sha256'} if table == 'troops' else set())


def enemies_for(path):
    """Read-only load of Data/Enemies.rvdata2 beside a native Data file (same snapshot/copy); returns the validated array."""
    from vxace_index_query import unlinked
    from vxace_python_mutator import load
    file = unlinked(path)
    if file.parent.name != 'Data':
        raise ValueError('Troop append requires a native project Data path to read Enemies')
    root, _ = load(unlinked(file.parent / 'Enemies.rvdata2'))
    return database_array(root, 'enemies')


def need_enemies(table, enemies):
    if table == 'troops':
        if enemies is None:
            raise ValueError('Troop append requires the Enemies array of the same snapshot')
        database_array(enemies, 'enemies')


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


def check_troop_template(entry):
    """Troop template: native schema, and exactly one blank battle page (no condition, one terminator command)."""
    from vxace_python_mutator import RubyObject
    check_objects(entry, entry.get('members'), 'RPG::Troop::Member', TROOP_MEMBER_FIELDS, 'members')
    for member in entry.get('members'):
        if any(type(member.get(k)) is not int for k in ('enemy_id', 'x', 'y')) or type(member.get('hidden')) is not bool:
            raise ValueError('Selected troop member field types are unsupported')
    pages = entry.get('pages')
    if not isinstance(pages, list) or len(pages) != 1:
        raise ValueError('Troop template must have exactly one blank battle page')
    page = pages[0]
    if not isinstance(page, RubyObject) or page.cls != 'RPG::Troop::Page' or set(page.ivars) != {'@condition', '@span', '@list'} or type(page.get('span')) is not int:
        raise ValueError('Selected troop page has unknown schema')
    condition = page.get('condition')
    cond_fields = CONDITION_BOOLS + CONDITION_INTS
    if not isinstance(condition, RubyObject) or condition.cls != 'RPG::Troop::Page::Condition' or set(condition.ivars) != {'@' + k for k in cond_fields}:
        raise ValueError('Selected troop page condition has unknown schema')
    if any(type(condition.get(k)) is not bool for k in CONDITION_BOOLS) or any(type(condition.get(k)) is not int for k in CONDITION_INTS):
        raise ValueError('Selected troop page condition field types are unsupported')
    if any(condition.get(k) for k in CONDITION_BOOLS):
        raise ValueError('Troop template page is not blank: battle-event conditions are never copied')
    commands = page.get('list')
    if not isinstance(commands, list) or len(commands) != 1:
        raise ValueError('Troop template page is not blank: battle-event commands are never copied')
    command = commands[0]
    if not isinstance(command, RubyObject) or command.cls != 'RPG::EventCommand' or set(command.ivars) != {'@code', '@indent', '@parameters'}:
        raise ValueError('Selected troop page command has unknown schema')
    if type(command.get('code')) is not int or type(command.get('indent')) is not int or not isinstance(command.get('parameters'), list) or \
       command.get('parameters') != [] or command.get('code') != 0 or command.get('indent') != 0:
        raise ValueError('Troop template page is not blank: it must hold only the terminator command')


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
    if table == 'troops':
        check_troop_template(entry)
        return entry
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


def troop_members(value, enemies):
    """Strictly validated member list; every enemy must be an existing static entry of the same-snapshot Enemies array."""
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_MEMBERS:
        raise ValueError('members must contain 1..' + str(MAX_MEMBERS) + ' entries')
    out = []
    for number, member in enumerate(value):
        label = 'members[' + str(number) + ']'
        if not isinstance(member, dict) or set(member) != set(TROOP_MEMBER_FIELDS):
            raise ValueError(label + ' must have exactly enemy_id, x, y and hidden')
        enemy_id = integer(member['enemy_id'], label + '.enemy_id', 1, len(enemies) - 1)
        if enemies[enemy_id] is None:
            raise ValueError(label + '.enemy_id references a missing enemy')
        if type(member['hidden']) is not bool:
            raise ValueError(label + '.hidden must be boolean')
        out.append({'enemy_id': enemy_id, 'x': integer(member['x'], label + '.x', *MEMBER_RANGES['x']),
                    'y': integer(member['y'], label + '.y', *MEMBER_RANGES['y']), 'hidden': member['hidden']})
    return out


def validated_overrides(table, selected, overrides, enemies=None):
    """Return the strictly validated override dict; includes cross-field checks against inherited values."""
    from vxace_balance import parse, Opaque, MAX_FORMULA
    if not isinstance(overrides, dict) or 'name' not in overrides or (table == 'troops' and 'members' not in overrides):
        raise ValueError('overrides must be an object that includes a name' + (' and members' if table == 'troops' else ''))
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
        elif key == 'members':
            out[key] = troop_members(value, enemies)
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
    if table == 'troops':
        return {'members_not_copied': [[m.get('enemy_id'), m.get('x'), m.get('y'), m.get('hidden')] for m in selected.get('members')],
                'page': 'one blank battle page (cloned)'}
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


def snapshot(root, table, template_id, enemies=None):
    need_enemies(table, enemies)
    selected = template(root, table, template_id)
    extra = {}
    if table == 'troops':
        extra = {'enemies_sha256': digest(enemies), 'valid_enemy_id_range': [1, len(enemies) - 1],
                 'enemy_count': sum(1 for e in enemies[1:] if e is not None),
                 'template_page_blank': True, 'template_member_count': len(selected.get('members')),
                 'max_members': MAX_MEMBERS, 'member_x_range': list(MEMBER_RANGES['x']), 'member_y_range': list(MEMBER_RANGES['y'])}
    return {**extra, 'array_sha256': digest(root), 'template_sha256': digest(selected), 'template_id': template_id,
            'next_id': len(root), 'existing_entries': len(root) - 1, 'append_slot_supported': len(root) <= 999,
            'template_name': selected.get('name').data.decode('utf-8', 'strict'),
            'template_fields': scalar_summary(selected, table), 'inherited': summarize(selected, table),
            'template_note_present': '@note' in selected.ivars and bool(selected.get('note').data),
            'supported_overrides': list(OVERRIDES[table]),
            'forced_values': {'id': 'new_id'} if table == 'troops' else {'id': 'new_id', 'note': ''},
            'scope': 'append-only native template clone; no deletion/reuse/reorder or arbitrary object creation'}


def new_entry(root, table, mutation, enemies=None):
    from vxace_python_mutator import RubyObject, RubyString, convert, marshal_rb
    if not isinstance(mutation, dict) or set(mutation) != mutation_fields(table) or mutation.get('action') != ACTION:
        raise ValueError('Only the exact ' + ACTION + ' schema is supported')
    database_array(root, table)
    need_enemies(table, enemies)
    new_id = integer(mutation['new_id'], 'new ' + table + ' ID', 1, 999)
    if new_id != len(root):
        raise ValueError('New ID must append at the exact next array slot')
    selected = template(root, table, mutation['template_id'])
    if mutation['expected_array_sha256'] != digest(root) or mutation['expected_template_sha256'] != digest(selected):
        raise ValueError('Database array/template fingerprint is stale')
    if table == 'troops' and mutation['expected_enemies_sha256'] != digest(enemies):
        raise ValueError('Enemies array fingerprint is stale')
    overrides = validated_overrides(table, selected, mutation['overrides'], enemies)
    entry = marshal_rb.load(marshal_rb.dump(selected))

    def put(owner, key, value):
        owner.set(key, convert(value, owner.get(key)) if isinstance(owner.get(key), RubyString) else value)
    put(entry, 'id', new_id)
    if table == 'troops':
        put(entry, 'name', overrides['name'])
        entry.set('members', [RubyObject('RPG::Troop::Member', {'@' + k: m[k] for k in TROOP_MEMBER_FIELDS}) for m in overrides['members']])
        return entry
    put(entry, 'note', '')
    damage = {'damage_formula': 'formula', 'damage_variance': 'variance', 'damage_critical': 'critical'}
    for key, value in overrides.items():
        if key in damage:
            put(entry.get('damage'), damage[key], value)
        else:
            put(entry, key, value)
    return entry


def apply(root, mutation, source_path=None):
    table = table_for_class(root)
    enemies = enemies_for(source_path) if table == 'troops' and source_path is not None else None
    root.append(new_entry(root, table, mutation, enemies))


def verify_transition(before, after, table, mutation, enemies=None):
    database_array(before, table);database_array(after, table)
    if len(after) != len(before) + 1 or digest(after[:-1]) != digest(before):
        raise ValueError('Database-entry candidate changed existing entries or array shape')
    if digest(after[-1]) != digest(new_entry(before, table, mutation, enemies)):
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
    file = {'enemies': 'Enemies', 'skills': 'Skills', 'states': 'States', 'weapons': 'Weapons', 'armors': 'Armors', 'troops': 'Troops'}[table]
    root, _ = load(unlinked(Path(project) / 'Data' / (file + '.rvdata2')))
    enemies = enemies_for(Path(project) / 'Data' / (file + '.rvdata2')) if table == 'troops' else None
    result = snapshot(root, table, template_id, enemies)
    indexed_check(data, table, result)
    if table == 'troops':
        indexed_enemies = data.json('database/enemies.json')
        if not isinstance(indexed_enemies, list) or len(indexed_enemies) != len(enemies):
            raise ValueError('Indexed/native Enemies array sizes disagree')
    troop_limits = ['Only a template with exactly one blank battle page is admitted; battle-event logic is never copied and template members are not copied.',
                    'Members must reference existing static enemies from the Enemies array fingerprinted here (expected_enemies_sha256); enemy edits after the snapshot make the spec stale.',
                    'The troop is not wired to encounter lists or Battle Processing events; do that separately. Troops have no note field.',
                    'Coordinates are range checked only (x 0..544, y 0..416); overlap and on-screen layout need an editor/battle-test review.'] if table == 'troops' else None
    return {'version': VERSION, 'table': table, **result,
            'limits': troop_limits or ['Only templates whose exact native field set, nested schemas and types are supported are admitted.',
                       'Features, effects, drops, actions and damage type/element are inherited as-is; note is forced empty. Review the inherited lists.',
                       'battler_name is only charset/length checked; the asset audit must confirm Graphics/Battlers files exist.',
                       'A new static ID can still collide with runtime-created IDs or custom consumers; review scripts/events/notes.',
                       'Snapshot is not mutation permission; use the reviewed Python disposable-copy workflow and native battle/save tests.']}
