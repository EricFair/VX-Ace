#!/usr/bin/env python3
"""Read-only notetag registry: notetag uses in a fresh VX Ace index vs. script parsers; never execute code."""
from __future__ import annotations
import argparse
import difflib
import json
import re
import sys
from vxace_index_query import Index, unlinked
from vxace_copy_patcher import verify_fresh, current_inventory

VERSION = '1.7.0'
DB_NOTE_FILES = ('actors', 'classes', 'skills', 'items', 'weapons', 'armors', 'enemies', 'states', 'tilesets')
MAX_TAGS = 20000
MAX_PARSERS = 5000
MAX_USES = 500000
MAX_VARIANTS = 64
MAX_RESULT_BYTES = 8 * 1024 * 1024
SAMPLE_USES = 20
MD_ROWS = 200
TAG_RE = re.compile(r'<(/?)([^<>\r\n]{1,200})>')
RX_LIT = re.compile(r'(?<![\w)\]}])/((?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n\[])+)/([a-z]*)')
RX_PCT = re.compile(r'%r\{((?:\\.|[^}\\\n])+)\}([a-z]*)')
STR_RE = re.compile(r'"((?:\\.|[^"\\\n])*)"|\'((?:\\.|[^\'\\\n])*)\'')
SEP_RE = re.compile(r'(?:\\s|\[ _\]|\[\\s_\]|\[_ \]|\[_\\s\]| )(?:[*+?]|\{\d+(?:,\d*)?\})?')
STRING_HINT = re.compile(r'Regexp|=~|\.match|\.scan|\.sub|\.gsub|\.index|\.include\?|\bnote\b|\.split|\.start_with', re.I)
META = set('\\[](){}.*+?^$|')
LIMITS = ['Heuristic: classifications come from static regex/string inspection, not proof; scripts may build patterns dynamically, '
          'alias other scripts, or parse tags through code this tool does not see.',
          'Tag names are case-folded with whitespace collapsed; space and underscore are treated as optional separators when matching.',
          'Event comments are read per command (108/408); tags split across comment lines are not joined.',
          'Parser patterns are found by line-based scanning of ruby text for regex literals, %r{} and quoted strings containing <...>; '
          'multi-line literals, heredocs and trailing comments are not understood. Patterns that cannot be reduced to a literal prefix are opaque.',
          'Case checks use only the /i flag, (?i), IGNORECASE on the same line; downcase/casecmp normalization is not detected.',
          'Typo suggestions are difflib nearest names, a hint only. Unused parser tags may be consumed by other plugins or never be needed.',
          'Nothing here authorizes editing notes, comments or scripts; no project code is evaluated.']


def canon(name):
    return re.sub(r'[\s_]+', '', name).casefold()


def canon_cs(name):
    return re.sub(r'[\s_]+', '', name)


def collapse(text):
    return re.sub(r'\s+', ' ', text).strip()


def extract_tags(text):
    """Notetag uses in text: <tag>, <tag: value>, <tag arg>, </tag>."""
    tags = []
    for m in TAG_RE.finditer(text):
        close, inner = m[1], m[2].strip()
        if not inner or not (inner[0].isalnum() or inner[0] == '_'): continue
        value = None
        if ':' in inner and not close:
            name, value = inner.split(':', 1); value = value.strip(); form = 'valued'
        else:
            name = inner; form = 'close' if close else ('args' if re.search(r'\s', inner) else 'bare')
        name = collapse(name)
        if not name or len(name) > 64: continue
        tags.append({'name': name, 'form': form, 'value': value, 'raw': m[0][:200]})
    return tags


def keys_for(tag):
    """Match keys for a use, longest first: args-form tags may be parser-name plus arguments."""
    words = tag['name'].split(' ')
    if tag['form'] == 'args':
        return [canon(' '.join(words[:n])) for n in range(len(words), 0, -1)]
    return [canon(tag['name'])]


def split_top(text):
    parts, depth, cur, i = [], 0, '', 0
    while i < len(text):
        c = text[i]
        if c == '\\': cur += text[i:i+2]; i += 2; continue
        if c == '(': depth += 1
        elif c == ')': depth -= 1
        if c == '|' and depth == 0: parts.append(cur); cur = ''
        else: cur += c
        i += 1
    return parts + [cur]


