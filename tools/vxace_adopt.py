#!/usr/bin/env python3
"""Adopt a reviewed, tested staged copy into the real VX Ace project, with backup and undo.

This is the ONLY VX Ace tool that writes to a working project, and only when the user runs `apply`
or `undo` explicitly. `plan` and `status` are read-only.
"""
from __future__ import annotations
import argparse, datetime, fnmatch, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vxace_index_query import unlinked  # noqa: E402

VERSION = '1.0.0'
SMOKE_SLOT_NAME = 'VXA Smoke Harness'
PROCESS_NAMES = ('rpgvxace.exe', 'game.exe')
EXCLUDED_NAMES = ('save*.rvdata2', 'vxa_smoke_*.txt', 'playtest_log.txt')
EXCLUDED_TOP_DIRS = ('backups',)


class Refused(Exception):
    """A deliberate refusal; carries a reason code and optional detail list."""
    def __init__(self, reason, message, details=None):
        super().__init__(message)
        self.reason, self.details = reason, details or []


# ---------------------------------------------------------------- helpers
def sha256_bytes(raw): return hashlib.sha256(raw).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def canonical(obj): return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
def digest(obj): return sha256_bytes(canonical(obj).encode('utf-8'))
def load_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def dump_json(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def utc_now(): return datetime.datetime.now(datetime.timezone.utc)


def safe_rel(value):
    if not isinstance(value, str) or not value: raise ValueError(f'unsafe relative path: {value!r}')
    p = Path(value)
    if p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value:
        raise ValueError(f'unsafe relative path: {value}')
    return p.as_posix()


def excluded(rel):
    parts = rel.split('/')
    if parts[0].lower() in EXCLUDED_TOP_DIRS and len(parts) > 1: return True
    name = parts[-1].lower()
    return any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_NAMES)


def inventory(root, use_exclusions=True):
    """{relative posix path: sha256}. Refuses links/junctions anywhere in the tree."""
    root = Path(root); out = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in list(dirnames) + filenames:
            full = Path(dirpath) / name
            attrs = full.lstat()
            if full.is_symlink() or getattr(attrs, 'st_file_attributes', 0) & 0x400:
                raise Refused('linked_path', f'links or junctions are refused: {full}')
        for name in filenames:
            full = Path(dirpath) / name; rel = full.relative_to(root).as_posix()
            if use_exclusions and excluded(rel): continue
            out[rel] = sha256_file(full)
    return out


def inside(child, parent):
    child, parent = Path(child).resolve(), Path(parent).resolve()
    return child == parent or parent in child.parents


def check_project(project):
    project = Path(project)
    if project.is_file() and project.name.lower() in ('game.rvproj2', 'game.ini'): project = project.parent
    project = unlinked(project)
    if not project.is_dir() or not (project / 'Data').is_dir():
        raise ValueError('PROJECT must be a VX Ace project folder containing Data/')
    if not ((project / 'Game.rvproj2').is_file() or (project / 'Game.ini').is_file()):
        raise ValueError('PROJECT must contain Game.rvproj2 or Game.ini')
    return project


def running_processes():
    """Lower-cased names of running processes. Module-level so tests can patch it."""
    if sys.platform == 'win32':
        p = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True)
        if p.returncode: raise OSError('tasklist failed: ' + p.stderr.strip())
        names = []
        for line in p.stdout.splitlines():
            line = line.strip()
            if line.startswith('"'): names.append(line.split('","')[0].strip('"').lower())
        return names
    p = subprocess.run(['ps', '-A', '-o', 'comm='], capture_output=True, text=True)
    if p.returncode: raise OSError('ps failed: ' + p.stderr.strip())
    return [os.path.basename(x.strip()).lower() for x in p.stdout.splitlines() if x.strip()]


def refuse_if_running():
    try:
        names = running_processes()
    except OSError as error:
        raise Refused('process_check_failed', f'cannot verify that the editor/game is closed: {error}')
    hits = sorted({n for n in names if n in PROCESS_NAMES})
    if hits:
        raise Refused('editor_running', 'close RPG Maker VX Ace and any running game first; found: ' + ', '.join(hits), hits)


def write_atomic(dest, data):
    """Write bytes via a temp file in the same directory, then os.replace (atomic per file)."""
    _atomic(Path(dest), data)


def _atomic(dest, data):
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.vxace-adopt-', suffix='.tmp', dir=dest.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, dest)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


