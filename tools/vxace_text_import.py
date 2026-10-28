#!/usr/bin/env python3
"""Turn an edited v1.7 text-export CSV into a reviewed patch spec of existing guarded change kinds; read-only."""
from __future__ import annotations
import argparse
import csv
import io
import json
import re
import sys
import unicodedata
from pathlib import Path
from vxace_index_query import Index, unlinked
from vxace_copy_patcher import verify_fresh, current_inventory
import vxace_text_export as te

VERSION = '1.10.0'
MAX_CSV_BYTES = 64 * 1024 * 1024
MAX_ROWS = 500000
CHOICE_SEPARATOR = ' | '
MULTILINE_DB_FIELDS = ('description', 'profile')
STATUSES = ('applied', 'unchanged', 'skipped_empty', 'stale', 'unknown', 'duplicate', 'refused_line_count',
            'refused_invalid', 'unsupported')
TEXT_COMMAND_CODES = {'actor_name': 320, 'actor_nickname': 324, 'actor_profile': 325}
LIMITS = [
    'Read-only: writes only the spec file(s) and the report, never the project or the index. Nothing is applied until you run the planner and the copy patcher.',
    'Only existing guarded change kinds are emitted: event set_parameter (existing 401/405/102/402/320/324/325 parameters), database field edits and map_name; no commands are inserted or deleted.',
    'Line counts must match the original block (101+401, 105+405). Adding or removing message lines is structural insertion and is out of scope; --allow-shorter pads with empty lines.',
    'The 101 header (face, background, position) and all non-text parameters are never touched.',
    'Choices (102) must keep their count; matching 402 branch labels are updated in the same row. Cancel type and branch bodies are untouched.',
    'System database text (game title, currency, terms, type names) has no id-addressed database edit and is reported as unsupported.',
    'Each map display name needs its own single-change transaction with a native map hash, so it is written to a separate numbered spec.',
    'Lint (width, control codes, references) is heuristic and reports warnings only; real font metrics and custom message systems are not modelled.',
    'Fingerprints and the fresh index guard staleness; the copy patcher re-checks the source and performs its own round-trip and post-copy gates.',
]


def map_name_snapshot(data, project, map_id):
    from vxace_map_names import indexed_snapshot
    return indexed_snapshot(data, project, map_id)


def read_csv(path):
    path = unlinked(path)
    if not path.is_file(): raise ValueError('CSV file not found')
    if path.stat().st_size > MAX_CSV_BYTES: raise ValueError('CSV file exceeds size budget')
    text = path.read_bytes().decode('utf-8-sig', 'strict')
    csv.field_size_limit(1 << 24)
    reader = csv.DictReader(io.StringIO(text, newline=''))
    missing = {'key', 'translation', 'fingerprint'} - set(reader.fieldnames or [])
    if missing: raise ValueError('CSV is missing column(s): ' + ', '.join(sorted(missing)))
    rows = []
    for n, row in enumerate(reader, 2):
        if len(rows) >= MAX_ROWS: raise ValueError('CSV row budget exceeded')
        if None in row or None in row.values(): raise ValueError('CSV row %d has the wrong number of columns' % n)
        rows.append({'row': n, **{k: v for k, v in row.items() if k is not None}})
    return rows