def group_end(text, i):
    depth = 0
    while i < len(text):
        c = text[i]
        if c == '\\': i += 2; continue
        if c == '(': depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0: return i
        i += 1
    return None


def prefix(text, stops=''):
    """Literal prefix of a regex source: (variants, consumed, stop reason). Separators become one space."""
    out, i = [''], 0
    while i < len(text):
        if text[i] in stops: return out, i, 'terminator'
        m = SEP_RE.match(text, i)
        if m: out = [o + ' ' for o in out]; i = m.end(); continue
        c = text[i]
        if c == '(':
            end = group_end(text, i)
            inner = text[i+1:end] if end is not None else None
            if inner is not None and inner.startswith('?'):
                inner = re.sub(r'^\?i?:', '', inner) if re.match(r'\?i?:', inner) else None
            if inner is None: return out, i, 'group' if text[i+1:i+2] == '?' else 'capture'
            alts = []
            for alt in split_top(inner):
                v, used, why = prefix(alt)
                if used != len(alt): return out, i, 'group'
                alts += v
            j = end + 1
            if j < len(text) and text[j] == '?': alts.append(''); j += 1
            elif j < len(text) and text[j] in '*+{': return out, i, 'quantified group'
            out = [o + a for o in out for a in alts]; i = j
            if len(out) > MAX_VARIANTS: return [''], 0, 'too many alternatives'
            continue
        if c == '#' and text[i+1:i+2] == '{': return out, i, 'interpolation'
        start = i
        if c == '\\':
            if i + 1 >= len(text): return out, i, 'escape'
            if text[i+1].isalnum(): return out, i, 'class'
            lit = text[i+1]; i += 2
        elif c in META: return out, i, 'class' if c == '[' else 'meta'
        else: lit = c; i += 1
        if i < len(text) and text[i] == '?': out = out + [o + lit for o in out]; i += 1
        elif i < len(text) and text[i] in '*+{': return out, start, 'quantified literal'
        else: out = [o + lit for o in out]
        if len(out) > MAX_VARIANTS: return [''], 0, 'too many alternatives'
    return out, i, 'end'


def derive(pattern):
    """Candidate tag names from a notetag-like regex source: (names, closing, partial, opaque reason)."""
    pos = None
    for m in re.finditer(r'\\?<', pattern):
        if m.start() > 0 and pattern[m.start()-1] == '?' and m[0] == '<': continue
        pos = m.end(); break
    if pos is None or '>' not in pattern[pos:]: return None
    rest = pattern[pos:]
    closing = False
    for lead in ('\\/', '/'):
        if rest.startswith(lead): closing = True; rest = rest[len(lead):]; break
    rest = re.sub(r'^(?:\\s\*|\\s\+| )', '', rest)
    variants, used, why = prefix(rest, ':>=')
    names = sorted({collapse(v) for v in variants if collapse(v)})
    if not names:
        return [], closing, False, 'no literal prefix (' + why + ')'
    partial = why not in ('terminator', 'end', 'capture') and not rest[used:used+1] in (':', '>', '=', '(', ' ')
    return names, closing, partial, None


def parser_candidates(line):
    """(kind, pattern, flags) literals in a ruby line that could be notetag patterns."""
    found, blanked = [], line
    for rx in (RX_LIT, RX_PCT):
        for m in rx.finditer(line):
            found.append(('regex', m[1], m[2]))
            blanked = blanked[:m.start()] + ' ' * (m.end() - m.start()) + blanked[m.end():]
    if STRING_HINT.search(line):
        for m in STR_RE.finditer(blanked):
            text = m[1] if m[1] is not None else m[2]
            if '<' in text and '>' in text: found.append(('string', text.replace('\\\\', '\\'), ''))
    return found


