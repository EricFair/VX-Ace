#!/usr/bin/env python3
"""Dry-run of a recipe: `vxace_recipe.py plan` predicts what `run` would do without creating any project copy.

The original project is only read. Every step is simulated in memory: the native files it touches live in an overlay
(file -> decoded root) that the existing loaders see instead of the disk, so each later step reads the state its
predecessors would have written. A step runs the same snapshot functions, the same spec builder, the same spec-shape
validators, the same python mutator and the same transition verifiers as `run`; only the bytes are never written and the
hashes (which depend on earlier writes) are reported as bound at run time."""
from __future__ import annotations
import contextlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
import vxace_recipe as R
from vxace_copy_patcher import current_inventory, normalize_changes
from vxace_index_query import unlinked

VERSION = '1.29.0'
PREDICTED = 'predicted, verify after run'
EXACT = 'exact'
HASHES = 'bound at run time'
# Kinds that make the real copy patcher advance System.version_id (reload_required in vxace_copy_patcher.build).
VERSION_BUMP = {'map_event', 'map_name', 'map_encounter', 'map_shop'}
FILES = {'actors': 'Actors', 'classes': 'Classes', 'enemies': 'Enemies', 'items': 'Items', 'skills': 'Skills', 'states': 'States',
         'weapons': 'Weapons', 'armors': 'Armors', 'troops': 'Troops'}
ID_KIND = {'item': 'items', 'weapon': 'weapons', 'armor': 'armors', 'actor': 'actors', 'troop': 'troops', 'common event': 'common_events'}
RESTRICTED_RECOMMEND = {'append_blank_map', 'add_area', 'append_blank_event', 'append_dialogue_event', 'append_staged_event', 'append_common_event', 'add_treasure_chest', 'add_touch_trigger',
                        'add_shop', 'append_encounter', 'insert_script', 'set_system_fields', 'append_learning'}


class PlanRefusal(Exception):
    """A step the real run would refuse (or that cannot be planned)."""


# ---------------------------------------------------------------- the in-memory overlay

class Sim:
    """Decoded native roots that shadow the project's files while a plan runs; the project on disk is never written."""

    def __init__(self, project, rtp):
        self.project, self.rtp = project, rtp
        self.roots = {}
        self.touched = []
        self.original_load = None

    @staticmethod
    def key(path):
        return os.path.normcase(str(Path(path).resolve()))

    def rel(self, path):
        return Path(path).resolve().relative_to(self.project).as_posix()

    def path(self, rel):
        return self.project / rel

    def fake_load(self, path):
        from vxace_python_mutator import marshal_rb
        key = self.key(path)
        if key in self.roots:
            raw = marshal_rb.dump(self.roots[key])
            return marshal_rb.load(raw), raw
        return self.original_load(path)

    def fake_load_native(self, project, relative):
        """vxace_staged_commands.load_native over the overlay (a map created by an earlier step has no file on disk yet)."""
        from vxace_python_mutator import marshal_rb
        key = self.key(Path(project) / 'Data' / relative)
        if key in self.roots:
            return marshal_rb.load(marshal_rb.dump(self.roots[key]))
        return self.original_load_native(project, relative)

    def fake_inventory(self, project):
        """vxace_maps.inventory over the overlay: edited maps hash their simulated bytes and new maps are listed (the files do not exist on disk)."""
        import hashlib
        from vxace_python_mutator import marshal_rb
        rows, _ = self.original_inventory(project)
        by_id = {row['id']: row for row in rows}
        folder = os.path.normcase(str((self.project / 'Data').resolve()))
        for key, root in self.roots.items():
            match = re.fullmatch(r'map([0-9]{3})\.rvdata2', os.path.basename(key), re.IGNORECASE)
            if match and os.path.dirname(key) == folder:
                by_id[int(match[1])] = {'id': int(match[1]), 'sha256': hashlib.sha256(marshal_rb.dump(root)).hexdigest()}
        rows = [by_id[number] for number in sorted(by_id)]
        return rows, hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def get(self, rel):
        import vxace_python_mutator as backend
        return backend.load(self.path(rel))[0]

    def store(self, rel, root):
        """Keep `root` as the new content of a file, after the same gates a real write has to pass (decodes cleanly, byte-stable)."""
        from vxace_python_mutator import marshal_rb
        raw = marshal_rb.dump(root)
        reloaded, warnings = marshal_rb.load_with_warnings(raw)
        if warnings or marshal_rb.dump(reloaded) != raw:
            raise PlanRefusal(f'{rel}: the written file would not reload byte-identically')
        self.roots[self.key(self.path(rel))] = reloaded
        if rel not in self.touched:
            self.touched.append(rel)


@contextlib.contextmanager
def installed(sim):
    """Route vxace_python_mutator.load (used lazily by every snapshot/validator module) through the overlay."""
    import vxace_maps
    import vxace_python_mutator as backend
    import vxace_staged_commands
    sim.original_load, sim.original_load_native, sim.original_inventory = backend.load, vxace_staged_commands.load_native, vxace_maps.inventory
    backend.load, vxace_staged_commands.load_native, vxace_maps.inventory = sim.fake_load, sim.fake_load_native, sim.fake_inventory
    try:
        yield sim
    finally:
        backend.load, vxace_staged_commands.load_native, vxace_maps.inventory = sim.original_load, sim.original_load_native, sim.original_inventory


def text_of(value):
    return value.data.decode('utf-8', 'replace') if hasattr(value, 'data') else None


def entry_name(sim, table, number):
    """Name of a database entry in the simulated state (None when absent or unnamed)."""
    try:
        root = sim.get(f'Data/{FILES[table]}.rvdata2') if table in FILES else sim.get('Data/CommonEvents.rvdata2')
        entry = root[number] if 0 < number < len(root) else None
        return text_of(entry.get('name')) or None if entry is not None else None
    except Exception:
        return None


# ---------------------------------------------------------------- per-step snapshot (root-level twins of the snapshot CLIs)

