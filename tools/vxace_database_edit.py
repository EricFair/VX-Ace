#!/usr/bin/env python3
"""Guarded in-place edit of one existing database entry (v1.32): the `edit_database_entry` action behind the recipe step `set_fields`.

The override machinery is the one of append_database_entry (vxace_database_append): the same whitelisted keys per table, the same validation and the same
referenced-database hash binding (expected_<name>_sha256, exactly for the databases the fields reference). Instead of cloning a template into a new slot, the
entry at `entry_id` is cloned, the validated overrides are written into the clone and the clone replaces the entry. The native verifier proves that only that
slot changed and that it equals the factory result of applying the overrides to the old entry. id and note are never touched."""
from __future__ import annotations
import hashlib

VERSION = '1.34.0'
ACTION = 'edit_database_entry'
BASE_FIELDS = {'action', 'expected_array_sha256', 'expected_entry_sha256', 'overrides'}
NATIVE_EXTRA = {'table', 'entry_id'}
# Actor graphics are bound by sheet hashes (expected_assets) in the append; an in-place edit does not carry that binding.
GRAPHIC_KEYS = {'character_name', 'character_index', 'face_name', 'face_index'}


def spec_fields(table, overrides=None):
    from vxace_database_append import required_refs, ref_field
    return BASE_FIELDS | {ref_field(name) for name in required_refs(table, overrides)}


def native_mutation(locator, mutation):
    """Check the spec locator/mutation pair and return the mutation with table and entry_id taken from the locator."""
    from vxace_database_append import TABLES, integer
    if not isinstance(locator, dict) or set(locator) != {'table', 'id'} or locator['table'] not in TABLES:
        raise ValueError('Database edit locator must be exactly {"table": TABLE, "id": ENTRY_ID}')
    integer(locator['id'], 'entry ID', 1, 999)
    if not isinstance(mutation, dict) or mutation.get('action') != ACTION or set(mutation) != spec_fields(locator['table'], mutation.get('overrides')):
        raise ValueError('Only the exact ' + ACTION + ' schema is supported (a referenced-database hash is required exactly for the databases the fields reference)')
    return {**mutation, 'table': locator['table'], 'entry_id': locator['id']}


def check_fields(table, overrides):
    if table == 'actors' and isinstance(overrides, dict) and GRAPHIC_KEYS & set(overrides):
        raise ValueError('An in-place edit does not change actor graphics (' + ', '.join(sorted(GRAPHIC_KEYS & set(overrides))) + '): they need a sheet binding; change them in the editor or on a new actor')


def edit_entry(root, mutation, refs=None):
    """The edited copy of the entry (the factory result): validates the schema and every hash, never changes `root`."""
    from vxace_database_append import (database_array, need_refs, required_refs, template, validated_overrides, apply_overrides, integer, digest,
                                       ref_field, REF_FILES)
    from vxace_python_mutator import marshal_rb
    table = mutation.get('table') if isinstance(mutation, dict) else None
    if not isinstance(mutation, dict) or mutation.get('action') != ACTION or set(mutation) != spec_fields(table, mutation.get('overrides')) | NATIVE_EXTRA:
        raise ValueError('Only the exact ' + ACTION + ' schema is supported (a referenced-database hash is required exactly for the databases the fields reference)')
    database_array(root, table)
    check_fields(table, mutation['overrides'])
    roots = need_refs(table, root, refs, required_refs(table, mutation['overrides']))
    entry_id = integer(mutation['entry_id'], 'entry ID', 1, len(root) - 1)
    selected = template(root, table, entry_id, True)
    if mutation['expected_array_sha256'] != digest(root) or mutation['expected_entry_sha256'] != digest(selected):
        raise ValueError('Database array/entry fingerprint is stale')
    for name, value in roots.items():
        if mutation[ref_field(name)] != digest(value):
            raise ValueError(REF_FILES[name] + ' fingerprint is stale (' + ref_field(name) + ')')
    overrides = validated_overrides(table, selected, mutation['overrides'], roots, True)
    entry = marshal_rb.load(marshal_rb.dump(selected))
    apply_overrides(entry, root, selected, table, overrides, roots)
    return entry


def apply(root, mutation, source_path=None):
    from vxace_database_append import mutation_refs
    table = mutation.get('table') if isinstance(mutation, dict) else None
    entry = edit_entry(root, mutation, mutation_refs(source_path, table, mutation))
    root[mutation['entry_id']] = entry


def verify_transition(before, after, mutation, refs=None):
    """The candidate is the old array with exactly the targeted slot replaced by the factory result (every other slot, incl. slot 0, deep-equal)."""
    from vxace_database_append import database_array, digest
    table, number = mutation['table'], mutation['entry_id']
    database_array(before, table);database_array(after, table)
    if len(after) != len(before):
        raise ValueError('Database-edit candidate changed the array shape')
    if digest([x for n, x in enumerate(before) if n != number]) != digest([x for n, x in enumerate(after) if n != number]):
        raise ValueError('Database-edit candidate changed an unselected entry')
    if digest(after[number]) != digest(edit_entry(before, mutation, refs)):
        raise ValueError('Database-edit candidate differs from the approved edit of the selected entry')


