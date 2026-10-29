#!/usr/bin/env python3
"""Guarded append-only native template clones for Actors, Classes, Enemies, Items, Skills, States, Weapons, Armors and blank-page Troops."""
from __future__ import annotations
import hashlib
import math
import re

VERSION = '1.23.0'
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
    # Editor-saved RPG::Actor (Project3): ivars name, face_index, character_index, initial_level, face_name, class_id, character_name, id, features,
    # note, equips, nickname, description, max_level; actors created in the editor also carry a trailing icon_index (an optional field here).
    'actors': ('RPG::Actor', {'id','name','nickname','class_id','initial_level','max_level','character_name','character_index','face_name','face_index',
                              'equips','features','note','description'}),
    # Editor-saved RPG::Class (Project3 and a stock editor project): ivars name, learnings, id, features, note, params, exp_params, icon_index, description.
    # params is a Table (dim 2, xsize 8 params, ysize 100 levels, zsize 1) addressed [param, level]; level 0 is an unused all-zero column.
    'classes': ('RPG::Class', {'id','name','icon_index','description','features','note','exp_params','params','learnings'}),
}
OPTIONAL_FIELDS = {'actors': {'icon_index'}}
EQUIP_SLOTS = 5
TROOP_MEMBER_FIELDS = ('enemy_id','x','y','hidden')
CONDITION_BOOLS = ('turn_ending','turn_valid','enemy_valid','actor_valid','switch_valid')
CONDITION_INTS = ('turn_a','turn_b','enemy_index','enemy_hp','actor_id','actor_hp','switch_id')
MEMBER_RANGES = {'x':(0,544),'y':(0,416)}
MAX_MEMBERS = 8
TEXT = {'name','description','note','battler_name','message1','message2','message3','message4','nickname','character_name','face_name'}
BOOLS = {'consumable','remove_at_battle_end','remove_by_restriction','remove_by_damage','release_by_damage','remove_by_walking'}
LISTS = {'features','effects','drop_items','actions','params','members','pages','equips','exp_params','learnings'}
NESTED = {'damage'}
FEATURE_FIELDS = {'code','data_id','value'}
EFFECT_FIELDS = {'code','data_id','value1','value2'}
DAMAGE_FIELDS = {'type','element_id','formula','variance','critical'}
DROP_FIELDS = {'kind','data_id','denominator'}
ACTION_FIELDS = {'condition_type','condition_param1','condition_param2','skill_id','rating'}
# Whitelisted overrides per table (note is deliberately never overridable).
OVERRIDES = {
    'enemies': ('name','params','exp','gold','battler_name','battler_hue','actions','drop_items','features'),
    'items': ('name','description','icon_index','price','consumable','damage_formula','damage_variance','damage_critical','effects'),
    'skills': ('name','description','icon_index','mp_cost','tp_cost','message1','message2','damage_formula','damage_variance','damage_critical','effects'),
    'states': ('name','icon_index','message1','message2','message3','message4','priority','min_turns','max_turns','auto_removal_timing','features'),
    'weapons': ('name','description','icon_index','price','params','features'),
    'armors': ('name','description','icon_index','price','params','features'),
    'troops': ('name','members'),
    'actors': ('name','nickname','description','class_id','initial_level','max_level','character_name','character_index','face_name','face_index','equips','features'),
    'classes': ('name','description','icon_index','exp_params','params','learnings','features'),
}
INT_RANGES = {'icon_index':(0,4095),'exp':(0,9999999),'gold':(0,9999999),'battler_hue':(0,360),
              'mp_cost':(0,9999),'tp_cost':(0,100),'damage_variance':(0,100),'priority':(0,100),
              'min_turns':(0,9999),'max_turns':(0,9999),'auto_removal_timing':(0,2),'price':(0,9999999)}
BATTLER_NAME = re.compile(r'[^\x00-\x1f\\/:*?"<>|]{0,100}')
PARAM_COUNT = 8
LIST_BUDGET = 256
# Classes. Editor-saved Class data (Project3 + stock project): params is Table(dim 2, 8 x 100 x 1) addressed [param, level] (cell = param + 8 * level), level 0 is an
# all-zero unused column, exp_params is four Integers, each Learning is ivars level, skill_id, note (note is the empty string). The engine caps battler
# params in Game_BattlerBase#param_max / Game_Actor#param_max: MHP 9999 (actors), MMP 9999, everything else 999.
CLASS_PARAM_KEYS = ('mhp', 'mmp', 'atk', 'def', 'mat', 'mdf', 'agi', 'luk')
CLASS_PARAM_RANGES = ((1, 9999), (0, 9999)) + ((1, 999),) * 6
CLASS_CURVES = ('linear', 'early', 'late')
CLASS_LEVELS = 99
CLASS_TABLE = (PARAM_COUNT, CLASS_LEVELS + 1, 1)
# EXP curve dialog sliders (basis, extra, acceleration A, acceleration B); acc_b is a divisor in Game_Actor/RPG::Class#exp_for_level, so it is never 0.
EXP_LABELS = ('basis', 'extra', 'acc_a', 'acc_b')
EXP_RANGES = ((10, 50), (0, 40), (10, 50), (10, 50))
MAX_LEARNINGS = 64
CLASS_MAX_ROWS = 32
LEARNING_CLS = 'RPG::Class::Learning'
LEARNING_FIELDS = ('level', 'skill_id', 'note')
CLASS_FEATURE_CODES = (41, 42, 51, 52, 53, 54, 55, 61, 62)


def integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(label + ' outside integer bounds')
    return value


def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


# Referenced databases (read-only, same snapshot/copy). Each one a mutation needs is bound by its own expected_<name>_sha256.
REF_FILES = {'enemies': 'Enemies', 'states': 'States', 'skills': 'Skills', 'common_events': 'CommonEvents', 'system': 'System',
             'classes': 'Classes', 'weapons': 'Weapons', 'armors': 'Armors', 'items': 'Items'}
# Which referenced database each effect / feature code needs (codes absent here carry no database id).
EFFECT_REFS = {21: 'states', 22: 'states', 43: 'skills', 44: 'common_events'}
FEATURE_REFS = {11: 'system', 31: 'system', 13: 'states', 14: 'states', 32: 'states', 43: 'skills', 41: 'system', 42: 'system', 51: 'system', 52: 'system'}
LIST_TABLES = {'effects': ('items', 'skills'), 'features': ('actors', 'armors', 'classes', 'enemies', 'states', 'weapons')}
# Referenced databases a snapshot reports (hashes/counts) per table; the table's own array is always reported.
SNAPSHOT_REFS = {'enemies': ('system', 'states', 'skills', 'items', 'weapons', 'armors'), 'troops': ('enemies',), 'items': ('states', 'skills', 'common_events'),
                 'skills': ('states', 'skills', 'common_events'), 'weapons': ('system', 'states', 'skills'),
                 'armors': ('system', 'states', 'skills'), 'states': ('system', 'states', 'skills'),
                 'actors': ('classes', 'weapons', 'armors', 'system', 'states', 'skills'), 'classes': ('classes', 'system', 'skills', 'states')}
