#!/usr/bin/env python3
"""Guarded append of one skill learning to an existing native RPG::Class (Classes.rvdata2, with Skills.rvdata2 read-only)."""
from __future__ import annotations
import hashlib

VERSION = '1.14.0'
ACTION = 'append_class_learning'
# Fields the user writes in a spec; the copy patcher adds class_id from the locator before the native chain sees the mutation.
SPEC_FIELDS = {'action', 'expected_array_sha256', 'expected_class_sha256', 'expected_learning_count', 'expected_skills_sha256', 'skill_id', 'level'}
NATIVE_FIELDS = SPEC_FIELDS | {'class_id'}
CLASS_CLS = 'RPG::Class'
LEARNING_CLS = 'RPG::Class::Learning'
CLASS_FIELDS = {'id', 'name', 'icon_index', 'description', 'features', 'note', 'exp_params', 'params', 'learnings'}
LEARNING_FIELDS = {'level', 'skill_id', 'note'}
LEVEL_RANGE = (1, 99)
MAX_LEARNINGS = 256


def integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(label + ' outside integer bounds')
    return value


def digest(value):
    from vxace_python_mutator import marshal_rb
    return hashlib.sha256(marshal_rb.dump(value)).hexdigest()


def class_array(root):
    """Dense native Classes array: nil slot zero, RPG::Class entries with exact slot IDs, no aliases."""
    from vxace_python_mutator import RubyObject
    if not isinstance(root, list) or not 2 <= len(root) <= 1000 or root[0] is not None:
        raise ValueError('Expected native classes array with nil slot zero; supported array limit is 1000')
    for number, entry in enumerate(root[1:], 1):
        if not isinstance(entry, RubyObject) or entry.cls != CLASS_CLS or type(entry.get('id')) is not int or entry.get('id') != number:
            raise ValueError('Every existing classes entry must be ' + CLASS_CLS + ' with its exact array-slot ID')
    if len({id(entry) for entry in root[1:]}) != len(root) - 1:
        raise ValueError('Aliased classes entries are unsupported')
    return root


def skills_for(path):
    """Read-only load of Data/Skills.rvdata2 beside a native Data file (same snapshot/copy); returns the validated dense array."""
    from vxace_index_query import unlinked
    from vxace_python_mutator import load
    from vxace_database_append import database_array
    file = unlinked(path)
    if file.parent.name != 'Data':
        raise ValueError('Class learning append requires a native project Data path to read Skills')
    root, _ = load(unlinked(file.parent / 'Skills.rvdata2'))
    return database_array(root, 'skills')


def selected_class(root, class_id):
    """Validated selected class: exact native field set and a fully typed, unaliased learnings list."""
    from vxace_python_mutator import RubyObject, RubyString
    class_array(root)
    identifier = integer(class_id, 'class ID', 1, len(root) - 1)
    entry = root[identifier]
    if set(entry.ivars) != {'@' + k for k in CLASS_FIELDS}:
        raise ValueError('Selected class has unknown or missing native fields')
    learnings = entry.get('learnings')
    if not isinstance(learnings, list) or len(learnings) > MAX_LEARNINGS:
        raise ValueError('Selected class learnings are opaque or exceed the budget of ' + str(MAX_LEARNINGS))
    if len({id(x) for x in learnings}) != len(learnings):
        raise ValueError('Aliased learning entries are unsupported')
    for other in root[1:]:
        if other is not entry and other.get('learnings') is learnings:
            raise ValueError('The learnings list is shared with another class; refusing')
    for item in learnings:
        if not isinstance(item, RubyObject) or item.cls != LEARNING_CLS or set(item.ivars) != {'@' + k for k in LEARNING_FIELDS}:
            raise ValueError('Existing learning has an unsupported schema; only exact ' + LEARNING_CLS + ' (level, skill_id, note) is admitted')
        if type(item.get('level')) is not int or type(item.get('skill_id')) is not int or not isinstance(item.get('note'), RubyString):
            raise ValueError('Existing learning field types are unsupported')
    return entry


def new_learning(skill_id, level):
    from vxace_python_mutator import RubyObject, convert
    return RubyObject(LEARNING_CLS, {'@level': level, '@skill_id': skill_id, '@note': convert('')})


def skill_name(skills, skill_id):
    return skills[skill_id].get('name').data.decode('utf-8', 'replace')


def snapshot(root, skills, class_id):
    from vxace_database_append import database_array
    database_array(skills, 'skills')
    entry = selected_class(root, class_id)
    return {'array_sha256': digest(root), 'class_sha256': digest(entry), 'skills_sha256': digest(skills),
            'class_id': class_id, 'class_name': entry.get('name').data.decode('utf-8', 'replace'),
            'class_count': len(root) - 1, 'learning_count': len(entry.get('learnings')), 'max_learnings': MAX_LEARNINGS,
            'learnings': [{'index': n, 'level': x.get('level'), 'skill_id': x.get('skill_id'),
                           'skill_name': skill_name(skills, x.get('skill_id')) if 0 < x.get('skill_id') < len(skills) else None,
                           'note_present': bool(x.get('note').data)} for n, x in enumerate(entry.get('learnings'))],
            'skill_count': len(skills) - 1, 'valid_skill_id_range': [1, len(skills) - 1], 'valid_level_range': list(LEVEL_RANGE),
            'append_supported': len(entry.get('learnings')) < MAX_LEARNINGS,
            'scope': 'append-only one skill learning; no deletion/reordering/edit of existing learnings, no other class fields'}