def entry_target(step):
    kind = step['type']
    if kind == 'append_entry':
        return f'Data/{FILES[step["table"]]}.rvdata2'
    return 'Data/Items.rvdata2' if kind == 'append_key_item' else 'Data/Classes.rvdata2'


def take_snapshot(sim, step, recipe_dir, source_text):
    """The snapshot dict the real step's snapshot CLI would write, computed from the simulated state (no index cross-check)."""
    from vxace_staged_commands import staged_refs, graphic_names
    project, rtp = sim.project, sim.rtp
    kind = step['type']
    if kind in ('append_entry', 'append_key_item'):
        path = sim.path(entry_target(step))
        root = sim.get(entry_target(step))
        if kind == 'append_key_item':
            from vxace_database_entries import snapshot
            return snapshot(root, step['template_item'])
        from vxace_database_append import snapshot, snapshot_refs, actor_graphics
        refs = snapshot_refs(path, step['table'])
        assets = None
        if step['table'] == 'actors':
            characters, faces = actor_graphics(step['overrides'])
            if characters or faces:
                from vxace_character_graphics import actor_assets
                assets = actor_assets(project, rtp, tuple(sorted(characters)), tuple(sorted(faces)))
        return snapshot(root, step['table'], step['template_id'], refs, assets)
    if kind == 'set_system_fields':
        from vxace_system_fields import snapshot
        start = step.get('start')
        return snapshot(sim.get('Data/System.rvdata2'), project, start['map_id'] if isinstance(start, dict) and R.is_int(start.get('map_id')) else None)
    if kind == 'append_learning':
        from vxace_class_learning import snapshot, skills_for
        path = sim.path('Data/Classes.rvdata2')
        return snapshot(sim.get('Data/Classes.rvdata2'), skills_for(path), step['class_id'])
    if kind in ('append_dialogue_event', 'append_staged_event', 'append_blank_event'):
        import vxace_map_events as events
        root = sim.get(f'Data/Map{step["map_id"]:03d}.rvdata2')
        if kind == 'append_blank_event':
            donor_root = sim.get(f'Data/Map{step["donor_map_id"]:03d}.rvdata2') if 'donor_map_id' in step else None
            return {'map_id': step['map_id'], **events.blank_snapshot(root, step['donor_event'], donor_root)}
        result = {'map_id': step['map_id'], **events.snapshot(root, step['template_event'])}
        if kind == 'append_staged_event':
            info = events.system_info(project)
            result.update(system_sha256=info['system_sha256'], switch_count=len(info['switches']) - 1, variable_count=len(info['variables']) - 1,
                          switch_names=info['switches'][1:], variable_names=info['variables'][1:])
            result.update(events.reference_snapshot(project, tuple(sorted(staged_refs(step['pages'])['maps']))))
            names = graphic_names(step['pages'])
            if names:
                from vxace_character_graphics import staged_assets
                result['assets'] = staged_assets(project, rtp, tuple(sorted(names)))
        return result
    if kind == 'append_blank_map':
        import vxace_maps
        return vxace_maps.native_snapshot(project, step['template_map_id'], {key: step[key] for key in vxace_maps.OPTIONS if key in step})[2]
    if kind == 'append_common_event':
        from vxace_common_event_append import snapshot
        maps = tuple(sorted(staged_refs([{'condition': {}, 'commands': step['commands']}])['maps']))
        return snapshot(sim.get('Data/CommonEvents.rvdata2'), project, maps)
    if kind == 'add_shop':
        import vxace_map_shops as shops
        mid, eid = step['map_id'], step['event_id']
        target = f'Data/Map{mid:03d}.rvdata2'
        root = sim.get(target)
        shops.events_for(root)
        arrays = shops.goods_arrays(sim.path(target))
        event = shops.locate(root, eid)
        shape, lines, reason = None, [], None
        try:
            _, shape, lines = shops.event_shape(root, eid)
        except ValueError as error:
            reason = str(error)
        page = event.get('pages')[0] if isinstance(event.get('pages'), list) and len(event.get('pages')) == 1 else None
        return {'map_id': mid, 'event_id': eid, 'target': target, 'event_name': text_of(event.get('name')),
                'map_sha256': shops.digest(root), 'event_sha256': shops.digest(event),
                'list_sha256': shops.digest(page.get('list')) if page is not None and isinstance(page.get('list'), list) else None,
                'items_sha256': shops.digest(arrays['item']), 'weapons_sha256': shops.digest(arrays['weapon']), 'armors_sha256': shops.digest(arrays['armor']),
                'event_shape': shape, 'dialogue_lines': lines, 'append_supported': shape is not None, 'unsupported_reason': reason}
    if kind == 'append_encounter':
        import hashlib
        import vxace_map_encounters as enc
        from vxace_map_names import fingerprint
        from collections import Counter
        target = f'Data/Map{step["map_id"]:03d}.rvdata2'
        root = sim.get(target)
        rows = enc.existing(root)
        troops = enc.troops_for(sim.path(target))
        table = enc.table_for(root)
        layer = table.xsize * table.ysize
        painted = Counter(x >> 8 for x in table.data[3 * layer:] if x >> 8)
        return {'map_id': step['map_id'], 'target': target, 'map_sha256': fingerprint(root), 'encounter_count': len(rows),
                'encounter_step': root.get('encounter_step'), 'troops_sha256': enc.troops_digest(troops), 'troop_id_range': [1, len(troops) - 1],
                'troops': {i: text_of(t.get('name')) for i, t in enumerate(troops) if i}, 'painted_region_counts': dict(sorted(painted.items())),
                'raw_file_sha256': hashlib.sha256(__import__('vxace_python_mutator').marshal_rb.dump(root)).hexdigest()}
    if kind == 'set_map_display_name':
        import hashlib
        import vxace_map_names as names
        from vxace_python_mutator import marshal_rb
        root = sim.get(f'Data/Map{step["map_id"]:03d}.rvdata2')
        return {'map_id': step['map_id'], 'display_name': names.current(root), 'map_sha256': hashlib.sha256(marshal_rb.dump(root)).hexdigest()}
    if kind == 'insert_script':
        import vxace_script_slots as slots
        root = sim.get('Data/Scripts.rvdata2')
        found = [number for number, name in enumerate(slots.archive(root)[0]) if name == 'Main']
        if len(found) != 1:
            raise R.StepFailure('Expected exactly one Main script to anchor the insertion')
        return slots.snapshot(root, found[0])
    raise R.RecipeError(f'step type {kind} has no snapshot')


