"""Shared bounded, read-only index access for search and event diagnostics."""
from __future__ import annotations
import hashlib
import json
import re
import stat
from pathlib import Path
from vxace_copy_patcher import verify_fresh, current_inventory

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_STEPS = 500000
MAX_FILES = 4096


def unlinked(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            attrs = part.lstat()
            if part.is_symlink() or getattr(attrs, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
                raise ValueError('Linked input/output paths are refused')
    return path.resolve()


class Index:
    def __init__(self, root):
        self.root = unlinked(root)
        self.steps = self.bytes = self.files = 0
        self.hashes = {}
        self.selections = {}
        self.project = self.json('project.json')
        if not isinstance(self.project, dict) or self.project.get('errors'):
            raise ValueError('A complete Project Reader index is required')
        from vxace_project_reader import DB_FILES
        for name in self.project.get('database_files_decoded', []):
            if name not in DB_FILES or not self.path('database/'+DB_FILES[name]).is_file():
                raise ValueError('Decoded database files are missing from the index')
        maps=self.paths('maps','map-*.json')
        if 'map_count' in self.project and self.project['map_count']!=len(maps):
            raise ValueError('Decoded maps are missing from the index')

    def spend(self, amount=1):
        self.steps += amount
        if self.steps > MAX_STEPS:
            raise ValueError('Index walk budget exceeded; no complete result produced')

    def path(self, relative):
        relative = Path(relative)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe index-relative path')
        path = unlinked(self.root / relative)
        if self.root not in path.parents:
            raise ValueError('Index path escapes input root')
        return path

    def text(self, relative):
        path = self.path(relative)
        size = path.stat().st_size
        if size > MAX_FILE_BYTES or self.bytes + size > MAX_TOTAL_BYTES or self.files >= MAX_FILES:
            raise ValueError('Index file/byte budget exceeded; no complete result produced')
        raw = path.read_bytes()
        if len(raw) > MAX_FILE_BYTES or self.bytes + len(raw) > MAX_TOTAL_BYTES:
            raise ValueError('Index grew beyond byte budget')
        self.bytes += len(raw); self.files += 1
        digest=hashlib.sha256(raw).hexdigest()
        if path in self.hashes and self.hashes[path]!=digest: raise ValueError('Input index changed between reads')
        self.hashes[path] = digest
        return raw.decode('utf-8', 'strict')

    def json(self, relative):
        return json.loads(self.text(relative))

    def paths(self, directory, pattern='*.json'):
        directory = self.path(directory)
        paths = sorted(directory.glob(pattern))
        if len(paths) > MAX_FILES:
            raise ValueError('Index file count budget exceeded')
        for path in paths:
            self.path(path.relative_to(self.root))
        selection=tuple(p.name for p in paths)
        key=(directory,pattern)
        if key in self.selections and self.selections[key]!=selection: raise ValueError('Input index file set changed')
        self.selections[key]=selection
        return [p.relative_to(self.root).as_posix() for p in paths]

    def unchanged(self):
        for path, digest in self.hashes.items():
            unlinked(path)
            if not path.is_file() or path.stat().st_size>MAX_FILE_BYTES or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError('Input index changed during analysis')
        for (directory,pattern),names in self.selections.items():
            if tuple(p.name for p in sorted(directory.glob(pattern)))!=names: raise ValueError('Input index file set changed')

    def strings(self, value, path=()):
        self.spend()
        if len(path) > 128:
            raise ValueError('Index nesting budget exceeded')
        if isinstance(value, str):
            yield list(path), value
        elif isinstance(value, dict):
            for key, item in value.items():
                if len(key)>256: raise ValueError('Oversized evidence key')
                if not key.startswith('__'):
                    yield from self.strings(item, (*path, key))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                yield from self.strings(item, (*path, i))

    def event_lists(self):
        for file in self.paths('maps', 'map-*.json'):
            match = re.fullmatch(r'maps/map-(\d{3})\.json', file)
            if not match:
                raise ValueError('Unexpected normalized map filename')
            root = self.json(file)
            if not isinstance(root, dict) or not isinstance(root.get('events'), dict):
                raise ValueError('Map events were not fully decoded')
            for key, event in sorted(root['events'].items()):
                self.spend()
                if not isinstance(event, dict) or event.get('__class__')!='RPG::Event' or type(event.get('id')) is not int or str(event['id']) != key:
                    raise ValueError('Ambiguous or opaque map event')
                pages = event.get('pages')
                if not isinstance(pages, list):
                    raise ValueError('Opaque map event pages')
                for n, page in enumerate(pages, 1):
                    self.spend()
                    if not isinstance(page, dict) or not isinstance(page.get('list'), list):
                        raise ValueError('Opaque event page/command list')
                    yield {'scope':'map','map_id':int(match[1]),'event_id':event['id'],'page':n}, file, ['events',key,'pages',n-1], page, pages
        for scope, file in (('common_event','database/common-events.json'),('troop','database/troops.json')):
            if not self.path(file).is_file():
                continue
            root = self.json(file)
            if not isinstance(root, list):
                raise ValueError('Expected normalized event database array')
            seen = set()
            for slot, owner in enumerate(root):
                self.spend()
                if owner is None:
                    continue
                if not isinstance(owner, dict) or owner.get('__class__')!=('RPG::CommonEvent' if scope=='common_event' else 'RPG::Troop') or type(owner.get('id')) is not int or owner['id'] in seen:
                    raise ValueError('Ambiguous or opaque database event')
                seen.add(owner['id'])
                pages = [owner] if scope == 'common_event' else owner.get('pages')
                if not isinstance(pages, list):
                    raise ValueError('Opaque troop page array')
                for n, page in enumerate(pages, 1):
                    self.spend()
                    if not isinstance(page, dict) or not isinstance(page.get('list'), list):
                        raise ValueError('Opaque database command list')
                    loc = {'scope':scope, 'common_event_id' if scope=='common_event' else 'troop_id':owner['id']}
                    path = [slot]
                    if scope=='troop': loc['page']=n; path += ['pages',n-1]
                    yield loc, file, path, page, pages


def execute(index, project, output, analyze, basename):
    """CLI transaction: freshness + input/source integrity, then external report."""
    project = unlinked(project)
    if project.is_file() and project.suffix.lower()=='.rvproj2': project=project.parent
    if not (project/'Data').is_dir(): raise ValueError('Expected a VX Ace project')
    data = Index(index)
    output = unlinked(output)
    if output.exists() or any(output==p or p in output.parents for p in (project,data.root)):
        raise ValueError('Use a new report directory outside project and index')
    manifest = data.json('manifest.json')
    files = manifest.get('files') if isinstance(manifest,dict) else None
    if not files or manifest.get('read_only') is not True or any(not isinstance(x,dict) or not re.fullmatch('[0-9a-fA-F]{64}',str(x.get('sha256',''))) for x in files):
        raise ValueError('A hashed Project Reader manifest is required')
    before = current_inventory(project)
    if verify_fresh(data.root,project)['status']!='fresh': raise ValueError('Stale index; re-index the current project')
    result = analyze(data)
    data.unchanged()
    if current_inventory(project)!=before: raise ValueError('Source project changed during analysis')
    result.update(source_unchanged=True,read_index_files_unchanged=True,source_freshness='fresh',read_only=True,mutation_authorized=False)
    output.mkdir(parents=True)
    (output/(basename+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result
