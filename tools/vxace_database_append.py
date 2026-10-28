#!/usr/bin/env python3
"""Guarded append-only native template clones for Enemies, Items, Skills, States, Weapons, Armors and blank-page Troops."""
from __future__ import annotations
import hashlib
import math
import re

VERSION = '1.20.0'
ACTION = 'append_database_entry'
MUTATION_FIELDS = {'action','template_id','new_id','expected_array_sha256','expected_template_sha256','overrides'}
BASE = {'id','name','icon_index','description','features','note'}
USABLE = {'scope','occasion','speed','success_rate','repeats','tp_gain','hit_type','animation_id','damage','effects'}
# Field sets observed in editor-saved VX Ace data: RPG::Enemy has no icon_index/description but
# keeps the legacy hit/eva integers; RPG::State has no description but keeps a legacy release_by_damage boolean.
TABLES = {
    'enemies': ('RPG::Enemy', {'id','name','features','note','battler_name','battler_hue','params','exp','gold',
                               'drop_items','actions','hit','eva'}),
    # Items: editor-saved RPG::Item field set (19 ivars) = BASE | USABLE | itype_id, price, consumable. Key items (itype 2) are not templates here.
    'items': ('RPG::Item', BASE | USABLE | {'itype_id','price','consumable'}),
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
BOOLS = {'consumable','remove_at_battle_end','remove_by_restriction','remove_by_damage','release_by_damage','remove_by_walking'}
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
    'items': ('name','description','icon_index','price','consumable','damage_formula','damage_variance','damage_critical','effects'),
    'skills': ('name','description','icon_index','mp_cost','tp_cost','message1','message2','damage_formula','damage_variance','damage_critical','effects'),
    'states': ('name','icon_index','message1','message2','message3','message4','priority','min_turns','max_turns','auto_removal_timing','features'),
    'weapons': ('name','description','icon_index','price','params','features'),
    'armors': ('name','description','icon_index','price','params','features'),
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


# Referenced databases (read-only, same snapshot/copy). Each one a mutation needs is bound by its own expected_<name>_sha256.
REF_FILES = {'enemies': 'Enemies', 'states': 'States', 'skills': 'Skills', 'common_events': 'CommonEvents', 'system': 'System'}
# Which referenced database each effect / feature code needs (codes absent here carry no database id).
EFFECT_REFS = {21: 'states', 22: 'states', 43: 'skills', 44: 'common_events'}
FEATURE_REFS = {11: 'system', 31: 'system', 13: 'states', 14: 'states', 32: 'states', 43: 'skills'}
LIST_TABLES = {'effects': ('items', 'skills'), 'features': ('armors', 'states', 'weapons')}
# Referenced databases a snapshot reports (hashes/counts) per table; the table's own array is always reported.
SNAPSHOT_REFS = {'enemies': (), 'troops': ('enemies',), 'items': ('states', 'skills', 'common_events'),
                 'skills': ('states', 'skills', 'common_events'), 'weapons': ('system', 'states', 'skills'),
                 'armors': ('system', 'states', 'skills'), 'states': ('system', 'states', 'skills')}
MAX_ROWS = 16
EFFECT_CODES = (11, 12, 13, 21, 22, 31, 32, 33, 34, 41, 42, 43, 44)
FEATURE_CODES = (11, 13, 14, 21, 22, 23, 31, 32, 43)
# Editor-saved Effect value1/value2 are always Floats; Feature values are Floats except the value-less attack-element/add-skill
# features (31/43), which the editor saves as Integer 0. State resist (14) is saved as Float 0.0.
FEATURE_INT_ZERO = (31, 43)


def ref_field(name):
    return 'expected_' + name + '_sha256'


def required_refs(table, overrides):
    """Names of the referenced databases the overrides need; tolerant of malformed input (validation refuses it later)."""
    names = {'enemies'} if table == 'troops' else set()
    if isinstance(overrides, dict):
        for key, rules in (('effects', EFFECT_REFS), ('features', FEATURE_REFS)):
            rows = overrides.get(key)
            if table in LIST_TABLES[key] and isinstance(rows, list):
                names |= {rules[r['code']] for r in rows if isinstance(r, dict) and type(r.get('code')) is int and r['code'] in rules}
    return names


def mutation_fields(table, overrides=None):
    return MUTATION_FIELDS | {ref_field(name) for name in required_refs(table, overrides)}


def refs_dict(refs):
    """Referenced roots as {name: native root}; a bare list is the legacy Enemies array of a troop append."""
    if refs is None:
        return {}
    return refs if isinstance(refs, dict) else {'enemies': refs}


def checked_reference(name, root):
    """Validated referenced database root: dense arrays for enemies/states/skills, a slot-id array for common events, RPG::System."""
    from vxace_python_mutator import RubyObject
    if name in ('enemies', 'states', 'skills'):
        return database_array(root, name)
    if name == 'common_events':
        if not isinstance(root, list) or not 2 <= len(root) <= 5001 or root[0] is not None:
            raise ValueError('Native CommonEvents must be an array with nil slot zero')
        for slot, entry in enumerate(root[1:], 1):
            if entry is not None and (not isinstance(entry, RubyObject) or entry.cls != 'RPG::CommonEvent' or type(entry.get('id')) is not int or entry.get('id') != slot):
                raise ValueError('Native CommonEvents entry ' + str(slot) + ' is not an RPG::CommonEvent with its slot id')
        return root
    if name == 'system':
        elements = root.get('elements') if isinstance(root, RubyObject) and root.cls == 'RPG::System' else None
        if not isinstance(elements, list) or not 2 <= len(elements) <= 1000:
            raise ValueError('Native System must be an RPG::System with an elements array')
        return root
    raise ValueError('Unknown referenced database: ' + str(name))


def load_reference(path, name):
    """Read-only load of a referenced Data file beside a native Data file (same snapshot/copy); returns the validated root."""
    from vxace_index_query import unlinked
    from vxace_python_mutator import load
    file = unlinked(path)
    if file.parent.name != 'Data':
        raise ValueError('This append requires a native project Data path to read ' + REF_FILES[name])
    root, _ = load(unlinked(file.parent / (REF_FILES[name] + '.rvdata2')))
    return checked_reference(name, root)


def enemies_for(path):
    """Read-only load of Data/Enemies.rvdata2 beside a native Data file (same snapshot/copy); returns the validated array."""
    return load_reference(path, 'enemies')


def snapshot_refs(path, table):
    """Referenced databases for a snapshot (everything the table's overrides might reference); only Enemies is mandatory (troops)."""
    refs = {}
    for name in SNAPSHOT_REFS[table]:
        if name == table:
            continue
        try:
            refs[name] = load_reference(path, name)
        except Exception:
            if name == 'enemies':
                raise
    return refs


def mutation_refs(path, table, mutation):
    """Referenced databases a mutation needs, loaded beside the target (empty without a native path)."""
    names = required_refs(table, mutation.get('overrides') if isinstance(mutation, dict) else None) - {table}
    return {name: load_reference(path, name) for name in sorted(names)} if path is not None else {}


def need_refs(table, root, refs, names):
    """Validated roots for `names`; the table's own array is used as-is (the pre-append array)."""
    refs = refs_dict(refs)
    out = {}
    for name in sorted(names):
        value = root if name == table else refs.get(name)
        if value is None:
            raise ValueError('This append requires the ' + REF_FILES[name] + ' array of the same snapshot')
        out[name] = checked_reference(name, value)
    return out


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
    if table == 'items' and entry.get('itype_id') == 2:
        raise ValueError('Key items (item type 2) are not admitted as templates here; use the append_key_item operation instead')
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


def number(value, label, low, high):
    if type(value) is bool or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(label + ' outside ' + str(low) + '..' + str(high))
    return float(value)


def zero(value, label):
    return number(value, label + ' (must be 0)', 0, 0)


def database_id(roots, name, value, label, zero_ok=False):
    """An existing id of a referenced database (checked against the same-snapshot array, pre-append for the table itself)."""
    if type(value) is not int:
        raise ValueError(label + ' must be an integer id')
    root = roots[name]
    if not (0 if zero_ok else 1) <= value < len(root) or (value and root[value] is None):
        raise ValueError(label + ' references a ' + name.replace('_', ' ') + ' id that does not exist in the fingerprinted ' + REF_FILES[name] + ' array')
    return value


def element_id(roots, value, label):
    elements = roots['system'].get('elements')
    if type(value) is not int or not 1 <= value < len(elements):
        raise ValueError(label + ' must be an element id 1..' + str(len(elements) - 1) + ' of the fingerprinted System')
    return value


def small_id(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label + ' must be an integer ' + str(low) + '..' + str(high))
    return value


def effect_rows(rows, roots):
    """Full replacement effects list as (code, data_id, value1, value2) tuples; values are native Floats like the editor saves."""
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError('effects must be a list of 0..' + str(MAX_ROWS) + ' entries')
    out = []
    for n, row in enumerate(rows):
        label = 'effects[' + str(n) + ']'
        if not isinstance(row, dict) or set(row) != EFFECT_FIELDS:
            raise ValueError(label + ' must have exactly code, data_id, value1 and value2')
        code = row['code']
        if type(code) is not int or code not in EFFECT_CODES:
            raise ValueError(label + '.code must be one of ' + ', '.join(map(str, EFFECT_CODES)))
        data, v1, v2 = row['data_id'], row['value1'], row['value2']
        if code in (11, 12):
            data = small_id(data, label + '.data_id', 0, 0)
            v1 = number(v1, label + '.value1 (rate)', -1.0, 1.0);v2 = number(v2, label + '.value2 (flat)', -999999, 999999)
            if v1 == 0 and v2 == 0:
                raise ValueError(label + ' recovers nothing: give a nonzero rate or flat amount')
        elif code == 13:
            data = small_id(data, label + '.data_id', 0, 0);v1 = number(v1, label + '.value1', 0, 100);v2 = zero(v2, label + '.value2')
        elif code in (21, 22):
            data = database_id(roots, 'states', data, label + '.data_id', code == 21)
            v1 = number(v1, label + '.value1 (chance)', 0.0, 1.0);v2 = zero(v2, label + '.value2')
        elif code in (31, 32, 42):
            data = small_id(data, label + '.data_id', 0, 7);v1 = number(v1, label + '.value1', 1, 999);v2 = zero(v2, label + '.value2')
            if v1 != int(v1):
                raise ValueError(label + '.value1 must be a whole number')
        elif code in (33, 34):
            data = small_id(data, label + '.data_id', 0, 7);v1 = zero(v1, label + '.value1');v2 = zero(v2, label + '.value2')
        elif code == 41:
            data = small_id(data, label + '.data_id', 0, 0);v1 = zero(v1, label + '.value1');v2 = zero(v2, label + '.value2')
        else:
            data = database_id(roots, 'skills' if code == 43 else 'common_events', data, label + '.data_id')
            v1 = zero(v1, label + '.value1');v2 = zero(v2, label + '.value2')
        out.append((code, data, v1, v2))
    return out


def feature_rows(rows, roots):
    """Full replacement features list as (code, data_id, value) tuples (value float, or integer 0 for codes 31/43 like the editor)."""
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError('features must be a list of 0..' + str(MAX_ROWS) + ' entries')
    out = []
    for n, row in enumerate(rows):
        label = 'features[' + str(n) + ']'
        if not isinstance(row, dict) or set(row) != FEATURE_FIELDS:
            raise ValueError(label + ' must have exactly code, data_id and value')
        code = row['code']
        if type(code) is not int or code not in FEATURE_CODES:
            raise ValueError(label + '.code must be one of ' + ', '.join(map(str, FEATURE_CODES)))
        data, value = row['data_id'], row['value']
        if code == 11:
            data = element_id(roots, data, label + '.data_id');value = number(value, label + '.value (rate)', 0.0, 10.0)
        elif code == 13:
            data = database_id(roots, 'states', data, label + '.data_id');value = number(value, label + '.value (rate)', 0.0, 10.0)
        elif code == 14:
            data = database_id(roots, 'states', data, label + '.data_id');value = zero(value, label + '.value')
        elif code == 21:
            data = small_id(data, label + '.data_id', 0, 7);value = number(value, label + '.value (rate)', 0.0, 10.0)
        elif code == 22:
            data = small_id(data, label + '.data_id', 0, 9);value = number(value, label + '.value', -10.0, 10.0)
        elif code == 23:
            data = small_id(data, label + '.data_id', 0, 9);value = number(value, label + '.value', 0.0, 10.0)
        elif code == 31:
            data = element_id(roots, data, label + '.data_id');value = zero(value, label + '.value')
        elif code == 32:
            data = database_id(roots, 'states', data, label + '.data_id');value = number(value, label + '.value (chance)', 0.0, 1.0)
        else:
            data = database_id(roots, 'skills', data, label + '.data_id');value = zero(value, label + '.value')
        out.append((code, data, 0 if code in FEATURE_INT_ZERO else value))
    return out


PARAMS = ('Max HP', 'Max MP', 'Attack', 'Defense', 'M.Attack', 'M.Defense', 'Agility', 'Luck')
XPARAMS = ('Hit', 'Evasion', 'Critical', 'Critical evasion', 'Magic evasion', 'Magic reflection', 'Counter', 'HP regen', 'MP regen', 'TP regen')
SPARAMS = ('Target rate', 'Guard effect', 'Recovery effect', 'Pharmacology', 'MP cost rate', 'TP charge rate', 'Physical damage', 'Magical damage', 'Floor damage', 'EXP gain')


def pct(value):
    return ('%g' % round(value * 100, 4)) + '%'


def describe_effects(rows, name_of=lambda kind, number: None):
    """Human description and warnings for validated effect tuples (code, data_id, value1, value2); `name_of(kind, id)` may return a name."""
    def named(kind, number):
        label = name_of(kind, number)
        return kind + ' ' + str(number) + (' "' + str(label) + '"' if label else '')
    text, warnings = [], []
    for code, data, v1, v2 in rows:
        if code in (11, 12):
            part = [pct(v1) + ' of max'] if v1 else []
            part += [('%g' % v2) + ' flat'] if v2 else []
            text.append('Recover ' + ('HP' if code == 11 else 'MP') + ': ' + ' + '.join(part))
        elif code == 13:
            text.append('Gain %g TP' % v1)
        elif code in (21, 22):
            what = 'normal-attack state (state 0)' if data == 0 else named('state', data)
            text.append(('Add ' if code == 21 else 'Remove ') + what + ' (' + pct(v1) + ' chance)')
        elif code in (31, 32):
            text.append(('Buff ' if code == 31 else 'Debuff ') + PARAMS[data] + ' for %d turns' % v1)
        elif code in (33, 34):
            text.append('Remove ' + ('buff' if code == 33 else 'debuff') + ' from ' + PARAMS[data])
        elif code == 41:
            text.append('Special effect: escape');warnings.append('Effect 41 (escape): using it removes the target from battle; review battle-end handling.')
        elif code == 42:
            text.append('Grow ' + PARAMS[data] + ' by %d' % v1)
        elif code == 43:
            text.append('Learn ' + named('skill', data));warnings.append('Effect 43 (learn skill) permanently teaches ' + named('skill', data) + ' to the target.')
        else:
            text.append('Call ' + named('common event', data));warnings.append('Effect 44 (common event call) runs ' + named('common event', data) + ' when used; review its commands.')
    return text, warnings


def describe_features(rows, name_of=lambda kind, number: None):
    def named(kind, number):
        label = name_of(kind, number)
        return kind + ' ' + str(number) + (' "' + str(label) + '"' if label else '')
    text, warnings = [], []
    for code, data, value in rows:
        if code == 11:
            text.append('Element rate: ' + named('element', data) + ' x%g' % value)
        elif code == 13:
            text.append('State rate: ' + named('state', data) + ' x%g' % value)
        elif code == 14:
            text.append('State resist: immune to ' + named('state', data))
        elif code == 21:
            text.append('Param rate: ' + PARAMS[data] + ' x%g' % value)
        elif code == 22:
            text.append('Ex-parameter: ' + XPARAMS[data] + ' ' + ('%+g' % round(value * 100, 4)) + ' points')
        elif code == 23:
            text.append('Sp-parameter: ' + SPARAMS[data] + ' x%g' % value)
        elif code == 31:
            text.append('Attack element: ' + named('element', data))
        elif code == 32:
            text.append('Attack state: ' + named('state', data) + ' (' + pct(value) + ' chance)')
        else:
            text.append('Add skill: ' + named('skill', data));warnings.append('Feature 43 (add skill) grants ' + named('skill', data) + ' while this is equipped or active.')
    return text, warnings


def validated_overrides(table, selected, overrides, refs=None):
    """Return the strictly validated override dict; includes cross-field checks against inherited values.

    `refs` holds the referenced roots by name (a bare list is the legacy Enemies array); entries needed by an override must be present."""
    from vxace_balance import parse, Opaque, MAX_FORMULA
    roots = refs_dict(refs)
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
            out[key] = troop_members(value, roots['enemies'])
        elif key == 'consumable':
            if type(value) is not bool:
                raise ValueError('consumable must be boolean')
            out[key] = value
        elif key == 'effects':
            out[key] = effect_rows(value, roots)
        elif key == 'features':
            out[key] = feature_rows(value, roots)
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
    if table in ('items', 'skills') and any(k.startswith('damage_') for k in out) and selected.get('damage').get('type') == 0:
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
    if table in ('items', 'skills'):
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


def has_shape(root, key, cls, fields):
    wanted = {'@' + f for f in fields}
    return any(getattr(o, 'cls', None) == cls and set(o.ivars) == wanted
               for entry in root[1:] for o in (entry.get(key) if isinstance(entry.get(key), list) else []))


def snapshot(root, table, template_id, refs=None):
    refs = refs_dict(refs)
    need_refs(table, root, refs, {'enemies'} if table == 'troops' else set())
    selected = template(root, table, template_id)
    extra = {}
    if table == 'troops':
        enemies = refs['enemies']
        extra = {'enemies_sha256': digest(enemies), 'valid_enemy_id_range': [1, len(enemies) - 1],
                 'enemy_count': sum(1 for e in enemies[1:] if e is not None),
                 'template_page_blank': True, 'template_member_count': len(selected.get('members')),
                 'max_members': MAX_MEMBERS, 'member_x_range': list(MEMBER_RANGES['x']), 'member_y_range': list(MEMBER_RANGES['y'])}
    else:
        # Hashes/counts of every database the effects/features overrides may reference (the table's own array = pre-append array).
        for name in SNAPSHOT_REFS[table]:
            value = root if name == table else refs.get(name)
            if value is None:
                continue
            extra[name + '_sha256'] = digest(value)
            if name == 'system':
                extra['element_count'] = len(value.get('elements')) - 1;extra['valid_element_id_range'] = [1, len(value.get('elements')) - 1]
            else:
                extra[name + '_count'] = len(value) - 1
        if table in LIST_TABLES['effects']:
            extra['effects_shape_available'] = has_shape(root, 'effects', 'RPG::UsableItem::Effect', EFFECT_FIELDS)
        if table in LIST_TABLES['features']:
            extra['features_shape_available'] = has_shape(root, 'features', 'RPG::BaseItem::Feature', FEATURE_FIELDS)
    return {**extra, 'array_sha256': digest(root), 'template_sha256': digest(selected), 'template_id': template_id,
            'next_id': len(root), 'existing_entries': len(root) - 1, 'append_slot_supported': len(root) <= 999,
            'template_name': selected.get('name').data.decode('utf-8', 'strict'),
            'template_fields': scalar_summary(selected, table), 'inherited': summarize(selected, table),
            'template_note_present': '@note' in selected.ivars and bool(selected.get('note').data),
            'supported_overrides': list(OVERRIDES[table]),
            'forced_values': {'id': 'new_id'} if table == 'troops' else {'id': 'new_id', 'note': ''},
            'scope': 'append-only native template clone; no deletion/reuse/reorder or arbitrary object creation'}


def object_shape(root, selected, key, cls, fields, what):
    """An existing native effect/feature object whose class and ivar order are copied (the template's first, else any in the file)."""
    for entry in [selected, *root[1:]]:
        for obj in entry.get(key) if isinstance(entry.get(key), list) else []:
            if getattr(obj, 'cls', None) == cls and set(obj.ivars) == {'@' + f for f in fields}:
                return obj
    raise ValueError('No existing ' + what + ' in this file to copy the native object shape from')


def build_objects(root, selected, key, rows):
    from vxace_python_mutator import marshal_rb
    from rpgvxace_mcp.rubytypes import RubyFloat
    if not rows:
        return []
    cls, fields, what = (('RPG::UsableItem::Effect', ('code', 'data_id', 'value1', 'value2'), 'effect') if key == 'effects'
                         else ('RPG::BaseItem::Feature', ('code', 'data_id', 'value'), 'feature'))
    shape = object_shape(root, selected, key, cls, fields, what)
    out = []
    for row in rows:
        obj = marshal_rb.load(marshal_rb.dump(shape))
        for field, value in zip(fields, row):
            # A fresh Float object per field: the Marshal writer links identical objects, which Ruby never does for Floats.
            obj.set(field, RubyFloat(value) if type(value) is float else value)
        out.append(obj)
    return out


def new_entry(root, table, mutation, refs=None):
    from vxace_python_mutator import RubyObject, RubyString, convert, marshal_rb
    if not isinstance(mutation, dict) or set(mutation) != mutation_fields(table, mutation.get('overrides')) or mutation.get('action') != ACTION:
        raise ValueError('Only the exact ' + ACTION + ' schema is supported (a referenced-database hash is required exactly for the databases the overrides reference)')
    database_array(root, table)
    roots = need_refs(table, root, refs, required_refs(table, mutation.get('overrides')))
    new_id = integer(mutation['new_id'], 'new ' + table + ' ID', 1, 999)
    if new_id != len(root):
        raise ValueError('New ID must append at the exact next array slot')
    selected = template(root, table, mutation['template_id'])
    if mutation['expected_array_sha256'] != digest(root) or mutation['expected_template_sha256'] != digest(selected):
        raise ValueError('Database array/template fingerprint is stale')
    for name, value in roots.items():
        if mutation[ref_field(name)] != digest(value):
            raise ValueError(REF_FILES[name] + ' fingerprint is stale (' + ref_field(name) + ')')
    overrides = validated_overrides(table, selected, mutation['overrides'], roots)
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
        elif key in ('effects', 'features'):
            entry.set(key, build_objects(root, selected, key, value))
        else:
            put(entry, key, value)
    return entry


def apply(root, mutation, source_path=None):
    table = table_for_class(root)
    root.append(new_entry(root, table, mutation, mutation_refs(source_path, table, mutation)))


def verify_transition(before, after, table, mutation, refs=None):
    database_array(before, table);database_array(after, table)
    if len(after) != len(before) + 1 or digest(after[:-1]) != digest(before):
        raise ValueError('Database-entry candidate changed existing entries or array shape')
    if digest(after[-1]) != digest(new_entry(before, table, mutation, refs)):
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
    file = {'enemies': 'Enemies', 'items': 'Items', 'skills': 'Skills', 'states': 'States', 'weapons': 'Weapons', 'armors': 'Armors', 'troops': 'Troops'}[table]
    root, _ = load(unlinked(Path(project) / 'Data' / (file + '.rvdata2')))
    refs = snapshot_refs(Path(project) / 'Data' / (file + '.rvdata2'), table)
    result = snapshot(root, table, template_id, refs)
    indexed_check(data, table, result)
    if table == 'troops':
        indexed_enemies = data.json('database/enemies.json')
        if not isinstance(indexed_enemies, list) or len(indexed_enemies) != len(refs['enemies']):
            raise ValueError('Indexed/native Enemies array sizes disagree')
    troop_limits = ['Only a template with exactly one blank battle page is admitted; battle-event logic is never copied and template members are not copied.',
                    'Members must reference existing static enemies from the Enemies array fingerprinted here (expected_enemies_sha256); enemy edits after the snapshot make the spec stale.',
                    'The troop is not wired to encounter lists or Battle Processing events; do that separately. Troops have no note field.',
                    'Coordinates are range checked only (x 0..544, y 0..416); overlap and on-screen layout need an editor/battle-test review.'] if table == 'troops' else None
    return {'version': VERSION, 'table': table, **result,
            'limits': troop_limits or ['Only templates whose exact native field set, nested schemas and types are supported are admitted.',
                       'Features, effects, drops, actions and damage type/element are inherited as-is unless an effects (skills, items) or features (weapons, armors, states) override replaces the whole list; note is forced empty. Review the inherited lists.',
                       'Each effects/features code that references the database needs that database fingerprinted here (expected_states_sha256, expected_skills_sha256, expected_common_events_sha256, expected_system_sha256); only the needed hashes may appear in the spec, and edits to those files after the snapshot make it stale.',
                       'Item templates of item type 2 (key items) are refused; use append_key_item for key items.',
                       'battler_name is only charset/length checked; the asset audit must confirm Graphics/Battlers files exist.',
                       'A new static ID can still collide with runtime-created IDs or custom consumers; review scripts/events/notes.',
                       'Snapshot is not mutation permission; use the reviewed Python disposable-copy workflow and native battle/save tests.']}