# ---------------------------------------------------------------- applying one change in memory

def verify_change(sim, change, before, after, extras):
    """The transition verifiers the copy patcher runs after the mutator (same arguments, simulated roots)."""
    kind, mutation, project, rtp = change['kind'], change['ruby_spec']['mutation'], sim.project, sim.rtp
    if kind == 'map_event':
        from vxace_map_events import verify_transition
        verify_transition(before, after, mutation, project, rtp)
    elif kind == 'database_entry':
        table = change['locator']['table']
        if table == 'classes' and mutation.get('action') == 'append_class_learning':
            from vxace_class_learning import verify_transition
            verify_transition(before, after, mutation, extras['skills'])
        elif mutation.get('action') == 'append_key_item':
            from vxace_database_entries import verify_transition
            verify_transition(before, after, mutation)
        else:
            from vxace_database_append import verify_transition
            verify_transition(before, after, table, mutation, extras['refs'], project if 'expected_assets' in mutation else None, rtp)
    elif kind == 'system_fields':
        from vxace_system_fields import verify_transition
        verify_transition(before, after, mutation, project)
    elif kind == 'common_event':
        from vxace_common_event_append import verify_transition
        verify_transition(before, after, mutation, project)
    elif kind == 'map_shop':
        from vxace_map_shops import verify_transition
        verify_transition(before, after, mutation, extras['arrays'])
    elif kind == 'map_encounter':
        from vxace_map_encounters import verify_transition
        verify_transition(before, after, mutation, extras['troops'])
    elif kind == 'map_name':
        from vxace_map_names import verify_transition
        verify_transition(before, after, mutation)
    elif kind == 'script_slot':
        from vxace_script_slots import verify_transition
        verify_transition(before, after, mutation)


def before_extras(sim, change):
    """Read-only context some verifiers need, taken before the mutation (as apply_one does)."""
    kind, target = change['kind'], sim.path(change['target'])
    if kind == 'database_entry':
        table = change['locator']['table']
        if table == 'classes' and change['ruby_spec']['mutation'].get('action') == 'append_class_learning':
            from vxace_class_learning import skills_for
            return {'skills': skills_for(target)}
        from vxace_database_append import snapshot_refs, SNAPSHOT_REFS
        key_item = table == 'items' and change['ruby_spec']['mutation'].get('action') == 'append_key_item'
        return {'refs': snapshot_refs(target, table) if table in SNAPSHOT_REFS and not key_item else None}
    if kind == 'map_shop':
        from vxace_map_shops import goods_arrays
        return {'arrays': goods_arrays(target)}
    if kind == 'map_encounter':
        from vxace_map_encounters import troops_for
        return {'troops': troops_for(target)}
    return {}


def apply_changes(sim, spec, index_dir=None):
    """Apply every change of a spec to the overlay. Returns the list of target files it changes (System included when its version advances)."""
    import vxace_python_mutator as backend
    from vxace_python_mutator import marshal_rb
    from vxace_staged_commands import graphic_names
    changes = normalize_changes(index_dir, spec)
    targets = []
    for change in changes:
        mutation = change['ruby_spec'].get('mutation', {})
        if change['kind'] == 'map_entry':
            # the copy patcher's apply_map_append: two native files together, existing entries and maps preserved
            import vxace_maps
            infos = backend.load(sim.path('Data/MapInfos.rvdata2'))[0]
            before_raw = marshal_rb.dump(infos)
            proposed_info, proposed_map = vxace_maps.candidates(infos, mutation, sim.project)
            retained = marshal_rb.load(marshal_rb.dump(proposed_info))
            retained.pairs.pop()
            if marshal_rb.dump(retained) != before_raw:
                raise PlanRefusal('Map append changed existing map-info entries or aliases')
            new_rel = f"Data/Map{mutation['new_id']:03d}.rvdata2"
            if sim.key(sim.path(new_rel)) in sim.roots or sim.path(new_rel).exists():
                raise PlanRefusal('New map file already exists; never overwrite maps')
            sim.store('Data/MapInfos.rvdata2', proposed_info)
            sim.store(new_rel, proposed_map)
            targets += ['Data/MapInfos.rvdata2', new_rel]
            continue
        graphics = isinstance(mutation, dict) and ('graphic' in mutation or graphic_names(mutation.get('pages')))
        if graphics or (isinstance(mutation, dict) and 'expected_assets' in mutation):
            change['ruby_spec']['context'] = {'rtp': str(sim.rtp) if sim.rtp else None}
        target = sim.path(change['target'])
        extras = before_extras(sim, change)
        before = backend.load(target)[0]
        after = backend.load(target)[0]
        backend.apply(after, change['ruby_spec'], source_path=target)
        verify_change(sim, change, before, after, extras)
        if marshal_rb.dump(before) == marshal_rb.dump(after):
            raise PlanRefusal(f'mutation produced no semantic change: {change["target"]}')
        sim.store(change['target'], after)
        targets.append(change['target'])
    if any(change['kind'] in VERSION_BUMP for change in changes):
        system = backend.load(sim.path('Data/System.rvdata2'))[0]
        version = system.get('version_id')
        backend.apply(system, {'type': 'system_version', 'mutation': {'expected_version': version}})
        sim.store('Data/System.rvdata2', system)
        targets.append('Data/System.rvdata2')
    return targets


# ---------------------------------------------------------------- human summaries and warnings

def find_links(value, created, where=''):
    """Every {"from_step": k} inside a step with the id it resolves to."""
    if R.is_ref(value):
        return [{'at': where or '(value)', 'from_step': value['from_step'], 'resolved_id': created.get(value['from_step'])}]
    out = []
    if isinstance(value, dict):
        for key, item in value.items():
            out += find_links(item, created, f'{where}.{key}' if where else key)
    elif isinstance(value, list):
        for number, item in enumerate(value):
            out += find_links(item, created, f'{where}[{number}]')
    return out