MAX_ROWS = 16
MAX_ACTIONS = 16
DROP_SLOTS = 3
DROP_KINDS = {'none': 0, 'item': 1, 'weapon': 2, 'armor': 3}
DROP_TABLES = {'item': 'items', 'weapon': 'weapons', 'armor': 'armors'}
# Row order of the built tuples, and the editor-saved ivar order of RPG::Enemy::Action / DropItem (Project3 and a stock editor project);
# the latter is used only when no enemy in the file has an object to copy.
ACTION_ORDER = ('condition_type', 'condition_param1', 'condition_param2', 'skill_id', 'rating')
DROP_ORDER = ('kind', 'data_id', 'denominator')
ACTION_SHAPE = ('condition_type', 'rating', 'skill_id', 'condition_param2', 'condition_param1')
DROP_SHAPE = ('denominator', 'kind', 'data_id')
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
    if table == 'actors' and isinstance(overrides, dict):
        equips = overrides.get('equips')
        listed = [value for value in equips if type(value) is int] if isinstance(equips, list) else []
        # classes: the class_id itself, or any equipped item (equippability is decided by the class); weapons: slot 0; armors: slots 1..4
        if 'class_id' in overrides or any(listed):
            names.add('classes')
        if isinstance(equips, list) and equips and type(equips[0]) is int and equips[0] != 0:
            names.add('weapons')
        if isinstance(equips, list) and any(type(value) is int and value != 0 for value in equips[1:]):
            names.add('armors')
    if table == 'classes' and isinstance(overrides, dict):
        learned = overrides.get('learnings')
        if isinstance(learned, list) and any(isinstance(row, dict) for row in learned):
            names.add('skills')
        params = overrides.get('params')
        if isinstance(params, dict) and 'copy_from_class' in params:
            names.add('classes')
    if table == 'enemies' and isinstance(overrides, dict):
        names |= enemy_refs(overrides)
    if isinstance(overrides, dict):
        for key, rules in (('effects', EFFECT_REFS), ('features', FEATURE_REFS)):
            rows = overrides.get(key)
            if table in LIST_TABLES[key] and isinstance(rows, list):
                names |= {rules[r['code']] for r in rows if isinstance(r, dict) and type(r.get('code')) is int and r['code'] in rules}
    return names


def enemy_refs(overrides):
    """Referenced databases the actions / drop_items overrides need; tolerant of malformed input (validation refuses it later)."""
    names = set()
    actions = overrides.get('actions')
    for action in actions if isinstance(actions, list) else []:
        if isinstance(action, dict):
            names.add('skills')
            condition = action.get('condition')
            if isinstance(condition, dict):
                names |= {'states' for key in condition if key == 'state'} | {'system' for key in condition if key == 'switch'}
    drops = overrides.get('drop_items')
    for slot in drops if isinstance(drops, list) else []:
        if isinstance(slot, dict) and isinstance(slot.get('kind'), str) and slot['kind'] in DROP_TABLES:
            names.add(DROP_TABLES[slot['kind']])
    return names


def actor_graphics(overrides):
    """(character sheet names, face sheet names) an actor override uses; tolerant of malformed input."""
    if not isinstance(overrides, dict):
        return set(), set()
    return ({overrides['character_name']} if isinstance(overrides.get('character_name'), str) else set(),
            {overrides['face_name']} if isinstance(overrides.get('face_name'), str) else set())


def mutation_fields(table, overrides=None):
    assets = {'expected_assets'} if table == 'actors' and isinstance(overrides, dict) and ('character_name' in overrides or 'face_name' in overrides) else set()
    return MUTATION_FIELDS | assets | {ref_field(name) for name in required_refs(table, overrides)}


def refs_dict(refs):
    """Referenced roots as {name: native root}; a bare list is the legacy Enemies array of a troop append."""
    if refs is None:
        return {}
    return refs if isinstance(refs, dict) else {'enemies': refs}


def checked_reference(name, root):
    """Validated referenced database root: dense arrays for enemies/states/skills, a slot-id array for common events, RPG::System."""
    from vxace_python_mutator import RubyObject
    if name in ('enemies', 'states', 'skills', 'weapons', 'armors', 'items'):
        return database_array(root, name)
    if name == 'classes':
        if not isinstance(root, list) or not 2 <= len(root) <= 1000 or root[0] is not None:
            raise ValueError('Native Classes must be an array with nil slot zero')
        for slot, entry in enumerate(root[1:], 1):
            if not isinstance(entry, RubyObject) or entry.cls != 'RPG::Class' or type(entry.get('id')) is not int or entry.get('id') != slot                or not isinstance(entry.get('features'), list):
                raise ValueError('Native Classes entry ' + str(slot) + ' is not an RPG::Class with its slot id and a features list')
        return root
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
    present = {name[1:] for name in entry.ivars}
    if not fields <= present <= fields | OPTIONAL_FIELDS.get(table, set()):
        raise ValueError('Selected ' + table + ' template has unknown or missing native fields')
    for key in present:
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
    if table == 'actors':
        equips = entry.get('equips')
        if not isinstance(equips, list) or len(equips) != EQUIP_SLOTS or any(type(value) is not int for value in equips):
            raise ValueError('Selected actor template equips must be five native integers')
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
    if table == 'classes':
        exp = entry.get('exp_params')
        if not isinstance(exp, list) or len(exp) != len(EXP_LABELS) or any(type(v) is not int for v in exp):
            raise ValueError('Selected class exp_params must be four native integers')
        class_table(entry)
        check_objects(entry, entry.get('learnings'), LEARNING_CLS, LEARNING_FIELDS, 'learnings')
        if any(type(o.get('level')) is not int or type(o.get('skill_id')) is not int or not isinstance(o.get('note'), RubyString) for o in entry.get('learnings')):
            raise ValueError('Selected class learning field types are unsupported')
    if 'params' in fields and table != 'classes':
        params = entry.get('params')
        if not isinstance(params, list) or len(params) != PARAM_COUNT or any(type(p) is not int for p in params):
            raise ValueError('Selected template params must be eight native integers')
    if 'drop_items' in fields:
        check_objects(entry, entry.get('drop_items'), 'RPG::Enemy::DropItem', DROP_FIELDS, 'drop items')
        check_objects(entry, entry.get('actions'), 'RPG::Enemy::Action', ACTION_FIELDS, 'actions')
        # condition params may be Floats (HP/MP percent conditions are stored as 0.0..1.0 rates by the editor)
        if any(type(o.get(k)) is not int for o in entry.get('drop_items') for k in DROP_FIELDS) or \
           any(type(o.get(k)) is not int for o in entry.get('actions') for k in ACTION_FIELDS if k not in ('condition_param1', 'condition_param2')) or \
           any(not finite_number(o.get(k)) for o in entry.get('actions') for k in ('condition_param1', 'condition_param2')):
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