# ---------------------------------------------------------------- plan
def load_audit(path):
    path = Path(path)
    if path.is_dir(): path = path / 'audit.json'
    path = unlinked(path)
    if not path.is_file(): raise ValueError(f'audit not found: {path}')
    audit = load_json(path)
    if audit.get('status') != 'ok' or not isinstance(audit.get('changes'), list) or not audit['changes']:
        raise Refused('bad_audit', f'audit is not a successful copy-patcher audit: {path}')
    return path, audit


def declared_state(audits):
    """Walk audit change records in order. Returns {path: {'before': sha|None, 'after': sha}}."""
    state = {}
    def note(target, before, after, where):
        target = safe_rel(target)
        if target in state:
            if state[target]['after'] != before:
                raise Refused('broken_chain', f'audit chain broken for {target} ({where})')
            state[target]['after'] = after
        else:
            state[target] = {'before': before, 'after': after}
    for path, audit in audits:
        for record in audit['changes']:
            note(record['target'], record['before_sha256'], record['after_sha256'], path)
            new_map = record.get('new_map')
            if new_map: note(new_map['target'], None, new_map['sha256'], path)
    return state


def plan(project, copy, audit_paths, recipe_report, output):
    project = check_project(project)
    output = unlinked(output)
    warnings = []
    recipe_info = None
    if recipe_report:
        rpath = unlinked(recipe_report)
        report = load_json(rpath)
        if report.get('status') != 'pass' or not report.get('final_copy') or not report.get('original_unchanged'):
            raise Refused('bad_recipe', 'recipe report is not a passing report with an unchanged original')
        if os.path.normcase(str(Path(report['project']).resolve())) != os.path.normcase(str(project)):
            raise Refused('wrong_project', 'recipe report was made for a different project: ' + str(report['project']))
        if copy is None: copy = report['final_copy']
        elif os.path.normcase(str(Path(copy).resolve())) != os.path.normcase(str(Path(report['final_copy']).resolve())):
            raise Refused('wrong_copy', 'COPY is not the recipe final copy: ' + str(report['final_copy']))
        steps = report.get('steps') or []
        if not steps or any(not s.get('audit') for s in steps):
            raise Refused('bad_recipe', 'every recipe step needs an audit')
        audit_paths = [s['audit'] for s in steps]
        recipe_info = {'report': str(rpath), 'report_sha256': sha256_file(rpath), 'steps': len(steps)}
    if copy is None: raise ValueError('--copy is required unless --recipe is given')
    if not audit_paths: raise ValueError('at least one --audit is required unless --recipe is given')
    copy = unlinked(copy)
    if not copy.is_dir(): raise ValueError('staged copy folder not found')
    if inside(copy, project) or inside(project, copy): raise Refused('nested_paths', 'COPY and PROJECT must not contain each other')
    if inside(output, project) or inside(output, copy): raise Refused('nested_paths', 'plan output must be outside PROJECT and COPY')
    if (output / 'adopt-plan.json').exists(): raise ValueError('adopt-plan.json already exists in the output folder')

    audits = [load_audit(a) for a in audit_paths]
    for path, audit in audits:
        cp = audit.get('copy_path')
        if cp and os.path.normcase(str(Path(cp).resolve())) != os.path.normcase(str(copy)) and not recipe_report:
            warnings.append(f'audit {path.name} was made for a copy at a different path ({cp}); hashes are what is verified')
    state = declared_state(audits)

    project_inv = inventory(project); copy_inv = inventory(copy)
    scripts = copy / 'Data' / 'Scripts.rvdata2'
    if scripts.is_file() and SMOKE_SLOT_NAME.encode('utf-8') in scripts.read_bytes():
        raise Refused('smoke_harness', 'the copy contains the smoke harness script slot; a smoke-test copy must never be adopted')

    declared = {rel: s for rel, s in state.items() if s['before'] != s['after']}
    problems = []
    for rel, s in sorted(declared.items()):
        have = project_inv.get(rel)
        if have != s['before']:
            problems.append(f'{rel}: project is {"absent" if have is None else have[:12]}, audit expected {"absent" if s["before"] is None else s["before"][:12]}')
    if problems: raise Refused('source_drift', 'files drifted in PROJECT since the audits were made', problems)

    differing = sorted(r for r in set(project_inv) | set(copy_inv) if project_inv.get(r) != copy_inv.get(r))
    undeclared = [r for r in differing if r not in declared]
    if undeclared:
        raise Refused('undeclared_change', 'COPY differs from PROJECT in files the audits do not declare '
                      '(project edited since staging, or copy modified afterwards)', undeclared)
    missing = [r for r in sorted(declared) if r not in differing]
    if missing: raise Refused('missing_change', 'declared changes are not present in COPY', missing)
    wrong = [f'{r}: copy {copy_inv.get(r, "absent")[:12]}, audit recorded {declared[r]["after"][:12]}' for r in sorted(declared) if copy_inv.get(r) != declared[r]['after']]
    if wrong: raise Refused('hash_mismatch', 'COPY files do not match the audits\' post-change hashes', wrong)

    files = []
    for rel in sorted(declared):
        files.append({'path': rel, 'action': 'create' if declared[rel]['before'] is None else 'replace',
                      'project_sha256': declared[rel]['before'], 'copy_sha256': declared[rel]['after'],
                      'size': (copy / rel).stat().st_size})
    warnings.insert(0, 'close RPG Maker VX Ace and any running game before apply')
    warnings.append('Save*.rvdata2 files, smoke artifacts and Backups/ are neither compared nor touched')
    body = {'version': VERSION, 'project': str(project), 'copy': str(copy), 'files': files,
            'audits': [{'path': str(p), 'sha256': sha256_file(p), 'title': a.get('title'), 'changes': len(a['changes'])} for p, a in audits],
            'recipe': recipe_info, 'warnings': warnings}
    result = {'plan_id': digest(body), **body}
    dump_json(output / 'adopt-plan.json', result)
    (output / 'adopt-plan.md').write_text(render_plan(result), encoding='utf-8')
    return result