def goods_label(sim, kind, number):
    name = entry_name(sim, ID_KIND[kind], number)
    return f'{kind} {number}' + (f' "{name}"' if name else ' (unnamed)')


def describe_entry(sim, step, snapshot, spec_mutation):
    """Summary lines and warnings of an appended database entry (effects/features through the existing describers)."""
    table, overrides = step['table'], step['overrides']
    new_id = snapshot['next_id']
    lines = [f'Append {table} entry {new_id} "{overrides.get("name", snapshot["template_name"])}" cloned from template {step["template_id"]} "{snapshot["template_name"]}".']
    others = sorted(set(overrides) - {'name', 'effects', 'features', 'members', 'actions', 'drop_items'} - ({'exp_params', 'params', 'learnings'} if table == 'classes' else set()))
    if others:
        lines.append('Overrides: ' + ', '.join(f'{key}={json.dumps(overrides[key], ensure_ascii=False)[:60]}' for key in others))
    warnings = []
    from vxace_database_append import effect_rows, feature_rows, describe_effects, describe_features, mutation_refs, action_rows, drop_rows, describe_actions, describe_drops
    from vxace_database_append import exp_params_value, class_params_spec, learning_rows, describe_class, class_feature_warnings, feature_pairs, load_reference
    try:
        roots = mutation_refs(sim.path(entry_target(step)), table, spec_mutation)
        roots[table] = sim.get(entry_target(step))
        if table == 'classes':
            for extra in ('system', 'skills'):
                if extra not in roots:       # names only: the hash-bound validation below uses the same roots, which then simply hold more
                    try:
                        roots[extra] = load_reference(sim.path(entry_target(step)), extra)
                    except Exception:
                        pass

        def name_of(kind, number):
            if kind == 'element':
                system = roots.get('system')
                elements = system.get('elements') if system is not None else None
                return text_of(elements[number]) if elements and 0 <= number < len(elements) else None
            if kind == 'switch':
                system = roots.get('system')
                names = system.get('switches') if system is not None else None
                return text_of(names[number]) or None if names and 0 <= number < len(names) and names[number] is not None else None
            if kind in ('skill type', 'weapon type', 'armor type'):
                system = roots.get('system')
                names = system.get(kind.replace(' ', '_') + 's') if system is not None else None
                return text_of(names[number]) or None if names and 0 <= number < len(names) else None
            source = roots.get({'state': 'states', 'skill': 'skills', 'common event': 'common_events', 'item': 'items', 'weapon': 'weapons', 'armor': 'armors', 'class': 'classes'}.get(kind))
            row = source[number] if source is not None and 0 <= number < len(source) else None
            return text_of(row.get('name')) if row is not None else None
        for key, rows, describe in (('effects', effect_rows, describe_effects), ('features', feature_rows, describe_features)):
            if key in overrides:
                text, warns = describe(rows(overrides[key], roots, table) if key == 'features' else rows(overrides[key], roots), name_of)
                lines += [f'{key[:-1].title()}: {item}' for item in text] or [f'{key.title()}: none']
                warnings += warns
        if table == 'classes':
            exp = exp_params_value(overrides['exp_params']) if 'exp_params' in overrides else None
            spec = class_params_spec(overrides['params'], roots) if 'params' in overrides else None
            learned = learning_rows(overrides['learnings'], roots) if 'learnings' in overrides else None
            lines += [f'Class: {item}' for item in describe_class(exp, spec, learned, name_of)]
            template_pairs = feature_pairs(roots[table][step['template_id']].get('features'))
            effective = feature_pairs(feature_rows(overrides['features'], roots, table)) if 'features' in overrides else template_pairs
            warnings += class_feature_warnings(effective, template_pairs, 'features' in overrides, name_of)
        if 'actions' in overrides:
            def skill_info(number):
                row = roots['skills'][number] if 0 < number < len(roots['skills']) else None
                return {k: row.get(k) for k in ('scope', 'mp_cost', 'tp_cost')} if row is not None else None
            params = overrides.get('params') if isinstance(overrides.get('params'), list) and len(overrides['params']) == 8 else roots[table][step['template_id']].get('params')
            text, warns = describe_actions(action_rows(overrides['actions'], roots), name_of, skill_info, params[1] if params else None)
            lines += [f'Action: {item}' for item in text]
            warnings += warns
        if 'drop_items' in overrides:
            lines += [f'Drop: {item}' for item in describe_drops(drop_rows(overrides['drop_items'], roots), name_of)]
    except Exception as error:
        lines.append(f'(effects/features not described: {error})')
    if table == 'troops':
        names = [entry_name(sim, 'enemies', member.get('enemy_id')) for member in overrides.get('members', []) if isinstance(member, dict)]
        lines.append('Members: ' + ', '.join(f'{member.get("enemy_id")} "{name}"' for member, name in zip(overrides.get('members', []), names)))
    return lines, warnings


