#!/usr/bin/env python3
"""Read-only export and heuristic lint of player-facing text from a fresh VX Ace index; never execute code."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from pathlib import Path
from vxace_index_query import Index, unlinked
from vxace_copy_patcher import verify_fresh, current_inventory

VERSION = '1.7.0'
MAX_ENTRIES = 500000
MAX_TEXT_CHARS = 64 * 1024 * 1024
MAX_ENTRY_CHARS = 262144
MAX_FINDINGS = 100000
DEFAULT_MAX_WIDTH, DEFAULT_MAX_WIDTH_FACE, DEFAULT_MAX_LINES = 50, 38, 4
NAME_CODES = {320: 'actor_name', 324: 'actor_nickname', 325: 'actor_profile'}
# Database text fields per normalized file; System is handled separately.
DB_FIELDS = {
    'actors': ('name', 'nickname', 'description', 'profile'), 'classes': ('name', 'description'),
    'skills': ('name', 'description', 'message1', 'message2'),
    'items': ('name', 'description'), 'weapons': ('name', 'description'), 'armors': ('name', 'description'),
    'enemies': ('name',), 'states': ('name', 'message1', 'message2', 'message3', 'message4'),
}
SYSTEM_LISTS = ('elements', 'skill_types', 'weapon_types', 'armor_types')
TERM_LISTS = ('basic', 'params', 'etypes', 'commands')
PARAM_CODES = 'CIVNP'
SIMPLE_CODES = '{}$.|!><^'
LIMITS = [
    'Heuristic lint only: findings are hints for a human proofreader, not engine behaviour.',
    'Width counts visible characters after stripping control codes (East Asian wide/fullwidth = 2); \\V \\N \\G \\I substitutions count as 0 and real font metrics are not measured.',
    'Custom message systems (Yanfly, Message Plus, ...) may use other codes, wider windows or auto-wrapping; adjust --max-width or ignore those findings.',
    '\\I[n] is an icon index, not a database id, so it is range-checked only when --icon-count is given; \\C[n] is checked against the 32 default windowskin colors.',
    'Variable and actor ranges come from System.rvdata2 variables and Actors.rvdata2 slots in the index; if absent the check is skipped.',
    'Word counts split on whitespace and are not meaningful for languages written without spaces.',
    'Export only: no import or write-back exists. Fingerprints let a future import verify the source parameters are unchanged.',
    'Script-generated and plugin-drawn text, picture text and notes are outside the export.',
]


def strip_codes(line):
    """-> (visible text, [(code letter, n)] references, [(finding code, detail)] problems)."""
    out, refs, problems, i, n = [], [], [], 0, len(line)
    while i < n:
        ch = line[i]
        if ch != '\\':
            out.append(ch); i += 1; continue
        if i + 1 >= n:
            problems.append(('malformed_control_code', 'trailing backslash')); i += 1; continue
        c = line[i + 1]; u = c.upper()
        if c == '\\':
            out.append('\\'); i += 2
        elif u == 'G' or c in SIMPLE_CODES:
            i += 2
        elif u in PARAM_CODES:
            m = re.compile(r'\[(\d+)\]').match(line, i + 2)
            if m:
                refs.append((u, int(m[1]))); i = m.end()
            else:
                problems.append(('malformed_control_code', '\\' + c + ' needs [n]')); i += 2
        else:
            problems.append(('unknown_control_code', '\\' + c)); i += 2
    return ''.join(out), refs, problems


def visible_width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in 'WF' else 1 for ch in text)


def word_count(text):
    return len(re.findall(r'\S+', strip_codes(text)[0]))


def fingerprint(commands):
    """sha256 of the exact (code, indent, parameters) tuples, canonical JSON."""
    blob = json.dumps([[c['code'], c.get('indent'), c['parameters']] for c in commands],
                      ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def value_fingerprint(file, path, value):
    blob = json.dumps([file, path, value], ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def valid_command(cmd):
    if not isinstance(cmd, dict) or cmd.get('__class__') != 'RPG::EventCommand' or type(cmd.get('code')) is not int \
            or not isinstance(cmd.get('parameters'), list):
        raise ValueError('Opaque command cannot be exported completely')
    return cmd


def one_line(text):
    return re.sub(r'\s+', ' ', str(text)).strip()


class Budget:
    def __init__(self):
        self.entries = []; self.chars = 0

    def add(self, entry):
        size = sum(len(x) for x in entry['lines']); self.chars += size
        if size > MAX_ENTRY_CHARS:
            raise ValueError('Text entry exceeds size budget; no complete result produced')
        if len(self.entries) >= MAX_ENTRIES or self.chars > MAX_TEXT_CHARS:
            raise ValueError('Text entry/character budget exceeded; no complete result produced')
        entry['text'] = '\n'.join(entry['lines'])
        self.entries.append(entry)


def map_pass(data, budget):
    """Display names and context names for maps, events, common events and troops."""
    names = {'map': {}, 'event': {}, 'common_event': {}, 'troop': {}}
    for file in data.paths('maps', 'map-*.json'):
        match = re.fullmatch(r'maps/map-(\d{3})\.json', file)
        if not match: raise ValueError('Unexpected normalized map filename')
        mid = int(match[1]); root = data.json(file)
        if not isinstance(root, dict): raise ValueError('Map was not fully decoded')
        display = root.get('display_name')
        names['map'][mid] = display if isinstance(display, str) else ''
        for key, event in (root.get('events') or {}).items():
            data.spend()
            if isinstance(event, dict) and isinstance(event.get('name'), str): names['event'][(mid, key)] = event['name']
        if isinstance(display, str) and display.strip():
            budget.add({'key': 'map:%03d/display_name' % mid, 'type': 'map_name', 'file': file, 'path': ['display_name'],
                        'scope': 'map', 'group': 'map:%03d' % mid, 'map_id': mid, 'section': map_section(mid, names['map']), 'subsection': 'Display name',
                        'context': 'Map %03d display name' % mid, 'speaker': '', 'lines': display.split('\n'),
                        'fingerprint': value_fingerprint(file, ['display_name'], display), 'problems': []})
    for scope, file in (('common_event', 'database/common-events.json'), ('troop', 'database/troops.json')):
        if data.path(file).is_file():
            for owner in data.json(file):
                data.spend()
                if isinstance(owner, dict) and type(owner.get('id')) is int and isinstance(owner.get('name'), str):
                    names[scope][owner['id']] = owner['name']
    return names


def map_section(mid, maps):
    name = one_line(maps.get(mid, ''))
    return 'Map %03d%s' % (mid, ' - ' + name if name else '')


def event_pass(data, budget, names, name_commands):
    for loc, file, path, page, _ in data.event_lists():
        cmds = [valid_command(c) for c in page['list']]
        scope = loc['scope']
        if scope == 'map':
            mid, eid, pg = loc['map_id'], loc['event_id'], loc['page']
            key_base = 'map:%03d/event:%d/page:%d' % (mid, eid, pg)
            section = map_section(mid, names['map']); group = 'map:%03d' % mid
            sub = 'Event %d %s, page %d' % (eid, one_line(names['event'].get((mid, str(eid)), '')), pg)
        elif scope == 'common_event':
            cid = loc['common_event_id']; key_base = 'common:%d' % cid
            section = 'Common Events'; group = 'common_events'
            sub = 'Common Event %d %s' % (cid, one_line(names['common_event'].get(cid, '')))
        else:
            tid, pg = loc['troop_id'], loc['page']; key_base = 'troop:%d/page:%d' % (tid, pg)
            section = 'Troops'; group = 'troops'
            sub = 'Troop %d %s, page %d' % (tid, one_line(names['troop'].get(tid, '')), pg)
        sub = sub.replace(' ,', ',').strip()
        n = 0
        while n < len(cmds):
            data.spend()
            cmd = cmds[n]; code = cmd['code']; p = cmd['parameters']; end = n + 1
            base = {'file': file, 'path': path + ['list', n], 'scope': scope, 'group': group, 'section': section,
                    'subsection': sub, 'command_index': n, 'problems': [], **{k: v for k, v in loc.items() if k != 'scope'}}
            base['context'] = '%s / %s / command %d' % (section, sub, n)
            entry = None
            if code in (101, 105):
                body = 401 if code == 101 else 405
                while end < len(cmds) and cmds[end]['code'] == body: end += 1
                lines = []
                for c in cmds[n + 1:end]:
                    if c['parameters'] and isinstance(c['parameters'][0], str): lines.append(c['parameters'][0])
                    else: lines.append(''); base['problems'].append(('malformed_parameters', 'continuation without text'))
                if code == 101:
                    face = p[0] if len(p) > 0 and isinstance(p[0], str) else ''
                    fidx = p[1] if len(p) > 1 and type(p[1]) is int else 0
                    if len(p) < 4 or not isinstance(p[0], str): base['problems'].append(('malformed_parameters', '101 header'))
                    entry = {**base, 'type': 'message', 'key': key_base + '/cmd:%d' % n, 'lines': lines,
                             'speaker': '%s[%d]' % (face, fidx) if face else '', 'face_name': face, 'face_index': fidx,
                             'background': p[2] if len(p) > 2 else None, 'position': p[3] if len(p) > 3 else None}
                else:
                    entry = {**base, 'type': 'scrolling', 'key': key_base + '/cmd:%d' % n, 'lines': lines, 'speaker': '',
                             'speed': p[0] if p else None, 'no_fast': p[1] if len(p) > 1 else None}
                entry['fingerprint'] = fingerprint(cmds[n:end])
            elif code == 102:
                choices = p[0] if p and isinstance(p[0], list) and all(isinstance(x, str) for x in p[0]) else None
                if choices is None: base['problems'].append(('malformed_parameters', '102 choices'))
                cancel = p[1] if len(p) > 1 and type(p[1]) is int else None
                branches = []; used = [cmd]; j = n + 1
                while j < len(cmds):
                    data.spend()
                    c = cmds[j]
                    if c['indent'] == cmd['indent'] and c['code'] in (402, 403, 404):
                        if c['code'] == 402:
                            branches.append(c['parameters'][1] if len(c['parameters']) > 1 and isinstance(c['parameters'][1], str) else None)
                            used.append(c)
                        if c['code'] == 404: break
                    j += 1
                entry = {**base, 'type': 'choices', 'key': key_base + '/cmd:%d' % n, 'lines': choices or [], 'speaker': '',
                         'cancel_type': cancel, 'cancel': {0: 'disallow', 5: 'branch'}.get(cancel, 'choice %s' % cancel),
                         'branch_labels': branches, 'fingerprint': fingerprint(used)}
            elif name_commands and code in NAME_CODES:
                text = p[1] if len(p) > 1 and isinstance(p[1], str) else None
                if text is not None:
                    entry = {**base, 'type': NAME_CODES[code], 'key': key_base + '/cmd:%d' % n, 'lines': text.split('\n'),
                             'speaker': 'actor %s' % p[0], 'actor_id': p[0], 'fingerprint': fingerprint([cmd])}
                else: base['problems'].append(('malformed_parameters', str(code)))
            if entry is not None:
                budget.add(entry)
            n = end


def database_pass(data, budget):
    def add(file, path, value, section, label, key):
        if isinstance(value, str) and value.strip():
            budget.add({'key': key, 'type': 'database', 'file': file, 'path': path, 'scope': 'database', 'group': 'database',
                        'section': section, 'subsection': label, 'context': '%s / %s' % (section, label), 'speaker': '',
                        'lines': value.split('\n'), 'fingerprint': value_fingerprint(file, path, value), 'problems': []})
    for stem, fields in DB_FIELDS.items():
        file = 'database/%s.json' % stem
        if not data.path(file).is_file(): continue
        root = data.json(file)
        if not isinstance(root, list): raise ValueError('Expected normalized database array')
        for slot, row in enumerate(root):
            data.spend()
            if row is None: continue
            if not isinstance(row, dict): raise ValueError('Ambiguous or opaque database row')
            rid = row['id'] if type(row.get('id')) is int else slot
            for field in fields:
                add(file, [slot, field], row.get(field), 'Database: ' + stem.capitalize(),
                    '%s %d %s' % (stem[:-1] if stem != 'classes' else 'class', rid, field),
                    'db:%s/%d/%s' % (stem, rid, field))
    file = 'database/system.json'
    if data.path(file).is_file():
        system = data.json(file)
        if not isinstance(system, dict): raise ValueError('Expected normalized System object')
        for field in ('game_title', 'currency_unit'):
            add(file, [field], system.get(field), 'Database: System', field, 'db:system/' + field)
        for field in SYSTEM_LISTS:
            for i, v in enumerate(system.get(field) or []):
                data.spend(); add(file, [field, i], v, 'Database: System', '%s %d' % (field, i), 'db:system/%s/%d' % (field, i))
        terms = system.get('terms') if isinstance(system.get('terms'), dict) else {}
        for field in TERM_LISTS:
            for i, v in enumerate(terms.get(field) or []):
                data.spend(); add(file, ['terms', field, i], v, 'Database: System', 'terms %s %d' % (field, i),
                                  'db:system/terms/%s/%d' % (field, i))


def ranges(data):
    """Highest valid ids for \\V and \\N references; None when the index lacks the table."""
    out = {'V': None, 'N': None}
    if data.path('database/system.json').is_file():
        v = data.json('database/system.json').get('variables')
        if isinstance(v, list) and v: out['V'] = len(v) - 1
    if data.path('database/actors.json').is_file():
        a = data.json('database/actors.json')
        if isinstance(a, list) and a: out['N'] = len(a) - 1
    return out


def lint_entry(entry, settings, rng):
    found = []
    def add(code, detail, line=None):
        found.append({'code': code, 'key': entry['key'], 'group': entry['group'], 'line': line, 'detail': detail,
                      'file': entry['file'], 'path': entry['path'], 'heuristic': True})
    for code, detail in entry['problems']: add(code, detail)
    kind = entry['type']; lines = entry['lines']
    if kind in ('message', 'scrolling', 'choices') and not any(x.strip() for x in lines):
        add('empty_message', 'no visible text')
    if kind == 'message' and len(lines) > settings['max_lines']:
        add('too_many_lines', '%d lines (limit %d)' % (len(lines), settings['max_lines']))
    limit = settings['max_width_face'] if entry.get('face_name') else settings['max_width']
    for i, line in enumerate(lines, 1):
        visible, refs, problems = strip_codes(line)
        for code, detail in problems: add(code, detail, i)
        for letter, n in refs:
            if letter == 'C' and n > 31: add('color_out_of_range', '\\C[%d] (windowskin has 0..31)' % n, i)
            elif letter == 'I' and settings['icon_count'] is not None and n >= settings['icon_count']:
                add('reference_out_of_range', '\\I[%d] (icon count %d)' % (n, settings['icon_count']), i)
            elif letter in 'VN':
                top = rng[letter]
                if n < 1 or (top is not None and n > top):
                    add('reference_out_of_range', '\\%s[%d] (valid 1..%s)' % (letter, n, top if top is not None else '?'), i)
        if kind == 'message' and visible_width(visible) > limit:
            add('line_too_wide', 'width %d exceeds %d%s' % (visible_width(visible), limit, ' (face)' if entry.get('face_name') else ''), i)
        if line != line.rstrip(' \t　'): add('trailing_whitespace', 'line ends with whitespace', i)
        if '  ' in line.strip(): add('doubled_space', 'two consecutive spaces', i)
    return found


def lint(entries, rng, settings):
    findings, counts, total = [], {}, 0
    for entry in entries:
        for f in lint_entry(entry, settings, rng):
            total += 1
            group = counts.setdefault(f['group'], {'total': 0})
            group['total'] += 1; group[f['code']] = group.get(f['code'], 0) + 1
            if len(findings) < settings['max_findings']: findings.append(f)
    return {'heuristic': True, 'settings': settings, 'finding_count': total, 'findings': findings,
            'findings_truncated': total > len(findings), 'counts_by_group': dict(sorted(counts.items()))}


def export_text(data, include_name_commands=False, max_width=DEFAULT_MAX_WIDTH, max_width_face=DEFAULT_MAX_WIDTH_FACE,
                max_lines=DEFAULT_MAX_LINES, icon_count=None, max_findings=2000):
    if not isinstance(data, Index): data = Index(data)
    for name, v, lo, hi in (('max_width', max_width, 1, 500), ('max_width_face', max_width_face, 1, 500),
                            ('max_lines', max_lines, 1, 100), ('max_findings', max_findings, 0, MAX_FINDINGS)):
        if type(v) is not int or not lo <= v <= hi: raise ValueError('%s must be an integer %d..%d' % (name, lo, hi))
    if icon_count is not None and (type(icon_count) is not int or not 1 <= icon_count <= 100000):
        raise ValueError('icon_count must be an integer 1..100000')
    budget = Budget()
    names = map_pass(data, budget)
    event_pass(data, budget, names, bool(include_name_commands))
    database_pass(data, budget)
    settings = {'max_width': max_width, 'max_width_face': max_width_face, 'max_lines': max_lines,
                'icon_count': icon_count, 'max_findings': max_findings}
    report = lint(budget.entries, ranges(data), settings)
    data.unchanged()
    types = {}
    for e in budget.entries:
        e['word_count'] = word_count(e['text']); e.pop('problems', None); e.pop('group', None)
        types[e['type']] = types.get(e['type'], 0) + 1
    return {'version': VERSION, 'read_only': True, 'mutation_authorized': False, 'import_enabled': False,
            'name_commands_included': bool(include_name_commands), 'entry_count': len(budget.entries),
            'entries_by_type': dict(sorted(types.items())), 'word_count': sum(e['word_count'] for e in budget.entries),
            'coverage_complete': True, 'entries': budget.entries, 'lint': report, 'limits': LIMITS}


def csv_text(result):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\r\n')
    w.writerow(['key', 'context', 'speaker', 'original', 'translation', 'fingerprint'])
    for e in result['entries']:
        w.writerow([e['key'], e['context'], e['speaker'], e['text'], '', e['fingerprint']])
    return buf.getvalue()


def markdown_text(result):
    sections = {}
    for e in result['entries']:
        sections.setdefault(e['section'], {}).setdefault(e['subsection'], []).append(e)
    out = ['# Text export', '', '%d entries, %d words. Export only; heuristic lint counts are in the JSON report.'
           % (result['entry_count'], result['word_count']), '']
    for section, subs in sections.items():
        out += ['## %s (%d words)' % (section, sum(e['word_count'] for es in subs.values() for e in es)), '']
        for sub, es in subs.items():
            out += ['### %s (%d words)' % (sub, sum(e['word_count'] for e in es)), '']
            for e in es:
                tag = e['type'] + (', face ' + e['speaker'] if e['speaker'] and e['type'] == 'message' else '')
                if e['type'] == 'choices': tag += ', cancel: ' + e['cancel']
                out.append('`%s` (%s)' % (e['key'], tag)); out.append('')
                out += ['> ' + x if x else '>' for x in e['lines']]
                out.append('')
    return '\n'.join(out)


def guard_outputs(paths, project, index_root):
    outs = []
    for p in paths:
        out = unlinked(p)
        if out.exists() or out.is_symlink(): raise ValueError('Use new output files outside project and index')
        if any(out == r or r in out.parents for r in (project, index_root)):
            raise ValueError('Use new output files outside project and index')
        if out in outs: raise ValueError('Output files must be distinct')
        outs.append(out)
    return outs


def run(index, project, json_path=None, csv_path=None, markdown_path=None, **options):
    """CLI transaction: output guards, freshness + source integrity, then external files."""
    project = unlinked(project)
    if project.is_file() and project.suffix.lower() == '.rvproj2': project = project.parent
    if not (project / 'Data').is_dir(): raise ValueError('Expected a VX Ace project')
    requested = [(k, v) for k, v in (('json', json_path), ('csv', csv_path), ('markdown', markdown_path)) if v]
    if not requested: raise ValueError('Supply at least one of --json, --csv, --markdown')
    data = Index(index)
    outs = dict(zip([k for k, _ in requested], guard_outputs([v for _, v in requested], project, data.root)))
    manifest = data.json('manifest.json')
    files = manifest.get('files') if isinstance(manifest, dict) else None
    if not files or manifest.get('read_only') is not True or any(not isinstance(x, dict) or not re.fullmatch('[0-9a-fA-F]{64}', str(x.get('sha256', ''))) for x in files):
        raise ValueError('A hashed Project Reader manifest is required')
    before = current_inventory(project)
    if verify_fresh(data.root, project)['status'] != 'fresh': raise ValueError('Stale index; re-index the current project')
    result = export_text(data, **options)
    if current_inventory(project) != before: raise ValueError('Source project changed during analysis')
    result.update(source_unchanged=True, read_index_files_unchanged=True, source_freshness='fresh')
    rendered = {'json': json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                'csv': csv_text(result) if 'csv' in outs else '', 'markdown': markdown_text(result) if 'markdown' in outs else ''}
    for kind, path in outs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        # utf-8-sig writes the BOM Excel needs to read the CSV as UTF-8.
        with open(path, 'x', encoding='utf-8-sig' if kind == 'csv' else 'utf-8', newline='') as f: f.write(rendered[kind])
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project', required=True)
    ap.add_argument('--json'); ap.add_argument('--csv'); ap.add_argument('--markdown')
    ap.add_argument('--include-name-commands', action='store_true', help='also export Change Name/Nickname/Profile (320/324/325)')
    ap.add_argument('--max-width', type=int, default=DEFAULT_MAX_WIDTH); ap.add_argument('--max-width-face', type=int, default=DEFAULT_MAX_WIDTH_FACE)
    ap.add_argument('--max-lines', type=int, default=DEFAULT_MAX_LINES); ap.add_argument('--icon-count', type=int)
    ap.add_argument('--max-findings', type=int, default=2000)
    a = ap.parse_args(argv)
    try:
        r = run(a.index, a.project, a.json, a.csv, a.markdown, include_name_commands=a.include_name_commands, max_width=a.max_width,
                max_width_face=a.max_width_face, max_lines=a.max_lines, icon_count=a.icon_count, max_findings=a.max_findings)
        print(json.dumps({'status': 'ok', 'entries': r['entry_count'], 'words': r['word_count'], 'lint_findings': r['lint']['finding_count']}))
        return 0
    except Exception as exc:
        print('Text export refused: ' + str(exc), file=sys.stderr); return 2


if __name__ == '__main__': raise SystemExit(main())