def type_id(roots, key, value, label):
    """A skill / weapon / armor type id 1..n of the fingerprinted System (slot 0 is the editor's unused empty name)."""
    names = roots['system'].get(key)
    count = len(names) - 1 if isinstance(names, list) else 0
    if type(value) is not int or not 1 <= value <= count:
        raise ValueError(label + ' must be a ' + key[:-1].replace('_', ' ') + ' id 1..' + str(count) + ' of the fingerprinted System')
    return value


def feature_rows(rows, roots, table=None):
    """Full replacement features list as (code, data_id, value) tuples (value float, or integer 0 for codes 31/43 like the editor).

    Codes 41/42/51..55/61/62 are admitted for classes only (their rows are Float values like every editor-added row: data_id carries the type / flag)."""
    limit = CLASS_MAX_ROWS if table == 'classes' else MAX_ROWS
    codes = FEATURE_CODES + CLASS_FEATURE_CODES if table == 'classes' else FEATURE_CODES
    if not isinstance(rows, list) or len(rows) > limit:
        raise ValueError('features must be a list of 0..' + str(limit) + ' entries')
    out = []
    for n, row in enumerate(rows):
        label = 'features[' + str(n) + ']'
        if not isinstance(row, dict) or set(row) != FEATURE_FIELDS:
            raise ValueError(label + ' must have exactly code, data_id and value')
        code = row['code']
        if type(code) is not int or code not in codes:
            raise ValueError(label + '.code must be one of ' + ', '.join(map(str, codes)) + (' (63 collapse type is not a class feature)' if table == 'classes' else ''))
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
        elif code in (41, 42):
            data = type_id(roots, 'skill_types', data, label + '.data_id');value = zero(value, label + '.value')
        elif code == 51:
            data = type_id(roots, 'weapon_types', data, label + '.data_id');value = zero(value, label + '.value')
        elif code == 52:
            data = type_id(roots, 'armor_types', data, label + '.data_id');value = zero(value, label + '.value')
        elif code in (53, 54):
            data = small_id(data, label + '.data_id (equip type)', 0, 4);value = zero(value, label + '.value')
        elif code == 55:
            data = small_id(data, label + '.data_id (1 = dual wield)', 1, 1);value = zero(value, label + '.value')
        elif code == 61:
            data = small_id(data, label + '.data_id', 0, 0);value = number(value, label + '.value (chance of an extra action)', 0.0, 1.0)
        elif code == 62:
            data = small_id(data, label + '.data_id (0 auto battle, 1 guard, 2 substitute, 3 preserve TP)', 0, 3);value = zero(value, label + '.value')
        else:
            data = database_id(roots, 'skills', data, label + '.data_id');value = zero(value, label + '.value')
        out.append((code, data, 0 if code in FEATURE_INT_ZERO else value))
    return out