def describe_step(sim, step, snapshot, mutation, number, plan_links):
    """(summary lines, warnings) for one concrete transaction, built from the simulated state."""
    kind = step['type']
    warnings = []
    if kind == 'append_entry':
        lines, warnings = describe_entry(sim, step, snapshot, mutation)
        if step['table'] == 'actors' and not plan_links.get(number):
            warnings.append('The new actor is in no party yet: add it with set_system_fields party_members (new games) or a Change Party Member command; an old save only meets it through such a command.')
        return lines, warnings
    if kind == 'append_key_item':
        return [f'Append inert key item {snapshot["next_item_id"]} "{step["name"]}" cloned from template {step["template_item"]}: {step["description"]}'], warnings
    if kind == 'append_learning':
        return [f'Class {step["class_id"]} "{snapshot.get("class_name")}" learns skill {step["skill_id"]} "{entry_name(sim, "skills", step["skill_id"])}" at level {step["level"]}.'], warnings
    if kind == 'append_encounter':
        regions = step.get('region_ids', [])
        unpainted = [r for r in regions if not snapshot['painted_region_counts'].get(r)]
        if unpainted:
            warnings.append(f'Region(s) {unpainted} have no painted cells on map {step["map_id"]}: the encounter would never fire there.')
        return [f'Map {step["map_id"]}: append a random encounter of troop {step["troop_id"]} "{snapshot["troops"].get(step["troop_id"])}", weight {step["weight"]}'
                + (f', regions {regions}' if regions else ', whole map') + (f', encounter step {step["encounter_step"]}' if step.get('encounter_step') is not None else '') + '.'], warnings
    if kind == 'append_blank_map':
        planned = snapshot['planned_map']
        lines = [f'Append map {snapshot["new_id"]} "{step["name"]}" from ' + (f'map {step["template_map_id"]} (fresh map: schema only, none of its content is copied)' if planned['fresh'] else f'inert template map {step["template_map_id"]}')
                 + f': {planned["width"]}x{planned["height"]}, tileset {planned["tileset_id"]}, '
                 + (f'child of map {planned["parent_id"]}' if planned['parent_id'] else 'root level') + ', no events.']
        if planned['floor_tile_id'] is not None:
            lines.append(f'  Floor: A5 tile index {planned["fill_floor"]} (tile id {planned["floor_tile_id"]}) on layer 0 of every cell; the other layers, regions and shadows stay 0.')
            warnings.append('fill_floor only makes a walkable placeholder room; real level design stays manual in the editor.')
        elif planned['tiles_rebuilt']:
            warnings.append('The new map has a different size or tileset than its template, so its tile Table starts empty (all 0); paint it in the editor.')
        return lines, warnings
    if kind == 'append_blank_event':
        donor = f'donor event {step["donor_event"]}' + (f' of map {step["donor_map_id"]}' if 'donor_map_id' in step else '')
        return [f'Map {step["map_id"]}: append blank event {snapshot["next_event_id"]} "{step.get("name", snapshot["default_name"])}" at ({step["x"]},{step["y"]}) ({donor} for schema only).'], warnings
    if kind == 'append_dialogue_event':
        return [f'Map {step["map_id"]}: append dialogue event {snapshot["next_event_id"]} "{step["name"]}" at ({step["x"]},{step["y"]}), template event {step["template_event"]}.'] + [f'  "{line}"' for line in step['lines']], warnings
    if kind == 'append_staged_event':
        from vxace_impact import staged_page_report
        from vxace_staged_commands import chest_summary, iter_ops
        rows, warnings = staged_page_report(step['pages'], [''] + list(snapshot['switch_names']), [''] + list(snapshot['variable_names']))
        lines = [f'Map {step["map_id"]}: append {len(step["pages"])}-page staged event {snapshot["next_event_id"]} "{step["name"]}" at ({step["x"]},{step["y"]}), template event {step["template_event"]}.']
        for row in rows:
            extra = (f', trigger {row["trigger"]}' if row['trigger'] != 'action' else '') + (f', move {json.dumps(row["move"])}' if row.get('move') else '')
            lines.append(f'  page {row["page"]}: condition {json.dumps(row["condition"])}, {row["commands"]} command(s){extra}')
        for chest in chest_summary(step['pages']):
            gives = []
            for op in chest['gives']:
                if 'gold' in op:
                    gives.append(f'{op["gold"]} gold')
                else:
                    goods = next(key for key in ('item', 'weapon', 'armor') if key in op)
                    gives.append(f'{op["amount"]} x {goods_label(sim, goods, op[goods])}')
            lines.append(f'  Treasure chest: page {chest["page"]} gives {", ".join(gives)} and turns self switch {chest["self_switch"]} ON; page {chest["opened_page"]} is the opened chest.')
        return lines, warnings
    if kind == 'append_common_event':
        from vxace_common_event_append import analyse
        import vxace_map_events as events

        def lookup(what, number):
            if what in ('switch', 'variable'):
                names = snapshot['switch_names' if what == 'switch' else 'variable_names']
                return names[number - 1] or None if 1 <= number <= len(names) else None
            if what == 'map':
                from vxace_staged_commands import load_mapinfos
                try:
                    for key, value in load_mapinfos(sim.project).pairs:
                        if key == number:
                            return text_of(value.get('name'))
                except Exception:
                    return None
                return None
            return entry_name(sim, ID_KIND[what], number)
        analysis = analyse(mutation, lookup)
        return ([f'Append {step["trigger"]} common event {snapshot["next_id"]} "{step["name"]}".'] + [f'  {row}' for row in analysis['summary']]), list(analysis['warnings'])
    if kind == 'add_shop':
        from vxace_map_shops import goods_arrays
        arrays = goods_arrays(sim.path(f'Data/Map{step["map_id"]:03d}.rvdata2'))
        lines = [f'Map {step["map_id"]} event {step["event_id"]} "{snapshot["event_name"]}": add a {len(step["goods"])}-item shop ({"purchase only" if step["purchase_only"] else "buy and sell"}).']
        for good in step['goods']:
            row = arrays[good['type']][good['id']] if 0 < good['id'] < len(arrays[good['type']]) else None
            base = row.get('price') if row is not None else None
            lines.append(f'  {goods_label(sim, good["type"], good["id"])}: ' + (f'database price {base}' if good['price'] is None else f'price {good["price"]} (database {base})'))
        return lines, warnings
    if kind == 'insert_script':
        return [f'Insert script "{step["name"]}" ({len(mutation["source"].encode("utf-8"))} bytes) before Main as script id {snapshot["unused_id_candidate"]}.'], warnings
    if kind == 'set_map_display_name':
        return [f'Map {step["map_id"]} display name: "{snapshot["display_name"]}" -> "{step["name"]}".'], warnings
    if kind == 'set_system_fields':
        from vxace_system_fields import describe, current
        old = current(sim.get('Data/System.rvdata2'))
        actor_names = {int(k): v for k, v in snapshot['actor_names'].items()}
        map_names = {int(k): v for k, v in snapshot['map_names'].items()}
        size = (snapshot['start_map']['width'], snapshot['start_map']['height']) if 'start_map' in snapshot else None
        rows, warnings = describe({k: v for k, v in mutation.items() if k not in ('action',) and not k.startswith('expected_')}, old, actor_names, map_names, size, snapshot['options'])
        return [f'System {row["field"]}: {json.dumps(row["old"], ensure_ascii=False)[:80]} -> {json.dumps(row["new"], ensure_ascii=False)[:80]}' for row in rows], warnings
    return [], warnings