def render_plan(p):
    lines = [f'# Adoption plan `{p["plan_id"]}`', '', f'- Project: `{p["project"]}`', f'- Staged copy: `{p["copy"]}`',
             f'- Files: **{len(p["files"])}**', '', '## Files', '', '| Action | Path | Size | Project sha256 | Copy sha256 |', '|---|---|---|---|---|']
    for f in p['files']:
        lines.append(f'| {f["action"]} | `{f["path"]}` | {f["size"]} | {(f["project_sha256"] or "-")[:12]} | {f["copy_sha256"][:12]} |')
    lines += ['', '## Audits', '']
    lines += [f'- `{a["path"]}` ({a["changes"]} change(s), {a["title"]})' for a in p['audits']]
    lines += ['', '## Warnings', ''] + [f'- {w}' for w in p['warnings']]
    lines += ['', '## Apply', '', '```', f'python tools/vxace_adopt.py apply "{p["project"]}" --plan <this folder>/adopt-plan.json --backup-root <BACKUP_ROOT> --confirm {p["plan_id"]}', '```', '']
    return '\n'.join(lines)


# ---------------------------------------------------------------- apply
def load_plan(path):
    plan_doc = load_json(path)
    body = {k: v for k, v in plan_doc.items() if k != 'plan_id'}
    if digest(body) != plan_doc.get('plan_id'): raise Refused('plan_tampered', 'plan content does not match its plan_id')
    for f in plan_doc['files']: safe_rel(f['path'])
    return plan_doc


def check_backup_root(backup_root, project, copy=None):
    root = unlinked(backup_root)
    if inside(root, project): raise Refused('nested_paths', 'BACKUP_ROOT must be outside PROJECT')
    if copy is not None and inside(root, copy): raise Refused('nested_paths', 'BACKUP_ROOT must be outside the staged copy')
    return root