def parsers_in(data):
    order = data.json('scripts/order.json')
    if not isinstance(order, dict) or not isinstance(order.get('scripts'), list): raise ValueError('Missing script order')
    if 'script_count' in data.project and data.project['script_count'] != len(order['scripts']): raise ValueError('Script order is incomplete')
    seen, rows = set(), []
    for script in order['scripts']:
        data.spend()
        if not isinstance(script, dict) or not isinstance(script.get('path'), str) or script['path'] in seen: raise ValueError('Ambiguous script order')
        seen.add(script['path'])
        file, block = 'scripts/' + script['path'], False
        for n, line in enumerate(data.text(file).splitlines(), 1):
            data.spend()
            if line.startswith('=begin'): block = True
            if block:
                block = not line.startswith('=end'); continue
            if line.lstrip().startswith('#') or '<' not in line: continue
            for kind, pattern, flags in parser_candidates(line):
                derived = derive(pattern)
                if derived is None: continue
                names, closing, partial, opaque = derived
                if len(rows) >= MAX_PARSERS: raise ValueError('Parser budget exceeded; no complete result produced')
                ignore = 'i' in flags or pattern.startswith('(?i') or bool(re.search(r'IGNORECASE|,\s*true\)', line) and kind == 'string')
                rows.append({'script': script['path'], 'script_index': script.get('index'), 'file': file, 'line': n, 'kind': kind,
                             'pattern': pattern[:200], 'flags': flags, 'ignore_case': ignore, 'names': names, 'closing': closing,
                             'prefix_only': partial, 'opaque': opaque is not None, 'opaque_reason': opaque,
                             'note_context': bool(re.search(r'\bnote\b', line)), 'excerpt': line.strip()[:200]})
    return rows


def uses(data):
    """Yield (tag, evidence) from database notes, map notes and event comments (108/408)."""
    for name in DB_NOTE_FILES:
        file = 'database/' + name + '.json'
        if not data.path(file).is_file(): continue
        root = data.json(file)
        if not isinstance(root, list): raise ValueError('Expected normalized database array')
        for slot, obj in enumerate(root):
            data.spend()
            if isinstance(obj, dict) and isinstance(obj.get('note'), str):
                for tag in extract_tags(obj['note']):
                    yield tag, {'source': 'database', 'file': file, 'path': [slot, 'note'], 'object_id': obj.get('id'), 'object_name': obj.get('name')}
    for file in data.paths('maps', 'map-*.json'):
        root = data.json(file)
        if isinstance(root, dict) and isinstance(root.get('note'), str):
            for tag in extract_tags(root['note']):
                yield tag, {'source': 'map', 'file': file, 'path': ['note'], 'object_name': root.get('display_name')}
    for loc, file, path, page, _ in data.event_lists():
        for n, cmd in enumerate(page['list']):
            data.spend()
            if not isinstance(cmd, dict) or cmd.get('code') not in (108, 408) or not isinstance(cmd.get('parameters'), list): continue
            text = cmd['parameters'][0] if cmd['parameters'] else None
            if isinstance(text, str):
                for tag in extract_tags(text):
                    yield tag, {'source': 'event_comment', 'file': file, 'path': path + ['list', n, 'parameters', 0], **loc, 'command_index': n, 'command_code': cmd['code']}