# ---------------------------------------------------------------- one step

def new_record(number, step, tag, source, macro='add_treasure_chest'):
    return {'step': number, **({'macro': macro, 'part': tag} if tag else {}), 'type': step['type'], 'status': 'planned',
            'target_files': [], 'created_id': None, 'id_confidence': None, 'resolved_parameters': None, 'resolved_links': [],
            'hashes': HASHES, 'summary': [], 'warnings': [], 'error': None}


def plan_step(sim, number, step, created, recipe_dir, records, tag, plan_links, workdir, ruby, original_step=None, links_step=None, macro='add_treasure_chest'):
    """Simulate one concrete transaction. Appends its record to `records`; raises PlanRefusal after filling the error."""
    record = new_record(number, step, tag, sim.project, macro)
    records.append(record)
    record['resolved_links'] = find_links(links_step if links_step is not None else step, created)
    try:
        kind = step['type']
        resolved = R.resolve_refs(step, created)
        resolved_record = dict(resolved)
        source_text = None
        csv_path = None
        if kind == 'insert_script':
            path = (recipe_dir / resolved['source_file']).resolve()
            if not path.is_file():
                raise PlanRefusal(f'source_file not found: {path}')
            raw = path.read_bytes()
            try:
                source_text = raw.decode('utf-8', 'strict')
            except UnicodeDecodeError as error:
                raise PlanRefusal(f'source_file is not UTF-8: {error}')
            resolved_record = {**resolved, 'source_file': str(path), 'source_sha256': R.sha256(raw), 'source_bytes': len(raw)}
        elif kind == 'text_import':
            csv_path = (recipe_dir / resolved['csv']).resolve()
            if not csv_path.is_file():
                raise PlanRefusal(f'csv not found: {csv_path}')
            resolved_record = {**resolved, 'csv': str(csv_path), 'csv_sha256': R.sha256(csv_path.read_bytes())}
        record['resolved_parameters'] = resolved_record
        title = None
        if kind == 'text_import':
            plan_text_import(sim, number, resolved, csv_path, record, workdir, ruby)
            return record
        try:
            snapshot = take_snapshot(sim, resolved, recipe_dir, source_text)
        except (R.StepFailure, PlanRefusal):
            raise
        except Exception as error:
            raise PlanRefusal(f'snapshot refused: {error}')
        try:
            spec = R.build_spec(title, number, resolved, snapshot, source_text)
        except (KeyError, R.RecipeError) as error:
            raise PlanRefusal(f'cannot build spec from snapshot: {error}')
        mutation = spec['changes'][0]['mutation']
        record['created_id'] = R.created_id(resolved, snapshot)
        record['id_confidence'] = EXACT if record['created_id'] is not None else None
        try:
            lines, warnings = describe_step(sim, resolved, snapshot, mutation, number, plan_links)
        except Exception as error:
            lines, warnings = [f'(summary unavailable: {error})'], []
        try:
            record['target_files'] = apply_changes(sim, spec)
        except PlanRefusal:
            raise
        except Exception as error:
            raise PlanRefusal(f'mutation refused: {error}')
        record['summary'], record['warnings'] = lines, warnings
        return record
    except PlanRefusal as error:
        record['status'] = 'refused'
        record['id_confidence'] = None
        record['error'] = str(error)
        raise
    except R.StepFailure as error:
        record['status'] = 'refused'
        record['id_confidence'] = None
        record['error'] = str(error)
        raise PlanRefusal(str(error))
    except Exception as error:
        record['status'] = 'refused'
        record['id_confidence'] = None
        record['error'] = f'{type(error).__name__}: {error}'
        raise PlanRefusal(record['error'])


def plan_text_import(sim, number, resolved, csv_path, record, workdir, ruby):
    """text_import reads the project and its index, so it is computed against the ORIGINAL project; earlier steps' edits are not merged."""
    index = ensure_index(sim, workdir, ruby)
    directory = workdir / f'step-{number:02d}'
    directory.mkdir(parents=True, exist_ok=True)
    spec = directory / 'spec.json'
    args = [index, '--project', sim.project, '--csv', csv_path, '--spec-out', spec, '--report', directory / 'import.md', '--json', directory / 'import.json']
    if resolved.get('allow_shorter'):
        args.append('--allow-shorter')
    code, out, err = R.run_tool(directory / 'logs', 'text-import', 'vxace_text_import.py', args)
    if code != 0:
        raise PlanRefusal(f'text-import failed (exit {code}): {R.last_line(err, out)}')
    if not spec.is_file():
        raise PlanRefusal('text import produced no ordinary change (no main spec was written)')
    report = R.read_json(directory / 'import.json')
    side = [s for s in report.get('specs', []) if Path(s['file']).resolve() != spec.resolve()]
    changes = R.read_json(spec)['changes']
    record['summary'] = [f'Import edited text: {len(changes)} native change(s) from {csv_path.name}.']
    if side:
        record['summary'].append(f'{len(side)} map display-name side spec(s) are not applied by a recipe step (use set_map_display_name steps).')
    record['id_confidence'] = PREDICTED
    clash = bool(sim.touched)
    if clash:
        record['warnings'].append('text_import is computed from the original project; edits made by earlier steps of this recipe are not merged into it, so it is predicted only. Verify after run.')
        record['target_files'] = sorted({normalize_target(c, sim) for c in changes})
        return
    try:
        record['target_files'] = apply_changes(sim, R.read_json(spec), index)
    except Exception as error:
        raise PlanRefusal(f'mutation refused: {error}')
    record['warnings'].append('Later steps see the imported text in this plan; text_import is still reported as predicted because the real run re-derives it from the previous copy.')