def snapshot(root, table, entry_id, refs=None):
    """The edit preconditions of one existing entry: array / entry hashes, the hashes of every database its fields might reference, and its current content."""
    from vxace_database_append import snapshot as table_snapshot, OVERRIDES
    raw = table_snapshot(root, table, entry_id, refs, None, True)
    drop = {'template_sha256', 'template_id', 'template_name', 'template_fields', 'inherited', 'template_note_present', 'forced_values', 'next_id',
            'append_slot_supported', 'scope', 'supported_overrides'}
    result = {k: v for k, v in raw.items() if k not in drop}
    result.update(entry_id=entry_id, entry_sha256=raw['template_sha256'], entry_name=raw['template_name'], entry_fields=raw['template_fields'], current=raw['inherited'],
                  supported_fields=[k for k in OVERRIDES[table] if not (table == 'actors' and k in GRAPHIC_KEYS)],
                  scope='in-place edit of one existing native entry; its id and note stay, no other entry is touched, no deletion/reuse/reorder')
    return result


def indexed_snapshot(data, project, table, entry_id):
    from pathlib import Path
    from vxace_index_query import unlinked
    from vxace_python_mutator import load
    from vxace_database_append import snapshot as table_snapshot, snapshot_refs, indexed_check
    file = Path(project) / 'Data' / (FILES[table] + '.rvdata2')
    root, _ = load(unlinked(file))
    refs = snapshot_refs(file, table)
    raw = table_snapshot(root, table, entry_id, refs, None, True)
    indexed_check(data, table, raw)
    if table == 'troops':
        indexed_enemies = data.json('database/enemies.json')
        if not isinstance(indexed_enemies, list) or len(indexed_enemies) != len(refs['enemies']):
            raise ValueError('Indexed/native Enemies array sizes disagree')
    return {'version': VERSION, 'table': table, **snapshot(root, table, entry_id, refs),
            'limits': ['Edits one existing native entry in place: every listed field is written from the fields object, id and note stay, and every other entry stays byte-identical.',
                       'The same keys, ranges and referenced-database hashes as an append of this table apply (expected_<name>_sha256 exactly for the databases the fields reference; the table\'s own array is bound by expected_array_sha256 and the entry by expected_entry_sha256).',
                       'Lists (features, effects, actions, drop_items, members, learnings, equips) are replaced whole, except features_add / features_remove which change single feature rows; a features replacement of an enemy, actor or class without the HIT row is refused unless allow_drop_hit is true.',
                       'Troops keep their battle pages: only name and members change. Actor graphics (character / face sheets) cannot be edited here.',
                       'Saves keep working: actors take class parameters and features live, enemies and troops load fresh each battle, inventories keep item ids; nothing that references the entry is rewritten.',
                       'Snapshot is not mutation permission; use the reviewed Python disposable-copy workflow and a battle or smoke test.']}


FILES = {'actors': 'Actors', 'enemies': 'Enemies', 'items': 'Items', 'skills': 'Skills', 'states': 'States', 'weapons': 'Weapons', 'armors': 'Armors', 'troops': 'Troops', 'classes': 'Classes'}


# ------------------------------------------------------------------ plain-language description (impact and plan)

def plain(value):
    """JSON-like view of a native value in the shape of the indexed database/*.json rows (ivars without '@', strings decoded, Tables as {'data': [...]})."""
    from vxace_python_mutator import RubyObject, RubyString, Table
    if isinstance(value, RubyObject):
        return {'__class__': value.cls, **{key[1:]: plain(item) for key, item in value.ivars.items()}}
    if isinstance(value, RubyString):
        return value.data.decode('utf-8', 'replace')
    if isinstance(value, Table):
        return {'data': list(value.data)}
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, float):
        return float(value)
    return value


def quote(value):
    return '"' + str(value) + '"'