def cross_reference(use_rows, parsers):
    """use_rows: [(tag, evidence)]; parsers: rows from parsers_in. Pure function, no I/O."""
    exact, prefixes, by_key = {}, [], {}
    for p in parsers:
        if p['opaque']: continue
        for name in p['names']:
            key = canon(name)
            if not key: continue
            by_key.setdefault(key, {}).setdefault(name, []).append(p)
            if p['prefix_only']: prefixes.append((key, name, p))
            else: exact.setdefault(key, []).append((name, p))
    tags = {}
    for tag, ev in use_rows:
        key = canon(tag['name'])
        entry = tags.setdefault(key, {'key': key, 'forms': {}, 'variants': {}, 'total': 0, 'samples': [], 'keys': keys_for(tag), 'tag_forms': set()})
        entry['total'] += 1; entry['forms'][tag['form']] = entry['forms'].get(tag['form'], 0) + 1
        entry['variants'][tag['name']] = entry['variants'].get(tag['name'], 0) + 1
        if len(entry['samples']) < SAMPLE_USES: entry['samples'].append({**ev, 'form': tag['form'], 'raw': tag['raw']})
    parser_keys = sorted(by_key)
    result, matched_keys = [], set()
    for key in sorted(tags):
        entry = tags[key]; matches, case_mismatch = [], []
        for variant in sorted(entry['variants']):
            hit_any = ok_any = False
            for ukey in entry['keys']:
                for name, p in exact.get(ukey, []):
                    hit_any = True; matched_keys.add(ukey)
                    ok = p['ignore_case'] or canon_cs(variant)[:len(ukey)] == canon_cs(name)
                    ok_any = ok_any or ok; matches.append((p, name, ok))
                for pkey, name, p in prefixes:
                    if len(pkey) >= 3 and ukey.startswith(pkey):
                        hit_any = True; matched_keys.add(pkey)
                        ok = p['ignore_case'] or canon_cs(variant)[:len(pkey)] == canon_cs(name)
                        ok_any = ok_any or ok; matches.append((p, name, ok))
                if hit_any: break
            if hit_any and not ok_any: case_mismatch.append(variant)
        seen, plist = set(), []
        for p, name, ok in matches:
            if (p['file'], p['line'], name) in seen: continue
            seen.add((p['file'], p['line'], name))
            plist.append({'script': p['script'], 'script_index': p['script_index'], 'line': p['line'], 'parser_name': name,
                          'pattern': p['pattern'], 'ignore_case': p['ignore_case'], 'prefix_only': p['prefix_only'], 'case_ok': ok})
        row = {'tag': sorted(entry['variants'], key=lambda v: (-entry['variants'][v], v))[0], 'key': key, 'forms': entry['forms'],
               'variants': entry['variants'], 'use_count': entry['total'], 'status': 'recognized' if plist else 'unrecognized',
               'parsers': plist, 'case_mismatches': case_mismatch, 'suggestions': [], 'evidence': entry['samples'],
               'evidence_truncated': entry['total'] > len(entry['samples']), 'shared_scripts': sorted({q['script'] for q in plist}) if len({q['script'] for q in plist}) > 1 else []}
        if not plist:
            close = []
            for ukey in dict.fromkeys(entry['keys']):
                close += difflib.get_close_matches(ukey, parser_keys, n=3, cutoff=0.8)
            row['suggestions'] = [{'parser_tag': sorted(by_key[k])[0], 'scripts': sorted({q['script'] for lst in by_key[k].values() for q in lst})}
                                  for k in dict.fromkeys(close)][:3]
        result.append(row)
    unused = []
    for key in parser_keys:
        if key in matched_keys: continue
        names = sorted(by_key[key])
        unused.append({'tag': names[0], 'names': names, 'scripts': sorted({q['script'] for lst in by_key[key].values() for q in lst}),
                       'lines': sorted({(q['script'], q['line']) for lst in by_key[key].values() for q in lst})[:10]})
    owners = {}
    for key, names in by_key.items():
        owners[key] = sorted({(q['script_index'], q['script']) for lst in names.values() for q in lst})
    used_keys = set(tags)
    collisions = [{'key': key, 'tag': sorted(by_key[key])[0], 'scripts': [s for _, s in scripts], 'used': key in used_keys}
                  for key, scripts in sorted(owners.items()) if len(scripts) > 1]
    return result, unused, collisions