def normalize_target(change, sim):
    try:
        return normalize_changes(None, {'changes': [change]})[0]['target']
    except Exception:
        return '(unknown)'


def ensure_index(sim, workdir, ruby):
    index = workdir / 'index'
    if not index.is_dir():
        code, out, err = R.run_tool(workdir / 'logs', 'reader', 'vxace_project_reader.py', [sim.project, '--output', index, *(['--ruby', ruby] if ruby else [])])
        if code != 0:
            raise PlanRefusal(f'reader failed (exit {code}): {R.last_line(err, out)}')
    return index


def plan_area(sim, number, step, created, recipe_dir, records, plan_links, workdir, ruby):
    """Expand add_area like execute_area (R.expand_area); the sub-steps refer to each other by local numbers. Returns a record whose created_id is the new map id."""
    try:
        sub_steps = R.expand_area(R.resolve_refs(step, created), sim.project)
    except (R.RecipeError, ValueError) as error:
        record = new_record(number, step, '', sim.project, 'add_area')
        record.update(status='refused', error=str(error))
        records.append(record)
        raise PlanRefusal(str(error))
    local = {}
    for position, sub in enumerate(sub_steps, 1):
        record = plan_step(sim, number, sub, local, recipe_dir, records, 'abcdefgh'[position - 1], plan_links, workdir, ruby, links_step={}, macro='add_area')
        if position == 1:
            record['resolved_links'] = find_links(step, created)
        local[position] = record['created_id']
    return {'created_id': local[1]}


def plan_chest(sim, number, step, created, recipe_dir, records, plan_links, workdir, ruby):
    """Expand a macro (add_treasure_chest, add_touch_trigger) like execute_chest: an optional append_blank_event, then one append_staged_event."""
    macro = step['type']
    if macro == 'add_area':
        return plan_area(sim, number, step, created, recipe_dir, records, plan_links, workdir, ruby)
    try:
        blank, staged = R.MACROS[macro](R.resolve_refs(step, created), sim.project)
    except (R.RecipeError, ValueError) as error:
        record = new_record(number, step, '', sim.project, macro)
        record.update(status='refused', error=str(error))
        records.append(record)
        raise PlanRefusal(str(error))
    if blank is not None:
        record = plan_step(sim, number, blank, created, recipe_dir, records, 'a', plan_links, workdir, ruby, macro=macro)
        staged['template_event'] = record['created_id']
    return plan_step(sim, number, staged, created, recipe_dir, records, 'b' if blank is not None else 'a', plan_links, workdir, ruby, links_step=step, macro=macro)


# ---------------------------------------------------------------- the plan

def tree_bytes(project):
    return sum(path.stat().st_size for path in project.rglob('*') if path.is_file())


def check_output(project, output):
    if output == project or project in output.parents or output in project.parents:
        raise R.RecipeError('Use a new output directory outside the original project')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise R.RecipeError('Output directory must be new or empty')


def link_targets(steps):
    """{step number: True} for every step referenced by another step (used for the actor-without-party advisory)."""
    found = {}
    for number, step in enumerate(steps, 1):
        for link in find_links(step, {}):
            found[link['from_step']] = True
    return found


def plan_recipe(recipe_path, project, output, ruby=None, rtp=None, in_place=False, backup_root=None):
    """Dry-run the recipe. Returns the plan dict; its status is 'ok', 'step_refused', 'validation_refused' or 'error'.
    With `in_place` the summary describes an in-place run (no retained project copies, a start backup under `backup_root`) instead of the copy-chain disk estimate."""
    recipe_path = Path(recipe_path).resolve()
    recipe = R.load_recipe(recipe_path)
    steps = recipe['steps']
    project, output = unlinked(project), unlinked(output).resolve()
    if rtp is not None:
        rtp = unlinked(rtp).resolve()
        if not rtp.is_dir() or rtp == output or output in rtp.parents or rtp in output.parents:
            raise R.RecipeError('--rtp must be an existing directory outside the output directory')
    if project.is_file() and project.suffix.lower() == '.rvproj2':
        project = project.parent
    project = project.resolve()
    if not (project / 'Data').is_dir():
        raise R.RecipeError('Expected a VX Ace project with Data/')
    check_output(project, output)
    ruby = ruby or shutil.which('ruby')
    before = current_inventory(project)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    plan = {'version': VERSION, 'title': recipe.get('title'), 'recipe': str(recipe_path), 'status': 'error', 'error': None, 'project': str(project),
            'output': str(output), 'validation': None, 'steps': records, 'refused_step': None, 'summary': None, 'smoke': None,
            'original_unchanged': None, 'original_files_checked': len(before), 'mutation_performed_on_original': False,
            'notes': ['Nothing was copied or written to the project. Hashes depend on earlier writes and are bound at run time.',
                      'Not simulated (checked only by run): the patch planner and impact report on the real index, per-step project-wide validation and round-trip preflight, post-copy re-index and selected-map tile audit.']}
    created = {}
    sim = Sim(project, rtp)
    try:
        code, out, err = R.run_tool(output / 'logs', 'validation', 'vxace_project_validator.py',
                                    [project, '--output', output / 'validation', '--backend', 'python', *(['--ruby', ruby] if ruby else [])])
        ready = bool(code == 0 and R.read_json(output / 'validation/validation.json').get('copy_mutation_ready'))
        plan['validation'] = {'exit_code': code, 'copy_mutation_ready': ready, 'output': str(output / 'validation')}
        if not ready:
            plan['status'] = 'validation_refused'
            plan['error'] = f'original project is not copy-mutation ready: {R.last_line(err, out)}'
        else:
            plan['status'] = 'ok'
            plan_links = link_targets(steps)
            with installed(sim):
                for number, step in enumerate(steps, 1):
                    try:
                        if step['type'] in R.MACROS:
                            record = plan_chest(sim, number, step, created, recipe_path.parent, records, plan_links, output, ruby)
                        else:
                            record = plan_step(sim, number, step, created, recipe_path.parent, records, '', plan_links, output, ruby)
                    except PlanRefusal as refusal:
                        plan['status'] = 'step_refused'
                        plan['refused_step'] = number
                        plan['error'] = f'step {number} ({step["type"]}): {refusal}'
                        break
                    if record['created_id'] is not None:
                        created[number] = record['created_id']
    except Exception as error:
        plan['status'] = 'error'
        plan['error'] = f'{type(error).__name__}: {error}'
    finally:
        plan['original_unchanged'] = current_inventory(project) == before
        if not plan['original_unchanged']:
            plan['status'] = 'error'
            plan['error'] = 'ORIGINAL PROJECT FILES CHANGED'
    plan['summary'] = summarize(plan, sim, project, steps, in_place, backup_root)
    plan['smoke'] = smoke_advice(steps)
    (output / 'recipe-plan.json').write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (output / 'recipe-plan.md').write_text(markdown_plan(plan), encoding='utf-8')
    return plan