def describe_edit(table, old, out, roots, name_of=lambda kind, number: None, class_cells=None, skill_info=lambda number: None):
    """(rows, warnings) for the validated overrides `out` of an edit of `old` (a plain, index-shaped row). rows are {'field', 'old', 'new'} with texts in plain words;
    only fields whose value really changes are listed. `class_cells` are the 800 Table cells a class `params` override produces."""
    from vxace_database_append import (PARAMS, describe_effects, describe_features, describe_actions, describe_drops, describe_class, class_feature_warnings,
                                       class_curve_points, feature_tuples, feature_plan, plan_rows, feature_changes, dropped_feature_warning, FEATURE_KEYS,
                                       CLASS_PARAM_KEYS, EQUIP_SLOTS, ETYPES)
    rows, warnings = [], []

    def add(field, before, after):
        if before != after:
            rows.append({'field': field, 'old': before, 'new': after})
    for key, value in out.items():
        if key in FEATURE_KEYS or key == 'allow_drop_hit':
            continue
        if key == 'params' and table == 'classes':
            before = class_curve_points(old['params']['data'])
            after = class_curve_points(class_cells)
            for label, short in zip(PARAMS, CLASS_PARAM_KEYS):
                add('params.' + short, '%s: Lv1 %d, Lv50 %d, Lv99 %d' % ((label,) + tuple(before[short][k] for k in ('lv1', 'lv50', 'lv99'))),
                    '%s: Lv1 %d, Lv50 %d, Lv99 %d' % ((label,) + tuple(after[short][k] for k in ('lv1', 'lv50', 'lv99'))))
        elif key == 'params':
            for number, label in enumerate(PARAMS):
                add('params[' + str(number) + '] ' + label, old['params'][number], value[number])
        elif key == 'exp_params':
            labels = ('basis', 'extra', 'acc_a', 'acc_b')
            add('exp_params', ', '.join(a + ' ' + str(b) for a, b in zip(labels, old['exp_params'])), ', '.join(a + ' ' + str(b) for a, b in zip(labels, value)))
        elif key == 'learnings':
            previous = sorted(((x['level'], x['skill_id']) for x in old['learnings']), key=lambda row: row[0])
            add('learnings', describe_class(None, None, previous, name_of)[0].replace('Learnings: ', ''), describe_class(None, None, value, name_of)[0].replace('Learnings: ', ''))
        elif key == 'effects':
            before = [(x['code'], x['data_id'], x['value1'], x['value2']) for x in old['effects']]
            before_text, _ = describe_effects(before, name_of)
            after_text, warns = describe_effects(value, name_of)
            add('effects', '; '.join(before_text) or 'none', '; '.join(after_text) or 'none')
            warnings += warns
        elif key == 'actions':
            before = [(x['condition_type'], x['condition_param1'], x['condition_param2'], x['skill_id'], x['rating']) for x in old['actions']]
            max_mp = (out.get('params') or old['params'])[1]
            before_text, _ = describe_actions(before, name_of, skill_info, max_mp)
            after_text, warns = describe_actions(value, name_of, skill_info, max_mp)
            add('actions', '; '.join(before_text), '; '.join(after_text))
            warnings += warns
        elif key == 'drop_items':
            before = [(x['kind'], x['data_id'], x['denominator']) for x in old['drop_items']]
            add('drop_items', '; '.join(describe_drops(before, name_of)), '; '.join(describe_drops(value, name_of)))
        elif key == 'members':
            def show(members):
                return '; '.join('enemy %s%s at (%s,%s)%s' % (m['enemy_id'], (' ' + quote(name_of('enemy', m['enemy_id']))) if name_of('enemy', m['enemy_id']) else '', m['x'], m['y'],
                                                           ' hidden' if m['hidden'] else '') for m in members)
            add('members', show(old['members']), show(value))
        elif key == 'equips':
            for slot in range(EQUIP_SLOTS):
                if old['equips'][slot] != value[slot]:
                    kind = 'weapon' if slot == 0 else 'armor'

                    def item(number):
                        return 'empty' if number == 0 else kind + ' ' + str(number) + ((' ' + quote(name_of(kind, number))) if name_of(kind, number) else '')
                    add('equips[' + str(slot) + '] ' + ETYPES[slot], item(old['equips'][slot]), item(value[slot]))
        elif key == 'class_id':
            def klass(number):
                return 'class ' + str(number) + ((' ' + quote(name_of('class', number))) if name_of('class', number) else '')
            add('class_id', klass(old['class_id']), klass(value))
        elif key.startswith('damage_'):
            part = {'damage_formula': 'formula', 'damage_variance': 'variance', 'damage_critical': 'critical'}[key]
            add(key, old['damage'][part], value)
        else:
            add(key, old.get(key), value)
    if any(key in out for key in FEATURE_KEYS):
        before = feature_tuples(old['features'])
        plan = feature_plan(before, out, table)
        final = plan_rows(plan, before)
        removed, added, changed = feature_changes(before, final)
        text = lambda row: describe_features([row], name_of)[0][0]
        for row in removed:
            add('features', text(row), '(removed)')
        for first, second in changed:
            add('features', text(first), text(second))
        for row in added:
            add('features', '(not present)', text(row))
        _, warns = describe_features(added + [new for _, new in changed], name_of)
        warnings += warns
        warnings += dropped_feature_warning(table, before, final, 'features' in out, name_of)
        if table == 'classes':
            warnings += class_feature_warnings([row[:2] for row in final], [row[:2] for row in before], 'features' in out, name_of)
    if not rows:
        warnings.append('Nothing changes: every listed field already holds the requested value.')
    return rows, warnings


def row_lines(rows):
    return [row['field'] + ': ' + str(row['old']) + ' -> ' + str(row['new']) for row in rows]