def registry(data):
    if not isinstance(data, Index): data = Index(data)
    parsers = parsers_in(data)
    use_rows, total = [], 0
    for item in uses(data):
        total += 1
        if total > MAX_USES: raise ValueError('Notetag use budget exceeded; no complete result produced')
        use_rows.append(item)
    tags, unused, collisions = cross_reference(use_rows, parsers)
    if len(tags) > MAX_TAGS: raise ValueError('Distinct tag budget exceeded; no complete result produced')
    data.unchanged()
    opaque = [p for p in parsers if p['opaque']]
    status = lambda s: sum(1 for t in tags if t['status'] == s)
    result = {'version': VERSION, 'read_only': True, 'mutation_authorized': False, 'heuristic': True, 'coverage_complete': True,
              'counts': {'tag_uses': total, 'distinct_tags': len(tags), 'recognized': status('recognized'), 'unrecognized': status('unrecognized'),
                         'case_mismatch': sum(1 for t in tags if t['case_mismatches']), 'parser_patterns': len(parsers),
                         'opaque_parsers': len(opaque), 'unused_parser_tags': len(unused), 'collisions': len(collisions)},
              'tags': tags, 'parsers': parsers, 'opaque_parsers': opaque, 'unused_parser_tags': unused,
              'possible_collisions': collisions, 'limits': LIMITS}
    if len((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')) > MAX_RESULT_BYTES: raise ValueError('Result budget exceeded; no complete result produced')
    return result


def review_required(result):
    return bool(result['counts']['unrecognized'] or result['counts']['case_mismatch'])


def markdown(result):
    c = result['counts']
    lines = ['# VX Ace notetag registry', '', 'Heuristic static inspection: evidence for review, not proof of behavior. See JSON for full evidence.', '',
             'Counts: ' + json.dumps(c), '']
    def section(title, rows, fmt):
        lines.extend(['## ' + title, ''])
        lines.extend([fmt(r) for r in rows[:MD_ROWS]] or ['- none'])
        if len(rows) > MD_ROWS: lines.append('- ... %d more in JSON' % (len(rows) - MD_ROWS))
        lines.append('')
    def where(t):
        e = t['evidence'][0]; return '%s %s %s' % (e['source'], e['file'], e['path'])
    section('Unrecognized tags', [t for t in result['tags'] if t['status'] == 'unrecognized'],
            lambda t: '- `%s` x%d (%s)%s' % (t['tag'], t['use_count'], where(t), ' - maybe: ' + ', '.join('`%s`' % s['parser_tag'] for s in t['suggestions']) if t['suggestions'] else ''))
    section('Case mismatches (parser lacks /i)', [t for t in result['tags'] if t['case_mismatches']],
            lambda t: '- `%s` written as %s; parsers: %s' % (t['tag'], ', '.join(t['case_mismatches']), ', '.join(sorted({p['script'] for p in t['parsers']}))))
    section('Possible collisions (parsed in several scripts)', result['possible_collisions'],
            lambda r: '- `%s` in %s%s' % (r['tag'], ', '.join(r['scripts']), '' if r['used'] else ' (unused)'))
    section('Recognized tags', [t for t in result['tags'] if t['status'] == 'recognized'],
            lambda t: '- `%s` x%d -> %s' % (t['tag'], t['use_count'], ', '.join(sorted({p['script'] for p in t['parsers']}))))
    section('Opaque parser patterns', result['opaque_parsers'],
            lambda p: '- %s:%d `%s` (%s)' % (p['script'], p['line'], p['pattern'], p['opaque_reason']))
    section('Parser tags never used (informational)', result['unused_parser_tags'],
            lambda r: '- `%s` in %s' % (r['tag'], ', '.join(r['scripts'])))
    lines += ['## Limits', ''] + ['- ' + x for x in result['limits']]
    return '\n'.join(lines) + '\n'


def run(index, project, json_path=None, markdown_path=None):
    """CLI transaction mirroring vxace_index_query.execute for explicit report files."""
    project = unlinked(project)
    if project.is_file() and project.suffix.lower() == '.rvproj2': project = project.parent
    if not (project / 'Data').is_dir(): raise ValueError('Expected a VX Ace project')
    data = Index(index)
    outputs = [unlinked(p) for p in (json_path, markdown_path) if p is not None]
    if len(set(outputs)) != len(outputs): raise ValueError('JSON and Markdown outputs must differ')
    for out in outputs:
        if out.exists() or any(out == p or p in out.parents for p in (project, data.root)):
            raise ValueError('Use new report files outside project and index')
    manifest = data.json('manifest.json')
    files = manifest.get('files') if isinstance(manifest, dict) else None
    if not files or manifest.get('read_only') is not True or any(not isinstance(x, dict) or not re.fullmatch('[0-9a-fA-F]{64}', str(x.get('sha256', ''))) for x in files):
        raise ValueError('A hashed Project Reader manifest is required')
    before = current_inventory(project)
    if verify_fresh(data.root, project)['status'] != 'fresh': raise ValueError('Stale index; re-index the current project')
    result = registry(data)
    if current_inventory(project) != before: raise ValueError('Source project changed during analysis')
    result.update(source_unchanged=True, read_index_files_unchanged=True, source_freshness='fresh')
    if json_path is not None:
        out = unlinked(json_path); out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if markdown_path is not None:
        out = unlinked(markdown_path); out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown(result), encoding='utf-8')
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('index'); ap.add_argument('--project', required=True)
    ap.add_argument('--json', help='New JSON report file outside the project and index')
    ap.add_argument('--markdown', help='New Markdown report file outside the project and index')
    a = ap.parse_args(argv)
    try:
        r = run(a.index, a.project, a.json, a.markdown)
    except Exception as exc:
        print('Notetag registry refused: ' + str(exc), file=sys.stderr); return 2
    review = review_required(r)
    print(json.dumps({'status': 'review_required' if review else 'ok', 'counts': r['counts']}))
    return 3 if review else 0


if __name__ == '__main__': raise SystemExit(main())