def apply(project, plan_path, backup_root, confirm):
    project = check_project(project)
    plan_doc = load_plan(plan_path)
    if confirm != plan_doc['plan_id']: raise Refused('wrong_confirm', '--confirm must equal the plan_id')
    if os.path.normcase(str(Path(plan_doc['project']).resolve())) != os.path.normcase(str(project)):
        raise Refused('wrong_project', 'plan was made for a different project: ' + plan_doc['project'])
    copy = unlinked(plan_doc['copy'])
    backup_root = check_backup_root(backup_root, project, copy)
    refuse_if_running()

    # Re-verify everything immediately before writing.
    payloads, problems = {}, []
    for f in plan_doc['files']:
        rel = f['path']; dest = unlinked(project / rel); src = unlinked(copy / rel)
        if not src.is_file(): problems.append(f'{rel}: missing from staged copy'); continue
        raw = src.read_bytes()
        if sha256_bytes(raw) != f['copy_sha256']: problems.append(f'{rel}: staged copy changed since planning')
        have = sha256_file(dest) if dest.is_file() else None
        if dest.exists() and not dest.is_file(): problems.append(f'{rel}: project path is not a file')
        elif have != f['project_sha256']: problems.append(f'{rel}: project changed since planning')
        payloads[rel] = raw
    if problems: raise Refused('stale_plan', 'plan no longer matches PROJECT/COPY; re-run plan', problems)

    stamp = utc_now().strftime('%Y%m%dT%H%M%SZ')
    backup_dir = backup_root / f'{stamp}-{plan_doc["plan_id"][:12]}'
    if backup_dir.exists(): raise Refused('backup_exists', f'backup folder already exists: {backup_dir}')
    backups = {}
    for f in plan_doc['files']:
        if f['action'] != 'replace': continue
        rel = f['path']; raw = (project / rel).read_bytes()
        if sha256_bytes(raw) != f['project_sha256']: raise Refused('stale_plan', f'{rel}: project changed during backup')
        _atomic(backup_dir / 'files' / rel, raw)
        if sha256_file(backup_dir / 'files' / rel) != f['project_sha256']: raise Refused('backup_failed', f'backup verification failed for {rel}')
        backups[rel] = raw
    created_dirs = sorted({str(Path(f['path']).parent.as_posix()) for f in plan_doc['files']
                           if f['action'] == 'create' and not (project / Path(f['path']).parent).is_dir()})
    record_body = {'version': VERSION, 'project': str(project), 'plan_id': plan_doc['plan_id'], 'created_utc': utc_now().isoformat(),
                   'backup_dir': str(backup_dir), 'plan': plan_doc, 'created_dirs': created_dirs,
                   'files': [{'path': f['path'], 'action': f['action'], 'before_sha256': f['project_sha256'], 'after_sha256': f['copy_sha256']} for f in plan_doc['files']]}
    record = {'record_id': digest(record_body), **record_body}
    dump_json(backup_dir / 'adopt-record.json', record)

    written = []
    try:
        for f in plan_doc['files']:
            write_atomic(project / f['path'], payloads[f['path']]); written.append(f)
        bad = [f['path'] for f in plan_doc['files']
               if not (project / f['path']).is_file() or sha256_file(project / f['path']) != f['copy_sha256']]
        if bad: raise RuntimeError('post-write verification failed: ' + ', '.join(bad))
    except BaseException as error:
        failures = rollback(project, plan_doc['files'], written, backups, created_dirs)
        status = {'status': 'rolled_back' if not failures else 'rollback_incomplete', 'reason': str(error),
                  'rollback_problems': failures, 'backup_dir': str(backup_dir)}
        raise Refused('write_failed', json.dumps(status), failures) from error
    return {'status': 'applied', 'plan_id': plan_doc['plan_id'], 'record_id': record['record_id'], 'files': len(plan_doc['files']),
            'backup_dir': str(backup_dir), 'record': str(backup_dir / 'adopt-record.json')}


def rollback(project, files, written, backups, created_dirs):
    """Restore every file touched (the one that failed mid-way included). Returns a list of problems."""
    problems = []
    for f in reversed(files):
        rel = f['path']; dest = project / rel
        try:
            if f['action'] == 'replace':
                if not dest.is_file() or sha256_file(dest) != f['project_sha256']: _atomic(dest, backups[rel])
                if sha256_file(dest) != f['project_sha256']: problems.append(f'{rel}: not restored')
            elif dest.is_file():
                dest.unlink()
        except OSError as error:
            problems.append(f'{rel}: {error}')
    remove_created_dirs(project, created_dirs)
    return problems


def remove_created_dirs(project, created_dirs):
    """Remove directories adoption created (deepest first), only while empty."""
    for rel in sorted(created_dirs, key=lambda x: -len(x)):
        d = project / rel
        while d != project and d.is_dir() and not any(d.iterdir()):
            try: d.rmdir()
            except OSError: break
            d = d.parent


# ---------------------------------------------------------------- undo / status
def load_record(path):
    record = load_json(path)
    body = {k: v for k, v in record.items() if k != 'record_id'}
    if digest(body) != record.get('record_id'): raise Refused('record_tampered', 'record content does not match its record_id')
    for f in record['files']: safe_rel(f['path'])
    return record


def current_hash(project, rel):
    p = unlinked(project / rel)
    return sha256_file(p) if p.is_file() else None