def percent_range(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(label + ' must be [min, max] percentages')
    low, high = number(value[0], label + ' min', 0, 100), number(value[1], label + ' max', 0, 100)
    if low > high:
        raise ValueError(label + ' min must not exceed max')
    return low, high


def rate_value(percent):
    """HP/MP percent as the editor stores it: a Float rate 0.0..1.0, except 0, which the editor leaves as Integer 0."""
    return round(percent / 100.0, 6) if percent else 0


def switch_id(roots, value, label):
    switches = roots['system'].get('switches')
    count = len(switches) - 1 if isinstance(switches, list) else 0
    if type(value) is not int or not 1 <= value <= count:
        raise ValueError(label + ' must be a switch id 1..' + str(count) + ' of the fingerprinted System')
    return value


def action_condition(condition, roots, label):
    """(condition_type, param1, param2) of an enemy action condition; the codes and params follow Game_Enemy#conditions_met_*."""
    if not isinstance(condition, dict) or len(condition) != 1:
        raise ValueError(label + ' must have exactly one of: always, turn, hp_percent, mp_percent, state, party_level_at_least, switch')
    (kind, value), = condition.items()
    if kind == 'always':
        if value is not True:
            raise ValueError(label + '.always must be true')
        return 0, 0, 0
    if kind == 'turn':
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError(label + '.turn must be [a, b]')
        return 1, integer(value[0], label + '.turn a', 0, 999), integer(value[1], label + '.turn b', 0, 999)
    if kind in ('hp_percent', 'mp_percent'):
        low, high = percent_range(value, label + '.' + kind)
        return (2 if kind == 'hp_percent' else 3), rate_value(low), rate_value(high)
    if kind == 'state':
        return 4, database_id(roots, 'states', value, label + '.state'), 0
    if kind == 'party_level_at_least':
        return 5, integer(value, label + '.party_level_at_least', 1, 99), 0
    if kind == 'switch':
        return 6, switch_id(roots, value, label + '.switch'), 0
    raise ValueError(label + ' has an unknown condition: ' + str(kind))


def condition_state(ctype, p1, p2):
    """'always' (certainly true), 'never' (certainly false) or 'maybe' for a validated condition."""
    if ctype == 0 or (ctype in (2, 3) and p1 <= 0 and p2 >= 1) or (ctype == 5 and p1 <= 1):
        return 'always'
    if ctype == 1 and p1 == 0 and p2 == 0:
        return 'never'      # the troop turn count is already 1 when actions are made, so "turn 0" never matches
    return 'maybe'


def action_rows(rows, roots):
    """Full replacement actions list as (condition_type, param1, param2, skill_id, rating) tuples."""
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ACTIONS:
        raise ValueError('actions must be a list of 1..' + str(MAX_ACTIONS) + ' entries')
    out = []
    for n, row in enumerate(rows):
        label = 'actions[' + str(n) + ']'
        if not isinstance(row, dict) or set(row) != {'skill_id', 'rating', 'condition'}:
            raise ValueError(label + ' must have exactly skill_id, rating and condition')
        skill = database_id(roots, 'skills', row['skill_id'], label + '.skill_id')
        rating = integer(row['rating'], label + '.rating', 1, 9)
        ctype, p1, p2 = action_condition(row['condition'], roots, label + '.condition')
        out.append((ctype, p1, p2, skill, rating))
    if all(condition_state(*row[:3]) == 'never' for row in out):
        raise ValueError('No action can ever be selected: every condition is false (turn [0, 0] never matches)')
    return out


def drop_rows(rows, roots):
    """Exactly three drop slots as (kind, data_id, denominator); an empty slot is the editor's kind 0, data_id 1, denominator 1."""
    if not isinstance(rows, list) or len(rows) != DROP_SLOTS:
        raise ValueError('drop_items must be a list of exactly ' + str(DROP_SLOTS) + ' slots')
    out = []
    for n, row in enumerate(rows):
        label = 'drop_items[' + str(n) + ']'
        if not isinstance(row, dict) or set(row) != {'kind', 'id', 'denominator'}:
            raise ValueError(label + ' must have exactly kind, id and denominator')
        kind = row['kind']
        if not isinstance(kind, str) or kind not in DROP_KINDS:
            raise ValueError(label + '.kind must be one of ' + ', '.join(DROP_KINDS))
        if kind == 'none':
            integer(row['id'], label + '.id (must be 0 for a none slot)', 0, 0)
            integer(row['denominator'], label + '.denominator (must be 1 for a none slot)', 1, 1)
            out.append((0, 1, 1))
        else:
            data = database_id(roots, DROP_TABLES[kind], row['id'], label + '.id')
            out.append((DROP_KINDS[kind], data, integer(row['denominator'], label + '.denominator', 1, 1000)))
    return out


def class_table(entry):
    """The class params Table (8 params x 100 levels, [param, level]); anything but the editor layout, or a non-zero level 0, refuses."""
    from vxace_python_mutator import Table
    table = entry.get('params')
    if not isinstance(table, Table) or (table.dim, table.xsize, table.ysize, table.zsize) != (2,) + CLASS_TABLE or len(table.data) != PARAM_COUNT * (CLASS_LEVELS + 1):
        raise ValueError('Selected class params must be the editor 8 x 100 Table (dim 2)')
    if any(table.data[:PARAM_COUNT]):
        raise ValueError('Selected class params Table has non-zero values in the unused level-0 column')
    return table


def exp_params_value(value):
    if not isinstance(value, list) or len(value) != len(EXP_LABELS):
        raise ValueError('exp_params must be [basis, extra, acc_a, acc_b]')
    return [integer(v, 'exp_params[' + str(n) + '] (' + EXP_LABELS[n] + ', ' + str(EXP_RANGES[n][0]) + '..' + str(EXP_RANGES[n][1]) + ')', *EXP_RANGES[n]) for n, v in enumerate(value)]


def param_curve(lv1, lv99, curve='linear'):
    """Levels 1..99 of one parameter as Integers. With k = level - 1 and D = 98, f(k) is the share of the lv1 -> lv99 rise already made:
    linear f = k / D, early f = 1 - ((D - k) / D)^2 (fast first, flattening), late f = (k / D)^2 (slow first, steep at the end);
    value = lv1 + round_half_up((lv99 - lv1) * f), computed in exact integer arithmetic. Needs lv99 >= lv1, so values never decrease and level 1 / 99 equal the endpoints."""
    top = CLASS_LEVELS - 1
    out = []
    for k in range(top + 1):
        num, den = {'linear': (k, top), 'early': (top * top - (top - k) ** 2, top * top), 'late': (k * k, top * top)}[curve]
        out.append(lv1 + (2 * (lv99 - lv1) * num + den) // (2 * den))
    return out


def class_params_spec(value, roots):
    """('copy', class_id) or ('curves', [(lv1, lv99, curve)] x 8) from a params override."""
    if not isinstance(value, dict):
        raise ValueError('params must be an object: {"copy_from_class": id} or an entry for each of ' + ', '.join(CLASS_PARAM_KEYS))
    if 'copy_from_class' in value:
        if set(value) != {'copy_from_class'}:
            raise ValueError('params copy_from_class cannot be combined with curves')
        return 'copy', database_id(roots, 'classes', value['copy_from_class'], 'params.copy_from_class')
    if set(value) != set(CLASS_PARAM_KEYS):
        raise ValueError('params must give exactly ' + ', '.join(CLASS_PARAM_KEYS) + ' (or only copy_from_class)')
    rows = []
    for n, key in enumerate(CLASS_PARAM_KEYS):
        item, (low, high) = value[key], CLASS_PARAM_RANGES[n]
        if not isinstance(item, dict) or not {'lv1', 'lv99'} <= set(item) <= {'lv1', 'lv99', 'curve'}:
            raise ValueError('params.' + key + ' must be {"lv1": n, "lv99": m} with an optional "curve"')
        lv1 = integer(item['lv1'], 'params.' + key + '.lv1 (' + str(low) + '..' + str(high) + ')', low, high)
        lv99 = integer(item['lv99'], 'params.' + key + '.lv99 (' + str(low) + '..' + str(high) + ')', low, high)
        if lv99 < lv1:
            raise ValueError('params.' + key + '.lv99 must not be below lv1 (growth never decreases)')
        curve = item.get('curve', 'linear')
        if not isinstance(curve, str) or curve not in CLASS_CURVES:
            raise ValueError('params.' + key + '.curve must be one of ' + ', '.join(CLASS_CURVES))
        rows.append((lv1, lv99, curve))
    return 'curves', rows


def class_param_cells(spec, classes=None):
    """The 800 Table cells (cell = param + 8 * level) for a params spec; level 0 stays all zero like the editor writes it."""
    kind, body = spec
    if kind == 'copy':
        return list(class_table(classes[body]).data)
    cells = [0] * (PARAM_COUNT * (CLASS_LEVELS + 1))
    for param, (lv1, lv99, curve) in enumerate(body):
        for level, number in enumerate(param_curve(lv1, lv99, curve), 1):
            cells[param + PARAM_COUNT * level] = number
    return cells


def learning_rows(rows, roots):
    """Full replacement learnings as (level, skill_id) tuples sorted by level (stable, so the given order breaks ties)."""
    if not isinstance(rows, list) or len(rows) > MAX_LEARNINGS:
        raise ValueError('learnings must be a list of 0..' + str(MAX_LEARNINGS) + ' entries')
    out, seen = [], set()
    for n, row in enumerate(rows):
        label = 'learnings[' + str(n) + ']'
        if not isinstance(row, dict) or set(row) != {'skill_id', 'level'}:
            raise ValueError(label + ' must have exactly skill_id and level')
        skill = database_id(roots, 'skills', row['skill_id'], label + '.skill_id')
        if skill in seen:
            raise ValueError(label + ' repeats skill ' + str(skill))
        seen.add(skill)
        out.append((integer(row['level'], label + '.level (1..99)', 1, CLASS_LEVELS), skill))
    return sorted(out, key=lambda row: row[0])


def build_learnings(root, selected, rows):
    from vxace_python_mutator import RubyObject, convert, marshal_rb
    wanted = ['@' + k for k in LEARNING_FIELDS]
    shape = next((o for entry in [selected, *root[1:]] for o in entry.get('learnings') if isinstance(o, RubyObject) and o.cls == LEARNING_CLS and list(o.ivars) == wanted),
                 RubyObject(LEARNING_CLS, {'@level': 0, '@skill_id': 0, '@note': convert('')}))
    out = []
    for level, skill in rows:
        obj = marshal_rb.load(marshal_rb.dump(shape))
        obj.set('level', level);obj.set('skill_id', skill);obj.set('note', convert('', obj.get('note')))
        out.append(obj)
    return out


def class_curve_points(cells):
    return {key: {'lv1': cells[n + PARAM_COUNT], 'lv50': cells[n + PARAM_COUNT * 50], 'lv99': cells[n + PARAM_COUNT * CLASS_LEVELS]} for n, key in enumerate(CLASS_PARAM_KEYS)}


PARAMS = ('Max HP', 'Max MP', 'Attack', 'Defense', 'M.Attack', 'M.Defense', 'Agility', 'Luck')
XPARAMS = ('Hit', 'Evasion', 'Critical', 'Critical evasion', 'Magic evasion', 'Magic reflection', 'Counter', 'HP regen', 'MP regen', 'TP regen')
ETYPES = ('Weapon', 'Shield', 'Head', 'Body', 'Accessory')
SPECIAL_FLAGS = ('auto battle', 'guard', 'substitute', 'preserve TP')
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
        elif code == 43:
            text.append('Add skill: ' + named('skill', data));warnings.append('Feature 43 (add skill) grants ' + named('skill', data) + ' while this is equipped or active.')
        elif code == 41:
            text.append('Add skill type: ' + named('skill type', data))
        elif code == 42:
            text.append('Seal skill type: ' + named('skill type', data));warnings.append('Feature 42 seals ' + named('skill type', data) + ': its skills cannot be used.')
        elif code == 51:
            text.append('Equip weapon type: ' + named('weapon type', data))
        elif code == 52:
            text.append('Equip armor type: ' + named('armor type', data))
        elif code == 53:
            text.append('Fix equip: ' + ETYPES[data] + ' (cannot be changed)')
        elif code == 54:
            text.append('Seal equip: ' + ETYPES[data] + ' (nothing can be equipped there)')
        elif code == 55:
            text.append('Slot type: dual wield')
        elif code == 61:
            text.append('Action plus: ' + pct(value) + ' chance of an extra action')
        else:
            text.append('Special flag: ' + SPECIAL_FLAGS[data])
    return text, warnings


def describe_class(exp_params, params_spec, learnings, name_of=lambda kind, number: None):
    """Human lines for the class-only overrides; any argument may be None (not overridden). `learnings` are (level, skill_id) tuples."""
    lines = []
    if exp_params is not None:
        lines.append('EXP curve: ' + ', '.join(label + ' ' + str(v) for label, v in zip(EXP_LABELS, exp_params)))
    if params_spec is not None:
        kind, body = params_spec
        if kind == 'copy':
            label = name_of('class', body)
            lines.append('Parameter curves copied from class ' + str(body) + (' "' + str(label) + '"' if label else ''))
        else:
            for name, (lv1, lv99, curve) in zip(PARAMS, body):
                lines.append('Parameter ' + name + ': ' + str(lv1) + ' at Lv1 -> ' + str(lv99) + ' at Lv99 (' + curve + ')')
    if learnings is not None:
        shown = []
        for level, skill in learnings:
            label = name_of('skill', skill)
            shown.append((str(label) if label else 'skill ' + str(skill)) + ' @ Lv' + str(level))
        lines.append('Learnings: ' + (', '.join(shown) if shown else 'none'))
    return lines


def class_feature_warnings(effective, template_features, overridden, name_of=lambda kind, number: None):
    """Warnings for a class feature list: (code, data_id) pairs it will have, the template's pairs, and whether features are replaced."""
    def named(kind, number):
        label = name_of(kind, number)
        return kind + ' ' + str(number) + (' "' + str(label) + '"' if label else '')
    warnings = []
    kinds = {41: 'skill type', 51: 'weapon type', 52: 'armor type'}
    if not any(code == 51 for code, _ in effective):
        warnings.append('The new class has no equip weapon type feature (51): actors of this class cannot equip any weapon.')
    if not any(code == 41 for code, _ in effective):
        warnings.append('The new class has no add skill type feature (41): actors of this class get no skill type, so no skill menu or battle skill command (unless their own features add one).')
    if overridden:
        for code, data in template_features:
            if code in kinds and (code, data) not in effective:
                warnings.append('The features override drops the template feature ' + str(code) + ' (' + named(kinds[code], data) + '): the new class loses it.')
    return warnings


def ordinal(n):
    return str(n) + ('th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th'))


def condition_text(ctype, p1, p2, name_of=lambda kind, number: None):
    def named(kind, number):
        label = name_of(kind, number)
        return kind + ' ' + str(number) + (' "' + str(label) + '"' if label else '')
    if ctype == 0:
        return 'always'
    if ctype == 1:
        if p2 == 0:
            return 'on turn ' + str(p1)
        first = p1 if p1 > 0 else p2
        if p2 == 1:
            return 'every turn' + (' from turn ' + str(first) if first > 1 else '')
        return 'every ' + ordinal(p2) + ' turn (turns ' + ', '.join(str(first + p2 * k) for k in range(3)) + '...)'
    if ctype in (2, 3):
        return ('HP ' if ctype == 2 else 'MP ') + ('%g' % round(p1 * 100, 4)) + '–' + ('%g' % round(p2 * 100, 4)) + '%'
    if ctype == 4:
        return 'affected by ' + named('state', p1)
    if ctype == 5:
        return 'party level at least ' + str(p1)
    return named('switch', p1) + ' is ON'


def describe_actions(rows, name_of=lambda kind, number: None, skill_info=lambda number: None, max_mp=None):
    """Human description and warnings for validated action tuples (ctype, p1, p2, skill_id, rating).

    `skill_info(id)` may return {'scope','mp_cost','tp_cost'}; `max_mp` is the enemy's final MP parameter (None = unknown)."""
    text, warnings = [], []
    top = max(row[4] for row in rows)
    for ctype, p1, p2, skill, rating in rows:
        label = name_of('skill', skill) or 'skill ' + str(skill)
        text.append(label + ' (rating ' + str(rating) + ') when ' + condition_text(ctype, p1, p2, name_of))
        if condition_state(ctype, p1, p2) == 'never':
            warnings.append(label + ': the condition "' + condition_text(ctype, p1, p2, name_of) + '" is never true.')
        if rating <= top - 3:
            warnings.append(label + ' (rating ' + str(rating) + ') is 3 or more below the highest rating (' + str(top) + '): it is never picked while a higher-rated action is usable.')
        info = skill_info(skill)
        if info:
            if info.get('scope') in (7, 8, 9, 10):
                warnings.append(label + ' has scope ' + str(info['scope']) + ' (allies only): as an enemy action it can only affect other enemies of the troop.')
            elif info.get('scope') == 0:
                warnings.append(label + ' has scope 0 (none): it has no target.')
            mp, tp = info.get('mp_cost') or 0, info.get('tp_cost') or 0
            if mp > 0 and max_mp is not None and mp > max_mp:
                warnings.append(label + ' costs ' + str(mp) + ' MP but the enemy has ' + str(max_mp) + ' max MP: it can never be used.')
            if tp > 0:
                warnings.append(label + ' costs ' + str(tp) + ' TP; enemies start battle with under 25 TP and gain it only from damage, so it may rarely be usable.')
    if not any(condition_state(*row[:3]) == 'always' for row in rows):
        warnings.append('Every action has a condition that can be false: on a turn where none holds the enemy has no usable action.')
    return text, warnings


def describe_drops(rows, name_of=lambda kind, number: None):
    """One line per validated drop slot (kind, data_id, denominator): `Potion 1/3` or `none`."""
    text = []
    for number, (kind, data, denominator) in enumerate(rows, 1):
        if kind == 0:
            text.append('Slot ' + str(number) + ': none')
        else:
            what = {1: 'item', 2: 'weapon', 3: 'armor'}[kind]
            text.append('Slot ' + str(number) + ': ' + (name_of(what, data) or what + ' ' + str(data)) + ' 1/' + str(denominator))
    return text


def feature_pairs(features):
    """(code, data_id) pairs of native RPG::BaseItem::Feature objects, or of validated (code, data_id, value) tuples."""
    out = []
    for feature in features:
        if isinstance(feature, tuple):
            out.append((feature[0], feature[1]))
        else:
            code, data = feature.get('code'), feature.get('data_id')
            if type(code) is not int or type(data) is not int:
                raise ValueError('Feature with unsupported field types')
            out.append((code, data))
    return out


def actor_equips(value, roots, features):
    """Validated 5-slot equips list. Slot 0 holds a weapon (etype 0); slots 1..4 hold an armor whose etype_id equals the slot
    (Game_Actor#init_equips: index -> etype id, slot_list(etype)). Each item must also be equippable by the class/actor features:
    weapon type (feature 51) / armor type (52) allowed and its equip type not sealed (54); otherwise refresh would silently release it."""
    if not isinstance(value, list) or len(value) != EQUIP_SLOTS:
        raise ValueError('equips must be a list of exactly ' + str(EQUIP_SLOTS) + ' ids (weapon, shield, head, body, accessory; 0 = empty)')
    allowed = lambda code: {data for c, data in features if c == code}
    if max(allowed(55), default=0) == 1 and type(value[1]) is int and value[1] != 0:
        raise ValueError('equips[1]: the class/actor features grant dual wield, where slot 1 holds a weapon; that is unsupported, use 0')
    out = []
    for slot, item_id in enumerate(value):
        label = 'equips[' + str(slot) + ']'
        if type(item_id) is not int:
            raise ValueError(label + ' must be an integer id')
        if item_id == 0:
            out.append(0);continue
        name, key, expected = ('weapons', 'wtype_id', 51) if slot == 0 else ('armors', 'atype_id', 52)
        database_id(roots, name, item_id, label)
        item = roots[name][item_id]
        if item.get('etype_id') != slot:
            raise ValueError(label + ' ' + name[:-1] + ' ' + str(item_id) + ' has equip type ' + str(item.get('etype_id')) + ', but slot ' + str(slot) + ' needs equip type ' + str(slot))
        if item.get(key) not in allowed(expected):
            raise ValueError(label + ' ' + name[:-1] + ' ' + str(item_id) + ' (' + key + ' ' + str(item.get(key)) + ') is not equippable by the actor class/features (feature ' + str(expected) + ')')
        if slot in allowed(54):
            raise ValueError(label + ': equip type ' + str(slot) + ' is sealed by the class/actor features (feature 54)')
        out.append(item_id)
    return out


def actor_overrides(selected, out, roots):
    """Cross-field rules of the actor overrides (levels, paired graphics, class, equips)."""
    initial, maximum = out.get('initial_level', selected.get('initial_level')), out.get('max_level', selected.get('max_level'))
    if not 1 <= initial <= maximum <= 99:
        raise ValueError('Levels must satisfy 1 <= initial_level <= max_level <= 99 (inherited values included)')
    for pair in (('character_name', 'character_index'), ('face_name', 'face_index')):
        if (pair[0] in out) != (pair[1] in out):
            raise ValueError(pair[0] + ' and ' + pair[1] + ' must be given together')
    from vxace_character_graphics import face_schema, graphic_schema
    if 'character_name' in out:
        graphic_schema({'character_name': out['character_name'], 'character_index': out['character_index'], 'direction': 2, 'pattern': 0})
    if 'face_name' in out:
        face_schema(out['face_name'], out['face_index'])
    class_id = out.get('class_id', selected.get('class_id'))
    if 'classes' in roots:
        database_id(roots, 'classes', class_id, 'class_id')
    if 'equips' in out:
        if any(out['equips']):
            actor_features = out['features'] if 'features' in out else selected.get('features')
            out['equips'] = actor_equips(out['equips'], roots, feature_pairs(roots['classes'][class_id].get('features')) + feature_pairs(actor_features))


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
        elif key == 'nickname':
            out[key] = text(value, key, 0, 100)
        elif key in ('character_name', 'face_name'):
            if not isinstance(value, str):
                raise ValueError(key + ' must be a sheet basename')
            out[key] = value
        elif key in ('character_index', 'face_index'):
            out[key] = integer(value, key, 0, 7)
        elif key == 'class_id':
            out[key] = integer(value, key, 1, 999)
        elif key in ('initial_level', 'max_level'):
            out[key] = integer(value, key, 1, 99)
        elif key == 'equips':
            if not isinstance(value, list) or len(value) != EQUIP_SLOTS or any(type(v) is not int for v in value):
                raise ValueError('equips must be a list of exactly ' + str(EQUIP_SLOTS) + ' integer ids')
            out[key] = list(value)
        elif key == 'members':
            out[key] = troop_members(value, roots['enemies'])
        elif key == 'consumable':
            if type(value) is not bool:
                raise ValueError('consumable must be boolean')
            out[key] = value
        elif key == 'effects':
            out[key] = effect_rows(value, roots)
        elif key == 'features':
            out[key] = feature_rows(value, roots, table)
        elif key == 'exp_params':
            out[key] = exp_params_value(value)
        elif key == 'learnings':
            out[key] = learning_rows(value, roots)
        elif key == 'params' and table == 'classes':
            out[key] = class_params_spec(value, roots)
            if out[key][0] == 'copy':
                class_table(roots['classes'][out[key][1]])
        elif key == 'actions':
            out[key] = action_rows(value, roots)
        elif key == 'drop_items':
            out[key] = drop_rows(value, roots)
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
    if table == 'actors':
        actor_overrides(selected, out, roots)
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
    if table == 'actors':
        summary['actor'] = {'class_id': selected.get('class_id'), 'equips': list(selected.get('equips')), 'initial_level': selected.get('initial_level'),
                            'max_level': selected.get('max_level'),
                            'character': [selected.get('character_name').data.decode('utf-8', 'replace'), selected.get('character_index')],
                            'face': [selected.get('face_name').data.decode('utf-8', 'replace'), selected.get('face_index')]}
    if table == 'classes':
        summary['class'] = {'exp_params': list(selected.get('exp_params')), 'param_curves': class_curve_points(list(selected.get('params').data)),
                            'learnings': [[o.get('level'), o.get('skill_id')] for o in selected.get('learnings')]}
    if table in ('weapons', 'armors'):
        summary['equipment'] = {k: selected.get(k) for k in ('etype_id','wtype_id','atype_id','animation_id') if '@' + k in selected.ivars}
    return summary


def scalar_summary(selected, table):
    from vxace_python_mutator import RubyString
    _, fields = table_spec(table)
    out = {}
    for key in sorted(fields | OPTIONAL_FIELDS.get(table, set())):
        value = selected.get(key)
        if isinstance(value, RubyString):
            out[key] = value.data.decode('utf-8', 'replace')
        elif type(value) in (int, bool) or (isinstance(value, list) and key in ('params', 'equips', 'exp_params')):
            out[key] = value
    return out


def has_shape(root, key, cls, fields):
    wanted = {'@' + f for f in fields}
    return any(getattr(o, 'cls', None) == cls and set(o.ivars) == wanted
               for entry in root[1:] for o in (entry.get(key) if isinstance(entry.get(key), list) else []))


def snapshot(root, table, template_id, refs=None, assets=None):
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
                if table == 'classes':
                    extra.update(skill_type_count=len(value.get('skill_types')) - 1, weapon_type_count=len(value.get('weapon_types')) - 1,
                                 armor_type_count=len(value.get('armor_types')) - 1)
            else:
                extra[name + '_count'] = len(value) - 1
        if table in LIST_TABLES['effects']:
            extra['effects_shape_available'] = has_shape(root, 'effects', 'RPG::UsableItem::Effect', EFFECT_FIELDS)
        if table in LIST_TABLES['features']:
            extra['features_shape_available'] = has_shape(root, 'features', 'RPG::BaseItem::Feature', FEATURE_FIELDS)
        if table == 'classes':
            extra.update(param_keys=list(CLASS_PARAM_KEYS), param_ranges={k: list(r) for k, r in zip(CLASS_PARAM_KEYS, CLASS_PARAM_RANGES)},
                         param_curves=list(CLASS_CURVES), exp_params_ranges={k: list(r) for k, r in zip(EXP_LABELS, EXP_RANGES)},
                         max_learnings=MAX_LEARNINGS, max_features=CLASS_MAX_ROWS, class_feature_codes=list(FEATURE_CODES + CLASS_FEATURE_CODES))
        if table == 'actors':
            extra['equip_slots'] = ['weapon (etype 0)', 'armor etype 1', 'armor etype 2', 'armor etype 3', 'armor etype 4']
            if assets:
                extra['assets'] = assets
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
    if cls == 'RPG::BaseItem::Feature' and getattr(root[1], 'cls', None) in ('RPG::Actor', 'RPG::Class'):
        # Editor-saved actors usually have no features to copy from; Project3 Classes/Weapons/Armors/States all store a Feature as ivars code, data_id, value.
        from vxace_python_mutator import RubyObject
        return RubyObject(cls, {'@code': 0, '@data_id': 0, '@value': 0.0})
    if cls in ('RPG::Enemy::Action', 'RPG::Enemy::DropItem'):
        from vxace_python_mutator import RubyObject
        return RubyObject(cls, {'@' + f: 0 for f in (ACTION_SHAPE if cls == 'RPG::Enemy::Action' else DROP_SHAPE)})
    raise ValueError('No existing ' + what + ' in this file to copy the native object shape from')


ROW_OBJECTS = {'effects': ('RPG::UsableItem::Effect', ('code', 'data_id', 'value1', 'value2'), 'effect'),
               'features': ('RPG::BaseItem::Feature', ('code', 'data_id', 'value'), 'feature'),
               'actions': ('RPG::Enemy::Action', ACTION_ORDER, 'action'),
               'drop_items': ('RPG::Enemy::DropItem', DROP_ORDER, 'drop item')}


def build_objects(root, selected, key, rows):
    from vxace_python_mutator import marshal_rb
    from rpgvxace_mcp.rubytypes import RubyFloat
    if not rows:
        return []
    cls, fields, what = ROW_OBJECTS[key]
    shape = object_shape(root, selected, key, cls, fields, what)
    out = []
    for row in rows:
        obj = marshal_rb.load(marshal_rb.dump(shape))
        for field, value in zip(fields, row):
            # A fresh Float object per field: the Marshal writer links identical objects, which Ruby never does for Floats.
            obj.set(field, RubyFloat(value) if type(value) is float else value)
        out.append(obj)
    return out


def new_entry(root, table, mutation, refs=None, project=None, rtp=None):
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
    if 'expected_assets' in mutation:
        # Actor graphics: each sheet is bound by the hash/layout of its PNG in the project (or the explicit RTP).
        from vxace_character_graphics import actor_assets
        assets = mutation['expected_assets']
        characters, faces = actor_graphics(overrides)
        if project is None:
            raise ValueError('Actor graphics need the native project to bind the sheets')
        if not isinstance(assets, dict) or assets != actor_assets(project, rtp, characters, faces):
            raise ValueError('Actor graphics asset binding is stale or inconsistent')
    entry = marshal_rb.load(marshal_rb.dump(selected))

    def put(owner, key, value):
        owner.set(key, convert(value, owner.get(key)) if isinstance(owner.get(key), RubyString) else value)
    put(entry, 'id', new_id)
    if table == 'troops':
        put(entry, 'name', overrides['name'])
        entry.set('members', [RubyObject('RPG::Troop::Member', {'@' + k: m[k] for k in TROOP_MEMBER_FIELDS}) for m in overrides['members']])
        return entry
    put(entry, 'note', '')
    if table == 'classes':
        from vxace_python_mutator import Table
        for key, value in overrides.items():
            if key == 'params':
                entry.set(key, Table(CLASS_TABLE[0], CLASS_TABLE[1], CLASS_TABLE[2], dim=2, data=class_param_cells(value, roots.get('classes'))))
            elif key == 'exp_params':
                entry.set(key, list(value))
            elif key == 'learnings':
                entry.set(key, build_learnings(root, selected, value))
            elif key in ROW_OBJECTS:
                entry.set(key, build_objects(root, selected, key, value))
            else:
                put(entry, key, value)
        return entry
    damage = {'damage_formula': 'formula', 'damage_variance': 'variance', 'damage_critical': 'critical'}
    for key, value in overrides.items():
        if key in damage:
            put(entry.get('damage'), damage[key], value)
        elif key in ROW_OBJECTS:
            entry.set(key, build_objects(root, selected, key, value))
        elif key == 'equips':
            entry.set(key, list(value))
        else:
            put(entry, key, value)
    return entry


def project_of(source_path):
    """Project root of a native Data file path (None without one)."""
    if source_path is None:
        return None
    from vxace_index_query import unlinked
    file = unlinked(source_path)
    if file.parent.name != 'Data':
        raise ValueError('This append requires a native project Data path')
    return file.parent.parent


def apply(root, mutation, source_path=None, rtp=None):
    table = table_for_class(root)
    root.append(new_entry(root, table, mutation, mutation_refs(source_path, table, mutation), project_of(source_path), rtp))


def verify_transition(before, after, table, mutation, refs=None, project=None, rtp=None):
    database_array(before, table);database_array(after, table)
    if len(after) != len(before) + 1 or digest(after[:-1]) != digest(before):
        raise ValueError('Database-entry candidate changed existing entries or array shape')
    if digest(after[-1]) != digest(new_entry(before, table, mutation, refs, project, rtp)):
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


def indexed_snapshot(data, project, table, template_id, characters=(), faces=(), rtp=None):
    from pathlib import Path
    from vxace_index_query import unlinked
    from vxace_python_mutator import load
    cls, _ = table_spec(table)
    file = {'actors': 'Actors', 'enemies': 'Enemies', 'items': 'Items', 'skills': 'Skills', 'states': 'States', 'weapons': 'Weapons', 'armors': 'Armors', 'troops': 'Troops', 'classes': 'Classes'}[table]
    root, _ = load(unlinked(Path(project) / 'Data' / (file + '.rvdata2')))
    refs = snapshot_refs(Path(project) / 'Data' / (file + '.rvdata2'), table)
    assets = None
    if characters or faces:
        if table != 'actors':
            raise ValueError('Character/face sheet bindings are only for the actors table')
        from vxace_character_graphics import actor_assets
        assets = actor_assets(project, rtp, characters, faces)
    result = snapshot(root, table, template_id, refs, assets)
    indexed_check(data, table, result)
    if table == 'troops':
        indexed_enemies = data.json('database/enemies.json')
        if not isinstance(indexed_enemies, list) or len(indexed_enemies) != len(refs['enemies']):
            raise ValueError('Indexed/native Enemies array sizes disagree')
    troop_limits = ['Only a template with exactly one blank battle page is admitted; battle-event logic is never copied and template members are not copied.',
                    'Members must reference existing static enemies from the Enemies array fingerprinted here (expected_enemies_sha256); enemy edits after the snapshot make the spec stale.',
                    'The troop is not wired to encounter lists or Battle Processing events; do that separately. Troops have no note field.',
                    'Coordinates are range checked only (x 0..544, y 0..416); overlap and on-screen layout need an editor/battle-test review.'] if table == 'troops' else None
    actor_limits = ['Only a template with the editor-saved actor field set (an optional trailing icon_index is kept) and five native equips is admitted; the new actor is not in any party until System party_members (set_system_fields) or a party command adds it.',
                    'class_id, equips (weapon, shield, head, body, accessory; each item must match the slot and be equippable by the class) and features need the matching hashes (expected_classes_sha256, expected_weapons_sha256, expected_armors_sha256, expected_system_sha256, expected_states_sha256, expected_skills_sha256); only the needed hashes may appear in the spec.',
                    'character_name/character_index and face_name/face_index must be given as a pair; each sheet is bound by expected_assets (character sheets: 4x2 characters or a !/$ single character; face sheets: 384x192 with 8 faces, a $-prefixed face is treated as a single face). Pass --character-sheet / --face-sheet (and --rtp for RTP sheets) to this snapshot to get the bindings.',
                    'Dual-wield classes (slot type 55) hold a weapon in slot 1; equips[1] must stay 0 for them. Appended equips are created in the actor slots only; the party inventory is not changed.',
                    'The note is forced empty and the class learnings are not copied; the actor learns the skills of the class at the initial level (Game_Actor#init_skills).'] if table == 'actors' else None
    class_limits = ['Only a class with the editor-saved field set (name, learnings, id, features, note, params, exp_params, icon_index, description), an 8 x 100 params Table with an all-zero level 0 and exact learning objects is admitted; the note is forced empty.',
                    'Unless overridden the clone keeps the template exp_params, params Table, learnings and features. params gives lv1/lv99 and an optional curve (linear, early, late) per parameter, or copy_from_class; learnings is a full replacement list (0..64, skill ids bound by expected_skills_sha256, written sorted by level); features is a full replacement list (up to 32 rows) that also admits codes 41, 42, 51, 52, 53, 54, 55, 61 and 62 (type ids bound by expected_system_sha256); code 63 (collapse type) is refused.',
                    'Parameter limits follow the engine caps: Max HP 1..9999, Max MP 0..9999, the rest 1..999 (Game_Actor#param_max); growth never decreases. exp_params bounds are the EXP curve dialog sliders: basis 10..50, extra 0..40, acc_a 10..50, acc_b 10..50.',
                    'The new class is used by no actor until an actor is appended or changed to use it (append_entry on actors with class_id); old saves keep their actors on their current class.',
                    'Equip and skill types are not cross-checked against actors, weapons or armors that already exist; the impact report warns when the class cannot equip a weapon or has no skill type.'] if table == 'classes' else None
    return {'version': VERSION, 'table': table, **result,
            'limits': troop_limits or actor_limits or class_limits or ['Only templates whose exact native field set, nested schemas and types are supported are admitted.',
                       'Features, effects, drops, actions and damage type/element are inherited as-is unless an effects (skills, items), features (actors, weapons, armors, states, enemies), actions or drop_items (enemies) override replaces the whole list; note is forced empty. Review the inherited lists.',
                       'Each effects/features code, enemy action (skill, state, switch) or enemy drop item (item, weapon, armor) that references a database needs that database fingerprinted here (expected_states_sha256, expected_skills_sha256, expected_common_events_sha256, expected_system_sha256, expected_items_sha256, expected_weapons_sha256, expected_armors_sha256); only the needed hashes may appear in the spec, and edits to those files after the snapshot make it stale.',
                       'Item templates of item type 2 (key items) are refused; use append_key_item for key items.',
                       'battler_name is only charset/length checked; the asset audit must confirm Graphics/Battlers files exist.',
                       'A new static ID can still collide with runtime-created IDs or custom consumers; review scripts/events/notes.',
                       'Snapshot is not mutation permission; use the reviewed Python disposable-copy workflow and native battle/save tests.']}