def backup_bytes(project):
    """Size of what an in-place run backs up at the start: Data/*.rvdata2 and Game.ini."""
    files = list((project / 'Data').glob('*.rvdata2')) + [project / 'Game.ini']
    return sum(path.stat().st_size for path in files if path.is_file())


def summarize(plan, sim, project, steps, in_place=False, backup_root=None):
    planned = [r for r in plan['steps'] if r['status'] == 'planned']
    files = []
    for record in plan['steps']:
        for target in record['target_files']:
            if target not in files:
                files.append(target)
    size = tree_bytes(project)
    transactions = len(planned)
    summary = {'complete': plan['status'] == 'ok', 'recipe_steps': len(steps), 'steps_planned': len({r['step'] for r in planned}),
               'transactions': transactions, 'files_changed': files, 'project_bytes': size,
               'estimated_disk_bytes': size * (transactions + 1),
               'estimated_disk_note': 'project size x (transactions + 1), as in the recipes.md limits note; add one more copy for smoke staging',
               'in_place': bool(in_place)}
    if in_place:
        backup = backup_bytes(project)
        where = str(backup_root) if backup_root else '(--backup-root, required for the run)'
        summary.update(retained_project_copies=0, backup_bytes=backup, estimated_disk_bytes=backup,
                       in_place_line=f'in place on {project}, backup under {where}, 0 project copies',
                       estimated_disk_note=f'in-place run: {backup} bytes of backup; at most one transient temp copy ({size} bytes) exists at a time and is deleted after each step; add one more transient copy for smoke staging')
    return summary


def smoke_advice(steps):
    kinds = {step['type'] for step in steps}
    reasons = sorted(kinds & RESTRICTED_RECOMMEND)
    custom = sorted(kinds & {'append_staged_event', 'add_treasure_chest', 'add_touch_trigger', 'add_area', 'append_common_event', 'insert_script'})
    return {'recommended': bool(reasons), 'reason_steps': reasons,
            'suite_needed': bool(custom),
            'note': ('A --smoke-mode run boots the final copy; a --smoke-suite is needed to exercise the new behavior (' + ', '.join(custom) + ') in the engine.'
                     if custom else 'A plain --smoke-mode boot is enough as a sanity check; a suite is optional.' if reasons else 'Database-only recipe: smoke is optional.')}


def markdown_plan(plan):
    lines = ['# VX Ace recipe plan (dry run)', '', f'Recipe: {plan.get("title") or "(untitled)"}', f'Status: **{plan["status"]}**',
             'Original unchanged: **' + str(plan['original_unchanged']) + '**', 'No project copy was made; nothing was written to the project.', '']
    if plan.get('error'):
        lines += [f'Error: {plan["error"]}', '']
    summary = plan['summary']
    lines += ['## Summary', '', f'- Steps planned: {summary["steps_planned"]} of {summary["recipe_steps"]}' + ('' if summary['complete'] else ' (stopped)'),
              f'- Transactions: {summary["transactions"]}',
              '- Data files that will change: ' + (', '.join(f'`{f}`' for f in summary['files_changed']) or 'none'),
              (f'- Mode: **{summary["in_place_line"]}** (backup {summary["backup_bytes"] / 1048576:.2f} MiB; at most one transient temp copy of {summary["project_bytes"] / 1048576:.2f} MiB at a time)'
               if summary.get('in_place') else
               f'- Estimated disk use for `run`: {summary["estimated_disk_bytes"] / 1048576:.1f} MiB ({summary["project_bytes"] / 1048576:.2f} MiB x ({summary["transactions"]} + 1))'),
              f'- Smoke: {"recommended" if plan["smoke"]["recommended"] else "optional"}' + (', suite needed' if plan['smoke']['suite_needed'] else '') + f'. {plan["smoke"]["note"]}', '']
    lines += ['## Steps', '']
    for record in plan['steps']:
        lines.append(f'### Step {record["step"]}{record.get("part", "")}: {record["type"]} ({record["status"]})' + (f' [{record["macro"]}]' if record.get('macro') else ''))
        lines.append('- Target files: ' + (', '.join(f'`{f}`' for f in record['target_files']) or 'none'))
        if record['created_id'] is not None and record['status'] == 'refused':
            lines.append(f'- Id it would have taken: {record["created_id"]}')
        elif record['created_id'] is not None:
            lines.append(f'- Predicted new id: **{record["created_id"]}** ({record["id_confidence"]})')
        elif record['id_confidence']:
            lines.append(f'- Prediction: {record["id_confidence"]}')
        for link in record['resolved_links']:
            lines.append(f'- from_step {link["from_step"]} at `{link["at"]}` resolves to id {link["resolved_id"]}')
        lines.append(f'- Hashes: {record["hashes"]}')
        for row in record['summary']:
            lines.append(f'- {row}' if not row.startswith(' ') else f'  - {row.strip()}')
        for warning in record['warnings']:
            lines.append(f'- Warning: {warning}')
        if record['error']:
            lines.append(f'- Refused: {record["error"]}')
        lines.append('')
    lines += ['## Not covered by a plan', ''] + [f'- {note}' for note in plan['notes']] + ['', '`plan` checks the recipe against the project and predicts the result; `validate` checks shape only; `run` makes the copies and is the only evidence of the real bytes.']
    return '\n'.join(lines) + '\n'