def normalize_newlines(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')


def invalid_chars(text):
    """Reject control characters except newline, surrogates and Unicode line/paragraph separators."""
    for ch in text:
        if ch == '\n': continue
        cat = unicodedata.category(ch)
        if cat in ('Cc', 'Cs') or cat in ('Zl', 'Zp'):
            return 'U+%04X' % ord(ch)
    return None


def locator_for(entry):
    scope = entry['scope']
    if scope == 'map':
        return {'map_id': entry['map_id'], 'event_id': entry['event_id'], 'page': entry['page']}
    if scope == 'common_event': return {'common_event_id': entry['common_event_id']}
    return {'troop_id': entry['troop_id'], 'page': entry['page']}


def event_change(entry, command_index, parameter_index, value, key, what):
    return {'kind': 'event', 'locator': {**locator_for(entry), 'command_index': command_index},
            'proposal': 'Import edited text for %s (%s).' % (key, what),
            'mutation': {'action': 'set_parameter', 'parameter_index': parameter_index, 'value': value}}


class Outcome:
    def __init__(self, row):
        self.row = row; self.status = None; self.reason = ''; self.changes = []; self.map_name = None
        self.warnings = []; self.notes = []

    def set(self, status, reason=''):
        self.status = status; self.reason = reason; return self


def fresh_entries(data, include_name_commands, settings):
    result = te.export_text(data, include_name_commands=include_name_commands, **settings)
    return result, {e['key']: e for e in result['entries']}


def lint_new(entry, lines, settings, rng):
    probe = {**entry, 'lines': list(lines), 'problems': [], 'group': entry.get('group', entry['scope'])}
    return te.lint_entry(probe, settings, rng)


def split_choices(translation):
    return translation.split('\n') if '\n' in translation else translation.split(CHOICE_SEPARATOR)


def process_row(row, entry, data, project, settings, rng, allow_shorter, commands_cache):
    out = Outcome(row)
    key = row['key']
    translation = normalize_newlines(row['translation'])
    bad = invalid_chars(translation)
    if bad: return out.set('refused_invalid', 'control or separator character %s is not allowed (only newline)' % bad)
    original = entry['text']
    kind = entry['type']
    if translation == original: return out.set('unchanged', 'translation equals the original text')
    cmd_index = entry.get('command_index')
    new_lines = None

    if kind in ('message', 'scrolling'):
        old = entry['lines']; new = translation.split('\n')
        if len(new) > len(old):
            return out.set('refused_line_count', '%d lines but the original has %d; adding lines is structural insertion and is not supported' % (len(new), len(old)))
        if len(new) < len(old):
            if not allow_shorter:
                return out.set('refused_line_count', '%d lines but the original has %d; use --allow-shorter to pad with empty lines' % (len(new), len(old)))
            out.notes.append('padded %d missing line(s) with empty strings' % (len(old) - len(new)))
            new = new + [''] * (len(old) - len(new))
        new_lines = new
        for i, (a, b) in enumerate(zip(old, new)):
            if a != b:
                out.changes.append(event_change(entry, cmd_index + 1 + i, 0, b, key, 'line %d' % (i + 1)))
        if not out.changes: return out.set('unchanged', 'no 401/405 line differs')
    elif kind == 'choices':
        old = entry['lines']; new = split_choices(translation)
        if len(new) != len(old):
            return out.set('refused_line_count', '%d choices but the original has %d; choice count must match' % (len(new), len(old)))
        new_lines = new
        out.changes.append(event_change(entry, cmd_index, 0, new, key, 'choices'))
        cmds = commands_cache(entry)
        depth = cmds[cmd_index]['indent']
        j = cmd_index + 1
        while j < len(cmds):
            c = cmds[j]
            if c['indent'] == depth and c['code'] in (402, 403, 404):
                if c['code'] == 404: break
                if c['code'] == 402:
                    p = c['parameters']
                    idx = p[0] if p and type(p[0]) is int else None
                    if idx is not None and 0 <= idx < len(old) and len(p) > 1 and p[1] == old[idx]:
                        if new[idx] != old[idx]:
                            out.changes.append(event_change(entry, j, 1, new[idx], key, 'branch label %d' % idx))
                    else:
                        out.notes.append('402 branch label at command %d does not match its choice and was left unchanged' % j)
            j += 1
    elif kind in TEXT_COMMAND_CODES:
        new_lines = translation.split('\n')
        out.changes.append(event_change(entry, cmd_index, 1, translation, key, kind))
    elif kind == 'map_name':
        if '\n' in translation: return out.set('refused_invalid', 'a map display name must be a single line')
        from vxace_map_names import name as valid_name
        try: valid_name(translation)
        except ValueError as exc: return out.set('refused_invalid', str(exc))
        try:
            snap = map_name_snapshot(data, project, entry['map_id'])
        except Exception as exc:
            return out.set('unsupported', 'native map snapshot unavailable: %s' % exc)
        if snap['display_name'] == translation: return out.set('unchanged', 'display name already equals the translation')
        new_lines = [translation]
        out.map_name = {'kind': 'map_name', 'locator': {'map_id': entry['map_id']},
                        'proposal': 'Import edited display name for %s.' % key,
                        'mutation': {'action': 'set_display_name', 'expected_map_sha256': snap['map_sha256'],
                                     'expected_display_name': snap['display_name'], 'value': translation}}
    elif kind == 'database':
        m = re.fullmatch(r'db:([a-z]+)/(\d+)/([a-z0-9_]+)', key)
        if not m:
            return out.set('unsupported', 'System database text (%s) has no id-addressed database edit' % key)
        table, rid, field = m[1], int(m[2]), m[3]
        if '\n' in translation and field not in MULTILINE_DB_FIELDS:
            return out.set('refused_invalid', 'field %s must be a single line' % field)
        new_lines = translation.split('\n')
        out.changes.append({'kind': 'database', 'locator': {'table': table, 'id': rid},
                            'proposal': 'Import edited text for %s.' % key,
                            'mutation': {'field': field, 'value': translation}})
    else:
        return out.set('unsupported', 'entry type %s is not importable' % kind)

    for f in lint_new(entry, new_lines, settings, rng):
        detail = '%s%s: %s' % (f['code'], ' (line %d)' % f['line'] if f['line'] else '', f['detail'])
        out.warnings.append(detail)
    return out.set('applied')


def build_import(index, project, rows, allow_shorter=False, include_name_commands=True, max_width=te.DEFAULT_MAX_WIDTH,
                 max_width_face=te.DEFAULT_MAX_WIDTH_FACE, max_lines=te.DEFAULT_MAX_LINES, icon_count=None):
    data = index if isinstance(index, Index) else Index(index)
    settings = {'max_width': max_width, 'max_width_face': max_width_face, 'max_lines': max_lines,
                'icon_count': icon_count, 'max_findings': 0}
    result, entries = fresh_entries(data, include_name_commands, {'max_width': max_width, 'max_width_face': max_width_face,
                                                                   'max_lines': max_lines, 'icon_count': icon_count, 'max_findings': 0})
    rng = te.ranges(data)
    lint_settings = {k: v for k, v in settings.items()}
    files = {}

    def commands_cache(entry):
        file = entry['file']
        if file not in files: files[file] = data.json(file)
        node = files[file]
        for part in entry['path'][:-1]: node = node[part]   # path ends in ['list', n]
        return node

    seen = {}
    for r in rows: seen[r['key']] = seen.get(r['key'], 0) + 1
    outcomes = []
    for row in rows:
        if row['translation'] == '':
            o = Outcome(row).set('skipped_empty', 'empty translation')
        elif seen[row['key']] > 1:
            o = Outcome(row).set('duplicate', 'key appears %d times in the CSV; none of its rows were applied' % seen[row['key']])
        elif row['key'] not in entries:
            o = Outcome(row).set('unknown', 'key not present in the fresh index')
        else:
            entry = entries[row['key']]
            if row['fingerprint'] != entry['fingerprint']:
                o = Outcome(row).set('stale', 'fingerprint differs: the source text changed since the export')
            else:
                o = process_row(row, entry, data, project, lint_settings, rng, allow_shorter, commands_cache)
        outcomes.append(o)
    data.unchanged()
    main_changes = []
    name_changes = []
    for o in sorted(outcomes, key=lambda x: x.row['key']):
        if o.status != 'applied': continue
        main_changes += o.changes
        if o.map_name: name_changes.append((o.row['key'], o.map_name))
    return {'outcomes': outcomes, 'changes': main_changes, 'name_changes': name_changes,
            'entry_count': len(entries)}


def spec_paths(spec_out, count):
    base = unlinked(spec_out)
    return [base.with_name('%s.mapname-%03d%s' % (base.stem, i, base.suffix)) for i in range(1, count + 1)]


def status_counts(outcomes):
    counts = {s: 0 for s in STATUSES}
    for o in outcomes: counts[o.status] += 1
    return counts


def report_json(result, specs, options):
    outs = result['outcomes']
    return {'version': VERSION, 'read_only': True, 'mutation_authorized': False, 'options': options,
            'rows': len(outs), 'counts': status_counts(outs), 'change_count': len(result['changes']) + len(result['name_changes']),
            'specs': specs,
            'rows_detail': [{'row': o.row['row'], 'key': o.row['key'], 'status': o.status, 'reason': o.reason,
                             'changes': len(o.changes) + (1 if o.map_name else 0), 'warnings': o.warnings, 'notes': o.notes}
                            for o in outs if o.status != 'skipped_empty'],
            'limits': LIMITS}


def report_markdown(rep):
    c = rep['counts']
    out = ['# Text import report', '', '%d CSV rows, %d guarded change(s) written. Read-only; nothing has been applied.' % (rep['rows'], rep['change_count']), '',
           '## Status counts', '', '| status | rows |', '|---|---|']
    out += ['| %s | %d |' % (s, c[s]) for s in STATUSES]
    out += ['', '## Spec files', '']
    for s in rep['specs']:
        out.append('- `%s` - %d change(s): %s' % (s['file'], s['changes'], s['note']))
    if not rep['specs']: out.append('- none (no row produced a change)')
    out += ['', '## Not applied', '']
    skipped = [r for r in rep['rows_detail'] if r['status'] not in ('applied',)]
    if skipped:
        for r in skipped: out.append('- row %d `%s` - **%s**: %s' % (r['row'], r['key'], r['status'], r['reason']))
    else: out.append('- none')
    out += ['', '## Warnings and notes on applied rows', '']
    notes = [r for r in rep['rows_detail'] if r['status'] == 'applied' and (r['warnings'] or r['notes'])]
    if notes:
        for r in notes:
            out.append('- row %d `%s`' % (r['row'], r['key']))
            out += ['  - lint: ' + w for w in r['warnings']] + ['  - note: ' + n for n in r['notes']]
    else: out.append('- none')
    out += ['', '## Next steps', '',
            'Run `vxace_patch_planner.py`, review impact, then `vxace_copy_patcher.py --backend python` for each spec file (map display-name specs each need their own run against the original source).',
            '', '## Limits', ''] + ['- ' + x for x in rep['limits']] + ['']
    return '\n'.join(out)


def run(index, project, csv_path, spec_out, report_path, json_path=None, **options):
    project = unlinked(project)
    if project.is_file() and project.suffix.lower() == '.rvproj2': project = project.parent
    if not (project / 'Data').is_dir(): raise ValueError('Expected a VX Ace project')
    data = Index(index)
    # The number of map-name specs is unknown until built, so guard the base outputs first and the extras afterwards.
    base_paths = [spec_out, report_path] + ([json_path] if json_path else [])
    te.guard_outputs(base_paths, project, data.root)
    manifest = data.json('manifest.json')
    files = manifest.get('files') if isinstance(manifest, dict) else None
    if not files or manifest.get('read_only') is not True or any(not isinstance(x, dict) or not re.fullmatch('[0-9a-fA-F]{64}', str(x.get('sha256', ''))) for x in files):
        raise ValueError('A hashed Project Reader manifest is required')
    rows = read_csv(csv_path)
    before = current_inventory(project)
    if verify_fresh(data.root, project)['status'] != 'fresh': raise ValueError('Stale index; re-index the current project')
    result = build_import(data, project, rows, **options)
    if current_inventory(project) != before: raise ValueError('Source project changed during analysis')
    extra = spec_paths(spec_out, len(result['name_changes']))
    te.guard_outputs(base_paths + [str(p) for p in extra], project, data.root)
    specs = []
    docs = []
    if result['changes']:
        docs.append((unlinked(spec_out), {'title': 'Import edited text', 'changes': result['changes']}))
        specs.append({'file': str(unlinked(spec_out)), 'changes': len(result['changes']),
                      'note': 'event text and database fields in one transaction'})
    elif extra:
        # Keep the base path meaningful: without ordinary changes the main spec is simply not written.
        pass
    for (key, change), path in zip(result['name_changes'], extra):
        docs.append((path, {'title': 'Import edited text - map display name (%s)' % key, 'changes': [change]}))
        specs.append({'file': str(path), 'changes': 1, 'note': 'single map display-name change for %s (needs its own transaction)' % key})
    options_rep = {k: v for k, v in options.items()}
    rep = report_json(result, specs, options_rep)
    rep.update(source_unchanged=True, source_freshness='fresh')
    outputs = [(path, json.dumps(doc, ensure_ascii=False, indent=2) + '\n') for path, doc in docs]
    outputs.append((unlinked(report_path), report_markdown(rep)))
    if json_path: outputs.append((unlinked(json_path), json.dumps(rep, ensure_ascii=False, indent=2) + '\n'))
    for path, text in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'x', encoding='utf-8', newline='') as f: f.write(text)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project', required=True); ap.add_argument('--csv', required=True)
    ap.add_argument('--spec-out', required=True); ap.add_argument('--report', required=True); ap.add_argument('--json')
    ap.add_argument('--allow-shorter', action='store_true', help='pad a translation with fewer lines than the original with empty lines')
    ap.add_argument('--max-width', type=int, default=te.DEFAULT_MAX_WIDTH); ap.add_argument('--max-width-face', type=int, default=te.DEFAULT_MAX_WIDTH_FACE)
    ap.add_argument('--max-lines', type=int, default=te.DEFAULT_MAX_LINES); ap.add_argument('--icon-count', type=int)
    a = ap.parse_args(argv)
    try:
        rep = run(a.index, a.project, a.csv, a.spec_out, a.report, a.json, allow_shorter=a.allow_shorter,
                  max_width=a.max_width, max_width_face=a.max_width_face, max_lines=a.max_lines, icon_count=a.icon_count)
        print(json.dumps({'status': 'ok', 'rows': rep['rows'], 'counts': rep['counts'], 'changes': rep['change_count'],
                          'specs': [s['file'] for s in rep['specs']]}))
        return 0
    except Exception as exc:
        print('Text import refused: ' + str(exc), file=sys.stderr); return 2


if __name__ == '__main__': raise SystemExit(main())