def undo(project, record_path, confirm):
    project = check_project(project)
    record_path = unlinked(record_path)
    record = load_record(record_path)
    if confirm != record['record_id']: raise Refused('wrong_confirm', '--confirm must equal the record_id')
    if os.path.normcase(str(Path(record['project']).resolve())) != os.path.normcase(str(project)):
        raise Refused('wrong_project', 'record was made for a different project: ' + record['project'])
    refuse_if_running()
    backup_dir = record_path.parent
    changed = [f'{f["path"]}: now {(current_hash(project, f["path"]) or "absent")[:12]}, adopted {f["after_sha256"][:12]}'
               for f in record['files'] if current_hash(project, f['path']) != f['after_sha256']]
    if changed: raise Refused('project_changed', 'files changed since adoption; undo would lose those edits', changed)
    originals, current = {}, {}
    for f in record['files']:
        current[f['path']] = (project / f['path']).read_bytes()
        if f['action'] == 'replace':
            b = backup_dir / 'files' / f['path']
            if not b.is_file() or sha256_file(b) != f['before_sha256']:
                raise Refused('backup_invalid', f'backup missing or altered: {f["path"]}')
            originals[f['path']] = b.read_bytes()
    done = []
    try:
        for f in record['files']:
            if f['action'] == 'replace': write_atomic(project / f['path'], originals[f['path']])
            else: (project / f['path']).unlink()
            done.append(f)
        bad = [f['path'] for f in record['files'] if current_hash(project, f['path']) != f['before_sha256']]
        if bad: raise RuntimeError('post-restore verification failed: ' + ', '.join(bad))
    except BaseException as error:
        problems = []
        for f in reversed(record['files']):
            try:
                if current_hash(project, f['path']) != f['after_sha256']: _atomic(project / f['path'], current[f['path']])
            except OSError as e: problems.append(f'{f["path"]}: {e}')
        raise Refused('undo_failed', json.dumps({'status': 'undo_reverted', 'reason': str(error), 'problems': problems}), problems) from error
    remove_created_dirs(project, record.get('created_dirs', []))
    dump_json(backup_dir / 'adopt-undone.json', {'record_id': record['record_id'], 'undone_utc': utc_now().isoformat()})
    return {'status': 'restored', 'record_id': record['record_id'], 'files': len(record['files'])}


def status(project, record_path):
    project = check_project(project)
    record = load_record(unlinked(record_path))
    if os.path.normcase(str(Path(record['project']).resolve())) != os.path.normcase(str(project)):
        raise Refused('wrong_project', 'record was made for a different project: ' + record['project'])
    adopted, original, modified = [], [], []
    for f in record['files']:
        have = current_hash(project, f['path'])
        if have == f['after_sha256']: adopted.append(f['path'])
        elif have == f['before_sha256']: original.append(f['path'])
        else: modified.append(f['path'])
    if modified: state = 'modified'
    elif adopted and original: state = 'mixed'
    elif adopted: state = 'adopted'
    else: state = 'original'
    return {'status': state, 'record_id': record['record_id'], 'adopted': adopted, 'original': original, 'modified': modified,
            'editor_running': bool(set(running_processes()) & set(PROCESS_NAMES)) if _can_check() else None}


def _can_check():
    try: running_processes(); return True
    except OSError: return False


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan', help='read-only: work out the adoptable changes')
    p.add_argument('project'); p.add_argument('--copy'); p.add_argument('--audit', action='append', default=[])
    p.add_argument('--recipe', help='recipe-report.json (supplies the audits and final copy)'); p.add_argument('--output', required=True)
    p = sub.add_parser('apply', help='back up and write the planned files into PROJECT')
    p.add_argument('project'); p.add_argument('--plan', required=True); p.add_argument('--backup-root', required=True); p.add_argument('--confirm', required=True)
    p = sub.add_parser('undo', help='restore the backed-up files')
    p.add_argument('project'); p.add_argument('--record', required=True); p.add_argument('--confirm', required=True)
    p = sub.add_parser('status', help='report whether PROJECT still matches the adopted state')
    p.add_argument('project'); p.add_argument('--record', required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'plan':
            r = plan(a.project, a.copy, a.audit, a.recipe, a.output)
            out = {'status': 'ok', 'plan_id': r['plan_id'], 'files': len(r['files']), 'plan': str(Path(a.output) / 'adopt-plan.json')}
        elif a.cmd == 'apply': out = apply(a.project, a.plan, a.backup_root, a.confirm)
        elif a.cmd == 'undo': out = undo(a.project, a.record, a.confirm)
        else:
            out = status(a.project, a.record)
            print(json.dumps(out)); return 0 if out['status'] in ('adopted', 'original') else 3
    except Refused as e:
        print(json.dumps({'status': 'refused', 'reason': e.reason, 'detail': str(e), 'items': e.details}), file=sys.stderr); return 3
    except (ValueError, OSError, KeyError) as e:
        print(json.dumps({'status': 'error', 'reason': str(e)}), file=sys.stderr); return 2
    print(json.dumps(out)); return 0


if __name__ == '__main__': raise SystemExit(main())