def validate(root, mutation, skills):
    """Check every precondition; return (class, skill_id, level)."""
    from vxace_database_append import database_array
    if not isinstance(mutation, dict) or set(mutation) != NATIVE_FIELDS or mutation.get('action') != ACTION:
        raise ValueError('Only the exact ' + ACTION + ' schema is supported')
    class_array(root)
    database_array(skills, 'skills')
    entry = selected_class(root, mutation['class_id'])
    if mutation['expected_array_sha256'] != digest(root) or mutation['expected_class_sha256'] != digest(entry):
        raise ValueError('Classes array/class fingerprint is stale')
    if mutation['expected_skills_sha256'] != digest(skills):
        raise ValueError('Skills array fingerprint is stale')
    learnings = entry.get('learnings')
    if type(mutation['expected_learning_count']) is not int or mutation['expected_learning_count'] != len(learnings):
        raise ValueError('Stale learning count precondition')
    skill_id = integer(mutation['skill_id'], 'skill ID', 1, len(skills) - 1)
    if skills[skill_id] is None:
        raise ValueError('skill_id references a missing skill')
    level = integer(mutation['level'], 'level', *LEVEL_RANGE)
    if len(learnings) >= MAX_LEARNINGS:
        raise ValueError('Learning list budget exhausted')
    if any(x.get('skill_id') == skill_id for x in learnings):
        raise ValueError('The class already learns this skill (duplicate skill_id refused)')
    return entry, skill_id, level


def append_learning(root, mutation, skills):
    entry, skill_id, level = validate(root, mutation, skills)
    # Detach the list so nothing else can observe the append; existing learning objects stay shared with the old list.
    entry.set('learnings', list(entry.get('learnings')) + [new_learning(skill_id, level)])


def apply(root, mutation, source_path=None):
    if source_path is None:
        raise ValueError('Class learning append requires a native project path to read Skills')
    append_learning(root, mutation, skills_for(source_path))


def verify_transition(before, after, mutation, skills):
    """Prove the candidate is the old Classes array plus exactly the approved learning on the selected class."""
    from vxace_python_mutator import marshal_rb
    entry, skill_id, level = validate(before, mutation, skills)
    class_array(after)
    if len(after) != len(before):
        raise ValueError('Class-learning candidate changed the array shape')
    cid = mutation['class_id']
    kept_before = [x for n, x in enumerate(before) if n != cid]
    kept_after = [x for n, x in enumerate(after) if n != cid]
    if marshal_rb.dump(kept_before) != marshal_rb.dump(kept_after):
        raise ValueError('Class-learning candidate changed an unselected class')
    new = selected_class(after, cid)
    if list(new.ivars) != list(entry.ivars) or any(marshal_rb.dump(new.ivars[k]) != marshal_rb.dump(entry.ivars[k]) for k in entry.ivars if k != '@learnings'):
        raise ValueError('Class-learning candidate changed a field other than learnings')
    old_list, new_list = entry.get('learnings'), new.get('learnings')
    if len(new_list) != len(old_list) + 1 or marshal_rb.dump(new_list[:-1]) != marshal_rb.dump(old_list):
        raise ValueError('Class-learning candidate changed the existing learnings prefix')
    if marshal_rb.dump(new_list[-1]) != marshal_rb.dump(new_learning(skill_id, level)):
        raise ValueError('Class-learning candidate differs from the approved learning')


def native_mutation(locator, mutation):
    """Check the spec locator/mutation pair and return the mutation with class_id taken from the locator."""
    if not isinstance(locator, dict) or set(locator) != {'table', 'id'} or locator['table'] != 'classes':
        raise ValueError('Class learning locator must be exactly {"table": "classes", "id": CLASS_ID}')
    integer(locator['id'], 'class ID', 1, 999)
    if not isinstance(mutation, dict) or set(mutation) != SPEC_FIELDS or mutation.get('action') != ACTION:
        raise ValueError('Only the exact ' + ACTION + ' schema is supported')
    return {**mutation, 'class_id': locator['id']}


def indexed_snapshot(data, project, class_id):
    from pathlib import Path
    from vxace_index_query import unlinked
    from vxace_python_mutator import load
    file = Path(project) / 'Data' / 'Classes.rvdata2'
    root, _ = load(unlinked(file))
    skills = skills_for(file)
    result = snapshot(root, skills, class_id)
    indexed = data.json('database/classes.json')
    if not isinstance(indexed, list) or len(indexed) != len(root) or indexed[0] is not None:
        raise ValueError('Indexed/native Classes array sizes disagree')
    for number, row in enumerate(indexed[1:], 1):
        if not isinstance(row, dict) or row.get('__class__') != CLASS_CLS or type(row.get('id')) is not int or row['id'] != number:
            raise ValueError('Indexed/native class identities disagree')
    if indexed[class_id].get('name') != result['class_name']:
        raise ValueError('Indexed/native class names disagree')
    indexed_skills = data.json('database/skills.json')
    if not isinstance(indexed_skills, list) or len(indexed_skills) != len(skills):
        raise ValueError('Indexed/native Skills array sizes disagree')
    return {'version': VERSION, 'table': 'classes', **result,
            'limits': ['Only classes whose exact native field set and existing learnings schema are supported are admitted.',
                       'skill_id must be an existing static skill of the Skills array fingerprinted here (expected_skills_sha256); skill edits after the snapshot make the spec stale.',
                       'The learning is appended at the end with an empty note; existing learnings are never edited, removed or reordered.',
                       'The database reloads at startup, but actors already in old saves only learn the skill on their next level-up to or past that level (Game_Actor#level_up learns skills for the new level); nothing is learned retroactively.',
                       'Class learnings are not checked against actor initial levels, class-change scripts or custom skill-learning scripts; review those separately.',
                       'Snapshot is not mutation permission; use the reviewed Python disposable-copy workflow and a native level-up test.']}
