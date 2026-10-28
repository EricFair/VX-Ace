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
from vxace_index_query import unlinked

VERSION = '1.13.0'
ROOT = Path(__file__).resolve().parent
STEP_TIMEOUT = 1800
MAX_STEPS = 50
TABLES = ('enemies', 'skills', 'states', 'weapons', 'armors', 'troops')
STEP_KEYS = {
    'append_entry': ({'type', 'table', 'template_id', 'overrides'}, {'type', 'table', 'template_id', 'overrides'}),
    'append_key_item': ({'type', 'template_item', 'name', 'description'}, {'type', 'template_item', 'name', 'description'}),
    'append_encounter': ({'type', 'map_id', 'troop_id', 'weight'}, {'type', 'map_id', 'troop_id', 'weight', 'region_ids', 'encounter_step'}),
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
    if earlier.get('type') != 'append_entry' or earlier.get('table') != want_table:
        raise RecipeError(f'step {number}: {where} from_step {k} must be an append_entry step on table {want_table}')


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
            if contains_ref_key(shadow):
                raise RecipeError(f'step {number}: from_step is only allowed for troop members enemy_id')
        elif kind == 'append_key_item':
            if not is_int(step['template_item']) or step['template_item'] < 1:
                raise RecipeError(f'step {number}: template_item must be a positive integer')
            for key in ('name', 'description'):
                if not isinstance(step[key], str):
                    raise RecipeError(f'step {number}: {key} must be a string')
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
        if kind != 'append_entry' and kind != 'append_encounter' and contains_ref_key(step):
            raise RecipeError(f'step {number}: from_step is not allowed in a {kind} step')
        if kind == 'append_encounter' and contains_ref_key({k: v for k, v in step.items() if k != 'troop_id'}):
            raise RecipeError(f'step {number}: from_step is only allowed for troop_id')
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
        if step['table'] == 'troops':
            mutation['expected_enemies_sha256'] = snapshot['enemies_sha256']
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
    elif kind == 'append_encounter':
        change = {'kind': 'map_encounter', 'locator': {'map_id': step['map_id']},
                  'proposal': f'Recipe step {number}: append one random encounter to map {step["map_id"]}.',
                  'mutation': {'action': 'append_encounter', 'expected_map_sha256': snapshot['map_sha256'],
                               'expected_encounter_count': snapshot['encounter_count'], 'expected_troops_sha256': snapshot['troops_sha256'],
                               'troop_id': step['troop_id'], 'weight': step['weight'], 'region_ids': step.get('region_ids', []),
                               'encounter_step': step.get('encounter_step')}}
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


def execute_step(number, step, title, source, work, ruby, created, recipe_dir, records):
    """Run one step as a normal transaction. Returns its report record; raises StepFailure after filling the record."""
    directory = work / f'step-{number:02d}'
    directory.mkdir()
    logs = directory / 'logs'
    index, copy, audit = directory / 'index', directory / 'copy', directory / 'audit'
    record = {'step': number, 'type': step['type'], 'status': 'running', 'source': str(source), 'directory': str(directory),
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
                                                  '--backend', 'python', *(['--ruby', ruby] if ruby else [])])
        record['audit'] = str(audit / 'audit.json')
        record['copy'] = str(copy)
        if not copy.is_dir():
            fail('copy patcher reported success but the copy is missing')
        if record['created_id'] is not None:
            try:
                audited = read_json(audit / 'audit.json')['changes'][0]['entry']['created_id']
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


def markdown_report(report):
    lines = ['# VX Ace recipe report', '', f'Recipe: {report.get("title") or "(untitled)"}', f'Status: **{report["status"]}**',
             f'Original unchanged: **{report["original_unchanged"]}**', 'Mutation performed on original: **False**',
             f'Final copy: `{report["final_copy"]}`' if report['final_copy'] else 'Final copy: none', '']
    if report.get('error'):
        lines += [f'Error: {report["error"]}', '']
    lines += ['## Steps', '']
    for s in report['steps']:
        lines.append(f'### Step {s["step"]}: {s["type"]} ({s["status"]})')
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


def run_recipe(recipe_path, project, work, ruby=None, smoke=None):
    """Execute the recipe. Returns the report dict; its status is 'pass', 'step_failed', 'validation_refused', 'smoke_failed' or 'error'."""
    recipe_path = Path(recipe_path).resolve()
    recipe = load_recipe(recipe_path)
    steps = recipe['steps']
    project, work = unlinked(project), unlinked(work).resolve()
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
                    record = execute_step(number, step, recipe.get('title'), current, work, ruby, created, recipe_path.parent, records)
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
        report = run_recipe(args.recipe, args.project, args.work, args.ruby, smoke)
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
